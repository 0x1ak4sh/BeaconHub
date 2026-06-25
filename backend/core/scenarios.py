"""
Scenario engine for BeaconHub.
Defines guided lab scenarios with objectives, personas, and auto-deployment.
"""

import asyncio
import uuid
import time
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field

from .events import event_bus


# === Data structures ===

@dataclass
class Persona:
    name: str
    role: str
    device_type: str  # laptop, phone, tablet
    hostname: str
    os: str
    behavior: str  # description of what this device does


@dataclass
class Objective:
    id: str
    title: str
    description: str
    points: int
    hint: Optional[str] = None
    status: str = "pending"  # pending, completed, failed
    validation_type: str = "manual"  # manual, auto_handshake, auto_deauth
    completed_at: Optional[str] = None


@dataclass
class ScenarioDefinition:
    id: str
    name: str
    description: str
    difficulty: str  # beginner, intermediate, advanced
    category: str
    points_total: int
    objectives: List[Objective]
    personas: List[Persona]
    attack_flow: List[str]  # visual flow steps
    # Environment config
    aps: List[dict] = field(default_factory=list)  # AP configs to auto-create
    auto_clients: int = 2


# === Scenario Definitions ===

SCENARIOS: Dict[str, ScenarioDefinition] = {}


def _define_scenarios():
    """Define all available scenarios."""

    # --- Scenario 1: WPA2 Handshake Capture ---
    SCENARIOS["wpa2_handshake"] = ScenarioDefinition(
        id="wpa2_handshake",
        name="WPA2 Handshake Capture",
        description="Capture a WPA2 4-way handshake from a corporate network. A client is actively connecting to the AP. Use deauthentication to force a reconnection and capture the handshake.",
        difficulty="beginner",
        category="Cracking",
        points_total=100,
        objectives=[
            Objective("obj_1", "Set adapter to monitor mode", "Switch a free adapter to monitor mode for packet capture.", 10, hint="Go to Adapters tab and click Monitor on a free adapter."),
            Objective("obj_2", "Identify the target AP", "Find the target AP's BSSID and channel.", 10, hint="Check the Access Points tab for BSSID info."),
            Objective("obj_3", "Start packet capture", "Launch airodump-ng / handshake capture on the target.", 20, hint="Use Attacks > Handshake Capture targeting the AP."),
            Objective("obj_4", "Deauthenticate a client", "Send deauth frames to force client reconnection.", 30, hint="Launch a Deauth attack on the same AP."),
            Objective("obj_5", "Capture the handshake", "Successfully capture the WPA2 4-way handshake.", 30, hint="Check the capture file with 'Check Handshake' button."),
        ],
        personas=[
            Persona("Sarah Chen", "Finance Manager", "laptop", "LAPTOP-SARAH", "Windows 11", "Connects to corporate WiFi, checks email every 5 min"),
            Persona("Mike Johnson", "Sales Rep", "phone", "MikePhone", "iOS 17", "Streaming music, constant connection"),
        ],
        attack_flow=[
            "Reconnaissance: Identify target AP",
            "Setup: Put adapter in monitor mode",
            "Capture: Start airodump-ng on target channel",
            "Deauth: Send deauthentication frames",
            "Client reconnects automatically",
            "Handshake captured in PCAP file",
            "Crack: Run aircrack-ng with wordlist",
        ],
        aps=[
            {"ssid": "CorpNet-Finance", "security": "wpa2-psk", "password": "Summer2024!", "channel": 6}
        ],
        auto_clients=2,
    )

    # --- Scenario 2: Hidden SSID Discovery ---
    SCENARIOS["hidden_ssid"] = ScenarioDefinition(
        id="hidden_ssid",
        name="Hidden SSID Discovery",
        description="A security team has hidden their network SSID thinking it provides security. Discover the hidden network name by monitoring probe requests from connected clients.",
        difficulty="beginner",
        category="Reconnaissance",
        points_total=60,
        objectives=[
            Objective("obj_1", "Enable monitor mode", "Set an adapter to monitor mode.", 10),
            Objective("obj_2", "Detect hidden network", "Identify that a hidden AP exists by observing beacons with empty SSID.", 20, hint="Hidden APs still broadcast beacons, but with blank SSID field."),
            Objective("obj_3", "Capture probe response", "Wait for a client probe request/response that reveals the SSID.", 30, hint="When a client connects, it sends the real SSID in probe requests."),
        ],
        personas=[
            Persona("Admin Workstation", "IT Administrator", "laptop", "IT-ADMIN-PC", "Ubuntu 22.04", "Periodic reconnection to hidden management network"),
        ],
        attack_flow=[
            "Monitor: Listen for beacon frames",
            "Detect: Spot beacons with empty SSID",
            "Wait: Client sends probe request with real SSID",
            "Reveal: SSID discovered from probe traffic",
        ],
        aps=[
            {"ssid": "MGMT-Secure", "security": "wpa2-psk", "password": "AdminP@ss99", "channel": 1, "hidden": True}
        ],
        auto_clients=1,
    )

    # --- Scenario 3: Evil Twin Attack ---
    SCENARIOS["evil_twin"] = ScenarioDefinition(
        id="evil_twin",
        name="Evil Twin Attack",
        description="Create a rogue access point that mimics the target corporate network. Deauth clients from the real AP and lure them to your fake one to capture credentials.",
        difficulty="intermediate",
        category="Impersonation",
        points_total=150,
        objectives=[
            Objective("obj_1", "Identify target network", "Note the SSID, BSSID, and security of the target.", 10),
            Objective("obj_2", "Create evil twin AP", "Create an open AP with the same SSID as the target.", 30, hint="Create an AP with same SSID but 'Open' security."),
            Objective("obj_3", "Deauth clients from real AP", "Force clients off the legitimate network.", 30, hint="Run deauth attack on the original AP."),
            Objective("obj_4", "Client connects to evil twin", "A victim client connects to your rogue AP.", 40, hint="After deauth, clients may auto-connect to the open network."),
            Objective("obj_5", "Capture traffic", "Monitor traffic from the connected victim.", 40, hint="Use packet capture on the evil twin's interface."),
        ],
        personas=[
            Persona("David Park", "Marketing Director", "laptop", "DAVID-LAPTOP", "macOS Sonoma", "Auto-connects to known SSIDs, browses frequently"),
            Persona("Lisa Wang", "Intern", "phone", "Lisa-iPhone", "iOS 17", "Social media heavy, accepts any WiFi"),
            Persona("Tom Baker", "Contractor", "laptop", "CONTRACTOR-PC", "Windows 10", "Connects to guest network, VPN usage"),
        ],
        attack_flow=[
            "Recon: Identify target AP and clients",
            "Clone: Create AP with same SSID (open)",
            "Deauth: Kick clients off real AP",
            "Lure: Victims auto-connect to evil twin",
            "Capture: Intercept plaintext traffic",
            "Harvest: Extract credentials from HTTP/DNS",
        ],
        aps=[
            {"ssid": "CorpGuest", "security": "wpa2-psk", "password": "Welcome123", "channel": 11}
        ],
        auto_clients=3,
    )

    # --- Scenario 4: WPA2 Enterprise ---
    SCENARIOS["wpa2_enterprise"] = ScenarioDefinition(
        id="wpa2_enterprise",
        name="WPA2 Enterprise Credential Harvesting",
        description="The target uses WPA2-Enterprise with RADIUS authentication. Set up a rogue RADIUS server to capture enterprise credentials (username/password hashes) from connecting clients.",
        difficulty="advanced",
        category="Enterprise",
        points_total=200,
        objectives=[
            Objective("obj_1", "Identify enterprise network", "Detect WPA2-Enterprise AP via beacon analysis.", 20),
            Objective("obj_2", "Setup rogue AP with same SSID", "Create an AP mimicking the enterprise network.", 40, hint="Use WPA2-Enterprise security type."),
            Objective("obj_3", "Deauth enterprise clients", "Force clients to reconnect.", 30),
            Objective("obj_4", "Capture EAP credentials", "Harvest username/hash from EAP exchange.", 60, hint="Clients will attempt EAP auth against your rogue AP."),
            Objective("obj_5", "Identify user accounts", "Determine at least one valid username.", 50, hint="Check the hostapd logs for EAP identity."),
        ],
        personas=[
            Persona("CEO - Richard Hayes", "Chief Executive", "laptop", "CEO-SURFACE", "Windows 11 Pro", "Connects to enterprise WiFi, Outlook, Teams"),
            Persona("IT Admin - Priya Sharma", "System Administrator", "laptop", "ADMIN-THINKPAD", "Ubuntu 22.04", "SSH sessions, admin panels"),
            Persona("HR - Jennifer Liu", "HR Manager", "tablet", "HR-IPAD", "iPadOS 17", "HR portal, employee data"),
        ],
        attack_flow=[
            "Recon: Identify WPA2-Enterprise AP",
            "Analyze: Determine EAP type (PEAP/EAP-TLS)",
            "Deploy: Create rogue AP + RADIUS",
            "Deauth: Force clients off legitimate AP",
            "Harvest: Capture EAP identity + challenge",
            "Crack: Offline brute-force the MS-CHAPv2 hash",
        ],
        aps=[
            {"ssid": "CORP-SECURE", "security": "wpa2-enterprise", "channel": 36}
        ],
        auto_clients=3,
    )

    # --- Scenario 5: PMKID Attack ---
    SCENARIOS["pmkid_attack"] = ScenarioDefinition(
        id="pmkid_attack",
        name="PMKID Clientless Attack",
        description="The PMKID attack allows capturing authentication material without any clients connected. Only the first message of the 4-way handshake is needed, extracted from the AP's RSN IE.",
        difficulty="intermediate",
        category="Cracking",
        points_total=120,
        objectives=[
            Objective("obj_1", "Enable monitor mode", "Prepare adapter for raw frame capture.", 10),
            Objective("obj_2", "Send association request", "Trigger the AP to send an EAPOL M1 with PMKID.", 30, hint="aireplay-ng can send authentication/association frames."),
            Objective("obj_3", "Capture PMKID from M1", "Extract PMKID from the first EAPOL frame.", 40),
            Objective("obj_4", "Prepare for offline crack", "Convert capture to hashcat format.", 40, hint="Use hcxpcapngtool to convert the PCAP."),
        ],
        personas=[
            Persona("IoT Camera", "Security Camera", "iot", "IPCAM-LOBBY", "Embedded Linux", "Streams video 24/7, rarely reconnects"),
        ],
        attack_flow=[
            "Scan: Find target AP (no clients needed)",
            "Associate: Send auth frame to AP",
            "Capture: AP responds with PMKID in M1",
            "Extract: Pull PMKID from PCAP",
            "Convert: hcxpcapngtool → hashcat format",
            "Crack: hashcat -m 22000 with wordlist",
        ],
        aps=[
            {"ssid": "IoT-Network", "security": "wpa2-psk", "password": "camera123", "channel": 3}
        ],
        auto_clients=1,
    )

    # --- Scenario 6: Rogue AP Detection ---
    SCENARIOS["rogue_detection"] = ScenarioDefinition(
        id="rogue_detection",
        name="Rogue Access Point Detection",
        description="You are the blue team. Multiple APs are broadcasting. Identify which one is the rogue AP by analyzing signal characteristics, BSSID anomalies, and security mismatches.",
        difficulty="intermediate",
        category="Defense",
        points_total=100,
        objectives=[
            Objective("obj_1", "Scan all APs", "List all broadcasting access points.", 10),
            Objective("obj_2", "Identify duplicate SSIDs", "Find SSIDs that appear more than once.", 20),
            Objective("obj_3", "Compare security settings", "Spot the AP with mismatched security.", 30, hint="The real AP uses WPA2, the rogue is open."),
            Objective("obj_4", "Flag the rogue", "Identify the rogue AP by BSSID.", 40),
        ],
        personas=[],
        attack_flow=[
            "Monitor: Enable passive scanning",
            "Collect: List all beacons and their properties",
            "Analyze: Compare SSIDs, BSSIDs, security",
            "Detect: Spot the impostor",
            "Report: Document the rogue AP details",
        ],
        aps=[
            {"ssid": "Office-WiFi", "security": "wpa2-psk", "password": "OfficePass1", "channel": 6},
            {"ssid": "Office-WiFi", "security": "open", "channel": 6},  # rogue
        ],
        auto_clients=2,
    )

    # --- Scenario 7: Captive Portal ---
    SCENARIOS["captive_portal"] = ScenarioDefinition(
        id="captive_portal",
        name="Captive Portal Phishing",
        description="Set up a fake open WiFi hotspot with a captive portal that mimics a hotel login page. Harvest credentials from unsuspecting guests.",
        difficulty="advanced",
        category="Social Engineering",
        points_total=180,
        objectives=[
            Objective("obj_1", "Create open honeypot AP", "Deploy an open AP with an attractive SSID.", 20, hint="Use names like 'Free_Hotel_WiFi' or 'Airport_Free'."),
            Objective("obj_2", "Configure DNS redirect", "All DNS queries redirect to your portal.", 30),
            Objective("obj_3", "Serve captive portal page", "HTTP server presents fake login page.", 40),
            Objective("obj_4", "Victim connects", "A persona connects to your honeypot.", 40),
            Objective("obj_5", "Harvest credentials", "Capture the submitted login credentials.", 50),
        ],
        personas=[
            Persona("Traveler - Anna Klein", "Business Traveler", "laptop", "ANNA-MACBOOK", "macOS", "Looking for free WiFi in hotel lobby"),
            Persona("Tourist - Raj Patel", "Tourist", "phone", "Raj-Pixel", "Android 14", "Connects to any open WiFi for maps"),
        ],
        attack_flow=[
            "Deploy: Create open AP (honeypot SSID)",
            "Configure: DNS hijack → portal server",
            "Serve: Fake login page (hotel/airport)",
            "Wait: Victim connects to open network",
            "Redirect: All HTTP → captive portal",
            "Harvest: Victim enters credentials",
            "Capture: Log username/password",
        ],
        aps=[
            {"ssid": "Hilton_Guest_WiFi", "security": "open", "channel": 9}
        ],
        auto_clients=2,
    )


