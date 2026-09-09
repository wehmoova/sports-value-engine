"""Deterministic football features from canonical, already completed results only."""

from collections import defaultdict
from statistics import mean
from typing import Any

from app.research.availability import MatchFact

ELO_HOME_ADVANTAGE = 60.0
ELO_K = 24.0


def elo_context(
    prior: list[MatchFact],
    target: MatchFact,
) -> tuple[dict[str, float], dict[str, tuple[float, float, float]]]:
    ratings: dict[str, float] = defaultdict(lambda: 1500.0)
    # Deltas are computed at kickoff, then applied only once completion is available.
    pending: list[tuple[MatchFact, float]] = []
    context: dict[str, tuple[float, float, float]] = {}
    for event in sorted(prior, key=lambda f: (f.kickoff, f.external_id)):
        ready = sorted(
            (p for p in pending if p[0].completed_bound < event.kickoff),
            key=lambda p: (p[0].completed_bound, p[0].kickoff, p[0].external_id),
        )
        for fact, delta in ready:
            ratings[fact.home] += delta
            ratings[fact.away] -= delta
        pending = [p for p in pending if p[0].completed_bound >= event.kickoff]
        home, away = ratings[event.home], ratings[event.away]
        expected = 1 / (1 + 10 ** ((away - home - ELO_HOME_ADVANTAGE) / 400))
        actual = 1.0 if event.outcome == 0 else 0.5 if event.outcome == 1 else 0.0
        context[event.event_id] = (home, away, actual - expected)
        pending.append((event, ELO_K * (actual - expected)))
    for fact, delta in sorted(
        pending, key=lambda p: (p[0].completed_bound, p[0].kickoff, p[0].external_id)
    ):
        if fact.completed_bound < target.kickoff:
            ratings[fact.home] += delta
            ratings[fact.away] -= delta
    return ratings, context


def result_values(fact: MatchFact, team: str) -> tuple[int, int, int]:
    scored, conceded = (
        (fact.home_score, fact.away_score)
        if fact.home == team
        else (fact.away_score, fact.home_score)
    )
    return scored, conceded, 3 if scored > conceded else 1 if scored == conceded else 0


def rolling(rows: list[MatchFact], team: str) -> dict[str, Any]:
    values = [result_values(f, team) for f in rows]
    return {
        "matches": len(values),
        "points_per_game": mean(v[2] for v in values),
        "wins": sum(v[0] > v[1] for v in values),
        "draws": sum(v[0] == v[1] for v in values),
        "losses": sum(v[0] < v[1] for v in values),
        "goals_for": mean(v[0] for v in values),
        "goals_against": mean(v[1] for v in values),
        "goal_difference": mean(v[0] - v[1] for v in values),
    }


def reconstruct_features(
    target: MatchFact,
    prior: list[MatchFact],
) -> tuple[dict[str, Any] | None, str | None]:
    home_rows = [f for f in prior if target.home in (f.home, f.away)]
    away_rows = [f for f in prior if target.away in (f.home, f.away)]
    home_games = [f for f in home_rows if f.home == target.home][-20:]
    away_games = [f for f in away_rows if f.away == target.away][-20:]
    league = [f for f in prior if f.competition == target.competition and f.league == target.league]
    if min(len(home_games), len(away_games)) < 3 or len(league) < 20:
        return None, "insufficient_home_away_or_league_history"
    base_home, base_away = mean(f.home_score for f in league), mean(f.away_score for f in league)
    if min(base_home, base_away) <= 0:
        return None, "nonpositive_league_goal_baseline"
    ratings, adjustments = elo_context(prior, target)

    def rate(rows: list[MatchFact], home: bool, baseline: float) -> float:
        # Same explicit 3-match shrinkage as v2; a model prior, not invented observations.
        return (sum(f.home_score if home else f.away_score for f in rows) + 3 * baseline) / (
            len(rows) + 3
        )

    home_attack = rate(home_games, True, base_home) / base_home
    away_defence = rate(away_games, True, base_home) / base_home
    away_attack = rate(away_games, False, base_away) / base_away
    home_defence = rate(home_games, False, base_away) / base_away
    features: dict[str, Any] = {
        "home_elo": ratings[target.home],
        "away_elo": ratings[target.away],
        "elo_delta": ratings[target.home] - ratings[target.away],
        "elo_home_advantage": ELO_HOME_ADVANTAGE,
        "home_advantage": 1,
        "home_samples": len(home_rows),
        "away_samples": len(away_rows),
        "league_home_goals": base_home,
        "league_away_goals": base_away,
        "home_attack_strength": home_attack,
        "away_attack_strength": away_attack,
        "home_defence_strength": home_defence,
        "away_defence_strength": away_defence,
        "home_goal_rate": base_home * home_attack * away_defence,
        "away_goal_rate": base_away * away_attack * home_defence,
        "xg": None,
        "team_goals_for_delta": None,
        "team_goals_against_delta": None,
        "standing_position_delta": None,
        "standing_points_delta": None,
        "standing_goal_difference_delta": None,
    }
    for side, team, rows, venue_rows in (
        ("home", target.home, home_rows, home_games),
        ("away", target.away, away_rows, away_games),
    ):
        for window in (5, 10):
            features[f"{side}_rolling_{window}"] = rolling(rows[-window:], team)
        features[f"{side}_venue_form"] = rolling(venue_rows[-5:], team)
        features[f"{side}_opponent_adjusted_form"] = mean(
            adjustments[f.event_id][2] * (1 if f.home == team else -1) for f in rows[-10:]
        )
        features[f"{side}_opponent_elo_mean"] = mean(
            adjustments[f.event_id][1 if f.home == team else 0] for f in rows[-10:]
        )
        season_rows = [
            f
            for f in rows
            if f.competition == target.competition
            and f.league == target.league
            and f.season == target.season
        ]
        # Partial result ledger, NOT official standings: no rank, deductions or stage reset.
        values = [result_values(f, team) for f in season_rows]
        features[f"{side}_reconstructed_ledger"] = (
            {
                "basis": "PARTIAL_KNOWN_RESULTS_SAME_COMPETITION_SEASON",
                "games_played": len(values),
                "points": sum(v[2] for v in values),
                "goals_for": sum(v[0] for v in values),
                "goals_against": sum(v[1] for v in values),
                "goal_difference": sum(v[0] - v[1] for v in values),
                "rank": None,
                "official_standing": False,
            }
            if values
            else None
        )
    features["form_delta"] = (
        features["home_rolling_10"]["points_per_game"]
        - features["away_rolling_10"]["points_per_game"]
    ) / 3
    return features, None
