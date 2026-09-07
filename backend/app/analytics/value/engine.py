from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite
from statistics import median, quantiles


@dataclass(frozen=True)
class MarketConsensus:
    average_odds: float
    median_odds: float
    best_odds: float
    lowest_odds: float
    valid_prices: tuple[float, ...]
    rejected_prices: tuple[float, ...]


@dataclass(frozen=True)
class ValueDecision:
    model_probability: float
    market_probability: float
    fair_odds: float
    best_odds: float
    edge: float
    expected_value: float
    confidence: int
    data_quality: int
    status: str
    reason_code: str


@dataclass(frozen=True)
class OddsValidation:
    status: str
    reason: str | None


def classify_odds_prices(prices: list[float]) -> list[OddsValidation]:
    """Classify prices with robust center, MAD, IQR and relative-deviation gates."""
    finite = [price for price in prices if isfinite(price) and price > 1]
    if not finite:
        return [OddsValidation("REJECTED", "IMPOSSIBLE_PRICE") for _ in prices]
    center = median(finite)
    deviations = [abs(price - center) for price in finite]
    mad = median(deviations)
    if len(finite) >= 4:
        q1, _, q3 = quantiles(finite, n=4, method="inclusive")
        iqr = q3 - q1
    else:
        q1 = q3 = center
        iqr = 0.0
    classifications: list[OddsValidation] = []
    for price in prices:
        if not isfinite(price) or not 1.01 <= price <= 100:
            classifications.append(OddsValidation("REJECTED", "IMPOSSIBLE_PRICE"))
            continue
        relative = abs(price - center) / center
        robust_z = 0.6745 * abs(price - center) / mad if mad > 1e-9 else 0.0
        outside_iqr = iqr > 0 and (price < q1 - 3 * iqr or price > q3 + 3 * iqr)
        if relative > 0.50 and (robust_z > 6 or outside_iqr or mad <= 1e-9):
            classifications.append(OddsValidation("REJECTED", "EXTREME_MARKET_OUTLIER"))
        elif relative > 0.20 or robust_z > 3.5:
            classifications.append(OddsValidation("SUSPECT", "MARKET_DEVIATION"))
        else:
            classifications.append(OddsValidation("VALID", None))
    return classifications


def classify_odds_freshness(
    observed_at: datetime,
    *,
    now: datetime | None = None,
    stale_minutes: int = 180,
    expired_minutes: int = 720,
) -> tuple[str, int]:
    reference = now or datetime.now(UTC)
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=UTC)
    if (observed_at - reference).total_seconds() > 60:
        return "EXPIRED", 0
    age_seconds = max(0, int((reference - observed_at).total_seconds()))
    if age_seconds > expired_minutes * 60:
        return "EXPIRED", age_seconds
    if age_seconds > stale_minutes * 60:
        return "STALE", age_seconds
    return "FRESH", age_seconds


def implied_probability(decimal_odds: float) -> float:
    if not isfinite(decimal_odds) or decimal_odds <= 1:
        raise ValueError("decimal odds must be finite and greater than 1")
    return 1 / decimal_odds


def remove_vig(decimal_odds_by_selection: dict[str, float]) -> dict[str, float]:
    """Proportional margin removal for one complete bookmaker market."""
    if len(decimal_odds_by_selection) < 2:
        raise ValueError("at least two market selections are required")
    raw = {
        selection: implied_probability(price)
        for selection, price in decimal_odds_by_selection.items()
    }
    overround = sum(raw.values())
    if overround <= 0:
        raise ValueError("market overround must be positive")
    return {selection: probability / overround for selection, probability in raw.items()}


def consensus_no_vig(bookmaker_markets: list[dict[str, float]]) -> dict[str, float]:
    """Average no-vig probabilities across complete, comparable bookmaker markets."""
    if not bookmaker_markets:
        raise ValueError("at least one bookmaker market is required")
    selection_sets = [set(market) for market in bookmaker_markets]
    if any(selection_set != selection_sets[0] for selection_set in selection_sets[1:]):
        raise ValueError("bookmaker markets must contain identical selections")
    normalized = [remove_vig(market) for market in bookmaker_markets]
    return {
        selection: sum(market[selection] for market in normalized) / len(normalized)
        for selection in sorted(selection_sets[0])
    }


