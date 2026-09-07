"""Frozen baseline + chronological calibration + unseen, time-ordered evaluation."""

from math import isfinite, log
from typing import Any

from app.core.config import Settings
from app.research.features import timestamp
from app.sports.football.models.poisson import three_way_probabilities


def probabilities(
    features: dict[str, Any], name: str, temperature: float = 1.0
) -> list[float] | None:
    football = name.startswith("football_")
    if name == "football_poisson":
        home, away = features.get("home_goal_rate"), features.get("away_goal_rate")
        if home is None or away is None:
            return None
        p = three_way_probabilities(min(8, max(0.05, home)), min(8, max(0.05, away)))
        result = [p["HOME"], p["DRAW"], p["AWAY"]]
    else:
        key = "surface_elo_delta" if name == "tennis_surface_elo" else "elo_delta"
        delta = features.get(key)
        if delta is None:
            return None
        if name.endswith("form"):
            delta = 200 * features["form_delta"]
        strength = 1 / (1 + 10 ** (-(delta + (60 if football else 0)) / 400))
        # Fixed Davidson-style draw prior; explicit model parameter, not a statistic.
        result = (
            [strength * 0.75, 0.25, (1 - strength) * 0.75] if football else [strength, 1 - strength]
        )
    powered = [max(p, 1e-12) ** (1 / temperature) for p in result]
    return [p / sum(powered) for p in powered]


def scores(rows: list[tuple[list[float], int]]) -> dict[str, Any]:
    if not rows:
        return {
            "sample_size": 0,
            "brier": None,
            "log_loss": None,
            "ece": None,
            "calibration": [],
            "roi": None,
            "clv": None,
        }
    bins = []
    for i in range(10):
        values = [
            (max(p), float(p.index(max(p)) == y)) for p, y in rows if min(int(max(p) * 10), 9) == i
        ]
        if values:
            bins.append(
                {
                    "lower": i / 10,
                    "count": len(values),
                    "predicted": sum(p for p, _ in values) / len(values),
                    "observed": sum(y for _, y in values) / len(values),
                }
            )
    return {
        "sample_size": len(rows),
        # Multiclass sum Brier; divide by two to equal ordinary binary Brier.
        "brier": sum(sum((p - int(j == y)) ** 2 for j, p in enumerate(ps)) / 2 for ps, y in rows)
        / len(rows),
        "log_loss": -sum(log(max(ps[y], 1e-12)) for ps, y in rows) / len(rows),
        "ece": sum(b["count"] * abs(b["predicted"] - b["observed"]) for b in bins) / len(rows),
        "calibration": bins,
        "roi": None,
        "clv": None,
    }


def train_baseline(dataset: dict[str, Any], name: str) -> dict[str, Any]:
    samples = dataset["samples"]
    if len(samples) < 30:
        return {"status": "INSUFFICIENT_DATA", "model": name, "training_samples": len(samples)}
    split = max(1, int(len(samples) * 0.6))
    calibration_end = max(split + 1, int(len(samples) * 0.8))
    test_start = timestamp(samples[calibration_end]["start"])
    calibration_start = timestamp(samples[split]["start"])
    train = [s for s in samples[:split] if timestamp(s["label_available_at"]) < calibration_start]
    calibration = [
        s
        for s in samples[split:calibration_end]
        if timestamp(s["label_available_at"]) < test_start and timestamp(s["start"]) < test_start
    ]
    if len(train) < 10 or len(calibration) < 10:
        return {
            "status": "INSUFFICIENT_DATA",
            "model": name,
            "reason": "Insufficient labels available before calibration/test cutoff",
        }
    best_temperature = 1.0
    best_loss = float("inf")
    for temperature in (0.75, 1.0, 1.25, 1.5, 2.0):
        rows = [
            (p, s["outcome"])
            for s in calibration
            if (p := probabilities(s["features"], name, temperature)) is not None
        ]
        result = scores(rows)
        if result["log_loss"] is not None and result["log_loss"] < best_loss:
            best_temperature, best_loss = temperature, result["log_loss"]
    if not isfinite(best_loss):
        return {"status": "INSUFFICIENT_DATA", "model": name, "reason": "Model features absent"}
    return {
        "status": "EXPERIMENTAL",
        "model": name,
        "temperature": best_temperature,
        "training_samples": len(train),
        "calibration_samples": len(calibration),
        "training_ids": [s["event_id"] for s in train],
        "calibration_ids": [s["event_id"] for s in calibration],
        "test_start": samples[calibration_end]["start"],
        "method": "fixed_baseline_online_elo_temperature_scaling",
        "parameters": {"elo_k": 24, "home_advantage": 60, "draw_prior": 0.25},
    }


def validate(dataset: dict[str, Any], trained: dict[str, Any]) -> dict[str, Any]:
    if trained["status"] != "EXPERIMENTAL":
        return {"status": "INSUFFICIENT_DATA", "metrics": scores([])}
    at = timestamp(trained["test_start"])
    held_out = [s for s in dataset["samples"] if timestamp(s["start"]) >= at]
    used = set(trained["training_ids"] + trained["calibration_ids"])
    if any(s["event_id"] in used for s in held_out):
        raise ValueError("Training/calibration/test overlap")
    results = []
    evidence = []
    for sample in held_out:
        if timestamp(sample["latest_source_available_at"]) >= timestamp(sample["start"]):
            raise ValueError("Future feature evidence")
        p = probabilities(sample["features"], trained["model"], trained["temperature"])
        if p is not None:
            results.append((p, sample["outcome"]))
            evidence.append(
                {
                    "event_id": sample["event_id"],
                    "start": sample["start"],
                    "probabilities": p,
                    "outcome": sample["outcome"],
                    "latest_source_available_at": sample["latest_source_available_at"],
                }
            )
    return {
        "status": "EVALUATED" if results else "INSUFFICIENT_DATA",
        "method": "chronological_prequential_frozen_parameters",
        "metrics": scores(results),
        "out_of_sample": evidence,
        "market_baseline": None,
        "market_comparison_samples": 0,
        "limitations": [
            "No verified matched historical market baseline",
            "ROI/CLV unavailable without matched execution/closing odds",
        ],
    }


def promotion_checks(report: dict[str, Any], config: Settings) -> dict[str, bool]:
    metrics = report.get("metrics", {})

    def below(key: str, maximum: float) -> bool:
        value = metrics.get(key)
        return isinstance(value, (int, float)) and isfinite(value) and 0 <= value <= maximum

    return {
        "evaluated": report.get("status") == "EVALUATED",
        "minimum_samples": metrics.get("sample_size", 0) >= config.min_validation_samples,
        "brier": below("brier", config.max_validation_brier),
        "log_loss": below("log_loss", config.max_validation_log_loss),
        "calibration": below("ece", config.max_validation_ece),
        "market_comparison": report.get("market_comparison_samples", 0)
        >= config.min_validation_samples,
        # Only implemented model families can be loaded by production inference.
        "supported_model": report.get("model")
        in {
            "football_elo",
            "football_poisson",
            "football_form",
            "tennis_elo",
            "tennis_surface_elo",
            "tennis_form",
        },
        "beats_matched_market": (
            isinstance(report.get("matched_model_metrics", {}).get("brier"), (int, float))
            and isinstance((report.get("market_baseline") or {}).get("brier"), (int, float))
            and report["matched_model_metrics"]["brier"] < report["market_baseline"]["brier"]
            and report["matched_model_metrics"]["log_loss"] < report["market_baseline"]["log_loss"]
        ),
    }
