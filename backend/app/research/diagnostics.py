"""Read-only evidence inventory; rejection reasons come from the actual builder."""

from collections import Counter
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import (
    Event,
    FootballStatistic,
    ModelPrediction,
    ModelRegistry,
    Recommendation,
    TennisStatistic,
)
from app.models.research import ResearchArtifact
from app.research.context import _provenance_ok, load_context_snapshots
from app.research.features import build_dataset, build_sample, eligible_context, eligible_history
from app.research.features import timestamp as parse_time
from app.research.football_reconstruction_v2 import build_dataset as build_football_dataset


async def diagnose(session: AsyncSession, sport: str) -> dict[str, Any]:
    histories = list(
        await session.scalars(
            select(ResearchArtifact).where(
                ResearchArtifact.kind == "history", ResearchArtifact.sport == sport
            )
        )
    )
    records = [dict(h.payload, artifact_id=h.id, sport=h.sport) for h in histories]
    targets = {r["event_id"]: r for r in sorted(records, key=lambda r: r["available_at"])}
    context = await load_context_snapshots(session, sport, list(targets), football_scope=True)
    minimum = (
        settings.min_football_history_matches
        if sport == "football"
        else settings.min_tennis_history_matches
    )
    participant = settings.min_participant_history_matches
    if sport == "football":
        result = build_football_dataset(records, minimum, participant, context)
        result.pop("samples")
        active_models = await session.scalar(
            select(func.count())
            .select_from(ModelRegistry)
            .where(ModelRegistry.status == "PRODUCTION", ModelRegistry.is_active.is_(True))
        )
        return {
            "status": "DIAGNOSED",
            "read_only": True,
            "sport": sport,
            "feature_summary": result,
            "PRODUCTION_MODEL_STATUS": "PRODUCTION" if active_models else "NO_PRODUCTION_MODEL",
            "PREDICTIONS": await session.scalar(select(func.count()).select_from(ModelPrediction)),
            "RECOMMENDATIONS": await session.scalar(
                select(func.count()).select_from(Recommendation)
            ),
            "MOCK_RECORDS": {
                "events": await session.scalar(
                    select(func.count())
                    .select_from(Event)
                    .where(Event.is_demo.is_(True) | (Event.data_origin != "REAL"))
                ),
                "predictions": await session.scalar(
                    select(func.count())
                    .select_from(ModelPrediction)
                    .where(
                        ModelPrediction.is_demo.is_(True) | (ModelPrediction.data_origin != "REAL")
                    )
                ),
                "recommendations": await session.scalar(
                    select(func.count())
                    .select_from(Recommendation)
                    .where(
                        Recommendation.is_demo.is_(True) | (Recommendation.data_origin != "REAL")
                    )
                ),
            },
        }
    reasons: list[str] = []
    evidence = []
    for event in targets.values():
        prior = eligible_history(records, parse_time(event["start"]))
        event_reasons: list[str] = []
        build_sample(event, records, minimum, participant, context, exclusions=event_reasons)
        reasons.extend(event_reasons)
        evidence.append(
            {
                "event_id": event["event_id"],
                "start": event["start"],
                "available_history": len(prior),
                "home_history": sum(event["home"] in (p["home"], p["away"]) for p in prior),
                "away_history": sum(event["away"] in (p["home"], p["away"]) for p in prior),
                "eligible_context": len(
                    eligible_context(context, event["event_id"], parse_time(event["start"]))
                ),
                "first_failed_gate": event_reasons[0] if event_reasons else None,
            }
        )
    # Inventory is per source table, not a claim that all rows belong to this sport.
    snapshots: list[FootballStatistic | TennisStatistic]
    if sport == "football":
        snapshots = list(await session.scalars(select(FootballStatistic)))
    else:
        snapshots = list(await session.scalars(select(TennisStatistic)))
    loaded_ids = {r["snapshot_id"] for r in context}
    partition: Counter[str] = Counter()
    for row in snapshots:
        if row.event_id not in targets:
            reason = "event_not_in_target_history"
        elif not _provenance_ok(row):
            reason = "provenance_gate"
        elif row.id not in loaded_ids:
            reason = "identity_or_real_event_join"
        else:
            reason = "loaded_context"
        partition[reason] += 1
    result = build_dataset(records, minimum, participant, context)
    result.pop("samples")
    return {
        "status": "DIAGNOSED",
        "read_only": True,
        "sport": sport,
        "feature_summary": result,
        "history_versions": len(records),
        "snapshot_inventory": dict(partition),
        "loaded_post_match_snapshots": sum(bool(c["post_match"]) for c in context),
        "excluded_first_gate": dict(Counter(reasons)),
        "event_evidence": evidence,
        "xg_available": False,
        "xg_is_required_gate": False,
        "coverage_is_not_an_exclusion_gate": True,
    }
