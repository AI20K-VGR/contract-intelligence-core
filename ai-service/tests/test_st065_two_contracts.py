from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from app.contracts.models import Disposition, ReviewState
from app.contracts.wire import (
    BeAi2ProcessingRequest,
    job_result_to_wire,
    validate_processing_result,
)
from app.pipeline.ai1_snapshot_adapter import (
    adapt_ai1_input,
    adapt_be_ai2_processing_request,
    adapt_snapshot,
)
from app.pipeline.idp import run_idp
from app.tools.store import InMemorySnapshotStore

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/two_contracts_one_pdf/snapshot.json"
IDENTITY_KEYS = {"party_a", "party_b", "mst_party_a", "mst_party_b"}


def snapshot_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def process_snapshot(snapshot: dict[str, Any]):
    adapted = adapt_snapshot(snapshot)
    store = InMemorySnapshotStore()
    store.put(adapted.record)
    job = run_idp(adapted.record, adapted.envelope, store=store)
    assert job.contribution is not None
    return adapted, job


def processing_request(snapshot: dict[str, Any]) -> BeAi2ProcessingRequest:
    digest = hashlib.sha256(
        json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return BeAi2ProcessingRequest.model_validate({
        "schema_version": "be.ai2.processing.request.v1",
        "service_envelope": {
            "schema_version": "ai2.service-envelope.v1", "issuer": "backend", "audience": "ai2",
            "tenant_id": "tenant_a", "actor_id": "user_001", "dossier_id": snapshot["dossier_id"],
            "scopes": ["process"], "key_id": "test", "issued_at": 1, "expires_at": 2,
            "nonce": "st065-nonce-00001", "payload_sha256": "a" * 64, "signature": "b" * 64,
        },
        "request_id": "req-st065", "idempotency_key": "st065:1", "attempt": 1,
        "task_id": "process-dossier", "dossier_id": snapshot["dossier_id"], "snapshots": [snapshot],
        "snapshot_identities": [{
            "snapshot_id": snapshot["snapshot_id"], "snapshot_version": "ai1.snapshot.v1",
            "source_digest": snapshot["source_digest"], "snapshot_digest": digest,
        }],
        "dossier_members": [{
            "member_id": "member-st065", "document_id": snapshot["document_id"],
            "snapshot_id": snapshot["snapshot_id"], "role": "body",
            "source_digest": snapshot["source_digest"],
        }],
        "policy_flags": {"budget_limits": {
            "max_processing_seconds": 60, "max_llm_calls": 0, "max_embedding_tokens": 0,
        }},
    })


def _identity_findings(job):
    return [c for c in job.contribution.candidates if c.scope and c.scope.value == "CONTRACT_CONTRACT"]


def test_two_units_keep_each_party_and_tax_identifier() -> None:
    snapshot = snapshot_fixture()
    before = copy.deepcopy(snapshot)
    adapted, job = process_snapshot(snapshot)
    units = [n for n in adapted.record.evidence_nodes() if n.structure_level == "CONTRACT_UNIT"]
    assert len(units) == 2
    identity = [f for f in job.contribution.facts if (f.role or f.item_key) in IDENTITY_KEYS]
    by_unit: dict[str, dict[str, str]] = {}
    for fact in identity:
        by_unit.setdefault(fact.scope, {})[fact.role or fact.item_key] = fact.raw_value
    assert set(by_unit) == {n.scope_id for n in units}
    assert [set(values) for values in by_unit.values()] == [IDENTITY_KEYS, IDENTITY_KEYS]
    assert [values["party_b"] for values in by_unit.values()] == ["Công ty BETA", "Công ty GAMMA"]
    assert [values["mst_party_b"] for values in by_unit.values()] == ["0201234567", "0301234567"]
    assert snapshot == before


@pytest.mark.parametrize("changed", [{"party_b", "mst_party_b"}, {"party_b"}, {"mst_party_b"}, set()])
def test_only_changed_identity_fields_have_bilateral_findings(changed: set[str]) -> None:
    snapshot = snapshot_fixture()
    for key, index in [("party_b", 4), ("mst_party_b", 5)]:
        if key not in changed:
            snapshot["pages"][1]["lines"][index]["raw_text"] = snapshot["pages"][0]["lines"][index]["raw_text"]
    adapted, job = process_snapshot(snapshot)
    findings = _identity_findings(job)
    assert {c.item_key for c in findings} == changed
    assert len(findings) == len(changed)
    for finding in findings:
        assert finding.review_state is ReviewState.NEEDS_REVIEW
        assert finding.disposition is Disposition.COMPARABLE_DIFFERENCE
        assert len(finding.evidence_left) == len(finding.evidence_right) == 1
        expected_line = 5 if finding.item_key == "party_b" else 6
        left, right = finding.evidence_left[0], finding.evidence_right[0]
        assert left.line_ids == [f"p1:l{expected_line}"]
        assert right.line_ids == [f"p2:l{expected_line}"]
        assert left.page == 1 and right.page == 2
        assert left.source_file_id == right.source_file_id == snapshot["document_id"]
        assert left.validation_status == right.validation_status == "VALID"
        for citation in [left, right]:
            page = adapted.record.pages[citation.page - 1]
            assert page.text[citation.char_start:citation.char_end] == citation.text_span
        assert "không kết luận bên nào thắng" in finding.reason


def test_single_contract_has_no_contract_contract_finding() -> None:
    snapshot = snapshot_fixture()
    snapshot["pages"] = snapshot["pages"][:1]
    _, job = process_snapshot(snapshot)
    assert _identity_findings(job) == []


def test_repeated_title_without_party_declarations_does_not_split() -> None:
    snapshot = snapshot_fixture()
    snapshot["pages"][1]["lines"] = snapshot["pages"][1]["lines"][:2] + [{
        "line_id": "p2:l3", "raw_text": "ĐIỀU 2. THANH TOÁN", "bbox": [0.1, 0.2, 0.9, 0.3],
    }]
    adapted, job = process_snapshot(snapshot)
    assert len([n for n in adapted.record.evidence_nodes() if n.structure_level == "CONTRACT_UNIT"]) < 2
    assert _identity_findings(job) == []
    assert job.review_state is ReviewState.NEEDS_REVIEW


def test_two_contracts_on_same_page_have_distinct_units() -> None:
    snapshot = snapshot_fixture()
    snapshot["pages"][0]["lines"].extend(snapshot["pages"][1]["lines"])
    snapshot["pages"] = snapshot["pages"][:1]
    for index, line in enumerate(snapshot["pages"][0]["lines"], 1):
        line["line_id"] = f"p1:l{index}"
        line["bbox"] = [0.1, index * 0.04, 0.9, index * 0.04 + 0.03]
    adapted, job = process_snapshot(snapshot)
    assert len([n for n in adapted.record.evidence_nodes() if n.structure_level == "CONTRACT_UNIT"]) == 2
    assert len(_identity_findings(job)) == 2
    for finding in _identity_findings(job):
        assert finding.evidence_left[0].page == finding.evidence_right[0].page == 1
        assert finding.evidence_left[0].line_ids != finding.evidence_right[0].line_ids


def test_two_contract_output_validates_processing_wire() -> None:
    snapshot = snapshot_fixture()
    _, job = process_snapshot(snapshot)
    payload = job_result_to_wire(job, processing_request(snapshot))
    validate_processing_result(payload)
    findings = payload["result"]["findings"]
    assert len([f for f in findings if f["scope"] == "CONTRACT_CONTRACT"]) == 2
    assert len([f for f in payload["result"]["facts"] if f["role"] in IDENTITY_KEYS]) == 8
    assert payload["review_state"] == "NEEDS_REVIEW"


def test_backend_processing_request_preserves_contract_units() -> None:
    request = processing_request(snapshot_fixture())
    parsed, adapted = adapt_be_ai2_processing_request(request.model_dump(mode="json"))
    store = InMemorySnapshotStore()
    store.put(adapted.record)
    job = run_idp(adapted.record, adapted.envelope, store=store)
    payload = job_result_to_wire(job, parsed)
    assert len([f for f in payload["result"]["findings"] if f["scope"] == "CONTRACT_CONTRACT"]) == 2


def test_result_compatibility_lane_recovers_identity_per_unit() -> None:
    from test_ai1_result_v01 import _result

    snapshot = snapshot_fixture()
    payload = _result()
    machine = payload["machine"]
    machine["documents"][0]["page_count"] = 2
    template = machine["pages"][0]
    machine["pages"] = []
    machine["citations"] = []
    machine["coverage"].update(expected_pages=2, completed_pages=2)
    for source_page in snapshot["pages"]:
        page = copy.deepcopy(template)
        page["page_count"] = 2
        page["page_number"] = source_page["page_no"]
        page["lines"] = [{
            "id": line["line_id"], "text": line["raw_text"], "bbox": line["bbox"], "words": [],
        } for line in source_page["lines"]]
        machine["pages"].append(page)
        for line in page["lines"]:
            machine["citations"].append({
                "id": f"cite-{line['id']}", "run_id": machine["run_id"],
                "document_id": page["document_id"], "source_hash": page["sha256"],
                "page_number": page["page_number"], "line_id": line["id"],
                "quote": line["text"], "bbox": line["bbox"],
                "coordinate_system": "normalized_top_left_rendered_page",
                "geometry_source": "test", "precision": "line",
            })
    adapted = adapt_ai1_input(payload)
    identity = [f for f in adapted.record.facts if (f.role or f.item_key) in IDENTITY_KEYS]
    assert len(identity) == 8
    assert len({f.scope for f in identity}) == 2
    store = InMemorySnapshotStore()
    store.put(adapted.record)
    job = run_idp(adapted.record, adapted.envelope, store=store)
    assert len(_identity_findings(job)) == 2
