"""Point-in-time features. Retrieval timestamps are never backdated to kickoff."""

from collections import defaultdict
from datetime import UTC, datetime
from math import isfinite
from statistics import mean
from typing import Any

FEATURE_VERSION = "strict-observed-v2"


def timestamp(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("Research timestamps must carry a timezone")
    return result.astimezone(UTC)


def eligible_history(records: list[dict[str, Any]], at: datetime) -> list[dict[str, Any]]:
    # One event, one result; take the latest version actually available at cutoff.
    latest: dict[str, dict[str, Any]] = {}
    for row in records:
        if timestamp(row["start"]) >= at or timestamp(row["available_at"]) >= at:
            continue
        existing = latest.get(row["event_id"])
        if existing is None or timestamp(row["available_at"]) > timestamp(existing["available_at"]):
            latest[row["event_id"]] = row
    return sorted(latest.values(), key=lambda r: (r["start"], r["event_id"]))


def context_available_at(row: dict[str, Any]) -> datetime:
    values = [timestamp(row["observed_at"]), timestamp(row["fetched_at"])]
    if row.get("source_updated_at") is not None:
        values.append(timestamp(row["source_updated_at"]))
    return max(values)


def eligible_context(
    records: list[dict[str, Any]], event_id: str, at: datetime
) -> list[dict[str, Any]]:
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    ambiguous: dict[tuple[str, str], datetime] = {}
    for row in records:
        if row.get("event_id") != event_id or row.get("post_match"):
            continue
        if not row.get("snapshot_id") or row.get("side") not in {"home", "away"}:
            continue
        try:
            available_at = context_available_at(row)
        except (KeyError, TypeError, ValueError):
            continue
        if available_at >= at:
            continue
        key = (str(row.get("kind") or "context"), str(row.get("side") or ""))
        existing = latest.get(key)
        if existing is None or available_at > context_available_at(existing):
            latest[key] = row
        elif available_at == context_available_at(existing) and row != existing:
            ambiguous[key] = available_at
    return sorted(
        (
            row
            for key, row in latest.items()
            if key not in ambiguous or context_available_at(row) > ambiguous[key]
        ),
        key=lambda r: (r.get("kind", ""), r.get("side", "")),
    )


def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
        return number if isfinite(number) and not isinstance(value, bool) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _rank(value: Any) -> float | None:
    number = _number(value)
    return number if number is not None and number > 0 and number.is_integer() else None


def _nonnegative(value: Any) -> float | None:
    number = _number(value)
    return number if number is not None and number >= 0 else None


def _side_context(records: list[dict[str, Any]], kind: str, side: str) -> dict[str, Any] | None:
    return next(
        (row for row in records if row.get("kind") == kind and row.get("side") == side),
        None,
    )


def _apply_tennis_context(features: dict[str, Any], context: list[dict[str, Any]]) -> list[str]:
    home = _side_context(context, "tennis_ranking", "home")
    away = _side_context(context, "tennis_ranking", "away")
    if home is None or away is None or home.get("source_provider") != away.get("source_provider"):
        return []
    used = [home, away]
    applied = False
    home_rank, away_rank = _rank(home.get("ranking")), _rank(away.get("ranking"))
    home_points = _nonnegative(home.get("ranking_points"))
    away_points = _nonnegative(away.get("ranking_points"))
    if home_rank is not None and away_rank is not None:
        # Lower rank is better, so positive delta means the home player is ranked better.
        features["ranking_delta"] = away_rank - home_rank
        features["home_ranking"] = home_rank
        features["away_ranking"] = away_rank
        applied = True
    if home_points is not None and away_points is not None:
        features["ranking_points_delta"] = home_points - away_points
        applied = True
    return [str(row["snapshot_id"]) for row in used] if applied else []


def _apply_football_context(features: dict[str, Any], context: list[dict[str, Any]]) -> list[str]:
    home = _side_context(context, "football_team", "home")
    away = _side_context(context, "football_team", "away")
    if home is None or away is None or home.get("source_provider") != away.get("source_provider"):
        return []
    used = [home, away]
    applied = False

    home_for, away_for = (
        _nonnegative(home.get("goals_per_match")),
        _nonnegative(away.get("goals_per_match")),
    )
    home_against = _nonnegative(home.get("goals_against_per_match"))
    away_against = _nonnegative(away.get("goals_against_per_match"))
    if not _rank(home.get("sample_size")) or not _rank(away.get("sample_size")):
        home_for = away_for = home_against = away_against = None
    if home_for is not None and away_for is not None:
        features["team_goals_for_delta"] = home_for - away_for
        features["home_team_goals_per_match"] = home_for
        features["away_team_goals_per_match"] = away_for
        applied = True
    if home_against is not None and away_against is not None:
        # Positive means the home team has conceded fewer goals per match.
        features["team_goals_against_delta"] = away_against - home_against
        features["home_team_goals_against_per_match"] = home_against
        features["away_team_goals_against_per_match"] = away_against
        applied = True

    home_position = _rank(home.get("standing_position"))
    away_position = _rank(away.get("standing_position"))
    if home_position is not None and away_position is not None:
        # Lower table position is better, mirroring ranking_delta semantics.
        features["standing_position_delta"] = away_position - home_position
        applied = True
    home_points = _number(home.get("standing_points"))
    away_points = _number(away.get("standing_points"))
    if home_points is not None and away_points is not None:
        features["standing_points_delta"] = home_points - away_points
        applied = True
    home_goal_diff = _number(home.get("standing_goal_difference"))
    away_goal_diff = _number(away.get("standing_goal_difference"))
    if home_goal_diff is not None and away_goal_diff is not None:
        features["standing_goal_difference_delta"] = home_goal_diff - away_goal_diff
        applied = True
    return [str(row["snapshot_id"]) for row in used] if applied else []


def build_sample(
    event: dict[str, Any],
    records: list[dict[str, Any]],
    min_history: int,
    min_player: int,
    context_records: list[dict[str, Any]] | None = None,
    *,
    exclusions: list[str] | None = None,
) -> dict[str, Any] | None:
    def reject(reason: str) -> None:
        if exclusions is not None:
            exclusions.append(reason)

    at = timestamp(event["start"])
    prior = eligible_history(records, at)
    if len(prior) < min_history:
        reject("insufficient_available_history")
        return None
    football = event["sport"] == "football"
    ratings: dict[str, float] = defaultdict(lambda: 1500.0)
    surface_ratings: dict[str, float] = defaultdict(lambda: 1500.0)
    appearances: dict[str, list[dict[str, Any]]] = defaultdict(list)
    surface_counts: dict[str, int] = defaultdict(int)
    for row in prior:
        home, away = row["home"], row["away"]
        actual = 1.0 if row["outcome"] == 0 else 0.5 if football and row["outcome"] == 1 else 0.0
        expected = 1 / (1 + 10 ** ((ratings[away] - ratings[home]) / 400))
        change = 24 * (actual - expected)
        ratings[home] += change
        ratings[away] -= change
        if event.get("surface") and row.get("surface") == event["surface"]:
            expected_surface = 1 / (
                1 + 10 ** ((surface_ratings[away] - surface_ratings[home]) / 400)
            )
            delta = 24 * (actual - expected_surface)
            surface_ratings[home] += delta
            surface_ratings[away] -= delta
            surface_counts[home] += 1
            surface_counts[away] += 1
        appearances[home].append(row)
        appearances[away].append(row)
    home, away = event["home"], event["away"]
    if min(len(appearances[home]), len(appearances[away])) < min_player:
        reject("insufficient_participant_history")
        return None

    def points(row: dict[str, Any], player: str) -> float:
        if football and row["outcome"] == 1:
            return 0.5
        return float((row["outcome"] == 0) == (row["home"] == player))

    features: dict[str, Any] = {
        "elo_delta": ratings[home] - ratings[away],
        "home_advantage": 1 if football else 0,
        "form_delta": mean(points(r, home) for r in appearances[home][-10:])
        - mean(points(r, away) for r in appearances[away][-10:]),
        "home_samples": len(appearances[home]),
        "away_samples": len(appearances[away]),
        "surface_elo_delta": None,
        "ranking_delta": None,
        "ranking_points_delta": None,
        "xg": None,
        "h2h_delta": None,
        "home_goal_rate": None,
        "away_goal_rate": None,
        "team_goals_for_delta": None,
        "team_goals_against_delta": None,
        "standing_position_delta": None,
        "standing_points_delta": None,
        "standing_goal_difference_delta": None,
        "rest_days_home": (at - timestamp(appearances[home][-1]["start"])).total_seconds() / 86400,
        "rest_days_away": (at - timestamp(appearances[away][-1]["start"])).total_seconds() / 86400,
    }
    if min(surface_counts[home], surface_counts[away]) >= min_player:
        features["surface_elo_delta"] = surface_ratings[home] - surface_ratings[away]
    h2h = [r for r in appearances[home] if away in (r["home"], r["away"])]
    if len(h2h) >= 5:
        features["h2h_delta"] = mean(points(r, home) for r in h2h[-10:]) - 0.5
    if football:
        home_games = [r for r in appearances[home] if r["home"] == home][-20:]
        away_games = [r for r in appearances[away] if r["away"] == away][-20:]
        league = [r for r in prior if r["competition"] == event["competition"]]
        if min(len(home_games), len(away_games)) < 3 or len(league) < 20:
            reject("insufficient_home_away_or_league_history")
            return None
        base_home = mean(float(r["home_score"]) for r in league)
        base_away = mean(float(r["away_score"]) for r in league)

        # Three league-average pseudo-matches are explicit regularisation, not data.
        def rate(rows: list[dict[str, Any]], field: str, baseline: float) -> float:
            return (sum(float(r[field]) for r in rows) + 3 * baseline) / (len(rows) + 3)

        if min(base_home, base_away) <= 0:
            reject("nonpositive_league_goal_baseline")
            return None
        features.update(
            home_goal_rate=rate(home_games, "home_score", base_home)
            * rate(away_games, "home_score", base_home)
            / base_home,
            away_goal_rate=rate(away_games, "away_score", base_away)
            * rate(home_games, "away_score", base_away)
            / base_away,
            home_form=mean(points(r, home) for r in home_games[-5:]),
            away_form=mean(points(r, away) for r in away_games[-5:]),
        )

    context = eligible_context(context_records or [], str(event["event_id"]), at)
    context_source_ids = (
        _apply_football_context(features, context)
        if football
        else _apply_tennis_context(features, context)
    )
    history_source_ids = [str(r["artifact_id"]) for r in prior]
    availability = [timestamp(r["available_at"]) for r in prior]
    availability.extend(
        context_available_at(row)
        for row in context
        if str(row["snapshot_id"]) in context_source_ids
    )
    return {
        "event_id": event["event_id"],
        "start": event["start"],
        "label_available_at": event["available_at"],
        "outcome": event["outcome"],
        "features": features,
        "source_ids": list(dict.fromkeys(history_source_ids + context_source_ids)),
        "context_source_ids": context_source_ids,
        "context_provenance": [
            {
                key: row.get(key)
                for key in (
                    "snapshot_id",
                    "source_table",
                    "event_id",
                    "side",
                    "source_provider",
                    "provider_entity_id",
                    "raw_payload_hash",
                    "ingestion_run_id",
                    "observed_at",
                    "fetched_at",
                    "source_updated_at",
                )
            }
            for row in context
            if str(row["snapshot_id"]) in context_source_ids
        ],
        "latest_source_available_at": max(availability).isoformat(),
    }


def build_dataset(
    records: list[dict[str, Any]],
    min_history: int,
    min_player: int,
    context_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    targets = {r["event_id"]: r for r in sorted(records, key=lambda r: r["available_at"])}
    samples = []
    for event in sorted(targets.values(), key=lambda r: (r["start"], r["event_id"])):
        sample = build_sample(event, records, min_history, min_player, context_records)
        if sample:
            samples.append(sample)
    football = any(row.get("sport") == "football" for row in targets.values())
    feature_coverage = {
        "ranking_delta": sum(s["features"].get("ranking_delta") is not None for s in samples),
        "timestamped_team_stats": sum(
            s["features"].get("team_goals_for_delta") is not None for s in samples
        ),
        "standings": sum(
            s["features"].get("standing_position_delta") is not None
            or s["features"].get("standing_points_delta") is not None
            for s in samples
        ),
    }
    missing_features = ["xg", "opponent_adjusted_rolling_stats"]
    if football:
        if feature_coverage["timestamped_team_stats"] == 0:
            missing_features.append("timestamped_team_statistics")
        if feature_coverage["standings"] == 0:
            missing_features.append("standings")
    elif feature_coverage["ranking_delta"] == 0:
        missing_features.append("historical_rankings")
    return {
        "feature_version": FEATURE_VERSION,
        "samples": samples,
        "history_records": len(targets),
        "context_records": len(context_records or []),
        "context_evidence_samples": sum(bool(s["context_source_ids"]) for s in samples),
        "feature_coverage": feature_coverage,
        "excluded": len(targets) - len(samples),
        "minimum_history": min_history,
        "minimum_participant": min_player,
        "availability_policy": "FIRST_OBSERVED_FINAL_AND_PROVIDER_SNAPSHOT_STRICT",
        "missing_features": missing_features,
        "status": "READY" if samples else "INSUFFICIENT_DATA",
    }
