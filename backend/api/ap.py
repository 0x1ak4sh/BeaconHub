"""
Access Point API endpoints.
"""

import time
from typing import List
from fastapi import APIRouter, Request, HTTPException

from ..core.lab_manager import LabError
from ..models.schemas import (
    CreateAPRequest, APInfo, SecurityType, APStatus, ClientInfo, UpdateAPRequest
)

router = APIRouter()


@router.post("", response_model=APInfo)
async def create_ap(request: Request, body: CreateAPRequest):
    """Create a new access point with optional auto-clients."""
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")

    # Determine password based on security type
    password = body.password
    if body.security == SecurityType.WEP and body.wep_key:
        password = body.wep_key

    # Validate password requirements based on security type
    if body.security == SecurityType.WPA2_PSK:
        if not password:
            raise HTTPException(
                status_code=400,
                detail="WPA2-PSK requires a password (8-63 characters)"
            )
        if len(password) < 8:
            raise HTTPException(
                status_code=400,
                detail="WPA2-PSK password must be at least 8 characters"
            )
    elif body.security == SecurityType.WEP:
        if not password:
            raise HTTPException(
                status_code=400,
                detail="WEP requires a key (5 or 13 ASCII chars, or 10 or 26 hex chars)"
            )
        if len(password) not in (5, 13, 10, 26):
            raise HTTPException(
                status_code=400,
                detail="WEP key must be 5 or 13 ASCII chars, or 10 or 26 hex chars"
            )

    try:
        ap = await lab.create_ap(
            ssid=body.ssid,
            security=body.security.value,
            password=password,
            channel=body.channel,
            hidden=body.hidden,
            num_clients=body.num_clients,
            enterprise_users=body.enterprise_users,
        )

        clients = lab.clients.get_clients_for_ap(ap.id)

        return APInfo(
            id=ap.id,
            ssid=ap.ssid,
            security=SecurityType(ap.security),
            channel=ap.channel,
            hidden=ap.hidden,
            status=APStatus.RUNNING,
            interface=ap.interface,
            clients_connected=len(clients),
            packets_sent=ap.packets_sent,
            packets_received=ap.packets_received,
            created_at=ap.created_at,
            bssid=ap.bssid,
            password=ap.password,
            wep_key=ap.password if ap.security == "wep" else None,
        )
    except LabError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=List[APInfo])
async def list_aps(request: Request):
    """List all access points."""
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")

    aps = lab.list_aps()
    result = []
    for ap in aps:
        clients = lab.clients.get_clients_for_ap(ap.id)
        is_running = lab.hostapd.is_running(ap.id)
        status = APStatus.RUNNING if is_running else APStatus.FAILED

        result.append(APInfo(
            id=ap.id,
            ssid=ap.ssid,
            security=SecurityType(ap.security),
            channel=ap.channel,
            hidden=ap.hidden,
            status=status,
            interface=ap.interface,
            clients_connected=len(clients),
            packets_sent=ap.packets_sent,
            packets_received=ap.packets_received,
            created_at=ap.created_at,
            bssid=ap.bssid,
            password=ap.password,
            wep_key=ap.password if ap.security == "wep" else None,
        ))
    return result


@router.get("/{ap_id}", response_model=APInfo)
async def get_ap(request: Request, ap_id: str):
    """Get details of a specific access point."""
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")

    ap = lab.get_ap(ap_id)
    if not ap:
        raise HTTPException(status_code=404, detail=f"AP {ap_id} not found")

    clients = lab.clients.get_clients_for_ap(ap.id)
    is_running = lab.hostapd.is_running(ap.id)

    return APInfo(
        id=ap.id,
        ssid=ap.ssid,
        security=SecurityType(ap.security),
        channel=ap.channel,
        hidden=ap.hidden,
        status=APStatus.RUNNING if is_running else APStatus.FAILED,
        interface=ap.interface,
        clients_connected=len(clients),
        packets_sent=ap.packets_sent,
        packets_received=ap.packets_received,
        created_at=ap.created_at,
        bssid=ap.bssid,
        password=ap.password,
        wep_key=ap.password if ap.security == "wep" else None,
    )


