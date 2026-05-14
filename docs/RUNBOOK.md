# Runbook — Resilience Day System

**System:** Case 6 microservices (orders-service, inventory-service, nginx, prometheus, grafana)
**Last updated:** May 2026

---

## 1. How to Start the System

```bash
docker compose up --build -d
```

Wait ~30 seconds for health checks to pass, then verify:

```bash
curl http://localhost:8080/health/orders
curl http://localhost:8080/health/inventory
```

Both should return `{"status": "healthy", ...}`.

---

## 2. How to Stop the System

```bash
docker compose down
```

To also remove volumes:

```bash
docker compose down -v
```

---

## 3. How to Restart One Service

```bash
docker compose restart orders-service
# or
docker compose restart inventory-service
```

To rebuild and restart a single service after code changes:

```bash
docker compose up --build -d orders-service
```

---

## 4. How to Check Service Health

```bash
# Via Nginx (public endpoint)
curl http://localhost:8080/health/orders
curl http://localhost:8080/health/inventory

# Direct (bypassing Nginx)
curl http://localhost:8001/health
curl http://localhost:8002/health
```

Check all container statuses:

```bash
docker compose ps
```

---

## 5. How to View Logs

All services:

```bash
docker compose logs -f
```

Specific service:

```bash
docker compose logs -f orders-service
docker compose logs -f inventory-service
docker compose logs -f nginx
```

Logs are structured JSON. To pretty-print orders-service logs:

```bash
docker compose logs orders-service | python3 -m json.tool
```

---

## 6. How to Open Grafana

1. Open browser: [http://localhost:3000](http://localhost:3000)
2. Login: `admin` / `admin`
3. Navigate to: **Dashboards → Resilience Day → Resilience Day Dashboard**

The dashboard auto-refreshes every 5 seconds.

---

## 7. How to Open Prometheus

1. Open browser: [http://localhost:9090](http://localhost:9090)
2. Go to **Status → Targets** to verify both services are being scraped.
3. Example queries:
   - `rate(orders_http_requests_total[1m])` — request rate
   - `orders_circuit_breaker_open_total` — circuit breaker opens
   - `orders_fallback_total` — fallback responses served

---

## 8. What to Do If orders-service Is Down

**Symptoms:** `curl http://localhost:8080/orders` returns 502 or connection refused.

**Steps:**
```bash
# Check container status
docker compose ps orders-service

# Check logs for error
docker compose logs --tail=50 orders-service

# Restart the service
docker compose restart orders-service

# Wait for health check
sleep 15 && curl http://localhost:8001/health
```

If the container keeps crashing, check for Python import errors in logs.

---

## 9. What to Do If inventory-service Is Down

**Symptoms:** Orders returning `status: pending` (fallback active). Grafana shows `orders_fallback_total` rising.

**Steps:**
```bash
# Check if it's stopped intentionally (chaos test)
docker compose ps inventory-service

# Restart
docker compose start inventory-service
# or
docker compose restart inventory-service

# Reset chaos mode after restart
curl -X POST http://localhost:8002/chaos/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "normal"}'

# Verify
curl http://localhost:8002/health
```

**Note:** While inventory-service is down, orders-service continues serving fallback responses — the system degrades gracefully.

---

## 10. What to Do If Latency Is High

**Symptoms:** Grafana p95 latency panel showing >1s. Users report slow responses.

**Investigate:**
```bash
# Check current chaos mode
curl http://localhost:8002/chaos/mode

# If mode is "slow", reset it
curl -X POST http://localhost:8002/chaos/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "normal"}'

# Check Prometheus for timeout spikes
# Query: rate(orders_timeout_total[1m])
```

If chaos mode is normal but latency is still high, check container resource limits and host load.

---

## 11. What to Do If Error Rate Is High

**Symptoms:** Grafana error rate panel showing elevated 5xx. `orders_circuit_breaker_open_total` incrementing.

**Investigate:**
```bash
# Check circuit breaker state
curl http://localhost:8001/resilience/status

# Check inventory chaos mode
curl http://localhost:8002/chaos/mode

# Check inventory health
curl http://localhost:8002/health

# Reset if needed
bash scripts/reset_chaos.sh
```

If circuit breaker is open and inventory-service is healthy, wait 15 seconds for the circuit to try half-open, or restart orders-service to reset in-memory CB state.

---

## 12. What to Do at 2AM If the Service Is Failing

1. **Don't panic.** Orders-service is designed to fail safely. Customers receive `status: pending`, not errors.

2. **Quick check:**
   ```bash
   docker compose ps
   curl http://localhost:8080/health/orders
   curl http://localhost:8080/health/inventory
   ```

3. **Restart everything if uncertain:**
   ```bash
   docker compose restart
   sleep 20
   curl http://localhost:8080/health/orders
   ```

4. **Reset chaos mode (if someone ran experiments and forgot to reset):**
   ```bash
   bash scripts/reset_chaos.sh
   ```

5. **Check Grafana for pattern:**
   - High fallback + high timeout → inventory is slow or down
   - High fallback + circuit open → inventory is throwing errors
   - Low request rate → possible Nginx issue

6. **Check logs for specific error message:**
   ```bash
   docker compose logs --tail=100 orders-service | grep '"levelname": "ERROR"'
   ```

7. **Escalate if:** container keeps restarting (OOM, import error), or Nginx returns 502 (both upstreams are down).
