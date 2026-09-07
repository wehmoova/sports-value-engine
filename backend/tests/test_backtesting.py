from datetime import UTC, datetime, timedelta

import pytest

from app.backtesting import compute_metrics, walk_forward_splits


def test_walk_forward_never_uses_future_training_rows() -> None:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    timestamps = [start + timedelta(days=day) for day in range(10)]
    splits = walk_forward_splits(timestamps, min_train_size=4, test_size=2)
    assert len(splits) == 3
    assert all(max(split.train_indices) < min(split.test_indices) for split in splits)


def test_backtest_metrics_include_clv_and_calibration() -> None:
    records = [
        {
            "stake": 10,
            "profit": 9,
            "model_probability": 0.6,
            "outcome": 1,
            "odds": 1.9,
            "closing_odds": 1.8,
        },
        {
            "stake": 10,
            "profit": -10,
            "model_probability": 0.55,
            "outcome": 0,
            "odds": 1.95,
            "closing_odds": 1.85,
        },
    ]
    metrics = compute_metrics(records)
    assert metrics.total_bets == 2
    assert metrics.profit == -1
    assert metrics.roi == pytest.approx(-0.05)
    assert metrics.closing_line_value is not None
