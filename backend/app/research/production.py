"""Only explicitly promoted, calibrated model artifacts may produce live outputs."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.value.engine import evaluate_value
from app.core.config import settings
from app.models import Event, ModelPrediction, ModelRegistry, Recommendation, Sport
from app.models.research import ResearchArtifact
from app.research.context import load_context_snapshots
from app.research.features import FEATURE_VERSION, build_sample, timestamp
from app.research.markets import market_at
from app.research.validation import probabilities


async def infer(session: AsyncSession, run_id: str) -> tuple[int, int]:
    now = datetime.now(UTC)
    predictions = recommendations = 0
    models = list(
        await session.scalars(
            select(ModelRegistry).where(
                ModelRegistry.status == "PRODUCTION", ModelRegistry.is_active.is_(True)
            )
        )
    )
    for model in models:
        checks = model.metrics.get("checks", {})
        if not checks or not all(checks.values()) or model.features_version != FEATURE_VERSION:
            continue
        if model.calibration_method != "temperature_scaling":
            continue
        promoted = model.metrics.get("promoted_at")
        if not promoted or not now - timedelta(days=30) < timestamp(promoted) <= now:
            continue
        trained = await session.get(ResearchArtifact, model.metrics.get("trained_id"))
        if trained is None or trained.kind != "trained" or trained.status != "EXPERIMENTAL":
            continue
        sport = await session.scalar(select(Sport).where(Sport.key == model.sport))
        if sport is None:
            continue
        history = list(
            await session.scalars(
                select(ResearchArtifact).where(
                    ResearchArtifact.kind == "history", ResearchArtifact.sport == model.sport
                )
            )
        )
        records = [{**h.payload, "artifact_id": h.id, "sport": h.sport} for h in history]
        minimum = (
            settings.min_football_history_matches
            if model.sport == "football"
            else settings.min_tennis_history_matches
        )
        events = list(
            await session.scalars(
                select(Event).where(
                    Event.sport_id == sport.id,
                    Event.start_time > now,
                    Event.start_time < now + timedelta(days=2),
                    Event.is_demo.is_(False),
                    Event.data_origin == "REAL",
                    Event.status.in_(["SCHEDULED", "NS", "NOT STARTED"]),
                )
            )
        )
        context_records = await load_context_snapshots(
            session, model.sport, [event.id for event in events]
        )
        for event in events:
            # Prediction-time cutoff, never future kickoff or the event's final score.
            sample = build_sample(
                {
                    "event_id": event.id,
                    "sport": model.sport,
                    "start": now.isoformat(),
                    "available_at": now.isoformat(),
                    "outcome": None,
                    "home": event.home_entity_id,
                    "away": event.away_entity_id,
                    "surface": event.surface,
                    "competition": event.competition_id,
                },
                records,
                minimum,
                settings.min_participant_history_matches,
                context_records,
            )
            if sample is None:
                continue
            p = probabilities(
                sample["features"], trained.payload["model"], trained.payload["temperature"]
            )
            if p is None:
                continue
            market = await market_at(session, event, now)
            if market is None or len(market["probabilities"]) != len(p):
                continue
            # Missing availability/news earns zero, not a fabricated certainty score.
            quality = round(
                40
                + 20
                * min(
                    1,
                    min(sample["features"]["home_samples"], sample["features"]["away_samples"])
                    / 30,
                )
                + 10 * min(1, market["bookmakers"] / 3)
            )
            ece = float(model.metrics["validation"]["ece"])
            confidence = round(min(quality, 100 * max(0, 1 - ece)))
            if quality < settings.min_data_quality:
                continue
            for index, selection in enumerate(market["selections"]):
                if await session.scalar(
                    select(ModelPrediction.id).where(
                        ModelPrediction.event_id == event.id,
                        ModelPrediction.model_version == model.model_version,
                        ModelPrediction.selection == selection,
                    )
                ):
                    continue
                prediction = ModelPrediction(
                    event_id=event.id,
                    market="MONEYLINE",
                    selection=selection,
                    model_name=model.model_name,
                    model_probability=p[index],
                    model_version=model.model_version,
                    feature_version=FEATURE_VERSION,
                    prediction_timestamp=now,
                    data_snapshot_timestamp=timestamp(sample["latest_source_available_at"]),
                    is_calibrated=True,
                    calibration_method="temperature_scaling",
                    ingestion_run_id=run_id,
                    data_origin="REAL",
                    is_demo=False,
                    explanation_factors=["Calibrated baseline using observed prior results"],
                    risk_factors=["Missing availability/news features", "No xG component"],
                )
                session.add(prediction)
                await session.flush()
                predictions += 1
                decision = evaluate_value(
                    model_probability=p[index],
                    market_probability=market["probabilities"][index],
                    best_odds=market["best"][index],
                    confidence=confidence,
                    data_quality=quality,
                    min_odds=settings.min_odds,
                    min_edge=settings.min_edge,
                    min_ev=settings.min_ev,
                    min_confidence=settings.min_confidence,
                    min_data_quality=settings.min_data_quality,
                )
                if decision.status != "VALUE":
                    continue
                session.add(
                    Recommendation(
                        event_id=event.id,
                        prediction_id=prediction.id,
                        market="MONEYLINE",
                        selection=selection,
                        bookmaker=market["best_bookmakers"][index],
                        best_odds=decision.best_odds,
                        average_odds=market["average"][index],
                        median_odds=market["median"][index],
                        model_probability=p[index],
                        market_probability=decision.market_probability,
                        fair_odds=decision.fair_odds,
                        edge=decision.edge,
                        expected_value=decision.expected_value,
                        confidence_score=confidence,
                        data_quality_score=quality,
                        status="VALUE",
                        reason_code="QUALIFIED_VALUE",
                        odds_timestamp=timestamp(market["latest_odds_at"]),
                        data_origin="REAL",
                        is_demo=False,
                        ingestion_run_id=run_id,
                        eligibility_checks={
                            "production_model": True,
                            "complete_fresh_market": True,
                        },
                        data_quality_components={
                            "history_market_score": quality,
                            "availability": 0,
                        },
                    )
                )
                recommendations += 1
    return predictions, recommendations
