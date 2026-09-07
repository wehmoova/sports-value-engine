from dataclasses import dataclass
from math import prod

import numpy as np


@dataclass(frozen=True)
class ChallengeResult:
    required_total_return: float
    required_daily_growth: float
    success_probability: float
    risk_of_ruin: float
    median_ending_bankroll: float
    expected_ending_bankroll: float
    percentile_5: float
    percentile_95: float
    median_max_drawdown: float
    runs: int


def simulate_challenge(
    *,
    starting_bankroll: float,
    target_bankroll: float,
    days: int,
    daily_opportunities: int = 2,
    stake_fraction: float = 0.01,
    win_probability: float = 0.56,
    average_odds: float = 1.9,
    runs: int = 10_000,
    seed: int = 42,
) -> ChallengeResult:
    if starting_bankroll <= 0 or target_bankroll <= starting_bankroll or days <= 0:
        raise ValueError("challenge values must be positive and target must exceed start")
    if not 0 < stake_fraction <= 0.1 or not 0 < win_probability < 1 or average_odds <= 1:
        raise ValueError("invalid simulation assumptions")
    runs = min(max(runs, 1_000), 100_000)
    rng = np.random.default_rng(seed)
    bankrolls = np.full(runs, starting_bankroll, dtype=float)
    peaks = bankrolls.copy()
    max_drawdowns = np.zeros(runs, dtype=float)
    ruined = np.zeros(runs, dtype=bool)
    for _ in range(days * daily_opportunities):
        stake = bankrolls * stake_fraction
        wins = rng.random(runs) < win_probability
        bankrolls += np.where(wins, stake * (average_odds - 1), -stake)
        peaks = np.maximum(peaks, bankrolls)
        drawdown = np.divide(peaks - bankrolls, peaks, out=np.zeros_like(peaks), where=peaks > 0)
        max_drawdowns = np.maximum(max_drawdowns, drawdown)
        ruined |= bankrolls < starting_bankroll * 0.1
    required_total_return = target_bankroll / starting_bankroll - 1
    required_daily_growth = prod([target_bankroll / starting_bankroll]) ** (1 / days) - 1
    return ChallengeResult(
        required_total_return=required_total_return,
        required_daily_growth=required_daily_growth,
        success_probability=float(np.mean(bankrolls >= target_bankroll)),
        risk_of_ruin=float(np.mean(ruined)),
        median_ending_bankroll=float(np.median(bankrolls)),
        expected_ending_bankroll=float(np.mean(bankrolls)),
        percentile_5=float(np.percentile(bankrolls, 5)),
        percentile_95=float(np.percentile(bankrolls, 95)),
        median_max_drawdown=float(np.median(max_drawdowns)),
        runs=runs,
    )
