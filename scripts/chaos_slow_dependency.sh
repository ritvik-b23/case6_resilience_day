#!/usr/bin/env bash
set -e

BASE_URL="http://localhost:8080"

echo "=== Chaos Experiment: Slow Dependency ==="
echo ""
echo "Setting inventory-service to SLOW mode (3 second delay)..."
curl -s -X POST "${BASE_URL}/inventory/chaos/mode" \
  -H "Content-Type: application/json" \
  -d '{"mode": "slow"}' | python3 -m json.tool 2>/dev/null
echo ""

echo "Sending 3 order requests. Each should time out quickly (~1s) and return fallback..."
echo ""

for i in 1 2 3; do
  echo "--- Request $i ---"
  START=$(date +%s%N)
  RESPONSE=$(curl -s -X POST "${BASE_URL}/orders" \
    -H "Content-Type: application/json" \
    -d "{\"customer_id\": \"C00${i}\", \"product_id\": \"P001\", \"quantity\": 1}")
  END=$(date +%s%N)
  ELAPSED_MS=$(( (END - START) / 1000000 ))
  echo "Response (${ELAPSED_MS}ms):"
  echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
  echo ""
done

echo ""
echo "=== Expected behavior ==="
echo "  - Each request completed in ~1-2 seconds (timeout after 1s, not 3s)"
echo "  - status=pending with fallback message (not a hard error)"
echo "  - orders-service timed out waiting for inventory-service and failed fast"
