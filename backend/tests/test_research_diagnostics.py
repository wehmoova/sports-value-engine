"""Isolated regression inputs; no provider substitutes are used in production."""

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select
from test_point_in_time_context import context_for
from test_research import histories

from app.database.base import Base
from app.database.session import SessionLocal, engine
from app.models.research import ResearchArtifact
from app.research.diagnostics import diagnose
from app.research.features import build_dataset, build_sample
from app.services.football_sync import sportmonks_team_metrics, sync_football_statistics


def test_exclusion_uses_actual_history_and_participant_gates():
    rows = histories(205)
    reasons = []
    assert build_sample(rows[199], rows, 200, 10, exclusions=reasons) is None
    assert reasons == ["insufficient_available_history"]
    target = {**rows[-1], "home": "unseen-team"}
    reasons = []
    assert build_sample(target, rows, 200, 10, exclusions=reasons) is None
    assert reasons == ["insufficient_participant_history"]


def test_backfilled_results_cannot_unlock_past_samples_and_xg_is_not_a_gate():
    rows = histories(220)
    for r in rows:
        r.update(sport="football", home_score=2, away_score=1, outcome=0)
    result = build_dataset(rows, 200, 10)
    assert result["samples"]
    assert all(s["features"]["xg"] is None for s in result["samples"])
    assert "xg" in result["missing_features"]
    for r in rows:
        r["available_at"] = datetime.now(UTC).isoformat()
    assert build_dataset(rows, 200, 10)["samples"] == []


def test_target_post_match_statistics_never_enter_features():
    rows = histories(220)
    for r in rows:
        r.update(sport="football", home_score=2, away_score=1, outcome=0)
    target = rows[-1]
    context = context_for(target, "football_team")
    for row in context:
        row.update(post_match=True, goals_per_match=99, xg=99)
    sample = build_sample(target, rows, 200, 10, context)
    assert sample["features"]["team_goals_for_delta"] is None
    assert sample["features"]["xg"] is None
    assert sample["context_source_ids"] == []
    assert target["artifact_id"] not in sample["source_ids"]


@pytest.mark.asyncio
async def test_diagnose_does_not_persist_artifacts():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with SessionLocal() as s:
        before = await s.scalar(select(func.count()).select_from(ResearchArtifact))
        result = await diagnose(s, "football")
        assert result["read_only"] and not s.new and not s.dirty and not s.deleted
        assert before == await s.scalar(select(func.count()).select_from(ResearchArtifact))


@pytest.mark.asyncio
async def test_upcoming_context_is_not_starved_by_final_fixture_order(monkeypatch):
    import app.services.football_sync as module

    now = datetime.now(UTC)
    past = SimpleNamespace(id="past", status="FINAL", start_time=now - timedelta(days=1))
    upcoming = SimpleNamespace(id="next", status="SCHEDULED", start_time=now + timedelta(days=1))
    store = AsyncMock(return_value=2)
    monkeypatch.setattr(module, "_store_team_statistics", store)
    session = SimpleNamespace(flush=AsyncMock())
    await sync_football_statistics(
        session, object(), "sportmonks", [(past, {}), (upcoming, {})], "test", 1
    )
    assert store.call_args.kwargs["event"].id == "next"


def test_sportmonks_details_are_season_scoped_and_never_impute_xg():
    payload = {
        "id": 85,
        "statistics": [
            {
                "team_id": 85,
                "season_id": 12,
                "details": [
                    {"type_id": 27263, "value": {"total": 7}},
                    {"type_id": 52, "value": {"all": {"average": 2.86}}},
                    {"type_id": 88, "value": {"all": {"average": 1.14}}},
                    {"type_id": 5304, "value": {"all": {"average": 99}}},
                ],
            }
        ],
    }
    assert sportmonks_team_metrics(payload, "85", 12) == (7, 2.86, 1.14)
    assert sportmonks_team_metrics(payload, "85", 13) == (0, None, None)
    assert sportmonks_team_metrics(payload, "86", 12) == (0, None, None)
    payload["statistics"][0]["details"] = []
    assert sportmonks_team_metrics(payload, "85", 12) == (0, None, None)


@pytest.mark.asyncio
async def test_dry_run_never_opens_database_or_lock(monkeypatch):
    import app.research.backfill as module

    class Provider:
        accessible_league_ids = [271]
        last_pagination = {}
        calls = []

        def __init__(self, config):
            pass

        async def discover_leagues(self):
            return []

        async def _request(self, path, params):
            self.calls.append(params["page"])
            self.last_pagination = {"has_more": params["page"] == "1"}
            return []

        def _records(self, rows):
            return rows

    def forbidden(*args):
        raise AssertionError("dry-run tried database access")

    monkeypatch.setattr(module, "SportmonksFootballProvider", Provider)
    monkeypatch.setattr(module, "SessionLocal", forbidden)
    monkeypatch.setattr(module, "job_lock", forbidden)
    monkeypatch.setattr(module.settings, "backfill_request_delay_seconds", 0)
    result = await module.backfill(
        "football", date(2020, 1, 1), date(2020, 1, 7), league=271, window_days=7, dry_run=True
    )
    assert Provider.calls == ["1", "2"]
    assert result["database_writes"] == 0 and result["complete"]
    assert result["new_immediate_point_in_time_samples"] is None
    with pytest.raises(ValueError, match="not accessible"):
        await module.backfill(
            "football", date(2020, 1, 1), date(2020, 1, 7), league=999, dry_run=True
        )


@pytest.mark.asyncio
async def test_rate_limit_stops_without_retry(monkeypatch):
    import httpx

    from app.core.config import Settings
    from app.providers.football.sportmonks import SportmonksFootballProvider

    response = httpx.Response(
        429, json={"message": "limit"}, request=httpx.Request("GET", "https://example.invalid")
    )
    request = AsyncMock(return_value=response)
    monkeypatch.setattr(httpx.AsyncClient, "get", request)
    p = SportmonksFootballProvider(Settings(_env_file=None, sportmonks_api_token="test-only"))
    with pytest.raises(PermissionError, match="defer"):
        await p._request("leagues")
    assert request.await_count == 1


@pytest.mark.asyncio
async def test_team_adapter_allowlists_no_xg_and_exact_season():
    from app.core.config import Settings
    from app.providers.football.sportmonks import SportmonksFootballProvider

    p = SportmonksFootballProvider(Settings(_env_file=None, sportmonks_api_token="test-only"))
    p._request = AsyncMock(return_value={"id": 85})
    await p.get_team_stats("85", "271", 27897)
    assert p._request.call_args.args[1] == {
        "include": "statistics.details",
        "filters": "teamStatisticSeasons:27897;teamStatisticDetailTypes:52,88,27263",
    }
