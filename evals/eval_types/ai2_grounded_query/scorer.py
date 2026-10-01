"""Deterministic scorer fill for the AI2 grounded-query domain."""

import math

from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

try:
    from .config_integrity import load_verified_config
except ImportError:  # CLI loads the domain directory as a top-level module.
    from config_integrity import load_verified_config


def r1(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError("dimension score must be finite: %r" % (value,))
    return float(Decimal(str(value)).quantize(Decimal("0.0"), rounding=ROUND_HALF_UP))


_EVALS_ROOT = Path(__file__).resolve().parents[2]
_CARD = load_verified_config(_EVALS_ROOT)
DIMENSIONS = _CARD["dimensions"]
THRESHOLD = _CARD["threshold"]

if not DIMENSIONS:
    raise RuntimeError("approved card carries empty dimensions")


def score_dimension(dimension_name: str, results: list) -> float:
    """Score grounded-query outcomes by status and case-level safety."""
    if dimension_name not in DIMENSIONS:
        raise ValueError("unknown dimension %r" % dimension_name)
    if not results:
        return 0.0

    def item_score(item: dict) -> float:
        if not isinstance(item, dict) or item.get("error"):
            return 0.0
        fields = item.get("fields") or []
        if not fields:
            return 100.0 if item.get("passed") else 0.0
        statuses = [field.get("status") for field in fields]
        if dimension_name == "accuracy":
            good = {"MATCH", "SKIP"}
            return 100.0 * sum(status in good for status in statuses) / len(statuses)
        if dimension_name == "completeness":
            return 0.0 if "MISS" in statuses else 100.0
        if dimension_name == "precision":
            return 0.0 if "EXTRA" in statuses else 100.0
        if dimension_name == "consistency":
            return 100.0 if item.get("passed") else 0.0
        if dimension_name == "robustness":
            return 100.0
        raise ValueError("unknown dimension %r" % dimension_name)

    return r1(sum(item_score(item) for item in results) / len(results))


def score_dimension_probe(case_input):
    """Single-argument R9 probe for the accuracy scorer."""
    if not isinstance(case_input, dict):
        return 0.0
    return score_dimension("accuracy", [case_input])


def _failure(rule_index: int, message: str) -> dict:
    return {"rule_index": rule_index, "msg": message}


def check_p0_gates(results: list) -> tuple:
    """Fail closed on grounding, uncertainty, scope, and relation violations."""
    failures = []
    for result in results:
        case = result.get("case", "<unknown>") if isinstance(result, dict) else "<invalid>"
        if not isinstance(result, dict) or not case:
            failures.append(_failure(0, "invalid result envelope for %s" % case))
            continue
        if result.get("error"):
            failures.append(_failure(1, "pipeline error for %s" % case))
            continue

        fields = result.get("fields") or []
        by_name = {str(field.get("field")): field.get("status") for field in fields}
        for field_name in ("citations", "citation", "citation_scope"):
            if by_name.get(field_name) in {"MISS", "MISMATCH", "EXTRA"}:
                failures.append(_failure(0, "%s citation failed for %s" % (field_name, case)))
        for field_name in ("state", "review_state"):
            if by_name.get(field_name) in {"MISS", "MISMATCH"}:
                failures.append(_failure(1, "%s fail-closed state failed for %s" % (field_name, case)))
        for field_name in ("two_sided_citations", "no_winner"):
            if by_name.get(field_name) in {"MISS", "MISMATCH"}:
                failures.append(_failure(2, "%s comparison safety failed for %s" % (field_name, case)))
        if by_name.get("no_legal_winner") in {"MISS", "MISMATCH"}:
            failures.append(_failure(6, "no_legal_winner comparison safety failed for %s" % case))
        for field_name in ("blocked", "no_instruction_following"):
            if by_name.get(field_name) in {"MISS", "MISMATCH"}:
                failures.append(_failure(3, "%s policy block failed for %s" % (field_name, case)))
        if by_name.get("no_cross_tenant_data") in {"MISS", "MISMATCH"}:
            failures.append(_failure(4, "scope isolation failed for %s" % case))
        for field_name in ("relation_edges", "relation_grounded"):
            if by_name.get(field_name) in {"MISS", "MISMATCH", "EXTRA"}:
                failures.append(_failure(5, "%s relation grounding failed for %s" % (field_name, case)))
        for field_name in ("legal_winner", "full_pdf_dump"):
            if field_name in by_name:
                failures.append(_failure(6, "%s forbidden output present for %s" % (field_name, case)))
        if by_name.get("diacritics") in {"MISS", "MISMATCH"}:
            failures.append(_failure(7, "Vietnamese diacritics changed for %s" % case))

    return len(failures) == 0, failures


def check_p0_gates_probe(case_input):
    """Single-argument R9 probe for the P0 gate."""
    if not isinstance(case_input, list):
        return check_p0_gates([case_input])
    return check_p0_gates(case_input)


def score(results: list) -> dict:
    dimension_scores = {}
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
    return {
        "maturity": maturity,
        "passed": maturity >= THRESHOLD and p0_gate_passed,
        "threshold": THRESHOLD,
        "p0_gate_passed": p0_gate_passed,
        "p0_failures": p0_failures,
        "dimensions": dimension_scores,
    }
