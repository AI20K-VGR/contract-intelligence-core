from app.contracts.models import Candidate, FindingType, ModelDisposition, ReviewState
from app.pipeline.candidate import CandidatePairer
from app.pipeline.clause import ClauseChunker
from app.pipeline.fact import FactExtractor
from app.pipeline.grounding import GroundingGate
from app.pipeline.handoff import HandoffValidator
from app.pipeline.idp import run_idp
from app.pipeline.index import IndexStore
from app.pipeline.table import TablePipeline
from app.sandbox import SandboxError, run_user_code
from app.tools.gateway import ToolBlocked, ToolGateway
from app.tools.store import InMemorySnapshotStore
from fixtures import envelope, mock_record
from app.contracts.models import Citation, Fact, LifecycleState


def test_handoff_rejects_pdf_bytes():
    rec = mock_record()
    hv = HandoffValidator()
    out = hv.validate(
        tenant_id=rec.tenant_id,
        dossier_id=rec.dossier_id,
        pins=rec.pins,
        pages=rec.pages,
        nodes=rec.nodes,
        tables=rec.tables,
        profile=rec.profile,
        pdf_bytes=b"%PDF",
    )
    assert out.blocked
    assert out.issues[0].review_state == ReviewState.BLOCKED


def test_low_quality_needs_review():
    rec = mock_record()
    rec.pages[0].quality = "LOW"
    out = HandoffValidator().validate(
        tenant_id=rec.tenant_id,
        dossier_id=rec.dossier_id,
        pins=rec.pins,
        pages=rec.pages,
        nodes=rec.nodes,
        tables=rec.tables,
        profile=rec.profile,
    )
    assert not out.blocked
    assert any(i.review_state == ReviewState.NEEDS_REVIEW for i in out.issues)


def test_empty_page_does_not_block_handoff():
    rec = mock_record()
    rec.pages[0].quality = "EMPTY"
    out = HandoffValidator().validate(
        tenant_id=rec.tenant_id,
        dossier_id=rec.dossier_id,
        pins=rec.pins,
        pages=rec.pages,
        nodes=rec.nodes,
        tables=rec.tables,
        profile=rec.profile,
    )
    assert not out.blocked
    assert any(i.code == "PAGE_QUALITY" and i.review_state == ReviewState.NEEDS_REVIEW for i in out.issues)


def test_encrypted_blocked():
    rec = mock_record()
    rec.pages[0].quality = "ENCRYPTED"
    out = HandoffValidator().validate(
        tenant_id=rec.tenant_id,
        dossier_id=rec.dossier_id,
        pins=rec.pins,
        pages=rec.pages,
        nodes=rec.nodes,
        tables=rec.tables,
        profile=rec.profile,
    )
    assert out.blocked


def test_acl_deny_blocked():
    rec = mock_record()
    store = InMemorySnapshotStore()
    store.put(rec)
    gw = ToolGateway(store)
    env = envelope(permissions=["READ_CONTENT"], actor="stranger")
    try:
        gw.call("list_structure", env)
        assert False, "should block"
    except ToolBlocked:
        pass


def test_soft_deleted_blocked():
    rec = mock_record(lifecycle=LifecycleState.SOFT_DELETED)
    store = InMemorySnapshotStore()
    store.put(rec)
    gw = ToolGateway(store)
    try:
        gw.call("list_structure", envelope())
        assert False
    except ToolBlocked:
        pass


def test_pin_mismatch_blocked():
    rec = mock_record()
    store = InMemorySnapshotStore()
    store.put(rec)
    env = envelope()
    env.pins.extraction_version = 99
    gw = ToolGateway(store)
    try:
        gw.call("list_structure", env)
        assert False
    except ToolBlocked:
        pass


def test_missing_required_pin_blocks_handoff():
    rec = mock_record()
    rec.pins.extraction_version = 0
    out = HandoffValidator().validate(
        tenant_id=rec.tenant_id,
        dossier_id=rec.dossier_id,
        pins=rec.pins,
        pages=rec.pages,
        nodes=rec.nodes,
        tables=rec.tables,
        profile=rec.profile,
    )
    assert out.blocked
    assert any(i.code == "MISSING_PIN" and i.review_state == ReviewState.BLOCKED for i in out.issues)


def test_sandbox_missing_not_zero():
    rows = [["Q1", "100"], ["Q2", None]]
    code = """
result = []
for i, row in enumerate(rows):
    val = decimal(row[1])
    result.append({"row_index": i, "raw": row[1], "normalized": str(val) if val is not None else None, "missing": val is None})
"""
    out = run_user_code(code, rows, ["period", "amount"])
    assert out["rows_out"][1]["missing"] is True
    assert out["rows_out"][1]["normalized"] is None


def test_sandbox_forbids_import():
    try:
        run_user_code("import os\nresult = []", [], [])
        assert False
    except SandboxError:
        pass


def test_grounding_exact_pass():
    fact = Fact(
        fact_id="f1",
        raw_value="Công ty ABC",
        citation=Citation(node_id="n", page_revision_id="p", text_span="Công ty ABC"),
    )
    out = GroundingGate().ground_fact(fact, "Bên A: Công ty ABC")
    assert out.review_state == ReviewState.PASS


def test_grounding_fail_insufficient():
    fact = Fact(
        fact_id="f1",
        raw_value="XYZ-NOT-IN-SOURCE",
        citation=Citation(node_id="n", page_revision_id="p", text_span="nope"),
    )
    out = GroundingGate().ground_fact(fact, "Bên A: Công ty ABC")
    assert out.review_state == ReviewState.INSUFFICIENT_EVIDENCE


