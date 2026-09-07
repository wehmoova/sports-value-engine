"""Point-in-time features. Retrieval timestamps are never backdated to kickoff."""

from collections import defaultdict
from datetime import UTC, datetime
from statistics import mean
from typing import Any

FEATURE_VERSION = "strict-observed-v1"


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


def build_sample(
    event: dict[str, Any], records: list[dict[str, Any]], min_history: int, min_player: int
) -> dict[str, Any] | None:
    at = timestamp(event["start"])
    prior = eligible_history(records, at)
    if len(prior) < min_history:
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
        "xg": None,
        "h2h_delta": None,
        "home_goal_rate": None,
        "away_goal_rate": None,
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
            return None
        base_home = mean(float(r["home_score"]) for r in league)
        base_away = mean(float(r["away_score"]) for r in league)

        # Three league-average pseudo-matches are explicit regularisation, not data.
        def rate(rows: list[dict[str, Any]], field: str, baseline: float) -> float:
            return (sum(float(r[field]) for r in rows) + 3 * baseline) / (len(rows) + 3)

        if min(base_home, base_away) <= 0:
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
    return {
        "event_id": event["event_id"],
        "start": event["start"],
        "label_available_at": event["available_at"],
        "outcome": event["outcome"],
        "features": features,
        "source_ids": [r["artifact_id"] for r in prior],
        "latest_source_available_at": max(r["available_at"] for r in prior),
    }


def build_dataset(
    records: list[dict[str, Any]], min_history: int, min_player: int
) -> dict[str, Any]:
    targets = {r["event_id"]: r for r in sorted(records, key=lambda r: r["available_at"])}
    samples = []
    for event in sorted(targets.values(), key=lambda r: (r["start"], r["event_id"])):
        sample = build_sample(event, records, min_history, min_player)
        if sample:
            samples.append(sample)
    return {
        "feature_version": FEATURE_VERSION,
        "samples": samples,
        "history_records": len(targets),
        "excluded": len(targets) - len(samples),
        "minimum_history": min_history,
        "minimum_participant": min_player,
        "availability_policy": "FIRST_OBSERVED_FINAL_STRICT",
        "missing_features": ["historical_rankings", "timestamped_team_statistics", "xg"],
        "status": "READY" if samples else "INSUFFICIENT_DATA",
    }
