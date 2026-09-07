from collections.abc import Callable
from math import exp, factorial


def poisson_probability(goals: int, expected_goals: float) -> float:
    if goals < 0 or expected_goals < 0:
        raise ValueError("goals and expected goals cannot be negative")
    return exp(-expected_goals) * expected_goals**goals / factorial(goals)


def score_matrix(home_xg: float, away_xg: float, max_goals: int = 10) -> list[list[float]]:
    return [
        [
            poisson_probability(home, home_xg) * poisson_probability(away, away_xg)
            for away in range(max_goals + 1)
        ]
        for home in range(max_goals + 1)
    ]


def three_way_probabilities(home_xg: float, away_xg: float) -> dict[str, float]:
    matrix = score_matrix(home_xg, away_xg)
    home = sum(value for i, row in enumerate(matrix) for j, value in enumerate(row) if i > j)
    draw = sum(value for i, row in enumerate(matrix) for j, value in enumerate(row) if i == j)
    away = sum(value for i, row in enumerate(matrix) for j, value in enumerate(row) if i < j)
    total = home + draw + away
    return {"HOME": home / total, "DRAW": draw / total, "AWAY": away / total}


def expected_goals_from_strengths(
    *,
    league_home_goals: float,
    league_away_goals: float,
    home_attack_strength: float,
    home_defence_strength: float,
    away_attack_strength: float,
    away_defence_strength: float,
) -> tuple[float, float]:
    inputs = (
        league_home_goals,
        league_away_goals,
        home_attack_strength,
        home_defence_strength,
        away_attack_strength,
        away_defence_strength,
    )
    if any(value <= 0 for value in inputs):
        raise ValueError("Poisson strengths and league baselines must be positive")
    home_expected = league_home_goals * home_attack_strength * away_defence_strength
    away_expected = league_away_goals * away_attack_strength * home_defence_strength
    return home_expected, away_expected


def market_probabilities(
    home_expected_goals: float, away_expected_goals: float, max_goals: int = 12
) -> dict[str, float]:
    matrix = score_matrix(home_expected_goals, away_expected_goals, max_goals=max_goals)
    mass = sum(sum(row) for row in matrix)
    if mass <= 0:
        raise ValueError("score matrix has no probability mass")

    def probability(condition: Callable[[int, int], bool]) -> float:
        return (
            sum(
                value
                for home, row in enumerate(matrix)
                for away, value in enumerate(row)
                if condition(home, away)
            )
            / mass
        )

    return {
        "HOME": probability(lambda home, away: home > away),
        "DRAW": probability(lambda home, away: home == away),
        "AWAY": probability(lambda home, away: home < away),
        "OVER_1_5": probability(lambda home, away: home + away > 1.5),
        "OVER_2_5": probability(lambda home, away: home + away > 2.5),
        "OVER_3_5": probability(lambda home, away: home + away > 3.5),
        "UNDER_2_5": probability(lambda home, away: home + away < 2.5),
        "BTTS_YES": probability(lambda home, away: home > 0 and away > 0),
        "BTTS_NO": probability(lambda home, away: home == 0 or away == 0),
    }
