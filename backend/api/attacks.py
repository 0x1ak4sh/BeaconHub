"""
Attack management API endpoints.
"""

from typing import List
from fastapi import APIRouter, Request, HTTPException

from ..core.lab_manager import LabError
from ..models.schemas import (
    LaunchAttackRequest, AttackInfo, AttackType, AttackStatus
)

router = APIRouter()


@router.get("/types")
async def list_attack_types():
    """List available attack types."""
    return [
        {"id": "deauth", "name": "Deauthentication", "description": "Disconnect clients from AP"},
        {"id": "capture_handshake", "name": "Handshake Capture", "description": "Capture WPA 4-way handshake"},
    ]


@router.post("", response_model=AttackInfo)
async def launch_attack(request: Request, body: LaunchAttackRequest):
    """Launch an attack against a target AP."""
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")

    try:
        record = await lab.launch_attack(
            attack_type=body.attack_type.value,
            target_ap_id=body.target_ap_id,
            adapter_id=body.adapter_id,
            duration=body.duration,
            target_client=body.target_client,
        )

        return AttackInfo(
            id=record.id,
            attack_type=AttackType(record.attack_type),
            target_ap_id=record.target_ap_id,
            adapter_id=record.adapter_id,
            status=AttackStatus(record.status),
            started_at=record.started_at,
            stopped_at=record.stopped_at,
            output_file=record.output_file,
            packets_sent=record.packets_sent,
        )
    except LabError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=List[AttackInfo])
async def list_attacks(request: Request):
    """List all attacks (running and completed)."""
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")

    attacks = lab.list_attacks()
    result = []
    for record in attacks:
        result.append(AttackInfo(
            id=record.id,
            attack_type=AttackType(record.attack_type),
            target_ap_id=record.target_ap_id,
            adapter_id=record.adapter_id,
            status=AttackStatus(record.status),
            started_at=record.started_at,
            stopped_at=record.stopped_at,
            output_file=record.output_file,
            packets_sent=record.packets_sent,
        ))
    return result


@router.get("/{attack_id}", response_model=AttackInfo)
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

    return AttackInfo(
        id=record.id,
        attack_type=AttackType(record.attack_type),
        target_ap_id=record.target_ap_id,
        adapter_id=record.adapter_id,
        status=AttackStatus(record.status),
        started_at=record.started_at,
        stopped_at=record.stopped_at,
        output_file=record.output_file,
        packets_sent=record.packets_sent,
    )


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
    """Stop and delete an attack (alias for stop)."""
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")

    try:
        await lab.stop_attack(attack_id)
        return {"status": "ok", "message": f"Attack {attack_id} stopped"}
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

    if record.attack_type != "capture_handshake":
        raise HTTPException(
            status_code=400,
            detail="Handshake check only available for capture attacks"
        )

    if not record.output_file:
        return {"has_handshake": False, "message": "No capture file available"}

    has_handshake = lab.aircrack.check_handshake(record.output_file)
    return {
        "has_handshake": has_handshake,
        "capture_file": record.output_file,
        "message": "Handshake found!" if has_handshake else "No handshake captured yet"
    }
