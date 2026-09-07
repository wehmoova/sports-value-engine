"""Atomic date/league/page checkpoints, immutable raw results and conservative identities."""

import asyncio
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database.session import SessionLocal
from app.models import FootballStatistic, TennisStatistic
from app.models.research import ResearchArtifact
from app.providers.football.sportmonks import SportmonksFootballProvider
from app.providers.odds.the_odds_api import ProviderError, payload_hash
from app.providers.tennis.api_tennis import ApiTennisProvider
from app.research.store import artifact
from app.services.football_sync import normalize_football_fixture
from app.services.ingestion import upsert_event
from app.services.job_lock import job_lock
from app.services.tennis_sync import normalize_tennis_fixture


def days(start: date, end: date) -> list[date]:
    if start > end or end >= datetime.now(UTC).date():
        raise ValueError("Use a nonempty historical range ending before today")
    if (end - start).days > 3660:
        raise ValueError("Maximum backfill range is ten years")
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


async def persist_result(
    session: AsyncSession, raw: dict[str, Any], provider: str, run_id: str
) -> bool:
    normalized = (
        normalize_football_fixture(raw, provider)
        if provider == "sportmonks"
        else normalize_tennis_fixture(raw)
    )
    if normalized.status != "FINAL":
        return False
    if not normalized.home_external_id or not normalized.away_external_id:
        raise ValueError("Historical participants require provider IDs")
    if normalized.start_time >= datetime.now(UTC):
        raise ValueError("Future final result")
    if provider == "sportmonks":
        for score in (normalized.home_score, normalized.away_score):
            if score is None or not 0 <= score <= 30 or score != int(score):
                raise ValueError("Invalid regulation score")
        assert normalized.home_score is not None and normalized.away_score is not None
        outcome = (
            0
            if normalized.home_score > normalized.away_score
            else 1
            if normalized.home_score == normalized.away_score
            else 2
        )
    else:
        if normalized.winner_name not in {normalized.home_name, normalized.away_name}:
            raise ValueError("Final match has no verified winner")
        outcome = 0 if normalized.winner_name == normalized.home_name else 1
    event = await upsert_event(session, normalized=normalized, provider=provider, run_id=run_id)
    now = datetime.now(UTC)
    digest = payload_hash(raw)
    history = await artifact(
        session,
        "history",
        normalized.sport,
        {
            "event_id": event.id,
            "provider": provider,
            "external_id": normalized.external_id,
            "start": normalized.start_time.isoformat(),
            "available_at": now.isoformat(),
            "availability_basis": "FIRST_OBSERVED_FINAL",
            "fetched_at": now.isoformat(),
            "home": event.home_entity_id,
            "away": event.away_entity_id,
            "competition": event.competition_id,
            "surface": normalized.surface,
            "home_score": normalized.home_score,
            "away_score": normalized.away_score,
            "outcome": outcome,
            "raw_hash": digest,
            "raw": raw,
            "run_id": run_id,
        },
        key=f"{provider}:{normalized.external_id}:{digest}",
    )
    # No current rankings/standings are assigned to historical match dates.
    # Raw post-match stats remain available for inspection, not pre-match features.
    values = raw.get("statistics")
    if values:
        for side, participant in (("home", event.home_entity_id), ("away", event.away_entity_id)):
            if provider == "sportmonks":
                football_existing = await session.scalar(
                    select(FootballStatistic.id).where(
                        FootballStatistic.event_id == event.id,
                        FootballStatistic.side == side,
                        FootballStatistic.raw_payload_hash == digest,
                    )
                )
                if football_existing is None:
                    external = (
                        normalized.home_external_id
                        if side == "home"
                        else normalized.away_external_id
                    )
                    side_values = [
                        v
                        for v in values
                        if isinstance(v, dict) and str(v.get("participant_id")) == external
                    ]
                    if side_values:
                        session.add(
                            FootballStatistic(
                                event_id=event.id,
                                team_id=participant,
                                side=side,
                                sample_size=1,
                                payload={"fixture_statistics": side_values, "post_match": True},
                                source_provider=provider,
                                provider_entity_id=external,
                                raw_payload_hash=digest,
                                observed_at=now,
                                fetched_at=now,
                                ingestion_run_id=run_id,
                            )
                        )
            else:
                tennis_existing = await session.scalar(
                    select(TennisStatistic.id).where(
                        TennisStatistic.event_id == event.id,
                        TennisStatistic.side == side,
                        TennisStatistic.raw_payload_hash == digest,
                    )
                )
                if tennis_existing is None:
                    session.add(
                        TennisStatistic(
                            event_id=event.id,
                            player_id=participant,
                            side=side,
                            sample_size=1,
                            payload={"fixture": raw, "post_match": True},
                            source_provider=provider,
                            provider_entity_id=(
                                normalized.home_external_id
                                if side == "home"
                                else normalized.away_external_id
                            ),
                            raw_payload_hash=digest,
                            observed_at=now,
                            fetched_at=now,
                            ingestion_run_id=run_id,
                        )
                    )
    return bool(history.payload["run_id"] == run_id)


