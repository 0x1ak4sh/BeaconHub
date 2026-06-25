"""
RADIUS server management API endpoints.
"""

from typing import List
from pydantic import BaseModel, Field
from fastapi import APIRouter, Request, HTTPException

from ..core.events import event_bus

router = APIRouter()


class RadiusUserRequest(BaseModel):
    username: str = Field(..., min_length=1, description="Username/identity for EAP")
    password: str = Field(..., min_length=1, description="Password for authentication")
    groups: List[str] = Field(default=[], description="Optional user groups")


class RadiusUserInfo(BaseModel):
    username: str
    groups: List[str] = []


@router.get("/status")
async def get_radius_status(request: Request):
    """Get RADIUS server status."""
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")
    
    return {
        "running": lab.radius.is_running(),
        "users_count": len(lab.radius.list_users())
    }


@router.post("/start")
async def start_radius(request: Request):
    """Start the RADIUS server."""
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")
    
    if lab.radius.is_running():
        return {"status": "ok", "message": "RADIUS server already running"}
    
    success = lab.radius.start()
    if success:
        lab._radius_running = True
        await event_bus.publish("info", "radius", "RADIUS server started")
        return {"status": "ok", "message": "RADIUS server started"}
    else:
        raise HTTPException(status_code=500, detail="Failed to start RADIUS server")


@router.post("/stop")
async def stop_radius(request: Request):
    """Stop the RADIUS server."""
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")
    
    lab.radius.stop()
    lab._radius_running = False
    await event_bus.publish("info", "radius", "RADIUS server stopped")
    return {"status": "ok", "message": "RADIUS server stopped"}


@router.get("/users", response_model=List[RadiusUserInfo])
async def list_radius_users(request: Request):
    """List all RADIUS users."""
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")
    
    users = lab.radius.list_users()
    return [RadiusUserInfo(**u) for u in users]


@router.post("/users")
async def add_radius_user(request: Request, body: RadiusUserRequest):
    """Add a RADIUS user for WPA2-Enterprise authentication."""
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")
    
    lab.radius.add_user(body.username, body.password, body.groups)
    await event_bus.publish("info", "radius", f"Added RADIUS user: {body.username}")
    return {"status": "ok", "message": f"User {body.username} added"}


@router.delete("/users/{username}")
async def remove_radius_user(request: Request, username: str):
    """Remove a RADIUS user."""
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")
    
    lab.radius.remove_user(username)
    await event_bus.publish("info", "radius", f"Removed RADIUS user: {username}")
    return {"status": "ok", "message": f"User {username} removed"}


@router.post("/test")
async def test_radius_auth(request: Request, body: RadiusUserRequest):
    """Test authentication against the RADIUS server."""
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")
    
    if not lab.radius.is_running():
        raise HTTPException(status_code=400, detail="RADIUS server is not running")
    
    success = lab.radius.test_auth(body.username, body.password)
    if success:
        return {"status": "ok", "message": "Authentication successful", "result": "Access-Accept"}
    else:
        return {"status": "ok", "message": "Authentication failed", "result": "Access-Reject"}
