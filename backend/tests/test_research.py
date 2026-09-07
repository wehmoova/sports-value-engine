"""Synthetic inputs below are isolated unit fixtures, never production records."""

from copy import deepcopy
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.backtesting.walk_forward import walk_forward_splits
from app.core.config import Settings
from app.database.base import Base
from app.database.session import SessionLocal, engine
from app.models.research import ResearchArtifact
from app.providers.retry import retry_delay
from app.research.backfill import days, persist_result
from app.research.features import build_dataset, build_sample, eligible_history, timestamp
from app.research.production import infer
from app.research.validation import (
    probabilities,
    promotion_checks,
    scores,
    train_baseline,
    validate,
)


@pytest.mark.asyncio
async def test_paginated_backfill_resumes_after_failure_and_rerun_skips(monkeypatch):
    import app.research.backfill as module

    class Provider:
        accessible_league_ids = [999999]
        last_status_code = 200
        last_pagination = {}
        calls = []
        failed_once = False

        def __init__(self, config):
            pass

        async def discover_leagues(self):
            return []

        async def _request(self, path, params):
            page = int(params["page"])
            self.calls.append(page)
            if page == 2 and not Provider.failed_once:
                Provider.failed_once = True
                raise RuntimeError("unit-test transient failure")
            self.last_pagination = {"has_more": page == 1}
            return []

        def _records(self, rows):
            return rows

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    monkeypatch.setattr(module, "SportmonksFootballProvider", Provider)
    monkeypatch.setattr(module.settings, "backfill_request_delay_seconds", 0)
    first = await module.backfill("football", date(2001, 1, 1), date(2001, 1, 1))
    assert first["status"] == "FAILED"
    second = await module.backfill("football", date(2001, 1, 1), date(2001, 1, 1))
    assert second["status"] == "COMPLETED"
    assert Provider.calls == [1, 2, 2]
    third = await module.backfill("football", date(2001, 1, 1), date(2001, 1, 1))
    assert third["skipped_pages"] == 2
    assert Provider.calls == [1, 2, 2]


def histories(count=120):
    rows = []
    for i in range(count):
        at = datetime(2020, 1, 1, tzinfo=UTC) + timedelta(days=i)
        rows.append(
            {
                "event_id": str(i),
                "artifact_id": str(i),
                "sport": "tennis_atp",
                "start": at.isoformat(),
                "available_at": (at + timedelta(hours=3)).isoformat(),
                "home": "a",
                "away": "b",
                "outcome": i % 2,
                "surface": "Clay",
                "competition": "competition",
            }
        )
    return rows


def test_future_results_equal_timestamps_and_late_corrections_excluded():
    rows = histories(20)
    target = rows[-1]
    before = build_sample(target, rows, 3, 3)
    assert before is not None
    changed = deepcopy(rows)
    changed[-1]["outcome"] = 1 - changed[-1]["outcome"]
    assert build_sample(target, changed, 3, 3)["features"] == before["features"]
    correction = {**rows[0], "available_at": target["start"], "outcome": 1}
    assert eligible_history(rows + [correction], timestamp(target["start"]))[0] == rows[0]
    assert target["artifact_id"] not in before["source_ids"]


def test_backfilled_today_does_not_pretend_past_availability():
    rows = histories()
    for row in rows:
        row["available_at"] = datetime.now(UTC).isoformat()
    result = build_dataset(rows, 3, 3)
    assert result["samples"] == [] and result["status"] == "INSUFFICIENT_DATA"


def test_missing_surface_is_not_filled_with_overall_elo():
    rows = histories(15)
    rows[-1]["surface"] = None
    sample = build_sample(rows[-1], rows, 3, 3)
    assert sample is not None
    assert probabilities(sample["features"], "tennis_surface_elo") is None
    assert sample["features"]["ranking_delta"] is None
    assert sample["features"]["xg"] is None


def test_training_and_calibration_precede_holdout_and_do_not_read_its_labels():
    dataset = build_dataset(histories(), 3, 3)
    trained = train_baseline(dataset, "tennis_elo")
    assert trained["status"] == "EXPERIMENTAL"
    changed = deepcopy(dataset)
    for sample in changed["samples"]:
        if sample["start"] >= trained["test_start"]:
            sample["outcome"] = 1 - sample["outcome"]
    assert train_baseline(changed, "tennis_elo") == trained
    report = validate(dataset, trained)
    assert report["metrics"]["sample_size"] > 0
    assert set(trained["training_ids"]).isdisjoint(r["event_id"] for r in report["out_of_sample"])
    assert not all(promotion_checks(report, Settings(_env_file=None)).values())


def test_insufficient_sample_never_trains():
    assert train_baseline({"samples": []}, "tennis_elo")["status"] == "INSUFFICIENT_DATA"


def test_metrics_and_nonfinite_promotion_fail_closed():
    assert scores([([0.6, 0.4], 0)])["brier"] == pytest.approx(0.16)
    assert scores([])["brier"] is None
    report = {
        "status": "EVALUATED",
        "metrics": {"sample_size": 1000, "brier": float("nan"), "log_loss": 0.2, "ece": 0.01},
    }
    assert not promotion_checks(report, Settings(_env_file=None))["brier"]


def test_equal_kickoff_groups_never_cross_fold_boundary():
    at = datetime(2020, 1, 1, tzinfo=UTC)
    times = [at, at, at + timedelta(days=1), at + timedelta(days=1), at + timedelta(days=2)]
    for fold in walk_forward_splits(times, min_train_size=1, test_size=1):
        assert max(times[i] for i in fold.train_indices) < min(times[i] for i in fold.test_indices)


def test_backfill_date_boundaries_and_retry_after():
    assert len(days(date(2020, 1, 1), date(2020, 1, 3))) == 3
    with pytest.raises(ValueError):
        days(date.today(), date.today())
    assert retry_delay("120", 0) == 120


@pytest.mark.asyncio
async def test_history_is_idempotent_and_inference_is_empty_without_production_model():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    raw = {
        "event_key": "research-unit-test",
        "event_date": "2020-01-01",
        "event_time": "12:00",
        "event_first_player": "Research Test A",
        "event_second_player": "Research Test B",
        "first_player_key": "research-a",
        "second_player_key": "research-b",
        "event_type_type": "ATP Singles",
        "tournament_name": "Research unit fixture",
        "tournament_key": "research-test",
        "event_status": "Finished",
        "event_winner": "First Player",
    }
    async with SessionLocal() as session:
        assert await persist_result(session, raw, "api_tennis", "first")
        assert not await persist_result(session, raw, "api_tennis", "second")
        count = await session.scalar(
            select(func.count())
            .select_from(ResearchArtifact)
            .where(
                ResearchArtifact.kind == "history",
                ResearchArtifact.artifact_key.like("api_tennis:research-unit-test:%"),
            )
        )
        assert count == 1
        assert await infer(session, "test-no-production") == (0, 0)
        await session.rollback()
