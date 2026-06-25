from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Request, HTTPException

from ..core.capture import CaptureManager

router = APIRouter()

capture_manager = CaptureManager()


class StartCaptureRequest(BaseModel):
    interface: str = Field(..., description="Interface to capture packets on")
    client_id: Optional[str] = Field(None, description="Client ID for display purposes")


@router.post("/start")
async def start_capture(request: Request, body: StartCaptureRequest):
    """Start packet capture on a specific interface (e.g. client0)."""
    capture_id = capture_manager.start_capture(body.interface)
    if not capture_id:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to start capture on {body.interface}. Is tshark/tcpdump installed?"
        )
    return {
        "status": "ok",
        "capture_id": capture_id,
        "interface": body.interface,
        "message": f"Packet capture started on {body.interface}",
        "hint": "Captured traffic will appear in the client detail view"
    }


@router.post("/{capture_id}/stop")
async def stop_capture(capture_id: str):
    """Stop a running packet capture."""
    cap = capture_manager.get_capture(capture_id)
    if not cap:
        raise HTTPException(status_code=404, detail="Capture not found")
    capture_manager.stop_capture(capture_id)
    data = cap.get_captured_data()
    return {
        "status": "ok",
        "message": "Capture stopped",
        "data": data,
        "credentials": cap.detect_credentials(),
    }


@router.get("/{capture_id}")
async def get_capture(capture_id: str):
    """Get capture data and detected credentials."""
    cap = capture_manager.get_capture(capture_id)
    if not cap:
        raise HTTPException(status_code=404, detail="Capture not found")
    return {
        "status": "ok",
        "data": cap.get_captured_data(),
        "credentials": cap.detect_credentials(),
    }


@router.get("")
async def list_captures():
    """List all active/stopped captures."""
    return {"captures": capture_manager.list_captures()}


@router.get("/interface/{interface}")
async def get_capture_for_interface(interface: str):
    """Get capture data for a specific interface."""
    cap = capture_manager.get_capture_for_interface(interface)
    if not cap:
        raise HTTPException(status_code=404, detail=f"No capture found for interface {interface}")
    return {
        "status": "ok",
        "data": cap.get_captured_data(),
        "credentials": cap.detect_credentials(),
    }
