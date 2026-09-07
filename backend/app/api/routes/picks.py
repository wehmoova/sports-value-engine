from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.api.dependencies import SessionDep
from app.services.queries import recommendation_rows

router = APIRouter()


@router.get("/picks")
async def get_picks(
    session: SessionDep,
    sport: str | None = Query(default=None),
    status: str = Query(default="VALUE"),
) -> list[dict[str, Any]]:
    return await recommendation_rows(session, status=status, sport_key=sport)


@router.get("/picks/today")
async def get_today_picks(
    session: SessionDep,
) -> list[dict[str, Any]]:
    return await recommendation_rows(session, status="VALUE")


@router.get("/picks/{pick_id}")
async def get_pick(pick_id: str, session: SessionDep) -> dict[str, Any]:
    picks = await recommendation_rows(session, limit=500)
    match = next((pick for pick in picks if pick["id"] == pick_id), None)
    if match is None:
        raise HTTPException(status_code=404, detail="Pick not found")
    return match


@router.get("/no-bet")
async def get_no_bets(
    session: SessionDep,
) -> list[dict[str, Any]]:
    return await recommendation_rows(session, status="NO_BET")
