#!/usr/bin/env python3
"""wilson.py — confidence intervals for probe-first, per the IV.7 specification in
docs/research/methodology/confidence-intervals/confidence-intervals-for-probe-first_en.md

The failure this exists to stop: "the probe passed 9 of 10, so it is 90%", stated with the
confidence a 9000-of-10000 result would earn. With n=10 the honest range spans most of the
upper half of the scale, and the decision was taken on a number the sample cannot support.

Stdlib only — `math`, `statistics.NormalDist`, `argparse`, `json`. No scipy/numpy: the
harness installs into arbitrary target repos. Measured 2026-08-06: scipy+numpy is 207.8 MB
against 32.4 MB for the harness's entire 29-package required set — 6.4x, for three of the
fifteen functions here. scipy WAS used, once, out of tree, to verify the specification's own
regression anchors (it warns they are self-confirming); that check found two of them to be
the document's own rounding/convergence artefacts. See test_wilson.py.

z is COMPUTED (`NormalDist().inv_cdf`), never a looked-up table: a table is a second place
for `conf` to be wrong.

Methods:
  wilson           routine reporting — narrowest acceptable deviation
  wilson-cc        hard gate at n < 50 — continuity-corrected, never under-covers
  clopper-pearson  audits, and all-pass lower bounds (needs 72 samples where wilson needs 73)
  jeffreys         Bayesian track — much cheaper (49 samples), answers a different question
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from functools import lru_cache
from statistics import NormalDist

METHODS = ("wilson", "wilson-cc", "clopper-pearson", "jeffreys")

EXIT_OK = 0
EXIT_THRESHOLD_NOT_MET = 1
EXIT_INVALID = 2
EXIT_JUDGE_REJECTED = 3


# ----------------------------------------------------------------- validation / z

def _check_counts(k, n):
    if isinstance(k, bool) or isinstance(n, bool) or not isinstance(k, int) or not isinstance(n, int):
        raise TypeError("k and n must be ints, got %r and %r" % (type(k).__name__, type(n).__name__))
    if n < 0:
        raise ValueError("n must not be negative, got %r" % (n,))
    if k < 0 or k > n:
        raise ValueError(
            "k must be within 0..n, got %r of %r — a count exceeding its own denominator "
            "is a caller bug, not a rate to clamp" % (k, n))


def _check_conf(conf):
    if not isinstance(conf, (int, float)) or isinstance(conf, bool):
        raise TypeError("conf must be a number, got %r" % (type(conf).__name__,))
    if not (0.0 < conf < 1.0):
        raise ValueError("conf must be strictly inside (0, 1), got %r" % (conf,))


def z_for(conf: float) -> float:
    """Two-sided normal quantile. Computed, not tabulated."""
    _check_conf(conf)
    return NormalDist().inv_cdf(1.0 - (1.0 - conf) / 2.0)


Z_95 = z_for(0.95)


# --------------------------------------------------------- incomplete beta / quantile

def _log_beta(a: float, b: float) -> float:
    return math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)


def _betacf(a: float, b: float, x: float) -> float:
    """Lentz's continued fraction for the incomplete beta. Chosen over numeric integration
    because it converges in tens of iterations at any (a, b) this module sees."""
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    return h


def betainc(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta I_x(a, b).

    The prefactor is assembled ENTIRELY IN LOG SPACE — `exp(a·ln x + b·ln(1−x) − lnB)` — and
    never as `integral / exp(lnB)`. Dividing afterwards underflows `exp(lnB)` to 0 once
    a+b >= 500 and raises ZeroDivisionError. The specification records that as a bug hit for
    real while the document was written, and as a mandatory test case."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    log_front = a * math.log(x) + b * math.log1p(-x) - _log_beta(a, b)
    if x < (a + 1.0) / (a + b + 2.0):
        return math.exp(log_front) * _betacf(a, b, x) / a
    return 1.0 - math.exp(log_front) * _betacf(b, a, 1.0 - x) / b


@lru_cache(maxsize=4096)
def beta_ppf(p: float, a: float, b: float) -> float:
    """Beta quantile by bisection on `betainc`. Cached: Clopper-Pearson at n >= 500 calls it
    repeatedly with the same arguments, and the spec budgets < 100 ms for that case."""
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if betainc(a, b, mid) < p:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-15:
            break
    return (lo + hi) / 2.0


# --------------------------------------------------------------------- the intervals

def _wilson(k, n, z):
    p_hat = k / n
    z2_over_n = z * z / n
    denom = 1.0 + z2_over_n
    center = (p_hat + z2_over_n / 2.0) / denom
    half = (z / denom) * math.sqrt(p_hat * (1.0 - p_hat) / n + z * z / (4.0 * n * n))
    return center, half


def _wilson_cc(k, n, z):
    """Continuity-corrected Wilson. Wider than plain Wilson by design: plain Wilson's real
    coverage dips to ~90% at extreme p (measured: 0.9044 at n=10, p=0.99), which is a gate
    passing 1-in-10 more often than its label claims. Has NO reference implementation in
    scipy or statsmodels — `coverage()` below is the only independent check it can get."""
    p_hat = k / n
    q_hat = 1.0 - p_hat
    z2 = z * z
    denom = 2.0 * (n + z2)
    if k == 0:
        lower = 0.0
    else:
        root = math.sqrt(max(0.0, z2 - 2.0 - 1.0 / n + 4.0 * p_hat * (n * q_hat + 1.0)))
        lower = (2.0 * n * p_hat + z2 - 1.0 - z * root) / denom
    if k == n:
        upper = 1.0
    else:
        root = math.sqrt(max(0.0, z2 + 2.0 - 1.0 / n + 4.0 * p_hat * (n * q_hat - 1.0)))
        upper = (2.0 * n * p_hat + z2 + 1.0 + z * root) / denom
    return max(0.0, lower), min(1.0, upper)


def _clopper_pearson(k, n, conf):
    alpha = 1.0 - conf
    lower = 0.0 if k == 0 else beta_ppf(alpha / 2.0, float(k), float(n - k + 1))
    upper = 1.0 if k == n else beta_ppf(1.0 - alpha / 2.0, float(k + 1), float(n - k))
    return lower, upper


def _jeffreys(k, n, conf):
    alpha = 1.0 - conf
    a, b = k + 0.5, n - k + 0.5
    lower = 0.0 if k == 0 else beta_ppf(alpha / 2.0, a, b)
    upper = 1.0 if k == n else beta_ppf(1.0 - alpha / 2.0, a, b)
    return lower, upper


def interval(k: int, n: int, conf: float = 0.95, method: str = "wilson"):
    """`(lower, upper)`.

    n == 0 returns (0.0, 1.0) rather than raising: zero samples is "no evidence", and the
    honest interval for no evidence is the whole scale. Raising would push every caller into
    a try/except, and the except branch is where an honest answer becomes a convenient one.

    k == 0 pins lower to exactly 0.0 and k == n pins upper to exactly 1.0 — algebraically
    exact, and float arithmetic misses it by an ulp (measured: 0.9999999999999999)."""
    _check_counts(k, n)
    _check_conf(conf)
    if method not in METHODS:
        raise ValueError("method must be one of %r, got %r" % (list(METHODS), method))
    if n == 0:
        return (0.0, 1.0)

    if method == "wilson":
        center, half = _wilson(k, n, z_for(conf))
        lower, upper = max(0.0, center - half), min(1.0, center + half)
    elif method == "wilson-cc":
        lower, upper = _wilson_cc(k, n, z_for(conf))
    elif method == "clopper-pearson":
        lower, upper = _clopper_pearson(k, n, conf)
    else:
        lower, upper = _jeffreys(k, n, conf)

    if k == 0:
        lower = 0.0
    if k == n:
        upper = 1.0
    return (lower, upper)


def interval_full(k: int, n: int, conf: float = 0.95, method: str = "wilson") -> dict:
    lower, upper = interval(k, n, conf, method)
    z = z_for(conf)
    if n == 0:
        center = half = float("nan")
        p_hat = float("nan")
    else:
        p_hat = k / n
        center, half = _wilson(k, n, z) if method in ("wilson", "wilson-cc") else ((lower + upper) / 2.0, (upper - lower) / 2.0)
    return {"k": k, "n": n, "conf": conf, "method": method, "p_hat": p_hat, "z": z,
            "center": center, "half_width": half, "lower": lower, "upper": upper,
            "width": upper - lower}


# ------------------------------------------------------------------ coverage & sizing

def coverage(n: int, p: float, conf: float = 0.95, method: str = "wilson") -> float:
    """Real coverage: sum EXACTLY over k = 0..n of P(k | n, p) where the interval contains p.
    No simulation — `math.comb` is exact, so the only error is float summation.

    This is the module's own independent check, and the only one `wilson-cc` can get."""
    if not isinstance(n, int) or n < 1:
        raise ValueError("n must be a positive int, got %r" % (n,))
    if not (0.0 <= p <= 1.0):
        raise ValueError("p must be in [0, 1], got %r" % (p,))
    total = 0.0
    for k in range(n + 1):
        lo, hi = interval(k, n, conf, method)
        if lo <= p <= hi:
            total += math.comb(n, k) * (p ** k) * ((1.0 - p) ** (n - k))
    return total


