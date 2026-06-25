#!/bin/bash
# BeaconHub - Status check

echo "BeaconHub Status"
echo "---"

# Kernel module
if lsmod | grep -q mac80211_hwsim; then
    IFACE_COUNT=$(iw dev 2>/dev/null | grep -c "Interface" || echo "0")
    echo "  hwsim:    loaded (${IFACE_COUNT} interfaces)"
else
    echo "  hwsim:    not loaded"
fi

# Backend
if pgrep -f "uvicorn backend.main:app" > /dev/null; then
    echo "  backend:  running (PID $(pgrep -f 'uvicorn backend.main:app' | head -1))"
else
    echo "  backend:  stopped"
fi

# Nginx
if systemctl is-active --quiet nginx; then
    echo "  nginx:    running"
else
    echo "  nginx:    stopped"
fi

# API check
if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
    STATUS=$(curl -sf http://localhost:8000/api/status 2>/dev/null)
    APS=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('aps_running',0))" 2>/dev/null)
    ATTACKS=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('attacks_running',0))" 2>/dev/null)
    CLIENTS=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('clients_connected',0))" 2>/dev/null)
    echo "  APs:      ${APS} running"
    echo "  attacks:  ${ATTACKS} active"
    echo "  clients:  ${CLIENTS} connected"
else
    echo "  api:      not responding"
fi

echo ""
echo "  Web UI:   http://localhost:8080"
