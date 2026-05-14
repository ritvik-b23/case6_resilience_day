# Service Level Objectives — Case 6: Resilience Day

## Overview

This document defines the SLO targets for the orders-service in normal operating conditions (inventory-service healthy, no chaos mode active).

---

## SLO 1: Request Latency

**Target:** 99% of POST /orders requests complete within **1000ms** (1 second) when inventory-service is healthy.

**Measurement:**
```promql
histogram_quantile(0.99, rate(orders_http_request_duration_seconds_bucket{path="/orders"}[5m])) < 1.0
```

**Rationale:** A 1-second SLO is appropriate for a demo system that involves two synchronous service calls over a local Docker network. In production with real network latency, a 500ms p99 would be more appropriate, but on localhost the dominant latency is application processing time (~5–20ms per hop). The 1-second target provides headroom for GC pauses and container scheduling jitter while remaining user-perceived as fast.

---

## SLO 2: Error Rate

**Target:** Error rate (HTTP 5xx responses) stays below **1%** for normal traffic.

**Measurement:**
```promql
rate(orders_http_requests_total{status_code=~"5.."}[5m])
/
rate(orders_http_requests_total[5m])
< 0.01
```

**Rationale:** With resilience patterns (fallback returning HTTP 200 with status=pending), the orders-service should produce zero 5xx responses under normal conditions. 1% is a conservative budget that accounts for extremely rare edge cases (e.g., malformed internal state, unexpected OS signal). In practice, with circuit breaker and fallback active, 5xx from orders-service should be effectively 0%.

---

## Error Budget

Assuming a 30-day rolling window:

| Metric | Total budget | At 99% | Allowed bad minutes |
|--------|-------------|--------|---------------------|
| Latency (p99 < 1s) | 43,200 minutes | 99% | 432 minutes (~7.2 hours) |
| Error rate (<1%) | 43,200 minutes | 99% | 432 minutes (~7.2 hours) |

**What counts as an error budget burn:**

1. **Latency burn:** Any window where p99 latency consistently exceeds 1000ms. Common causes: chaos mode `slow` active, orders-service CPU-starved, Nginx misconfiguration.

2. **Error rate burn:** Any window where >1% of requests return HTTP 5xx. This would be unusual given the fallback architecture and indicates a failure in the fallback path itself (e.g., orders-service process crash, code bug).

**What does NOT burn the error budget:**
- Orders returning `status: pending` (HTTP 200) — this is the intended degraded state.
- Circuit breaker in open state — orders still receive responses (fallback).
- inventory-service being down — orders-service handles this gracefully.

---

## Monitoring

The Grafana dashboard includes panels for:
- p95 and p50 latency (proxy for p99)
- Error rate (5xx per second)
- Fallback count (indicates degraded but functional state)

For production, Prometheus alerting rules would be added:
```yaml
# Alert if p99 latency exceeds SLO
- alert: HighLatency
  expr: histogram_quantile(0.99, rate(orders_http_request_duration_seconds_bucket[5m])) > 1.0
  for: 2m
  labels:
    severity: warning

# Alert if error rate exceeds SLO
- alert: HighErrorRate
  expr: rate(orders_http_requests_total{status_code=~"5.."}[5m]) / rate(orders_http_requests_total[5m]) > 0.01
  for: 2m
  labels:
    severity: critical
```
