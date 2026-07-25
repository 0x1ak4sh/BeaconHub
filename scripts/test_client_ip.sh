#!/bin/bash
# Create WEP AP with just 1 client and check IP
set -e

echo "=== Creating WEP Network with 1 client ==="
WEP_RESPONSE=$(curl -s -X POST http://127.0.0.1:8000/api/ap \
  -H "Content-Type: application/json" \
  -d '{"ssid": "WEPTEST", "security": "wep", "password": "crack", "channel": 6, "num_clients": 1}')
echo "$WEP_RESPONSE"

WEP_ID=$(echo "$WEP_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', 'ERROR'))")
echo "AP ID: $WEP_ID"

echo ""
echo "=== Waiting 10 seconds for client to get IP ==="
sleep 10

echo ""
echo "=== Interface IPs ==="
ip addr | grep -E "client[0-9]|inet 10\." | head -20

echo ""
echo "=== API Client List ==="
curl -s http://127.0.0.1:8000/api/clients | python3 -m json.tool

echo ""
echo "=== Cleanup ==="
curl -s -X DELETE "http://127.0.0.1:8000/api/ap/$WEP_ID" || true
