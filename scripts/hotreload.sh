#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# BeaconHub Hot-Reload Script
# Runs INSIDE the VM. Rebuilds frontend + restarts backend.
#
# Usage (from Windows host):
#   cd C:\path\to\WifiAI
#   vagrant ssh -c "bash /vagrant/scripts/hotreload.sh"
#
# Usage (inside VM):
#   bash /vagrant/scripts/hotreload.sh
# ─────────────────────────────────────────────────────────────────────────────

# Don't exit on error - handle errors gracefully
set +e

FRONTEND_SRC="/vagrant/frontend"
FRONTEND_DST="/opt/beaconhub/frontend"
BACKEND_SRC="/vagrant/backend"
BACKEND_DST="/opt/beaconhub/backend"
LOGDIR="/opt/beaconhub/logs"
LOG="${LOGDIR}/hotreload.log"

# Ensure we're running as root or with sudo
if [ "$EUID" -ne 0 ]; then
    exec sudo bash "$0" "$@"
fi

# Create directories
mkdir -p "${LOGDIR}"
mkdir -p "${BACKEND_DST}"
mkdir -p "${FRONTEND_DST}"

# Fix permissions
chmod 755 "${LOGDIR}" 2>/dev/null || true
touch "${LOG}" 2>/dev/null || LOG="/tmp/hotreload.log"

echo "═══════════════════════════════════════════"
echo "  BeaconHub Hot-Reload  $(date)"
echo "═══════════════════════════════════════════"

# 1. Copy backend source
echo "[1/5] Syncing backend source..."
if [ -d "${BACKEND_SRC}" ]; then
    rsync -a --delete \
      --exclude '__pycache__' \
      --exclude '*.pyc' \
      --exclude '.pytest_cache' \
      "${BACKEND_SRC}/" "${BACKEND_DST}/" 2>/dev/null
    echo "    done"
else
    echo "    [!] Backend source not found at ${BACKEND_SRC}"
fi

# 2. Build frontend
echo "[2/5] Building frontend..."
if [ -d "${FRONTEND_SRC}" ]; then
    cd "${FRONTEND_SRC}"
    
    # Install dependencies if node_modules missing
    if [ ! -d "node_modules" ]; then
        echo "    installing dependencies..."
        npm install --silent 2>/dev/null || npm install 2>&1 | tail -3
    fi
    
    # Build
    npm run build 2>&1 | grep -E "(built|error|ERROR)" | head -5
    
    if [ -d "dist" ]; then
        echo "    done"
    else
        echo "    [!] Build failed - dist directory not created"
    fi
else
    echo "    [!] Frontend source not found at ${FRONTEND_SRC}"
fi

# 3. Deploy frontend dist
echo "[3/5] Deploying frontend..."
if [ -d "${FRONTEND_SRC}/dist" ]; then
    rm -rf "${FRONTEND_DST}"
    cp -r "${FRONTEND_SRC}/dist" "${FRONTEND_DST}"
    echo "    done"
else
    echo "    [!] No dist to deploy"
fi

# 4. Update nginx config and reload
echo "[4/5] Updating nginx..."
if [ -f "/vagrant/configs/nginx.conf" ]; then
    cp /vagrant/configs/nginx.conf /etc/nginx/sites-available/beaconhub
    rm -f /etc/nginx/sites-enabled/default
    ln -sf /etc/nginx/sites-available/beaconhub /etc/nginx/sites-enabled/beaconhub
    
    # Test and reload nginx
    if nginx -t 2>&1 | grep -q "successful"; then
        systemctl reload nginx 2>/dev/null || systemctl restart nginx
        echo "    done"
    else
        echo "    [!] nginx config test failed"
        nginx -t
    fi
else
    echo "    [!] nginx config not found"
fi

# 5. Restart backend
echo "[5/5] Restarting backend..."

# Kill existing backend processes
pkill -9 -f "uvicorn backend.main:app" 2>/dev/null || true
pkill -9 -f "uvicorn.*8000" 2>/dev/null || true
sleep 2

# Start backend
cd /opt/beaconhub

# Check if uvicorn is available
if ! command -v uvicorn &> /dev/null; then
    echo "    [!] uvicorn not found, installing..."
    pip3 install --break-system-packages -q uvicorn fastapi pydantic websockets python-multipart 2>/dev/null
fi

# Start backend with nohup
nohup python3 -m uvicorn backend.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 1 \
  --log-level info \
  >> "${LOG}" 2>&1 &

BACKEND_PID=$!
sleep 3

# Verify backend started
if pgrep -f "uvicorn backend.main:app" > /dev/null; then
    echo "    backend running (PID: $(pgrep -f 'uvicorn backend.main:app' | head -1))"
else
    echo "    [!] backend failed to start"
    echo "    Last 15 lines of log:"
    tail -15 "${LOG}" 2>/dev/null || echo "    (no log available)"
fi

# Test API health
sleep 1
if curl -s http://localhost:8000/api/health | grep -q '"status":"ok"'; then
    echo "    API responding OK"
else
    echo "    [!] API not responding"
fi

echo ""
echo "  Done. UI: http://localhost:8080 (from host)"
echo "═══════════════════════════════════════════"