def market_consensus(prices: list[float], mad_multiplier: float = 4.0) -> MarketConsensus:
    """Reject obvious feed errors using median absolute deviation before aggregating."""
    clean = [price for price in prices if isfinite(price) and 1.01 <= price <= 100.0]
    if not clean:
        raise ValueError("no valid market prices")
    center = median(clean)
    deviations = [abs(price - center) for price in clean]
    mad = median(deviations)
    tolerance = max(0.12 * center, mad_multiplier * mad)
    valid = [price for price in clean if abs(price - center) <= tolerance]
    rejected = [price for price in clean if price not in valid]
    if not valid:
        valid = [center]
    return MarketConsensus(
        average_odds=sum(valid) / len(valid),
        median_odds=median(valid),
        best_odds=max(valid),
        lowest_odds=min(valid),
        valid_prices=tuple(sorted(valid)),
        rejected_prices=tuple(sorted(rejected)),
    )


def expected_value(model_probability: float, decimal_odds: float) -> float:
    if not 0 < model_probability < 1:
        raise ValueError("model probability must be between zero and one")
    implied_probability(decimal_odds)
    return model_probability * decimal_odds - 1


def confidence_score(
    *,
    model_agreement: float,
    data_quality: float,
    historical_accuracy: float,
    form_reliability: float,
    market_information: float,
    availability_certainty: float,
) -> int:
    components = (
        (model_agreement, 0.25),
        (data_quality, 0.20),
        (historical_accuracy, 0.20),
        (form_reliability, 0.15),
        (market_information, 0.10),
        (availability_certainty, 0.10),
    )
    if any(not 0 <= value <= 100 for value, _ in components):
        raise ValueError("confidence components must be in the 0..100 range")
    return round(sum(value * weight for value, weight in components))


def data_quality_score(
    *,
    freshness: float,
    sample_size: float,
    odds_freshness: float,
    bookmaker_coverage: float,
    availability_coverage: float,
    statistics_completeness: float,
    provider_consistency: float,
) -> int:
    """Deterministic data-quality composite; each input is independently auditable."""
    components = (
        (freshness, 0.18),
        (sample_size, 0.15),
        (odds_freshness, 0.18),
        (bookmaker_coverage, 0.12),
        (availability_coverage, 0.12),
        (statistics_completeness, 0.17),
        (provider_consistency, 0.08),
    )
    if any(not 0 <= value <= 100 for value, _ in components):
        raise ValueError("data quality components must be in the 0..100 range")
    return round(sum(value * weight for value, weight in components))


def evaluate_value(
    *,
    model_probability: float,
    market_probability: float,
    best_odds: float,
    confidence: int,
    data_quality: int,
    min_odds: float = 1.45,
    min_edge: float = 0.03,
    min_ev: float = 0.03,
    min_confidence: int = 70,
    min_data_quality: int = 60,
) -> ValueDecision:
    if not 0 < market_probability < 1:
        raise ValueError("market probability must be between zero and one")
    ev = expected_value(model_probability, best_odds)
    edge = model_probability - market_probability
    fair_odds = 1 / model_probability

    rules = (
        (data_quality < min_data_quality, "NO_BET", "INSUFFICIENT_DATA"),
        (confidence < min_confidence, "NO_BET", "LOW_CONFIDENCE"),
        (best_odds < min_odds, "NO_BET", "PRICE_TOO_SHORT"),
        (edge < min_edge, "NO_BET", "EDGE_BELOW_THRESHOLD"),
        (ev < min_ev, "NO_BET", "EV_BELOW_THRESHOLD"),
    )
    status, reason = "VALUE", "QUALIFIED_VALUE"
    for failed, failed_status, failed_reason in rules:
        if failed:
            status, reason = failed_status, failed_reason
            break
    return ValueDecision(
        model_probability=model_probability,
        market_probability=market_probability,
        fair_odds=fair_odds,
        best_odds=best_odds,
        edge=edge,
        expected_value=ev,
        confidence=confidence,
        data_quality=data_quality,
        status=status,
        reason_code=reason,
    )