def min_n_all_pass(target: float, conf: float = 0.95, method: str = "wilson",
                   max_n: int = 100000) -> int:
    """Smallest n whose all-pass (k == n) lower bound reaches `target`."""
    if not (0.0 < target < 1.0):
        raise ValueError("target must be strictly inside (0, 1), got %r" % (target,))
    for n in range(1, max_n + 1):
        if interval(n, n, conf, method)[0] >= target:
            return n
    raise ValueError("no n <= %d reaches target %r" % (max_n, target))


def max_fails(n: int, target: float, conf: float = 0.95, method: str = "wilson"):
    """How many failures `n` samples can absorb and still clear `target`. None when even a
    perfect run cannot — which is the answer that stops a doomed probe before it runs."""
    _check_counts(0, n)
    if not (0.0 < target < 1.0):
        raise ValueError("target must be strictly inside (0, 1), got %r" % (target,))
    best = None
    for fails in range(0, n + 1):
        if interval(n - fails, n, conf, method)[0] >= target:
            best = fails
        else:
            break
    return best


# --------------------------------------------------------------------------- clusters

def icc_anova(clusters):
    """One-way random-effects ICC from the data. None when K < 2.

    ICC is COMPUTED, never declared: III.2.8 shows no default constant is safe, so there is
    deliberately no `--icc` anywhere in this module."""
    clusters = [(int(k), int(n)) for k, n in (clusters or [])]
    K = len(clusters)
    if K < 2:
        return None
    N = sum(n for _, n in clusters)
    if N <= K:
        return None
    for k, n in clusters:
        _check_counts(k, n)
    p_bar = sum(k for k, _ in clusters) / N
    if p_bar in (0.0, 1.0):
        return {"icc": 0.0, "n0": N / K, "msb": 0.0, "msw": 0.0, "K": K, "N": N}
    msb = sum(n * ((k / n) - p_bar) ** 2 for k, n in clusters) / (K - 1)
    msw = sum(k * (1.0 - k / n) for k, n in clusters) / (N - K)
    n0 = (N - sum(n * n for _, n in clusters) / N) / (K - 1)
    denom = msb + (n0 - 1.0) * msw
    icc = 0.0 if denom == 0 else max(0.0, (msb - msw) / denom)
    return {"icc": icc, "n0": n0, "msb": msb, "msw": msw, "K": K, "N": N}


