"""A missing annex mention stays beside a value pair as an unconfirmed note."""

from __future__ import annotations

from app.contracts.models import Disposition, ReviewState
from app.pipeline.ai1_snapshot_adapter import adapt_snapshot
from app.pipeline.idp import run_idp
from app.tools.store import InMemorySnapshotStore
from tests.test_same_snapshot_pair import _page, _snapshot


def test_missing_annex_mention_is_unconfirmed_note_not_a_dropped_pair() -> None:
    adapted = adapt_snapshot(
        _snapshot(
            "gap-note",
            [
                _page(1, [
                    "ĐIỀU 1. GIÁ TRỊ HỢP ĐỒNG",
                    "1.1. Tổng giá trị hợp đồng là 1.000.000.000 đồng.",
                ]),
                _page(2, [
                    "PHỤ LỤC 01 - BẢNG GIÁ",
                    "Tổng giá trị hợp đồng là 1.200.000.000 đồng.",
                ]),
            ],
        )
    )
    page_text_before = [page.text for page in adapted.record.pages]
    labels_before = [node.raw_label for node in adapted.record.nodes]
    store = InMemorySnapshotStore()
    store.put(adapted.record)
    job = run_idp(adapted.record, adapted.envelope, store=store)
    assert job.contribution is not None
    assert any(
        item.item_key == "contract_value" and item.disposition == Disposition.COMPARABLE_DIFFERENCE
        for item in job.contribution.candidates
    )
    findings = job.contribution.contract_context.findings
    gaps = [item for item in findings if item.kind == "CONTEXT_GAP"]
    assert gaps
    assert gaps[0].metadata.get("relation") == "UNCONFIRMED"
    assert any(item.kind == "CONTEXT_CONFLICT" for item in findings) or any(
        item.disposition == Disposition.COMPARABLE_DIFFERENCE for item in job.contribution.candidates
    )
    assert [page.text for page in adapted.record.pages] == page_text_before
    assert [node.raw_label for node in adapted.record.nodes] == labels_before
    assert "theo Phụ lục 01" not in "\n".join(page_text_before)
    assert job.review_state is ReviewState.NEEDS_REVIEW
    cited = [part.citation for part in job.contribution.contract_context.parts if part.citation is not None]
    assert cited
    assert {item.validation_status for item in cited} == {"VALID"}
