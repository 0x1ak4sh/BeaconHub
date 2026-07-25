#!/bin/bash
# Install BeaconHub CLI

cat > /usr/local/bin/beaconhub << 'EOF'
#!/bin/bash
case "$1" in
  start)
    /opt/beaconhub/scripts/start.sh
    ;;
  stop)
    /opt/beaconhub/scripts/stop.sh
    ;;
  status)
    /opt/beaconhub/scripts/status.sh
    ;;
  test)
    /opt/beaconhub/scripts/test.sh
    ;;
  rebuild)
    echo "[*] Rebuilding from /vagrant..."
    /opt/beaconhub/scripts/stop.sh 2>/dev/null
    rm -rf /opt/beaconhub/backend
    cp -r /vagrant/backend /opt/beaconhub/backend
    cp -r /vagrant/scripts /opt/beaconhub/scripts
    chmod +x /opt/beaconhub/scripts/*.sh
    cd /vagrant/frontend && npm run build --silent 2>/dev/null
    rm -rf /opt/beaconhub/frontend && cp -r /vagrant/frontend/dist /opt/beaconhub/frontend
    echo "[+] Rebuild done. Run: beaconhub start"
    ;;
  tools)
    echo ""
    echo "=== WiFi Hacking Tools ==="
    echo ""
    echo "  wifite      - Automated wireless auditing tool"
    echo "                Usage: sudo wifite"
    echo ""
    echo "  airgeddon   - Multi-use WiFi auditing script"
    echo "                Usage: sudo airgeddon"
    echo ""
    echo "  wifiphisher - Rogue AP framework for phishing"
    echo "                Usage: sudo wifiphisher"
    echo ""
    echo "  eaphammer   - WPA2-Enterprise/802.1x attacks"
    echo "                Usage: sudo eaphammer --help"
    echo ""
    echo "  aircrack-ng - Classic WiFi cracking suite"
    echo "                Usage: aircrack-ng, airodump-ng, aireplay-ng"
    echo ""
    echo "Tools directory: /opt/tools/"
    echo ""
    ;;
  *)
    echo "BeaconHub - WiFi Security Lab"
    echo ""
    echo "Usage: beaconhub <command>"
    echo ""
    echo "Commands:"
    echo "  start    - Start the lab (API + Web UI)"
    echo "  stop     - Stop the lab"
    echo "  status   - Show lab status"
    echo "  test     - Run API tests"
    echo "  rebuild  - Rebuild from /vagrant source"
    echo "  tools    - List installed hacking tools"
    echo ""
    exit 1
    ;;
esac
EOF

chmod +x /usr/local/bin/beaconhub
echo "[+] BeaconHub CLI installed"
