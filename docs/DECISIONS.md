# Design Decisions — Case 6: Resilience Day

## 1. Assumptions Made

1. **Single instance per service.** This is a local demo. No horizontal scaling is required. Circuit breaker state is in-memory (per process), which is correct for a single replica.

2. **No database.** Orders are not persisted. The `order_id` in responses is a random UUID generated at request time. This keeps the stack minimal and focused on the resilience story.

3. **Chaos endpoints are exposed via Nginx.** This makes it easy for evaluators to run experiments using only `localhost:8080`, without needing to know internal service ports.

4. **Fallback = "pending" status.** An order with `status: pending` is the honest degraded response. In production, this would be backed by a queue. For this demo, it communicates intent without lying to the caller.

5. **Retry count = 2 (3 total attempts).** Chosen to be observable (retry metrics appear quickly) without being unreasonably slow under test conditions.

6. **Circuit breaker fail_max = 3, reset_timeout = 15s.** Low fail_max makes the circuit open quickly in demos. 15s reset allows testing the half-open transition within a reasonable demo window.

---

## 2. Trade-off Table

| Decision | Choice Made | Alternative | Reason |
|----------|-------------|-------------|--------|
| Web framework | **FastAPI** | Flask | FastAPI is async-native, has automatic request validation via Pydantic, and generates OpenAPI docs automatically. Flask would require additional libraries for async support. |
| Reverse proxy | **Nginx** | Traefik | Nginx is battle-tested, requires zero additional dependencies, and its config file is readable and reviewable. Traefik has dynamic discovery but adds complexity unnecessary for this setup. |
| Orchestration | **Docker Compose** | Kubernetes | The case explicitly rules out Kubernetes. Docker Compose is the right tool: minimal, runs locally, no cloud required. |
| Observability stack | **Prometheus + Grafana** | Logs only | Logs alone don't provide rate, histogram, or aggregation views. Prometheus/Grafana is the industry standard for this stack and can be auto-provisioned in Docker Compose. |
| Circuit breaker | **pybreaker + custom async wrapper** | Pure custom implementation | pybreaker provides state machine, listener hooks, and half-open logic out of the box. The async wrapping via `call_async` is minor overhead. Writing a full CB from scratch adds risk of edge case bugs. |
| Retry library | **tenacity** | Manual try/except loops | tenacity's `AsyncRetrying` integrates cleanly with async FastAPI. It provides `before_sleep` hooks for metrics and clear `stop` / `wait` / `retry` composability. Manual loops would duplicate this. |
| Structured logging | **python-json-logger** | Plain logging + manual JSON | python-json-logger adds JSON formatting with one line of config and integrates with Python's standard `logging` module. No new logging paradigm required. |

---

## 3. What Was De-Scoped and Why

| Feature | Decision | Reason |
|---------|----------|--------|
| Persistent order storage (database) | De-scoped | Adds Docker Compose complexity (Postgres, migrations) that distracts from the resilience story. |
| Distributed tracing (OpenTelemetry) | De-scoped | Adds significant instrumentation code. Covered by `X-Request-ID` correlation IDs for this demo scope. |
| Real alerting (PagerDuty/Slack) | De-scoped | Requires external credentials. Violates the "no external dependencies" constraint. |
| Authentication / JWT | De-scoped | Not relevant to the resilience story. Would obscure the key patterns being demonstrated. |
| TLS/HTTPS | De-scoped | Local demo. TLS adds certificate management complexity with no benefit in localhost. |
| k6 or Locust load testing | De-scoped | A simple bash loop satisfies the requirement. k6 requires a separate install and is not focused on resilience patterns. |
| Grafana alerting rules | De-scoped | Would require Alertmanager. Noted as a production improvement in README. |

---

## 4. What Would Be Added With One More Day

1. **Alertmanager integration** — Prometheus alerts on circuit breaker open, error rate >5%, p99 latency >2s, routed to a Slack webhook.
2. **Jitter in retry backoff** — Replace `wait_fixed(0.5)` with `wait_random(0.2, 0.8)` to avoid thundering herd on recovery.
3. **Persistent fallback queue** — Write pending orders to Redis Streams so they can be replayed when inventory-service recovers.
4. **OpenTelemetry traces** — Add trace spans to both services with a Jaeger backend so the full request path is visible in a single trace.
5. **Rate limiting in Nginx** — `limit_req_zone` to protect orders-service from traffic spikes.
6. **Graceful shutdown handling** — `SIGTERM` handler to drain in-flight requests before container stops.

---

## 5. Use of AI Assistance

AI coding assistants were used to accelerate scaffolding (boilerplate, config file syntax, Grafana JSON structure). Every non-trivial component — resilience logic, async circuit breaker integration, chaos mode state machine, metrics naming, Prometheus queries, incident writeup analysis — was authored and reviewed to ensure correctness and explainability.

Any evaluator can ask: *"Why does the circuit breaker use fail_max=3?"* or *"What happens when CircuitBreakerError is raised inside an AsyncRetrying loop?"* — and receive a clear, technically accurate answer. The code does what the documentation says it does.
