"""
Attack management API endpoints.
"""

import os
from fastapi import APIRouter, Request, HTTPException

from ..core.lab_manager import LabError
from ..models.schemas import (
    LaunchAttackRequest, AttackType, AttackStatus
)

router = APIRouter()


@router.get("/types")
async def list_attack_types():
    """List available attack types."""
    return [
        {
            "id": "deauth",
            "name": "Deauthentication",
            "description": "Send deauth frames to disconnect clients from the target AP",
            "needs_monitor": True,
            "needs_client": False,
        },
        {
            "id": "capture_handshake",
            "name": "Handshake Capture",
            "description": "Capture WPA 4-way handshake with airodump-ng. Combine with deauth for best results.",
            "needs_monitor": True,
            "needs_client": False,
        },
        {
            "id": "pmkid_capture",
            "name": "PMKID Capture",
            "description": "Capture PMKID from AP using hcxdumptool. No client required!",
            "needs_monitor": True,
            "needs_client": False,
        },
    ]


# ── Wordlists & Captures (static routes, must be before /{attack_id}) ──

@router.get("/wordlists/list")
async def list_wordlists(request: Request):
    """List all available wordlist files."""
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")

    return {"wordlists": lab.list_wordlists()}


@router.get("/captures/list")
async def list_captures(request: Request):
    """List all capture files available for cracking."""
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")

    return {"captures": lab.aircrack.list_captures()}


@router.post("")
async def launch_attack(request: Request, body: LaunchAttackRequest):
    """Launch an attack against a target AP."""
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")

    try:
        # Handle cracking separately
        if body.attack_type == AttackType.CRACK:
            if not body.cap_file:
                raise HTTPException(status_code=400, detail="cap_file is required for cracking")
            if not body.wordlist:
                raise HTTPException(status_code=400, detail="wordlist is required for cracking")

            record = await lab.crack_capture(
                attack_id="",
                cap_file=body.cap_file,
                wordlist=body.wordlist,
                target_ap_id=body.target_ap_id,
                adapter_id=body.adapter_id or "",
            )
        else:
            if not body.adapter_id:
                raise HTTPException(status_code=400, detail="adapter_id is required for this attack type")

            record = await lab.launch_attack(
                attack_type=body.attack_type.value,
                target_ap_id=body.target_ap_id,
                adapter_id=body.adapter_id,
                duration=body.duration,
                target_client=body.target_client,
            )

        return _record_to_info(record)
    except LabError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("")
async def list_attacks(request: Request):
    """List all attacks (running and completed)."""
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")

    result = []
    for record in lab.list_attacks():
        result.append(_record_to_info_dict(record))
    return result


@router.get("/{attack_id}")
async def get_attack(request: Request, attack_id: str):
    """Get details of a specific attack."""
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")

    record = lab.get_attack(attack_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Attack {attack_id} not found")

    # Check live status
    attack_proc = lab.aircrack.get_attack(attack_id)
    if attack_proc and not attack_proc.is_running and record.status == "running":
        record.status = "completed"

    # If it's a crack attempt, get the result
    result = None
    if record.attack_type == "crack":
        crack_result = lab.get_crack_result(attack_id)
        result = crack_result.get("message", "")
        if crack_result.get("status") == "cracked":
            record.status = "cracked"
            result = crack_result.get("key", "")
        elif crack_result.get("status") == "failed":
            record.status = "failed"

    return _record_to_info_dict(record, result)


@router.post("/{attack_id}/stop")
async def stop_attack(request: Request, attack_id: str):
    """Stop a running attack."""
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")

    try:
        await lab.stop_attack(attack_id)
        return {"status": "ok", "message": f"Attack {attack_id} stopped"}
    except LabError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{attack_id}")
async def delete_attack(request: Request, attack_id: str):
    """Stop and delete an attack record."""
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")

    try:
        await lab.stop_attack(attack_id)
        lab.remove_attack(attack_id)
        return {"status": "ok", "message": f"Attack {attack_id} stopped and deleted"}
    except LabError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{attack_id}/log")
async def get_attack_log(request: Request, attack_id: str):
    """Get the log output of an attack."""
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")

    log = lab.aircrack.get_attack_log(attack_id)
    return {"attack_id": attack_id, "log": log}


@router.get("/{attack_id}/check-handshake")
async def check_handshake(request: Request, attack_id: str):
    """Check if a capture contains a valid WPA handshake."""
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")

    record = lab.get_attack(attack_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Attack {attack_id} not found")

    if record.attack_type not in ("capture_handshake", "pmkid_capture"):
        raise HTTPException(
            status_code=400,
            detail="Handshake check only available for capture attacks"
        )

    if not record.output_file:
        return {"has_handshake": False, "message": "No capture file available"}

    if not os.path.exists(record.output_file):
        return {"has_handshake": False, "message": "Capture file not found on disk"}

    if record.attack_type == "pmkid_capture":
        has_pmkid = lab.aircrack.check_pmkid(record.output_file)
        return {
            "has_handshake": has_pmkid,
            "has_pmkid": has_pmkid,
            "capture_file": record.output_file,
            "message": "PMKID found!" if has_pmkid else "No PMKID captured yet"
        }

    has_hs = lab.aircrack.check_handshake(record.output_file)
    return {
        "has_handshake": has_hs,
        "capture_file": record.output_file,
        "message": "Handshake found!" if has_hs else "No handshake captured yet"
    }


@router.get("/{attack_id}/crack-status")
async def get_crack_status(request: Request, attack_id: str):
    """Get cracking progress (keys tested, key found, etc.)."""
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")

    record = lab.get_attack(attack_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Attack {attack_id} not found")

    if record.attack_type != "crack":
        raise HTTPException(status_code=400, detail="Not a cracking attack")

    result = lab.get_crack_result(attack_id)
    return result


# ── Helpers ────────────────────────────────────────────────────────────

def _record_to_info_dict(record, result=None):
    """Convert an AttackRecord to a dict for API response."""
    try:
        attack_type = AttackType(record.attack_type)
    except ValueError:
        attack_type = record.attack_type  # Pass through if not in enum

    try:
        status = AttackStatus(record.status)
    except ValueError:
        status = record.status

    d = {
        "id": record.id,
        "attack_type": attack_type if isinstance(attack_type, (AttackType, str)) else str(attack_type),
        "target_ap_id": record.target_ap_id,
        "adapter_id": record.adapter_id,
        "status": status if isinstance(status, (AttackStatus, str)) else str(status),
        "started_at": record.started_at,
        "stopped_at": record.stopped_at,
        "output_file": record.output_file,
        "packets_sent": record.packets_sent,
        "result": result or record.result,
    }
    return d


def _record_to_info(record, result=None):
    """Convert an AttackRecord to an AttackInfo response (flexible)."""
    d = _record_to_info_dict(record, result)
    # Return as dict since attack_type/status may be strings not enum values
    return d
