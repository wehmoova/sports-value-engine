from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import Event, TennisStatistic
from app.providers.base import NormalizedEvent, NormalizedOdd, ProviderBatch, TennisProvider
from app.providers.odds.the_odds_api import payload_hash
from app.services.ingestion import persist_odds_batch, upsert_event


def _tour(record: dict[str, Any]) -> str:
    description = " ".join(
        str(record.get(key) or "") for key in ("event_type_type", "tournament_name", "league_name")
    ).lower()
    if any(term in description for term in ("double", "itf", "challenger")):
        raise ValueError("Unsupported tennis competition")
    if "wta" in description:
        return "tennis_wta"
    if "atp" in description:
        return "tennis_atp"
    raise ValueError("Cannot verify ATP/WTA competition")


def _scheduled_at(record: dict[str, Any]) -> datetime:
    date = str(record.get("event_date") or "")
    time = str(record.get("event_time") or "")
    if not date or not time:
        raise ValueError("tennis fixture has no scheduled date/time")
    parsed = datetime.fromisoformat(f"{date}T{time}")
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def normalize_tennis_fixture(record: dict[str, Any]) -> NormalizedEvent:
    first = str(record.get("event_first_player") or "").strip()
    second = str(record.get("event_second_player") or "").strip()
    if not first or not second:
        raise ValueError("tennis fixture has no players")
    status = str(record.get("event_status") or "SCHEDULED").upper()
    if "FINISH" in status or status in {"FT", "ENDED"}:
        status = "FINAL"
    raw_winner = str(record.get("event_winner") or "")
    winner_name = None
    if raw_winner and raw_winner in {
        "First Player",
        "1",
        str(record.get("first_player_key") or ""),
    }:
        winner_name = first
    elif raw_winner and raw_winner in {
        "Second Player",
        "2",
        str(record.get("second_player_key") or ""),
    }:
        winner_name = second
    return NormalizedEvent(
        external_id=str(record["event_key"]),
        sport=_tour(record),
        competition=str(
            record.get("tournament_name") or record.get("event_type_type") or "Unknown tournament"
        ),
        competition_key=str(record.get("tournament_key") or record.get("event_type_key") or ""),
        home_name=first,
        away_name=second,
        home_external_id=str(record.get("first_player_key") or ""),
        away_external_id=str(record.get("second_player_key") or ""),
        start_time=_scheduled_at(record),
        status=status,
        winner_name=winner_name,
        surface=str(record.get("tournament_surface") or record.get("event_surface") or "") or None,
        round=str(record.get("tournament_round") or record.get("event_round") or "") or None,
        source_timestamp=datetime.now(UTC),
        raw_payload_hash=payload_hash(record),
    )


def _number(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace("%", ""))
    except ValueError:
        return None


def _stat_lookup(record: dict[str, Any], player_key: str) -> dict[str, float]:
    found: dict[str, float] = {}
    for item in record.get("statistics", []):
        if str(item.get("player_key") or "") != player_key:
            continue
        name = str(item.get("stat_name") or "").strip().lower()
        value = _number(item.get("stat_value") or item.get("stat_won"))
        if name and value is not None:
            found[name] = value
    return found


def _ranking_map(rows: list[dict[str, Any]]) -> dict[str, tuple[int | None, int | None]]:
    result: dict[str, tuple[int | None, int | None]] = {}
    for row in rows:
        key = str(row.get("player_key") or row.get("id") or "")
        rank = _number(row.get("place") or row.get("ranking") or row.get("rank"))
        points = _number(row.get("points") or row.get("ranking_points"))
        if key:
            result[key] = (
                int(rank) if rank is not None else None,
                int(points) if points is not None else None,
            )
    return result


def _normalized_api_tennis_odds(
    events: list[NormalizedEvent], raw_odds: dict[str, Any]
) -> list[NormalizedOdd]:
    by_id = {event.external_id: event for event in events}
    now = datetime.now(UTC)
    normalized: list[NormalizedOdd] = []
    for event_id, markets in raw_odds.items():
        event = by_id.get(str(event_id))
        if event is None or not isinstance(markets, dict):
            continue
        home_away = markets.get("Home/Away") or markets.get("Home/Away (1X2)")
        if not isinstance(home_away, dict):
            continue
        for provider_selection, prices in home_away.items():
            if not isinstance(prices, dict):
                continue
            selection_key = str(provider_selection).lower()
            selection = event.home_name if selection_key == "home" else event.away_name
            for bookmaker, raw_price in prices.items():
                try:
                    normalized.append(
                        NormalizedOdd(
                            event_external_id=event.external_id,
                            bookmaker=str(bookmaker),
                            market="MONEYLINE",
                            selection=selection,
                            decimal_odds=float(raw_price),
                            timestamp=now,
                        )
                    )
                except (TypeError, ValueError):
                    continue
    return normalized


