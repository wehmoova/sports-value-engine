"""CLI for durable backfill, point-in-time datasets and gated model research."""

import argparse
import asyncio
import json
from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database.session import SessionLocal, engine
from app.models import Event, ModelPrediction, ModelRegistry, Recommendation, Sport
from app.models.research import ResearchArtifact
from app.research.backfill import backfill
from app.research.context import load_context_snapshots
from app.research.features import build_dataset
from app.research.markets import attach_market_baseline
from app.research.store import artifact
from app.research.validation import promotion_checks, train_baseline, validate
from app.services.job_lock import job_lock

MODELS = (
    "football_elo",
    "football_poisson",
    "football_form",
    "tennis_elo",
    "tennis_surface_elo",
    "tennis_form",
)


async def required(session: AsyncSession, identity: str, kind: str) -> ResearchArtifact:
    row = await session.get(ResearchArtifact, identity)
    if row is None or row.kind != kind:
        raise ValueError(f"Expected an existing {kind} artifact")
    return row


async def status_report(session: AsyncSession) -> dict[str, Any]:
    histories = list(
        await session.scalars(select(ResearchArtifact).where(ResearchArtifact.kind == "history"))
    )
    datasets = list(
        await session.scalars(
            select(ResearchArtifact)
            .where(ResearchArtifact.kind == "dataset")
            .order_by(ResearchArtifact.created_at)
        )
    )
    validations = list(
        await session.scalars(
            select(ResearchArtifact)
            .where(ResearchArtifact.kind == "validation")
            .order_by(ResearchArtifact.created_at)
        )
    )
    models = list(
        await session.scalars(
            select(ModelRegistry).where(
                ModelRegistry.is_active.is_(True), ModelRegistry.status == "PRODUCTION"
            )
        )
    )
    final_events = {}
    for sport, count in (
        await session.execute(
            select(Sport.key, func.count(Event.id))
            .join(Event, Event.sport_id == Sport.id)
            .where(Event.status == "FINAL", Event.is_demo.is_(False), Event.data_origin == "REAL")
            .group_by(Sport.key)
        )
    ).all():
        final_events[sport] = count
    latest_datasets = {
        d.sport: {"id": d.id, "samples": len(d.payload["samples"]), "status": d.status}
        for d in datasets
    }
    return {
        "DATABASE_ENGINE": engine.dialect.name,
        "HISTORICAL_FOOTBALL_RECORDS": len(
            {h.payload["event_id"] for h in histories if h.sport == "football"}
        ),
        "HISTORICAL_TENNIS_RECORDS": len(
            {h.payload["event_id"] for h in histories if h.sport.startswith("tennis")}
        ),
        "FINAL_REAL_EVENTS": final_events,
        "TRAINING_SAMPLES": latest_datasets,
        "VALIDATION_METRICS": [
            {"id": v.id, "model": v.payload.get("model"), "metrics": v.payload.get("metrics")}
            for v in validations[-10:]
        ],
        "PRODUCTION_MODEL_STATUS": "PRODUCTION" if models else "NO_PRODUCTION_MODEL",
        "PREDICTIONS": await session.scalar(select(func.count()).select_from(ModelPrediction)),
        "RECOMMENDATIONS": await session.scalar(select(func.count()).select_from(Recommendation)),
        "MOCK_RECORDS": {
            "events": await session.scalar(
                select(func.count())
                .select_from(Event)
                .where(Event.is_demo.is_(True) | (Event.data_origin != "REAL"))
            ),
            "predictions": await session.scalar(
                select(func.count())
                .select_from(ModelPrediction)
                .where(ModelPrediction.is_demo.is_(True) | (ModelPrediction.data_origin != "REAL"))
            ),
            "recommendations": await session.scalar(
                select(func.count())
                .select_from(Recommendation)
                .where(Recommendation.is_demo.is_(True) | (Recommendation.data_origin != "REAL"))
            ),
        },
    }


