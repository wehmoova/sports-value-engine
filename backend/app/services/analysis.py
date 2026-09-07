from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.core.config import settings
from app.database.session import SessionLocal
from app.models import (
    AnalysisRun,
    AnalysisRunStep,
    ApiLog,
    ProviderPayloadAudit,
    ProviderStatus,
)
from app.providers.football import ApiFootballProvider, SportmonksFootballProvider
from app.providers.odds import TheOddsApiProvider
from app.providers.tennis import ApiTennisProvider
from app.services.football_sync import sync_football_data
from app.services.ingestion import persist_odds_batch
from app.services.job_lock import job_lock
from app.services.settlement import settle_finished_events
from app.services.tennis_sync import sync_tennis_data

ANALYSIS_STEPS = (
    "SYNC_ODDS",
    "SYNC_FOOTBALL",
    "SYNC_TENNIS",
    "SETTLEMENT",
    "FEATURE_ENGINEERING",
    "MODEL_VALIDATION",
    "VALUE_ELIGIBILITY",
    "PERSIST_OUTPUT",
)


async def create_analysis_run(
    trigger: str = "MANUAL", job_type: str = "daily_analysis"
) -> tuple[AnalysisRun, bool]:
    async with job_lock("analysis-enqueue") as acquired:
        if not acquired:
            raise RuntimeError("Job queue is busy; retry shortly")
        return await _create_analysis_run(trigger, job_type)


async def _create_analysis_run(trigger: str, job_type: str) -> tuple[AnalysisRun, bool]:
    async with SessionLocal() as session:
        active = await session.scalar(
            select(AnalysisRun).where(AnalysisRun.status.in_(["QUEUED", "RUNNING"]))
        )
        if active is not None:
            return active, False
        run = AnalysisRun(
            status="QUEUED",
            trigger=trigger,
            job_type=job_type,
            deployment_version=settings.deployment_version,
            model_version="NO_PRODUCTION_MODEL",
        )
        session.add(run)
        await session.flush()
        session.add_all(
            [AnalysisRunStep(analysis_run_id=run.id, step_name=name) for name in ANALYSIS_STEPS]
        )
        await session.commit()
        await session.refresh(run)
        return run, True


async def _set_step(
    run_id: str,
    step_name: str,
    status: str,
    *,
    records: int = 0,
    error: str | None = None,
) -> None:
    async with SessionLocal() as session:
        step = await session.scalar(
            select(AnalysisRunStep).where(
                AnalysisRunStep.analysis_run_id == run_id,
                AnalysisRunStep.step_name == step_name,
            )
        )
        if step is None:
            step = AnalysisRunStep(analysis_run_id=run_id, step_name=step_name)
            session.add(step)
        now = datetime.now(UTC)
        step.status = status
        if status == "RUNNING":
            step.started_at = now
        if status in {"COMPLETED", "FAILED", "SKIPPED"}:
            step.finished_at = now
        step.records_processed = records
        step.error = error[:1000] if error else None
        await session.commit()


async def _update_provider(
    *,
    name: str,
    configured: bool,
    status: str,
    records: int = 0,
    latency_ms: float | None = None,
    error: str | None = None,
    quota_remaining: int | None = None,
    quota_used: int | None = None,
    request_cost: int | None = None,
    sports: list[str] | None = None,
) -> None:
    async with SessionLocal() as session:
        item = await session.scalar(
            select(ProviderStatus).where(ProviderStatus.provider_name == name)
        )
        if item is None:
            item = ProviderStatus(provider_name=name)
            session.add(item)
        now = datetime.now(UTC)
        item.configured = configured
        item.status = status
        item.last_request_at = now if configured else item.last_request_at
        item.last_response_at = now if configured else item.last_response_at
        item.last_error = error[:1000] if error else None
        item.latency_ms = latency_ms
        item.records_received = records
        item.rate_limit_remaining = quota_remaining
        item.rate_limit_used = quota_used
        item.last_request_cost = request_cost
        item.sports_supplied = sports or []
        if status == "ONLINE":
            item.last_success = now
            item.data_freshness_seconds = 0
        session.add(
            ApiLog(
                provider_name=name,
                endpoint="SCHEDULED_SYNC",
                status_code=200 if status == "ONLINE" else None,
                latency_ms=latency_ms,
                occurred_at=now,
                error_type="ProviderError" if error else None,
                context={"records": records, "status": status},
            )
        )
        await session.commit()


