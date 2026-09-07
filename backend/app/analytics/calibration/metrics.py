from math import log


def brier_score(probabilities: list[float], outcomes: list[int]) -> float:
    if len(probabilities) != len(outcomes) or not probabilities:
        raise ValueError("probability and outcome arrays must have equal non-zero length")
    if any(not 0 <= probability <= 1 for probability in probabilities):
        raise ValueError("probabilities must be in the 0..1 range")
    if any(outcome not in {0, 1} for outcome in outcomes):
        raise ValueError("outcomes must be binary")
    return sum(
        (probability - outcome) ** 2
        for probability, outcome in zip(probabilities, outcomes, strict=True)
    ) / len(outcomes)


def binary_log_loss(probabilities: list[float], outcomes: list[int]) -> float:
    if len(probabilities) != len(outcomes) or not probabilities:
        raise ValueError("probability and outcome arrays must have equal non-zero length")
    epsilon = 1e-15
    losses = []
    for probability, outcome in zip(probabilities, outcomes, strict=True):
        clipped = min(max(probability, epsilon), 1 - epsilon)
        losses.append(-(outcome * log(clipped) + (1 - outcome) * log(1 - clipped)))
    return sum(losses) / len(losses)


def calibration_curve(
    probabilities: list[float], outcomes: list[int], bins: int = 10
) -> list[dict[str, float | int]]:
    if bins < 2:
        raise ValueError("at least two calibration bins are required")
    if len(probabilities) != len(outcomes) or not probabilities:
        raise ValueError("probability and outcome arrays must have equal non-zero length")
    curve: list[dict[str, float | int]] = []
    for index in range(bins):
        lower, upper = index / bins, (index + 1) / bins
        members = [
            (probability, outcome)
            for probability, outcome in zip(probabilities, outcomes, strict=True)
            if (
                lower <= probability <= upper if index == bins - 1 else lower <= probability < upper
            )
        ]
        if members:
            curve.append(
                {
                    "lower": lower,
                    "upper": upper,
                    "count": len(members),
                    "mean_prediction": sum(item[0] for item in members) / len(members),
                    "observed_frequency": sum(item[1] for item in members) / len(members),
                }
            )
    return curve


def expected_calibration_error(
    probabilities: list[float], outcomes: list[int], bins: int = 10
) -> float:
    curve = calibration_curve(probabilities, outcomes, bins)
    total = sum(int(bucket["count"]) for bucket in curve)
    return sum(
        int(bucket["count"])
        / total
        * abs(float(bucket["mean_prediction"]) - float(bucket["observed_frequency"]))
        for bucket in curve
    )
