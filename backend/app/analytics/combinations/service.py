from dataclasses import dataclass
from itertools import combinations
from math import prod


@dataclass(frozen=True)
class CombinationCandidate:
    leg_ids: tuple[str, ...]
    category: str
    combined_odds: float
    combined_probability: float
    combined_ev: float
    confidence: int
    independence_assumed: bool
    warning: str | None


def build_combinations(
    qualified: list[dict[str, str | float | int]], max_results: int = 6
) -> list[CombinationCandidate]:
    """Combine qualified picks only, never two selections from the same event."""
    output: list[CombinationCandidate] = []
    for legs_count in (2, 3):
        for legs in combinations(qualified, legs_count):
            event_ids = [str(leg["event_id"]) for leg in legs]
            if len(set(event_ids)) != legs_count:
                continue
            combined_odds = prod(float(leg["best_odds"]) for leg in legs)
            probability = prod(float(leg["model_probability"]) for leg in legs)
            confidence = round(
                min(int(leg["confidence_score"]) for leg in legs) - (legs_count - 1) * 4
            )
            category = "LOWER_VARIANCE" if legs_count == 2 and combined_odds < 4 else "BALANCED"
            output.append(
                CombinationCandidate(
                    leg_ids=tuple(str(leg["id"]) for leg in legs),
                    category=category,
                    combined_odds=combined_odds,
                    combined_probability=probability,
                    combined_ev=probability * combined_odds - 1,
                    confidence=max(0, confidence),
                    independence_assumed=True,
                    warning=(
                        "Events are treated as independent; cross-event correlation is not "
                        "modelled."
                    ),
                )
            )
    return sorted(output, key=lambda candidate: candidate.combined_ev, reverse=True)[:max_results]
