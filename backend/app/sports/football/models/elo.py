from dataclasses import dataclass
from datetime import datetime


@dataclass
class EloRating:
    rating: float = 1500.0
    k_factor: float = 24.0

    def expected(self, opponent_rating: float, home_advantage: float = 0.0) -> float:
        return 1 / (1 + 10 ** ((opponent_rating - (self.rating + home_advantage)) / 400))

    def update(self, opponent_rating: float, score: float, home_advantage: float = 0.0) -> float:
        self.rating += self.k_factor * (score - self.expected(opponent_rating, home_advantage))
        return self.rating


@dataclass(frozen=True)
class FootballEloMatch:
    played_at: datetime
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int


@dataclass(frozen=True)
class FootballEloSnapshot:
    played_at: datetime
    home_team: str
    away_team: str
    pre_match_home_elo: float
    pre_match_away_elo: float
    home_win_expectancy: float


def chronological_elo(
    matches: list[FootballEloMatch],
    *,
    initial_rating: float = 1500.0,
    k_factor: float = 24.0,
    home_advantage: float = 65.0,
) -> list[FootballEloSnapshot]:
    if matches != sorted(matches, key=lambda match: match.played_at):
        raise ValueError("matches must be chronological")
    ratings: dict[str, float] = {}
    snapshots: list[FootballEloSnapshot] = []
    for match in matches:
        home_rating = ratings.get(match.home_team, initial_rating)
        away_rating = ratings.get(match.away_team, initial_rating)
        expected_home = 1 / (1 + 10 ** ((away_rating - (home_rating + home_advantage)) / 400))
        score_home = (
            1.0
            if match.home_goals > match.away_goals
            else 0.5
            if match.home_goals == match.away_goals
            else 0.0
        )
        snapshots.append(
            FootballEloSnapshot(
                played_at=match.played_at,
                home_team=match.home_team,
                away_team=match.away_team,
                pre_match_home_elo=home_rating,
                pre_match_away_elo=away_rating,
                home_win_expectancy=expected_home,
            )
        )
        change = k_factor * (score_home - expected_home)
        ratings[match.home_team] = home_rating + change
        ratings[match.away_team] = away_rating - change
    return snapshots
