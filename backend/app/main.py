import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app import models  # noqa: F401
from app.api.router import api_router
from app.core.config import settings
from app.database.base import Base
from app.database.session import SessionLocal, engine
from app.scheduler.jobs import build_scheduler
from app.services.data_mode import initialize_provider_statuses, purge_legacy_simulation_records


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if settings.database_url.startswith("sqlite"):
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async with SessionLocal() as session:
        if settings.is_real_mode:
            await purge_legacy_simulation_records(session)
        await initialize_provider_statuses(session, settings)

    scheduler: AsyncIOScheduler | None = None
    if settings.scheduler_enabled and settings.environment != "production":
        scheduler = build_scheduler()
        scheduler.start()
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    description=(
        "Typed internal API for pre-match sports analytics, price consensus, "
        "value evaluation and model monitoring."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.middleware("http")
async def protect_production_writes(request: Request, call_next: Any) -> Any:
    if settings.environment == "production" and request.method not in {"GET", "HEAD", "OPTIONS"}:
        token = settings.admin_api_token
        provided = request.headers.get("authorization", "")
        if not token or not secrets.compare_digest(provided, f"Bearer {token}"):
            return JSONResponse(status_code=401, content={"detail": "Admin authorization required"})
    return await call_next(request)


@app.get("/health", tags=["system"])
async def health() -> dict[str, Any]:
    async with SessionLocal() as session:
        await session.execute(text("SELECT 1"))
    return {
        "status": "healthy",
        "service": settings.app_name,
        "environment": settings.environment,
        "data_mode": settings.data_mode,
    }
