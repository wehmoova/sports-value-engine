"""Read-only V2 reproducibility and source-window audit; no statistical validation."""

import math
from collections import Counter
from statistics import median
from typing import Any

from app.research.availability import canonical_facts
from app.research.football_reconstruction_v2 import FEATURE_VERSION, sample


def distribution(values: list[float]) -> dict[str, Any]:
    return {
        "count": len(values),
        "min": min(values) if values else None,
        "median": median(values) if values else None,
        "max": max(values) if values else None,
    }


def leaves(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            result.update(leaves(item, f"{prefix}.{key}" if prefix else key))
        return result
    return {prefix: value}


def audit(
    dataset: dict[str, Any],
    records: list[dict[str, Any]],
    context_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if dataset.get("feature_version") != FEATURE_VERSION:
        raise ValueError("V2 audit requires a V2 dataset")
    facts, invalid = canonical_facts(records)
    by_event = {f.event_id: f for f in facts}
    by_artifact = {f.artifact_id: f for f in facts}
    snapshots = {r["snapshot_id"]: r for r in context_records or []}
    rows = dataset["samples"]
    violations: list[dict[str, Any]] = []
    cross_season = cross_competition = 0
    contamination: Counter[str] = Counter()
    timing: Counter[str] = Counter()
    used_counts: dict[str, list[float]] = {
        "result_form": [],
        "goal_form": [],
        "home_away": [],
        "poisson": [],
    }
    missing: Counter[str] = Counter()
    ages: list[float] = []
    current_counts: list[float] = []
    flattened = [leaves(row["features"]) for row in rows]
    all_columns = set().union(*(set(f) for f in flattened))
    for row, flat in zip(rows, flattened, strict=True):
        identity = row["event_id"]
        reasons = []
        if any(snapshots.get(r["snapshot_id"]) != r for r in row["context_provenance"]):
            reasons.append("snapshot_provenance_mismatch")
        for name in all_columns:
            missing[name] += int(flat.get(name) is None)
        if any(isinstance(v, float) and not math.isfinite(v) for v in flat.values()):
            reasons.append("nonfinite_feature")
        target = by_event.get(identity)
        if target is None:
            reasons.append("missing_or_conflicting_target")
        else:
            ids = row["immutable_source_ids"]
            if len(ids) != len(set(ids)):
                reasons.append("duplicate_source")
            if any(i not in by_artifact for i in ids):
                reasons.append("missing_or_noncanonical_source")
            else:
                sources = [by_artifact[i] for i in ids]
                timing["target"] += sum(f.event_id == identity for f in sources)
                timing["same_kickoff"] += sum(f.kickoff == target.kickoff for f in sources)
                timing["future"] += sum(f.kickoff > target.kickoff for f in sources)
                timing["unavailable_completion"] += sum(
                    f.completed_bound >= target.kickoff for f in sources
                )
                if any(
                    f.event_id == identity
                    or f.kickoff >= target.kickoff
                    or f.completed_bound >= target.kickoff
                    for f in sources
                ):
                    reasons.append("target_or_future_source")
                rebuilt, reason = sample(target, sources, row["context_provenance"])
                if rebuilt != row:
                    reasons.append("reproduction_mismatch:" + str(reason))
                for family, family_ids in row["family_source_ids"].items():
                    for source_id in family_ids:
                        fact = by_artifact.get(source_id)
                        if fact is None or source_id not in ids:
                            reasons.append("missing_family_source")
                            continue
                        if family == "long_term_history":
                            continue
                        kind = "poisson" if "poisson" in family else "short_term"
                        if (fact.competition, fact.league) != (target.competition, target.league):
                            cross_competition += 1
                            contamination[f"cross_competition_{kind}"] += 1
                            reasons.append("cross_competition:" + family)
                        if family != "elo" and fact.season != target.season:
                            cross_season += 1
                            contamination[f"cross_season_{kind}"] += 1
                            reasons.append("cross_season:" + family)
        if row["features"].get("xg") is not None:
            reasons.append("xg_enabled")
        for side in ("home", "away"):
            counts = row["coverage"][side]
            current_counts.append(counts["current_season_matches"])
            for kind, family in (
                ("result_form", "rolling_10"),
                ("goal_form", "rolling_10"),
                ("home_away", "venue"),
                ("poisson", "poisson"),
            ):
                used_counts[kind].append(len(row["family_source_ids"][f"{side}_{family}"]))
            if counts["recent_form_oldest_age_days"] is not None:
                ages.append(counts["recent_form_oldest_age_days"])
        if reasons:
            violations.append({"event_id": identity, "reasons": sorted(set(reasons))})
    duplicate_count = len(rows) - len({s["event_id"] for s in rows})
    return {
        "status": "PASSED" if not violations and not duplicate_count else "FAILED",
        "read_only": True,
        "feature_version": FEATURE_VERSION,
        "samples": len(rows),
        "competitions": dict(Counter(s["league"] for s in rows)),
        "seasons": dict(Counter(s["season"] for s in rows)),
        "labels": dict(Counter(str(s["outcome"]) for s in rows)),
        "missingness": {k: v for k, v in sorted(missing.items()) if v},
        "duplicate_count": duplicate_count,
        "violations": violations,
        "cross_season_short_form_contamination": cross_season,
        "cross_competition_context_contamination": cross_competition,
        "contamination_counts": {
            f"{scope}_{kind}": contamination[f"{scope}_{kind}"]
            for scope in ("cross_season", "cross_competition")
            for kind in ("short_term", "poisson")
        },
        "leakage_counts": {
            k: timing[k] for k in ("target", "future", "same_kickoff", "unavailable_completion")
        },
        "used_match_counts": {k: distribution(v) for k, v in used_counts.items()},
        "form_oldest_age_days": distribution(ages),
        "current_season_form_counts": distribution(current_counts),
        "invalid_history": invalid,
        "training": False,
        "validation": False,
        "promotion": False,
    }