def _f_ppf(p: float, d1: float, d2: float) -> float:
    """F quantile via the Beta relation — no new machinery, and the Beta quantile is already
    load-bearing here."""
    x = beta_ppf(p, d1 / 2.0, d2 / 2.0)
    if x >= 1.0:
        return float("inf")
    return (d2 / d1) * x / (1.0 - x)


def _icc_upper(stats, conf):
    """Upper confidence bound on ICC (one-way random ANOVA, F-based). Used at 10 <= K < 20,
    where the point estimate is biased LOW — and biased low means penalising less than
    required, which errs in the dangerous direction."""
    K, N, msb, msw, n0 = stats["K"], stats["N"], stats["msb"], stats["msw"], stats["n0"]
    if msw <= 0 or msb <= 0:
        return 1.0
    alpha = 1.0 - conf
    f_obs = msb / msw
    f_u = f_obs * _f_ppf(1.0 - alpha / 2.0, N - K, K - 1)
    if math.isinf(f_u):
        return 1.0
    return min(1.0, max(0.0, (f_u - 1.0) / (f_u + n0 - 1.0)))


def cluster_adjusted(clusters, conf: float = 0.95, pass_threshold: float = 1.0) -> dict:
    """Wilson on non-independent samples, routed BY CLUSTER COUNT — never by a declared ICC.

      K >= 20   'icc'           point estimate is stable enough
      10<=K<20  'icc-upper'     estimate, but take its upper bound
      K < 10    'cluster-floor' one sample per cluster; do not guess ICC

    The route is returned and must be printed: which correction ran changes what the number
    means. `pass_threshold` only bites on the cluster-floor route; the spec leaves its origin
    open (IV.10 Q6) and defaults it to 1.0 — a cluster counts only if it is clean, matching
    the document's own worked example."""
    clusters = [(int(k), int(n)) for k, n in (clusters or [])]
    K = len(clusters)
    if K == 0:
        raise ValueError("no clusters given")
    N = sum(n for _, n in clusters)
    total_k = sum(k for k, _ in clusters)

    if K < 10:
        passed = sum(1 for k, n in clusters if n > 0 and (k / n) >= pass_threshold)
        lower, upper = interval(passed, K, conf, "wilson")
        return {"route": "cluster-floor", "icc": None, "deff": None, "n_eff": float(K),
                "lower": lower, "upper": upper, "K": K, "N": N,
                "clusters_passed": passed, "pass_threshold": pass_threshold}

    stats = icc_anova(clusters)
    if stats is None:
        raise ValueError("cannot estimate ICC from %d cluster(s)" % K)
    icc = stats["icc"] if K >= 20 else _icc_upper(stats, conf)
    route = "icc" if K >= 20 else "icc-upper"
    m = N / K
    deff = 1.0 + (m - 1.0) * icc
    n_eff = N / deff if deff > 0 else float(N)
    p_bar = total_k / N
    k_eff = int(round(p_bar * n_eff))
    n_eff_int = max(1, int(round(n_eff)))
    k_eff = min(k_eff, n_eff_int)
    lower, upper = interval(k_eff, n_eff_int, conf, "wilson")
    return {"route": route, "icc": icc, "deff": deff, "n_eff": n_eff,
            "lower": lower, "upper": upper, "K": K, "N": N}


