import hashlib
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.value.engine import classify_odds_freshness, classify_odds_prices
from app.core.config import Settings
from app.models import Competition, Event, OddsSnapshot, ProviderEntity, Sport
from app.providers.base import NormalizedEvent, ProviderBatch
from app.services.entities import normalize_entity_name, resolve_participant


def canonical_event_key(event: NormalizedEvent) -> str:
    participants = [normalize_entity_name(event.home_name), normalize_entity_name(event.away_name)]
    if event.sport.startswith("tennis"):
        participants.sort()
    start_minute = event.start_time.astimezone(UTC).replace(second=0, microsecond=0).isoformat()
    raw = "|".join([event.sport, *participants, start_minute])
    return hashlib.sha256(raw.encode()).hexdigest()


def odds_snapshot_key(
    *,
    event_id: str,
    provider: str,
    bookmaker: str,
    market: str,
    selection: str,
    point: float | None,
    observed_at: datetime,
) -> str:
    raw = "|".join(
        [
            event_id,
            provider,
            bookmaker,
            market,
            selection,
            "" if point is None else f"{point:.4f}",
            observed_at.astimezone(UTC).isoformat(),
        ]
    )
    return hashlib.sha256(raw.encode()).hexdigest()


async def _sport(session: AsyncSession, key: str) -> Sport:
    sport = await session.scalar(select(Sport).where(Sport.key == key))
    if sport is None:
        sport = Sport(key=key, name=key.replace("_", " ").title())
        session.add(sport)
        await session.flush()
    return sport


async def _competition(session: AsyncSession, sport: Sport, event: NormalizedEvent) -> Competition:
    query = select(Competition).where(Competition.sport_id == sport.id)
    query = (
        query.where(Competition.external_key == event.competition_key)
        if event.competition_key
        else query.where(Competition.name == event.competition)
    )
    competition = await session.scalar(query)
    if competition is None:
        competition = await session.scalar(
            select(Competition).where(
                Competition.sport_id == sport.id, Competition.name == event.competition
            )
        )
    if competition is None:
        competition = Competition(
            sport_id=sport.id,
            name=event.competition,
            external_key=event.competition_key,
            surface=event.surface,
        )
        session.add(competition)
        await session.flush()
    return competition


async def upsert_event(
    session: AsyncSession,
    *,
    normalized: NormalizedEvent,
    provider: str,
    run_id: str,
) -> Event:
    mapping = await session.scalar(
        select(ProviderEntity).where(
            ProviderEntity.provider == provider,
            ProviderEntity.entity_type == "event",
            ProviderEntity.external_id == normalized.external_id,
        )
    )
    if mapping is not None:
        mapped_event = await session.get(Event, mapping.internal_id)
        if mapped_event is not None:
            event = mapped_event
        else:
            await session.delete(mapping)
            event = None
    else:
        event = None

    sport = await _sport(session, normalized.sport)
    competition = await _competition(session, sport, normalized)
    home_external_id = normalized.home_external_id or (
        f"{normalized.sport}:{normalize_entity_name(normalized.home_name)}"
    )
    away_external_id = normalized.away_external_id or (
        f"{normalized.sport}:{normalize_entity_name(normalized.away_name)}"
    )
    home_id = await resolve_participant(
        session,
        sport=sport,
        provider=provider,
        external_id=home_external_id,
        name=normalized.home_name,
    )
    away_id = await resolve_participant(
        session,
        sport=sport,
        provider=provider,
        external_id=away_external_id,
        name=normalized.away_name,
    )
    key = canonical_event_key(normalized)
    if event is None and normalized.sport == "football":
        candidates = list(
            await session.scalars(
                select(Event).where(
                    Event.sport_id == sport.id,
                    Event.home_entity_id == home_id,
                    Event.away_entity_id == away_id,
                    Event.competition_id == competition.id,
                    Event.start_time >= normalized.start_time - timedelta(minutes=10),
                    Event.start_time <= normalized.start_time + timedelta(minutes=10),
                    Event.is_demo.is_(False),
                    Event.data_origin == "REAL",
                )
            )
        )
        if len(candidates) == 1:
            event = candidates[0]
    if event is None:
        event = await session.scalar(select(Event).where(Event.canonical_key == key))
        if (
            event is not None
            and normalized.sport == "football"
            and event.competition_id != competition.id
        ):
            event = None
            key = hashlib.sha256(f"{key}|{provider}|{normalized.external_id}".encode()).hexdigest()
    if event is None:
        event = Event(
            sport_id=sport.id,
            competition_id=competition.id,
            provider=provider,
            external_id=normalized.external_id,
            canonical_key=key,
            name=f"{normalized.home_name} vs {normalized.away_name}",
            home_name=normalized.home_name,
            away_name=normalized.away_name,
            home_entity_id=home_id,
            away_entity_id=away_id,
            start_time=normalized.start_time,
            status=normalized.status,
            home_score=normalized.home_score,
            away_score=normalized.away_score,
            winner_name=normalized.winner_name,
            surface=normalized.surface,
            round=normalized.round,
            source_timestamp=normalized.source_timestamp,
            source_provider=provider,
            provider_entity_id=normalized.external_id,
            fetched_at=datetime.now(UTC),
            source_updated_at=normalized.source_updated_at,
            raw_payload_hash=normalized.raw_payload_hash,
            ingestion_run_id=run_id,
            data_origin="REAL",
            is_demo=False,
        )
        session.add(event)
        await session.flush()
    else:
        event.competition_id = competition.id
        event.name = f"{normalized.home_name} vs {normalized.away_name}"
        event.home_name = normalized.home_name
        event.away_name = normalized.away_name
        event.home_entity_id = home_id
        event.away_entity_id = away_id
        event.start_time = normalized.start_time
        if provider != "the_odds_api":
            event.status = normalized.status
            event.home_score = normalized.home_score
            event.away_score = normalized.away_score
            event.winner_name = normalized.winner_name
        event.surface = normalized.surface or event.surface
        event.round = normalized.round or event.round
        event.source_timestamp = normalized.source_timestamp
        event.source_updated_at = normalized.source_updated_at
        event.fetched_at = datetime.now(UTC)
        event.raw_payload_hash = normalized.raw_payload_hash
        event.ingestion_run_id = run_id
        event.data_origin = "REAL"
        event.is_demo = False

    if mapping is None:
        session.add(
            ProviderEntity(
                provider=provider,
                entity_type="event",
                external_id=normalized.external_id,
                internal_id=event.id,
                canonical_name=event.name,
            )
        )
    return event


