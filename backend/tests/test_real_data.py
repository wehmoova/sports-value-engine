from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.analytics.value.engine import classify_odds_freshness, classify_odds_prices
from app.core.config import Settings, settings
from app.database.session import SessionLocal
from app.main import app
from app.models import AnalysisRun, Event, OddsSnapshot
from app.providers.base import NormalizedEvent, NormalizedOdd, ProviderBatch
from app.services.analysis import create_analysis_run, run_analysis
from app.services.ingestion import persist_odds_batch
from app.services.job_lock import job_lock


@pytest.mark.parametrize(
    "overrides",
    [
        {"database_url": "sqlite+aiosqlite:///:memory:"},
        {"enable_mock_data": True},
        {"data_mode": "simulation", "enable_simulation": True},
    ],
)
def test_production_guards(overrides: dict) -> None:
    values = {
        "environment": "production",
        "database_url": "postgresql://user:pass@db/sve",
        **overrides,
    }
    with pytest.raises(ValueError):
        Settings(_env_file=None, **values)


def test_provider_fallback_never_simulates() -> None:
    config = Settings(
        _env_file=None,
        football_provider="sportmonks",
        sportmonks_api_token=None,
        api_football_key="test-key",
    )
    assert config.football_provider == "api_football"
    assert config.data_mode == "real" and not config.enable_simulation


def test_identical_prices_are_valid_and_extreme_price_is_rejected() -> None:
    assert all(v.status == "VALID" for v in classify_odds_prices([1.9, 1.9, 1.9]))
    assert classify_odds_prices([1.9, 1.92, 4.8])[-1].status == "REJECTED"


def test_expired_and_future_odds_fail_closed() -> None:
    now = datetime.now(UTC)
    assert classify_odds_freshness(now - timedelta(days=1), now=now)[0] == "EXPIRED"
    assert classify_odds_freshness(now + timedelta(hours=1), now=now)[0] == "EXPIRED"


def test_empty_real_api_and_cloud_health(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("the_odds_api_key", "api_football_key", "sportmonks_api_token", "api_tennis_key"):
        monkeypatch.setattr(settings, key, None)
    with TestClient(app) as client:
        diagnostics = client.get("/api/v1/system/data-diagnostics").json()
        assert diagnostics["data_mode"] == "real"
        assert diagnostics["mock_events"] == 0
        assert diagnostics["predictions"] == 0
        assert diagnostics["recommendations"] == 0
        health = client.get("/api/v1/system/health").json()
        assert health["bot_status"] == "SETUP_REQUIRED"
        assert all(p["status"] == "NOT_CONFIGURED" for p in health["providers"])


async def test_lock_rejects_overlap_and_releases() -> None:
    async with job_lock("test-lock") as acquired:
        assert acquired
        async with job_lock("test-lock") as duplicate:
            assert not duplicate
    async with job_lock("test-lock") as acquired:
        assert acquired


async def test_sync_is_idempotent() -> None:
    now = datetime.now(UTC)
    event = NormalizedEvent(
        external_id="idempotence-test",
        sport="football",
        competition="Test league",
        home_name="Test home",
        away_name="Test away",
        start_time=now + timedelta(days=1),
        source_timestamp=now,
    )
    odd = NormalizedOdd(
        event_external_id=event.external_id,
        bookmaker="Test book",
        market="MONEYLINE",
        selection=event.home_name,
        decimal_odds=1.9,
        timestamp=now,
    )
    batch = ProviderBatch(events=[event], odds=[odd])
    async with SessionLocal() as session:
        first = await persist_odds_batch(
            session, batch=batch, provider="the_odds_api", run_id="test", settings=settings
        )
        second = await persist_odds_batch(
            session, batch=batch, provider="the_odds_api", run_id="test", settings=settings
        )
        assert first[:2] == (1, 0)
        assert second[:2] == (0, 1)
        assert await session.scalar(select(func.count(OddsSnapshot.id))) == 1
        assert await session.scalar(select(func.count(Event.id))) == 1
        await session.rollback()


async def test_missing_keys_do_not_produce_predictions(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("the_odds_api_key", "api_football_key", "sportmonks_api_token", "api_tennis_key"):
        monkeypatch.setattr(settings, key, None)
    run, created = await create_analysis_run("TEST")
    assert created
    second, duplicate = await create_analysis_run("TEST")
    assert not duplicate and second.id == run.id
    await run_analysis(run.id)
    async with SessionLocal() as session:
        final = await session.get(AnalysisRun, run.id)
        assert final is not None and final.status == "FAILED"
        assert final.predictions_created == 0
