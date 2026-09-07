import pytest

from app.analytics.value.engine import (
    consensus_no_vig,
    data_quality_score,
    evaluate_value,
    expected_value,
    market_consensus,
    remove_vig,
)


def test_no_vig_probabilities_sum_to_one() -> None:
    probabilities = remove_vig({"home": 1.9, "draw": 3.5, "away": 4.2})
    assert sum(probabilities.values()) == pytest.approx(1.0)
    assert probabilities["home"] > probabilities["away"]


def test_consensus_no_vig_uses_multiple_books() -> None:
    probabilities = consensus_no_vig([{"home": 1.9, "away": 2.0}, {"home": 1.95, "away": 1.95}])
    assert sum(probabilities.values()) == pytest.approx(1.0)


def test_data_quality_is_auditable_composite() -> None:
    score = data_quality_score(
        freshness=90,
        sample_size=80,
        odds_freshness=95,
        bookmaker_coverage=85,
        availability_coverage=60,
        statistics_completeness=90,
        provider_consistency=90,
    )
    assert score == 85


def test_expected_value_and_fair_odds() -> None:
    decision = evaluate_value(
        model_probability=0.60,
        market_probability=0.53,
        best_odds=1.90,
        confidence=82,
        data_quality=90,
    )
    assert expected_value(0.60, 1.90) == pytest.approx(0.14)
    assert decision.fair_odds == pytest.approx(1.666666, rel=1e-5)
    assert decision.edge == pytest.approx(0.07)
    assert decision.status == "VALUE"


def test_no_bet_wins_over_high_win_probability() -> None:
    decision = evaluate_value(
        model_probability=0.77,
        market_probability=0.82,
        best_odds=1.19,
        confidence=88,
        data_quality=92,
    )
    assert decision.status == "NO_BET"
    assert decision.reason_code == "PRICE_TOO_SHORT"


def test_market_consensus_rejects_extreme_feed_error() -> None:
    consensus = market_consensus([1.90, 1.92, 4.80])
    assert consensus.best_odds == pytest.approx(1.92)
    assert consensus.rejected_prices == (4.8,)