# ------------------------------------------------------------------------ comparison

def mcnemar_wilson(b: int, c: int, conf: float = 0.95) -> dict:
    """Two candidates, SAME test set. Only the discordant pairs carry information: b won by
    A, c won by B. Conclusive when the interval excludes 0.5."""
    for name, v in (("b", b), ("c", c)):
        if isinstance(v, bool) or not isinstance(v, int) or v < 0:
            raise ValueError("%s must be a non-negative int, got %r" % (name, v))
    n_disc = b + c
    if n_disc == 0:
        return {"n_disc": 0, "lower": 0.0, "upper": 1.0, "conclusive": False}
    lower, upper = interval(b, n_disc, conf, "wilson")
    return {"n_disc": n_disc, "lower": lower, "upper": upper,
            "conclusive": not (lower <= 0.5 <= upper)}


def diff_newcombe(k1: int, n1: int, k2: int, n2: int, conf: float = 0.95) -> dict:
    """Two candidates, DIFFERENT test sets — Newcombe's hybrid-score difference interval.

    There is deliberately no `intervals_overlap()` anywhere in this module: "the intervals
    overlap, so there is no difference" is a reading error (III.4.5), and a function with
    that name would ship the error as an API."""
    l1, u1 = interval(k1, n1, conf, "wilson")
    l2, u2 = interval(k2, n2, conf, "wilson")
    p1, p2 = (k1 / n1 if n1 else 0.0), (k2 / n2 if n2 else 0.0)
    diff = p1 - p2
    lower = diff - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    upper = diff + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return {"diff": diff, "lower": lower, "upper": upper,
            "conclusive": not (lower <= 0.0 <= upper)}


# ----------------------------------------------------------------------------- judge

