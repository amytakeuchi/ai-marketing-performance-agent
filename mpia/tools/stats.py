"""Small, dependency-free statistics helpers."""
from __future__ import annotations

import math


def two_prop_z(x1: float, n1: float, x2: float, n2: float) -> tuple[float, float]:
    """Two-proportion z-test (pooled). Returns (z, two-sided p). Degenerate inputs -> (0, 1)."""
    if n1 <= 0 or n2 <= 0:
        return 0.0, 1.0
    p1, p2 = x1 / n1, x2 / n2
    p = (x1 + x2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    if se == 0:
        return 0.0, 1.0
    z = (p1 - p2) / se
    return z, math.erfc(abs(z) / math.sqrt(2))


def binom_ll(x: float, n: float, p: float) -> float:
    p = min(max(p, 1e-9), 1 - 1e-9)
    return x * math.log(p) + (n - x) * math.log(1 - p)


def change_point(successes: list[float], trials: list[float], min_seg: int = 4) -> dict | None:
    """Best single split of a daily rate series by binomial log-likelihood ratio.
    Returns {index, rate_before, rate_after, llr} or None if the series is too short."""
    n = len(successes)
    if n < 2 * min_seg:
        return None
    X, N = sum(successes), sum(trials)
    if N == 0:
        return None
    ll0 = binom_ll(X, N, X / N)
    best = None
    for i in range(min_seg, n - min_seg + 1):
        x1, n1 = sum(successes[:i]), sum(trials[:i])
        x2, n2 = sum(successes[i:]), sum(trials[i:])
        if n1 == 0 or n2 == 0:
            continue
        llr = binom_ll(x1, n1, x1 / n1) + binom_ll(x2, n2, x2 / n2) - ll0
        if best is None or llr > best["llr"]:
            best = {"index": i, "rate_before": x1 / n1, "rate_after": x2 / n2, "llr": llr}
    return best
