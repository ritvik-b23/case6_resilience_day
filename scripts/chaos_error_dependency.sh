#!/usr/bin/env bash
set -e

BASE_URL="http://localhost:8080"

echo "=== Chaos Experiment: Dependency Errors (500s) ==="
echo ""
echo "Setting inventory-service to ERROR mode (always returns HTTP 500)..."
curl -s -X POST "${BASE_URL}/inventory/chaos/mode" \
  -H "Content-Type: application/json" \
  -d '{"mode": "error"}' | python3 -m json.tool 2>/dev/null
echo ""

echo "Sending 6 order requests to trigger retries and circuit breaker..."
echo ""

for i in $(seq 1 6); do
  echo "--- Request $i ---"
  RESPONSE=$(curl -s -X POST "${BASE_URL}/orders" \
    -H "Content-Type: application/json" \
    -d "{\"customer_id\": \"C00${i}\", \"product_id\": \"P001\", \"quantity\": 1}")
  echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
  echo ""
  sleep 0.5
done

echo ""
echo "=== Resilience Status ==="
curl -s "${BASE_URL}/orders/resilience/status" | python3 -m json.tool 2>/dev/null
echo ""

echo "=== Expected behavior ==="
echo "  - Requests 1-3: orders-service retries 3 times each, circuit breaker counts failures"
echo "  - After 3 total failures, circuit breaker opens"
echo "  - Requests 4-6: circuit breaker is OPEN, returns fallback immediately (fast failure)"
echo "  - All responses: status=pending with fallback message (no hard crash)"
