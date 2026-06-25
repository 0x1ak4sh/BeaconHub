"""
Scenario API endpoints.
"""

from typing import List
from fastapi import APIRouter, Request, HTTPException

from ..core.scenarios import ScenarioManager, SCENARIOS
from ..models.schemas import (
    ScenarioInfo, ScenarioSummary, ObjectiveInfo, ObjectiveStatus,
    PersonaInfo, Difficulty, ScenarioStatus, LaunchScenarioRequest,
    CompleteObjectiveRequest, ScoreboardSummary, ScoreboardEntry
)

router = APIRouter()


def _get_scenario_manager(request: Request) -> ScenarioManager:
    if not hasattr(request.app.state, 'scenario_manager'):
        request.app.state.scenario_manager = ScenarioManager()
    return request.app.state.scenario_manager


@router.get("", response_model=List[ScenarioSummary])
async def list_scenarios(request: Request):
    """List all available scenarios."""
    mgr = _get_scenario_manager(request)
    result = []
    for scenario in mgr.get_all_scenarios():
        result.append(ScenarioSummary(
            id=scenario.id,
            name=scenario.name,
            description=scenario.description,
            difficulty=Difficulty(scenario.difficulty),
            category=scenario.category,
            points_total=scenario.points_total,
            status=ScenarioStatus(mgr.get_scenario_status(scenario.id)),
        ))
    return result


@router.get("/scoreboard", response_model=ScoreboardSummary)
async def get_scoreboard(request: Request):
    """Get overall scoreboard."""
    mgr = _get_scenario_manager(request)
    data = mgr.get_scoreboard()
    return ScoreboardSummary(
        total_points=data["total_points"],
        max_points=data["max_points"],
        scenarios_completed=data["scenarios_completed"],
        scenarios_total=data["scenarios_total"],
        entries=[ScoreboardEntry(**e) for e in data["entries"]],
    )


@router.get("/{scenario_id}", response_model=ScenarioInfo)
async def get_scenario(request: Request, scenario_id: str):
    """Get full scenario details including objectives and personas."""
    mgr = _get_scenario_manager(request)
    scenario = mgr.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    obj_states = mgr.get_objective_states(scenario_id)

    objectives = []
    for obj in scenario.objectives:
        status = obj_states.get(obj.id, "pending")
        objectives.append(ObjectiveInfo(
            id=obj.id,
            title=obj.title,
            description=obj.description,
            points=obj.points,
            status=ObjectiveStatus(status),
            hint=obj.hint,
        ))

    personas = [
        PersonaInfo(
            name=p.name, role=p.role, device_type=p.device_type,
            hostname=p.hostname, os=p.os, behavior=p.behavior
        ) for p in scenario.personas
    ]

    return ScenarioInfo(
        id=scenario.id,
        name=scenario.name,
        description=scenario.description,
        difficulty=Difficulty(scenario.difficulty),
        category=scenario.category,
        points_total=scenario.points_total,
        objectives=objectives,
        status=ScenarioStatus(mgr.get_scenario_status(scenario_id)),
        personas=personas,
        attack_flow=scenario.attack_flow,
    )


@router.post("/{scenario_id}/deploy")
async def deploy_scenario(request: Request, scenario_id: str):
    """Deploy a scenario - auto-creates the environment."""
    mgr = _get_scenario_manager(request)
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")

    try:
        state = await mgr.deploy_scenario(scenario_id, lab)
        return {"status": "ok", "message": f"Scenario deployed", "state": state}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{scenario_id}/stop")
async def stop_scenario(request: Request, scenario_id: str):
    """Stop and tear down a scenario."""
    mgr = _get_scenario_manager(request)
    lab = request.app.state.lab_manager
    if not lab:
        raise HTTPException(status_code=503, detail="Lab not initialized")

    success = await mgr.stop_scenario(scenario_id, lab)
    if not success:
        raise HTTPException(status_code=400, detail="Scenario not active")
    return {"status": "ok", "message": "Scenario stopped"}


@router.post("/{scenario_id}/objectives/{objective_id}/complete")
async def complete_objective(request: Request, scenario_id: str, objective_id: str):
    """Mark an objective as completed."""
    mgr = _get_scenario_manager(request)

    success = await mgr.complete_objective(scenario_id, objective_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot complete objective")
    return {"status": "ok", "message": "Objective completed"}