async def _audit_payload(
    *,
    provider_name: str,
    endpoint: str,
    run_id: str,
    record_count: int,
    payload_hash_value: str | None,
    external_ids: list[str],
) -> None:
    async with SessionLocal() as session:
        now = datetime.now(UTC)
        session.add(
            ProviderPayloadAudit(
                provider_name=provider_name,
                endpoint=endpoint,
                requested_at=now,
                responded_at=now,
                status_code=200,
                record_count=record_count,
                payload_hash=payload_hash_value,
                external_ids=external_ids[:100],
                ingestion_run_id=run_id,
            )
        )
        await session.commit()


async def _sync_odds(run_id: str) -> dict[str, int]:
    if not settings.the_odds_api_key:
        await _update_provider(
            name="The Odds API",
            configured=False,
            status="NOT_CONFIGURED",
            error="Missing server credential: THE_ODDS_API_KEY",
        )
        await _set_step(run_id, "SYNC_ODDS", "SKIPPED", error="THE_ODDS_API_KEY missing")
        return {"events": 0, "odds": 0, "duplicates": 0}
    await _set_step(run_id, "SYNC_ODDS", "RUNNING")
    provider = TheOddsApiProvider(settings)
    try:
        batch = await provider.get_target_odds()
        async with SessionLocal() as session:
            inserted, duplicates, events = await persist_odds_batch(
                session,
                batch=batch,
                provider="the_odds_api",
                run_id=run_id,
                settings=settings,
            )
            await session.commit()
        records = len(batch.events) + inserted
        await _update_provider(
            name="The Odds API",
            configured=True,
            status="ONLINE",
            records=records,
            latency_ms=provider.last_latency_ms,
            quota_remaining=batch.requests_remaining,
            quota_used=batch.requests_used,
            request_cost=batch.last_request_cost,
            sports=batch.requested_sport_keys,
        )
        await _audit_payload(
            provider_name="The Odds API",
            endpoint="GET /sports + /sports/{key}/odds",
            run_id=run_id,
            record_count=records,
            payload_hash_value=batch.payload_hashes[-1] if batch.payload_hashes else None,
            external_ids=[event.external_id for event in batch.events],
        )
        await _set_step(run_id, "SYNC_ODDS", "COMPLETED", records=records)
        return {"events": len(events), "odds": inserted, "duplicates": duplicates}
    except Exception as exc:
        message = str(exc)[:1000]
        await _update_provider(
            name="The Odds API",
            configured=True,
            status="DEGRADED",
            latency_ms=provider.last_latency_ms,
            error=message,
            quota_remaining=provider.requests_remaining,
            quota_used=provider.requests_used,
            request_cost=provider.last_request_cost,
        )
        await _set_step(run_id, "SYNC_ODDS", "FAILED", error=message)
        raise


