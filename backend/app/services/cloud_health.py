from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AnalysisRun, AnalysisRunStep
from app.models.system import WorkerHeartbeat
from app.services.queries import data_diagnostics, system_status


async def cloud_health(session: AsyncSession) -> dict[str, Any]:
    await session.execute(text("SELECT 1"))
    diagnostic = await data_diagnostics(session)
    system = await system_status(session)
    pulse = await session.get(WorkerHeartbeat, "scheduler")
    age = None
    if pulse:
        observed = (
            pulse.last_seen.replace(tzinfo=UTC)
            if pulse.last_seen.tzinfo is None
            else pulse.last_seen
        )
        age = (datetime.now(UTC) - observed).total_seconds()
    timestamps: dict[str, str | None] = {}
    for name, steps in {
        "last_sync": ["SYNC_ODDS", "SYNC_FOOTBALL", "SYNC_TENNIS"],
        "last_odds_sync": ["SYNC_ODDS"],
        "last_settlement": ["SETTLEMENT"],
    }.items():
        query = select(AnalysisRunStep.finished_at)
        if name == "last_settlement":
            query = query.where(AnalysisRunStep.records_processed > 0)
        stamp = await session.scalar(
            query.where(
                AnalysisRunStep.step_name.in_(steps), AnalysisRunStep.status == "COMPLETED"
            ).order_by(desc(AnalysisRunStep.finished_at))
        )
        timestamps[name] = stamp.isoformat() if stamp else None
    analysis = await session.scalar(
        select(AnalysisRun.finished_at)
        .where(
            AnalysisRun.job_type == "daily_analysis",
            AnalysisRun.status.in_(["COMPLETED", "PARTIAL"]),
        )
        .order_by(desc(AnalysisRun.finished_at))
    )
    timestamps["last_analysis"] = analysis.isoformat() if analysis else None
    configured = [p for p in system["providers"] if p["configured"]]
    worker_online = age is not None and 0 <= age < 90
    bot = (
        "SETUP_REQUIRED"
        if not configured
        else "ONLINE"
        if worker_online and all(p["status"] == "ONLINE" for p in configured)
        else "DEGRADED"
    )
    if diagnostic["status"] != "HEALTHY" or diagnostic["data_mode"] != "real":
        bot = "DEGRADED"
    return {
        "status": diagnostic["status"],
        "bot_status": bot,
        "api": "ONLINE",
        "database": "ONLINE",
        "data_mode": diagnostic["data_mode"],
        "worker_status": "ONLINE" if worker_online else "OFFLINE",
        "worker_last_seen": pulse.last_seen.isoformat() if pulse else None,
        "providers": system["providers"],
        "real_events": diagnostic["real_events"],
        "production_predictions": diagnostic["predictions"],
        "production_picks": diagnostic["recommendations"],
        **timestamps,
    }
