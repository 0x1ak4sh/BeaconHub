"""
Client management API - list, inspect, control traffic, submit credentials.
"""

from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Request, HTTPException

from ..core.lab_manager import LabError
from ..core.events import event_bus
from ..models.schemas import (
    ClientInfo, ClientActionRequest, ClientCredentialsRequest,
    TrafficStartRequest, CreateClientRequest
)

router = APIRouter()


def _bot_to_info(bot, ap_ssid: Optional[str] = None) -> ClientInfo:
    return ClientInfo(
        id=bot.client_id,
        mac_address=bot.mac_address,
        ip_address=bot.ip_address,
        connected_to_ap=bot.ap_id,
        ap_ssid=ap_ssid,
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
        eap_identity=bot.eap_identity,
    )


@router.get("", response_model=List[ClientInfo])
async def list_all_clients(request: Request):
    """List all connected clients across all APs."""
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")

    bots = lab.clients.list_all()
    result = []
    for bot in bots:
        ap = lab.get_ap(bot.ap_id)
        result.append(_bot_to_info(bot, ap.ssid if ap else bot.ssid))
    return result


@router.post("", response_model=dict)
async def create_client(request: Request, body: CreateClientRequest):
    """
    Create a standalone client and connect it to any WiFi network.
    
    This allows creating clients that connect to:
    - An AP managed by this lab (specify ap_id or matching ssid)
    - An external/existing AP (specify ssid and password)
    
    For WPA2-Enterprise, provide eap_identity and eap_password.
    """
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")
    
    try:
        result = await lab.create_client(
            ssid=body.ssid,
            security=body.security.value,
            password=body.password,
            ap_id=body.ap_id,
            persona=body.persona,
            device_type=body.device_type,
            hostname=body.hostname,
            eap_identity=body.eap_identity,
            eap_password=body.eap_password,
        )
        return {"status": "ok", **result}
    except LabError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{client_id}", response_model=ClientInfo)
async def get_client(request: Request, client_id: str):
    """Get details of a specific client."""
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")

    bot = lab.clients.get_client(client_id)
    if not bot:
        raise HTTPException(status_code=404, detail=f"Client {client_id} not found")

    ap = lab.get_ap(bot.ap_id)
    return _bot_to_info(bot, ap.ssid if ap else bot.ssid)


@router.delete("/{client_id}")
async def delete_client(request: Request, client_id: str):
    """Disconnect and remove a client."""
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")
    
    try:
        await lab.disconnect_client(client_id)
        return {"status": "ok", "message": f"Client {client_id} disconnected"}
    except LabError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{client_id}/traffic/start")
async def start_traffic(request: Request, client_id: str, body: TrafficStartRequest):
    """Start continuous background traffic for a client.
    
    Set aggressive=true for high-volume traffic (useful for WEP IV collection).
    """
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")

    bot = lab.clients.get_client(client_id)
    if not bot:
        raise HTTPException(status_code=404, detail=f"Client {client_id} not found")

    success = lab.clients.start_traffic(client_id, interval=body.interval_seconds, aggressive=body.aggressive)
    if success:
        mode = "aggressive" if body.aggressive else "normal"
        await event_bus.publish("info", "client", f"Client {client_id} ({bot.persona}) traffic started ({mode} mode)")
        return {"status": "ok", "message": f"Traffic started ({mode} mode)", "aggressive": body.aggressive}
    return {"status": "error", "message": "Failed to start traffic"}


@router.post("/{client_id}/traffic/stop")
async def stop_traffic(request: Request, client_id: str):
    """Stop background traffic for a client."""
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")

    bot = lab.clients.get_client(client_id)
    if not bot:
        raise HTTPException(status_code=404, detail=f"Client {client_id} not found")

    lab.clients.stop_traffic(client_id)
    await event_bus.publish("info", "client", f"Client {client_id} ({bot.persona}) traffic stopped")
    return {"status": "ok", "message": "Traffic stopped"}


@router.post("/{client_id}/credentials")
async def set_credentials(request: Request, client_id: str, body: ClientCredentialsRequest):
    """
    Store credentials for a client (username/password can be false/fake).
    Optionally submits immediately and reconnects to regenerate WPA handshake.
    """
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")

    bot = lab.clients.get_client(client_id)
    if not bot:
        raise HTTPException(status_code=404, detail=f"Client {client_id} not found")

    # Store credentials
    lab.clients.set_credentials(client_id, body.username, body.password, body.target_url)
    await event_bus.publish(
        "info", "client",
        f"Client {client_id} ({bot.persona}) credentials set: user='{body.username}' url={body.target_url}"
    )

    result = {"status": "ok", "message": "Credentials saved"}

    if body.submit_and_reconnect:
        # Submit credentials via HTTP POST
        import asyncio
        submit_result = lab.clients.submit_credentials(client_id)
        await event_bus.publish(
            "warning", "client",
            f"Client {client_id} submitted credentials to {body.target_url} — PLAINTEXT IN CAPTURE"
        )
        # Reconnect to regenerate WPA handshake (offloaded to thread pool)
        reconnected = await asyncio.to_thread(lab.clients.reconnect, client_id)
        if reconnected:
            await event_bus.publish(
                "info", "client",
                f"Client {client_id} reconnected — new WPA handshake generated"
            )
        result["submitted"] = submit_result
        result["reconnected"] = reconnected

    return result