async def sync_tennis_events(
    session: AsyncSession,
    provider: TennisProvider,
    run_id: str,
) -> tuple[list[tuple[Event, dict[str, Any], NormalizedEvent]], list[NormalizedEvent]]:
    now = datetime.now(UTC)
    fixtures = await provider.get_matches(now - timedelta(days=3), now + timedelta(days=7))
    persisted: list[tuple[Event, dict[str, Any], NormalizedEvent]] = []
    normalized_events: list[NormalizedEvent] = []
    for raw in fixtures:
        try:
            normalized = normalize_tennis_fixture(raw)
        except (KeyError, TypeError, ValueError):
            continue
        event = await upsert_event(
            session, normalized=normalized, provider="api_tennis", run_id=run_id
        )
        persisted.append((event, raw, normalized))
        normalized_events.append(normalized)
    await session.flush()
    return persisted, normalized_events


async def sync_tennis_statistics(
    session: AsyncSession,
    provider: TennisProvider,
    fixtures: list[tuple[Event, dict[str, Any], NormalizedEvent]],
    run_id: str,
) -> int:
    atp, wta = await provider.get_rankings("ATP"), await provider.get_rankings("WTA")
    rankings = _ranking_map(atp + wta)
    created = 0
    for event, raw, normalized in fixtures:
        digest = normalized.raw_payload_hash or payload_hash(raw)
        for side, entity_id, external_id in (
            ("home", event.home_entity_id, normalized.home_external_id),
            ("away", event.away_entity_id, normalized.away_external_id),
        ):
            if not external_id:
                continue
            existing = await session.scalar(
                select(TennisStatistic).where(
                    TennisStatistic.event_id == event.id,
                    TennisStatistic.side == side,
                    TennisStatistic.raw_payload_hash == digest,
                )
            )
            if existing is not None:
                continue
            stats = _stat_lookup(raw, external_id)
            rank, points = rankings.get(external_id, (None, None))
            session.add(
                TennisStatistic(
                    event_id=event.id,
                    player_id=entity_id,
                    side=side,
                    sample_size=0,
                    ranking=rank,
                    ranking_points=points,
                    overall_elo=None,
                    surface_elo=None,
                    hold_pct=stats.get("service games won"),
                    break_pct=stats.get("return games won"),
                    first_serve_pct=stats.get("1st serve"),
                    first_serve_won_pct=stats.get("1st serve points won"),
                    second_serve_won_pct=stats.get("2nd serve points won"),
                    return_points_won_pct=stats.get("return points won"),
                    matches_last_7_days=None,
                    payload={"fixture": raw, "ranking": rankings.get(external_id)},
                    observed_at=datetime.now(UTC),
                    source_provider="api_tennis",
                    provider_entity_id=external_id,
                    fetched_at=datetime.now(UTC),
                    raw_payload_hash=digest,
                    ingestion_run_id=run_id,
                )
            )
            created += 1
    await session.flush()
    return created


async def sync_tennis_odds(
    session: AsyncSession,
    provider: TennisProvider,
    normalized_events: list[NormalizedEvent],
    run_id: str,
    settings: Settings,
) -> int:
    now = datetime.now(UTC)
    raw_odds = await provider.get_odds(now, now + timedelta(days=7))
    batch = ProviderBatch(
        events=normalized_events,
        odds=_normalized_api_tennis_odds(normalized_events, raw_odds),
        payload_hashes=[payload_hash(raw_odds)] if raw_odds else [],
    )
    inserted, _, _ = await persist_odds_batch(
        session,
        batch=batch,
        provider="api_tennis",
        run_id=run_id,
        settings=settings,
    )
    return inserted


async def sync_tennis_data(
    session: AsyncSession,
    provider: TennisProvider,
    run_id: str,
    settings: Settings,
) -> dict[str, int]:
    fixtures, normalized = await sync_tennis_events(session, provider, run_id)
    statistics = await sync_tennis_statistics(session, provider, fixtures, run_id)
    # This provider's odds payload has no observation timestamp. Do not fabricate
    # freshness; tennis prices come from The Odds API's timestamped snapshots.
    odds = 0
    return {"events": len(fixtures), "statistics": statistics, "odds": odds}
