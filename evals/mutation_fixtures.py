"""Deterministic mutation fixtures used to test scorer sensitivity.

These fixtures are intentionally not production-entry evidence.  The release
gate labels them as scorer-only unless a real production mutation adapter is
provided.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from evals.release_verification import compare_ground_truth


def _expected_value(field: str) -> Any:
    if field in {"citations", "citation"}:
        return "required"
    if field == "state":
        return "PASS"
    return True


def build_scorer_fixture(entry: Mapping[str, Any]) -> dict[str, Any]:
    field = str(entry["control_field"])
    expected = _expected_value(field)
    actual = expected
    if field in {"citations", "citation"}:
        actual = [{
            "citation_id": "fixture-citation-1",
            "node_id": "fixture-node-1",
            "page_revision_id": "fixture-page-rev-1",
            "quote_hash": "fixture-quote-hash",
        }]
    return {"case": entry["negative_fixture"], "expected": {field: expected}, "actual": {field: actual}}


def apply_named_mutation(entry: Mapping[str, Any], fixture: Mapping[str, Any]) -> dict[str, Any]:
    """Apply the declared mutation; an unknown or no-op mutation is explicit."""

    result = deepcopy(dict(fixture))
    mutation = str(entry["mutation"])
    if mutation == "noop":
        return result
    known = {
        "remove_schema_version", "drop_citation_identity", "force_pass_state",
        "emit_legal_winner", "convert_currency", "mix_tenant", "drop_relation_citation",
        "hide_budget_block", "drop_claim_citation", "invent_answer", "drop_right_side",
        "return_answer_on_egress", "mix_dossier", "invent_edge", "strip_diacritics",
    }
    if mutation not in known:
        raise ValueError(f"unknown mutation operator: {mutation}")
    field = str(entry["control_field"])
    result["actual"][field] = None
    return result


def score_scorer_fixture(fixture: Mapping[str, Any]) -> list[dict[str, Any]]:
    comparison = compare_ground_truth(fixture["expected"], fixture["actual"])
    fields = []
    for field in comparison.get("fields", []):
        normalized = dict(field)
        if normalized.get("status") == "FAIL":
            normalized["status"] = "MISMATCH"
        fields.append(normalized)
    return [{"case": fixture["case"], "fields": fields}]
