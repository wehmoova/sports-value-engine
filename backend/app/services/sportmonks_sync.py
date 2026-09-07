"""Subscription-aware ingestion: persist basic fixtures before optional enrichment."""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import ApiLog, FootballStatistic
from app.providers.football.sportmonks import SportmonksFootballProvider
from app.providers.odds.the_odds_api import payload_hash
from app.services.football_sync import normalize_football_fixture, sync_football_statistics
from app.services.ingestion import upsert_event


async def sync_sportmonks_capabilities(
    session: AsyncSession, provider: SportmonksFootballProvider
) -> list[dict[str, Any]]:
    leagues = await provider.discover_leagues()
    session.add(
        ApiLog(
            provider_name="Sportmonks",
            endpoint="leagues",
            status_code=200,
            context={"accessible_league_ids": provider.accessible_league_ids},
        )
    )
    await session.commit()
    return leagues


async def sync_sportmonks_data(
    session: AsyncSession, provider: SportmonksFootballProvider, run_id: str, config: Settings
) -> dict[str, int]:
    await sync_sportmonks_capabilities(session, provider)
    now = datetime.now(UTC)
    rows = await provider.get_fixtures(now - timedelta(days=14), now + timedelta(days=14))
    fixtures = []
    invalid = 0
    for row in rows:
        if row.get("league_id") not in provider.accessible_league_ids:
            continue
        try:
            normalized = normalize_football_fixture(row, "sportmonks")
        except (ValueError, KeyError, TypeError):
            invalid += 1
            continue
        event = await upsert_event(
            session, normalized=normalized, provider="sportmonks", run_id=run_id
        )
        fixtures.append((event, row))
        if normalized.status == "FINAL":
            from app.research.backfill import persist_result

            try:
                async with session.begin_nested():
                    await persist_result(session, row, "sportmonks", run_id)
            except (ValueError, TypeError, KeyError):
                invalid += 1
    await session.commit()
    # Never roll back valid fixtures because premium access is denied.
    statistics = 0
    provider.capabilities.update(
        statistics="NOT_TESTED", lineups="NOT_TESTED", xg="DISABLED", standings="NOT_TESTED"
    )
    for event, row in fixtures[: config.provider_detail_event_limit]:
        data = await provider.optional_fixture(str(row["id"]), "statistics", "statistics.type")
        for side, team_id, participant_id in (
            (
                "home",
                event.home_entity_id,
                next(
                    (
                        p["id"]
                        for p in row.get("participants", [])
                        if p.get("meta", {}).get("location") == "home"
                    ),
                    None,
                ),
            ),
            (
                "away",
                event.away_entity_id,
                next(
                    (
                        p["id"]
                        for p in row.get("participants", [])
                        if p.get("meta", {}).get("location") == "away"
                    ),
                    None,
                ),
            ),
        ):
            values = [
                stat
                for stat in data.get("statistics", [])
                if stat.get("participant_id") == participant_id
            ]
            if not values:
                continue
            digest = payload_hash(values)
            existing = await session.scalar(
                select(FootballStatistic).where(
                    FootballStatistic.event_id == event.id,
                    FootballStatistic.side == side,
                    FootballStatistic.source_provider == "sportmonks",
                    FootballStatistic.raw_payload_hash == digest,
                )
            )
            if existing is None:
                session.add(
                    FootballStatistic(
                        event_id=event.id,
                        team_id=team_id,
                        side=side,
                        sample_size=0,
                        payload={"fixture_statistics": values, "fixture_id": row["id"]},
                        source_provider="sportmonks",
                        provider_entity_id=str(participant_id),
                        fetched_at=now,
                        observed_at=now,
                        raw_payload_hash=digest,
                        ingestion_run_id=run_id,
                    )
                )
                statistics += 1
        if provider.capabilities["statistics"] == "FORBIDDEN":
            break
    statistics += await sync_football_statistics(
        session,
        provider,
        "sportmonks",
        fixtures,
        run_id,
        config.provider_detail_event_limit,
    )
    if fixtures:
        first = fixtures[0][1]
        await provider.optional_fixture(str(first["id"]), "lineups", "lineups")
    provider.capabilities["normalization_rejected"] = invalid
    session.add(
        ApiLog(
            provider_name="Sportmonks",
            endpoint="capabilities",
            status_code=200,
            context={
                **provider.capabilities,
                "run_id": run_id,
                "fixtures_persisted": len(fixtures),
            },
        )
    )
    await session.commit()
    return {
        "events": len(fixtures),
        "statistics": statistics,
        "injuries": 0,
        "suspensions": 0,
        "lineups": 0,
    }