@router.post("/{client_id}/action")
async def client_action(request: Request, client_id: str, body: ClientActionRequest):
    """
    Trigger a one-off action on a client:
    reconnect | browse_url | submit_credentials | open_captive | dns_lookup
    """
    import subprocess
    import time

    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")

    bot = lab.clients.get_client(client_id)
    if not bot:
        raise HTTPException(status_code=404, detail=f"Client {client_id} not found")

    if body.action == "reconnect":
        await event_bus.publish("info", "client", f"Client {client_id} reconnecting...")
        import asyncio
        success = await asyncio.to_thread(lab.clients.reconnect, client_id)
        if success:
            await event_bus.publish("info", "client", f"Client {client_id} reconnected — WPA handshake generated")
            return {"status": "ok", "message": "Client reconnected — WPA handshake generated"}
        raise HTTPException(status_code=500, detail="Reconnect failed")

    elif body.action == "browse_url":
        url = body.url or "http://example.com"
        await event_bus.publish("info", "client", f"Client {client_id} browsing: {url}")
        try:
            result = subprocess.run(
                ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                 "--interface", bot.interface, "--max-time", "5", url],
                capture_output=True, text=True, timeout=10
            )
            code = result.stdout.strip()
            await event_bus.publish("info", "client", f"Client {client_id} got HTTP {code} from {url}")
            return {"status": "ok", "message": f"HTTP {code}", "http_code": code}
        except Exception as e:
            return {"status": "ok", "message": f"Traffic generated: {e}"}

    elif body.action == "submit_credentials":
        url = body.url or bot.credentials.get("url", "http://10.0.1.1/login") if bot.credentials else "http://10.0.1.1/login"
        username = body.username or (bot.credentials.get("username", "user") if bot.credentials else "user")
        password = body.password or (bot.credentials.get("password", "pass") if bot.credentials else "pass")

        if body.username or body.password:
            lab.clients.set_credentials(client_id, username, password, url)

        await event_bus.publish("info", "client", f"Client {client_id} submitting creds to {url}")
        try:
            subprocess.run(
                ["curl", "-s", "-o", "/dev/null", "--interface", bot.interface,
                 "--max-time", "5", "-X", "POST",
                 "-d", f"username={username}&password={password}", url],
                capture_output=True, text=True, timeout=10
            )
            await event_bus.publish(
                "warning", "client",
                f"Client {client_id} submitted '{username}:{password}' to {url} — PLAINTEXT IN CAPTURE"
            )
            return {"status": "ok", "message": "Credentials submitted — visible in packet capture"}
        except Exception as e:
            return {"status": "ok", "message": f"POST sent: {e}"}

    elif body.action == "open_captive":
        captive_urls = [
            "http://connectivitycheck.gstatic.com/generate_204",
            "http://captive.apple.com/hotspot-detect.html",
            "http://www.msftconnecttest.com/connecttest.txt",
        ]
        await event_bus.publish("info", "client", f"Client {client_id} checking captive portal...")
        for url in captive_urls:
            try:
                subprocess.run(
                    ["curl", "-s", "-o", "/dev/null", "--interface", bot.interface,
                     "--max-time", "3", url],
                    capture_output=True, timeout=5
                )
            except Exception:
                pass
            time.sleep(0.5)
        await event_bus.publish("info", "client", f"Client {client_id} captive portal check done")
        return {"status": "ok", "message": "Captive portal check triggered"}

    elif body.action == "dns_lookup":
        domain = body.url or "mail.google.com"
        await event_bus.publish("info", "client", f"Client {client_id} DNS: {domain}")
        try:
            subprocess.run(["nslookup", domain], capture_output=True, timeout=5)
            return {"status": "ok", "message": f"DNS query for {domain}"}
        except Exception:
            return {"status": "ok", "message": "DNS query sent"}

    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {body.action}")


@router.post("/probe-requests/start")
async def start_probe_requests(request: Request, interface: str = "wlan1"):
    """
    Start broadcasting probe requests for known networks.
    
    This simulates real client behavior where devices probe for networks
    they've previously connected to. Useful for:
    - Evil twin attack testing (create AP matching probed SSID)
    - Passive reconnaissance testing
    - Testing probe request capture with airodump-ng
    
    Probed SSIDs will appear in airodump-ng's "Probes" column.
    """
    from ..core.events import event_bus
    
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")
    
    if lab.clients.start_probe_requests(interface):
        await event_bus.publish(
            "info", "client",
            f"Started probe request broadcasting on {interface}"
        )
        return {
            "status": "ok",
            "message": f"Probe requests started on {interface}",
            "hint": "Use 'airodump-ng' to see probed SSIDs in the Probes column"
        }
    else:
        return {"status": "ok", "message": "Probe requests already running"}


@router.post("/probe-requests/stop")
async def stop_probe_requests(request: Request, interface: str = "wlan1"):
    """Stop probe request broadcasting on an interface."""
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")
    
    if lab.clients.stop_probe_requests(interface):
        return {"status": "ok", "message": f"Probe requests stopped on {interface}"}
    else:
        return {"status": "ok", "message": "No probe requests were running"}
