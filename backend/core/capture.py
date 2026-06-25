import asyncio
import os
import signal
import re
import subprocess
import logging
import time
from typing import Optional, Dict, List
from datetime import datetime

logger = logging.getLogger(__name__)

CAPTURE_DIR = "/opt/beaconhub/captures"


class CaptureError(Exception):
    pass


class PacketCapture:
    def __init__(self, capture_id: str, interface: str):
        self.capture_id = capture_id
        self.interface = interface
        self.process: Optional[subprocess.Popen] = None
        self.output_file = os.path.join(CAPTURE_DIR, f"live_{capture_id}.pcap")
        self.text_file = os.path.join(CAPTURE_DIR, f"live_{capture_id}.txt")
        self._captured_lines: List[str] = []
        self._running = False

    @property
    def is_running(self) -> bool:
        if self.process is None:
            return False
        return self.process.poll() is None

    def start(self) -> bool:
        if self._running:
            return True
        try:
            os.makedirs(CAPTURE_DIR, exist_ok=True)

            # Use tshark for live packet analysis
            # Filter: HTTP POST, ARP, EAPOL, or all data packets from this interface
            bpf = "arp or port 80 or port 443 or port 53 or eapol"
            cmd = [
                "tshark",
                "-i", self.interface,
                "-f", bpf,
                "-w", self.output_file,
                "-F", "pcap",
            ]

            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid
            )

            self._running = True
            logger.info(f"Started packet capture on {self.interface} -> {self.output_file}")
            return True

        except FileNotFoundError:
            logger.warning("tshark not found, trying tcpdump...")
            return self._start_tcpdump()
        except Exception as e:
            logger.error(f"Failed to start capture: {e}")
            return False

    def _start_tcpdump(self) -> bool:
        try:
            cmd = [
                "tcpdump",
                "-i", self.interface,
                "-w", self.output_file,
                "-n",
                "arp or port 80 or port 53 or eapol",
            ]
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid
            )
            self._running = True
            logger.info(f"Started tcpdump capture on {self.interface} -> {self.output_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to start tcpdump: {e}")
            return False

    def stop(self):
        self._running = False
        if self.process and self.is_running:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                self.process.wait(timeout=5)
            except Exception:
                try:
                    os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                except Exception:
                    pass

        self._extract_text()
        logger.info(f"Stopped capture on {self.interface}")

    def _extract_text(self):
        """Extract readable text from the pcap for display."""
        if not os.path.exists(self.output_file):
            return
        try:
            result = subprocess.run(
                ["tshark", "-r", self.output_file, "-Y", "http or arp or dns or eapol",
                 "-T", "fields", "-e", "frame.number", "-e", "frame.time",
                 "-e", "ip.src", "-e", "ip.dst", "-e", "http.host",
                 "-e", "http.request.uri", "-e", "http.request.method",
                 "-e", "http.file_data", "-e", "eapol.msg", "-e", "arp.dst.proto_ipv4"],
                capture_output=True, text=True, timeout=15
            )
            lines = result.stdout.strip().split('\n')
            self._captured_lines = [l for l in lines if l.strip()]

            with open(self.text_file, 'w') as f:
                f.write(result.stdout)
        except Exception:
            pass

    def get_captured_data(self) -> dict:
        return {
            "capture_id": self.capture_id,
            "interface": self.interface,
            "running": self._running,
            "pcap_file": self.output_file if os.path.exists(self.output_file) else None,
            "text_file": self.text_file if os.path.exists(self.text_file) else None,
            "captured_lines": self._captured_lines[-50:],
            "line_count": len(self._captured_lines),
        }

    def detect_credentials(self) -> List[dict]:
        """Scan captured data for plaintext credentials (username/password POSTs)."""
        creds = []
        if not os.path.exists(self.output_file):
            return creds
        try:
            result = subprocess.run(
                ["tshark", "-r", self.output_file, "-Y", "http.request.method == POST",
                 "-T", "fields", "-e", "frame.time", "-e", "ip.src",
                 "-e", "ip.dst", "-e", "http.host", "-e", "http.request.uri",
                 "-e", "http.file_data"],
                capture_output=True, text=True, timeout=15
            )
            for line in result.stdout.strip().split('\n'):
                parts = line.split('\t')
                if len(parts) >= 4 and any(kw in line.lower() for kw in ['user', 'pass', 'login', 'email', 'auth']):
                    creds.append({
                        "timestamp": parts[0] if len(parts) > 0 else "",
                        "source": parts[1] if len(parts) > 1 else "",
                        "destination": parts[2] if len(parts) > 2 else "",
                        "host": parts[3] if len(parts) > 3 else "",
                        "uri": parts[4] if len(parts) > 4 else "",
                        "data": parts[5] if len(parts) > 5 else "",
                    })
        except Exception:
            pass
        return creds


class CaptureManager:
    def __init__(self):
        self._captures: Dict[str, PacketCapture] = {}
        os.makedirs(CAPTURE_DIR, exist_ok=True)

    def start_capture(self, interface: str) -> Optional[str]:
        capture_id = f"cap_{int(time.time())}"
        cap = PacketCapture(capture_id, interface)
        if cap.start():
            self._captures[capture_id] = cap
            return capture_id
        return None

    def stop_capture(self, capture_id: str) -> bool:
        cap = self._captures.get(capture_id)
        if not cap:
            return False
        cap.stop()
        return True

    def get_capture(self, capture_id: str) -> Optional[PacketCapture]:
        return self._captures.get(capture_id)

    def list_captures(self) -> List[dict]:
        return [cap.get_captured_data() for cap in self._captures.values()]

    def stop_all(self):
        for cap in self._captures.values():
            cap.stop()
        self._captures.clear()

    def get_capture_for_interface(self, interface: str) -> Optional[PacketCapture]:
        for cap in self._captures.values():
            if cap.interface == interface:
                return cap
        return None
