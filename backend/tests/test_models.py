import pytest

from app.sports.football.models.elo import EloRating
from app.sports.football.models.poisson import three_way_probabilities
from app.sports.tennis.models.elo import TennisElo


def test_poisson_three_way_is_normalized() -> None:
    probabilities = three_way_probabilities(1.7, 1.1)
    assert sum(probabilities.values()) == pytest.approx(1.0)
    assert probabilities["HOME"] > probabilities["AWAY"]


def test_football_elo_moves_after_win() -> None:
    home = EloRating(1500)
    before = home.rating
    home.update(1500, score=1, home_advantage=60)
    assert home.rating > before


def test_surface_elo_has_more_weight_than_overall() -> None:
    clay_specialist = TennisElo(overall=1450, surfaces={"clay": 1700}, surface_matches={"clay": 50})
    all_court = TennisElo(overall=1550, surfaces={"clay": 1500}, surface_matches={"clay": 50})
    assert clay_specialist.expected(all_court, "clay") > 0.5