@router.patch("/{ap_id}", response_model=APInfo)
async def update_ap(request: Request, ap_id: str, body: UpdateAPRequest):
    """
    Update an access point's settings.
    
    This will restart the AP with new settings and reconnect all clients.
    Only password, hidden, and channel can be changed. Security type cannot be changed.
    """
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")

    ap = lab.get_ap(ap_id)
    if not ap:
        raise HTTPException(status_code=404, detail=f"AP {ap_id} not found")

    # Validate password if provided
    if body.password is not None:
        if ap.security == "wpa2-psk":
            if len(body.password) < 8:
                raise HTTPException(status_code=400, detail="WPA2-PSK password must be at least 8 characters")
        elif ap.security == "wep":
            if len(body.password) not in (5, 13, 10, 26):
                raise HTTPException(status_code=400, detail="WEP key must be 5/13 ASCII chars or 10/26 hex digits")
        elif ap.security == "open":
            raise HTTPException(status_code=400, detail="Cannot set password on open network")

    try:
        updated_ap = await lab.update_ap(
            ap_id=ap_id,
            password=body.password,
            hidden=body.hidden,
            channel=body.channel
        )
        
        clients = lab.clients.get_clients_for_ap(updated_ap.id)
        is_running = lab.hostapd.is_running(updated_ap.id)

        return APInfo(
            id=updated_ap.id,
            ssid=updated_ap.ssid,
            security=SecurityType(updated_ap.security),
            channel=updated_ap.channel,
            hidden=updated_ap.hidden,
            status=APStatus.RUNNING if is_running else APStatus.FAILED,
            interface=updated_ap.interface,
            clients_connected=len(clients),
            packets_sent=updated_ap.packets_sent,
            packets_received=updated_ap.packets_received,
            created_at=updated_ap.created_at,
            bssid=updated_ap.bssid,
            password=updated_ap.password,
            wep_key=updated_ap.password if updated_ap.security == "wep" else None,
        )
    except LabError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{ap_id}")
async def stop_ap(request: Request, ap_id: str):
    """Stop and remove an access point."""
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")

    try:
        await lab.stop_ap(ap_id)
        return {"status": "ok", "message": f"AP {ap_id} stopped"}
    except LabError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{ap_id}/clients", response_model=List[ClientInfo])
async def get_ap_clients(request: Request, ap_id: str):
    """Get clients connected to an AP."""
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")

    ap = lab.get_ap(ap_id)
    if not ap:
        raise HTTPException(status_code=404, detail=f"AP {ap_id} not found")

    bots = lab.clients.get_clients_for_ap(ap_id)
    result = []
    for bot in bots:
        result.append(ClientInfo(
            id=bot.client_id,
            mac_address=bot.mac_address,
            ip_address=bot.ip_address,
            connected_to_ap=bot.ap_id,
            ap_ssid=ap.ssid,
            interface=bot.interface,
            connected_at=str(bot.connected_at),
            persona=bot.persona,
            device_type=bot.device_type,
            hostname=bot.hostname,
            is_running=bot.is_running,
            connection_state=bot.connection_state,
            last_error=bot.last_error,
            traffic_running=bot.traffic_running,
            traffic_count=bot.traffic_count,
            credentials=bot.credentials,
        ))
    return result


@router.get("/{ap_id}/log")
async def get_ap_log(request: Request, ap_id: str):
    """Get hostapd log for an AP."""
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")

    log = lab.hostapd.get_log(ap_id)
    return {"ap_id": ap_id, "log": log}


