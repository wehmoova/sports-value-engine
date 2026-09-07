from dataclasses import asdict
from typing import Any

from fastapi import APIRouter
from sqlalchemy import desc, select

from app.analytics.monte_carlo import simulate_challenge
from app.api.dependencies import SessionDep
from app.core.config import settings
from app.models import BankrollHistory, ModelRegistry
from app.schemas.api import ChallengeRequest
from app.services.queries import combinations, performance

router = APIRouter()


@router.get("/combinations")
async def get_combinations(session: SessionDep) -> list[dict[str, Any]]:
    return await combinations(session)


@router.get("/performance")
async def get_performance(session: SessionDep) -> dict[str, Any]:
    return await performance(session)


@router.get("/performance/football")
async def get_football_performance(
    session: SessionDep,
) -> dict[str, Any]:
    data = await performance(session)
    data["filter"] = "football"
    return data


@router.get("/performance/tennis")
async def get_tennis_performance(
    session: SessionDep,
) -> dict[str, Any]:
    data = await performance(session)
    data["filter"] = "tennis"
    return data


@router.get("/bankroll")
async def get_bankroll(session: SessionDep) -> dict[str, Any]:
    records = list(
        (
            await session.execute(select(BankrollHistory).order_by(BankrollHistory.recorded_at))
        ).scalars()
    )
    starting = records[0].bankroll if records else 0
    current = records[-1].bankroll if records else 0
    peak = max((record.bankroll for record in records), default=0)
    return {
        "starting_bankroll": starting,
        "current_bankroll": current,
        "profit": current - starting,
        "roi": (current / starting - 1) if starting else 0,
        "current_drawdown": (peak - current) / peak if peak else 0,
        "history": [
            {
                "timestamp": record.recorded_at.isoformat(),
                "bankroll": record.bankroll,
                "change": record.change,
                "reason": record.reason,
            }
            for record in records
        ],
        "data_mode": settings.data_mode,
    }


@router.post("/challenge/simulate")
async def challenge_simulation(request: ChallengeRequest) -> dict[str, Any]:
    return asdict(simulate_challenge(**request.model_dump()))


@router.get("/models")
async def get_models(session: SessionDep) -> list[dict[str, Any]]:
    rows = list(
        (
            await session.execute(select(ModelRegistry).order_by(desc(ModelRegistry.created_at)))
        ).scalars()
    )
    return [
        {
            "model_name": row.model_name,
            "model_version": row.model_version,
            "sport": row.sport,
            "market": row.market,
            "status": row.status,
            "is_active": row.is_active,
            "calibration_method": row.calibration_method,
            "metrics": row.metrics,
        }
        for row in rows
    ]
