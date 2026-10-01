"""
Deterministic scoring engine for ai2_contract_package evaluation.

Scaffold variables:
    ai2_contract_package       — eval domain name (e.g., cv_extraction, chatbot_quality)
    public result schema and evidence rules     — P0 hard-gate rule marker (implement in check_p0_gates)

CONTRACT: this module's scoring logic MUST be pure — reads the verified card
(deterministic local read); no network calls, no nondeterminism — R2-compatible.
Every scoring function MUST produce bit-identical results with Excel rounding.
Fill in score_dimension() and check_p0_gates() for your domain — DIMENSIONS/
THRESHOLD come from the approved strategy card below (a single source of
truth, so the card-hash covers the scoring axes too), never a stamped literal.
"""

import math

from decimal import Decimal, ROUND_HALF_UP

from pathlib import Path

try:
    from .config_integrity import load_verified_config
except ImportError:  # CLI loads the domain directory as a top-level module.
    from config_integrity import load_verified_config


def r1(value: float) -> float:
    """Round to 1 decimal place with ROUND_HALF_UP (matches Excel ROUND).

    >>> r1(77.55)
    77.6
    >>> r1(77.54)
    77.5
    """
    if not math.isfinite(value):
        # A dimension score must be a real 0-100 number. NaN/Inf would raise a
        # cryptic decimal.InvalidOperation inside quantize() -- fail loud with
        # the actual offending value instead.
        raise ValueError(
            "r1() requires a finite score, got %r -- a dimension score must be "
            "a real number (check the score_dimension fill)" % (value,))
    return float(Decimal(str(value)).quantize(Decimal("0.0"), rounding=ROUND_HALF_UP))


# ── Dimension weights + threshold: read ONCE from the verified card at import
# (single hash, no double-read/TOCTOU window between DIMENSIONS and
# THRESHOLD; see config_integrity.py for the single-source rationale) ──────
_EVALS_ROOT = Path(__file__).resolve().parents[2]
_CARD = load_verified_config(_EVALS_ROOT)
DIMENSIONS = _CARD["dimensions"]
THRESHOLD = _CARD["threshold"]  # Minimum score to pass (before P0 gate)

if not DIMENSIONS:
    # The "no card / missing file" path already raises earlier inside
    # load_verified_config (ConfigDriftError) — this guard fires ONLY for a
    # hash-valid card whose dimensions are empty, i.e. a card built outside
    # the R7 approval flow (validate_card requires non-empty dims on every
    # approved card).
    raise RuntimeError(
        "approved card carries empty dimensions — card was built outside the R7 approval flow")


def score_dimension(dimension_name: str, results: list) -> float:
    """Score one evidence dimension from field-level comparison outcomes."""
    if not results:
        return 0.0

    def item_score(item: dict) -> float:
        if item.get("error"):
            return 0.0
        fields = item.get("fields") or []
        if not fields:
            return 100.0 if item.get("passed") else 0.0
        statuses = {str(field.get("status")) for field in fields}
        if dimension_name == "accuracy":
            good = {"MATCH", "SKIP"}
            return 100.0 * sum(field.get("status") in good for field in fields) / len(fields)
        if dimension_name == "completeness":
            return 0.0 if "MISS" in statuses else 100.0
        if dimension_name == "precision":
            return 0.0 if "EXTRA" in statuses else 100.0
        if dimension_name == "consistency":
            return 100.0 if item.get("passed") else 0.0
        if dimension_name == "robustness":
            return 0.0 if item.get("error") else 100.0
        raise ValueError("unknown dimension %r" % dimension_name)

    return r1(sum(item_score(item) for item in results) / len(results))


def score_dimension_probe(case_input):
    """Single-argument R9 probe for the dimension scorer."""
    if not isinstance(case_input, dict):
        return 0.0
    return score_dimension("accuracy", [case_input])


def check_p0_gates(results: list) -> tuple:
    """Evaluate P0 hard-gate rules. A single P0 failure forces BLOCK.

    Returns (passed, failures): passed is True only if ALL P0 gates pass;
    each failure is a dict {"rule_index": <int>, "msg": <str>} -- the shape the
    conformance test and the mutation matrix's rule-id attribution both key off.
    """
    failures = []

    for result in results:
        case = result.get("case", "<unknown>") if isinstance(result, dict) else "<invalid>"
        if not isinstance(result, dict) or not case:
            failures.append({"rule_index": 0, "msg": "invalid result envelope for %s" % case})
            continue
        if result.get("error"):
            failures.append({"rule_index": 0, "msg": "pipeline error for %s" % case})
            continue
        fields = result.get("fields") or []
        by_name = {str(field.get("field")): field.get("status") for field in fields}
        if by_name.get("state") in {"MISS", "MISMATCH"} and case == "malformed_snapshot":
            failures.append({"rule_index": 0, "msg": "schema envelope failed for %s" % case})
        for field_name in ("citations", "citation", "relations", "relation_edges"):
            if by_name.get(field_name) in {"MISS", "MISMATCH", "EXTRA"}:
                failures.append({"rule_index": 1 if field_name in {"citations", "citation"} else 6, "msg": "%s evidence failed for %s" % (field_name, case)})
        for field_name in ("state", "review_state"):
            if by_name.get(field_name) in {"MISS", "MISMATCH"}:
                failures.append({"rule_index": 2, "msg": "%s uncertainty state failed for %s" % (field_name, case)})
        for field_name in ("no_legal_winner", "no_winner", "prompt_not_authority"):
            if by_name.get(field_name) in {"MISS", "MISMATCH"}:
                failures.append({"rule_index": 3, "msg": "%s safety invariant failed for %s" % (field_name, case)})
        if by_name.get("no_unsupported_conversion") in {"MISS", "MISMATCH"}:
            failures.append({"rule_index": 4, "msg": "raw numeric/date/unit preservation failed for %s" % case})
        if by_name.get("no_leakage") in {"MISS", "MISMATCH"}:
            failures.append({"rule_index": 5, "msg": "scope isolation failed for %s" % case})
        if by_name.get("two_sided_evidence") in {"MISS", "MISMATCH"}:
            failures.append({"rule_index": 6, "msg": "two-sided relation evidence failed for %s" % case})
        if by_name.get("blocked") == "MISMATCH":
            failures.append({"rule_index": 7, "msg": "blocked policy outcome failed for %s" % case})

    return len(failures) == 0, failures


def score(results: list) -> dict:
    """Compute the weighted maturity score with P0 hard-gate enforcement.

    Returns a dict with maturity, passed, threshold, p0_gate_passed,
    p0_failures, and per-dimension scores. `passed` is True only when
    maturity >= threshold AND the P0 gate passes.
    """
    dimension_scores: dict = {}
    weighted_sum = 0.0

    for dim_name, weight in DIMENSIONS.items():
        dim_score = score_dimension(dim_name, results)
        weighted = r1(weight * dim_score / 100.0)
        dimension_scores[dim_name] = {
            "weight": weight,
            "score": r1(dim_score),
            "weighted": weighted,
        }
        weighted_sum += weighted

    maturity = r1(weighted_sum)
    p0_gate_passed, p0_failures = check_p0_gates(results)
    passed = maturity >= THRESHOLD and p0_gate_passed

    return {
        "maturity": maturity,
        "passed": passed,
        "threshold": THRESHOLD,
        "p0_gate_passed": p0_gate_passed,
        "p0_failures": p0_failures,
        "dimensions": dimension_scores,
    }