async def _sync_football(run_id: str) -> dict[str, int]:
    provider_key = settings.football_provider
    configured = settings.football_provider_configured
    provider_name = "Sportmonks" if provider_key == "sportmonks" else "API-Football"
    if not configured:
        credential = "SPORTMONKS_API_TOKEN" if provider_key == "sportmonks" else "API_FOOTBALL_KEY"
        await _update_provider(
            name=provider_name,
            configured=False,
            status="NOT_CONFIGURED",
            error=f"Missing server credential: {credential}",
        )
        await _set_step(run_id, "SYNC_FOOTBALL", "SKIPPED", error=f"{credential} missing")
        return {"events": 0, "statistics": 0, "injuries": 0, "suspensions": 0, "lineups": 0}
    await _set_step(run_id, "SYNC_FOOTBALL", "RUNNING")
    provider = (
        SportmonksFootballProvider(settings)
        if provider_key == "sportmonks"
        else ApiFootballProvider(settings)
    )
    try:
        async with SessionLocal() as session:
            if isinstance(provider, SportmonksFootballProvider):
                from app.services.sportmonks_sync import sync_sportmonks_data

                counts = await sync_sportmonks_data(session, provider, run_id, settings)
            else:
                counts = await sync_football_data(session, provider, provider_key, run_id, settings)
            await session.commit()
        records = sum(counts.values())
        await _update_provider(
            name=provider_name,
            configured=True,
            status="ONLINE" if records else "EMPTY",
            records=records,
            latency_ms=provider.last_latency_ms,
            quota_remaining=getattr(provider, "rate_limit_remaining", None),
            sports=["football"],
        )
        await _audit_payload(
            provider_name=provider_name,
            endpoint="fixtures + statistics + availability",
            run_id=run_id,
            record_count=records,
            payload_hash_value=provider.last_payload_hash,
            external_ids=[],
        )
        await _set_step(run_id, "SYNC_FOOTBALL", "COMPLETED", records=records)
        return counts
    except Exception as exc:
        message = str(exc)[:1000]
        football_status = "DEGRADED"
        if isinstance(provider, SportmonksFootballProvider):
            provider.capabilities["fixtures"] = (
                "FORBIDDEN" if provider.last_status_code == 403 else "FAILED"
            )
            football_status = (
                "DEGRADED"
                if provider.capabilities.get("authentication") == "VERIFIED"
                else "FORBIDDEN"
                if provider.last_status_code == 403
                else "FAILED"
            )
        await _update_provider(
            name=provider_name,
            configured=True,
            status=football_status,
            latency_ms=provider.last_latency_ms,
            error=message,
        )
        await _set_step(run_id, "SYNC_FOOTBALL", "FAILED", error=message)
        raise


async def _sync_tennis(run_id: str) -> dict[str, int]:
    if not settings.tennis_provider_configured:
        await _update_provider(
            name="API Tennis",
            configured=False,
            status="NOT_CONFIGURED",
            error="Missing server credential: API_TENNIS_KEY",
        )
        await _set_step(run_id, "SYNC_TENNIS", "SKIPPED", error="API_TENNIS_KEY missing")
        return {"events": 0, "statistics": 0, "odds": 0}
    await _set_step(run_id, "SYNC_TENNIS", "RUNNING")
    provider = ApiTennisProvider(settings)
    try:
        async with SessionLocal() as session:
            counts = await sync_tennis_data(session, provider, run_id, settings)
            await session.commit()
        records = sum(counts.values())
        await _update_provider(
            name="API Tennis",
            configured=True,
            status="ONLINE",
            records=records,
            latency_ms=provider.last_latency_ms,
            sports=["tennis_atp", "tennis_wta"],
        )
        await _audit_payload(
            provider_name="API Tennis",
            endpoint="get_fixtures + get_standings + get_odds",
            run_id=run_id,
            record_count=records,
            payload_hash_value=provider.last_payload_hash,
            external_ids=[],
        )
        await _set_step(run_id, "SYNC_TENNIS", "COMPLETED", records=records)
        return counts
    except Exception as exc:
        message = str(exc)[:1000]
        await _update_provider(
            name="API Tennis",
            configured=True,
            status="DEGRADED",
            latency_ms=provider.last_latency_ms,
            error=message,
        )
        await _set_step(run_id, "SYNC_TENNIS", "FAILED", error=message)
        raise


async def run_analysis(run_id: str) -> None:
    async with job_lock("analysis-execute") as acquired:
        if not acquired:
            return
        await _run_analysis(run_id)


