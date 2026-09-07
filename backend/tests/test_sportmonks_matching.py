from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.database.session import SessionLocal
from app.models import ProviderEntity
from app.providers.base import NormalizedEvent
from app.services.ingestion import upsert_event


async def test_matching_requires_competition_and_stores_both_provider_ids() -> None:
    now = datetime.now(UTC)
    normalized = NormalizedEvent(
        external_id="odds-match",
        sport="football",
        competition="Matching test league",
        competition_key="odds-league",
        home_name="Match home",
        away_name="Match away",
        start_time=now,
        source_timestamp=now,
    )
    async with SessionLocal() as session:
        odds = await upsert_event(
            session, normalized=normalized, provider="the_odds_api", run_id="test"
        )
        fixture = await upsert_event(
            session,
            normalized=normalized.model_copy(
                update={
                    "external_id": "fixture-match",
                    "competition_key": "fixture-league",
                    "start_time": now + timedelta(minutes=5),
                }
            ),
            provider="sportmonks",
            run_id="test",
        )
        assert odds.id == fixture.id
        await session.flush()
        mappings = list(
            await session.scalars(
                select(ProviderEntity).where(
                    ProviderEntity.internal_id == fixture.id, ProviderEntity.entity_type == "event"
                )
            )
        )
        assert {row.provider for row in mappings} == {"the_odds_api", "sportmonks"}
        uncertain = await upsert_event(
            session,
            normalized=normalized.model_copy(
                update={
                    "external_id": "other-fixture",
                    "competition_key": "other-league",
                    "competition": "Different competition",
                }
            ),
            provider="sportmonks",
            run_id="test",
        )
        assert uncertain.id != fixture.id
        await session.rollback()
