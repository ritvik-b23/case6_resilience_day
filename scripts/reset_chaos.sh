#!/usr/bin/env bash
set -e

BASE_URL="http://localhost:8080"

echo "=== Reset: Restoring system to normal state ==="
echo ""

echo "Starting inventory-service (in case it was stopped)..."
docker compose start inventory-service 2>/dev/null || true
echo ""

echo "Waiting for inventory-service to be healthy..."
for i in $(seq 1 15); do
  STATUS=$(curl -s "${BASE_URL}/inventory/health" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null || echo "")
  if [ "$STATUS" = "healthy" ]; then
    echo "inventory-service is healthy."
    break
  fi
  echo "Waiting... (attempt $i/15)"
  sleep 2
done

echo ""
echo "Setting chaos mode back to NORMAL..."
curl -s -X POST "${BASE_URL}/inventory/chaos/mode" \
  -H "Content-Type: application/json" \
  -d '{"mode": "normal"}' | python3 -m json.tool 2>/dev/null
echo ""

echo "Verifying with a happy-path order..."
RESPONSE=$(curl -s -X POST "${BASE_URL}/orders" \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "C001", "product_id": "P001", "quantity": 1}')
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
echo ""
echo "=== System reset complete ==="
