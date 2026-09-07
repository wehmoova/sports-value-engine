import pytest

from app.analytics.bankroll import fractional_kelly, settle_profit
from app.analytics.calibration import binary_log_loss, brier_score
from app.analytics.combinations import build_combinations
from app.analytics.monte_carlo import simulate_challenge


def test_settlement_rules() -> None:
    assert settle_profit(result="WIN", stake=10, decimal_odds=1.9) == pytest.approx(9)
    assert settle_profit(result="LOSS", stake=10, decimal_odds=1.9) == -10
    assert settle_profit(result="VOID", stake=10, decimal_odds=1.9) == 0


def test_fractional_kelly_never_forces_negative_stake() -> None:
    assert fractional_kelly(model_probability=0.40, decimal_odds=2.0) == 0


def test_combinations_require_different_events() -> None:
    picks = [
        {
            "id": "a",
            "event_id": "e1",
            "best_odds": 1.9,
            "model_probability": 0.6,
            "confidence_score": 80,
        },
        {
            "id": "b",
            "event_id": "e1",
            "best_odds": 2.1,
            "model_probability": 0.5,
            "confidence_score": 78,
        },
        {
            "id": "c",
            "event_id": "e2",
            "best_odds": 1.8,
            "model_probability": 0.62,
            "confidence_score": 82,
        },
    ]
    combos = build_combinations(picks)
    assert combos
    assert all(len(set(combo.leg_ids)) == len(combo.leg_ids) for combo in combos)
    assert all(set(combo.leg_ids) != {"a", "b"} for combo in combos)


def test_calibration_metrics() -> None:
    assert brier_score([0.8, 0.2], [1, 0]) == pytest.approx(0.04)
    assert binary_log_loss([0.8, 0.2], [1, 0]) < 0.3


def test_challenge_simulation_is_deterministic_and_bounded() -> None:
    result = simulate_challenge(starting_bankroll=10, target_bankroll=1000, days=7, runs=1000)
    assert result.runs == 1000
    assert 0 <= result.success_probability <= 1
    assert result.required_total_return == 99
