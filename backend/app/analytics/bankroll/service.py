def settle_profit(*, result: str, stake: float, decimal_odds: float) -> float:
    if stake < 0 or decimal_odds <= 1:
        raise ValueError("stake must be non-negative and decimal odds greater than one")
    normalized = result.upper()
    if normalized == "WIN":
        return stake * (decimal_odds - 1)
    if normalized == "LOSS":
        return -stake
    if normalized == "HALF_WIN":
        return stake * (decimal_odds - 1) / 2
    if normalized == "HALF_LOSS":
        return -stake / 2
    if normalized in {"PUSH", "VOID"}:
        return 0.0
    raise ValueError(f"unknown settlement result: {result}")


def fractional_kelly(
    *, model_probability: float, decimal_odds: float, fraction: float = 0.25
) -> float:
    if not 0 < model_probability < 1 or decimal_odds <= 1 or not 0 <= fraction <= 1:
        raise ValueError("invalid Kelly inputs")
    net_odds = decimal_odds - 1
    full_kelly = (net_odds * model_probability - (1 - model_probability)) / net_odds
    return max(0.0, full_kelly * fraction)
