"""Versioned research-only football reconstruction; old v2/live/tennis are unchanged."""

from collections import Counter
from typing import Any

from app.research.availability import (
    AvailabilityClass,
    MatchFact,
    available_before,
    canonical_facts,
    prior_facts,
)
from app.research.features import _apply_football_context, context_available_at, eligible_context
from app.research.football_history import reconstruct_features

FEATURE_VERSION = "strict-historical-reconstruction-v1"


def sample(
    target: MatchFact,
    prior: list[MatchFact],
    context: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, str | None]:
    features, reason = reconstruct_features(target, prior)
    if features is None:
        return None, reason
    eligible = eligible_context(
        [
            r
            for r in context
            if available_before(r, target.kickoff, AvailabilityClass.OBSERVED_SNAPSHOT_TIME)
        ],
        target.event_id,
        target.kickoff,
    )
    context_ids = _apply_football_context(features, eligible)
    used_context = [r for r in eligible if r["snapshot_id"] in context_ids]
    return {
        "event_id": target.event_id,
        "start": target.kickoff.isoformat(),
        "label_available_at": target.completed_bound.isoformat(),
        "outcome": target.outcome,
        "label_observed_at": target.observed_at,
        "features": features,
        "source_ids": [f.artifact_id for f in prior] + context_ids,
        "context_source_ids": context_ids,
        "immutable_source_ids": [f.artifact_id for f in prior],
        "context_provenance": used_context,
        "immutable_provenance": [
            {
                "artifact_id": f.artifact_id,
                "event_id": f.event_id,
                "provider": "sportmonks",
                "external_id": f.external_id,
                "raw_hash": f.raw_hash,
                "availability_class": AvailabilityClass.IMMUTABLE_EVENT_TIME,
                "kickoff": f.kickoff.isoformat(),
                "completed_bound": f.completed_bound.isoformat(),
                "completion_basis": f.completion_basis,
                "observed_at": f.observed_at,
            }
            for f in prior
        ],
        "latest_source_available_at": max(
            [f.completed_bound for f in prior] + [context_available_at(r) for r in used_context]
        ).isoformat(),
    }, None


def build_dataset(
    records: list[dict[str, Any]],
    min_history: int,
    min_player: int,
    context_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    facts, invalid = canonical_facts(records)
    samples = []
    exclusions = Counter(invalid.values())
    evidence = []
    warmup = 0
    participant_warmup = 0
    for target in facts:
        prior = prior_facts(facts, target)
        home = sum(target.home in (f.home, f.away) for f in prior)
        away = sum(target.away in (f.home, f.away) for f in prior)
        participant_warmup += int(min(home, away) < min_player)
        reason = None
        if not prior:
            reason = "no_prior_matches"
        elif len(prior) < min_history:
            reason = "insufficient_global_history"
        elif min(home, away) < min_player:
            reason = "insufficient_participant_history"
        else:
            warmup += 1
            row, reason = sample(target, prior, context_records or [])
            if row:
                samples.append(row)
        if reason:
            exclusions[reason] += 1
        evidence.append(
            {
                "event_id": target.event_id,
                "available_history": len(prior),
                "home_history": home,
                "away_history": away,
                "first_failed_gate": reason,
            }
        )
    basic = len(samples)
    coverage = dict.fromkeys(
        (
            "elo",
            "elo_delta",
            "recent_form",
            "goal_form",
            "home_away_form",
            "opponent_adjusted_form",
            "poisson_inputs",
        ),
        basic,
    )
    coverage.update(
        {
            "reconstructed_season_state": sum(
                s["features"]["home_reconstructed_ledger"] is not None
                and s["features"]["away_reconstructed_ledger"] is not None
                for s in samples
            ),
            "timestamped_team_stats": sum(
                s["features"]["team_goals_for_delta"] is not None for s in samples
            ),
            "provider_standings": sum(
                s["features"]["standing_position_delta"] is not None
                or s["features"]["standing_points_delta"] is not None
                for s in samples
            ),
            "xg": 0,
        }
    )
    return {
        "feature_version": FEATURE_VERSION,
        "status": "READY" if samples else "INSUFFICIENT_DATA",
        "samples": samples,
        "history_records": len(facts) + len(invalid),
        "eligible_targets": len(facts),
        "eligible_after_warmup": warmup,
        "sample_count": len(samples),
        "participant_warmup_targets": participant_warmup,
        "context_records": len(context_records or []),
        "context_evidence_samples": sum(bool(s["context_source_ids"]) for s in samples),
        "immutable_event_context": len({i for s in samples for i in s["immutable_source_ids"]}),
        "observed_snapshot_context": len({i for s in samples for i in s["context_source_ids"]}),
        "feature_coverage": coverage,
        "excluded": sum(exclusions.values()),
        "exclusions": dict(sorted(exclusions.items())),
        "invalid_event_facts": invalid,
        "event_evidence": evidence,
        "minimum_history": min_history,
        "minimum_participant": min_player,
        "availability_policy": "IMMUTABLE_EVENT_TIME_AND_OBSERVED_SNAPSHOT_TIME",
        "completion_fallback_hours": 24,
        "xg_available": False,
        "missing_features": ["xg", "official_reconstructed_rank"]
        + (["timestamped_team_statistics"] if not coverage["timestamped_team_stats"] else [])
        + (["provider_standings"] if not coverage["provider_standings"] else []),
        "research_only": True,
    }