def judge_screen(TP: int, FN: int, TN: int, FP: int, conf: float = 0.95) -> dict:
    """Tier 1 — is this LLM judge usable as a ruler at all?

    Rejected when Youden's J < 0.5, or when either arm of the calibration set is empty: a
    judge never shown a true negative has an unmeasured specificity, and an unmeasured
    number is not a small number."""
    for name, v in (("TP", TP), ("FN", FN), ("TN", TN), ("FP", FP)):
        if isinstance(v, bool) or not isinstance(v, int) or v < 0:
            raise ValueError("%s must be a non-negative int, got %r" % (name, v))
    pos, neg = TP + FN, TN + FP
    n_calib = pos + neg
    if pos == 0 or neg == 0:
        return {"sens": None, "spec": None, "sens_ci": (0.0, 1.0), "spec_ci": (0.0, 1.0),
                "youden_j": None, "verdict": "rejected", "bias_direction": None,
                "n_calib": n_calib}
    sens, spec = TP / pos, TN / neg
    j = sens + spec - 1.0
    if j < 0.5:
        verdict = "rejected"
    elif abs(sens - spec) > 0.15:
        verdict = "biased"
    else:
        verdict = "ok"
    bias = None if verdict == "ok" else ("lenient" if sens > spec else "strict")
    return {"sens": sens, "spec": spec,
            "sens_ci": interval(TP, pos, conf, "wilson"),
            "spec_ci": interval(TN, neg, conf, "wilson"),
            "youden_j": j, "verdict": verdict, "bias_direction": bias, "n_calib": n_calib}


def rogan_gladen(p_obs: float, sens: float, spec: float):
    """True rate behind a judge's observed rate. None when sens + spec <= 1 — a judge no
    better than a coin has nothing to invert."""
    j = sens + spec - 1.0
    if j <= 0:
        return None
    return (p_obs + spec - 1.0) / j


def judge_adjust(k: int, n: int, TP: int, FN: int, TN: int, FP: int,
                 conf: float = 0.95, split: int = 3) -> dict:
    """Tier 2 — the observed rate corrected for the judge, carrying BOTH uncertainty tiers.

    Bonferroni: the alpha is split `split` ways across p_obs, sens and spec, then the corner
    envelope of Rogan-Gladen over the three boxes is taken. Conservative and auditable; a
    bootstrap would be tighter and is out of scope for v1.

    Returns raw_lower/raw_upper UNCLAMPED alongside the clamped pair. III.3.10: a corrected
    interval clamped to [0,1] can look narrow and reassuring precisely when the judge is bad,
    and the raw values are what show it."""
    screen = judge_screen(TP, FN, TN, FP, conf)
    if screen["verdict"] == "rejected" or not screen["youden_j"] or screen["youden_j"] <= 0:
        return {"lower": 0.0, "upper": 1.0, "raw_lower": 0.0, "raw_upper": 1.0,
                "saturated_low": False, "saturated_high": False, "verdict": "rejected",
                "screen": screen}
    sub_conf = 1.0 - (1.0 - conf) / split
    p_lo, p_hi = interval(k, n, sub_conf, "wilson")
    s_lo, s_hi = interval(TP, TP + FN, sub_conf, "wilson")
    q_lo, q_hi = interval(TN, TN + FP, sub_conf, "wilson")

    corners = [rogan_gladen(p, s, q)
               for p in (p_lo, p_hi) for s in (s_lo, s_hi) for q in (q_lo, q_hi)]
    corners = [c for c in corners if c is not None]
    if not corners:
        return {"lower": 0.0, "upper": 1.0, "raw_lower": 0.0, "raw_upper": 1.0,
                "saturated_low": False, "saturated_high": False, "verdict": "rejected",
                "screen": screen}
    raw_lower, raw_upper = min(corners), max(corners)
    return {"lower": max(0.0, raw_lower), "upper": min(1.0, raw_upper),
            "raw_lower": raw_lower, "raw_upper": raw_upper,
            "saturated_low": raw_lower < 0.0, "saturated_high": raw_upper > 1.0,
            "verdict": screen["verdict"], "screen": screen}


# -------------------------------------------------------------------------- Bayesian

def jeffreys(k: int, n: int, conf: float = 0.95):
    return interval(k, n, conf, "jeffreys")


