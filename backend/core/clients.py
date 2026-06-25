"""
Client bot manager.
Simulates wireless clients connecting to APs using wpa_supplicant.
Generates realistic traffic noise after connection.
"""

import os
import re
import signal
import subprocess
import logging
import time
import threading
import string
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

CONFIG_DIR = "/opt/beaconhub/configs/wpa_supplicant"
RUN_DIR = "/opt/beaconhub/run"


class ClientBotError(Exception):
    pass


class ClientBot:
    """Represents a simulated wireless client."""

    def __init__(self, client_id: str, interface: str, ap_id: str):
        self.client_id = client_id
        self.interface = interface
        self.ap_id = ap_id
        self.process: Optional[subprocess.Popen] = None
        self.dhcp_process: Optional[subprocess.Popen] = None
        self.noise_thread: Optional[threading.Thread] = None
        self.pid: Optional[int] = None
        self.config_path: str = ""
        self.connected: bool = False
        self.connection_state: str = "created"
        self.last_error: Optional[str] = None
        self.connected_at: float = 0
        self.mac_address: str = ""
        self.ip_address: Optional[str] = None
        self.persona: Optional[str] = None
        self.device_type: Optional[str] = None
        self.hostname: Optional[str] = None
        self._stop_noise: bool = False
        self._traffic_running: bool = False
        self.traffic_count: int = 0

        # Stored credentials (can be false/fake)
        self.credentials: Optional[dict] = None

        # Store ssid/security/password for reconnect
        self.ssid: str = ""
        self.security: str = "wpa2-psk"
        self.password: Optional[str] = None
        self.eap_identity: Optional[str] = None  # EAP identity for WPA2-Enterprise
        self.eap_password: Optional[str] = None
        
        # Auto-reconnect settings
        self.auto_reconnect: bool = True
        self._reconnect_thread: Optional[threading.Thread] = None
        self._stop_reconnect_watcher: bool = False

    @property
    def is_running(self) -> bool:
        if self.process is None:
            return False
        return self.process.poll() is None

    @property
    def traffic_running(self) -> bool:
        return self._traffic_running


