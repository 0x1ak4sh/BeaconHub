"""
Pydantic models for BeaconHub API.
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class SecurityType(str, Enum):
    OPEN = "open"
    WEP = "wep"
    WPA2_PSK = "wpa2-psk"
    WPA2_ENTERPRISE = "wpa2-enterprise"


class APStatus(str, Enum):
    STARTING = "starting"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"


class AdapterMode(str, Enum):
    MANAGED = "managed"
    MONITOR = "monitor"
    AP = "ap"


# === Request Models ===

class CreateAPRequest(BaseModel):
    ssid: str = Field(..., min_length=1, max_length=32)
    security: SecurityType = Field(default=SecurityType.WPA2_PSK)
    password: Optional[str] = Field(None, max_length=63)
    wep_key: Optional[str] = Field(None, description="WEP key (5/13 ASCII chars or 10/26 hex digits)")
    channel: int = Field(default=6, ge=1, le=14)
    hidden: bool = Field(default=False)
    num_clients: int = Field(default=2, ge=0, le=8, description="Number of simulated clients to auto-connect")
    enterprise_users: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description="List of {username, password} for WPA2-Enterprise RADIUS users"
    )


class CreateClientRequest(BaseModel):
    """Request to create a standalone client that connects to any WiFi."""
    ssid: str = Field(..., min_length=1, max_length=32, description="WiFi network SSID to connect to")
    security: SecurityType = Field(default=SecurityType.WPA2_PSK, description="Security type of the network")
    password: Optional[str] = Field(None, description="WiFi password (WPA2-PSK or WEP key)")
    ap_id: Optional[str] = Field(None, description="Internal AP ID to connect to (optional)")
    persona: Optional[str] = Field(None, description="Client persona name")
    device_type: Optional[str] = Field(None, description="Device type (laptop, smartphone, etc)")
    hostname: Optional[str] = Field(None, description="Client hostname")
    eap_identity: Optional[str] = Field(None, description="EAP identity for WPA2-Enterprise")
    eap_password: Optional[str] = Field(None, description="EAP password for WPA2-Enterprise")


class SetAdapterModeRequest(BaseModel):
    mode: AdapterMode


class ClientActionRequest(BaseModel):
    action: str  # reconnect, browse_url, submit_credentials, open_captive, dns_lookup
    url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None


class ClientCredentialsRequest(BaseModel):
    username: str = ""
    password: str = ""
    target_url: str = "http://10.0.1.1/login"
    submit_and_reconnect: bool = True


class TrafficStartRequest(BaseModel):
    interval_seconds: int = Field(default=10, ge=1, le=120)
    traffic_types: List[str] = Field(default=["dns", "ping", "browse"])
    aggressive: bool = Field(default=False, description="High-volume traffic for WEP IV generation")


class UpdateAPRequest(BaseModel):
    """Request to update an existing AP settings."""
    password: Optional[str] = Field(None, description="New password (for WPA2-PSK/WEP)")
    hidden: Optional[bool] = Field(None, description="Toggle hidden SSID")
    channel: Optional[int] = Field(None, ge=1, le=14, description="New channel")


# === Response Models ===

class APInfo(BaseModel):
    id: str
    ssid: str
    security: SecurityType
    channel: int
    hidden: bool
    status: APStatus
    interface: str
    clients_connected: int = 0
    packets_sent: int = 0
    packets_received: int = 0
    created_at: str
    bssid: Optional[str] = None
    password: Optional[str] = None
    wep_key: Optional[str] = None


class AdapterInfo(BaseModel):
    id: str
    interface: str
    mode: AdapterMode
    phy: str
    mac_address: str
    in_use: bool = False
    used_by: Optional[str] = None


class ClientInfo(BaseModel):
    id: str
    mac_address: str
    ip_address: Optional[str] = None
    connected_to_ap: str
    ap_ssid: Optional[str] = None
    interface: str
    connected_at: str
    persona: Optional[str] = None
    device_type: Optional[str] = None
    hostname: Optional[str] = None
    is_running: bool = True
    connection_state: str = "starting"
    last_error: Optional[str] = None
    traffic_running: bool = False
    traffic_count: int = 0
    credentials: Optional[Dict[str, str]] = None
    eap_identity: Optional[str] = None  # EAP identity for WPA2-Enterprise clients


class SystemStatus(BaseModel):
    hwsim_loaded: bool
    total_radios: int
    aps_running: int
    adapters_available: int
    clients_connected: int
    uptime_seconds: int


class LogEntry(BaseModel):
    timestamp: str
    level: str
    source: str
    message: str


# === Attack Models ===

class AttackType(str, Enum):
    DEAUTH = "deauth"
    CAPTURE_HANDSHAKE = "capture_handshake"


class AttackStatus(str, Enum):
    STARTING = "starting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class LaunchAttackRequest(BaseModel):
    attack_type: AttackType = Field(..., description="Type of attack to launch")
    target_ap_id: str = Field(..., description="Target AP ID")
    adapter_id: str = Field(..., description="Adapter to use for the attack")
    duration: int = Field(default=60, ge=5, le=600, description="Attack duration in seconds")
    target_client: Optional[str] = Field(None, description="Target client MAC for deauth (optional)")


class AttackInfo(BaseModel):
    id: str
    attack_type: AttackType
    target_ap_id: str
    adapter_id: str
    status: AttackStatus
    started_at: str
    stopped_at: Optional[str] = None
    output_file: Optional[str] = None
    packets_sent: int = 0


# === Scenario Models ===

class Difficulty(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class ScenarioStatus(str, Enum):
    AVAILABLE = "available"
    DEPLOYING = "deploying"
    ACTIVE = "active"
    COMPLETED = "completed"


class ObjectiveStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class LaunchScenarioRequest(BaseModel):
    scenario_id: str


class CompleteObjectiveRequest(BaseModel):
    objective_id: str


class PersonaInfo(BaseModel):
    name: str
    role: str
    device_type: str
    hostname: str
    os: Optional[str] = None
    behavior: Optional[str] = None


class ObjectiveInfo(BaseModel):
    id: str
    title: str
    description: str
    points: int
    status: ObjectiveStatus
    hint: Optional[str] = None


class ScenarioSummary(BaseModel):
    id: str
    name: str
    description: str
    difficulty: Difficulty
    category: str
    points_total: int
    status: ScenarioStatus


class ScenarioInfo(BaseModel):
    id: str
    name: str
    description: str
    difficulty: Difficulty
    category: str
    points_total: int
    objectives: List[ObjectiveInfo]
    status: ScenarioStatus
    personas: List[PersonaInfo] = []
    attack_flow: Optional[List[str]] = None


class ScoreboardEntry(BaseModel):
    scenario_id: str
    scenario_name: str
    points_earned: int
    points_total: int
    completed: bool
    completed_at: Optional[str] = None


class ScoreboardSummary(BaseModel):
    total_points: int
    max_points: int
    scenarios_completed: int
    scenarios_total: int
    entries: List[ScoreboardEntry]
