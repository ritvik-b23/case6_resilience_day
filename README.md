# Case 6 — Resilience Day

> A Docker Compose microservice system that demonstrates observability, chaos testing, and resilience patterns.

[![CI](https://github.com/your-org/case6-resilience-day/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/case6-resilience-day/actions/workflows/ci.yml)

---

## Live / Local URLs

| Service | URL |
|---------|-----|
| API via Nginx | http://localhost:8080 |
| Grafana Dashboard | http://localhost:3000 (admin/admin) |
| Prometheus | http://localhost:9090 |
| orders-service (direct) | http://localhost:8001 |
| inventory-service (direct) | http://localhost:8002 |

---

## Architecture

```
Client
  │
  ▼
Nginx :8080  (reverse proxy)
  ├──▶ orders-service :8001
  │         │
  │         ▼
  │    inventory-service :8002
  │         │
  └─────────┘
       │           │
    Metrics     Metrics
       │           │
       ▼           ▼
   Prometheus :9090
       │
       ▼
   Grafana :3000
```

---

## Case Requirement Mapping

| Requirement | Implementation |
|-------------|----------------|
| Two services communicating | orders-service calls inventory-service via httpx |
| Reverse proxy | Nginx (`infra/nginx/nginx.conf`) routing `/orders` and `/inventory/` |
| Structured logging | `python-json-logger` with request_id, latency_ms, status_code in both services |
| Prometheus metrics | `/metrics` endpoint on both services; prometheus.yml scrape config |
| Grafana dashboard | Auto-provisioned dashboard (`infra/grafana/dashboards/resilience-dashboard.json`) |
| Chaos experiments | `POST /chaos/mode` endpoint + scripts in `scripts/` |
| Timeout | httpx `Timeout(1.0)` in `resilience.py` |
| Retry with backoff | tenacity `AsyncRetrying` (2 retries, 0.5s wait) in `resilience.py` |
| Circuit breaker | pybreaker `CircuitBreaker` (fail_max=3, reset=15s) in `resilience.py` |
| Fallback response | Returns `status: pending` with message when CB open or dependency fails |
| Before/after evidence | `docs/INCIDENT_WRITEUP.md` |
| Documentation | `docs/` directory + `EXPLANATION.md` |

---

## How to Run

### 1. Start the full stack

```bash
docker compose up --build
```

All five containers start: orders-service, inventory-service, nginx, prometheus, grafana.

Wait ~20 seconds for health checks to pass, then verify:

```bash
curl http://localhost:8080/health/orders
curl http://localhost:8080/health/inventory
```

### 2. Happy path order request

```bash
curl -X POST http://localhost:8080/orders \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "C001", "product_id": "P001", "quantity": 2}'
```

Expected response:
```json
{
  "order_id": "abc12345",
  "status": "accepted",
  "product_id": "P001",
  "quantity": 2,
  "inventory_status": "available",
  "message": "Order accepted"
}
```

---

## Chaos Experiments

### Experiment 1: Slow dependency (timeout)

```bash
# Set inventory-service to slow mode
curl -X POST http://localhost:8080/inventory/chaos/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "slow"}'

# Send an order — should time out and return fallback within ~2s
curl -X POST http://localhost:8080/orders \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "C001", "product_id": "P001", "quantity": 1}'
```

Or use the script:
```bash
bash scripts/chaos_slow_dependency.sh
```

**Expected:** `status: pending`, response within 2 seconds, `orders_timeout_total` incrementing in Prometheus.

---

### Experiment 2: Dependency errors (retry + circuit breaker)

```bash
curl -X POST http://localhost:8080/inventory/chaos/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "error"}'
```

Send 6 requests:
```bash
bash scripts/chaos_error_dependency.sh
```

**Expected:** First requests show retries (`orders_retry_total` rises), then circuit breaker opens (`orders_circuit_breaker_open_total` increments), subsequent requests return fallback immediately.

---

### Experiment 3: Flaky dependency

```bash
bash scripts/chaos_flaky_dependency.sh
```

**Expected:** Mixed results — some requests succeed (retry recovered), others fall back.

---

### Experiment 4: Kill inventory-service

```bash
bash scripts/chaos_kill_inventory.sh
```

**Expected:** orders-service returns `status: pending` immediately. No hanging, no crash.

---

### Reset to normal

```bash
bash scripts/reset_chaos.sh
```

---

## View Metrics and Dashboard

**Grafana:** http://localhost:3000 → login `admin/admin` → Dashboards → Resilience Day

**Key panels:**
- Orders Request Rate
- Orders Error Rate (5xx)
- p95 Latency
- Inventory Dependency Calls (by outcome: success/timeout/error/circuit_open)
- Retry Count
- Timeout Count
- Fallback Count
- Circuit Breaker Opens

**Prometheus:** http://localhost:9090 → Status → Targets (both services should show UP)

Useful queries:
```promql
rate(orders_http_requests_total[1m])
orders_circuit_breaker_open_total
orders_fallback_total
histogram_quantile(0.95, rate(orders_http_request_duration_seconds_bucket[5m]))
```

---

## Running Tests

```bash
# orders-service tests
cd services/orders-service
pip install -r requirements.txt
pytest tests/ -v

# inventory-service tests
cd services/inventory-service
pip install -r requirements.txt
pytest tests/ -v
```

## Linting

```bash
ruff check services/orders-service/app
ruff check services/inventory-service/app
```

## Makefile Commands

```bash
make up           # Start all services
make down         # Stop and remove containers
make test         # Run all tests
make lint         # Run ruff linter
make happy-path   # Run happy path script
make chaos-slow   # Slow dependency experiment
make chaos-error  # Error dependency experiment
make chaos-flaky  # Flaky dependency experiment
make chaos-kill   # Kill inventory container
make reset-chaos  # Reset everything to normal
make load-test    # Send 20 requests
```

---

## Resilience Features

| Feature | Config | File |
|---------|--------|------|
| Timeout | 1.0 second | `services/orders-service/app/resilience.py` |
| Retry | 2 retries, 0.5s wait | `services/orders-service/app/resilience.py` |
| Circuit Breaker | fail_max=3, reset=15s | `services/orders-service/app/resilience.py` |
| Fallback | status=pending message | `services/orders-service/app/resilience.py` |

Resilience status endpoint:
```bash
curl http://localhost:8001/resilience/status
```

---

## What to Show in Demo Video

1. `docker compose up --build` — all 5 containers start healthy
2. Happy path order → `status: accepted`
3. Open Grafana — show all 8 panels with live data
4. `bash scripts/chaos_slow_dependency.sh` — show timeout + fallback in <2s
5. `bash scripts/chaos_error_dependency.sh` — watch retry count rise, circuit open
6. Check `curl http://localhost:8001/resilience/status` — show `circuit_breaker_state: open`
7. Grafana: show `orders_circuit_breaker_open_total = 1`, `orders_fallback_total` rising
8. `bash scripts/reset_chaos.sh` — system returns to normal
9. Happy path again → `status: accepted`

---

## Screenshots for Slide Deck

1. **Architecture diagram** — draw.io or Excalidraw version of the text diagram above
2. **Grafana dashboard** — all 8 panels visible, green state (happy path traffic)
3. **Grafana during chaos** — timeout/fallback/circuit breaker panels highlighted
4. **Terminal: chaos_error_dependency.sh output** — showing first 3 requests falling back, then immediate fallback
5. **Terminal: resilience/status** — `circuit_breaker_state: open`
6. **Prometheus targets page** — both services showing UP
7. **Structured log output** — `docker compose logs orders-service` showing JSON lines with request_id, latency_ms

---

## Known Limitations

- **Circuit breaker state is in-memory.** Restarting orders-service resets the circuit breaker. For multi-replica production deployments, use a shared Redis-backed state.
- **Fallback orders are not persisted.** `status: pending` is returned but the order is not written to a queue or database. Production would require a message queue.
- **No distributed tracing.** X-Request-ID provides correlation across two services but no timing tree. OpenTelemetry + Jaeger would complete this.
- **No alerting.** Grafana dashboard shows metrics but does not fire alerts. Prometheus alerting rules + Alertmanager would be added for production.

---

## Production Improvements

| Improvement | Tool |
|-------------|------|
| Kubernetes deployment | Helm charts |
| Distributed tracing | OpenTelemetry + Jaeger |
| Centralized log search | Grafana Loki or ELK |
| Real-time alerting | Prometheus Alertmanager + Slack/PagerDuty |
| Real load testing | k6 or Locust |
| Horizontal autoscaling | Kubernetes HPA |
| Persistent order queue | Redis Streams or AWS SQS |
| mTLS between services | Istio or manual cert setup |