def posterior_prob_ge(k: int, n: int, T: float, prior_a: float = 0.5, prior_b: float = 0.5) -> float:
    """P(p >= T | data) under a Beta prior. The number a ship decision actually wants —
    Wilson answers a different question and saying otherwise is the sentence in III.6.2."""
    _check_counts(k, n)
    if not (0.0 <= T <= 1.0):
        raise ValueError("T must be in [0, 1], got %r" % (T,))
    return 1.0 - betainc(prior_a + k, prior_b + (n - k), T)


def prior_from_evidence(k_old: int, n_old: int, weight: float):
    """A Beta prior from earlier evidence, down-weighted.

    RAISES above weight 0.5, deliberately: III.6.10 forbids w = 1.0, and a rule the tool
    refuses to break is worth more than a rule written down."""
    _check_counts(k_old, n_old)
    if not isinstance(weight, (int, float)) or isinstance(weight, bool):
        raise TypeError("weight must be a number, got %r" % (type(weight).__name__,))
    if weight < 0:
        raise ValueError("weight must not be negative, got %r" % (weight,))
    if weight > 0.5:
        raise ValueError(
            "weight %r exceeds 0.5 — reusing old evidence at full strength lets one prior "
            "outvote the run you just did (III.6.10)" % (weight,))
    return (0.5 + k_old * weight, 0.5 + (n_old - k_old) * weight)


# ------------------------------------------------------------------------------- CLI

def _render(full: dict) -> str:
    hint = "   (pulled toward 0.5 by small n)" if full["n"] and full["n"] < 30 else ""
    return ("k=%d  n=%d  conf=%.0f%%  method=%s\n"
            "p_hat  = %.4f\n"
            "center = %.4f%s\n"
            "CI     = [%.4f, %.4f]   width = %.4f"
            % (full["k"], full["n"], full["conf"] * 100, full["method"],
               full["p_hat"], full["center"], hint,
               full["lower"], full["upper"], full["width"]))


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="confidence intervals for probe-first")
    p.add_argument("--k", type=int)
    p.add_argument("--n", type=int)
    p.add_argument("--conf", type=float, default=0.95)
    p.add_argument("--method", choices=list(METHODS), default="wilson")
    p.add_argument("--json", action="store_true")
    p.add_argument("--threshold", type=float)
    p.add_argument("--min-n", type=float)
    p.add_argument("--max-fails", action="store_true")
    p.add_argument("--clusters")
    p.add_argument("--strata")
    p.add_argument("--mcnemar", action="store_true")
    p.add_argument("--b", type=int)
    p.add_argument("--c", type=int)
    p.add_argument("--diff", action="store_true")
    p.add_argument("--k1", type=int)
    p.add_argument("--n1", type=int)
    p.add_argument("--k2", type=int)
    p.add_argument("--n2", type=int)
    p.add_argument("--judge-screen", action="store_true")
    p.add_argument("--judge-adjust", action="store_true")
    p.add_argument("--tp", type=int)
    p.add_argument("--fn", type=int)
    p.add_argument("--tn", type=int)
    p.add_argument("--fp", type=int)
    p.add_argument("--bayes", action="store_true")
    p.add_argument("--prob-ge", type=float)
    p.add_argument("--prior-k", type=int)
    p.add_argument("--prior-n", type=int)
    p.add_argument("--prior-weight", type=float)
    return p


