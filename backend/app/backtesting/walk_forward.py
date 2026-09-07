from dataclasses import dataclass
from datetime import datetime
from math import log


@dataclass(frozen=True)
class WalkForwardSplit:
    train_indices: tuple[int, ...]
    test_indices: tuple[int, ...]


@dataclass(frozen=True)
class BacktestMetrics:
    total_bets: int
    wins: int
    losses: int
    win_rate: float
    profit: float
    roi: float
    yield_pct: float
    average_odds: float
    expected_value: float
    closing_line_value: float | None
    max_drawdown: float
    brier_score: float
    log_loss: float


def walk_forward_splits(
    timestamps: list[datetime], *, min_train_size: int, test_size: int
) -> list[WalkForwardSplit]:
    """Return strictly chronological expanding-window splits without data leakage."""
    if timestamps != sorted(timestamps):
        raise ValueError("timestamps must be sorted chronologically")
    if min_train_size < 1 or test_size < 1:
        raise ValueError("split sizes must be positive")
    splits: list[WalkForwardSplit] = []
    train_end = min_train_size
    while train_end < len(timestamps):
        test_end = min(train_end + test_size, len(timestamps))
        splits.append(
            WalkForwardSplit(
                train_indices=tuple(range(train_end)),
                test_indices=tuple(range(train_end, test_end)),
            )
        )
        train_end = test_end
    return splits


def compute_metrics(records: list[dict[str, float | int | None]]) -> BacktestMetrics:
    if not records:
        raise ValueError("at least one settled record is required")
    stakes = [float(record["stake"] or 0) for record in records]
    profits = [float(record["profit"] or 0) for record in records]
    probabilities = [float(record["model_probability"] or 0) for record in records]
    outcomes = [int(record["outcome"] or 0) for record in records]
    odds = [float(record["odds"] or 0) for record in records]
    closing = [record.get("closing_odds") for record in records]
    total_staked = sum(stakes)
    if total_staked <= 0:
        raise ValueError("total stake must be positive")
    bankroll = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for profit in profits:
        bankroll += profit
        peak = max(peak, bankroll)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - bankroll) / peak)
    epsilon = 1e-15
    brier = sum(
        (probability - outcome) ** 2
        for probability, outcome in zip(probabilities, outcomes, strict=True)
    ) / len(records)
    logloss = -sum(
        outcome * log(min(max(probability, epsilon), 1 - epsilon))
        + (1 - outcome) * log(1 - min(max(probability, epsilon), 1 - epsilon))
        for probability, outcome in zip(probabilities, outcomes, strict=True)
    ) / len(records)
    valid_clv = [
        price / float(close) - 1
        for close, price in zip(closing, odds, strict=True)
        if close is not None and price > 0
    ]
    return BacktestMetrics(
        total_bets=len(records),
        wins=sum(outcomes),
        losses=len(records) - sum(outcomes),
        win_rate=sum(outcomes) / len(records),
        profit=sum(profits),
        roi=sum(profits) / total_staked,
        yield_pct=sum(profits) / total_staked,
        average_odds=sum(odds) / len(records),
        expected_value=sum(
            probability * price - 1 for probability, price in zip(probabilities, odds, strict=True)
        )
        / len(records),
        closing_line_value=sum(valid_clv) / len(valid_clv) if valid_clv else None,
        max_drawdown=max_drawdown,
        brier_score=brier,
        log_loss=logloss,
    )
