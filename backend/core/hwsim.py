"""
mac80211_hwsim kernel module interface.
Handles loading the module, creating/deleting virtual radios, and interface management.
"""

import subprocess
import re
import time
import logging
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

INTERFACE_PREFIX = "beacon"


class HwsimError(Exception):
    """Custom exception for hwsim operations."""
    pass


class HwsimManager:
    """Manages mac80211_hwsim kernel module and virtual wireless interfaces."""

    def __init__(self):
        self._radios_count = 0

    def check_module_available(self) -> bool:
        """Check if mac80211_hwsim module is available (loaded or loadable)."""
        try:
            result = subprocess.run(
                ["modinfo", "mac80211_hwsim"],
                capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def is_module_loaded(self) -> bool:
        """Check if mac80211_hwsim is currently loaded."""
        try:
            result = subprocess.run(
                ["lsmod"],
                capture_output=True, text=True, timeout=10
            )
            return "mac80211_hwsim" in result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def load_module(self, radios: int = 6) -> bool:
        """Load mac80211_hwsim with specified number of radios."""
        if radios < 2 or radios > 20:
            raise HwsimError(f"Radio count must be between 2 and 20, got {radios}")

        # Unload if already loaded
        if self.is_module_loaded():
            self.unload_module()

        try:
            result = subprocess.run(
                ["modprobe", "mac80211_hwsim", f"radios={radios}"],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode != 0:
                raise HwsimError(
                    f"Failed to load mac80211_hwsim: {result.stderr.strip()}"
                )
            self._radios_count = radios
            logger.info(f"Loaded mac80211_hwsim with {radios} radios")
            return True
        except subprocess.TimeoutExpired:
            raise HwsimError("Timeout while loading mac80211_hwsim module")
        except FileNotFoundError:
            raise HwsimError("modprobe command not found. Are you running on Linux?")

    def unload_module(self) -> bool:
        """Unload the mac80211_hwsim module."""
        try:
            result = subprocess.run(
                ["modprobe", "-r", "mac80211_hwsim"],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode != 0:
                raise HwsimError(
                    f"Failed to unload mac80211_hwsim: {result.stderr.strip()}"
                )
            self._radios_count = 0
            logger.info("Unloaded mac80211_hwsim")
            return True
        except subprocess.TimeoutExpired:
            raise HwsimError("Timeout while unloading module")

    def get_interfaces(self) -> List[Dict[str, str]]:
        """Get all wireless interfaces and their details."""
        interfaces = []
        try:
            result = subprocess.run(
                ["iw", "dev"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                logger.error(f"iw dev failed: {result.stderr}")
                return interfaces

            current_phy = None
            current_iface = None
            current_mac = None
            current_type = None

            for line in result.stdout.splitlines():
                line = line.strip()
                if line.startswith("phy#"):
                    current_phy = line.rstrip(":")
                elif line.startswith("Interface"):
                    if current_iface:
                        interfaces.append({
                            "interface": current_iface,
                            "phy": current_phy or "unknown",
                            "mac": current_mac or "00:00:00:00:00:00",
                            "type": current_type or "managed"
                        })
                    current_iface = line.split()[1]
                    current_mac = None
                    current_type = None
                elif line.startswith("addr"):
                    current_mac = line.split()[1]
                elif line.startswith("type"):
                    current_type = line.split()[1]

            # Don't forget the last one
            if current_iface:
                interfaces.append({
                    "interface": current_iface,
                    "phy": current_phy or "unknown",
                    "mac": current_mac or "00:00:00:00:00:00",
                    "type": current_type or "managed"
                })

        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.error(f"Failed to get interfaces: {e}")

        return interfaces

    def get_phy_list(self) -> List[str]:
        """Get list of all phy devices."""
        phys = []
        try:
            result = subprocess.run(
                ["iw", "phy"],
                capture_output=True, text=True, timeout=10
            )
            for line in result.stdout.splitlines():
                if line.startswith("Wiphy"):
                    phys.append(line.split()[1])
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return phys

    def rename_interface(self, old_name: str, new_name: str) -> bool:
        """Rename a wireless interface."""
        try:
            # Bring interface down first
            subprocess.run(
                ["ip", "link", "set", old_name, "down"],
                capture_output=True, text=True, timeout=10
            )
            # Rename
            result = subprocess.run(
                ["ip", "link", "set", old_name, "name", new_name],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                logger.error(f"Failed to rename {old_name} to {new_name}: {result.stderr}")
                return False
            # Bring back up
            subprocess.run(
                ["ip", "link", "set", new_name, "up"],
                capture_output=True, text=True, timeout=10
            )
            logger.info(f"Renamed interface {old_name} -> {new_name}")
            return True
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.error(f"Failed to rename interface: {e}")
            return False

    def set_interface_up(self, interface: str) -> bool:
        """Bring an interface up."""
        try:
            result = subprocess.run(
                ["ip", "link", "set", interface, "up"],
                capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def set_interface_down(self, interface: str) -> bool:
        """Bring an interface down."""
        try:
            result = subprocess.run(
                ["ip", "link", "set", interface, "down"],
                capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def set_monitor_mode(self, interface: str) -> bool:
        """Put an interface into monitor mode."""
        try:
            # Down
            self.set_interface_down(interface)
            # Set monitor
            result = subprocess.run(
                ["iw", "dev", interface, "set", "type", "monitor"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                logger.error(f"Failed to set monitor mode on {interface}: {result.stderr}")
                self.set_interface_up(interface)
                return False
            # Up
            self.set_interface_up(interface)
            logger.info(f"Set {interface} to monitor mode")
            return True
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.error(f"Failed to set monitor mode: {e}")
            return False

    def set_managed_mode(self, interface: str) -> bool:
        """Put an interface into managed mode."""
        try:
            self.set_interface_down(interface)
            result = subprocess.run(
                ["iw", "dev", interface, "set", "type", "managed"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                logger.error(f"Failed to set managed mode on {interface}: {result.stderr}")
                self.set_interface_up(interface)
                return False
            self.set_interface_up(interface)
            logger.info(f"Set {interface} to managed mode")
            return True
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.error(f"Failed to set managed mode: {e}")
            return False

    def get_interface_mac(self, interface: str) -> Optional[str]:
        """Get MAC address of an interface."""
        try:
            result = subprocess.run(
                ["ip", "link", "show", interface],
                capture_output=True, text=True, timeout=10
            )
            match = re.search(r"link/ether\s+([\da-f:]+)", result.stdout)
            if match:
                return match.group(1)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return None

    def get_radio_count(self) -> int:
        """Get the number of loaded radios."""
        return len(self.get_phy_list())

    def create_radio(self, interface_name: Optional[str] = None) -> Optional[str]:
        """
        Dynamically create a new virtual radio using mac80211_hwsim.
        Returns the new interface name or None on failure.
        
        Args:
            interface_name: Optional custom name for the interface (e.g., 'client0')
        """
        try:
            # First get current interfaces to detect new ones
            before_interfaces = set(iface["interface"] for iface in self.get_interfaces())
            
            # Method 1: Try using hwsim tool (available on newer kernels)
            result = subprocess.run(
                ["tee", "/sys/kernel/debug/mac80211_hwsim/hwsim_register"],
                input="1\n",
                capture_output=True, text=True, timeout=5
            )

            new_iface = None
            
            if result.returncode != 0:
                # Method 2: Create a new virtual interface on an existing phy
                current_count = self.get_radio_count()
                phys = self.get_phy_list()
                if not phys:
                    return None

                # Use the last phy to add a new virtual interface
                # This creates an additional interface on an existing radio
                temp_name = interface_name or f"wlan_new_{current_count}"
                result = subprocess.run(
                    ["iw", "phy", phys[-1], "interface", "add", temp_name, "type", "managed"],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    new_iface = temp_name
                    self.set_interface_up(new_iface)
                    logger.info(f"Created new interface: {new_iface}")
                else:
                    logger.error(f"Failed to create interface: {result.stderr}")
                    return None
            else:
                # If method 1 worked, find the new interface
                time.sleep(1)
                after_interfaces = set(iface["interface"] for iface in self.get_interfaces())
                new_interfaces = after_interfaces - before_interfaces
                if new_interfaces:
                    new_iface = list(new_interfaces)[0]
                else:
                    # Fallback to last interface
                    interfaces = self.get_interfaces()
                    if interfaces:
                        new_iface = interfaces[-1]["interface"]
            
            # Rename the interface if a custom name was provided and it's different
            if new_iface and interface_name and new_iface != interface_name:
                if self.rename_interface(new_iface, interface_name):
                    new_iface = interface_name
            
            return new_iface

        except Exception as e:
            logger.error(f"Failed to create radio: {e}")
            return None

    def create_client_interface(self, client_number: int) -> Optional[str]:
        """
        Create a new virtual interface specifically named for a client.
        This creates interfaces like client0, client1, etc.
        
        Args:
            client_number: The client number (0, 1, 2, ...)
        
        Returns:
            The interface name (e.g., 'client0') or None on failure.
        """
        interface_name = f"client{client_number}"
        
        # First check if interface already exists
        existing = self.get_interfaces()
        for iface in existing:
            if iface["interface"] == interface_name:
                logger.warning(f"Interface {interface_name} already exists")
                return interface_name
        
        # Get a phy to create the interface on
        phys = self.get_phy_list()
        if not phys:
            logger.error("No phy devices available")
            return None
        
        # Use round-robin phy assignment to distribute clients
        phy = phys[client_number % len(phys)]
        
        try:
            # Create the interface
            result = subprocess.run(
                ["iw", "phy", phy, "interface", "add", interface_name, "type", "managed"],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to create client interface {interface_name}: {result.stderr}")
                return None
            
            # Bring it up
            self.set_interface_up(interface_name)
            
            logger.info(f"Created client interface: {interface_name} on {phy}")
            return interface_name
            
        except Exception as e:
            logger.error(f"Failed to create client interface: {e}")
            return None

    def delete_interface(self, interface: str) -> bool:
        """Delete a virtual wireless interface."""
        try:
            self.set_interface_down(interface)
            result = subprocess.run(
                ["iw", "dev", interface, "del"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                logger.info(f"Deleted interface: {interface}")
                return True
            logger.error(f"Failed to delete {interface}: {result.stderr}")
            return False
        except Exception as e:
            logger.error(f"Failed to delete interface: {e}")
            return False
