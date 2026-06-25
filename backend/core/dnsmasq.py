"""
dnsmasq process manager.
Handles DHCP and DNS for virtual access points.
"""

import os
import signal
import subprocess
import logging
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

CONFIG_DIR = "/opt/beaconhub/configs/dnsmasq"
RUN_DIR = "/opt/beaconhub/run"
LEASE_DIR = "/opt/beaconhub/leases"


class DnsmasqError(Exception):
    """Custom exception for dnsmasq operations."""
    pass


class DnsmasqInstance:
    """Represents a running dnsmasq instance."""

    def __init__(self, ap_id: str, interface: str, subnet: str):
        self.ap_id = ap_id
        self.interface = interface
        self.subnet = subnet
        self.process: Optional[subprocess.Popen] = None
        self.pid: Optional[int] = None
        self.config_path: str = ""
        self.lease_file: str = ""

    @property
    def is_running(self) -> bool:
        if self.process is None:
            return False
        return self.process.poll() is None


class DnsmasqManager:
    """Manages dnsmasq instances for DHCP on virtual APs."""

    def __init__(self):
        self._instances: Dict[str, DnsmasqInstance] = {}
        self._used_subnets: set = set()  # Track used subnet IDs
        self._freed_subnets: List[int] = []  # Reusable subnet IDs
        os.makedirs(CONFIG_DIR, exist_ok=True)
        os.makedirs(RUN_DIR, exist_ok=True)
        os.makedirs(LEASE_DIR, exist_ok=True)

    def _allocate_subnet(self) -> str:
        """Allocate a unique /24 subnet for an AP."""
        # Reuse a freed subnet if available
        if self._freed_subnets:
            subnet_id = self._freed_subnets.pop(0)
            self._used_subnets.add(subnet_id)
            return f"10.0.{subnet_id}"
        
        # Find next available subnet
        for subnet_id in range(1, 255):
            if subnet_id not in self._used_subnets:
                self._used_subnets.add(subnet_id)
                return f"10.0.{subnet_id}"
        
        raise DnsmasqError("No more subnets available (max 254)")
    
    def _release_subnet(self, subnet: str):
        """Release a subnet back to the pool."""
        try:
            subnet_id = int(subnet.split('.')[2])
            self._used_subnets.discard(subnet_id)
            if subnet_id not in self._freed_subnets:
                self._freed_subnets.append(subnet_id)
                self._freed_subnets.sort()
        except (IndexError, ValueError):
            pass

    def setup_interface(self, interface: str, subnet: str) -> bool:
        """Assign IP to the AP interface and set up routing."""
        gateway_ip = f"{subnet}.1"
        try:
            # Flush existing IPs
            subprocess.run(
                ["ip", "addr", "flush", "dev", interface],
                capture_output=True, text=True, timeout=10
            )
            # Assign gateway IP
            result = subprocess.run(
                ["ip", "addr", "add", f"{gateway_ip}/24", "dev", interface],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                logger.error(f"Failed to assign IP to {interface}: {result.stderr}")
                return False

            # Bring interface up
            subprocess.run(
                ["ip", "link", "set", interface, "up"],
                capture_output=True, text=True, timeout=10
            )

            logger.info(f"Configured {interface} with IP {gateway_ip}/24")
            return True
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.error(f"Failed to setup interface: {e}")
            return False

    def start(self, ap_id: str, interface: str) -> DnsmasqInstance:
        """Start a dnsmasq instance for an AP."""
        if ap_id in self._instances and self._instances[ap_id].is_running:
            raise DnsmasqError(f"dnsmasq already running for AP {ap_id}")

        subnet = self._allocate_subnet()
        gateway_ip = f"{subnet}.1"
        range_start = f"{subnet}.10"
        range_end = f"{subnet}.100"

        # Setup interface IP
        if not self.setup_interface(interface, subnet):
            raise DnsmasqError(f"Failed to configure interface {interface}")

        # Write config
        config_path = os.path.join(CONFIG_DIR, f"{ap_id}.conf")
        lease_file = os.path.join(LEASE_DIR, f"{ap_id}.leases")

        config_content = (
            f"interface={interface}\n"
            f"bind-interfaces\n"
            f"dhcp-range={range_start},{range_end},255.255.255.0,12h\n"
            f"dhcp-option=3,{gateway_ip}\n"
            f"dhcp-option=6,{gateway_ip}\n"
            f"server=8.8.8.8\n"
            f"log-queries\n"
            f"log-dhcp\n"
            f"listen-address={gateway_ip}\n"
            f"dhcp-leasefile={lease_file}\n"
            f"no-resolv\n"
            f"no-hosts\n"
        )

        with open(config_path, "w") as f:
            f.write(config_content)

        # Touch lease file
        open(lease_file, 'a').close()

        log_file = os.path.join(RUN_DIR, f"dnsmasq_{ap_id}.log")

        try:
            log_fd = open(log_file, "w")
            process = subprocess.Popen(
                ["dnsmasq", "-C", config_path, "--no-daemon", "--log-facility=-"],
                stdout=log_fd,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid
            )
            log_fd.close()

            instance = DnsmasqInstance(ap_id, interface, subnet)
            instance.process = process
            instance.pid = process.pid
            instance.config_path = config_path
            instance.lease_file = lease_file
            self._instances[ap_id] = instance

            logger.info(
                f"Started dnsmasq for AP {ap_id} on {interface} "
                f"(subnet: {subnet}.0/24, PID: {process.pid})"
            )
            return instance

        except FileNotFoundError:
            raise DnsmasqError("dnsmasq binary not found. Is it installed?")
        except Exception as e:
            raise DnsmasqError(f"Failed to start dnsmasq: {str(e)}")

    def stop(self, ap_id: str) -> bool:
        """Stop a dnsmasq instance."""
        if ap_id not in self._instances:
            return False

        instance = self._instances[ap_id]
        
        # Release the subnet back to the pool
        self._release_subnet(instance.subnet)
        
        if instance.process and instance.is_running:
            try:
                os.killpg(os.getpgid(instance.process.pid), signal.SIGTERM)
                instance.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(instance.process.pid), signal.SIGKILL)
                instance.process.wait(timeout=3)
            except ProcessLookupError:
                pass
            except Exception as e:
                logger.error(f"Error stopping dnsmasq for AP {ap_id}: {e}")

        # Flush interface IP
        try:
            subprocess.run(
                ["ip", "addr", "flush", "dev", instance.interface],
                capture_output=True, text=True, timeout=5
            )
        except Exception:
            pass

        # Cleanup files
        for path in [instance.config_path, instance.lease_file]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass

        del self._instances[ap_id]
        logger.info(f"Stopped dnsmasq for AP {ap_id}")
        return True

    def stop_all(self):
        """Stop all dnsmasq instances."""
        ap_ids = list(self._instances.keys())
        for ap_id in ap_ids:
            self.stop(ap_id)

    def get_leases(self, ap_id: str) -> List[Dict[str, str]]:
        """Get current DHCP leases for an AP."""
        if ap_id not in self._instances:
            return []

        instance = self._instances[ap_id]
        leases = []

        if not os.path.exists(instance.lease_file):
            return leases

        try:
            with open(instance.lease_file, "r") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 4:
                        leases.append({
                            "expires": parts[0],
                            "mac": parts[1],
                            "ip": parts[2],
                            "hostname": parts[3] if parts[3] != "*" else "unknown"
                        })
        except Exception:
            pass

        return leases

    def get_subnet(self, ap_id: str) -> Optional[str]:
        """Get the subnet assigned to an AP."""
        instance = self._instances.get(ap_id)
        if instance:
            return instance.subnet
        return None