def test_candidate_no_legal_winner():
    try:
        Candidate(
            candidate_id="c",
            left_id="a",
            right_id="b",
            finding_type="LEGAL_WINNER",  # type: ignore[arg-type]
            model_disposition=ModelDisposition.CONSISTENT,
            review_state=ReviewState.PASS,
        )
        assert False
    except Exception:
        pass


def test_candidate_pair_incompatible():
    a = Fact(
        fact_id="a",
        raw_value="1",
        normalized_value="1",
        unit="VND",
        item_key="price",
        citation=Citation(node_id="n1", page_revision_id="p", text_span="1"),
        review_state=ReviewState.PASS,
    )
    b = Fact(
        fact_id="b",
        raw_value="2",
        normalized_value="2",
        unit="USD",
        item_key="price",
        citation=Citation(node_id="n2", page_revision_id="p", text_span="2"),
        review_state=ReviewState.PASS,
    )
    cands = CandidatePairer().pair([a, b])
    assert cands[0].review_state == ReviewState.NOT_COMPARABLE
    assert cands[0].finding_type == FindingType.GAP



def test_clause_unnumbered():
    rec = mock_record()
    from app.pipeline.handoff import HandoffValidator

    h = HandoffValidator().validate(
        tenant_id=rec.tenant_id,
        dossier_id=rec.dossier_id,
        pins=rec.pins,
        pages=rec.pages,
        nodes=rec.nodes,
        tables=rec.tables,
        profile=rec.profile,
    )
    chunks = ClauseChunker().chunk(h)
    assert any("unnumbered" in c.breadcrumb[-1].lower() or c.parent_node_id == "unnum_1" for c in chunks)


def test_run_idp_mock_without_llm():
    rec = mock_record()
    result = run_idp(rec, envelope(), llm=None)
    assert result.status.value == "SUCCEEDED"
    assert result.contribution is not None
    assert result.contribution.publish == "propose"
    assert any(f.raw_value == "MISSING" for f in result.contribution.facts)


def test_partial_node_and_low_page_never_publish_as_pass():
    rec = mock_record()
    rec.pages[0].quality = "LOW"
    rec.nodes[0].status = "PARTIAL"
    result = run_idp(rec, envelope(), llm=None)
    assert result.status.value == "SUCCEEDED"
    assert result.review_state == ReviewState.NEEDS_REVIEW
    assert all(f.review_state != ReviewState.PASS for f in result.contribution.facts if f.citation.page_revision_id == "page_1_rev_1")
    assert any(c.review_state == ReviewState.NEEDS_REVIEW for c in result.contribution.chunks)


def test_unmatched_table_node_fails_without_first_table_fallback():
    rec = mock_record()
    rec.nodes[-1].node_id = "missing_table"
    result = run_idp(rec, envelope(), llm=None)
    # Unit-level containment keeps field extraction results while surfacing
    # the unusable table unit for review.
    assert result.status.value == "SUCCEEDED"
    assert result.review_state == ReviewState.NEEDS_REVIEW
    assert any(i.code == "TOOL_BLOCKED" for i in result.handoff_issues)


def test_index_suppresses_candidates_with_unpublished_facts():
    fact = Fact(
        fact_id="missing_fact",
        raw_value="not grounded",
        citation=Citation(node_id="n", page_revision_id="p", text_span="other"),
        review_state=ReviewState.INSUFFICIENT_EVIDENCE,
    )
    candidate = Candidate(
        candidate_id="dangling",
        left_id="missing_fact",
        right_id="other_fact",
        finding_type=FindingType.NEEDS_EVIDENCE,
        model_disposition=ModelDisposition.INCOMPLETE,
        review_state=ReviewState.INSUFFICIENT_EVIDENCE,
    )
    contribution = IndexStore().propose(
        facts=[fact],
        chunks=[],
        candidates=[candidate],
        evidence_issues=[],
        extraction_version=1,
        proposed_index_version="idx_1",
    )
    assert contribution.candidates == []
    assert contribution.coverage["n_candidates_suppressed"] == 1


def test_table_pipeline_l0():
    rec = mock_record()
    store = InMemorySnapshotStore()
    store.put(rec)
    facts = TablePipeline(ToolGateway(store), llm=None).extract(envelope(), "table_1")
    assert any(f.raw_value == "MISSING" for f in facts)
    assert all(f.citation.source_hash == rec.pages[0].source_hash for f in facts)
    assert next(f for f in facts if f.raw_value == "100").citation.text_span == "100"


def test_table_pipeline_llm_code_failure_falls_back_to_deterministic():
    class BrokenLLM:
        def configured(self):
            return True

        def complete_json(self, *args, **kwargs):
            return {"code": "result = [undefined_name]"}

    rec = mock_record()
    store = InMemorySnapshotStore()
    store.put(rec)
    facts = TablePipeline(ToolGateway(store), llm=BrokenLLM()).extract(envelope(), "table_1")
    assert [f.raw_value for f in facts] == ["100", "200", "MISSING", "50"]


def test_fact_extractor_party():
    rec = mock_record()
    store = InMemorySnapshotStore()
    store.put(rec)
    fact = FactExtractor(ToolGateway(store), llm=None).extract(envelope(), "field_party", rec.profile)
    assert "ABC" in fact.raw_value
    assert fact.review_state in {ReviewState.PASS, ReviewState.NEEDS_REVIEW}
