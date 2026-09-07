from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response, status
from sqlalchemy import select

from app.api.dependencies import SessionDep
from app.core.config import settings
from app.models import User, UserSettings
from app.schemas.api import SettingsUpdate
from app.services.analysis import create_analysis_run, run_analysis
from app.services.cloud_health import cloud_health
from app.services.queries import data_diagnostics, system_status

router = APIRouter()


@router.get("/system/health")
async def get_cloud_health(session: SessionDep, response: Response) -> dict[str, Any]:
    result = await cloud_health(session)
    if result["status"] == "ERROR":
        response.status_code = 503
    return result


@router.get("/system/status")
@router.get("/providers/status")
async def get_system_status(session: SessionDep) -> dict[str, Any]:
    return await system_status(session)


@router.post("/analysis/run", status_code=status.HTTP_202_ACCEPTED)
@router.post("/admin/sync", status_code=status.HTTP_202_ACCEPTED)
@router.post("/admin/sync-real-data", status_code=status.HTTP_202_ACCEPTED)
async def start_analysis(background_tasks: BackgroundTasks, response: Response) -> dict[str, Any]:
    try:
        run, created = await create_analysis_run("MANUAL")
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail="Job queue busy; retry shortly") from exc
    if not created:
        response.status_code = status.HTTP_200_OK
        return {"id": run.id, "status": run.status, "message": "An analysis run is already active."}
    if settings.environment != "production":
        background_tasks.add_task(run_analysis, run.id)
    return {"id": run.id, "status": run.status, "message": "Analysis queued."}


@router.get("/system/data-diagnostics")
async def get_data_diagnostics(session: SessionDep) -> dict[str, Any]:
    return await data_diagnostics(session)


@router.get("/settings")
async def get_user_settings(session: SessionDep) -> dict[str, Any]:
    item = await session.scalar(select(UserSettings))
    if item is None:
        return SettingsUpdate().model_dump()
    return {
        "min_odds": item.min_odds,
        "min_edge": item.min_edge,
        "min_ev": item.min_ev,
        "min_confidence": item.min_confidence,
        "timezone": item.timezone,
        "odds_format": item.odds_format,
        "sports_enabled": item.sports_enabled,
        "notifications_enabled": item.notifications_enabled,
        "auto_refresh_minutes": item.auto_refresh_minutes,
    }


@router.post("/settings")
async def update_user_settings(payload: SettingsUpdate, session: SessionDep) -> dict[str, Any]:
    user = await session.scalar(select(User))
    if user is None:
        user = User(email="local@sports-value-engine.invalid", display_name="Local Analyst")
        session.add(user)
        await session.flush()
    item = await session.scalar(select(UserSettings).where(UserSettings.user_id == user.id))
    if item is None:
        item = UserSettings(user_id=user.id)
        session.add(item)
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    await session.commit()
    return payload.model_dump()
