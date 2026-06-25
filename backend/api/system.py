"""
System API endpoints - health, status, reset.
"""

from fastapi import APIRouter, Request, HTTPException

from ..core.events import event_bus
from ..models.schemas import SystemStatus

router = APIRouter()


@router.get("/health")
async def health_check(request: Request):
    """Health check endpoint."""
    lab = request.app.state.lab_manager
    return {
        "status": "ok",
        "initialized": lab._initialized if lab else False,
    }


@router.get("/status", response_model=SystemStatus)
async def get_system_status(request: Request):
    """Get overall system status."""
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")

    status = lab.get_system_status()
    # Only pass fields that SystemStatus expects
    return SystemStatus(
        hwsim_loaded=status.get("hwsim_loaded", False),
        total_radios=status.get("total_radios", 0),
        aps_running=status.get("aps_running", 0),
        adapters_available=status.get("adapters_available", 0),
        clients_connected=status.get("clients_connected", 0),
        uptime_seconds=status.get("uptime_seconds", 0),
    )


@router.post("/reset")
async def reset_lab(request: Request):
    """Reset the entire lab."""
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")

    await lab.reset_lab()
    return {"status": "ok", "message": "Lab reset successfully"}


@router.get("/logs")
async def get_logs(count: int = 50):
    """Get recent log entries."""
    if count > 500:
        count = 500
    entries = event_bus.get_history(count)
    return {"logs": entries}
