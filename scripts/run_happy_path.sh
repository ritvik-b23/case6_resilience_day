#!/usr/bin/env bash
set -e

BASE_URL="http://localhost:8080"

echo "=== Happy Path: Sending a normal order request ==="
echo ""

RESPONSE=$(curl -s -X POST "${BASE_URL}/orders" \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: happy-path-001" \
  -d '{"customer_id": "C001", "product_id": "P001", "quantity": 2}')

echo "Response:"
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
echo ""
echo "Expected: status=accepted, inventory_status=available"