@router.post("/{ap_id}/flood-traffic")
async def flood_traffic(request: Request, ap_id: str):
    """
    Start aggressive traffic on ALL clients connected to this AP.
    
    Useful for:
    - WEP cracking: Generates high volume of encrypted packets for IV collection
    - WPA handshake: More traffic = more chances for handshake during deauth
    
    For WEP APs: Launches aireplay-ng -3 (ARP replay) on each client + airodump-ng
    capture. This generates ~500+ unique IVs/second via ARP packet replay.
    """
    from ..core.events import event_bus
    
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")

    ap = lab.get_ap(ap_id)
    if not ap:
        raise HTTPException(status_code=404, detail=f"AP {ap_id} not found")

    clients = lab.clients.get_clients_for_ap(ap_id)
    if not clients:
        raise HTTPException(status_code=400, detail="No clients connected to this AP")

    if ap.security == "wep":
        # Use ARP replay for WEP — much faster IV generation
        try:
            result = lab.start_wep_attack(ap_id, ap.channel)
            iv_count = lab.get_wep_iv_count(ap_id)
            await event_bus.publish(
                "warning", "traffic",
                f"WEP ARP replay started on AP '{ap.ssid}' with {len(result['replay_ids'])} clients"
            )
            return {
                "status": "ok",
                "message": f"WEP ARP replay active on {len(result['replay_ids'])} client(s)",
                "ap_ssid": ap.ssid,
                "security": "wep",
                "clients_flooding": len(result['replay_ids']),
                "capture_id": result["capture_id"],
                "replay_ids": result["replay_ids"],
                "iv_count": iv_count,
                "hint": "ARP replay generating ~500 IVs/sec. Check /api/ap/{ap_id}/wep-status for IV progress."
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        # Non-WEP: use standard aggressive traffic
        started = 0
        for bot in clients:
            lab.clients.stop_traffic(bot.client_id)
            if lab.clients.start_traffic(bot.client_id, interval=1, aggressive=True):
                started += 1

        await event_bus.publish(
            "warning", "traffic",
            f"Aggressive traffic flood started on {started} clients for AP '{ap.ssid}'"
        )

        return {
            "status": "ok",
            "message": f"Aggressive traffic started on {started} client(s)",
            "ap_ssid": ap.ssid,
            "security": ap.security,
            "clients_flooding": started,
        }


@router.get("/{ap_id}/wep-status")
async def wep_status(request: Request, ap_id: str):
    """Get WEP IV generation status: IV count, replay uptime, estimated time to 5000 IVs."""
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")

    ap = lab.get_ap(ap_id)
    if not ap:
        raise HTTPException(status_code=404, detail=f"AP {ap_id} not found")

    wep = lab._wep_attacks.get(ap_id)
    if not wep:
        return {
            "status": "idle",
            "ap_id": ap_id,
            "ssid": ap.ssid,
            "iv_count": 0,
            "message": "No WEP attack running. POST /api/ap/{ap_id}/flood-traffic to start."
        }

    iv_count = lab.get_wep_iv_count(ap_id)
    capture_attack = lab.aircrack.get_attack(wep["capture_id"])

    # Estimate time to 5000 IVs
    elapsed = time.time() - capture_attack.started_at if capture_attack else 0
    iv_rate = iv_count / elapsed if elapsed > 1 else 0
    remaining = max(0, 5000 - iv_count)
    eta_sec = remaining / iv_rate if iv_rate > 0 else 0

    replay_status = []
    for rid in wep.get("replay_ids", []):
        a = lab.aircrack.get_attack(rid)
        replay_status.append({
            "id": rid,
            "running": a.is_running if a else False,
            "uptime_seconds": int(time.time() - a.started_at) if a else 0,
        })

    return {
        "status": "running" if capture_attack and capture_attack.is_running else "stopped",
        "ap_id": ap_id,
        "ssid": ap.ssid,
        "iv_count": iv_count,
        "iv_rate_per_sec": round(iv_rate, 1),
        "eta_seconds": int(eta_sec),
        "ivs_needed": remaining,
        "elapsed_seconds": int(elapsed),
        "capture_file": capture_attack.output_file if capture_attack else None,
        "replays": replay_status,
    }


@router.post("/{ap_id}/stop-flood")
async def stop_flood(request: Request, ap_id: str):
    """Stop aggressive traffic flood on all clients of this AP."""
    from ..core.events import event_bus
    
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")

    ap = lab.get_ap(ap_id)
    if not ap:
        raise HTTPException(status_code=404, detail=f"AP {ap_id} not found")

    # Stop WEP attack if running
    iv_count = lab.get_wep_iv_count(ap_id)
    lab.stop_wep_attack(ap_id)

    # Also stop regular traffic
    clients = lab.clients.get_clients_for_ap(ap_id)
    stopped = 0
    for bot in clients:
        if lab.clients.stop_traffic(bot.client_id):
            stopped += 1

    message = f"Traffic flood stopped on {stopped} client(s)"
    if iv_count > 0:
        message += f" — {iv_count} WEP IVs collected"

    await event_bus.publish("info", "traffic", message)

    return {
        "status": "ok",
        "message": message,
        "iv_count": iv_count,
        "clients_stopped": stopped,
    }


@router.post("/{ap_id}/beacon")
async def send_beacon(request: Request, ap_id: str):
    """
    Force beacon re-broadcast by briefly reloading hostapd config.
    
    Useful for:
    - Hidden SSID networks: Forces response to probe requests
    - Refreshing beacon frames for scanner visibility
    - Verifying AP is still broadcasting correctly
    """
    from ..core.events import event_bus
    import asyncio
    
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")

    ap = lab.get_ap(ap_id)
    if not ap:
        raise HTTPException(status_code=404, detail=f"AP {ap_id} not found")

    # Send HUP signal to hostapd to reload config (triggers beacon burst)
    try:
        lab.hostapd.reload(ap_id)
        await event_bus.publish("info", "ap", f"Beacon refresh triggered for AP '{ap.ssid}'")
        return {
            "status": "ok",
            "message": f"Beacon refresh triggered for '{ap.ssid}'",
            "bssid": ap.bssid,
            "ssid": ap.ssid,
            "channel": ap.channel
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to refresh beacons: {str(e)}")
