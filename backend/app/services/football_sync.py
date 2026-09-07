from datetime import UTC, datetime, timedelta
from math import isfinite
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import Event, FootballStatistic, Injury, Lineup, Suspension
from app.providers.base import FootballProvider, NormalizedEvent
from app.providers.odds.the_odds_api import ProviderError, payload_hash
from app.services.ingestion import upsert_event


def _datetime(value: object) -> datetime:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=UTC)
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _float(value: object) -> float | None:
    if value is None:
        return None
    try:
        number = float(str(value).replace("%", ""))
        return number if isfinite(number) and not isinstance(value, bool) else None
    except ValueError:
        return None


def _api_football_event(record: dict[str, Any]) -> NormalizedEvent:
    fixture = record.get("fixture", {})
    league = record.get("league", {})
    teams = record.get("teams", {})
    status = str(fixture.get("status", {}).get("short", "NS"))
    normalized_status = "FINAL" if status in {"FT", "AET", "PEN"} else status
    # Standard pre-match football markets settle at regulation time, never penalties.
    goals = record.get("score", {}).get("fulltime") or {}
    if status == "FT" and not goals:
        goals = record.get("goals", {})
    return NormalizedEvent(
        external_id=str(fixture["id"]),
        sport="football",
        competition=str(league.get("name") or "Unknown competition"),
        competition_key=str(league.get("id") or ""),
        home_name=str(teams["home"]["name"]),
        away_name=str(teams["away"]["name"]),
        home_external_id=str(teams["home"]["id"]),
        away_external_id=str(teams["away"]["id"]),
        start_time=_datetime(fixture.get("date") or fixture.get("timestamp")),
        status=normalized_status,
        home_score=_float(goals.get("home")),
        away_score=_float(goals.get("away")),
        round=str(league.get("round")) if league.get("round") else None,
        source_timestamp=datetime.now(UTC),
        raw_payload_hash=payload_hash(record),
    )


def _sportmonks_event(record: dict[str, Any]) -> NormalizedEvent:
    participants = [item for item in record.get("participants", []) if isinstance(item, dict)]
    home = next(
        (item for item in participants if item.get("meta", {}).get("location") == "home"), None
    )
    away = next(
        (item for item in participants if item.get("meta", {}).get("location") == "away"), None
    )
    if home is None or away is None:
        raise ValueError("Sportmonks fixture is missing home/away participants")
    league = record.get("league") or {}
    state = record.get("state") or {}
    state_name = str(state.get("short_name") or state.get("name") or "SCHEDULED").upper()
    status = "FINAL" if state_name in {"FT", "FINISHED"} else state_name
    current_scores = [
        score
        for score in record.get("scores", [])
        if score.get("description") == "CURRENT" and isinstance(score.get("score"), dict)
    ]
    home_score = next(
        (
            _float(score["score"].get("goals"))
            for score in current_scores
            if score["score"].get("participant") == "home"
        ),
        None,
    )
    away_score = next(
        (
            _float(score["score"].get("goals"))
            for score in current_scores
            if score["score"].get("participant") == "away"
        ),
        None,
    )
    return NormalizedEvent(
        external_id=str(record["id"]),
        sport="football",
        competition=str(league.get("name") or f"League {record.get('league_id', 'unknown')}"),
        competition_key=str(record.get("league_id") or league.get("id") or ""),
        home_name=str(home["name"]),
        away_name=str(away["name"]),
        home_external_id=str(home["id"]),
        away_external_id=str(away["id"]),
        start_time=_datetime(record.get("starting_at") or record.get("starting_at_timestamp")),
        status=status,
        home_score=home_score,
        away_score=away_score,
        round=str(record.get("round_id")) if record.get("round_id") else None,
        source_timestamp=datetime.now(UTC),
        source_updated_at=_datetime(record["last_processed_at"])
        if record.get("last_processed_at")
        else None,
        raw_payload_hash=payload_hash(record),
    )


def normalize_football_fixture(record: dict[str, Any], provider_key: str) -> NormalizedEvent:
    if provider_key == "api_football":
        return _api_football_event(record)
    if provider_key == "sportmonks":
        return _sportmonks_event(record)
    raise ValueError(f"unsupported football provider: {provider_key}")


def _team_context(
    record: dict[str, Any], provider_key: str
) -> tuple[str, int, list[tuple[str, str]]]:
    if provider_key == "api_football":
        league = record.get("league", {})
        teams = record.get("teams", {})
        return (
            str(league.get("id") or ""),
            int(league.get("season") or 0),
            [
                ("home", str(teams.get("home", {}).get("id") or "")),
                ("away", str(teams.get("away", {}).get("id") or "")),
            ],
        )
    return (
        str(record.get("league_id") or ""),
        int(record.get("season_id") or 0),
        [
            (
                str(item.get("meta", {}).get("location")),
                str(item.get("id") or ""),
            )
            for item in record.get("participants", [])
            if item.get("meta", {}).get("location") in {"home", "away"}
        ],
    )


