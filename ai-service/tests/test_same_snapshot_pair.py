"""Lock: same-snapshot body/annex totals pair even when the body never names the annex."""

from __future__ import annotations

from app.contracts.models import Disposition, ReviewState
from app.pipeline.ai1_snapshot_adapter import adapt_snapshot
from app.pipeline.idp import run_idp
from app.tools.store import InMemorySnapshotStore


def _page(number: int, lines: list[str]) -> dict:
    return {
        "page_no": number,
        "input_type": "SCANNED_OCR",
        "status": "SUCCESS",
        "raw_text_digest": "b" * 64,
        "render": {},
        "transform": {"rotation_degrees": 0, "profile_version": "test"},
        "lines": [
            {
                "line_id": f"p{number}:l{index}",
                "raw_text": text,
                "bbox": [0.1, min(0.9, 0.08 + index * 0.05), 0.9, min(0.95, 0.12 + index * 0.05)],
            }
            for index, text in enumerate(lines, start=1)
        ],
        "tables": [],
        "warnings": [],
        "text": "\n".join(lines),
    }


def _snapshot(name: str, pages: list[dict]) -> dict:
    return {
        "schema_version": "ai1.snapshot.v1",
        "snapshot_id": f"snap-{name}",
        "dossier_id": f"dos-{name}",
        "document_id": f"doc-{name}",
        "run_id": f"run-{name}",
        "source_digest": "c" * 64,
        "execution": {},
        "producer": {},
        "status": "SUCCESS",
        "pages": pages,
    }


def test_body_annex_pair_without_annex_mention_still_differs_no_winner() -> None:
    adapted = adapt_snapshot(
        _snapshot(
            "pair-no-mention",
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
    before = [node.raw_label for node in adapted.record.nodes]
    store = InMemorySnapshotStore()
    store.put(adapted.record)
    job = run_idp(adapted.record, adapted.envelope, store=store)
    assert job.contribution is not None
    conflict = [
        item
        for item in job.contribution.candidates
        if item.item_key == "contract_value" and item.disposition == Disposition.COMPARABLE_DIFFERENCE
    ]
    assert conflict
    pair = conflict[0]
    assert len(pair.evidence_left) == 1
    assert len(pair.evidence_right) == 1
    assert "không kết luận bên nào thắng" in pair.reason
    findings = job.contribution.contract_context.findings
    assert any(item.kind == "CONTEXT_GAP" for item in findings)
    assert [node.raw_label for node in adapted.record.nodes] == before
    assert job.review_state is ReviewState.NEEDS_REVIEW
