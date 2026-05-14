#!/usr/bin/env bash
set -e

BASE_URL="http://localhost:8080"

echo "=== Chaos Experiment: Kill inventory-service container ==="
echo ""
echo "Stopping inventory-service container..."
docker compose stop inventory-service
echo ""
sleep 2

echo "Sending order request with inventory-service DOWN..."
echo ""
RESPONSE=$(curl -s -X POST "${BASE_URL}/orders" \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "C001", "product_id": "P001", "quantity": 2}')
echo "Response:"
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
echo ""

echo "Sending 2 more requests..."
for i in 2 3; do
  RESPONSE=$(curl -s -X POST "${BASE_URL}/orders" \
    -H "Content-Type: application/json" \
    -d "{\"customer_id\": \"C00${i}\", \"product_id\": \"P001\", \"quantity\": 1}")
  echo "Request $i: $(echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status'), '-', d.get('message','')[:60])" 2>/dev/null || echo "$RESPONSE")"
done

echo ""
echo "=== Expected behavior ==="
echo "  - orders-service detects that inventory-service is unreachable"
echo "  - Returns graceful fallback: status=pending"
echo "  - No 500 errors, no hanging requests"
echo ""
echo "Run 'bash scripts/reset_chaos.sh' to bring inventory-service back up."
