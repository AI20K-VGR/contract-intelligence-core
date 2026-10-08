"""P4 wire: flag-on payload stays inside ``ai2.be.processing.result.v1`` and edge sub-types never
leave ``index_contribution.coverage`` (K3, D5, D6)."""

from __future__ import annotations

import copy
import json
import re
import uuid
from contextlib import ExitStack
from unittest import mock

from test_processing_wire_contract import _request

from app.contracts.contract_graph import EdgeOp
from app.contracts.models import JobStatus
from app.contracts.schema_validation import validate_contract
from app.contracts.wire import BeAi2ProcessingRequest, job_result_to_wire
from app.pipeline import idp
from app.pipeline.contract_graph import builder
from app.tools.store import InMemorySnapshotStore
from fixtures import envelope
from fixtures.contract_graph_records import (
    ANNEX,
    ANNEX_NODES,
    BODY,
    BODY_NODES,
    UNLOCK_FACTS,
    Spec,
    dossier,
    graph_record,
)

FLAG = "AI2_CONTRACT_GRAPH_ENABLED"
SUBTYPES = re.compile(r"INSERTION|SUBSTITUTION|REPEAL|REJECTION|SCOPE_LIMIT")
UUID_SOURCES = ("app.pipeline.idp.uuid4", "app.pipeline.clause.uuid4", "app.pipeline.compare.uuid4")
# every edge op plus a new-unit insertion (P3 issue without an edge) and a missing target
NEW_UNIT = Spec(
    "a13", "13.", "Bổ sung Điều 18a vào sau Điều 18 như sau:\n“Điều 18a. Bảo hành”", "a_pl"
)


def _wide_record():
    return dossier([(BODY, "body", BODY_NODES), (ANNEX, "annex", [*ANNEX_NODES, NEW_UNIT])], UNLOCK_FACTS)


def _run(record, monkeypatch, *, enabled: bool = True, store=None):
    if enabled:
        monkeypatch.setenv(FLAG, "1")
    else:
        monkeypatch.delenv(FLAG, raising=False)
    counter = iter(range(1, 1 << 30))
    with ExitStack() as stack:
        for target in UUID_SOURCES:
            stack.enter_context(mock.patch(target, lambda: uuid.UUID(int=next(counter))))
        return idp.run_idp(record, envelope(), job_id="job_cg", store=store)


def _wire(result) -> dict:
    return job_result_to_wire(result, BeAi2ProcessingRequest.model_validate(_request()))


def test_flag_on_wire_validates_against_result_schema(monkeypatch):
    wire = _wire(_run(_wide_record(), monkeypatch))

    validate_contract(wire, "ai2.be.processing.result.v1.schema.json", error_code="RESULT_SCHEMA_INVALID")
    assert wire["status"] == "SUCCEEDED"
    graph = wire["result"]["index_contribution"]["coverage"]["contract_graph"]
    assert graph["status"] == "OK" and graph["edges_total"] > 0
    findings = [f for f in wire["result"]["context_findings"] if f["finding_id"].startswith("contract-graph:")]
    assert findings and {f["relation_type"] for f in findings} == {"AMENDS"}


def test_flag_on_subtypes_only_inside_coverage(monkeypatch):
    record = _wide_record()
    result = _run(record, monkeypatch)
    wire = _wire(result)
    ops = {edge.op for edge in record.contract_edges}

    assert ops >= {EdgeOp.SUBSTITUTION, EdgeOp.INSERTION, EdgeOp.SCOPE_LIMIT, EdgeOp.REJECTION}
    assert any(i.missing == "TARGET_NOT_FOUND" for i in result.contribution.evidence_issues)
    assert len(result.contribution.evidence_issues) > 0
    coverage = wire["result"]["index_contribution"]["coverage"]
    assert SUBTYPES.search(json.dumps(coverage["contract_graph"]))  # positive control
    stripped = copy.deepcopy(wire)
    del stripped["result"]["index_contribution"]["coverage"]
    text = json.dumps(stripped, ensure_ascii=False)
    assert not SUBTYPES.search(text), SUBTYPES.findall(text)


def test_cross_document_edge_meets_be_context_finding_filter(monkeypatch):
    record = graph_record()
    result = _run(record, monkeypatch)
    wire = _wire(result)
    citations = {c["citation_id"]: c for c in wire["result"]["citations"]}
    edge = next(e for e in record.contract_edges if e.source_node_id == "a1")
    (finding,) = [
        f for f in wire["result"]["context_findings"] if f["finding_id"] == "contract-graph:" + edge.edge_id
    ]

    # backend/src/contract_intelligence/shared/ai/persistence.py:811-835
    assert finding["review_state"] in {None, "NEEDS_REVIEW", "INSUFFICIENT_EVIDENCE"}
    assert not finding["metadata"].get("candidate_id")
    by_document = {}
    for cid in finding["citation_ids"]:
        citation = citations[cid]
        if citation.get("source_file_id") and citation.get("text_span"):
            by_document.setdefault(citation["source_file_id"], citation)
    assert set(by_document) == {"f-annex", "f-body"}
    assert finding["relation_type"] == "AMENDS"
    assert finding["finding_type"] == "AMENDMENT_SIGNAL"


def test_flag_on_sets_record_contract_edges_and_ran_flag(monkeypatch):
    record = graph_record()
    store = InMemorySnapshotStore()
    result = _run(record, monkeypatch, store=store)

    stored = store.get(record.tenant_id, record.dossier_id)
    assert stored is record and stored.contract_graph_ran is True
    assert stored.contract_edges
    assert {e.edge_id for e in stored.contract_edges} >= {
        f.finding_id.removeprefix("contract-graph:")
        for f in result.contribution.contract_context.findings
        if f.finding_id.startswith("contract-graph:")
    }
    coverage = result.contribution.coverage["contract_graph"]
    assert coverage["edges_total"] == len(stored.contract_edges)
    keys = list(result.contribution.coverage)  # IndexStore.propose appends its own keys after
    assert keys.index("contract_graph") == keys.index("runtime") + 1


def test_flag_on_builder_failure_sets_failed_coverage_and_keeps_ran_false(monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("synthetic builder failure")

    monkeypatch.setattr(builder, "build_contract_graph", boom)
    record = graph_record()
    result = _run(record, monkeypatch)

    assert result.status == JobStatus.SUCCEEDED
    coverage = result.contribution.coverage["contract_graph"]
    assert coverage["status"] == "FAILED" and coverage["edges_total"] == 0
    assert record.contract_graph_ran is False and record.contract_edges == []
    _wire(result)  # still a valid payload


def test_flag_off_has_no_contract_graph_coverage_key(monkeypatch):
    record = graph_record()
    result = _run(record, monkeypatch, enabled=False)

    assert "contract_graph" not in result.contribution.coverage
    assert not any(
        f.finding_id.startswith("contract-graph:") for f in result.contribution.contract_context.findings
    )
    assert record.contract_graph_ran is False and record.contract_edges == []
    wire = _wire(result)
    assert "contract_graph" not in wire["result"]["index_contribution"]["coverage"]
