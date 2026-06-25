"""
aircrack-ng suite wrapper.
Handles monitor mode, packet capture, deauthentication, and handshake cracking.
"""

import os
import signal
import subprocess
import logging
import time
from typing import Optional, Dict, List
from pathlib import Path

logger = logging.getLogger(__name__)

CAPTURE_DIR = "/opt/beaconhub/captures"
RUN_DIR = "/opt/beaconhub/run"


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

        try:
            log_fd = open(log_file, "w")
            process = subprocess.Popen(
                cmd,
                stdout=log_fd,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid
            )
            log_fd.close()

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
            raise AircrackError("aireplay-ng not found. Is aircrack-ng suite installed?")
        except Exception as e:
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

        try:
            log_fd = open(log_file, "w")
            process = subprocess.Popen(
                cmd,
                stdout=log_fd,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid
            )
            log_fd.close()

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
            raise AircrackError("airodump-ng not found. Is aircrack-ng suite installed?")
        except Exception as e:
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
                os.killpg(os.getpgid(attack.process.pid), signal.SIGKILL)
                attack.process.wait(timeout=3)
            except ProcessLookupError:
                pass
            except Exception as e:
                logger.error(f"Error stopping attack {attack_id}: {e}")

        logger.info(f"Stopped attack {attack_id}")
        return True

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

        try:
            log_fd = open(log_file, "w")
            process = subprocess.Popen(
                cmd,
                stdout=log_fd,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid
            )
            log_fd.close()

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
            raise AircrackError("aireplay-ng not found. Is aircrack-ng suite installed?")
        except Exception as e:
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

        try:
            log_fd = open(log_file, "w")
            process = subprocess.Popen(
                cmd,
                stdout=log_fd,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid
            )
            log_fd.close()

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
            raise AircrackError("airodump-ng not found. Is aircrack-ng suite installed?")
        except Exception as e:
            raise AircrackError(f"Failed to start WEP capture: {str(e)}")

    def get_iv_count(self, csv_file: str) -> int:
        """Parse airodump-ng CSV to count unique IVs collected for WEP."""
        if not os.path.exists(csv_file):
            return 0
        try:
            result = subprocess.run(
                ["aircrack-ng", "-s", csv_file.replace("-01.csv", "-01.cap")],
                capture_output=True, text=True, timeout=15,
                input="q\n"
            )
            # aircrack-ng -s outputs: "Total number of WEP data packets: <N>"
            for line in result.stdout.split('\n'):
                if "WEP data packets" in line:
                    parts = line.split(':')
                    if len(parts) >= 2:
                        return int(parts[1].strip())
            return 0
        except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
            try:
                # Fallback: parse CSV for IV count in column 7
                with open(csv_file, 'r') as f:
                    for line in f:
                        if line.startswith("#") or "BSSID" in line:
                            continue
                        parts = line.split(',')
                        if len(parts) >= 8 and parts[0].strip():
                            try:
                                return int(parts[6].strip())
                            except ValueError:
                                continue
                return 0
            except Exception:
                return 0

    def list_captures(self) -> List[Dict[str, str]]:
        """List all capture files."""
        captures = []
        for f in Path(CAPTURE_DIR).glob("*.cap"):
            captures.append({
                "filename": f.name,
                "path": str(f),
                "size": str(f.stat().st_size),
                "modified": str(f.stat().st_mtime)
            })
        return captures

    def remove_attack(self, attack_id: str):
        """Remove an attack from tracking (after it's stopped)."""
        if attack_id in self._attacks:
            del self._attacks[attack_id]
