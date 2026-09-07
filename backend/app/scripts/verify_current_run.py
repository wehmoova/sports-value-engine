"""Acceptance evidence must belong to this run and use PostgreSQL."""

from sqlalchemy import select

from app.database.session import SessionLocal, engine
from app.models import Event, OddsSnapshot, ProviderPayloadAudit


async def verify_current_run(run_id: str) -> bool:
    if engine.dialect.name != "postgresql":
        print("REAL DATA NOT VERIFIED: PostgreSQL acceptance environment required")
        return False
    async with SessionLocal() as session:
        event = await session.scalar(
            select(Event).where(
                Event.ingestion_run_id == run_id,
                Event.data_origin == "REAL",
                Event.is_demo.is_(False),
            )
        )
        audit = await session.scalar(
            select(ProviderPayloadAudit).where(
                ProviderPayloadAudit.ingestion_run_id == run_id,
                ProviderPayloadAudit.status_code == 200,
            )
        )
        odds = await session.scalar(
            select(OddsSnapshot).where(OddsSnapshot.ingestion_run_id == run_id)
        )
        verified = event is not None and audit is not None and odds is not None
        print(
            "REAL DATA VERIFIED: current run persisted event + odds + request audit"
            if verified
            else "REAL DATA NOT VERIFIED: current run has incomplete evidence"
        )
        return verified
