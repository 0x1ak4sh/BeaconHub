# -*- mode: ruby -*-
# vi: set ft=ruby :
#
# BeaconHub - Virtual Wi-Fi Pentesting Lab
#
# Usage:
#   vagrant up        (first time: ~10 min, downloads ~500MB)
#   vagrant ssh       (enter the VM)
#   beaconhub start   (start the lab)
#
# Web UI: http://localhost:8080

Vagrant.configure("2") do |config|
  config.vm.box = "debian/bookworm64"
  config.vm.hostname = "beaconhub"

  # Forward web UI (nginx listens on port 80 inside VM)
  config.vm.network "forwarded_port", guest: 80, host: 8080

  config.vm.provider "virtualbox" do |vb|
    vb.memory = "2048"
    vb.cpus = 2
    vb.name = "BeaconHub"
    # Disable USB to avoid warnings
    vb.customize ["modifyvm", :id, "--usb", "off"]
    vb.customize ["modifyvm", :id, "--usbehci", "off"]
  end

  # Provision: install everything
  config.vm.provision "shell", inline: <<-SHELL
    set -e
    export DEBIAN_FRONTEND=noninteractive

    echo "[*] Updating packages..."
    apt-get update -qq

    echo "[*] Installing wireless tools..."
    apt-get install -y -qq \
      hostapd \
      dnsmasq \
      aircrack-ng \
      iw \
      wpasupplicant \
      kmod \
      iproute2 \
      procps \
      curl \
      iputils-arping \
      dnsutils \
      iputils-ping \
      isc-dhcp-client \
      net-tools \
      freeradius \
      > /dev/null 2>&1

    echo "[*] Installing EaphammerMeals tools..."
      apt-get install -y -qq \
        apache2 \
        dnsmasq \
        libssl-dev \
        libnfnetlink-dev \
        libnl-3-dev \
        libnl-genl-3-dev \
        libcurl4-openssl-dev \
        zlib1g-dev \
        libpcap-dev \
        wget \
        python3-pip \
        python3-gevent \
        python3-tqdm \
        python3-pem \
        python3-openssl \
        python3-scapy \
        python3-lxml \
        python3-bs4 \
        python3-flask-cors \
        python3-flask-socketio \
        > /dev/null 2>&1






    # Stop system dnsmasq immediately - we manage our own
    systemctl stop dnsmasq 2>/dev/null || true
    systemctl disable dnsmasq 2>/dev/null || true
    systemctl mask dnsmasq 2>/dev/null || true

    echo "[*] Installing dependencies for hacking tools..."
    apt-get install -y -qq \
      git \
      python3-scapy \
      tshark \
      tcpdump \
      macchanger \
      hashcat \
      reaver \
      bully \
      mdk4 \
      pixiewps \
      cowpatty \
      hcxtools \
      hcxdumptool \
      lighttpd \
      php-cgi \
      dsniff \
      > /dev/null 2>&1

    # Disable lighttpd (installed for tools but conflicts with nginx on port 80)
    systemctl stop lighttpd 2>/dev/null || true
    systemctl disable lighttpd 2>/dev/null || true
    systemctl stop apache2 2>/dev/null || true
    systemctl disable apache2 2>/dev/null || true


    echo "[*] Installing Python..."
    apt-get install -y -qq \
      python3 \
      python3-pip \
      python3-venv \
      > /dev/null 2>&1

    echo "[*] Installing nginx..."
    apt-get install -y -qq nginx > /dev/null 2>&1

    echo "[*] Installing Node.js (for frontend build)..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - > /dev/null 2>&1
    apt-get install -y -qq nodejs > /dev/null 2>&1

    echo "[*] Installing kernel modules..."
    apt-get install -y -qq linux-headers-$(uname -r) > /dev/null 2>&1 || true

    echo "[*] Setting up BeaconHub..."
    # Create app directory
    mkdir -p /opt/beaconhub
    mkdir -p /opt/tools/wordlists
    rm -rf /opt/beaconhub/backend
    rm -rf /opt/beaconhub/scripts
    cp -r /vagrant/backend /opt/beaconhub/backend
    mkdir -p /opt/beaconhub/scripts
    cp -r /vagrant/scripts/* /opt/beaconhub/scripts/
    cp /vagrant/configs/nginx.conf /etc/nginx/sites-available/beaconhub
    chmod +x /opt/beaconhub/scripts/*.sh 2>/dev/null || true
    
    # Install attack helper script
    ln -sf /opt/beaconhub/scripts/attack.sh /usr/local/bin/attack
    chmod +x /opt/beaconhub/scripts/attack.sh
    
    # Copy wordlists
    if [ -d "/vagrant/wordlists" ]; then
        cp -r /vagrant/wordlists/* /opt/tools/wordlists/ 2>/dev/null || true
    fi

    # Remove default nginx site, add ours
    rm -f /etc/nginx/sites-enabled/default
    ln -sf /etc/nginx/sites-available/beaconhub /etc/nginx/sites-enabled/beaconhub
    # Restart nginx so it picks up the new config (plain 'start' is a no-op when already running)
    systemctl restart nginx

    # Disable freeradius autostart (we manage it ourselves)
    systemctl disable freeradius 2>/dev/null || true
    systemctl stop freeradius 2>/dev/null || true

    # Install Python dependencies
    pip3 install --break-system-packages -q \
      fastapi uvicorn[standard] pydantic websockets python-multipart

    # ==========================================
    # Install WiFi Hacking Tools
    # ==========================================
    echo "[*] Installing WiFi hacking tools..."
    
    # Create tools directory
    mkdir -p /opt/tools
    cd /opt/tools

    # --- Wifite2 ---
    echo "    - Installing Wifite2..."
    if [ ! -d "/opt/tools/wifite2" ]; then
      git clone --depth 1 https://github.com/derv82/wifite2.git /opt/tools/wifite2 > /dev/null 2>&1
      ln -sf /opt/tools/wifite2/Wifite.py /usr/local/bin/wifite
      chmod +x /opt/tools/wifite2/Wifite.py
    fi

    # --- Airgeddon ---
    echo "    - Installing Airgeddon..."
    if [ ! -d "/opt/tools/airgeddon" ]; then
      git clone --depth 1 https://github.com/v1s1t0r1sh3r3/airgeddon.git /opt/tools/airgeddon > /dev/null 2>&1
      ln -sf /opt/tools/airgeddon/airgeddon.sh /usr/local/bin/airgeddon
      chmod +x /opt/tools/airgeddon/airgeddon.sh
    fi

    # --- Wifiphisher ---
    echo "    - Installing Wifiphisher..."
    pip3 install --break-system-packages -q wifiphisher 2>/dev/null || {
      # If pip install fails, install from source
      if [ ! -d "/opt/tools/wifiphisher" ]; then
        git clone --depth 1 https://github.com/wifiphisher/wifiphisher.git /opt/tools/wifiphisher > /dev/null 2>&1
        cd /opt/tools/wifiphisher
        pip3 install --break-system-packages -q . 2>/dev/null || true
        cd /opt/tools
      fi
    }

    # --- EAPHammer ---
    echo "    - Installing EAPHammer..."
    if [ ! -d "/opt/tools/eaphammer" ]; then
      git clone --depth 1 https://github.com/s0lst1c3/eaphammer.git /opt/tools/eaphammer > /dev/null 2>&1
      cd /opt/tools/eaphammer
      # Install EAPHammer dependencies
      apt-get install -y -qq libssl-dev libffi-dev build-essential > /dev/null 2>&1
      pip3 install --break-system-packages -q -r requirements.txt 2>/dev/null || true
      # Run the setup (non-interactive)
      echo "y" | python3 setup.py 2>/dev/null || true
      ln -sf /opt/tools/eaphammer/eaphammer /usr/local/bin/eaphammer
      chmod +x /opt/tools/eaphammer/eaphammer
      pip install pywebcopy --break-system-packages 2>/dev/null

      if [ -d "/opt/tools/eaphammer/local/hostapd-eaphammer/hostapd" ]; then
        cd /opt/tools/eaphammer/local/hostapd-eaphammer/hostapd
        echo "    - Building EAPHammer hostapd library with -fPIC..."
        apt-get install -y -qq build-essential pkg-config libssl-dev libnl-3-dev libnl-genl-3-dev > /dev/null 2>&1
        make clean > /tmp/eaphammer-hostapd-build.log 2>&1 || true
        if ! CFLAGS="-fPIC" make hostapd-eaphammer_lib >> /tmp/eaphammer-hostapd-build.log 2>&1; then
          echo "    ! hostapd-eaphammer_lib build failed; retrying full hostapd target"
          CFLAGS="-fPIC" make >> /tmp/eaphammer-hostapd-build.log 2>&1 || {
            echo "    ! EAPHammer hostapd build failed. See /tmp/eaphammer-hostapd-build.log inside the VM"
          }
        fi
      fi

      cd /opt/tools/eaphammer && bash ubuntu-unattended-setup > /dev/null 2>&1 || true
      cd /opt/tools
      echo "    - EAPHammer ready"


    fi

    echo "[+] WiFi hacking tools installed:"
    echo "    - wifite      : Automated wireless attack tool"
    echo "    - airgeddon   : Multi-use bash script for wireless auditing"  
    echo "    - wifiphisher : Rogue AP framework for credential harvesting"
    echo "    - eaphammer   : WPA2-Enterprise attack tool"
    echo ""
    echo "    Tools location: /opt/tools/"
    # Build frontend
    echo "[*] Building frontend..."
    cd /vagrant/frontend
    rm -rf node_modules
    npm install 2>&1 | tail -5
    npm run build 2>&1 | tail -5
    if [ -d "dist" ]; then
      rm -rf /opt/beaconhub/frontend
      cp -r dist /opt/beaconhub/frontend
      echo "[+] Frontend built successfully"
    else
      echo "[!] Frontend build failed - creating placeholder"
      mkdir -p /opt/beaconhub/frontend
      echo "<html><body><h1>BeaconHub</h1><p>Frontend build failed. Run: beaconhub rebuild</p></body></html>" > /opt/beaconhub/frontend/index.html
    fi

    # Install the CLI command
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

    # Disable auto-start of hostapd and dnsmasq
    systemctl disable hostapd 2>/dev/null || true
    systemctl stop hostapd 2>/dev/null || true
    systemctl disable dnsmasq 2>/dev/null || true
    systemctl stop dnsmasq 2>/dev/null || true

    # Verify mac80211_hwsim
    echo ""
    if modinfo mac80211_hwsim > /dev/null 2>&1; then
      echo "[+] mac80211_hwsim available"
    else
      echo "[!] mac80211_hwsim not found - trying to load anyway"
    fi

    echo ""
    echo "==========================================="
    echo " BeaconHub installed!"
    echo "==========================================="
    echo ""
    echo " Web UI:  http://localhost:8080"
    echo ""
    echo " Commands:"
    echo "   vagrant ssh           - Enter the VM"
    echo "   beaconhub start       - Start the lab"
    echo "   beaconhub stop        - Stop the lab"
    echo "   beaconhub status      - Check status"
    echo ""
    echo " Hacking Tools (run inside VM):"
    echo "   wifite                - Automated WiFi attacks"
    echo "   airgeddon             - WiFi auditing framework"
    echo "   wifiphisher           - Rogue AP phishing"
    echo "   eaphammer             - WPA2-Enterprise attacks"
    echo ""
    echo " Tools are in /opt/tools/"
    echo "==========================================="
    
    # ==========================================
    # Create systemd service for BeaconHub
    # ==========================================
    echo "[*] Creating BeaconHub systemd service..."
    
    # Create necessary directories
    mkdir -p /opt/beaconhub/configs/hostapd
    mkdir -p /opt/beaconhub/configs/dnsmasq
    mkdir -p /opt/beaconhub/configs/wpa_supplicant
    mkdir -p /opt/beaconhub/configs/radius
    mkdir -p /opt/beaconhub/configs/radius/certs
    mkdir -p /opt/beaconhub/run
    mkdir -p /opt/beaconhub/captures
    mkdir -p /opt/beaconhub/leases
    mkdir -p /opt/beaconhub/logs
    mkdir -p /var/run/wpa_supplicant
    chmod -R 777 /opt/beaconhub/configs /opt/beaconhub/run /opt/beaconhub/captures /opt/beaconhub/leases /opt/beaconhub/logs
    
    cat > /etc/systemd/system/beaconhub.service << 'SVCEOF'
[Unit]
Description=BeaconHub WiFi Security Lab Backend
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/beaconhub
ExecStartPre=/bin/bash -c 'modprobe mac80211_hwsim radios=6 || true'
ExecStartPre=/bin/bash -c 'mkdir -p /opt/beaconhub/configs/hostapd /opt/beaconhub/configs/dnsmasq /opt/beaconhub/configs/wpa_supplicant /opt/beaconhub/run /opt/beaconhub/leases /opt/beaconhub/logs /var/run/wpa_supplicant && chmod -R 777 /opt/beaconhub/configs /opt/beaconhub/run /opt/beaconhub/leases /opt/beaconhub/logs'
ExecStartPre=/bin/bash -c 'sysctl -w net.ipv4.ip_forward=1'
ExecStart=/usr/bin/python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 1 --log-level info
ExecStop=/bin/kill -TERM $MAINPID
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
SVCEOF

    # Enable and start the service
    systemctl daemon-reload
    systemctl enable beaconhub
    
    # Load kernel module now
    echo "[*] Loading mac80211_hwsim kernel module..."
    modprobe mac80211_hwsim radios=6 || echo "[!] Note: hwsim may fail in provisioning but works after reboot"
    
    # Start BeaconHub service
    echo "[*] Starting BeaconHub backend service..."
    systemctl start beaconhub || echo "[!] Service start may fail during provisioning - will work after reboot"
    
    # Wait for backend to be ready
    sleep 3
    
    # Test if backend is running
    if curl -s http://127.0.0.1:8000/api/health > /dev/null 2>&1; then
      echo "[+] BeaconHub backend is running!"
    else
      echo "[!] Backend not yet ready - will start on next boot"
    fi
    
    echo ""
    echo "==========================================="
    echo " BeaconHub is ready!"
    echo "==========================================="
    echo ""
    echo " Web UI:  http://localhost:8080"
    echo ""
    echo " The lab auto-starts on boot."
    echo " No manual steps required!"
    echo ""
    echo " Quick test: curl http://localhost:8080/api/health"
    echo ""
    echo "==========================================="
  SHELL

  config.vm.synced_folder ".", "/vagrant"
end