def _emit(payload, as_json, text):
    print(json.dumps(payload) if as_json else text)


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.clusters:
            res = cluster_adjusted(
                [(c["k"], c["n"]) for c in _load(args.clusters)["clusters"]], args.conf)
            _emit(res, args.json,
                  "route=%s  K=%d  N=%d  n_eff=%s\nCI = [%.4f, %.4f]"
                  % (res["route"], res["K"], res["N"],
                     ("%.1f" % res["n_eff"]), res["lower"], res["upper"]))
        elif args.strata:
            strata = _load(args.strata)["strata"]
            # Bonferroni once K >= 5: more strata means more chances for one to look bad
            # by luck alone, and an uncorrected per-stratum alpha turns that into a finding.
            conf = args.conf if len(strata) < 5 else 1.0 - (1.0 - args.conf) / len(strata)
            rows = [{"name": s.get("name"), "k": s["k"], "n": s["n"],
                     **dict(zip(("lower", "upper"), interval(s["k"], s["n"], conf, args.method)))}
                    for s in strata]
            payload = {"conf_each": conf, "bonferroni": len(strata) >= 5, "strata": rows}
            _emit(payload, args.json, "\n".join(
                "%-20s %d/%d  [%.4f, %.4f]" % (r["name"], r["k"], r["n"], r["lower"], r["upper"])
                for r in rows))
        elif args.mcnemar:
            res = mcnemar_wilson(args.b, args.c, args.conf)
            _emit(res, args.json, "n_disc=%d  CI=[%.4f, %.4f]  conclusive=%s"
                  % (res["n_disc"], res["lower"], res["upper"], res["conclusive"]))
        elif args.diff:
            res = diff_newcombe(args.k1, args.n1, args.k2, args.n2, args.conf)
            _emit(res, args.json, "diff=%+.4f  CI=[%+.4f, %+.4f]  conclusive=%s"
                  % (res["diff"], res["lower"], res["upper"], res["conclusive"]))
        elif args.judge_screen:
            res = judge_screen(args.tp, args.fn, args.tn, args.fp, args.conf)
            _emit(res, args.json, "sens=%s spec=%s J=%s verdict=%s"
                  % (res["sens"], res["spec"], res["youden_j"], res["verdict"]))
            return EXIT_JUDGE_REJECTED if res["verdict"] == "rejected" else EXIT_OK
        elif args.judge_adjust:
            res = judge_adjust(args.k, args.n, args.tp, args.fn, args.tn, args.fp, args.conf)
            _emit(res, args.json,
                  "CI=[%.4f, %.4f]  raw=[%.4f, %.4f]  saturated=(%s,%s)  verdict=%s"
                  % (res["lower"], res["upper"], res["raw_lower"], res["raw_upper"],
                     res["saturated_low"], res["saturated_high"], res["verdict"]))
            return EXIT_JUDGE_REJECTED if res["verdict"] == "rejected" else EXIT_OK
        elif args.min_n is not None:
            n = min_n_all_pass(args.min_n, args.conf, args.method)
            _emit({"min_n_all_pass": n, "target": args.min_n, "method": args.method},
                  args.json, "min_n_all_pass(%.2f, %s) = %d" % (args.min_n, args.method, n))
        elif args.max_fails:
            f = max_fails(args.n, args.threshold, args.conf, args.method)
            _emit({"max_fails": f, "n": args.n, "threshold": args.threshold},
                  args.json, "max_fails(n=%d, threshold=%.2f) = %s" % (args.n, args.threshold, f))
        elif args.prob_ge is not None:
            a, b = (0.5, 0.5)
            if args.prior_k is not None and args.prior_n is not None:
                a, b = prior_from_evidence(args.prior_k, args.prior_n, args.prior_weight or 0.0)
            prob = posterior_prob_ge(args.k, args.n, args.prob_ge, a, b)
            _emit({"prob_ge": prob, "T": args.prob_ge, "prior_a": a, "prior_b": b},
                  args.json, "P(p >= %.2f | data) = %.4f" % (args.prob_ge, prob))
        else:
            method = "jeffreys" if args.bayes else args.method
            if args.prior_k is not None and args.prior_n is not None:
                a, b = prior_from_evidence(args.prior_k, args.prior_n, args.prior_weight or 0.0)
                lo = beta_ppf((1 - args.conf) / 2, a + args.k, b + (args.n - args.k))
                hi = beta_ppf(1 - (1 - args.conf) / 2, a + args.k, b + (args.n - args.k))
                _emit({"lower": lo, "upper": hi, "prior_a": a, "prior_b": b},
                      args.json, "posterior CI = [%.4f, %.4f]  prior Beta(%.2f, %.2f)" % (lo, hi, a, b))
            else:
                full = interval_full(args.k, args.n, args.conf, method)
                _emit(full, args.json, _render(full))
                if args.threshold is not None:
                    return EXIT_OK if full["lower"] >= args.threshold else EXIT_THRESHOLD_NOT_MET
    except (ValueError, TypeError, KeyError, FileNotFoundError) as e:
        print("error: %s" % e, file=sys.stderr)
        return EXIT_INVALID
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