async def persist_odds_batch(
    session: AsyncSession,
    *,
    batch: ProviderBatch,
    provider: str,
    run_id: str,
    settings: Settings,
) -> tuple[int, int, dict[str, Event]]:
    event_cache: dict[str, Event] = {}
    for normalized in batch.events:
        event_cache[normalized.external_id] = await upsert_event(
            session, normalized=normalized, provider=provider, run_id=run_id
        )

    grouped_indices: dict[tuple[str, str, str, float | None], list[int]] = defaultdict(list)
    for index, odd in enumerate(batch.odds):
        grouped_indices[(odd.event_external_id, odd.market, odd.selection, odd.point)].append(index)
    validations: dict[int, tuple[str, str | None]] = {}
    for indices in grouped_indices.values():
        group_validations = classify_odds_prices(
            [batch.odds[index].decimal_odds for index in indices]
        )
        for index, validation in zip(indices, group_validations, strict=True):
            validations[index] = (validation.status, validation.reason)

    inserted = 0
    duplicate = 0
    now = datetime.now(UTC)
    for index, odd in enumerate(batch.odds):
        event = event_cache.get(odd.event_external_id)
        if event is None:
            continue
        key = odds_snapshot_key(
            event_id=event.id,
            provider=provider,
            bookmaker=odd.bookmaker,
            market=odd.market,
            selection=odd.selection,
            point=odd.point,
            observed_at=odd.timestamp,
        )
        status, reason = validations[index]
        freshness, age_seconds = classify_odds_freshness(
            odd.timestamp,
            now=now,
            stale_minutes=settings.odds_stale_minutes,
            expired_minutes=settings.odds_expired_minutes,
        )
        existing = await session.scalar(
            select(OddsSnapshot).where(OddsSnapshot.snapshot_key == key)
        )
        if existing is not None:
            if existing.decimal_odds != odd.decimal_odds:
                existing.validation_status = "SUSPECT"
                existing.validation_reason = "Conflicting price at identical provider timestamp"
                existing.is_outlier = True
                duplicate += 1
                continue
            existing.validation_status = status
            existing.is_outlier = status != "VALID"
            existing.validation_reason = reason
            existing.freshness_status = freshness
            existing.odds_age_seconds = age_seconds
            existing.ingestion_run_id = run_id
            duplicate += 1
            continue
        session.add(
            OddsSnapshot(
                event_id=event.id,
                provider=provider,
                bookmaker=odd.bookmaker,
                market=odd.market,
                selection=odd.selection,
                snapshot_key=key,
                decimal_odds=odd.decimal_odds,
                point=odd.point,
                observed_at=odd.timestamp,
                source_timestamp=odd.timestamp,
                fetched_at=now,
                is_live=odd.is_live or odd.timestamp >= event.start_time.replace(tzinfo=UTC),
                is_outlier=status != "VALID",
                validation_status=status,
                validation_reason=reason,
                freshness_status=freshness,
                odds_age_seconds=age_seconds,
                ingestion_run_id=run_id,
            )
        )
        inserted += 1
    await session.flush()
    return inserted, duplicate, event_cache
