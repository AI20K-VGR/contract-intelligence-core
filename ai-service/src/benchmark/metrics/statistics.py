from __future__ import annotations

import statistics

import numpy as np


def describe(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {key: None for key in ("mean", "median", "std", "min", "max", "p50", "p90", "p95")} | {"n": 0}
    array = np.asarray(values, dtype=float)
    return {
        "n": len(values),
        "mean": float(array.mean()),
        "median": float(np.median(array)),
        "std": float(array.std(ddof=1)) if len(array) > 1 else 0.0,
        "min": float(array.min()),
        "max": float(array.max()),
        "p50": float(np.percentile(array, 50)),
        "p90": float(np.percentile(array, 90)),
        "p95": float(np.percentile(array, 95)),
    }


def bootstrap_ci(
    document_values: dict[str, float], *, iterations: int = 1000, confidence: float = 0.95, seed: int = 42
) -> tuple[float | None, float | None]:
    if not document_values:
        return None, None
    values = list(document_values.values())
    rng = np.random.default_rng(seed)
    samples = [statistics.mean(rng.choice(values, size=len(values), replace=True)) for _ in range(iterations)]
    alpha = (1 - confidence) / 2
    return float(np.quantile(samples, alpha)), float(np.quantile(samples, 1 - alpha))