def _team_metric(payload: dict[str, Any], path: tuple[str, ...]) -> float | None:
    value: Any = payload
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return _float(value)


def _flatten_standings(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(value, list):
        for item in value:
            rows.extend(_flatten_standings(item))
        return rows
    if not isinstance(value, dict):
        return rows
    league = value.get("league")
    if isinstance(league, dict) and isinstance(league.get("standings"), list):
        return _flatten_standings(league["standings"])
    nested = value.get("standings")
    if isinstance(nested, list):
        return _flatten_standings(nested)
    rows.append(value)
    return rows


def normalize_standings(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    ambiguous: set[str] = set()
    for row in _flatten_standings(rows):
        team = row.get("team")
        if not isinstance(team, dict):
            team = {}
        participant = row.get("participant")
        if not isinstance(participant, dict):
            participant = {}
        team_id = (
            row.get("participant_id")
            or row.get("team_id")
            or team.get("id")
            or participant.get("id")
        )
        if not team_id:
            continue
        position_value = row.get("position")
        if position_value is None:
            position_value = row.get("rank")
        goal_difference_value = row.get("goal_difference")
        if goal_difference_value is None:
            goal_difference_value = row.get("goalDifference")
        if goal_difference_value is None:
            goal_difference_value = row.get("goalsDiff")
        all_stats = row.get("all") if isinstance(row.get("all"), dict) else {}
        position = _float(position_value)
        played = _float(all_stats.get("played") if all_stats else row.get("played"))
        normalized = {
            "position": int(position)
            if position is not None and position > 0 and position.is_integer()
            else None,
            "points": _float(row.get("points")),
            "goal_difference": _float(goal_difference_value),
            "played": int(played)
            if played is not None and played >= 0 and played.is_integer()
            else None,
            "raw": row,
        }
        identity = str(team_id)
        if identity in ambiguous:
            continue
        if identity in result and result[identity] != normalized:
            ambiguous.add(identity)
            result.pop(identity)
            continue
        result[identity] = normalized
    return result


def _set_capability(provider: FootballProvider, key: str, status: str) -> None:
    capabilities = getattr(provider, "capabilities", None)
    if isinstance(capabilities, dict):
        capabilities[key] = status


async def sync_football_events(
    session: AsyncSession,
    provider: FootballProvider,
    provider_key: str,
    run_id: str,
) -> list[tuple[Event, dict[str, Any]]]:
    now = datetime.now(UTC)
    fixtures = await provider.get_fixtures(now - timedelta(days=1), now + timedelta(days=7))
    persisted: list[tuple[Event, dict[str, Any]]] = []
    for record in fixtures:
        try:
            normalized = normalize_football_fixture(record, provider_key)
        except (KeyError, TypeError, ValueError):
            continue
        event = await upsert_event(
            session, normalized=normalized, provider=provider_key, run_id=run_id
        )
        persisted.append((event, record))
    await session.flush()
    return persisted


async def _store_team_statistics(
    session: AsyncSession,
    *,
    event: Event,
    provider: FootballProvider,
    provider_key: str,
    raw_fixture: dict[str, Any],
    run_id: str,
    standings: dict[str, dict[str, Any]],
) -> int:
    league_id, season, sides = _team_context(raw_fixture, provider_key)
    created = 0
    for side, team_external_id in sides:
        if not team_external_id or not league_id or season <= 0:
            continue
        standing = standings.get(team_external_id)
        try:
            team_payload = await provider.get_team_stats(team_external_id, league_id, season)
        except (PermissionError, ProviderError):
            team_payload = {}
        if not team_payload and standing is None:
            continue
        observed_at = datetime.now(UTC)
        snapshot_payload = {
            "team_statistics": team_payload or None,
            "standing": standing,
            "availability_basis": "OBSERVED_PROVIDER_SNAPSHOT",
            "league_id": league_id,
            "season": season,
            "post_match": event.status == "FINAL" or _datetime(event.start_time) <= observed_at,
        }
        digest = payload_hash(snapshot_payload)
        existing = await session.scalar(
            select(FootballStatistic)
            .where(
                FootballStatistic.event_id == event.id,
                FootballStatistic.side == side,
                FootballStatistic.source_provider == provider_key,
                FootballStatistic.payload["availability_basis"].as_string()
                == "OBSERVED_PROVIDER_SNAPSHOT",
            )
            .order_by(FootballStatistic.observed_at.desc(), FootballStatistic.id.desc())
            .limit(1)
        )
        if existing is not None and existing.raw_payload_hash == digest:
            continue
        team_id = event.home_entity_id if side == "home" else event.away_entity_id
        sample = int(
            _team_metric(team_payload, ("fixtures", "played", "total"))
            or _float(standing.get("played") if standing else None)
            or 0
        )
        session.add(
            FootballStatistic(
                event_id=event.id,
                team_id=team_id,
                side=side,
                sample_size=sample,
                goals_per_match=_team_metric(team_payload, ("goals", "for", "average", "total")),
                goals_against_per_match=_team_metric(
                    team_payload, ("goals", "against", "average", "total")
                ),
                xg_per_match=None,
                xga_per_match=None,
                shots_per_match=None,
                shots_on_target_per_match=None,
                form_points=None,
                rest_days=None,
                payload=snapshot_payload,
                observed_at=observed_at,
                source_provider=provider_key,
                provider_entity_id=team_external_id,
                fetched_at=observed_at,
                raw_payload_hash=digest,
                ingestion_run_id=run_id,
            )
        )
        created += 1
    return created


async def sync_football_statistics(
    session: AsyncSession,
    provider: FootballProvider,
    provider_key: str,
    fixtures: list[tuple[Event, dict[str, Any]]],
    run_id: str,
    limit: int,
) -> int:
    created = 0
    standings_cache: dict[tuple[str, int], dict[str, dict[str, Any]]] = {}
    for event, raw in fixtures[:limit]:
        league_id, season, _ = _team_context(raw, provider_key)
        key = (league_id, season)
        if league_id and season > 0 and key not in standings_cache:
            try:
                raw_standings = await provider.get_standings(league_id, season)
                standings_cache[key] = normalize_standings(raw_standings)
                _set_capability(provider, "standings", "AVAILABLE" if raw_standings else "EMPTY")
            except (PermissionError, ProviderError):
                standings_cache[key] = {}
                _set_capability(
                    provider,
                    "standings",
                    "FORBIDDEN" if getattr(provider, "last_status_code", None) == 403 else "FAILED",
                )
        created += await _store_team_statistics(
            session,
            event=event,
            provider=provider,
            provider_key=provider_key,
            raw_fixture=raw,
            run_id=run_id,
            standings=standings_cache.get(key, {}),
        )
    await session.flush()
    return created


async def sync_football_availability(
    session: AsyncSession,
    provider: FootballProvider,
    provider_key: str,
    fixtures: list[tuple[Event, dict[str, Any]]],
    run_id: str,
    limit: int,
) -> tuple[int, int, int]:
    injuries_created = suspensions_created = lineups_created = 0
    for event, raw in fixtures[:limit]:
        external_id = str(
            raw.get("fixture", {}).get("id") if provider_key == "api_football" else raw.get("id")
        )
        injuries = await provider.get_injuries(external_id)
        suspensions = [
            row for row in injuries if "suspend" in str(row).lower() or "card" in str(row).lower()
        ]
        lineups = await provider.get_lineups(external_id)
        existing_injuries = await session.scalar(
            select(Injury.id).where(
                Injury.event_id == event.id,
                Injury.provider == provider_key,
            )
        )
        if existing_injuries is None:
            for row in injuries:
                player = row.get("player", {}) if isinstance(row.get("player"), dict) else {}
                session.add(
                    Injury(
                        event_id=event.id,
                        status="CONFIRMED",
                        detail=str(player.get("reason") or row.get("reason") or "Unavailable"),
                        impact_score=None,
                        provider=provider_key,
                        observed_at=datetime.now(UTC),
                    )
                )
                injuries_created += 1
            for row in suspensions:
                session.add(
                    Suspension(
                        event_id=event.id,
                        reason=str(row.get("reason") or row.get("sideline") or "Suspended"),
                        provider=provider_key,
                        observed_at=datetime.now(UTC),
                    )
                )
                suspensions_created += 1
        existing_lineup = await session.scalar(select(Lineup.id).where(Lineup.event_id == event.id))
        if existing_lineup is None:
            for team in lineups:
                groups = (
                    [
                        ("STARTER", team.get("startXI", [])),
                        ("SUBSTITUTE", team.get("substitutes", [])),
                    ]
                    if provider_key == "api_football"
                    else [("STARTER", [team])]
                )
                for lineup_status, players in groups:
                    for item in players:
                        player = item.get("player", item)
                        name = str(player.get("name") or player.get("display_name") or "Unknown")
                        session.add(
                            Lineup(
                                event_id=event.id,
                                player_name=name,
                                status=lineup_status,
                                position=player.get("pos") or player.get("position"),
                                confirmed=bool(
                                    team.get("formation") or team.get("confirmed", False)
                                ),
                                observed_at=datetime.now(UTC),
                            )
                        )
                        lineups_created += 1
    await session.flush()
    return injuries_created, suspensions_created, lineups_created


async def sync_football_data(
    session: AsyncSession,
    provider: FootballProvider,
    provider_key: str,
    run_id: str,
    settings: Settings,
) -> dict[str, int]:
    fixtures = await sync_football_events(session, provider, provider_key, run_id)
    statistics = await sync_football_statistics(
        session,
        provider,
        provider_key,
        fixtures,
        run_id,
        settings.provider_detail_event_limit,
    )
    injuries, suspensions, lineups = await sync_football_availability(
        session,
        provider,
        provider_key,
        fixtures,
        run_id,
        settings.provider_detail_event_limit,
    )
    return {
        "events": len(fixtures),
        "statistics": statistics,
        "injuries": injuries,
        "suspensions": suspensions,
        "lineups": lineups,
    }
