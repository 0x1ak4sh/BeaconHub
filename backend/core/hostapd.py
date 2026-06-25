"""
hostapd process manager.
Handles generating configs, starting/stopping hostapd instances for access points.
"""

import os
import signal
import subprocess
import logging
import tempfile
import string
from typing import Optional, Dict
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_DIR = "/opt/beaconhub/configs/hostapd"
RUN_DIR = "/opt/beaconhub/run"


class HostapdError(Exception):
    """Custom exception for hostapd operations."""
    pass


class HostapdInstance:
    """Represents a running hostapd instance."""

    def __init__(self, ap_id: str, interface: str, config_path: str):
        self.ap_id = ap_id
        self.interface = interface
        self.config_path = config_path
        self.process: Optional[subprocess.Popen] = None
        self.pid: Optional[int] = None

    @property
    def is_running(self) -> bool:
        if self.process is None:
            return False
        return self.process.poll() is None

    def get_return_code(self) -> Optional[int]:
        if self.process is None:
            return None
        return self.process.poll()


class HostapdManager:
    """Manages hostapd instances for creating access points."""

    def __init__(self):
        self._instances: Dict[str, HostapdInstance] = {}
        os.makedirs(CONFIG_DIR, exist_ok=True)
        os.makedirs(RUN_DIR, exist_ok=True)

    def _format_wep_key(self, key: str) -> str:
        """Return a hostapd-safe WEP key, quoted for ASCII and raw for hex."""
        if not key:
            raise HostapdError("WEP requires a password/key")

        if len(key) in (5, 13):
            escaped = key.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{escaped}"'

        if len(key) in (10, 26):
            if all(ch in string.hexdigits for ch in key):
                return key
            raise HostapdError(
                f"WEP key of length {len(key)} must be valid hexadecimal. "
                "Use 5 or 13 ASCII chars, or 10 or 26 hex digits."
            )

        raise HostapdError(
            f"WEP key must be 5 or 13 ASCII chars, or 10 or 26 hex chars. Got {len(key)} characters."
        )

    def generate_config(
        self,
        ap_id: str,
        interface: str,
        ssid: str,
        channel: int = 6,
        security: str = "wpa2-psk",
        password: Optional[str] = None,
        hidden: bool = False,
    ) -> str:
        """Generate a hostapd configuration file."""
        # Sanitize inputs to prevent config injection
        ssid = ssid.replace('\n', '').replace('\r', '').replace('\x00', '')
        if password:
            password = password.replace('\n', '').replace('\r', '').replace('\x00', '')
        if not (1 <= channel <= 14):
            raise HostapdError(f"Invalid channel: {channel}")
        if security not in ("open", "wep", "wpa2-psk", "wpa2-enterprise"):
            raise HostapdError(f"Invalid security type: {security}")
        config_path = os.path.join(CONFIG_DIR, f"{ap_id}.conf")

        # Base config common to all security types
        # NOTE: auth_algs is set per-security type, not in base
        base_lines = [
            f"interface={interface}",
            f"driver=nl80211",
            f"ssid={ssid}",
            f"hw_mode=g",
            f"channel={channel}",
            f"wmm_enabled=0",
            f"macaddr_acl=0",
            f"ignore_broadcast_ssid={'1' if hidden else '0'}",
        ]

        if security == "wpa2-psk":
            if not password:
                raise HostapdError("WPA2-PSK requires a password")
            config_lines = base_lines + [
                f"auth_algs=1",  # Open System auth (standard for WPA2)
                f"wpa=2",
                f"wpa_key_mgmt=WPA-PSK",
                f"wpa_passphrase={password}",
                f"wpa_pairwise=CCMP",
                f"rsn_pairwise=CCMP",
            ]
        elif security == "wep":
            wep_key = self._format_wep_key(password or "")
            config_lines = base_lines + [
                f"auth_algs=3",  # Both Open System + Shared Key for realistic WEP
                f"wep_default_key=0",
                f"wep_key0={wep_key}",
                f"wep_rekey_period=0",
            ]
        elif security == "open":
            config_lines = base_lines + [
                f"auth_algs=1",  # Open System auth
            ]
        elif security == "wpa2-enterprise":
            config_lines = base_lines + [
                f"auth_algs=1",  # Open System auth
                f"wpa=2",
                f"ieee8021x=1",
                f"wpa_key_mgmt=WPA-EAP",
                f"wpa_pairwise=CCMP",
                f"rsn_pairwise=CCMP",
                f"auth_server_addr=127.0.0.1",
                f"auth_server_port=1812",
                f"auth_server_shared_secret=testing123",
            ]
        else:
            config_lines = base_lines + [
                f"auth_algs=1",
            ]

        config_content = "\n".join(config_lines) + "\n"

        with open(config_path, "w") as f:
            f.write(config_content)

        logger.info(f"Generated hostapd config at {config_path}")
        return config_path

    def start(self, ap_id: str, interface: str, config_path: str) -> HostapdInstance:
        """Start a hostapd instance."""
        if ap_id in self._instances and self._instances[ap_id].is_running:
            raise HostapdError(f"AP {ap_id} is already running")

        # Ensure interface is down and in correct mode for hostapd
        subprocess.run(
            ["ip", "link", "set", interface, "down"],
            capture_output=True, text=True, timeout=10
        )

        # Kill any existing wpa_supplicant on this interface
        subprocess.run(
            ["pkill", "-f", f"wpa_supplicant.*{interface}"],
            capture_output=True, text=True, timeout=5
        )

        # Set interface type to managed (hostapd will switch it to AP itself)
        subprocess.run(
            ["iw", "dev", interface, "set", "type", "managed"],
            capture_output=True, text=True, timeout=10
        )

        # Do NOT bring interface up - hostapd manages this itself
        # Bringing it up before hostapd causes "nl80211: Could not configure driver mode"

        log_file = os.path.join(RUN_DIR, f"{ap_id}.log")

        try:
            log_fd = open(log_file, "w")
            process = subprocess.Popen(
                ["hostapd", config_path],
                stdout=log_fd,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid
            )
            # Close fd in parent - child process has its own copy
            log_fd.close()

            instance = HostapdInstance(ap_id, interface, config_path)
            instance.process = process
            instance.pid = process.pid
            self._instances[ap_id] = instance

            logger.info(f"Started hostapd for AP {ap_id} on {interface} (PID: {process.pid})")
            return instance

        except FileNotFoundError:
            raise HostapdError("hostapd binary not found. Is it installed?")
        except Exception as e:
            raise HostapdError(f"Failed to start hostapd: {str(e)}")

    def stop(self, ap_id: str) -> bool:
        """Stop a hostapd instance."""
        if ap_id not in self._instances:
            logger.warning(f"AP {ap_id} not found in instances")
            return False

        instance = self._instances[ap_id]
        if instance.process and instance.is_running:
            try:
                # Kill the entire process group
                os.killpg(os.getpgid(instance.process.pid), signal.SIGTERM)
                instance.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(instance.process.pid), signal.SIGKILL)
                instance.process.wait(timeout=3)
            except ProcessLookupError:
                pass  # Already dead
            except Exception as e:
                logger.error(f"Error stopping hostapd for AP {ap_id}: {e}")

        # Cleanup config file
        if os.path.exists(instance.config_path):
            os.remove(instance.config_path)

        del self._instances[ap_id]
        logger.info(f"Stopped hostapd for AP {ap_id}")
        return True

    def reload(self, ap_id: str) -> bool:
        """
        Send SIGHUP to hostapd to reload config and refresh beacons.
        
        This triggers a burst of beacon frames and re-reads the config file.
        Useful for forcing hidden SSIDs to respond to probe requests.
        """
        if ap_id not in self._instances:
            logger.warning(f"AP {ap_id} not found in instances")
            return False

        instance = self._instances[ap_id]
        if instance.process and instance.is_running:
            try:
                # Send HUP signal to reload config
                os.kill(instance.process.pid, signal.SIGHUP)
                logger.info(f"Sent SIGHUP to hostapd for AP {ap_id}")
                return True
            except ProcessLookupError:
                logger.warning(f"Process for AP {ap_id} not found")
                return False
            except Exception as e:
                logger.error(f"Error reloading hostapd for AP {ap_id}: {e}")
                return False
        return False

    def stop_all(self):
        """Stop all running hostapd instances."""
        ap_ids = list(self._instances.keys())
        for ap_id in ap_ids:
            self.stop(ap_id)

    def get_instance(self, ap_id: str) -> Optional[HostapdInstance]:
        """Get a hostapd instance by AP ID."""
        return self._instances.get(ap_id)

    def is_running(self, ap_id: str) -> bool:
        """Check if an AP's hostapd is running."""
        instance = self._instances.get(ap_id)
        if instance is None:
            return False
        return instance.is_running

    def get_log(self, ap_id: str, lines: int = 50) -> str:
        """Get the last N lines of the hostapd log."""
        log_file = os.path.join(RUN_DIR, f"{ap_id}.log")
        if not os.path.exists(log_file):
            return ""
        try:
            with open(log_file, "r") as f:
                all_lines = f.readlines()
                return "".join(all_lines[-lines:])
        except Exception:
            return ""
