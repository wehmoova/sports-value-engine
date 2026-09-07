from fastapi import APIRouter

from app.api.routes import analytics, dashboard, events, picks, system

api_router = APIRouter()
api_router.include_router(dashboard.router, tags=["dashboard"])
api_router.include_router(events.router, tags=["events"])
api_router.include_router(picks.router, tags=["picks"])
api_router.include_router(analytics.router, tags=["analytics"])
api_router.include_router(system.router, tags=["system"])
