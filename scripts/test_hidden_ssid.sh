#!/bin/bash
# Test hidden SSID network support
# Hidden SSIDs can be discovered using mdk4 brute force or by monitoring probe responses

set -e

echo "=== Creating Hidden SSID Network ==="
RESPONSE=$(curl -s -X POST http://127.0.0.1:8000/api/ap \
  -H "Content-Type: application/json" \
  -d '{"ssid": "SECRET_NETWORK", "security": "wpa2-psk", "password": "HiddenPass123", "channel": 11, "hidden": true, "num_clients": 1}')
echo "$RESPONSE"

AP_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', 'ERROR'))")
if [ "$AP_ID" = "ERROR" ]; then
  echo "ERROR: Failed to create hidden AP"
  exit 1
fi
echo "AP ID: $AP_ID"

sleep 3

echo ""
echo "=== Verifying hostapd config has hidden flag ==="
cat /opt/beaconhub/configs/hostapd/$AP_ID.conf | grep -E "ignore_broadcast_ssid|ssid"

echo ""
echo "=== AP Info ==="
curl -s "http://127.0.0.1:8000/api/ap/$AP_ID" | python3 -m json.tool

echo ""
echo "=== Listing clients ==="
curl -s "http://127.0.0.1:8000/api/clients" | python3 -m json.tool

echo ""
echo "=== Testing Hidden SSID Detection ==="
echo "To discover this hidden network, you can:"
echo ""
echo "1. Monitor for probe responses (passive):"
echo "   sudo airodump-ng wlan1mon -c 11"
echo "   Look for AP with blank SSID but with BSSID and data"
echo ""
echo "2. Wait for client probe request:"
echo "   When client connects, it sends probe with SSID"
echo "   The SSID appears in airodump-ng probes column"
echo ""
echo "3. Use mdk4 to brute force SSID (active):"
echo "   sudo mdk4 wlan1mon p -t <bssid> -f /opt/wordlists/common.txt"
echo ""
echo "=== Network Details (for verification) ==="
BSSID=$(curl -s "http://127.0.0.1:8000/api/ap/$AP_ID" | python3 -c "import sys, json; print(json.load(sys.stdin).get('bssid', 'N/A'))")
echo "BSSID: $BSSID"
echo "Channel: 11"
echo "SSID: SECRET_NETWORK (hidden)"
echo "Password: HiddenPass123"

echo ""
echo "=== Cleanup ==="
curl -s -X DELETE "http://127.0.0.1:8000/api/ap/$AP_ID" | python3 -m json.tool
