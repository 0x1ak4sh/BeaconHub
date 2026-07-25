#!/bin/bash
# BeaconHub - Stop the lab

echo "BeaconHub stopping..."

# Stop backend (try systemd first, then direct kill)
if systemctl is-active beaconhub > /dev/null 2>&1; then
    sudo systemctl stop beaconhub
    echo "[+] Backend service stopped"
elif pgrep -f "uvicorn backend.main:app" > /dev/null; then
    sudo pkill -f "uvicorn backend.main:app"
    echo "[+] Backend stopped"
fi

# Kill any hostapd instances we spawned
sudo pkill -f "hostapd /opt/beaconhub" 2>/dev/null && echo "[+] hostapd stopped" || true

# Kill any dnsmasq instances we spawned (not system dnsmasq)
sudo pkill -f "dnsmasq -C /opt/beaconhub" 2>/dev/null && echo "[+] dnsmasq stopped" || true

# Kill any wpa_supplicant instances we spawned
sudo pkill -f "wpa_supplicant.*-c /opt/beaconhub" 2>/dev/null && echo "[+] wpa_supplicant stopped" || true

# Kill freeradius if running
sudo pkill -f "freeradius" 2>/dev/null && echo "[+] freeradius stopped" || true

# Kill any dhclient instances
sudo pkill -f "dhclient.*client" 2>/dev/null || true

# Kill any aircrack tools
sudo pkill -f "aireplay-ng" 2>/dev/null || true
sudo pkill -f "airodump-ng" 2>/dev/null || true

# Nginx stays running (it's just a reverse proxy)

# Unload kernel module (frees all interfaces) - optional
if [ "$1" = "--full" ]; then
    if lsmod | grep -q mac80211_hwsim; then
        sudo modprobe -r mac80211_hwsim 2>/dev/null && echo "[+] mac80211_hwsim unloaded" || true
    fi
fi

# Cleanup runtime files
sudo rm -rf /opt/beaconhub/configs/hostapd/* 2>/dev/null
sudo rm -rf /opt/beaconhub/configs/dnsmasq/* 2>/dev/null
sudo rm -rf /opt/beaconhub/configs/wpa_supplicant/* 2>/dev/null
sudo rm -rf /opt/beaconhub/run/* 2>/dev/null
sudo rm -rf /opt/beaconhub/leases/* 2>/dev/null

echo ""
echo "[+] BeaconHub stopped"
echo "    Start again with: beaconhub start"