async def _run_analysis(run_id: str) -> None:
    async with SessionLocal() as session:
        run = await session.get(AnalysisRun, run_id)
        if run is None or run.status != "QUEUED":
            return
        job_type = run.job_type
        run.status = "RUNNING"
        run.started_at = datetime.now(UTC)
        await session.commit()

    errors: list[dict[str, Any]] = []
    totals = {"events": 0, "odds": 0, "statistics": 0}
    for name, sync in (
        ("The Odds API", _sync_odds),
        (settings.football_provider, _sync_football),
        ("API Tennis", _sync_tennis),
    ):
        if job_type == "sync_odds" and sync != _sync_odds:
            await _set_step(
                run_id,
                "SYNC_FOOTBALL" if sync == _sync_football else "SYNC_TENNIS",
                "SKIPPED",
                error="Not part of this job",
            )
            continue
        if job_type in {"sync_events", "sync_statistics", "settle_events"} and sync == _sync_odds:
            await _set_step(run_id, "SYNC_ODDS", "SKIPPED", error="Not part of this job")
            continue
        try:
            result = await sync(run_id)
            totals["events"] += result.get("events", 0)
            totals["odds"] += result.get("odds", 0)
            totals["statistics"] += result.get("statistics", 0)
        except Exception as exc:
            errors.append({"provider": name, "message": str(exc)[:500]})

    await _set_step(run_id, "SETTLEMENT", "RUNNING")
    try:
        async with SessionLocal() as session:
            settled = (
                await settle_finished_events(session)
                if job_type in {"daily_analysis", "settle_events"}
                else 0
            )
            await session.commit()
        await _set_step(
            run_id,
            "SETTLEMENT",
            "SKIPPED",
            records=settled,
            error="No explicit stake ledger; automatic bankroll settlement is disabled",
        )
    except Exception as exc:
        errors.append({"provider": "settlement", "message": str(exc)[:500]})
        await _set_step(run_id, "SETTLEMENT", "FAILED", error=str(exc))

    for step in ("FEATURE_ENGINEERING", "MODEL_VALIDATION", "VALUE_ELIGIBILITY"):
        await _set_step(
            run_id,
            step,
            "SKIPPED",
            error="No validated PRODUCTION model registry entry; no prediction generated.",
        )
    await _set_step(run_id, "PERSIST_OUTPUT", "COMPLETED", records=sum(totals.values()))

    configured_count = sum(
        [
            bool(settings.the_odds_api_key),
            settings.football_provider_configured,
            settings.tennis_provider_configured,
        ]
    )
    if job_type == "sync_odds":
        configured_count = int(bool(settings.the_odds_api_key))
    elif job_type in {"sync_events", "sync_statistics", "settle_events"}:
        configured_count = int(settings.football_provider_configured) + int(
            settings.tennis_provider_configured
        )
    async with SessionLocal() as session:
        run = await session.get(AnalysisRun, run_id)
        if run is None:
            return
        run.finished_at = datetime.now(UTC)
        run.events_processed = totals["events"]
        run.records_processed = sum(totals.values())
        run.predictions_created = 0
        run.value_picks_created = 0
        run.errors = errors
        if configured_count == 0:
            run.status = "FAILED"
            run.log_summary = (
                "No real provider is configured. Set server-side provider credentials; "
                "no demo data or predictions were created."
            )
        elif errors:
            run.status = "PARTIAL"
            run.log_summary = (
                f"Real-data sync persisted {totals['events']} events, {totals['odds']} odds "
                f"and {totals['statistics']} statistic snapshots with provider errors."
            )
        else:
            run.status = "COMPLETED"
            run.log_summary = (
                f"Real-data sync persisted {totals['events']} events, {totals['odds']} odds "
                f"and {totals['statistics']} statistic snapshots. No recommendation was "
                "created because no calibrated production model is registered."
            )
        await session.commit()
