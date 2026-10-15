from __future__ import annotations

import copy
import json

import pytest
from test_contract_graph_pairs_idp_integration import flags as flags
from test_contract_graph_pairs_idp_integration import run

from app.contracts.contract_graph import PairLabel
from app.contracts.wire import (
    BeAi2ProcessingRequest,
    job_result_to_wire,
    validate_processing_result,
)
from fixtures.contract_graph_pair_records import FakePairLLM
from scripts.capture_idp_golden import _request_payload


@pytest.fixture
def wire():
    rec, res = run(llm=FakePairLLM())
    request = BeAi2ProcessingRequest.model_validate(_request_payload())
    return rec, job_result_to_wire(res, request), request


def test_wire_validates_with_pairs_llm_mode(wire):
    rec, payload, request = wire
    validate_processing_result(payload, request=request)
    assert payload["result"]["index_contribution"]["coverage"]["contract_graph"]["pairs"]["mode"] == "llm"


def test_pair_labels_only_inside_coverage(wire):
    _, payload, _ = wire
    labels = {label.value for label in PairLabel}
    assert all(label in json.dumps(payload["result"]["index_contribution"]["coverage"]) for label in labels)
    stripped = copy.deepcopy(payload)
    del stripped["result"]["index_contribution"]["coverage"]
    text = json.dumps(stripped, ensure_ascii=False)
    assert not any(label in text for label in labels)


def test_conflict_reaches_findings_as_comparable_difference(wire):
    _, payload, _ = wire
    findings = [f for f in payload["result"]["findings"] if f["finding_id"].startswith("cand_pair_")]
    assert 1 <= len(findings) <= 5
    citations = {c["citation_id"]: c for c in payload["result"]["citations"]}
    for finding in findings:
        assert finding["finding_type"] == "COMPARABLE_DIFFERENCE"
        assert finding["review_state"] == "NEEDS_REVIEW" and finding["item_key"]
        assert finding["disposition"] == "COMPARABLE_DIFFERENCE"
        for cid in finding["evidence_left_citation_ids"] + finding["evidence_right_citation_ids"]:
            assert citations[cid]["source_file_id"] and citations[cid]["text_span"]


def test_general_specific_not_in_context_findings(wire):
    rec, payload, _ = wire
    assert any(r.label.value == "GENERAL_SPECIFIC" for r in rec.pair_relations)
    assert "GENERAL_SPECIFIC" not in json.dumps(payload["result"]["context_findings"])
