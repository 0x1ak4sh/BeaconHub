#!/bin/bash
# BeaconHub - Start the lab

set -e

echo "BeaconHub starting..."

# Load kernel module
RADIOS=${BEACONHUB_RADIOS:-6}

if lsmod | grep -q mac80211_hwsim; then
    echo "[+] mac80211_hwsim already loaded"
else
    echo "[*] Loading mac80211_hwsim (radios=${RADIOS})..."
    if sudo modprobe mac80211_hwsim radios=${RADIOS}; then
        echo "[+] Module loaded"
    else
        echo "[!] Failed to load mac80211_hwsim"
        echo "    Try: sudo apt install linux-modules-extra-\$(uname -r)"
        exit 1
    fi
fi

sleep 1
IFACE_COUNT=$(iw dev 2>/dev/null | grep -c "Interface" || echo "0")
echo "[+] ${IFACE_COUNT} wireless interfaces ready"

# Enable IP forwarding
sudo sysctl -w net.ipv4.ip_forward=1 > /dev/null 2>&1

# Create runtime directories
sudo mkdir -p /opt/beaconhub/configs/hostapd
sudo mkdir -p /opt/beaconhub/configs/dnsmasq
sudo mkdir -p /opt/beaconhub/configs/wpa_supplicant
sudo mkdir -p /opt/beaconhub/configs/radius
sudo mkdir -p /opt/beaconhub/configs/radius/certs
sudo mkdir -p /opt/beaconhub/run
sudo mkdir -p /opt/beaconhub/captures
sudo mkdir -p /opt/beaconhub/leases
sudo mkdir -p /opt/beaconhub/logs
sudo mkdir -p /var/run/wpa_supplicant
sudo chmod -R 777 /opt/beaconhub/configs /opt/beaconhub/run /opt/beaconhub/captures /opt/beaconhub/leases /opt/beaconhub/logs

# Start nginx
echo "[*] Starting nginx..."
sudo systemctl restart nginx

# Start backend (use systemd service if available, otherwise direct)
echo "[*] Starting backend..."
if systemctl is-enabled beaconhub > /dev/null 2>&1; then
    sudo systemctl start beaconhub
    sleep 2
    if systemctl is-active beaconhub > /dev/null 2>&1; then
        echo "[+] Backend service running"
    else
        echo "[!] Service failed - falling back to direct start"
        cd /opt/beaconhub
        sudo nohup python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 1 \
            > /opt/beaconhub/logs/backend.log 2>&1 &
        sleep 2
    fi
else
    if pgrep -f "uvicorn backend.main:app" > /dev/null; then
        echo "    Backend already running"
    else
        cd /opt/beaconhub
        sudo nohup python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 1 \
            > /opt/beaconhub/logs/backend.log 2>&1 &
        sleep 2
    fi
fi

# Verify backend is up
if curl -s http://127.0.0.1:8000/api/health > /dev/null 2>&1; then
    echo "[+] Backend API responding"
else
    echo "[!] Backend may still be starting..."
fi

echo ""
echo "[+] BeaconHub is running"
echo "    Web UI: http://localhost:8080"
echo ""
echo "    Stop with: beaconhub stop"