async def execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "backfill":
        return await backfill(args.sport, args.start, args.end, args.max_pages)
    async with SessionLocal() as session:
        if args.command == "status":
            return await status_report(session)
        if args.command == "features":
            histories = list(
                await session.scalars(
                    select(ResearchArtifact).where(
                        ResearchArtifact.kind == "history", ResearchArtifact.sport == args.sport
                    )
                )
            )
            records = [{**h.payload, "artifact_id": h.id, "sport": h.sport} for h in histories]
            context_records = await load_context_snapshots(
                session,
                args.sport,
                [str(h.payload["event_id"]) for h in histories if h.payload.get("event_id")],
            )
            minimum = (
                settings.min_football_history_matches
                if args.sport == "football"
                else settings.min_tennis_history_matches
            )
            result = build_dataset(
                records, minimum, settings.min_participant_history_matches, context_records
            )
            row = await artifact(session, "dataset", args.sport, result, status=result["status"])
        elif args.command == "train":
            dataset = await required(session, args.dataset, "dataset")
            if args.model.startswith("football") != (dataset.sport == "football"):
                raise ValueError("Model and dataset sport mismatch")
            result = train_baseline(dataset.payload, args.model)
            result["dataset_id"] = dataset.id
            row = await artifact(session, "trained", dataset.sport, result, status=result["status"])
        elif args.command == "validate":
            trained = await required(session, args.trained, "trained")
            dataset = await required(session, trained.payload["dataset_id"], "dataset")
            result = validate(dataset.payload, trained.payload)
            result.update(
                trained_id=trained.id, dataset_id=dataset.id, model=trained.payload["model"]
            )
            await attach_market_baseline(session, result)
            row = await artifact(
                session, "validation", dataset.sport, result, status=result["status"]
            )
        else:
            validation = await required(session, args.validation, "validation")
            trained = await required(session, validation.payload["trained_id"], "trained")
            dataset = await required(session, trained.payload["dataset_id"], "dataset")
            # Recompute from stored source artifact, not caller-supplied summary metrics.
            recomputed = validate(dataset.payload, trained.payload)
            recomputed["model"] = trained.payload["model"]
            recomputed["trained_id"] = trained.id
            await attach_market_baseline(session, recomputed)
            checks = promotion_checks(recomputed, settings)
            result = {
                "status": "NO_PRODUCTION_MODEL",
                "checks": checks,
                "validation_id": validation.id,
                "trained_id": trained.id,
            }
            if all(checks.values()):
                for previous in await session.scalars(
                    select(ModelRegistry).where(
                        ModelRegistry.sport == validation.sport, ModelRegistry.is_active.is_(True)
                    )
                ):
                    previous.status = "RETIRED"
                    previous.is_active = False
                registered = await session.scalar(
                    select(ModelRegistry).where(
                        ModelRegistry.model_version == trained.id,
                        ModelRegistry.sport == validation.sport,
                    )
                )
                if registered is None:
                    registered = ModelRegistry(
                        model_name=trained.payload["model"],
                        model_version=trained.id,
                        sport=validation.sport,
                        market="MONEYLINE",
                        features_version=dataset.payload["feature_version"],
                    )
                    session.add(registered)
                registered.status = "PRODUCTION"
                registered.is_active = True
                registered.trained_at = trained.created_at
                registered.calibration_method = "temperature_scaling"
                registered.metrics = {
                    "checks": checks,
                    "validation_id": validation.id,
                    "trained_id": trained.id,
                    "dataset_id": dataset.id,
                    "validation": recomputed["metrics"],
                    "promoted_at": datetime.now(UTC).isoformat(),
                }
                result["status"] = "PRODUCTION"
            row = await artifact(
                session,
                "promotion_attempt",
                validation.sport,
                result,
                status=result["status"],
                key=str(uuid4()),
            )
        await session.commit()
        return {
            "id": row.id,
            "status": row.status,
            "summary": {
                k: v
                for k, v in row.payload.items()
                if k not in {"samples", "out_of_sample", "training_ids", "calibration_ids"}
            },
        }


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description=__doc__)
    sub = cli.add_subparsers(dest="command", required=True)
    historical = sub.add_parser("backfill")
    historical.add_argument("--sport", choices=("football", "tennis"), required=True)
    historical.add_argument("--start", type=date.fromisoformat, required=True)
    historical.add_argument("--end", type=date.fromisoformat, required=True)
    historical.add_argument("--max-pages", type=int, default=100)
    features = sub.add_parser("features")
    features.add_argument(
        "--sport", choices=("football", "tennis_atp", "tennis_wta"), required=True
    )
    train = sub.add_parser("train")
    train.add_argument("--dataset", required=True)
    train.add_argument("--model", choices=MODELS, required=True)
    validation = sub.add_parser("validate")
    validation.add_argument("--trained", required=True)
    promote = sub.add_parser("promote")
    promote.add_argument("--validation", required=True)
    sub.add_parser("status")
    return cli


async def main() -> int:
    args = parser().parse_args()
    try:
        if args.command in {"backfill", "status"}:
            result = await execute(args)
        else:
            async with job_lock("research-write") as acquired:
                if not acquired:
                    print(json.dumps({"status": "BUSY"}))
                    return 1
                result = await execute(args)
        print(json.dumps(result, default=str, allow_nan=False))
        return (
            1
            if result.get("status")
            in {"FAILED", "BUSY", "INSUFFICIENT_DATA", "NO_PRODUCTION_MODEL"}
            else 0
        )
    except Exception as exc:
        # HTTP exception causes may contain authenticated URLs; never dump traceback.
        print(json.dumps({"status": "FAILED", "error_type": type(exc).__name__}))
        return 1
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
