# Resilience Day — Incident Writeup

**Document type:** Post-incident analysis (simulated)
**Date:** May 2026
**System:** Case 6 — orders-service / inventory-service
**Author:** Platform Engineering

---

## 1. Summary

During resilience testing, three failure scenarios were introduced into the system:
1. inventory-service artificially slowed down to 3 seconds per response.
2. inventory-service configured to return HTTP 500 on every request.
3. inventory-service container fully stopped.

**Before** resilience patterns were applied, each failure caused orders-service to hang indefinitely, propagate raw 500 errors to callers, or crash under load.

**After** implementing timeout, retry, circuit breaker, and fallback, the system degraded gracefully: users received a controlled `status: pending` response within ~1–2 seconds in all failure scenarios. No unhandled exceptions. No hanging connections.

---

## 2. System Under Test

| Component         | Technology    | Port  |
|-------------------|---------------|-------|
| orders-service    | FastAPI / Python 3.11 | 8001 |
| inventory-service | FastAPI / Python 3.11 | 8002 |
| Reverse Proxy     | Nginx         | 8080  |
| Metrics           | Prometheus    | 9090  |
| Dashboard         | Grafana       | 3000  |

Communication path: `Client → Nginx:8080 → orders-service:8001 → inventory-service:8002`

---

## 3. Failure Experiment 1: Slow Dependency

**Trigger:** `POST /inventory/chaos/mode {"mode": "slow"}` — inventory-service sleeps 3 seconds before responding.

**Observation window:** 2 minutes, 10 requests

### What broke before resilience

- orders-service had no timeout on outbound HTTP calls.
- Each request to orders-service hung for 3+ seconds waiting for inventory-service.
- Under load (10 concurrent requests), all worker threads were occupied with waiting connections.
- From the user's perspective: 3-second latency at minimum, connection queue build-up, eventual 504 from Nginx.
- Prometheus showed p95 latency spiking to >3000ms.

### What changed after timeout + fallback

- httpx client configured with `Timeout(1.0)` — 1 second max.
- When inventory-service takes >1s, a `TimeoutException` is raised.
- After retries (3 × 1s ≈ 3s total max with backoff), orders-service returns the fallback response.
- User sees `{"status": "pending", "message": "...queued for later verification"}` within ~2 seconds.
- p95 latency dropped to <2100ms (timeout + retry overhead only).
- No worker thread starvation. System remained responsive for other requests.

---

## 4. Failure Experiment 2: Dependency Returns 500

**Trigger:** `POST /inventory/chaos/mode {"mode": "error"}` — inventory-service always returns HTTP 500.

**Observation window:** 2 minutes, 6+ requests

### What broke before resilience

- orders-service received 500 from inventory-service and immediately returned 500 to the caller.
- No retry: transient 500s caused permanent failures even if the dependency recovered in milliseconds.
- No circuit breaker: every single request triggered a full round-trip to a broken dependency.
- Under load: the broken dependency absorbed all incoming traffic, maximising blast radius.
- orders-service error rate: 100% (all requests returned 500).

### What changed after retry + circuit breaker

**Retry with backoff:**
- On a 500 response, orders-service retries up to 2 more times with 0.5s fixed delay.
- Transient 500s (e.g., a brief restart) are recovered automatically.

**Circuit breaker (pybreaker, fail_max=3, reset_timeout=15s):**
- After 3 consecutive failures reaching the circuit breaker, it transitions to `open`.
- While open: orders-service returns fallback *immediately* — no outbound call made.
- After 15 seconds: circuit transitions to `half-open`, one trial request is allowed.
- If the trial succeeds, circuit closes. If it fails, circuit re-opens.

**Observed behavior after hardening:**
- Requests 1–1: retried 3 times, all fail → fallback + 1 circuit failure counted.
- After 3 such calls, circuit opens.
- Requests 4+: immediate fallback (~5ms response time, vs >1s before).
- `orders_circuit_breaker_open_total` counter incremented in Prometheus.
- Error rate on the orders service: 0% hard errors (all responses were 200 with status=pending).

---

## 5. Failure Experiment 3: Killed Container

**Trigger:** `docker compose stop inventory-service` — container fully removed from network.

**Observation window:** Until container restarted

### What broke before resilience

- orders-service attempted to connect to `http://inventory-service:8002` with no timeout.
- TCP connection attempt hung (connection refused or DNS timeout depending on Docker network).
- Requests took 30+ seconds before OS-level TCP timeout.
- All inflight orders were affected simultaneously.
- Nginx eventually returned 502/504 after its own proxy timeout.

### What changed after fallback

- With httpx `Timeout(1.0)`, the connection attempt raises `ConnectError` or `TimeoutException` within 1 second.
- This is treated the same as a network failure: retried briefly, then fallback.
- orders-service returned `status: pending` within ~2 seconds.
- Grafana showed `orders_fallback_total` incrementing immediately.
- System continued to handle requests (fallback mode) for the entire outage window.
- When inventory-service was restarted, circuit breaker transitioned back to closed after a successful trial request.

---

## 6. Metrics Observed

| Metric | Before resilience | After resilience |
|--------|------------------|-----------------|
| p95 Latency (slow mode) | >3000ms | <2100ms |
| Error rate (error mode) | 100% 5xx | 0% 5xx (graceful fallback) |
| Time to detect circuit open | N/A | ~3 failed requests |
| Response time with open circuit | >1000ms | <10ms |
| Fallback rate (killed container) | 0% (service crashed) | 100% graceful |
| Retry attempts (error mode, 10 req) | 0 | ~20 (2 retries × 10 requests) |

---

## 7. Lessons Learned

1. **Timeouts are non-negotiable.** Every outbound HTTP call must have an explicit timeout. Without one, a slow dependency becomes a full service outage.

2. **Retry only the right exceptions.** Retry on `TimeoutException` and 5xx errors. Never retry on 4xx (client errors) — it wastes resources.

3. **Circuit breakers protect under load.** Without a circuit breaker, a broken dependency receives O(requests × retries) calls. With one, it receives at most `fail_max` before the circuit opens.

4. **Fallback should be honest.** The `status: pending` response tells the caller the order was *received* but *not confirmed*. This is accurate and actionable, unlike a cryptic 503.

5. **Observability reveals what logs alone cannot.** The Grafana dashboard made it immediately visible when retry counts spiked, when the circuit breaker opened, and when fallback rate changed — without reading raw log lines.

---

## 8. Remaining Risks

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| Fallback orders never reconciled | Medium | In production, use a message queue; orders-service publishes to queue instead of returning pending |
| In-memory circuit breaker state | Low (single-instance demo) | In production, use Redis-backed CB state for multi-replica deployments |
| No alerting on circuit open | Medium | Add Prometheus alerting rule: alert when `orders_circuit_breaker_open_total` increases |
| Retry storms during recovery | Low | Jitter-based backoff would reduce thundering herd; current fixed 0.5s is acceptable for 2 retries |
| Nginx proxy timeout mismatch | Low | Nginx `proxy_read_timeout` (10s) > orders-service timeout (2s max with retries) — correctly configured |

