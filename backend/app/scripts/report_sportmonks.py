import asyncio
import json

from sqlalchemy import func, select

from app.database.session import SessionLocal, engine
from app.models import (
    Event,
    FootballStatistic,
    ModelPrediction,
    OddsSnapshot,
    ProviderEntity,
    ProviderStatus,
    Recommendation,
    TennisStatistic,
)
from app.services.queries import system_status


async def report() -> None:
    async with SessionLocal() as session:
        counts = {}
        for model in (
            Event,
            OddsSnapshot,
            FootballStatistic,
            TennisStatistic,
            ModelPrediction,
            Recommendation,
        ):
            counts[model.__tablename__] = await session.scalar(
                select(func.count()).select_from(model)
            )
        mappings = list(
            await session.scalars(
                select(ProviderEntity).where(
                    ProviderEntity.provider == "sportmonks", ProviderEntity.entity_type == "event"
                )
            )
        )
        counts["sportmonks_fixtures"] = len(mappings)
        counts["sportmonks_statistics"] = await session.scalar(
            select(func.count())
            .select_from(FootballStatistic)
            .where(FootballStatistic.source_provider == "sportmonks")
        )
        counts["mock_events"] = await session.scalar(
            select(func.count())
            .select_from(Event)
            .where((Event.is_demo.is_(True)) | (Event.data_origin != "REAL"))
        )
        proof = None
        if mappings:
            event = await session.get(Event, mappings[0].internal_id)
            if event:
                proof = {
                    "internal_id": event.id,
                    "provider": "sportmonks",
                    "provider_event_id": mappings[0].external_id,
                    "name": event.name,
                    "fetched_at": str(event.fetched_at),
                    "data_origin": event.data_origin,
                }
        providers = [
            {
                "name": p.provider_name,
                "status": p.status,
                "records": p.records_received,
                "error": p.last_error,
            }
            for p in await session.scalars(select(ProviderStatus))
        ]
        print(
            json.dumps(
                {
                    "database": engine.dialect.name,
                    "counts": counts,
                    "providers": providers,
                    "capabilities": (await system_status(session))["sportmonks_capabilities"],
                    "proof": proof,
                },
                default=str,
            )
        )
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(report())