class ClientManager:
    """Manages simulated client bots that connect to APs."""

    # Device personas for realistic simulation
    PERSONAS = [
        {"persona": "John Smith", "device_type": "laptop", "hostname": "JOHNS-THINKPAD"},
        {"persona": "Sarah Connor", "device_type": "macbook", "hostname": "Sarahs-MacBook-Pro"},
        {"persona": "DevOps Bot", "device_type": "server", "hostname": "devops-ubuntu-01"},
        {"persona": "Alice Chen", "device_type": "smartphone", "hostname": "alice-iphone"},
        {"persona": "Bob Marley", "device_type": "tablet", "hostname": "Bobs-iPad"},
        {"persona": "Scanner Bot", "device_type": "iot", "hostname": "rpi-scanner-01"},
        {"persona": "Mark Davis", "device_type": "laptop", "hostname": "MARK-DELL-XPS"},
        {"persona": "Eva Müller", "device_type": "macbook", "hostname": "eva-macbook-air"},
    ]
    
    # Known networks that clients will probe for (simulates real device behavior)
    # These SSIDs are visible in airodump-ng probes column and can be used for evil twin attacks
    KNOWN_NETWORKS = [
        "HOME-WIFI",
        "Starbucks WiFi",
        "xfinitywifi",
        "attwifi",
        "Google Starbucks",
        "AndroidAP",
        "iPhone",
        "NETGEAR",
        "linksys",
        "default",
        "FreeWifi",
        "Guest",
        "Corporate",
        "DIRECT-",
        "HP-Print",
    ]

    def __init__(self):
        self._clients: Dict[str, ClientBot] = {}
        self._reconnect_watcher_running: bool = False
        self._reconnect_watcher_thread: Optional[threading.Thread] = None
        self._probe_threads: Dict[str, threading.Thread] = {}
        os.makedirs(CONFIG_DIR, exist_ok=True)
        
        # Start global reconnect watcher
        self._start_reconnect_watcher()

    def _start_reconnect_watcher(self):
        """Start a background thread that monitors client connections and auto-reconnects."""
        if self._reconnect_watcher_running:
            return
        
        self._reconnect_watcher_running = True
        
        def watcher():
            while self._reconnect_watcher_running:
                try:
                    for client_id, bot in list(self._clients.items()):
                        if not bot.auto_reconnect:
                            continue
                        
                        # Check if wpa_supplicant is still running
                        if bot.process and bot.process.poll() is not None:
                            # Process died - reconnect
                            logger.info(f"Client {client_id} ({bot.persona}) wpa_supplicant died, auto-reconnecting...")
                            try:
                                self.reconnect(client_id)
                                logger.info(f"Client {client_id} auto-reconnected successfully")
                            except Exception as e:
                                logger.error(f"Auto-reconnect failed for {client_id}: {e}")
                        
                        # Also check if client lost connection (no IP or disconnected state)
                        elif bot.is_running:
                            # Check wpa_supplicant status
                            try:
                                result = subprocess.run(
                                    ["wpa_cli", "-i", bot.interface, "status"],
                                    capture_output=True, text=True, timeout=3
                                )
                                if "wpa_state=DISCONNECTED" in result.stdout or "wpa_state=INACTIVE" in result.stdout:
                                    logger.info(f"Client {client_id} ({bot.persona}) disconnected (deauth?), auto-reconnecting...")
                                    self.reconnect(client_id)
                                    logger.info(f"Client {client_id} auto-reconnected (handshake regenerated)")
                            except Exception:
                                pass  # Ignore errors checking status
                
                except Exception as e:
                    logger.error(f"Reconnect watcher error: {e}")
                
                time.sleep(2)  # Check every 2 seconds for faster handshake capture after deauth
        
        self._reconnect_watcher_thread = threading.Thread(target=watcher, daemon=True, name="ClientReconnectWatcher")
        self._reconnect_watcher_thread.start()
        logger.info("Client auto-reconnect watcher started")

    def _stop_reconnect_watcher(self):
        """Stop the reconnect watcher thread."""
        self._reconnect_watcher_running = False
        if self._reconnect_watcher_thread:
            self._reconnect_watcher_thread.join(timeout=2)

    def stop_reconnect_watcher(self):
        """Public method to stop the reconnect watcher thread."""
        self._stop_reconnect_watcher()

    def generate_config(
        self,
        client_id: str,
        ssid: str,
        security: str = "wpa2-psk",
        password: Optional[str] = None,
    ) -> str:
        """Generate wpa_supplicant config for connecting to an AP."""
        config_path = os.path.join(CONFIG_DIR, f"{client_id}.conf")

        # Sanitize
        ssid = ssid.replace('"', '').replace('\n', '').replace('\r', '')
        if password:
            password = password.replace('"', '').replace('\n', '').replace('\r', '')

        if security == "open":
            config_content = (
                f"ctrl_interface=/var/run/wpa_supplicant/{client_id}\n"
                f"ap_scan=1\n"
                f"network={{\n"
                f"    ssid=\"{ssid}\"\n"
                f"    key_mgmt=NONE\n"
                f"    scan_ssid=1\n"
                f"}}\n"
            )
        elif security == "wep":
            if not password:
                raise ClientBotError("WEP requires a key")
            # WEP key handling - can be ASCII (quoted) or hex (unquoted)
            if len(password) in (5, 13):
                # ASCII key - needs quotes
                wep_key = f'"{password}"'
            elif len(password) in (10, 26) and all(ch in string.hexdigits for ch in password):
                # Hex key - no quotes
                wep_key = password
            else:
                raise ClientBotError("WEP key must be 5/13 ASCII chars or 10/26 hex digits")
            config_content = (
                f"ctrl_interface=/var/run/wpa_supplicant/{client_id}\n"
                f"ap_scan=1\n"
                f"network={{\n"
                f"    ssid=\"{ssid}\"\n"
                f"    key_mgmt=NONE\n"
                f"    wep_key0={wep_key}\n"
                f"    wep_tx_keyidx=0\n"
                f"    auth_alg=SHARED OPEN\n"
                f"    scan_ssid=1\n"
                f"}}\n"
            )
        elif security == "wpa2-psk":
            if not password:
                raise ClientBotError("WPA2-PSK requires a password")
            config_content = (
                f"ctrl_interface=/var/run/wpa_supplicant/{client_id}\n"
                f"ap_scan=1\n"
                f"network={{\n"
                f"    ssid=\"{ssid}\"\n"
                f"    psk=\"{password}\"\n"
                f"    key_mgmt=WPA-PSK\n"
                f"    proto=RSN WPA\n"
                f"    pairwise=CCMP TKIP\n"
                f"    group=CCMP TKIP\n"
                f"    scan_ssid=1\n"
                f"}}\n"
            )
        elif security == "wpa2-enterprise":
            # Use provided identity/password or defaults
            identity = "employee@corp.local"
            eap_password = "Welcome123"
            if password and ":" in password:
                parts = password.split(":", 1)
                identity = parts[0]
                eap_password = parts[1] if len(parts) > 1 else "Welcome123"
            elif password:
                eap_password = password
            
            config_content = (
                f"ctrl_interface=/var/run/wpa_supplicant/{client_id}\n"
                f"ap_scan=1\n"
                f"network={{\n"
                f"    ssid=\"{ssid}\"\n"
                f"    key_mgmt=WPA-EAP\n"
                f"    eap=PEAP\n"
                f"    identity=\"{identity}\"\n"
                f"    password=\"{eap_password}\"\n"
                f"    phase2=\"auth=MSCHAPV2\"\n"
                f"    scan_ssid=1\n"
                f"}}\n"
            )
        else:
            config_content = (
                f"ctrl_interface=/var/run/wpa_supplicant/{client_id}\n"
                f"ap_scan=1\n"
                f"network={{\n"
                f"    ssid=\"{ssid}\"\n"
                f"    key_mgmt=NONE\n"
                f"    scan_ssid=1\n"
                f"}}\n"
            )

        with open(config_path, "w") as f:
            f.write(config_content)

        return config_path

    def connect(
        self,
        client_id: str,
        interface: str,
        ap_id: str,
        ssid: str,
        security: str = "wpa2-psk",
        password: Optional[str] = None,
        persona: Optional[str] = None,
        device_type: Optional[str] = None,
        hostname: Optional[str] = None,
    ) -> ClientBot:
        """Connect a client bot to an AP using proper authentication."""
        if client_id in self._clients and self._clients[client_id].is_running:
            raise ClientBotError(f"Client {client_id} is already connected")

        # Auto-assign persona if not provided
        if persona is None:
            idx = len(self._clients) % len(self.PERSONAS)
            p = self.PERSONAS[idx]
            persona = p["persona"]
            device_type = p["device_type"]
            hostname = p["hostname"]

        config_path = self.generate_config(client_id, ssid, security, password)

        # Get MAC address
        mac = "00:00:00:00:00:00"
        try:
            result = subprocess.run(
                ["ip", "link", "show", interface],
                capture_output=True, text=True, timeout=5
            )
            match = re.search(r"link/ether\s+([\da-f:]+)", result.stdout)
            if match:
                mac = match.group(1)
        except Exception:
            pass

        # Ensure interface is up and in managed mode
        subprocess.run(["ip", "link", "set", interface, "up"],
                       capture_output=True, text=True, timeout=5)

        log_file = os.path.join(RUN_DIR, f"client_{client_id}.log")

        try:
            ctrl_dir = f"/var/run/wpa_supplicant/{client_id}"
            os.makedirs(ctrl_dir, exist_ok=True)

            log_fd = open(log_file, "w")
            process = subprocess.Popen(
                [
                    "wpa_supplicant",
                    "-i", interface,
                    "-c", config_path,
                    "-D", "nl80211",
                ],
                stdout=log_fd,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid
            )
            log_fd.close()

            # Wait for WPA authentication. A wrong password is still a useful
            # lab state, so we keep the client record even if auth/DHCP fails.
            time.sleep(2)

            try:
                subprocess.run(["dhclient", "-r", interface],
                               capture_output=True, text=True, timeout=5)
                time.sleep(0.5)

                # -1 means try once then exit. Failure is expected for fake,
                # offline, rogue, or wrong-password client simulations.
                dhcp_result = subprocess.run(
                    ["dhclient", "-v", "-1", interface],
                    capture_output=True, text=True, timeout=15
                )
                logger.info(f"DHCP for {interface}: returncode={dhcp_result.returncode}")
                if dhcp_result.stdout:
                    logger.debug(f"DHCP stdout: {dhcp_result.stdout[:500]}")
                if dhcp_result.stderr:
                    logger.debug(f"DHCP stderr: {dhcp_result.stderr[:500]}")
            except Exception as e:
                logger.warning(f"DHCP did not complete for {interface}: {e}")

            bot = ClientBot(client_id, interface, ap_id)
            bot.process = process
            bot.dhcp_process = None  # No longer tracking async process
            bot.pid = process.pid
            bot.config_path = config_path
            bot.mac_address = mac
            bot.connected = False
            bot.connection_state = "authenticating"
            bot.connected_at = time.time()
            bot.persona = persona
            bot.device_type = device_type
            bot.hostname = hostname
            bot.ssid = ssid
            bot.security = security
            bot.password = password
            if security == "wpa2-enterprise" and password and ":" in password:
                bot.eap_identity = password.split(":", 1)[0]
                bot.eap_password = password.split(":", 1)[1]
            self._clients[client_id] = bot

            self._refresh_connection_state(bot)

            # Get IP (should already be assigned by dhclient)
            bot.ip_address = self._get_interface_ip(interface)
            if not bot.ip_address:
                # DHCP might have failed or still completing, try a few more times
                for attempt in range(3):
                    time.sleep(1)
                    bot.ip_address = self._get_interface_ip(interface)
                    if bot.ip_address:
                        break
            self._refresh_connection_state(bot)
            logger.info(f"Client {client_id} got IP: {bot.ip_address or 'none'}")
            
            # Start background noise traffic
            # For WEP, start aggressive mode automatically to generate IVs
            is_wep = (security == "wep")
            self.start_traffic(client_id, aggressive=is_wep)

            logger.info(f"Client {client_id} ({persona}) connected to AP {ap_id} via {interface} (IP: {bot.ip_address})")
            return bot

        except FileNotFoundError:
            raise ClientBotError("wpa_supplicant not found. Is it installed?")
        except Exception as e:
            raise ClientBotError(f"Failed to connect client: {str(e)}")

    def _refresh_connection_state(self, bot: ClientBot) -> str:
        """Update and return a client state without deleting useful lab clients."""
        if not bot.process or bot.process.poll() is not None:
            bot.connected = False
            bot.connection_state = "supplicant_stopped"
            bot.last_error = "wpa_supplicant is not running"
            return bot.connection_state

        state = "authenticating"
        try:
            result = subprocess.run(
                ["wpa_cli", "-i", bot.interface, "status"],
                capture_output=True, text=True, timeout=3
            )
            match = re.search(r"^wpa_state=(.+)$", result.stdout, re.MULTILINE)
            if match:
                wpa_state = match.group(1).strip()
                if wpa_state == "COMPLETED":
                    state = "connected" if bot.ip_address else "associated_no_ip"
                    bot.last_error = None if bot.ip_address else "Associated, waiting for DHCP"
                elif wpa_state in ("DISCONNECTED", "INACTIVE", "SCANNING", "ASSOCIATING", "ASSOCIATED", "4WAY_HANDSHAKE", "GROUP_HANDSHAKE"):
                    state = wpa_state.lower()
                    bot.last_error = f"wpa_supplicant state: {wpa_state}"
                else:
                    state = wpa_state.lower()
                    bot.last_error = None
        except Exception as e:
            bot.last_error = f"status check failed: {e}"

        bot.connected = state in ("connected", "associated_no_ip")
        bot.connection_state = state
        return state

    def start_traffic(self, client_id: str, interval: int = 10, aggressive: bool = False) -> bool:
        """Start continuous background traffic for a client.
        
        Args:
            client_id: Client identifier
            interval: Seconds between traffic bursts (default 10)
            aggressive: If True, generate high-volume traffic for WEP IV collection
        """
        bot = self._clients.get(client_id)
        if not bot:
            return False
        self._refresh_connection_state(bot)
        if bot._traffic_running:
            return True  # Already running

        bot._stop_noise = False
        bot._traffic_running = True

        def noise_worker():
            """Generate periodic traffic bound to the client interface."""
            urls = [
                "http://example.com",
                "http://httpbin.org/get",
                "http://neverssl.com",
            ]
            domains = ["google.com", "cloudflare.com", "microsoft.com", "amazon.com"]
            url_idx = 0
            domain_idx = 0
            
            # For aggressive mode (WEP cracking), use much faster intervals
            actual_interval = 0.05 if aggressive else interval

            idle_tick = 0
            while not bot._stop_noise and bot.is_running:
                try:
                    self._refresh_connection_state(bot)
                    if not bot.ip_address:
                        # Even unauthenticated clients are useful: they keep probing,
                        # scanning, and trying to reconnect for rogue AP workflows.
                        subprocess.run(
                            ["wpa_cli", "-i", bot.interface, "scan"],
                            capture_output=True, timeout=3
                        )
                        bot.traffic_count += 1
                        idle_tick += 1
                        time.sleep(max(2, min(interval, 10)))
                        continue

                    if aggressive:
                        # ============================================
                        # AGGRESSIVE MODE: For WEP IV Generation
                        # ============================================
                        # WEP cracking requires thousands of IVs (encrypted packets)
                        # ARP replay attack (aireplay-ng -3) captures an ARP packet
                        # and replays it to generate massive IV traffic.
                        # We need to generate continuous ARP traffic for this.
                        
                        if bot.ip_address:
                            gateway = bot.ip_address.rsplit('.', 1)[0] + '.1'
                            network = bot.ip_address.rsplit('.', 1)[0]
                            
                            # === ARP Requests (CRITICAL for WEP) ===
                            # These are the packets aireplay-ng -3 captures and replays
                            # Generate ARP who-has requests rapidly
                            for target_host in range(1, 10):
                                target = f"{network}.{target_host}"
                                subprocess.run(
                                    ["arping", "-c", "1", "-w", "1", "-I", bot.interface, target],
                                    capture_output=True, timeout=2
                                )
                                bot.traffic_count += 1
                            
                            # ARP to gateway (most reliable)
                            subprocess.run(
                                ["arping", "-c", "10", "-w", "2", "-I", bot.interface, gateway],
                                capture_output=True, timeout=5
                            )
                            bot.traffic_count += 10
                            
                            # === ICMP Ping flood (generates encrypted data) ===
                            subprocess.run(
                                ["ping", "-c", "20", "-i", "0.05", "-s", "100", "-W", "1", "-I", bot.interface, gateway],
                                capture_output=True, timeout=5
                            )
                            bot.traffic_count += 20
                            
                            # === Small HTTP request (more data packets) ===
                            subprocess.run(
                                ["curl", "-s", "-o", "/dev/null", "--interface", bot.interface, 
                                 "--max-time", "2", "--connect-timeout", "1", "http://example.com"],
                                capture_output=True, timeout=4
                            )
                            bot.traffic_count += 5
                            
                            # === UDP traffic (DNS queries generate packets) ===
                            subprocess.run(
                                ["nslookup", "google.com", gateway],
                                capture_output=True, timeout=2
                            )
                            bot.traffic_count += 2
                        
                        time.sleep(actual_interval)
                    else:
                        # ============================================
                        # NORMAL MODE: Regular background traffic
                        # ============================================
                        # DNS query
                        domain = domains[domain_idx % len(domains)]
                        subprocess.run(
                            ["nslookup", domain],
                            capture_output=True, text=True, timeout=3
                        )
                        domain_idx += 1
                        bot.traffic_count += 1
                        time.sleep(actual_interval / 3)

                        if bot._stop_noise:
                            break

                        # Ping gateway (generates ICMP traffic)
                        if bot.ip_address:
                            gateway = bot.ip_address.rsplit('.', 1)[0] + '.1'
                            subprocess.run(
                                ["ping", "-c", "2", "-W", "1", "-I", bot.interface, gateway],
                                capture_output=True, text=True, timeout=5
                            )
                        bot.traffic_count += 1
                        time.sleep(actual_interval / 3)

                        if bot._stop_noise:
                            break

                        # HTTP browse (generates TCP traffic)
                        url = urls[url_idx % len(urls)]
                        subprocess.run(
                            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                             "--interface", bot.interface, "--max-time", "4", url],
                            capture_output=True, text=True, timeout=6
                        )
                        url_idx += 1
                        bot.traffic_count += 1
                        time.sleep(actual_interval / 3)

                except Exception:
                    time.sleep(actual_interval if aggressive else interval)

            bot._traffic_running = False

        bot.noise_thread = threading.Thread(target=noise_worker, daemon=True)
        bot.noise_thread.start()
        return True

    def stop_traffic(self, client_id: str) -> bool:
        """Stop continuous background traffic for a client."""
        bot = self._clients.get(client_id)
        if not bot:
            return False
        bot._stop_noise = True
        bot._traffic_running = False
        return True

    def set_credentials(self, client_id: str, username: str, password: str, url: str) -> bool:
        """Store credentials for a client (can be false/fake)."""
        bot = self._clients.get(client_id)
        if not bot:
            return False
        bot.credentials = {"username": username, "password": password, "url": url}
        return True

    def submit_credentials(self, client_id: str) -> dict:
        """Submit stored credentials via HTTP POST (generates plaintext traffic)."""
        bot = self._clients.get(client_id)
        if not bot or not bot.credentials:
            return {"status": "error", "message": "No credentials stored"}

        creds = bot.credentials
        try:
            result = subprocess.run(
                ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                 "--interface", bot.interface, "--max-time", "5",
                 "-X", "POST",
                 "-d", f"username={creds['username']}&password={creds['password']}",
                 creds["url"]],
                capture_output=True, text=True, timeout=10
            )
            bot.traffic_count += 1
            return {"status": "ok", "http_code": result.stdout.strip(), "message": "Credentials submitted (visible in capture)"}
        except Exception as e:
            return {"status": "ok", "message": f"POST sent (traffic generated): {e}"}

    def reconnect(self, client_id: str) -> bool:
        """Force reconnect a client (generates new WPA handshake)."""
        bot = self._clients.get(client_id)
        if not bot:
            return False
        
        # Remember if traffic was running
        was_running_traffic = bot._traffic_running
        
        try:
            # Stop traffic if running
            if bot._traffic_running:
                self.stop_traffic(client_id)
            
            # Kill wpa_supplicant
            subprocess.run(["pkill", "-f", f"wpa_supplicant.*{bot.interface}"],
                           capture_output=True, timeout=3)
            time.sleep(1)
            # Re-generate config and restart
            config_path = self.generate_config(bot.client_id, bot.ssid, bot.security, bot.password)
            bot.config_path = config_path

            ctrl_dir = f"/var/run/wpa_supplicant/{bot.client_id}"
            os.makedirs(ctrl_dir, exist_ok=True)

            log_file = os.path.join(RUN_DIR, f"client_{bot.client_id}.log")
            log_fd = open(log_file, "a")
            process = subprocess.Popen(
                ["wpa_supplicant", "-i", bot.interface, "-c", config_path, "-D", "nl80211"],
                stdout=log_fd, stderr=subprocess.STDOUT,
                preexec_fn=os.setsid
            )
            log_fd.close()
            bot.process = process
            bot.pid = process.pid
            bot.connection_state = "authenticating"
            bot.last_error = None
            
            try:
                subprocess.run(["dhclient", "-r", bot.interface],
                               capture_output=True, text=True, timeout=5)
                subprocess.run(["dhclient", "-v", "-1", bot.interface],
                               capture_output=True, text=True, timeout=15)
            except Exception as e:
                logger.warning(f"DHCP did not complete during reconnect for {bot.interface}: {e}")

            # Wait for DHCP with retry
            for attempt in range(5):
                time.sleep(1)
                bot.ip_address = self._get_interface_ip(bot.interface)
                if bot.ip_address:
                    break
            self._refresh_connection_state(bot)
            
            # Restart traffic if it was running before (or start it anyway for handshake generation)
            # For WEP, use aggressive mode
            is_wep = (bot.security == "wep")
            self.start_traffic(client_id, aggressive=is_wep)
            
            return True
        except Exception as e:
            logger.error(f"Reconnect failed for {client_id}: {e}")
            return False

    def disconnect(self, client_id: str) -> bool:
        """Disconnect a client bot."""
        if client_id not in self._clients:
            return False

        bot = self._clients[client_id]
        bot._stop_noise = True
        bot._traffic_running = False

        # Kill dhclient
        if bot.dhcp_process:
            try:
                os.killpg(os.getpgid(bot.dhcp_process.pid), signal.SIGTERM)
                bot.dhcp_process.wait(timeout=3)
            except Exception:
                pass

        # Release DHCP lease
        try:
            subprocess.run(["dhclient", "-r", bot.interface],
                           capture_output=True, text=True, timeout=5)
        except Exception:
            pass

        # Kill wpa_supplicant
        if bot.process and bot.is_running:
            try:
                os.killpg(os.getpgid(bot.process.pid), signal.SIGTERM)
                bot.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(bot.process.pid), signal.SIGKILL)
                except Exception:
                    pass
            except ProcessLookupError:
                pass
            except Exception as e:
                logger.error(f"Error disconnecting client {client_id}: {e}")

        # Also kill any lingering wpa_supplicant on this interface
        try:
            subprocess.run(["pkill", "-f", f"wpa_supplicant.*{bot.interface}"],
                           capture_output=True, text=True, timeout=5)
        except Exception:
            pass

        # Flush interface
        try:
            subprocess.run(["ip", "addr", "flush", "dev", bot.interface],
                           capture_output=True, text=True, timeout=5)
        except Exception:
            pass

        # Cleanup config
        if bot.config_path and os.path.exists(bot.config_path):
            try:
                os.remove(bot.config_path)
            except Exception:
                pass

        del self._clients[client_id]
        logger.info(f"Disconnected client {client_id}")
        return True

    def disconnect_all(self):
        """Disconnect all client bots."""
        client_ids = list(self._clients.keys())
        for client_id in client_ids:
            self.disconnect(client_id)

    def disconnect_by_ap(self, ap_id: str):
        """Disconnect all clients connected to a specific AP."""
        to_disconnect = [
            cid for cid, bot in self._clients.items()
            if bot.ap_id == ap_id
        ]
        for client_id in to_disconnect:
            self.disconnect(client_id)

    def get_client(self, client_id: str) -> Optional[ClientBot]:
        bot = self._clients.get(client_id)
        if bot:
            bot.ip_address = self._get_interface_ip(bot.interface)
            self._refresh_connection_state(bot)
        return bot

    def get_clients_for_ap(self, ap_id: str) -> List[ClientBot]:
        bots = [bot for bot in self._clients.values() if bot.ap_id == ap_id]
        for bot in bots:
            bot.ip_address = self._get_interface_ip(bot.interface)
            self._refresh_connection_state(bot)
        return bots

    def list_all(self) -> List[ClientBot]:
        bots = list(self._clients.values())
        for bot in bots:
            bot.ip_address = self._get_interface_ip(bot.interface)
            self._refresh_connection_state(bot)
        return bots

    def _get_interface_ip(self, interface: str) -> Optional[str]:
        """Get the IP address of an interface."""
        try:
            result = subprocess.run(
                ["ip", "-4", "addr", "show", interface],
                capture_output=True, text=True, timeout=5
            )
            logger.debug(f"IP check for {interface}: {result.stdout[:200] if result.stdout else 'empty'}")
            match = re.search(r"inet\s+([\d.]+)/", result.stdout)
            if match:
                ip = match.group(1)
                logger.debug(f"Found IP {ip} for {interface}")
                return ip
            logger.debug(f"No IP found for {interface}")
        except Exception as e:
            logger.debug(f"Error getting IP for {interface}: {e}")
        return None

    def start_probe_requests(self, interface: str, ssids: Optional[List[str]] = None) -> bool:
        """
        Start broadcasting probe requests for known networks on an interface.
        
        This simulates real client behavior where devices probe for networks
        they've connected to before. Useful for:
        - Evil twin attacks (attacker sees what SSIDs clients want)
        - Passive reconnaissance
        - Testing probe request capture with airodump-ng
        
        Args:
            interface: WiFi interface to send probes from
            ssids: Optional list of SSIDs to probe for. Defaults to KNOWN_NETWORKS.
        """
        if interface in self._probe_threads:
            return True  # Already running
        
        probe_ssids = ssids or self.KNOWN_NETWORKS
        stop_flag = {"stop": False}
        
        def probe_worker():
            """Send probe requests periodically."""
            import random
            
            while not stop_flag["stop"]:
                try:
                    # Pick a random SSID to probe for
                    ssid = random.choice(probe_ssids)
                    
                    # Use wpa_supplicant scan to trigger probe requests
                    # Create a temporary config that will trigger active scanning
                    temp_config = f"/tmp/probe_{interface}.conf"
                    with open(temp_config, "w") as f:
                        f.write(f"ctrl_interface=/tmp/wpa_probe_{interface}\n")
                        f.write("ap_scan=1\n")
                        f.write(f"network={{\n")
                        f.write(f'    ssid="{ssid}"\n')
                        f.write("    key_mgmt=NONE\n")
                        f.write("    scan_ssid=1\n")
                        f.write("}\n")
                    
                    # Run a quick wpa_supplicant scan (this sends probe requests)
                    # The -s flag makes it scan immediately
                    subprocess.run(
                        ["timeout", "2", "wpa_supplicant", "-i", interface, "-c", temp_config, "-D", "nl80211"],
                        capture_output=True, timeout=5
                    )
                    
                    # Clean up
                    try:
                        os.remove(temp_config)
                    except:
                        pass
                    
                    logger.debug(f"Sent probe request for '{ssid}' on {interface}")
                    
                except Exception as e:
                    logger.debug(f"Probe request error on {interface}: {e}")
                
                # Random delay between probes (2-10 seconds)
                time.sleep(random.uniform(2, 10))
            
            logger.info(f"Probe request broadcasting stopped on {interface}")
        
        thread = threading.Thread(target=probe_worker, daemon=True)
        thread.start()
        self._probe_threads[interface] = (thread, stop_flag)
        logger.info(f"Started probe request broadcasting on {interface} for {len(probe_ssids)} SSIDs")
        return True

    def stop_probe_requests(self, interface: str) -> bool:
        """Stop probe request broadcasting on an interface."""
        if interface not in self._probe_threads:
            return False
        
        thread, stop_flag = self._probe_threads[interface]
        stop_flag["stop"] = True
        thread.join(timeout=5)
        del self._probe_threads[interface]
        return True

    def stop_all_probes(self):
        """Stop all probe request broadcasting."""
        interfaces = list(self._probe_threads.keys())
        for interface in interfaces:
            self.stop_probe_requests(interface)
