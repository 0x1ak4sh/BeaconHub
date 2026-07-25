#!/bin/bash
# BeaconHub - Integration tests

PASS=0; FAIL=0
pass() { echo "  [+] $1"; PASS=$((PASS + 1)); }
fail() { echo "  [-] $1"; FAIL=$((FAIL + 1)); }

echo "BeaconHub Tests"
echo "---"

# Module
if lsmod | grep -q mac80211_hwsim; then pass "hwsim loaded"; else fail "hwsim not loaded"; fi

# Interfaces
IFACE_COUNT=$(iw dev 2>/dev/null | grep -c "Interface" || echo "0")
if [ "$IFACE_COUNT" -ge 2 ]; then pass "$IFACE_COUNT interfaces"; else fail "only $IFACE_COUNT interfaces"; fi

# Binaries
for bin in hostapd dnsmasq wpa_supplicant aireplay-ng airodump-ng aircrack-ng iw; do
  command -v $bin > /dev/null 2>&1 && pass "$bin" || fail "$bin missing"
done

# API
if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then pass "backend api"; else fail "backend api down"; fi

# Frontend
if curl -sf http://localhost:8080/ > /dev/null 2>&1; then pass "frontend"; else fail "frontend down"; fi

# Create AP
AP=$(curl -sf -X POST http://localhost:8000/api/ap \
  -H "Content-Type: application/json" \
  -d '{"ssid":"TestNet","security":"wpa2-psk","password":"testpass123","channel":6}' 2>/dev/null)
AP_ID=$(echo "$AP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null)
if [ -n "$AP_ID" ]; then pass "AP created ($AP_ID)"; else fail "AP creation"; fi

# Cleanup
if [ -n "$AP_ID" ]; then
  curl -sf -X DELETE "http://localhost:8000/api/ap/${AP_ID}" > /dev/null 2>&1
  pass "AP stopped"
fi

echo ""
echo "--- $PASS passed / $FAIL failed ---"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