# Initialize scenarios
_define_scenarios()


# === Scenario Runtime Manager ===

class ScenarioManager:
    """Manages scenario deployment, state, and scoring."""

    def __init__(self):
        self._active_scenario: Optional[str] = None
        self._scenario_state: Dict[str, dict] = {}  # scenario_id -> state
        self._scores: Dict[str, dict] = {}  # scenario_id -> score info

    @property
    def active_scenario_id(self) -> Optional[str]:
        return self._active_scenario

    def get_all_scenarios(self) -> List[ScenarioDefinition]:
        """Get all available scenarios."""
        return list(SCENARIOS.values())

    def get_scenario(self, scenario_id: str) -> Optional[ScenarioDefinition]:
        """Get a specific scenario definition."""
        return SCENARIOS.get(scenario_id)

    def get_scenario_status(self, scenario_id: str) -> str:
        """Get current status of a scenario."""
        if scenario_id not in self._scenario_state:
            return "available"
        return self._scenario_state[scenario_id].get("status", "available")

    async def deploy_scenario(self, scenario_id: str, lab_manager) -> dict:
        """Deploy a scenario - creates APs, clients, sets up environment."""
        scenario = SCENARIOS.get(scenario_id)
        if not scenario:
            raise ValueError(f"Scenario {scenario_id} not found")

        if self._active_scenario:
            raise ValueError(f"Scenario {self._active_scenario} is already active. Stop it first.")

        await event_bus.publish("info", "scenario", f"Deploying scenario: {scenario.name}")

        self._active_scenario = scenario_id
        self._scenario_state[scenario_id] = {
            "status": "deploying",
            "started_at": datetime.now().isoformat(),
            "objectives": {obj.id: "pending" for obj in scenario.objectives},
            "ap_ids": [],
        }

        # Create APs defined in scenario
        created_aps = []
        for ap_config in scenario.aps:
            try:
                ap = await lab_manager.create_ap(
                    ssid=ap_config["ssid"],
                    security=ap_config.get("security", "wpa2-psk"),
                    password=ap_config.get("password"),
                    channel=ap_config.get("channel", 6),
                    hidden=ap_config.get("hidden", False),
                    num_clients=scenario.auto_clients,
                )
                created_aps.append(ap.id)
                await event_bus.publish(
                    "info", "scenario",
                    f"Created AP: {ap_config['ssid']} (ch {ap_config.get('channel', 6)})"
                )
            except Exception as e:
                await event_bus.publish("error", "scenario", f"Failed to create AP: {e}")

        self._scenario_state[scenario_id]["ap_ids"] = created_aps
        self._scenario_state[scenario_id]["status"] = "active"

        await event_bus.publish(
            "info", "scenario",
            f"Scenario '{scenario.name}' deployed. {len(created_aps)} APs created. Complete the objectives."
        )

        return self._scenario_state[scenario_id]

    async def stop_scenario(self, scenario_id: str, lab_manager) -> bool:
        """Stop and tear down a scenario."""
        if scenario_id not in self._scenario_state:
            return False

        state = self._scenario_state[scenario_id]

        # Stop all APs created by this scenario
        for ap_id in state.get("ap_ids", []):
            try:
                await lab_manager.stop_ap(ap_id)
            except Exception:
                pass

        state["status"] = "completed"
        state["completed_at"] = datetime.now().isoformat()
        self._active_scenario = None

        # Calculate score
        scenario = SCENARIOS.get(scenario_id)
        if scenario:
            earned = sum(
                obj.points for obj in scenario.objectives
                if state["objectives"].get(obj.id) == "completed"
            )
            self._scores[scenario_id] = {
                "points_earned": earned,
                "points_total": scenario.points_total,
                "completed": earned == scenario.points_total,
                "completed_at": state["completed_at"],
            }

        await event_bus.publish("info", "scenario", f"Scenario stopped.")
        return True

    async def complete_objective(self, scenario_id: str, objective_id: str) -> bool:
        """Mark an objective as completed."""
        if scenario_id not in self._scenario_state:
            return False

        state = self._scenario_state[scenario_id]
        if objective_id not in state["objectives"]:
            return False

        if state["objectives"][objective_id] == "completed":
            return True  # Already done

        state["objectives"][objective_id] = "completed"

        # Find objective details for logging (don't mutate the global definition)
        scenario = SCENARIOS.get(scenario_id)
        if scenario:
            obj = next((o for o in scenario.objectives if o.id == objective_id), None)
            if obj:
                await event_bus.publish(
                    "info", "scenario",
                    f"Objective completed: {obj.title} (+{obj.points} pts)"
                )

        # Check if all objectives done
        all_done = all(v == "completed" for v in state["objectives"].values())
        if all_done:
            await event_bus.publish("info", "scenario", "All objectives complete! Scenario finished.")

        return True

    def get_scoreboard(self) -> dict:
        """Get overall scoreboard."""
        entries = []
        total_earned = 0
        total_possible = 0
        completed_count = 0

        for scenario_id, scenario in SCENARIOS.items():
            score = self._scores.get(scenario_id, {})
            earned = score.get("points_earned", 0)
            entries.append({
                "scenario_id": scenario_id,
                "scenario_name": scenario.name,
                "points_earned": earned,
                "points_total": scenario.points_total,
                "completed": score.get("completed", False),
                "completed_at": score.get("completed_at"),
            })
            total_earned += earned
            total_possible += scenario.points_total
            if score.get("completed"):
                completed_count += 1

        return {
            "total_points": total_earned,
            "max_points": total_possible,
            "scenarios_completed": completed_count,
            "scenarios_total": len(SCENARIOS),
            "entries": entries,
        }

    def get_objective_states(self, scenario_id: str) -> Dict[str, str]:
        """Get objective completion states for a scenario."""
        if scenario_id not in self._scenario_state:
            return {}
        return self._scenario_state[scenario_id].get("objectives", {})
