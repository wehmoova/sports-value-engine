"""Isolated regression fixtures; never written to the production database."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from test_research import histories

from app.database.base import Base
from app.database.session import SessionLocal, engine
from app.models import TennisStatistic
from app.research.context import load_context_snapshots
from app.research.features import build_sample, eligible_context, timestamp
from app.services.football_sync import normalize_standings, sync_football_statistics
from app.services.ingestion import upsert_event
from app.services.tennis_sync import normalize_tennis_fixture, sync_tennis_statistics


def context_for(target, kind="tennis_ranking"):
    earlier = (timestamp(target["start"]) - timedelta(hours=2)).isoformat()
    return [
        {
            "snapshot_id": f"{kind}-{side}",
            "source_table": "tennis_statistics",
            "event_id": target["event_id"],
            "kind": kind,
            "side": side,
            "observed_at": earlier,
            "fetched_at": earlier,
            "source_updated_at": None,
            "source_provider": "api_tennis",
            "provider_entity_id": side,
            "raw_payload_hash": side * 16,
            "ingestion_run_id": "test-run",
            "post_match": False,
            "ranking": rank,
            "ranking_points": 100,
            "sample_size": 10,
            "goals_per_match": 1.5,
            "goals_against_per_match": 1,
            "standing_position": rank,
            "standing_points": 30,
        }
        for side, rank in (("home", 5), ("away", 20))
    ]


@pytest.mark.parametrize("field", ["observed_at", "fetched_at", "source_updated_at"])
@pytest.mark.parametrize("offset", [0, 1])
def test_each_timestamp_must_be_strictly_before_cutoff(field, offset):
    rows = histories(25)
    target = rows[-1]
    context = context_for(target)
    context[1][field] = (timestamp(target["start"]) + timedelta(seconds=offset)).isoformat()
    sample = build_sample(target, rows, 3, 3, context)
    assert sample["features"]["ranking_delta"] is None
    assert sample["context_source_ids"] == []


@pytest.mark.parametrize("bad", [None, "", "not-a-date", "2020-01-01T12:00:00"])
def test_invalid_required_timestamps_are_excluded(bad):
    rows = histories(25)
    context = context_for(rows[-1])
    context[1]["fetched_at"] = bad
    assert build_sample(rows[-1], rows, 3, 3, context)["features"]["ranking_delta"] is None


@pytest.mark.parametrize("bad", [0, -1, 1.5, float("nan"), float("inf"), True])
def test_invalid_rank_is_not_a_feature(bad):
    rows = histories(25)
    context = context_for(rows[-1])
    context[1]["ranking"] = bad
    assert build_sample(rows[-1], rows, 3, 3, context)["features"]["ranking_delta"] is None


def test_provenance_and_latest_availability_include_used_context_only():
    rows = histories(25)
    context = context_for(rows[-1])
    sample = build_sample(rows[-1], rows, 3, 3, context)
    assert len(sample["context_provenance"]) == 2
    assert sample["context_provenance"][0]["ingestion_run_id"] == "test-run"
    assert sample["latest_source_available_at"] == context[0]["fetched_at"]
    assert set(sample["context_source_ids"]).issubset(sample["source_ids"])
    for mutation in ({"post_match": True}, {"event_id": "unrelated"}):
        rejected = deepcopy(context)
        rejected[1].update(mutation)
        assert build_sample(rows[-1], rows, 3, 3, rejected)["context_source_ids"] == []


def test_same_time_conflicts_are_order_independent():
    target = histories(25)[-1]
    context = context_for(target)
    conflict = {**context[0], "snapshot_id": "conflicting", "ranking": 50}
    for records in (context + [conflict], [conflict] + context):
        eligible = eligible_context(records, target["event_id"], timestamp(target["start"]))
        assert [row["side"] for row in eligible] == ["away"]


def test_football_standings_gates_and_xg_remain_absent():
    rows = histories(25)
    for row in rows:
        row.update(sport="football", home_score=2, away_score=1, outcome=0)
    context = context_for(rows[-1], "football_team")
    sample = build_sample(rows[-1], rows, 3, 3, context)
    assert sample["features"]["standing_position_delta"] == 15
    assert sample["features"]["team_goals_for_delta"] == 0
    assert sample["features"]["xg"] is None
    context[0]["sample_size"] = 0
    assert build_sample(rows[-1], rows, 3, 3, context)["features"]["team_goals_for_delta"] is None
    context[1]["source_updated_at"] = rows[-1]["start"]
    assert (
        build_sample(rows[-1], rows, 3, 3, context)["features"]["standing_position_delta"] is None
    )


def test_standings_with_missing_nested_objects_and_ambiguous_groups():
    assert normalize_standings([{"team": None, "participant": None}]) == {}
    assert (
        normalize_standings(
            [{"participant_id": 1, "position": 1}, {"participant_id": 1, "position": 5}]
        )
        == {}
    )
    value = normalize_standings(
        [{"participant_id": 1, "position": float("nan"), "played": float("inf")}]
    )["1"]
    assert value["position"] is None and value["played"] is None


@pytest.mark.asyncio
async def test_missing_season_does_not_request_guessed_standings():
    provider = AsyncMock()
    async with SessionLocal() as session:
        count = await sync_football_statistics(
            session,
            provider,
            "sportmonks",
            [(None, {"league_id": 1, "participants": []})],
            "test",
            1,
        )
    assert count == 0
    provider.get_standings.assert_not_called()
    provider.get_team_stats.assert_not_called()


@pytest.mark.asyncio
async def test_ranking_change_hashes_tour_isolation_and_context_identity():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    start = datetime.now(UTC) + timedelta(days=4)
    raw = {
        "event_key": "pit-test-event",
        "event_date": start.date().isoformat(),
        "event_time": "12:00",
        "event_first_player": "PIT A",
        "event_second_player": "PIT B",
        "first_player_key": "pit-a",
        "second_player_key": "pit-b",
        "tournament_key": "pit-tournament",
        "tournament_name": "ATP PIT test",
        "event_status": "SCHEDULED",
    }
    normalized = normalize_tennis_fixture(raw)
    atp = [
        {"player_key": "pit-a", "place": 5, "points": 0},
        {"player_key": "pit-b", "place": 10, "points": 100},
    ]
    wta = [{"player_key": "pit-a", "place": 200, "points": 2}]
    provider = AsyncMock()
    provider.get_rankings.side_effect = [
        atp,
        wta,
        atp,
        wta,
        [{**atp[0], "place": 6}, atp[1]],
        wta,
        atp,
        wta,
    ]
    async with SessionLocal() as session:
        event = await upsert_event(
            session, normalized=normalized, provider="api_tennis", run_id="pit"
        )
        fixtures = [(event, raw, normalized)]
        assert await sync_tennis_statistics(session, provider, fixtures, "first") == 2
        assert await sync_tennis_statistics(session, provider, fixtures, "repeat") == 0
        assert await sync_tennis_statistics(session, provider, fixtures, "changed") == 1
        context = await load_context_snapshots(session, "tennis_atp", [event.id])
        assert len(context) == 3
        assert {r["ranking"] for r in context if r["side"] == "home"} == {5, 6}
        assert all(r["ranking_points"] == 0 for r in context if r["side"] == "home")
        assert await load_context_snapshots(session, "tennis_wta", [event.id]) == []
        snapshot = await session.scalar(
            select(TennisStatistic).where(
                TennisStatistic.event_id == event.id, TennisStatistic.side == "away"
            )
        )
        snapshot.player_id = event.home_entity_id
        await session.flush()
        assert len(await load_context_snapshots(session, "tennis_atp", [event.id])) == 2
        snapshot.player_id = event.away_entity_id
        snapshot.raw_payload_hash = "tampered"
        await session.flush()
        assert len(await load_context_snapshots(session, "tennis_atp", [event.id])) == 2
        # Restoring an earlier rank is a new observation, not a duplicate of the
        # original snapshot. Its availability must not revert to the earlier time.
        assert await sync_tennis_statistics(session, provider, fixtures, "reverted") == 2
        latest = list(
            await session.scalars(
                select(TennisStatistic)
                .where(TennisStatistic.event_id == event.id, TennisStatistic.side == "home")
                .order_by(TennisStatistic.observed_at)
            )
        )
        assert [row.ranking for row in latest] == [5, 6, 5]
        assert latest[-1].observed_at > latest[0].observed_at
        await session.rollback()
