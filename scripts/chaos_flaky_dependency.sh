#!/usr/bin/env bash
set -e

BASE_URL="http://localhost:8080"

echo "=== Chaos Experiment: Flaky Dependency (~50% failures) ==="
echo ""
echo "Setting inventory-service to FLAKY mode (random 50% failure rate)..."
curl -s -X POST "${BASE_URL}/inventory/chaos/mode" \
  -H "Content-Type: application/json" \
  -d '{"mode": "flaky"}' | python3 -m json.tool 2>/dev/null
echo ""

echo "Sending 10 order requests. Expect a mix of accepted and fallback responses..."
echo ""

SUCCESS=0
FALLBACK=0

for i in $(seq 1 10); do
  echo "--- Request $i ---"
  RESPONSE=$(curl -s -X POST "${BASE_URL}/orders" \
    -H "Content-Type: application/json" \
    -d "{\"customer_id\": \"C00${i}\", \"product_id\": \"P001\", \"quantity\": 1}")
  STATUS=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null || echo "unknown")
  echo "Status: $STATUS"
  if [ "$STATUS" = "accepted" ]; then
    SUCCESS=$((SUCCESS + 1))
  else
    FALLBACK=$((FALLBACK + 1))
  fi
  sleep 0.3
done

echo ""
echo "=== Summary ==="
echo "  Accepted: $SUCCESS / 10"
echo "  Fallback/Pending: $FALLBACK / 10"
echo ""
echo "=== Expected behavior ==="
echo "  - Some requests succeed (retry recovers transient failures)"
echo "  - Others fall back (repeated failures may open circuit breaker)"
echo "  - No hard crashes or unhandled errors"
