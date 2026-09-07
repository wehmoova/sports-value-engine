from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.analytics.value.engine import classify_odds_freshness
from app.api.dependencies import SessionDep
from app.core.config import settings
from app.models import Event, OddsSnapshot
from app.services.queries import event_detail, event_rows

router = APIRouter()


@router.get("/events")
async def get_events(
    session: SessionDep,
    sport: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, Any]]:
    return await event_rows(session, sport_key=sport, limit=limit)


@router.get("/football/events")
async def get_football_events(
    session: SessionDep,
) -> list[dict[str, Any]]:
    return await event_rows(session, sport_key="football")


@router.get("/tennis/events")
async def get_tennis_events(
    session: SessionDep,
) -> list[dict[str, Any]]:
    return await event_rows(session, sport_key="tennis")


@router.get("/events/{event_id}")
async def get_event(event_id: str, session: SessionDep) -> dict[str, Any]:
    detail = await event_detail(session, event_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return detail


@router.get("/odds/{event_id}")
async def get_event_odds(event_id: str, session: SessionDep) -> list[dict[str, Any]]:
    result = await session.execute(
        select(OddsSnapshot)
        .join(Event, OddsSnapshot.event_id == Event.id)
        .where(OddsSnapshot.event_id == event_id)
        .where(Event.is_demo.is_(False), Event.data_origin == "REAL")
        .order_by(OddsSnapshot.observed_at)
    )
    rows = []
    for odd in result.scalars():
        freshness, age_seconds = classify_odds_freshness(
            odd.observed_at,
            stale_minutes=settings.odds_stale_minutes,
            expired_minutes=settings.odds_expired_minutes,
        )
        rows.append(
            {
                "id": odd.id,
                "bookmaker": odd.bookmaker,
                "market": odd.market,
                "selection": odd.selection,
                "decimal_odds": odd.decimal_odds,
                "point": odd.point,
                "observed_at": odd.observed_at.isoformat(),
                "is_live": odd.is_live,
                "is_outlier": odd.is_outlier,
                "validation_status": odd.validation_status,
                "validation_reason": odd.validation_reason,
                "freshness_status": freshness,
                "odds_age_seconds": age_seconds,
                "eligible_for_best_price": odd.validation_status == "VALID"
                and freshness == "FRESH",
            }
        )
    return rows
