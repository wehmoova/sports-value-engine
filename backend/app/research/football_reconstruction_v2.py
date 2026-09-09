"""Season-isolated football research. V1, observed-time and live contracts stay intact."""

from collections import Counter
from statistics import mean
from typing import Any

from app.research.availability import MatchFact, canonical_facts, prior_facts
from app.research.football_history import elo_context, reconstruct_features
from app.research.football_policy_v2 import (
    MINIMUMS,
    coverage,
    family_coverage,
    history_distributions,
    segment_summary,
    windows,
)
from app.research.football_reconstruction import sample as v1_sample

FEATURE_VERSION = "strict-historical-reconstruction-v2"


def sample(
    target: MatchFact, prior: list[MatchFact], context: list[dict[str, Any]]
) -> tuple[dict[str, Any] | None, str | None]:
    groups = windows(target, prior)
    if not family_coverage(groups)["poisson_inputs"]:
        return None, "insufficient_current_season_home_away_or_league_history"
    # The frozen V1 mathematical functions receive ONLY this competition/season.
    features, reason = reconstruct_features(target, groups["poisson_baseline"])
    if features is None:
        return None, reason
    # Preserve the exact observed snapshot availability contract. V1 builds the
    # envelope/provenance; its result features are replaced by seasonal inputs.
    scoped_context = [
        r
        for r in context
        if str(r.get("league")) == target.league and str(r.get("season")) == target.season
    ]
    envelope, reason = v1_sample(target, groups["long_term_history"], scoped_context)
    if envelope is None:
        return None, reason
    for name in (
        "team_goals_for_delta",
        "team_goals_against_delta",
        "standing_position_delta",
        "standing_points_delta",
        "standing_goal_difference_delta",
    ):
        features[name] = envelope["features"][name]
    ratings, adjustments = elo_context(groups["elo"], target)
    features.update(
        home_elo=ratings[target.home],
        away_elo=ratings[target.away],
        elo_delta=ratings[target.home] - ratings[target.away],
    )
    for side, team in (("home", target.home), ("away", target.away)):
        rows = groups[f"{side}_rolling_10"]
        features[f"{side}_samples"] = sum(
            team in (f.home, f.away) for f in groups["long_term_history"]
        )
        features[f"{side}_opponent_adjusted_form"] = mean(
            adjustments[f.event_id][2] * (1 if f.home == team else -1) for f in rows
        )
        features[f"{side}_opponent_elo_mean"] = mean(
            adjustments[f.event_id][1 if f.home == team else 0] for f in rows
        )
    envelope["features"] = features
    envelope["coverage"] = coverage(target, groups)
    envelope["family_source_ids"] = {
        name: [f.artifact_id for f in rows] for name, rows in groups.items()
    }
    envelope["competition"] = target.competition
    envelope["league"] = target.league
    envelope["season"] = target.season
    return envelope, None


def build_dataset(
    records: list[dict[str, Any]],
    min_history: int,
    min_player: int,
    context_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    facts, invalid = canonical_facts(records)
    return build_from_facts(facts, min_history, min_player, context_records or [], invalid)


def build_from_facts(
    facts: list[MatchFact],
    min_history: int,
    min_player: int,
    context: list[dict[str, Any]],
    invalid: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Also supports local impact checks on exported canonical facts, without DB writes."""
    facts = sorted(facts, key=lambda f: (f.kickoff, f.external_id))
    samples: list[dict[str, Any]] = []
    exclusions = Counter((invalid or {}).values())
    evidence = []
    all_coverage: Counter[str] = Counter()
    warm_coverage: Counter[str] = Counter()
    warmup = 0
    for target in facts:
        prior = prior_facts(facts, target)
        groups = windows(target, prior)
        counts = coverage(target, groups)
        families = family_coverage(groups)
        all_coverage.update({k: int(v) for k, v in families.items()})
        home, away = (counts[s]["long_term_history_count"] for s in ("home", "away"))
        reason = None
        if not prior:
            reason = "no_prior_matches"
        elif len(prior) < min_history:
            reason = "insufficient_global_history"
        elif min(home, away) < min_player:
            reason = "insufficient_participant_history"
        else:
            warmup += 1
            warm_coverage.update({k: int(v) for k, v in families.items()})
            row, reason = sample(target, prior, context)
            if row:
                samples.append(row)
        if reason:
            exclusions[reason] += 1
        evidence.append(
            {
                "event_id": target.event_id,
                "league": target.league,
                "season": target.season,
                "available_history": len(prior),
                "home_history": home,
                "away_history": away,
                "coverage": counts,
                "families": families,
                "first_failed_gate": reason,
            }
        )
    return {
        "feature_version": FEATURE_VERSION,
        "status": "READY" if samples else "INSUFFICIENT_DATA",
        "samples": samples,
        "sample_count": len(samples),
        "history_records": len(facts) + len(invalid or {}),
        "eligible_targets": len(facts),
        "eligible_after_warmup": warmup,
        "exclusions": dict(sorted(exclusions.items())),
        "excluded": sum(exclusions.values()),
        "invalid_event_facts": invalid or {},
        "event_evidence": evidence,
        "history_distributions": history_distributions(evidence),
        "segments": segment_summary(facts, evidence),
        "targets_by_league_season": dict(Counter(f"{f.league}:{f.season}" for f in facts)),
        "feature_coverage_all_targets": dict(all_coverage),
        "feature_coverage_after_warmup": dict(warm_coverage),
        "feature_coverage": {
            **dict.fromkeys(
                (k for k in all_coverage if not k.startswith("complete_")), len(samples)
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
        },
        "minimum_history": min_history,
        "minimum_participant": min_player,
        "family_minimums": MINIMUMS,
        "elo_policy": "COMPETITION_LEAGUE_LOCAL_1500_PRIOR_SEASON_CARRY_NO_REGRESSION",
        "short_form_policy": "SAME_COMPETITION_LEAGUE_SEASON_UP_TO_N_NO_FILL",
        "poisson_policy": "SAME_COMPETITION_LEAGUE_SEASON_VENUE20_SHRINKAGE3",
        "context_records": len(context),
        "context_evidence_samples": sum(bool(s["context_source_ids"]) for s in samples),
        "immutable_event_context": len({i for s in samples for i in s["immutable_source_ids"]}),
        "observed_snapshot_context": len({i for s in samples for i in s["context_source_ids"]}),
        "availability_policy": "IMMUTABLE_EVENT_TIME_AND_OBSERVED_SNAPSHOT_TIME",
        "completion_fallback_hours": 24,
        "xg_available": False,
        "research_only": True,
        "missing_features": ["xg", "official_reconstructed_rank"],
    }
