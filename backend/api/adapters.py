"""
Adapter management API endpoints.
"""

from typing import List
from fastapi import APIRouter, Request, HTTPException

from ..core.lab_manager import LabError
from ..models.schemas import AdapterInfo, AdapterMode, SetAdapterModeRequest

router = APIRouter()


@router.get("", response_model=List[AdapterInfo])
async def list_adapters(request: Request):
    """List all virtual wireless adapters."""
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")

    adapters = lab.list_adapters()
    result = []
    for adapter in adapters:
        result.append(AdapterInfo(
            id=adapter.id,
            interface=adapter.interface,
            mode=AdapterMode(adapter.mode),
            phy=adapter.phy,
            mac_address=adapter.mac_address,
            in_use=adapter.in_use,
            used_by=adapter.used_by,
        ))
    return result


@router.post("")
async def create_adapter(request: Request):
    """Create a new virtual wireless adapter."""
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")

    try:
        adapter = await lab.create_adapter()
        return {
            "status": "ok",
            "adapter": AdapterInfo(
                id=adapter.id,
                interface=adapter.interface,
                mode=AdapterMode(adapter.mode),
                phy=adapter.phy,
                mac_address=adapter.mac_address,
                in_use=adapter.in_use,
                used_by=adapter.used_by,
            )
        }
    except LabError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{adapter_id}")
async def delete_adapter(request: Request, adapter_id: str):
    """Delete a virtual wireless adapter."""
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")

    try:
        await lab.delete_adapter(adapter_id)
        return {"status": "ok", "message": f"Adapter {adapter_id} deleted"}
    except LabError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{adapter_id}", response_model=AdapterInfo)
async def get_adapter(request: Request, adapter_id: str):
    """Get details of a specific adapter."""
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")

    adapter = lab.get_adapter(adapter_id)
    if not adapter:
        raise HTTPException(status_code=404, detail=f"Adapter {adapter_id} not found")

    return AdapterInfo(
        id=adapter.id,
        interface=adapter.interface,
        mode=AdapterMode(adapter.mode),
        phy=adapter.phy,
        mac_address=adapter.mac_address,
        in_use=adapter.in_use,
        used_by=adapter.used_by,
    )


@router.post("/{adapter_id}/mode")
@router.put("/{adapter_id}/mode")
async def set_adapter_mode(request: Request, adapter_id: str, body: SetAdapterModeRequest):
    """Set the mode of an adapter (managed/monitor). Accepts both POST and PUT."""
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")

    try:
        await lab.set_adapter_mode(adapter_id, body.mode.value)
        adapter = lab.get_adapter(adapter_id)
        return {
            "status": "ok",
            "adapter_id": adapter_id,
            "mode": adapter.mode if adapter else body.mode.value,
            "message": f"Adapter set to {body.mode.value} mode"
        }
    except LabError as e:
        raise HTTPException(status_code=400, detail=str(e))
