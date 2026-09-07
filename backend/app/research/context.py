"""Load persisted provider snapshots as point-in-time research evidence."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event, FootballStatistic, ProviderEntity, Sport, TennisStatistic
from app.providers.odds.the_odds_api import payload_hash

_CONTEXT_QUERY_CHUNK = 500


def _provenance_ok(row: FootballStatistic | TennisStatistic) -> bool:
    return bool(
        row.source_provider not in {"unknown", "", None}
        and row.provider_entity_id
        and row.ingestion_run_id
        and row.payload.get("availability_basis") == "OBSERVED_PROVIDER_SNAPSHOT"
        and row.raw_payload_hash == payload_hash(row.payload)
    )


def _utc_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _standing_value(payload: dict[str, Any], key: str) -> Any:
    standing = payload.get("standing")
    return standing.get(key) if isinstance(standing, dict) else None


def _football_record(row: FootballStatistic) -> dict[str, Any]:
    payload = row.payload or {}
    fixture_only = (
        "fixture_statistics" in payload
        and "team_statistics" not in payload
        and "standing" not in payload
    )
    return {
        "snapshot_id": row.id,
        "source_table": "football_statistics",
        "event_id": row.event_id,
        "kind": "football_fixture_stat" if fixture_only else "football_team",
        "side": row.side,
        "observed_at": _utc_iso(row.observed_at),
        "fetched_at": _utc_iso(row.fetched_at),
        "source_updated_at": _utc_iso(row.source_updated_at),
        "source_provider": row.source_provider,
        "provider_entity_id": row.provider_entity_id,
        "raw_payload_hash": row.raw_payload_hash,
        "ingestion_run_id": row.ingestion_run_id,
        "post_match": bool(payload.get("post_match")),
        "sample_size": row.sample_size,
        "goals_per_match": row.goals_per_match,
        "goals_against_per_match": row.goals_against_per_match,
        "standing_position": _standing_value(payload, "position"),
        "standing_points": _standing_value(payload, "points"),
        "standing_goal_difference": _standing_value(payload, "goal_difference"),
        "standing_played": _standing_value(payload, "played"),
    }


def _tennis_record(row: TennisStatistic) -> dict[str, Any]:
    payload = row.payload or {}
    return {
        "snapshot_id": row.id,
        "source_table": "tennis_statistics",
        "event_id": row.event_id,
        "kind": "tennis_ranking",
        "side": row.side,
        "observed_at": _utc_iso(row.observed_at),
        "fetched_at": _utc_iso(row.fetched_at),
        "source_updated_at": _utc_iso(row.source_updated_at),
        "source_provider": row.source_provider,
        "provider_entity_id": row.provider_entity_id,
        "raw_payload_hash": row.raw_payload_hash,
        "ingestion_run_id": row.ingestion_run_id,
        "post_match": bool(payload.get("post_match")),
        "ranking": row.ranking,
        "ranking_points": row.ranking_points,
    }


async def load_context_snapshots(
    session: AsyncSession, sport: str, event_ids: list[str]
) -> list[dict[str, Any]]:
    """Return exact-event snapshots; feature code applies the strict time cutoff."""
    if sport not in {"football", "tennis_atp", "tennis_wta"}:
        raise ValueError("Unsupported context sport")
    ids = list(dict.fromkeys(event_id for event_id in event_ids if event_id))
    if not ids:
        return []
    records: list[dict[str, Any]] = []
    for offset in range(0, len(ids), _CONTEXT_QUERY_CHUNK):
        chunk = ids[offset : offset + _CONTEXT_QUERY_CHUNK]
        if sport == "football":
            football_rows = list(
                await session.scalars(
                    select(FootballStatistic)
                    .join(Event, Event.id == FootballStatistic.event_id)
                    .join(Sport, Sport.id == Event.sport_id)
                    .join(
                        ProviderEntity,
                        (ProviderEntity.internal_id == FootballStatistic.team_id)
                        & (ProviderEntity.external_id == FootballStatistic.provider_entity_id)
                        & (ProviderEntity.provider == FootballStatistic.source_provider)
                        & (ProviderEntity.entity_type == "team"),
                    )
                    .where(
                        FootballStatistic.event_id.in_(chunk),
                        Sport.key == sport,
                        Event.is_demo.is_(False),
                        Event.data_origin == "REAL",
                        (
                            (FootballStatistic.side == "home")
                            & (FootballStatistic.team_id == Event.home_entity_id)
                        )
                        | (
                            (FootballStatistic.side == "away")
                            & (FootballStatistic.team_id == Event.away_entity_id)
                        ),
                    )
                )
            )
            records.extend(_football_record(row) for row in football_rows if _provenance_ok(row))
        else:
            tennis_rows = list(
                await session.scalars(
                    select(TennisStatistic)
                    .join(Event, Event.id == TennisStatistic.event_id)
                    .join(Sport, Sport.id == Event.sport_id)
                    .join(
                        ProviderEntity,
                        (ProviderEntity.internal_id == TennisStatistic.player_id)
                        & (ProviderEntity.external_id == TennisStatistic.provider_entity_id)
                        & (ProviderEntity.provider == TennisStatistic.source_provider)
                        & (ProviderEntity.entity_type == "player"),
                    )
                    .where(
                        TennisStatistic.event_id.in_(chunk),
                        Sport.key == sport,
                        Event.is_demo.is_(False),
                        Event.data_origin == "REAL",
                        (
                            (TennisStatistic.side == "home")
                            & (TennisStatistic.player_id == Event.home_entity_id)
                        )
                        | (
                            (TennisStatistic.side == "away")
                            & (TennisStatistic.player_id == Event.away_entity_id)
                        ),
                    )
                )
            )
            records.extend(_tennis_record(row) for row in tennis_rows if _provenance_ok(row))
    return records
