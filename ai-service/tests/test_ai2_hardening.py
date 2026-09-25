from __future__ import annotations

from app.pipeline.idp import run_idp
from fixtures.eval_suite import all_eval_cases, synthetic_cases
from app.reasoning.l3_ground import L3Ground
from app.reasoning.l1_retrieval import L1Retrieval
from app.reasoning.stack import FourLayerReasoner, _restrict_selected_members
from scripts.live_eval import _citation_errors
from app.tools.gateway import ToolGateway
from app.tools.store import InMemorySnapshotStore


def test_processing_budget_uses_local_partial_review_when_llm_was_requested():
    pack = all_eval_cases()["EC-047"]

    result = run_idp(pack.record, pack.envelope, llm=object())

    assert result.status.value == "SUCCEEDED"
    assert result.review_state.value == "NEEDS_REVIEW"
    assert any(issue.code == "BUDGET_EXCEEDED" for issue in result.handoff_issues)
    assert not any(issue.code == "PROCESSING_TIMEOUT" for issue in result.handoff_issues)


def test_live_eval_accepts_exact_page_spans_for_structural_nodes():
    pack = synthetic_cases()["SYN-001"]
    node = next(item for item in pack.record.nodes if item.node_id == "cl_5_body")
    page = next(item for item in pack.record.pages if item.page_revision_id == node.page_revision_id)

    answer = {
        "citations": [
            {
                "node_id": node.node_id,
                "page_revision_id": page.page_revision_id,
                "text_span": page.text,
            }
        ]
    }

    assert _citation_errors(answer, pack.record) == []


def test_answered_requires_grounded_claim_level_citations():
    pack = synthetic_cases()["SYN-001"]
    store = InMemorySnapshotStore()
    store.put(pack.record)
    gateway = ToolGateway(store)
    node = next(item for item in pack.record.nodes if item.node_id == "cl_5_body")
    citation = gateway.call("get_node", pack.envelope, node_id=node.node_id)["citation"]
    result = L3Ground(gateway).run(
        pack.envelope,
        {"type": "lookup_term", "must_cite": []},
        review_state="ANSWERED",
        answer={"claims": [{"claim_id": "c1", "text": "claim without a citation", "citation_ids": []}]},
        citations=[citation],
        outline_ids=[node.node_id],
    )
    assert result["review_state"] != "ANSWERED"
    assert result["grounded"] is False


def test_free_form_retrieval_is_bounded_to_selected_members():
    pack = synthetic_cases()["SYN-001"]
    store = InMemorySnapshotStore()
    store.put(pack.record)
    gateway = ToolGateway(store)
    selected = pack.record.evidence_nodes()[0].node_id
    result = L1Retrieval(gateway).run(
        pack.envelope,
        {"type": "unscoped", "query": "nội dung", "selected_member_ids": [selected]},
    )
    result = _restrict_selected_members(
        result,
        {"selected_member_ids": [selected]},
        pack.envelope,
        gateway,
    )
    assert {item["node_id"] for item in result["outline_ids"]} <= {selected}
    assert {item.get("node_id") for item in result["hits"]} <= {selected}


def test_unknown_member_scope_blocks_before_retrieval():
    pack = synthetic_cases()["SYN-001"]
    store = InMemorySnapshotStore()
    store.put(pack.record)
    gateway = ToolGateway(store)

    result = FourLayerReasoner(gateway, llm=None).run(
        pack.envelope,
        {"type": "unscoped", "query": "secret", "selected_member_ids": ["other-dossier-member"]},
    )

    assert result["review_state"] == "BLOCKED"
    assert result["blocked_reason"] == "selected member is outside dossier scope"
