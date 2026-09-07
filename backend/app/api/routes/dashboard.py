from typing import Any

from fastapi import APIRouter

from app.api.dependencies import SessionDep
from app.services.queries import dashboard

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard(session: SessionDep) -> dict[str, Any]:
    return await dashboard(session)
