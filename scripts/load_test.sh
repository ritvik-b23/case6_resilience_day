#!/usr/bin/env bash
set -e

BASE_URL="http://localhost:8080"
REQUESTS=20

echo "=== Load Test: Sending ${REQUESTS} order requests ==="
echo ""

SUCCESS=0
FALLBACK=0
ERROR=0

for i in $(seq 1 $REQUESTS); do
  RESPONSE=$(curl -s -X POST "${BASE_URL}/orders" \
    -H "Content-Type: application/json" \
    -d "{\"customer_id\": \"C$(printf '%03d' $i)\", \"product_id\": \"P001\", \"quantity\": 1}")
  STATUS=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null || echo "parse_error")
  echo "Request $i: $STATUS"
  case "$STATUS" in
    accepted) SUCCESS=$((SUCCESS + 1)) ;;
    pending)  FALLBACK=$((FALLBACK + 1)) ;;
    *)        ERROR=$((ERROR + 1)) ;;
  esac
done

echo ""
echo "=== Load Test Summary ==="
echo "  Total:    $REQUESTS"
echo "  Accepted: $SUCCESS"
echo "  Pending (fallback): $FALLBACK"
echo "  Other/Error: $ERROR"
