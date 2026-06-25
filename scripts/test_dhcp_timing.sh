#!/bin/bash
# Test timing of DHCP
set -e

echo "=== Starting fresh ==="
sudo pkill -9 hostapd 2>/dev/null || true
sudo pkill -9 dnsmasq 2>/dev/null || true
sudo pkill -9 wpa_supplicant 2>/dev/null || true
sudo pkill -9 dhclient 2>/dev/null || true
sleep 2

echo ""
echo "=== Restarting backend ==="
sudo pkill -f uvicorn 2>/dev/null || true
sleep 1
cd /opt/beaconhub
nohup python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 1 --log-level debug > /tmp/backend.log 2>&1 &
sleep 3

echo ""
echo "=== Creating WEP AP with 1 client ==="
curl -s -X POST http://127.0.0.1:8000/api/ap \
  -H "Content-Type: application/json" \
  -d '{"ssid": "WEPTEST", "security": "wep", "password": "crack", "channel": 6, "num_clients": 1}'
echo ""

echo "=== Checking every second for 15 seconds ==="
for i in {1..15}; do
  IP=$(ip -4 addr show client0 2>/dev/null | grep -oP 'inet \K[\d.]+' || echo "none")
  API_IP=$(curl -s http://127.0.0.1:8000/api/clients 2>/dev/null | python3 -c "import sys, json; clients=json.load(sys.stdin); print(clients[0]['ip_address'] if clients else 'no-clients')" 2>/dev/null || echo "api-error")
  echo "T+${i}s: interface=$IP, api=$API_IP"
  sleep 1
done

echo ""
echo "=== Relevant backend logs ==="
grep -E "DHCP|IP|client_" /tmp/backend.log | tail -30
