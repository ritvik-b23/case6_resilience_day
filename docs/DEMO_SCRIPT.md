# Demo Script — Case 6: Resilience Day

**Total duration:** ~5 minutes
**Prerequisites:** `docker compose up --build -d` already running, all containers healthy.

---

## 0:00 – 0:30 | Introduction

> "This is Case 6 — Resilience Day. The goal is to show not just that microservices work when everything is healthy, but that they *survive* when things go wrong."

> "I've built two FastAPI microservices — orders-service and inventory-service — behind an Nginx reverse proxy, with Prometheus metrics and a Grafana dashboard. Then I deliberately broke things and hardened the system against four real-world failure scenarios."

---

## 0:30 – 1:00 | Architecture Overview

> "Here's the architecture:"

```
Client → Nginx:8080 → orders-service:8001 → inventory-service:8002
                            ↓                       ↓
                         Metrics               Metrics
                            ↓                       ↓
                        Prometheus:9090 → Grafana:3000
```

> "Nginx is the single entry point. Orders-service calls inventory-service to check stock. If anything goes wrong in that call, four resilience mechanisms kick in: timeout, retry, circuit breaker, and fallback."

*Show the project directory structure briefly.*

---

## 1:00 – 1:45 | Happy Path

> "Let me show the happy path first — everything healthy."

```bash
curl -s -X POST http://localhost:8080/orders \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "C001", "product_id": "P001", "quantity": 2}' | python3 -m json.tool
```

> "The response is status=accepted, inventory_status=available. The order went through Nginx, to orders-service, to inventory-service, and back in milliseconds."

> "Notice the X-Request-ID header in both service logs — that's the correlation ID that links the request across services."

---

## 1:45 – 2:30 | Grafana Dashboard

*Open http://localhost:3000, login admin/admin, open Resilience Day Dashboard.*

> "Here's the Grafana dashboard. It's auto-provisioned from a JSON file — no manual setup needed."

> "I can see: request rate, error rate, p95 latency, inventory call outcomes, retry count, timeout count, fallback count, and circuit breaker opens."

> "Right now everything is green. Let me break that."

---

## 2:30 – 3:15 | Chaos Experiment 1: Slow Dependency

```bash
bash scripts/chaos_slow_dependency.sh
```

> "I've set inventory-service to sleep for 3 seconds on every request. Without resilience, every order would hang for 3+ seconds."

> "Watch the response times... each one returns in about 1-2 seconds instead of 3+ seconds. That's the 1-second timeout kicking in."

> "The response is status=pending — a graceful fallback, not an error. The Timeout Count panel in Grafana is now ticking up."

---

## 3:15 – 4:00 | Chaos Experiment 2: Error Dependency

```bash
bash scripts/chaos_error_dependency.sh
```

> "Now I'm making inventory-service return HTTP 500 on every call. Watch what happens as I send 6 requests."

> "Requests 1–3: each one retries twice and returns fallback. The retry count in Grafana goes up."

> "After 3 failures reach the circuit breaker, it opens. Now look at requests 4–6 — they return fallback *immediately*. No network call is made. The circuit breaker is protecting inventory-service from being hammered."

```bash
curl http://localhost:8001/resilience/status | python3 -m json.tool
```

> "The resilience status endpoint confirms: circuit_breaker_state=open."

---

## 4:00 – 4:45 | Circuit Breaker and Fallback Behavior

*Show Grafana panels: Circuit Breaker Opens = 1, Fallback Count rising, Retry Count elevated.*

> "This is exactly the story. Before resilience: 500s propagated to the user. After: the circuit opens, inventory-service gets a break, and users see a controlled pending response."

```bash
bash scripts/reset_chaos.sh
```

> "After 15 seconds, the circuit goes half-open, sends a trial request, and closes again. Here's the reset — chaos mode back to normal, one test order returns status=accepted."

---

## 4:45 – 5:30 | What Would Be Improved

> "For production I'd add three things immediately:"

> "First: a persistent queue. Instead of returning status=pending and hoping, orders-service would publish to Redis Streams or SQS. An async worker would replay confirmed orders when inventory-service recovers."

> "Second: distributed tracing with OpenTelemetry. X-Request-ID gets you correlation, but traces give you exact span durations, service dependencies, and error root cause in one view."

> "Third: alerting. A Prometheus alerting rule that fires when the circuit breaker opens or fallback rate exceeds 5% — routed to PagerDuty or Slack — so an on-call engineer knows before customers notice."

> "The system as built passes the core test: it fails safely, it's observable, and you can see exactly what's happening from the dashboard."

---

*End of demo.*
