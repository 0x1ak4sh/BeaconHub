"""
Lab Manager - Central orchestrator for BeaconHub.
Coordinates all components: hwsim, hostapd, dnsmasq, clients.
"""

import asyncio
import logging
import string
import time
import uuid
from typing import Dict, List, Optional
from datetime import datetime

from .hwsim import HwsimManager, HwsimError
from .hostapd import HostapdManager, HostapdError
from .dnsmasq import DnsmasqManager, DnsmasqError
from .clients import ClientManager, ClientBotError
from .radius import RadiusManager, RadiusError
from .aircrack import AircrackManager, AircrackError
from .capture import CaptureManager
from .events import event_bus

logger = logging.getLogger(__name__)


class LabError(Exception):
    """Custom exception for lab operations."""
    pass


class AccessPointRecord:
    """Tracks an AP and all its associated resources."""

    def __init__(self, ap_id: str, ssid: str, security: str, channel: int,
                 hidden: bool, interface: str, password: Optional[str] = None,
                 dynamic_interface: bool = False):
        self.id = ap_id
        self.ssid = ssid
        self.security = security
        self.channel = channel
        self.hidden = hidden
        self.interface = interface
        self.password = password
        self.dynamic_interface = dynamic_interface
        self.status = "starting"
        self.created_at = datetime.now().isoformat()
        self.bssid: Optional[str] = None
        self.packets_sent = 0
        self.packets_received = 0
        # Track adapters dedicated to this AP's clients
        self.client_adapter_ids: List[str] = []


class AdapterRecord:
    """Tracks a virtual adapter."""

    def __init__(self, adapter_id: str, interface: str, phy: str, mac: str):
        self.id = adapter_id
        self.interface = interface
        self.phy = phy
        self.mac_address = mac
        self.mode = "managed"
        self.in_use = False
        self.used_by: Optional[str] = None


class AttackRecord:
    """Tracks an attack and its resources."""

    def __init__(self, attack_id: str, attack_type: str, target_ap_id: str, adapter_id: str):
        self.id = attack_id
        self.attack_type = attack_type
        self.target_ap_id = target_ap_id
        self.adapter_id = adapter_id
        self.status = "starting"
        self.started_at = datetime.now().isoformat()
        self.stopped_at: Optional[str] = None
        self.output_file: Optional[str] = None
        self.packets_sent: int = 0


