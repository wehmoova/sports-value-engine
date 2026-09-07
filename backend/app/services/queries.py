from datetime import UTC, datetime, timedelta
from math import log
from typing import Any, cast

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.value.engine import classify_odds_freshness
from app.core.config import settings
from app.models import (
    AnalysisRun,
    AnalysisRunStep,
    ApiLog,
    BankrollHistory,
    BetResult,
    CombinationRecommendation,
    Competition,
    Event,
    FootballStatistic,
    ModelPerformance,
    ModelPrediction,
    OddsSnapshot,
    ProviderStatus,
    Recommendation,
    Sport,
    TennisStatistic,
)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


async def recommendation_rows(
    session: AsyncSession,
    *,
    status: str | None = None,
    sport_key: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    query = (
        select(Recommendation, Event, Sport, Competition, ModelPrediction)
        .join(Event, Recommendation.event_id == Event.id)
        .join(Sport, Event.sport_id == Sport.id)
        .outerjoin(Competition, Event.competition_id == Competition.id)
        .outerjoin(ModelPrediction, Recommendation.prediction_id == ModelPrediction.id)
        .where(Event.is_demo.is_(False), Recommendation.is_demo.is_(False))
        .where(Event.data_origin == "REAL", Recommendation.data_origin == "REAL")
        .where(
            ModelPrediction.is_demo.is_(False),
            ModelPrediction.data_origin == "REAL",
            ModelPrediction.is_calibrated.is_(True),
            Event.start_time > datetime.now(UTC),
            Recommendation.odds_timestamp
            >= datetime.now(UTC) - timedelta(minutes=settings.odds_stale_minutes),
        )
        .order_by(desc(Recommendation.expected_value))
        .limit(limit)
    )
    if status:
        query = query.where(Recommendation.status == status)
    if sport_key:
        query = query.where(Sport.key == sport_key)
    result = await session.execute(query)
    return [
        {
            "id": recommendation.id,
            "event_id": event.id,
            "sport": sport.key,
            "sport_name": sport.name,
            "competition": competition.name if competition else "Unknown competition",
            "event": event.name,
            "home_name": event.home_name,
            "away_name": event.away_name,
            "start_time": _iso(event.start_time),
            "market": recommendation.market,
            "selection": recommendation.selection,
            "bookmaker": recommendation.bookmaker,
            "best_odds": recommendation.best_odds,
            "average_odds": recommendation.average_odds,
            "median_odds": recommendation.median_odds,
            "opening_odds": recommendation.opening_odds,
            "model_probability": recommendation.model_probability,
            "market_probability": recommendation.market_probability,
            "fair_odds": recommendation.fair_odds,
            "edge": recommendation.edge,
            "expected_value": recommendation.expected_value,
            "confidence_score": recommendation.confidence_score,
            "data_quality_score": recommendation.data_quality_score,
            "status": recommendation.status,
            "reason_code": recommendation.reason_code,
            "desired_entry_odds": recommendation.desired_entry_odds,
            "odds_timestamp": _iso(recommendation.odds_timestamp),
            "data_origin": recommendation.data_origin,
            "model_version": prediction.model_version if prediction else None,
            "feature_version": prediction.feature_version if prediction else None,
            "probability_low": prediction.probability_low if prediction else None,
            "probability_high": prediction.probability_high if prediction else None,
            "model_components": prediction.components if prediction else {},
            "positive_factors": prediction.explanation_factors if prediction else [],
            "risks": prediction.risk_factors if prediction else [],
        }
        for recommendation, event, sport, competition, prediction in result.all()
    ]


async def event_rows(
    session: AsyncSession, *, sport_key: str | None = None, limit: int = 100
) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    query = (
        select(Event, Sport, Competition)
        .join(Sport, Event.sport_id == Sport.id)
        .outerjoin(Competition, Event.competition_id == Competition.id)
        .where(Event.start_time >= now - timedelta(hours=3))
        .where(Event.is_demo.is_(False), Event.data_origin == "REAL")
        .order_by(Event.start_time)
        .limit(limit)
    )
    if sport_key:
        if sport_key == "tennis":
            query = query.where(Sport.key.in_(["tennis_atp", "tennis_wta"]))
        else:
            query = query.where(Sport.key == sport_key)
    result = await session.execute(query)
    rows = []
    for event, sport, competition in result.all():
        recommendation = await session.scalar(
            select(Recommendation)
            .where(Recommendation.event_id == event.id)
            .order_by(desc(Recommendation.expected_value))
        )
        rows.append(
            {
                "id": event.id,
                "sport": sport.key,
                "sport_name": sport.name,
                "competition": competition.name if competition else "Unknown competition",
                "name": event.name,
                "home_name": event.home_name,
                "away_name": event.away_name,
                "start_time": _iso(event.start_time),
                "status": event.status,
                "surface": event.surface,
                "round": event.round,
                "data_origin": event.data_origin,
                "recommendation": (
                    {
                        "status": recommendation.status,
                        "best_odds": recommendation.best_odds,
                        "edge": recommendation.edge,
                        "confidence_score": recommendation.confidence_score,
                    }
                    if recommendation
                    else None
                ),
            }
        )
    return rows


async def event_detail(session: AsyncSession, event_id: str) -> dict[str, Any] | None:
    result = await session.execute(
        select(Event, Sport, Competition)
        .join(Sport, Event.sport_id == Sport.id)
        .outerjoin(Competition, Event.competition_id == Competition.id)
        .where(Event.id == event_id, Event.is_demo.is_(False), Event.data_origin == "REAL")
    )
    row = result.first()
    if row is None:
        return None
    event, sport, competition = row
    picks = await recommendation_rows(session, limit=200)
    recommendations = [pick for pick in picks if pick["event_id"] == event_id]
    odds_result = await session.execute(
        select(OddsSnapshot)
        .where(OddsSnapshot.event_id == event_id)
        .order_by(OddsSnapshot.observed_at)
    )
    odds = [
        {
            "bookmaker": odd.bookmaker,
            "market": odd.market,
            "selection": odd.selection,
            "decimal_odds": odd.decimal_odds,
            "point": odd.point,
            "observed_at": _iso(odd.observed_at),
            "is_outlier": odd.is_outlier,
            "validation_status": odd.validation_status,
            "validation_reason": odd.validation_reason,
            "freshness_status": classify_odds_freshness(
                odd.observed_at,
                stale_minutes=settings.odds_stale_minutes,
                expired_minutes=settings.odds_expired_minutes,
            )[0],
            "odds_age_seconds": odd.odds_age_seconds,
            "provider": odd.provider,
        }
        for odd in odds_result.scalars()
    ]
    statistics = []
    statistic_models: tuple[type[FootballStatistic] | type[TennisStatistic], ...] = (
        FootballStatistic,
        TennisStatistic,
    )
    for model in statistic_models:
        for raw_stat in await session.scalars(select(model).where(model.event_id == event_id)):
            stat = cast(FootballStatistic | TennisStatistic, raw_stat)
            statistics.append(
                {
                    "provider": stat.source_provider,
                    "fetched_at": _iso(stat.fetched_at),
                    "side": stat.side,
                    "sample_size": stat.sample_size,
                }
            )
    return {
        "statistics_sources": statistics,
        "prediction_status": "AVAILABLE" if recommendations else "INSUFFICIENT_DATA",
        "model_probability": recommendations[0]["model_probability"] if recommendations else None,
        "id": event.id,
        "sport": sport.key,
        "competition": competition.name if competition else "Unknown competition",
        "name": event.name,
        "home_name": event.home_name,
        "away_name": event.away_name,
        "start_time": _iso(event.start_time),
        "status": event.status,
        "surface": event.surface,
        "round": event.round,
        "best_of": event.best_of,
        "data_origin": event.data_origin,
        "source_timestamp": _iso(event.source_timestamp),
        "data_sources": {
            "event": event.source_provider,
            "provider_entity_id": event.provider_entity_id,
            "fetched_at": _iso(event.fetched_at),
            "source_updated_at": _iso(event.source_updated_at),
            "ingestion_run_id": event.ingestion_run_id,
        },
        "recommendations": recommendations,
        "odds": odds,
    }


async def combinations(session: AsyncSession) -> list[dict[str, Any]]:
    records = (
        await session.execute(
            select(CombinationRecommendation)
            .where(CombinationRecommendation.is_demo.is_(False))
            .order_by(desc(CombinationRecommendation.combined_ev))
        )
    ).scalars()
    picks = await recommendation_rows(session, limit=500)
    by_id = {pick["id"]: pick for pick in picks}
    return [
        {
            "id": record.id,
            "category": record.category,
            "legs": [by_id[leg_id] for leg_id in record.leg_ids if leg_id in by_id],
            "combined_odds": record.combined_odds,
            "combined_probability": record.combined_probability,
            "combined_ev": record.combined_ev,
            "confidence_score": record.confidence_score,
            "correlation_warning": record.correlation_warning,
            "independence_assumed": record.independence_assumed,
        }
        for record in records
    ]


async def dashboard(session: AsyncSession) -> dict[str, Any]:
    now = datetime.now(UTC)
    events = await event_rows(session, limit=100)
    picks = await recommendation_rows(session, status="VALUE", limit=20)
    no_bets = await recommendation_rows(session, status="NO_BET", limit=20)
    combo_rows = await combinations(session)
    last_run = await session.scalar(select(AnalysisRun).order_by(desc(AnalysisRun.created_at)))
    football_count = sum(event["sport"] == "football" for event in events)
    tennis_count = sum(str(event["sport"]).startswith("tennis") for event in events)
    avg_edge = sum(float(pick["edge"]) for pick in picks) / len(picks) if picks else 0.0
    avg_ev = sum(float(pick["expected_value"]) for pick in picks) / len(picks) if picks else 0.0
    return {
        "generated_at": _iso(now),
        "data_mode": settings.data_mode,
        "provider_configured": any(
            [
                bool(settings.the_odds_api_key),
                settings.football_provider_configured,
                settings.tennis_provider_configured,
            ]
        ),
        "last_refresh": _iso(last_run.finished_at if last_run else None),
        "metrics": {
            "events_analysed": len(events),
            "football_events": football_count,
            "tennis_events": tennis_count,
            "value_opportunities": len(picks),
            "strong_picks": sum(int(pick["confidence_score"]) >= 80 for pick in picks),
            "average_edge": avg_edge,
            "average_ev": avg_ev,
        },
        "top_picks": picks[:4],
        "football_opportunities": [pick for pick in picks if pick["sport"] == "football"][:3],
        "tennis_opportunities": [pick for pick in picks if str(pick["sport"]).startswith("tennis")][
            :3
        ],
        "combinations": combo_rows[:2],
        "no_bets": no_bets[:3],
        "analysis_run": (
            {
                "id": last_run.id,
                "status": last_run.status,
                "events_processed": last_run.events_processed,
                "log_summary": last_run.log_summary,
            }
            if last_run
            else None
        ),
    }


async def performance(session: AsyncSession) -> dict[str, Any]:
    rows = list(
        (
            await session.execute(
                select(ModelPerformance).where(~ModelPerformance.segment.like("%SIMULATED%"))
            )
        ).scalars()
    )
    history = list(
        (
            await session.execute(select(BankrollHistory).order_by(BankrollHistory.recorded_at))
        ).scalars()
    )
    start = history[0].bankroll if history else 0
    current = history[-1].bankroll if history else 0
    settled = list(
        (
            await session.execute(
                select(BetResult, Recommendation)
                .join(Recommendation, BetResult.recommendation_id == Recommendation.id)
                .join(Event, Recommendation.event_id == Event.id)
                .where(Event.is_demo.is_(False), Event.data_origin == "REAL")
            )
        ).all()
    )
    decisions = [item for item in settled if item[0].result in {"WIN", "LOSS"}]
    total_stake = sum(item[0].stake for item in settled)
    profit = sum(item[0].profit_loss for item in settled)
    wins = sum(item[0].result == "WIN" for item in decisions)
    price_clv = [
        item[0].odds_at_prediction / item[0].closing_odds - 1
        for item in settled
        if item[0].closing_odds and item[0].closing_odds > 1
    ]
    if decisions:
        brier = sum(
            (item[1].model_probability - (1 if item[0].result == "WIN" else 0)) ** 2
            for item in decisions
        ) / len(decisions)
    else:
        brier = None
    return {
        "data_mode": settings.data_mode,
        "metrics": {
            "total_bets": len(settled),
            "win_rate": wins / len(decisions) if decisions else None,
            "roi": profit / start if start > 0 else None,
            "yield": profit / total_stake if total_stake else None,
            "profit": profit if settled else current - start,
            "average_odds": (
                sum(item[0].odds_at_prediction for item in settled) / len(settled) if settled else 0
            ),
            "average_edge": (
                sum(item[1].edge for item in settled) / len(settled) if settled else 0
            ),
            "average_clv": sum(price_clv) / len(price_clv) if price_clv else None,
            "max_drawdown": max((row.max_drawdown or 0 for row in rows), default=0),
            "brier_score": brier,
            "log_loss": -sum(
                log(
                    max(
                        1e-15,
                        min(
                            1 - 1e-15,
                            item[1].model_probability
                            if item[0].result == "WIN"
                            else 1 - item[1].model_probability,
                        ),
                    )
                )
                for item in decisions
            )
            / len(decisions)
            if decisions
            else None,
        },
        "bankroll_history": [
            {
                "timestamp": _iso(point.recorded_at),
                "bankroll": point.bankroll,
                "change": point.change,
            }
            for point in history
        ],
        "segments": [
            {
                "segment": row.segment,
                "bets": row.bets,
                "roi": row.roi,
                "clv": row.clv,
                "brier_score": row.brier_score,
                "enabled": row.enabled,
            }
            for row in rows
        ],
    }


async def system_status(session: AsyncSession) -> dict[str, Any]:
    sportmonks_capabilities = await session.scalar(
        select(ApiLog)
        .where(ApiLog.provider_name == "Sportmonks", ApiLog.endpoint == "capabilities")
        .order_by(desc(ApiLog.occurred_at))
    )
    providers = list((await session.execute(select(ProviderStatus))).scalars())
    last_run = await session.scalar(select(AnalysisRun).order_by(desc(AnalysisRun.created_at)))
    event_count = await session.scalar(select(func.count(Event.id)))
    steps = []
    if last_run is not None:
        steps = list(
            (
                await session.execute(
                    select(AnalysisRunStep)
                    .where(AnalysisRunStep.analysis_run_id == last_run.id)
                    .order_by(AnalysisRunStep.created_at)
                )
            ).scalars()
        )
    return {
        "data_mode": settings.data_mode,
        "database": {"status": "HEALTHY", "events": event_count or 0},
        "sportmonks_capabilities": sportmonks_capabilities.context
        if sportmonks_capabilities
        else None,
        "scheduler": {"status": "ACTIVE" if settings.scheduler_enabled else "DISABLED"},
        "model_engine": {"status": "NO_PRODUCTION_MODEL", "version": None},
        "providers": [
            {
                "name": provider.provider_name,
                "configured": provider.configured,
                "status": provider.status,
                "last_request": _iso(provider.last_request_at),
                "last_success": _iso(provider.last_success),
                "last_error": provider.last_error,
                "latency_ms": provider.latency_ms,
                "rate_limit_remaining": provider.rate_limit_remaining,
                "rate_limit_used": provider.rate_limit_used,
                "last_request_cost": provider.last_request_cost,
                "records_received": provider.records_received,
                "data_freshness_seconds": provider.data_freshness_seconds,
                "sports_supplied": provider.sports_supplied,
                "last_response_at": _iso(provider.last_response_at),
            }
            for provider in providers
        ],
        "last_analysis": (
            {
                "id": last_run.id,
                "status": last_run.status,
                "started_at": _iso(last_run.started_at),
                "finished_at": _iso(last_run.finished_at),
                "events_processed": last_run.events_processed,
                "predictions_created": last_run.predictions_created,
                "value_picks_created": last_run.value_picks_created,
                "errors": last_run.errors,
                "summary": last_run.log_summary,
                "steps": [
                    {
                        "name": step.step_name,
                        "status": step.status,
                        "started_at": _iso(step.started_at),
                        "finished_at": _iso(step.finished_at),
                        "records_processed": step.records_processed,
                        "error": step.error,
                    }
                    for step in steps
                ],
            }
            if last_run
            else None
        ),
    }


async def data_diagnostics(session: AsyncSession) -> dict[str, Any]:
    events_total = int(await session.scalar(select(func.count(Event.id))) or 0)
    mock_events = int(
        await session.scalar(
            select(func.count(Event.id)).where(
                (Event.is_demo.is_(True)) | (Event.data_origin != "REAL")
            )
        )
        or 0
    )
    real_events = int(
        await session.scalar(
            select(func.count(Event.id)).where(
                Event.is_demo.is_(False), Event.data_origin == "REAL"
            )
        )
        or 0
    )
    odds = int(await session.scalar(select(func.count(OddsSnapshot.id))) or 0)
    football_statistics = int(await session.scalar(select(func.count(FootballStatistic.id))) or 0)
    tennis_statistics = int(await session.scalar(select(func.count(TennisStatistic.id))) or 0)
    predictions = int(
        await session.scalar(
            select(func.count(ModelPrediction.id)).where(
                ModelPrediction.is_demo.is_(False), ModelPrediction.data_origin == "REAL"
            )
        )
        or 0
    )
    recommendations = int(
        await session.scalar(
            select(func.count(Recommendation.id)).where(
                Recommendation.is_demo.is_(False), Recommendation.data_origin == "REAL"
            )
        )
        or 0
    )
    mock_predictions = int(
        await session.scalar(
            select(func.count(ModelPrediction.id)).where(
                (ModelPrediction.is_demo.is_(True)) | (ModelPrediction.data_origin != "REAL")
            )
        )
        or 0
    )
    mock_recommendations = int(
        await session.scalar(
            select(func.count(Recommendation.id)).where(
                (Recommendation.is_demo.is_(True)) | (Recommendation.data_origin != "REAL")
            )
        )
        or 0
    )
    status = (
        "ERROR"
        if settings.is_real_mode and (mock_events + mock_predictions + mock_recommendations) > 0
        else "HEALTHY"
    )
    return {
        "status": status,
        "data_mode": settings.data_mode,
        "events_total": events_total,
        "real_events": real_events,
        "mock_events": mock_events,
        "mock_predictions": mock_predictions,
        "mock_recommendations": mock_recommendations,
        "mode": settings.data_mode,
        "events": {"total": events_total, "real": real_events, "simulated": mock_events},
        "prediction_counts": {"production": predictions, "simulation": mock_predictions},
        "odds_snapshots": odds,
        "football_statistics": football_statistics,
        "tennis_statistics": tennis_statistics,
        "predictions": predictions,
        "recommendations": recommendations,
        "provider_configuration": {
            "the_odds_api": bool(settings.the_odds_api_key),
            "football_provider": settings.football_provider,
            "football_configured": settings.football_provider_configured,
            "tennis_provider": settings.tennis_provider,
            "tennis_configured": settings.tennis_provider_configured,
        },
    }