async def backfill(sport: str, start: date, end: date, max_pages: int = 100) -> dict[str, Any]:
    dates = days(start, end)
    if max_pages < 1:
        raise ValueError("max_pages must be positive")
    if not settings.is_real_mode or settings.enable_mock_data:
        raise ValueError("Historical backfill requires real mode")
    async with job_lock("analysis-execute") as acquired:
        if not acquired:
            return {"status": "BUSY", "resume": True}
        football = SportmonksFootballProvider(settings) if sport == "football" else None
        tennis = ApiTennisProvider(settings) if sport == "tennis" else None
        if football:
            await football.discover_leagues()
        leagues = football.accessible_league_ids if football else [0]
        completed = inserted = skipped = 0
        for day in dates:
            for league in leagues:
                page = 1
                while True:
                    key = f"v1:{sport}:{league}:{day}:{page}"
                    async with SessionLocal() as session:
                        checkpoint = await artifact(
                            session,
                            "backfill_page",
                            sport,
                            {"attempts": 0},
                            key=key,
                            status="QUEUED",
                        )
                        if checkpoint.status == "COMPLETED":
                            skipped += 1
                            if not checkpoint.payload["has_more"]:
                                break
                            page += 1
                            continue
                        if completed >= max_pages:
                            return {
                                "status": "PAUSED",
                                "pages": completed,
                                "inserted": inserted,
                                "resume_key": key,
                            }
                        attempt = int(checkpoint.payload.get("attempts", 0)) + 1
                        run_id = str(uuid4())
                        checkpoint.status = "RUNNING"
                        checkpoint.payload = {
                            "attempts": attempt,
                            "run_id": run_id,
                            "started_at": datetime.now(UTC).isoformat(),
                        }
                        await session.commit()
                        try:
                            await asyncio.sleep(settings.backfill_request_delay_seconds)
                            if football:
                                path = f"fixtures/between/{day}/{day}"
                                params = {
                                    "filters": f"fixtureLeagues:{league}",
                                    "page": str(page),
                                    "include": "participants;league;state;scores;statistics.type",
                                }
                                try:
                                    raw_rows = await football._request(path, params)
                                except PermissionError:
                                    if football.last_status_code != 403:
                                        raise
                                    params["include"] = "participants;league;state;scores"
                                    raw_rows = await football._request(path, params)
                                rows = football._records(raw_rows)
                                has_more = bool(football.last_pagination.get("has_more"))
                                if any(int(r.get("league_id", -1)) != league for r in rows):
                                    raise ProviderError("Provider returned unexpected league")
                            else:
                                assert tennis is not None
                                at = datetime.combine(day, datetime.min.time(), tzinfo=UTC)
                                rows = await tennis.get_matches(at, at)
                                # API Tennis documents no page cursor. One UTC day is a
                                # resumable date partition, not an invented page parameter.
                                has_more = False
                            rejected = []
                            new = 0
                            for raw in rows:
                                try:
                                    async with session.begin_nested():
                                        new += int(
                                            await persist_result(
                                                session,
                                                raw,
                                                "sportmonks" if football else "api_tennis",
                                                run_id,
                                            )
                                        )
                                except (ValueError, TypeError, KeyError):
                                    rejected.append(
                                        str(raw.get("id", raw.get("event_key", "unknown")))
                                    )
                            checkpoint.status = "COMPLETED"
                            checkpoint.payload = {
                                **checkpoint.payload,
                                "has_more": has_more,
                                "records_received": len(rows),
                                "inserted": new,
                                "rejected_ids": rejected,
                                "payload_hash": payload_hash(rows),
                                "http_status": (
                                    football.last_status_code
                                    if football
                                    else tennis.last_status_code
                                    if tennis
                                    else None
                                ),
                                "finished_at": datetime.now(UTC).isoformat(),
                            }
                            await artifact(
                                session, "backfill_attempt", sport, checkpoint.payload, key=run_id
                            )
                            await session.commit()
                            inserted += new
                            completed += 1
                        except Exception as exc:
                            await session.rollback()
                            failed_checkpoint = await session.scalar(
                                select(ResearchArtifact).where(
                                    ResearchArtifact.kind == "backfill_page",
                                    ResearchArtifact.artifact_key == key,
                                )
                            )
                            assert failed_checkpoint is not None
                            failed_checkpoint.status = "FAILED"
                            failed_checkpoint.payload = {
                                "attempts": attempt,
                                "run_id": run_id,
                                "error_type": type(exc).__name__,
                                "finished_at": datetime.now(UTC).isoformat(),
                            }
                            await artifact(
                                session,
                                "backfill_attempt",
                                sport,
                                failed_checkpoint.payload,
                                key=run_id,
                                status="FAILED",
                            )
                            await session.commit()
                            return {
                                "status": "FAILED",
                                "resume_key": key,
                                "error_type": type(exc).__name__,
                            }
                        if not has_more:
                            break
                        page += 1
                        if page > 1000:
                            raise ProviderError("Pagination safety bound exceeded")
        return {
            "status": "COMPLETED",
            "pages": completed,
            "skipped_pages": skipped,
            "inserted": inserted,
        }
