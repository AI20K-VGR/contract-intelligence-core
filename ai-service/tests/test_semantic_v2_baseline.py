"""P1 contract and fixture-integrity checks for semantic conflict v2."""

from __future__ import annotations

import json
from pathlib import Path

from app.contracts.models import IndexContribution

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "semantic_v2_cases.json"
CONTRACT = ROOT.parents[2] / "docs" / "contracts" / "ai2-semantic-v2.md"


def test_fixture_covers_positive_and_negative_alignment_cases() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    cases = payload["cases"]

    assert payload["schema_version"] == "ai2.semantic.v2.baseline"
    names = {case["name"] for case in cases}
    assert {"opposite_polarity", "same_milestone_value_delta", "entire_agreement_negative"} <= names
    assert all(case["expected_before"]["review_only"] for case in cases)
    assert not any("dos_" in json.dumps(case, ensure_ascii=False) for case in cases)


def test_contract_separates_semantic_and_arithmetic_outputs() -> None:
    contract = CONTRACT.read_text(encoding="utf-8")

    assert "CONFLICT_CANDIDATE" in contract
    assert "ARITHMETIC_INCONSISTENCY" in contract
    assert "two valid citations" in contract
    assert "NEEDS_REVIEW" in contract


def test_old_wire_payload_can_omit_semantic_extension() -> None:
    contribution = IndexContribution(extraction_version=1, proposed_index_version="idx_1")

    assert contribution.semantic_extension is None
    assert "semantic_extension" not in contribution.model_dump(exclude_none=True)