class LabManager:
    """
    Central coordinator for the BeaconHub virtual wireless lab.
    Manages the lifecycle of all components.
    """

    def __init__(self):
        self.hwsim = HwsimManager()
        self.hostapd = HostapdManager()
        self.dnsmasq = DnsmasqManager()
        self.clients = ClientManager()
        self.radius = RadiusManager()
        self.aircrack = AircrackManager()
        self.capture = CaptureManager()

        self._aps: Dict[str, AccessPointRecord] = {}
        self._adapters: Dict[str, AdapterRecord] = {}
        self._attacks: Dict[str, 'AttackRecord'] = {}
        self._wep_attacks: Dict[str, dict] = {}  # ap_id -> {capture_id, replay_ids: [ids]}
        self._started_at = time.time()
        self._initialized = False
        self._radius_running = False

        # Interface allocation tracking
        self._interface_pool: List[str] = []
        self._allocated_interfaces: Dict[str, str] = {}  # interface -> purpose
        
        # Counter for client interface naming
        self._client_counter = 0
        self._freed_client_numbers: List[int] = []  # Reusable client numbers
        self._ap_counter = 0
        self._freed_ap_numbers: List[int] = []  # Reusable AP interface numbers

    async def initialize(self, radios: int = 6) -> bool:
        """Initialize the lab: load hwsim, discover interfaces."""
        try:
            await event_bus.publish("info", "lab", "Initializing BeaconHub...")

            if not self.hwsim.check_module_available():
                await event_bus.publish(
                    "error", "lab",
                    "mac80211_hwsim module not available."
                )
                raise LabError("mac80211_hwsim module not available")

            if self.hwsim.is_module_loaded():
                await event_bus.publish("info", "lab", "mac80211_hwsim already loaded, using existing interfaces...")
            else:
                await event_bus.publish("info", "lab", f"Loading mac80211_hwsim with {radios} radios...")
                self.hwsim.load_module(radios)

            await asyncio.sleep(1)

            interfaces = self.hwsim.get_interfaces()
            if not interfaces:
                await event_bus.publish("error", "lab", "No interfaces found after loading module")
                raise LabError("No interfaces found after loading hwsim")

            await event_bus.publish(
                "info", "lab",
                f"Found {len(interfaces)} wireless interfaces"
            )

            # Register adapters with UUID-based IDs (no collision on delete)
            for iface_info in interfaces:
                adapter_id = f"adapter_{uuid.uuid4().hex[:8]}"
                adapter = AdapterRecord(
                    adapter_id=adapter_id,
                    interface=iface_info["interface"],
                    phy=iface_info["phy"],
                    mac=iface_info["mac"]
                )
                self._adapters[adapter_id] = adapter
                self._interface_pool.append(iface_info["interface"])

            self._initialized = True
            await event_bus.publish(
                "info", "lab",
                f"Lab initialized. {len(self._adapters)} adapters available."
            )
            return True

        except HwsimError as e:
            await event_bus.publish("error", "lab", f"Initialization failed: {str(e)}")
            raise LabError(f"Failed to initialize lab: {str(e)}")

    def _allocate_interface(self, purpose: str, prefer_wlan: bool = False) -> Optional[str]:
        """Allocate a free interface for a specific purpose.
        
        Args:
            purpose: Description of what this interface will be used for
            prefer_wlan: If True, prefer wlan* interfaces (for APs), otherwise prefer client* (for clients)
        """
        # Sort interfaces based on preference
        if prefer_wlan:
            # For APs, prefer wlan* interfaces first
            sorted_ifaces = sorted(self._interface_pool, key=lambda x: (not x.startswith('wlan'), x))
        else:
            # For clients, prefer client* interfaces first
            sorted_ifaces = sorted(self._interface_pool, key=lambda x: (not x.startswith('client'), x))
        
        for iface in sorted_ifaces:
            if iface not in self._allocated_interfaces:
                self._allocated_interfaces[iface] = purpose
                return iface
        return None

    def _release_interface(self, interface: str):
        """Release an allocated interface back to the pool."""
        if interface in self._allocated_interfaces:
            del self._allocated_interfaces[interface]

    def _find_adapter_by_interface(self, interface: str) -> Optional[AdapterRecord]:
        """Find adapter record by interface name."""
        for adapter in self._adapters.values():
            if adapter.interface == interface:
                return adapter
        return None

    def _reserve_number(self, free_list: List[int], counter_attr: str) -> int:
        """Reserve a stable number for generated interface names."""
        if free_list:
            return free_list.pop(0)
        value = getattr(self, counter_attr)
        setattr(self, counter_attr, value + 1)
        return value

    def _remember_freed_number(self, interface: str, prefix: str, free_list: List[int]):
        """Make generated interface numbers reusable after cleanup."""
        if not interface.startswith(prefix):
            return
        try:
            number = int(interface.replace(prefix, "", 1))
        except ValueError:
            return
        if number not in free_list:
            free_list.append(number)
            free_list.sort()

    async def _create_named_adapter(self, interface_name: str, purpose: str) -> AdapterRecord:
        """Create and register a virtual adapter with a predictable lab name."""
        new_iface = self.hwsim.create_radio(interface_name=interface_name)
        if not new_iface:
            raise LabError(f"Failed to create interface {interface_name}")

        mac = self.hwsim.get_interface_mac(new_iface) or "00:00:00:00:00:00"
        interfaces = self.hwsim.get_interfaces()
        phy = "unknown"
        for iface_info in interfaces:
            if iface_info["interface"] == new_iface:
                phy = iface_info["phy"]
                break

        adapter_id = f"adapter_{uuid.uuid4().hex[:8]}"
        adapter = AdapterRecord(
            adapter_id=adapter_id,
            interface=new_iface,
            phy=phy,
            mac=mac,
        )
        self._adapters[adapter_id] = adapter
        self._interface_pool.append(new_iface)
        self._allocated_interfaces[new_iface] = purpose

        await event_bus.publish("info", "adapter", f"Created interface {new_iface} for {purpose}")
        return adapter

    # === Access Point Operations ===

    async def create_ap(
        self,
        ssid: str,
        security: str = "wpa2-psk",
        password: Optional[str] = None,
        channel: int = 6,
        hidden: bool = False,
        num_clients: int = 2,
        enterprise_users: Optional[List[dict]] = None,
    ) -> AccessPointRecord:
        """Create and start an access point."""
        # Validate
        if security == "wpa2-psk" and not password:
            raise LabError("WPA2-PSK requires a password")
        if security == "wpa2-psk" and password and len(password) < 8:
            raise LabError("WPA2-PSK password must be at least 8 characters")
        if security == "wep" and not password:
            raise LabError("WEP requires a password/key")
        if security == "wep" and password:
            if len(password) not in (5, 13, 10, 26):
                raise LabError("WEP key must be 5 or 13 ASCII chars, or 10 or 26 hex chars")
            if len(password) in (10, 26) and not all(ch in string.hexdigits for ch in password):
                raise LabError("WEP hex keys must contain only 0-9 and a-f characters")

        # For WPA2-Enterprise, ensure RADIUS is running
        if security == "wpa2-enterprise":
            if not self._radius_running:
                await event_bus.publish("info", "radius", "Starting RADIUS server for WPA2-Enterprise...")
                if enterprise_users:
                    for user in enterprise_users:
                        self.radius.add_user(user.get("username", ""), user.get("password", ""))
                if self.radius.start():
                    self._radius_running = True
                    await event_bus.publish("info", "radius", "RADIUS server started")
                else:
                    await event_bus.publish("warning", "radius", "RADIUS server failed to start - Enterprise auth may not work")

        ap_id = f"ap_{uuid.uuid4().hex[:8]}"
        ap_num = self._reserve_number(self._freed_ap_numbers, "_ap_counter")
        interface = f"bhap{ap_num}"
        dynamic_interface = True
        adapter = None

        await event_bus.publish("info", "ap", f"Creating AP '{ssid}' on new interface {interface}...")

        try:
            adapter = await self._create_named_adapter(interface, f"ap:{ssid}")

            if adapter:
                adapter.in_use = True
                adapter.used_by = ap_id
                adapter.mode = "ap"

            await event_bus.publish("info", "cmd", f"hostapd config: interface={interface} ssid={ssid} security={security} channel={channel}")
            config_path = self.hostapd.generate_config(
                ap_id=ap_id,
                interface=interface,
                ssid=ssid,
                channel=channel,
                security=security,
                password=password,
                hidden=hidden,
            )

            await event_bus.publish("info", "cmd", f"hostapd {config_path}")
            self.hostapd.start(ap_id, interface, config_path)
            await asyncio.sleep(1)

            if not self.hostapd.is_running(ap_id):
                log = self.hostapd.get_log(ap_id)
                self._release_interface(interface)
                if adapter:
                    adapter.in_use = False
                    adapter.used_by = None
                    adapter.mode = "managed"
                if dynamic_interface:
                    self.hwsim.delete_interface(interface)
                    if adapter and adapter.id in self._adapters:
                        del self._adapters[adapter.id]
                    if interface in self._interface_pool:
                        self._interface_pool.remove(interface)
                    self._remember_freed_number(interface, "bhap", self._freed_ap_numbers)
                raise LabError(f"hostapd failed to start. Log: {log[:200]}")

            await event_bus.publish("info", "cmd", f"dnsmasq -C /opt/beaconhub/configs/dnsmasq/{ap_id}.conf")
            self.dnsmasq.start(ap_id, interface)

            ap = AccessPointRecord(
                ap_id=ap_id,
                ssid=ssid,
                security=security,
                channel=channel,
                hidden=hidden,
                interface=interface,
                password=password,
                dynamic_interface=dynamic_interface,
            )
            ap.status = "running"
            ap.bssid = self.hwsim.get_interface_mac(interface)
            self._aps[ap_id] = ap

            await event_bus.publish(
                "info", "ap",
                f"AP '{ssid}' running (BSSID: {ap.bssid}, Ch:{channel}, Security:{security})"
            )

            # Create dedicated adapters for this AP's clients and spawn them
            if num_clients > 0:
                await self._spawn_dedicated_clients(ap, num_clients)

            return ap

        except (HostapdError, DnsmasqError) as e:
            self._release_interface(interface)
            if adapter:
                adapter.in_use = False
                adapter.used_by = None
                adapter.mode = "managed"
            if dynamic_interface:
                self.hwsim.delete_interface(interface)
                if adapter and adapter.id in self._adapters:
                    del self._adapters[adapter.id]
                if interface in self._interface_pool:
                    self._interface_pool.remove(interface)
                self._remember_freed_number(interface, "bhap", self._freed_ap_numbers)
            await event_bus.publish("error", "ap", f"Failed to create AP: {str(e)}")
            raise LabError(f"Failed to create AP: {str(e)}")
        except Exception as e:
            self._release_interface(interface)
            if adapter:
                adapter.in_use = False
                adapter.used_by = None
                adapter.mode = "managed"
            if dynamic_interface:
                self.hwsim.delete_interface(interface)
                if adapter and adapter.id in self._adapters:
                    del self._adapters[adapter.id]
                if interface in self._interface_pool:
                    self._interface_pool.remove(interface)
                self._remember_freed_number(interface, "bhap", self._freed_ap_numbers)
            await event_bus.publish("error", "ap", f"Unexpected error creating AP: {str(e)}")
            raise LabError(f"Failed to create AP: {str(e)}")

    async def _spawn_dedicated_clients(self, ap: AccessPointRecord, count: int):
        """
        Create N new virtual adapters specifically for this AP's clients,
        then spawn client bots on those adapters.
        Uses properly named interfaces like client0, client1, etc.
        Reuses freed client numbers when available.
        """
        for i in range(count):
            # Create a brand new adapter for this client with proper naming
            try:
                # Reuse freed client numbers if available, otherwise use next counter
                if self._freed_client_numbers:
                    client_num = self._freed_client_numbers.pop(0)
                else:
                    client_num = self._client_counter
                    self._client_counter += 1
                
                # Create interface with proper client name
                client_interface = self.hwsim.create_client_interface(client_num)
                if not client_interface:
                    # Fallback to generic adapter creation
                    new_adapter = await self.create_adapter(purpose_hint=f"client:{ap.id}:{i}")
                    client_interface = new_adapter.interface
                else:
                    # Register the new interface in our adapter tracking
                    mac = self.hwsim.get_interface_mac(client_interface) or "00:00:00:00:00:00"
                    interfaces = self.hwsim.get_interfaces()
                    phy = "unknown"
                    for iface_info in interfaces:
                        if iface_info["interface"] == client_interface:
                            phy = iface_info["phy"]
                            break
                    
                    adapter_id = f"adapter_{uuid.uuid4().hex[:8]}"
                    new_adapter = AdapterRecord(
                        adapter_id=adapter_id,
                        interface=client_interface,
                        phy=phy,
                        mac=mac,
                    )
                    self._adapters[adapter_id] = new_adapter
                    self._interface_pool.append(client_interface)
                
                client_id = f"client_{uuid.uuid4().hex[:8]}"

                new_adapter.in_use = True
                new_adapter.used_by = client_id
                self._allocated_interfaces[client_interface] = f"client:{ap.id}:{i}"

                ap.client_adapter_ids.append(new_adapter.id)

                await event_bus.publish(
                    "info", "cmd",
                    f"wpa_supplicant -i {client_interface} -c /opt/beaconhub/configs/wpa_supplicant/{client_id}.conf -D nl80211"
                )
                await asyncio.to_thread(
                    self.clients.connect,
                    client_id=client_id,
                    interface=client_interface,
                    ap_id=ap.id,
                    ssid=ap.ssid,
                    security=ap.security,
                    password=ap.password,
                )
                
                # For WEP networks, start aggressive traffic immediately
                # This generates the IVs needed for cracking
                if ap.security == "wep":
                    self.clients.start_traffic(client_id, interval=1, aggressive=True)
                    await event_bus.publish(
                        "info", "client",
                        f"Client {client_id} connected to WEP AP '{ap.ssid}' - aggressive traffic enabled for IV generation"
                    )
                else:
                    await event_bus.publish(
                        "info", "client",
                        f"Client {client_id} connected to '{ap.ssid}' via {client_interface}"
                    )
            except Exception as e:
                await event_bus.publish(
                    "warning", "client",
                    f"Failed to spawn client {i+1} for AP '{ap.ssid}': {str(e)}"
                )

    async def stop_ap(self, ap_id: str) -> bool:
        """Stop an access point and all associated resources."""
        if ap_id not in self._aps:
            raise LabError(f"AP {ap_id} not found")

        ap = self._aps[ap_id]
        await event_bus.publish("info", "ap", f"Stopping AP '{ap.ssid}'...")

        # Get client list before disconnecting
        clients = self.clients.get_clients_for_ap(ap_id)
        client_interfaces = [bot.interface for bot in clients]

        # Stop WEP attack if running
        self.stop_wep_attack(ap_id)

        # Disconnect all clients
        self.clients.disconnect_by_ap(ap_id)

        # Delete client interfaces that were created for this AP
        # These are virtual interfaces (client0, client1, etc.) that should be removed
        for iface in client_interfaces:
            if iface.startswith("client"):
                # Extract client number for reuse
                try:
                    client_num = int(iface.replace("client", ""))
                    self._remember_freed_number(iface, "client", self._freed_client_numbers)
                except ValueError:
                    pass
                # Delete the virtual interface
                self.hwsim.delete_interface(iface)
                logger.info(f"Deleted client interface {iface} for AP {ap_id}")
            
            # Release the adapter record
            adapter = self._find_adapter_by_interface(iface)
            if adapter:
                adapter.in_use = False
                adapter.used_by = None
                adapter.mode = "managed"
                self._release_interface(adapter.interface)
                # Remove from adapters dict since interface is deleted
                if iface.startswith("client") and adapter.id in self._adapters:
                    del self._adapters[adapter.id]
                    if iface in self._interface_pool:
                        self._interface_pool.remove(iface)

        # Also clean up any dedicated adapters tracked on the AP record
        for adapter_id in ap.client_adapter_ids:
            adapter = self._adapters.get(adapter_id)
            if adapter:
                if adapter.interface.startswith("client"):
                    try:
                        client_num = int(adapter.interface.replace("client", ""))
                        self._remember_freed_number(adapter.interface, "client", self._freed_client_numbers)
                    except ValueError:
                        pass
                    self.hwsim.delete_interface(adapter.interface)
                    if adapter.interface in self._interface_pool:
                        self._interface_pool.remove(adapter.interface)
                    if adapter_id in self._adapters:
                        del self._adapters[adapter_id]
                else:
                    adapter.in_use = False
                    adapter.used_by = None

        # Stop dnsmasq and hostapd
        self.dnsmasq.stop(ap_id)
        self.hostapd.stop(ap_id)

        # Release AP interface (but don't delete wlan* interfaces, only release them)
        self._release_interface(ap.interface)
        ap_adapter = self._find_adapter_by_interface(ap.interface)
        if ap_adapter:
            ap_adapter.in_use = False
            ap_adapter.used_by = None
            ap_adapter.mode = "managed"
            if ap.dynamic_interface:
                self.hwsim.delete_interface(ap.interface)
                if ap.interface in self._interface_pool:
                    self._interface_pool.remove(ap.interface)
                if ap_adapter.id in self._adapters:
                    del self._adapters[ap_adapter.id]
                self._remember_freed_number(ap.interface, "bhap", self._freed_ap_numbers)

        ap.status = "stopped"
        del self._aps[ap_id]

        await event_bus.publish("info", "ap", f"AP '{ap.ssid}' stopped")
        return True

    def get_ap(self, ap_id: str) -> Optional[AccessPointRecord]:
        return self._aps.get(ap_id)

    def list_aps(self) -> List[AccessPointRecord]:
        return list(self._aps.values())

    async def update_ap(
        self,
        ap_id: str,
        password: Optional[str] = None,
        hidden: Optional[bool] = None,
        channel: Optional[int] = None
    ) -> AccessPointRecord:
        """
        Update an AP's settings and restart it.
        
        This will:
        1. Stop hostapd
        2. Update the AP record
        3. Restart hostapd with new config
        4. Reconnect all clients
        """
        if ap_id not in self._aps:
            raise LabError(f"AP {ap_id} not found")

        ap = self._aps[ap_id]
        
        # Track what changed for logging
        changes = []
        
        # Update password if provided
        if password is not None and ap.security in ("wpa2-psk", "wep"):
            ap.password = password
            changes.append("password")
        
        # Update hidden if provided
        if hidden is not None:
            ap.hidden = hidden
            changes.append(f"hidden={hidden}")
        
        # Update channel if provided
        if channel is not None:
            ap.channel = channel
            changes.append(f"channel={channel}")
        
        if not changes:
            # Nothing to update
            return ap
        
        await event_bus.publish("info", "ap", f"Updating AP '{ap.ssid}': {', '.join(changes)}")
        
        # Get connected clients before restart
        clients = self.clients.get_clients_for_ap(ap_id)
        
        # Stop hostapd (but keep clients, dnsmasq running)
        self.hostapd.stop(ap_id)
        
        # Give it a moment
        await asyncio.sleep(0.5)
        
        # Restart hostapd with updated settings
        config_path = self.hostapd.generate_config(
            ap_id=ap.id,
            interface=ap.interface,
            ssid=ap.ssid,
            channel=ap.channel,
            security=ap.security,
            password=ap.password,
            hidden=ap.hidden,
        )
        await event_bus.publish("info", "cmd", f"hostapd {config_path}")
        self.hostapd.start(ap.id, ap.interface, config_path)
        
        await asyncio.sleep(1)
        if not self.hostapd.is_running(ap.id):
            log = self.hostapd.get_log(ap.id)
            raise LabError(f"hostapd failed after update. Log: {log[:200]}")

        ap.bssid = self.hwsim.get_interface_mac(ap.interface)
        
        await event_bus.publish("info", "ap", f"AP '{ap.ssid}' updated and restarted")
        
        # Reconnect all clients in thread pool to avoid blocking the event loop
        for bot in clients:
            try:
                await asyncio.to_thread(self.clients.reconnect, bot.client_id)
            except Exception as e:
                logger.warning(f"Failed to reconnect client {bot.client_id}: {e}")
        
        return ap

    # === Client Operations ===

    async def create_client(
        self,
        ssid: str,
        security: str = "wpa2-psk",
        password: Optional[str] = None,
        ap_id: Optional[str] = None,
        persona: Optional[str] = None,
        device_type: Optional[str] = None,
        hostname: Optional[str] = None,
        eap_identity: Optional[str] = None,
        eap_password: Optional[str] = None,
    ):
        """
        Create a standalone client and connect it to any WiFi network.
        
        This allows creating clients that connect to:
        - An AP managed by this lab (specify ap_id or just ssid)
        - An external/existing AP (specify ssid and password)
        
        For WPA2-Enterprise, use eap_identity and eap_password.
        """
        # Determine the internal AP if ssid matches one of ours
        internal_ap = None
        if ap_id:
            internal_ap = self.get_ap(ap_id)
            if not internal_ap:
                raise LabError(f"AP {ap_id} not found")
            ssid = internal_ap.ssid
            security = internal_ap.security
            password = internal_ap.password
        else:
            # Check if ssid matches an internal AP
            for ap in self._aps.values():
                if ap.ssid == ssid:
                    internal_ap = ap
                    ap_id = ap.id
                    if not password:
                        password = ap.password
                    if not security or security == "wpa2-psk":
                        security = ap.security
                    break
        
        # For enterprise, format password as identity:password
        if security == "wpa2-enterprise" and eap_identity:
            password = f"{eap_identity}:{eap_password or 'password'}"
        
        # Create a new client interface
        client_num = self._reserve_number(self._freed_client_numbers, "_client_counter")
        
        client_interface = self.hwsim.create_client_interface(client_num)
        if not client_interface:
            raise LabError("Failed to create client interface")
        
        # Register adapter
        mac = self.hwsim.get_interface_mac(client_interface) or "00:00:00:00:00:00"
        interfaces = self.hwsim.get_interfaces()
        phy = "unknown"
        for iface_info in interfaces:
            if iface_info["interface"] == client_interface:
                phy = iface_info["phy"]
                break
        
        adapter_id = f"adapter_{uuid.uuid4().hex[:8]}"
        adapter = AdapterRecord(
            adapter_id=adapter_id,
            interface=client_interface,
            phy=phy,
            mac=mac,
        )
        self._adapters[adapter_id] = adapter
        self._interface_pool.append(client_interface)
        
        client_id = f"client_{uuid.uuid4().hex[:8]}"
        adapter.in_use = True
        adapter.used_by = client_id
        self._allocated_interfaces[client_interface] = f"client:standalone:{ssid}"
        
        # If connected to internal AP, track it
        if internal_ap:
            internal_ap.client_adapter_ids.append(adapter_id)
        
        await event_bus.publish(
            "info", "client",
            f"Creating standalone client {client_id} for '{ssid}' on {client_interface}..."
        )
        
        try:
            await event_bus.publish(
                "info", "cmd",
                f"wpa_supplicant -i {client_interface} -c /opt/beaconhub/configs/wpa_supplicant/{client_id}.conf -D nl80211"
            )
            bot = await asyncio.to_thread(
                self.clients.connect,
                client_id=client_id,
                interface=client_interface,
                ap_id=ap_id or f"external:{ssid}",
                ssid=ssid,
                security=security,
                password=password,
                persona=persona,
                device_type=device_type,
                hostname=hostname,
            )
            
            await event_bus.publish(
                "info", "client",
                f"Client {client_id} ({bot.persona}) connected to '{ssid}' via {client_interface} (IP: {bot.ip_address})"
            )
            
            return {
                "client_id": client_id,
                "adapter_id": adapter_id,
                "interface": client_interface,
                "mac_address": mac,
                "ip_address": bot.ip_address,
                "ssid": ssid,
                "security": security,
                "persona": bot.persona,
                "device_type": bot.device_type,
                "hostname": bot.hostname,
            }
            
        except Exception as e:
            # Cleanup on failure
            adapter.in_use = False
            adapter.used_by = None
            self._release_interface(client_interface)
            if client_interface in self._interface_pool:
                self._interface_pool.remove(client_interface)
            if adapter_id in self._adapters:
                del self._adapters[adapter_id]
            self.hwsim.delete_interface(client_interface)
            self._remember_freed_number(client_interface, "client", self._freed_client_numbers)
            await event_bus.publish("error", "client", f"Failed to connect client: {str(e)}")
            raise LabError(f"Failed to create client: {str(e)}")

    async def disconnect_client(self, client_id: str) -> bool:
        """Disconnect and remove a client."""
        bot = self.clients.get_client(client_id)
        if not bot:
            raise LabError(f"Client {client_id} not found")
        
        interface = bot.interface
        
        # Disconnect the client
        self.clients.disconnect(client_id)
        
        # Release the adapter
        adapter = self._find_adapter_by_interface(interface)
        if adapter:
            adapter.in_use = False
            adapter.used_by = None
            adapter.mode = "managed"
            self._release_interface(interface)
            if interface.startswith("client"):
                self.hwsim.delete_interface(interface)
                if interface in self._interface_pool:
                    self._interface_pool.remove(interface)
                if adapter.id in self._adapters:
                    del self._adapters[adapter.id]
                self._remember_freed_number(interface, "client", self._freed_client_numbers)
        
        await event_bus.publish("info", "client", f"Client {client_id} disconnected")
        return True

    # === Adapter Operations ===

    def list_adapters(self) -> List[AdapterRecord]:
        return list(self._adapters.values())

    def get_adapter(self, adapter_id: str) -> Optional[AdapterRecord]:
        return self._adapters.get(adapter_id)

    async def create_adapter(self, purpose_hint: str = "") -> AdapterRecord:
        """Create a new virtual wireless adapter dynamically."""
        new_iface = self.hwsim.create_radio()
        if not new_iface:
            raise LabError("Failed to create new adapter. Max radios may be reached.")

        mac = self.hwsim.get_interface_mac(new_iface) or "00:00:00:00:00:00"
        interfaces = self.hwsim.get_interfaces()
        phy = "unknown"
        for iface_info in interfaces:
            if iface_info["interface"] == new_iface:
                phy = iface_info["phy"]
                break

        # UUID-based ID to prevent collisions after deletions
        adapter_id = f"adapter_{uuid.uuid4().hex[:8]}"
        adapter = AdapterRecord(
            adapter_id=adapter_id,
            interface=new_iface,
            phy=phy,
            mac=mac,
        )
        self._adapters[adapter_id] = adapter
        self._interface_pool.append(new_iface)
        # Mark as allocated if a purpose was given
        if purpose_hint:
            self._allocated_interfaces[new_iface] = purpose_hint

        await event_bus.publish("info", "adapter", f"Created adapter: {new_iface} ({mac})")
        return adapter

    async def delete_adapter(self, adapter_id: str) -> bool:
        """Delete a virtual wireless adapter."""
        adapter = self._adapters.get(adapter_id)
        if not adapter:
            raise LabError(f"Adapter {adapter_id} not found")
        if adapter.in_use:
            raise LabError(f"Adapter {adapter_id} is in use by {adapter.used_by}. Stop it first.")

        success = self.hwsim.delete_interface(adapter.interface)
        if not success:
            raise LabError(f"Failed to delete interface {adapter.interface}")

        if adapter.interface in self._interface_pool:
            self._interface_pool.remove(adapter.interface)
        self._release_interface(adapter.interface)
        del self._adapters[adapter_id]

        await event_bus.publish("info", "adapter", f"Deleted adapter: {adapter.interface}")
        return True

    async def set_adapter_mode(self, adapter_id: str, mode: str) -> bool:
        """Set adapter mode (managed/monitor)."""
        adapter = self._adapters.get(adapter_id)
        if not adapter:
            raise LabError(f"Adapter {adapter_id} not found")

        if adapter.in_use:
            raise LabError(
                f"Adapter {adapter_id} is in use by {adapter.used_by}. "
                "Stop the process using it first."
            )

        if mode == "monitor":
            success = self.hwsim.set_monitor_mode(adapter.interface)
            if success:
                adapter.mode = "monitor"
                await event_bus.publish("info", "adapter", f"Adapter {adapter.interface} → monitor mode")
            else:
                raise LabError(f"Failed to set {adapter.interface} to monitor mode")
        elif mode == "managed":
            success = self.hwsim.set_managed_mode(adapter.interface)
            if success:
                adapter.mode = "managed"
                await event_bus.publish("info", "adapter", f"Adapter {adapter.interface} → managed mode")
            else:
                raise LabError(f"Failed to set {adapter.interface} to managed mode")
        else:
            raise LabError(f"Unsupported mode: {mode}")

        return True

    # === System Operations ===

    def get_system_status(self) -> dict:
        """Get overall system status."""
        total_clients = len(self.clients.list_all())
        available_adapters = sum(1 for a in self._adapters.values() if not a.in_use)

        return {
            "hwsim_loaded": self.hwsim.is_module_loaded(),
            "total_radios": self.hwsim.get_radio_count(),
            "aps_running": len(self._aps),
            "adapters_available": available_adapters,
            "clients_connected": total_clients,
            "uptime_seconds": int(time.time() - self._started_at),
        }

    async def reset_lab(self):
        """Reset the entire lab — stop everything."""
        await event_bus.publish("warning", "lab", "Resetting lab...")

        self.clients.disconnect_all()

        for ap_id in list(self._aps.keys()):
            self.dnsmasq.stop(ap_id)
            self.hostapd.stop(ap_id)
        self._aps.clear()

        for adapter in self._adapters.values():
            adapter.in_use = False
            adapter.used_by = None
            adapter.mode = "managed"
            self.hwsim.set_managed_mode(adapter.interface)

        self._allocated_interfaces.clear()
        self._client_counter = 0
        
        # Stop RADIUS if running
        if self._radius_running:
            self.radius.stop()
            self._radius_running = False
            
        await event_bus.publish("info", "lab", "Lab reset complete")

    async def shutdown(self):
        """Graceful shutdown of all components."""
        await event_bus.publish("info", "lab", "Shutting down BeaconHub...")
        self.clients.stop_reconnect_watcher()
        self.clients.stop_all_probes()
        self.clients.disconnect_all()
        self.capture.stop_all()
        for ap_id in list(self._wep_attacks.keys()):
            self.stop_wep_attack(ap_id)
        self.aircrack.stop_all()
        self.hostapd.stop_all()
        self.dnsmasq.stop_all()
        
        # Stop RADIUS server
        if self._radius_running:
            self.radius.stop()
            self._radius_running = False
            
        await event_bus.publish("info", "lab", "Shutdown complete")

    # === WEP Attack Operations ===

    def start_wep_attack(self, ap_id: str, channel: int) -> dict:
        """Start airodump-ng capture + aireplay-ng ARP replay on all clients for WEP IV generation."""
        ap = self.get_ap(ap_id)
        if not ap:
            raise LabError(f"AP {ap_id} not found")
        if ap.security != "wep":
            raise LabError(f"AP {ap_id} is not WEP")

        # Stop existing WEP attack for this AP
        self.stop_wep_attack(ap_id)

        clients = self.clients.get_clients_for_ap(ap_id)
        if not clients:
            raise LabError(f"No clients connected to AP {ap_id}")

        # Start airodump-ng capture
        capture_id = f"wep_cap_{ap_id}"
        self.aircrack.start_wep_capture(capture_id, ap.interface, ap.bssid, channel)

        # Ensure client interfaces are in monitor mode for aireplay
        # Clients already connected so their interfaces are on the right channel

        # Start ARP replay on each client
        replay_ids = []
        for bot in clients:
            replay_id = f"wep_replay_{bot.client_id}"
            try:
                self.aircrack.start_arp_replay(
                    replay_id, bot.interface, ap.bssid, bot.mac_address
                )
                replay_ids.append(replay_id)
            except Exception as e:
                logger.warning(f"Failed to start ARP replay on {bot.client_id}: {e}")

        # Start aggressive traffic as well (background noise + ARP)
        for bot in clients:
            self.clients.stop_traffic(bot.client_id)
            self.clients.start_traffic(bot.client_id, interval=1, aggressive=True)

        self._wep_attacks[ap_id] = {
            "capture_id": capture_id,
            "replay_ids": replay_ids,
        }

        logger.info(f"WEP attack started on AP '{ap.ssid}' with {len(replay_ids)} ARP replays")
        return {"capture_id": capture_id, "replay_ids": replay_ids}

    def get_wep_iv_count(self, ap_id: str) -> int:
        """Get current IV count for a WEP attack."""
        wep = self._wep_attacks.get(ap_id)
        if not wep:
            return 0
        capture_id = wep["capture_id"]
        attack = self.aircrack.get_attack(capture_id)
        if not attack or not attack.output_file:
            return 0
        return self.aircrack.get_iv_count(attack.output_file)

    def stop_wep_attack(self, ap_id: str):
        """Stop all WEP attack processes for an AP."""
        wep = self._wep_attacks.pop(ap_id, None)
        if not wep:
            return

        # Stop ARP replays
        for replay_id in wep.get("replay_ids", []):
            self.aircrack.stop_attack(replay_id)

        # Stop capture
        self.aircrack.stop_attack(wep["capture_id"])

        # Stop aggressive traffic on clients
        for bot in self.clients.get_clients_for_ap(ap_id):
            self.clients.stop_traffic(bot.client_id)

        logger.info(f"WEP attack stopped on AP {ap_id}")

    # === Attack Operations ===

    async def launch_attack(
        self,
        attack_type: str,
        target_ap_id: str,
        adapter_id: str,
        duration: int = 60,
        target_client: Optional[str] = None,
    ) -> AttackRecord:
        """Launch an attack against a target AP."""
        # Validate target AP
        ap = self.get_ap(target_ap_id)
        if not ap:
            raise LabError(f"Target AP {target_ap_id} not found")
        
        # Validate and get adapter
        adapter = self.get_adapter(adapter_id)
        if not adapter:
            raise LabError(f"Adapter {adapter_id} not found")
        
        if adapter.in_use:
            raise LabError(f"Adapter {adapter_id} is already in use by {adapter.used_by}")
        
        # Adapter must be in monitor mode for attacks
        if adapter.mode != "monitor":
            await event_bus.publish("info", "attack", f"Setting {adapter.interface} to monitor mode...")
            success = self.hwsim.set_monitor_mode(adapter.interface)
            if not success:
                raise LabError(f"Failed to set {adapter.interface} to monitor mode")
            adapter.mode = "monitor"
        
        attack_id = f"attack_{uuid.uuid4().hex[:8]}"
        record = AttackRecord(attack_id, attack_type, target_ap_id, adapter_id)
        
        try:
            adapter.in_use = True
            adapter.used_by = attack_id
            
            if attack_type == "deauth":
                await event_bus.publish(
                    "warning", "attack",
                    f"Launching deauth attack on {ap.ssid} ({ap.bssid})..."
                )
                await event_bus.publish(
                    "info", "cmd",
                    f"aireplay-ng --deauth 0 -a {ap.bssid}" + (f" -c {target_client}" if target_client else "") + f" {adapter.interface}"
                )
                attack_proc = self.aircrack.start_deauth(
                    attack_id=attack_id,
                    interface=adapter.interface,
                    target_bssid=ap.bssid,
                    count=0,  # Continuous
                    client_mac=target_client,
                )
                record.status = "running"
                
            elif attack_type == "capture_handshake":
                await event_bus.publish(
                    "info", "attack",
                    f"Starting handshake capture on {ap.ssid} ({ap.bssid})..."
                )
                await event_bus.publish(
                    "info", "cmd",
                    f"airodump-ng --bssid {ap.bssid} --channel {ap.channel} --write /opt/beaconhub/captures/capture_{attack_id} {adapter.interface}"
                )
                attack_proc = self.aircrack.start_capture(
                    attack_id=attack_id,
                    interface=adapter.interface,
                    target_bssid=ap.bssid,
                    channel=ap.channel,
                )
                record.output_file = attack_proc.output_file
                record.status = "running"
                
            else:
                adapter.in_use = False
                adapter.used_by = None
                raise LabError(f"Unknown attack type: {attack_type}")
            
            self._attacks[attack_id] = record
            if duration > 0:
                asyncio.create_task(self._auto_stop_attack(attack_id, duration))
            
            await event_bus.publish(
                "info", "attack",
                f"Attack {attack_id} ({attack_type}) launched against {ap.ssid} for {duration}s"
            )
            
            return record
            
        except AircrackError as e:
            adapter.in_use = False
            adapter.used_by = None
            raise LabError(f"Failed to launch attack: {str(e)}")

    async def stop_attack(self, attack_id: str) -> bool:
        """Stop a running attack."""
        if attack_id not in self._attacks:
            raise LabError(f"Attack {attack_id} not found")
        
        record = self._attacks[attack_id]
        
        self.aircrack.stop_attack(attack_id)
        record.status = "stopped"
        record.stopped_at = datetime.now().isoformat()
        
        # Release adapter
        adapter = self.get_adapter(record.adapter_id)
        if adapter:
            adapter.in_use = False
            adapter.used_by = None
        
        await event_bus.publish("info", "attack", f"Attack {attack_id} stopped")
        return True

    async def _auto_stop_attack(self, attack_id: str, duration: int):
        """Stop an attack after its requested duration."""
        await asyncio.sleep(duration)
        record = self._attacks.get(attack_id)
        if not record or record.status != "running":
            return
        try:
            await self.stop_attack(attack_id)
            record.status = "completed"
            await event_bus.publish("info", "attack", f"Attack {attack_id} completed after {duration}s")
        except Exception as e:
            logger.warning(f"Failed to auto-stop attack {attack_id}: {e}")

    def get_attack(self, attack_id: str) -> Optional[AttackRecord]:
        """Get attack record."""
        return self._attacks.get(attack_id)

    def list_attacks(self) -> List[AttackRecord]:
        """List all attacks."""
        return list(self._attacks.values())
