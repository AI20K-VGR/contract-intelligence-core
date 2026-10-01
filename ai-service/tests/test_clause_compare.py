from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.contracts.wire import job_result_to_wire
from app.pipeline.ai1_snapshot_adapter import adapt_be_ai2_processing_request
from app.pipeline.citations import CitationResolver
from app.pipeline.clause_compare import compare_clauses_across_files
from app.pipeline.contract_context import build_contract_context
from app.pipeline.idp import run_idp
from app.pipeline.index import IndexStore
from app.security.service_envelope import build_service_envelope
from app.tools.store import InMemorySnapshotStore

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "docs" / "contracts" / "examples" / "ai1.snapshot.v1.body.example.json"

CONTRACT_PAGES = [
    [
        "HỢP ĐỒNG KINH TẾ",
        "Số: 09/2026/HĐKT-PT-MH",
        "ĐIỀU 3. TIẾN ĐỘ THỰC HIỆN",
        "3.1. Thời gian thực hiện: 08 tuần kể từ ngày ký hợp đồng.",
        "3.2. Bên B bàn giao theo từng đợt.",
        "ĐIỀU 4. GIÁ TRỊ HỢP ĐỒNG VÀ THANH TOÁN",
        "4.1. Tổng giá trị hợp đồng là 1.286.400.000 đồng (đã bao gồm VAT).",
        "4.2. Thanh toán đợt 1: 30% giá trị hợp đồng; đợt 2: 40% giá trị hợp đồng.",
        "Trang 1",
    ],
    [
        "ĐIỀU 8. BẢO MẬT VÀ BẢO VỆ DỮ LIỆU",
        "8.3. Nghĩa vụ bảo mật kéo dài 03 (ba) năm sau khi hợp đồng kết thúc.",
        "ĐIỀU 11. XỬ LÝ VI PHẠM",
        "11.1. Bên vi phạm phải khắc phục trong 15 ngày làm việc.",
        "11.2. Thông báo vi phạm gửi bằng văn bản.",
        "Trang 2",
    ],
    ["PHỤ LỤC 01", "BẢNG KHỐI LƯỢNG", "Hạng mục A: 10 bộ", "Trang 3"],
]

ANNEX_PAGES = [
    [
        "PHỤ LỤC 02",
        "Kèm theo Hợp đồng số 09/2026/HĐKT-PT-MH",
        "Điều 3. Tiến độ thực hiện",
        "3.1. Thời gian thực hiện: 10 tuần kể từ ngày ký hợp đồng.",
        "3.2. Bên B bàn giao theo từng đợt.",
        "Điều 4. Giá trị hợp đồng và thanh toán",
        "4.1. Tổng giá trị hợp đồng là 1.586.400.000 đồng (đã bao gồm VAT).",
        "4.2. Thanh toán đợt 1: 20% giá trị hợp đồng; đợt 2: 50% giá trị hợp đồng.",
    ],
    [
        "Điều 6. Bảo mật và bảo vệ dữ liệu",
        "6.3. Nghĩa vụ bảo mật kéo dài 05 (năm) năm sau khi hợp đồng kết thúc.",
        "Điều 8. Xử lý vi phạm",
        "8.1. Bên vi phạm phải khắc phục trong 10 ngày làm việc.",
        "8.2. Thông báo vi phạm gửi bằng văn bản.",
        "BẢNG DỮ LIỆU KIỂM THỬ XUNG ĐỘT",
        "15 ngày - Điều 11.1",
        "30 ngày - Điều 13.2",
    ],
]


def _lines(doc: str, page_no: int, texts: list[str]) -> list[dict]:
    lines = []
    for index, text in enumerate(texts, start=1):
        y = 0.05 + index * 0.04
        lines.append(
            {
                "line_id": f"{doc}:s1:p{page_no:03d}:l{index:03d}",
                "raw_text": text,
                "bbox": [0.1, y, 0.9, y + 0.03],
                "bbox_source": "native",
                "geometry_status": "measured",
                "words": [],
            }
        )
    return lines


def _snapshot(doc: str, pages: list[list[str]], digest: str) -> dict:
    base = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    template = base["pages"][0]
    base.update(
        {
            "snapshot_id": f"snap-{doc}",
            "dossier_id": "dossier-clauses",
            "document_id": doc,
            "source_digest": digest,
            "pages": [
                {
                    **template,
                    "page_no": number,
                    "page_revision_id": f"{doc}:p{number}",
                    "quality": {"coverage_status": "COMPLETE", "ocr_confidence": 0.97, "signals": []},
                    "lines": _lines(doc, number, texts),
                    "tables": [],
                    "warnings": [],
                    "table_coverage": {"status": "NOT_PRESENT", "method": "test", "version": "1"},
                }
                for number, texts in enumerate(pages, start=1)
            ],
        }
    )
    return base


def _identity(snapshot: dict) -> dict:
    return {
        "snapshot_id": snapshot["snapshot_id"],
        "snapshot_version": "ai1.snapshot.v1",
        "source_digest": snapshot["source_digest"],
        "snapshot_digest": hashlib.sha256(
            json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
    }


def _request() -> dict:
    body = _snapshot("doc_body", CONTRACT_PAGES, "1" * 64)
    annex = _snapshot("doc_annex", ANNEX_PAGES, "2" * 64)
    payload = {
        "schema_version": "be.ai2.processing.request.v1",
        "request_id": "req-clauses",
        "idempotency_key": "dossier-clauses:1",
        "attempt": 1,
        "task_id": "process-dossier",
        "dossier_id": "dossier-clauses",
        "snapshots": [body, annex],
        "snapshot_identities": [_identity(body), _identity(annex)],
        "dossier_members": [
            {
                "member_id": "m-body",
                "document_id": "doc_body",
                "snapshot_id": body["snapshot_id"],
                "role": "body",
                "source_digest": body["source_digest"],
            },
            {
                "member_id": "m-annex",
                "document_id": "doc_annex",
                "snapshot_id": annex["snapshot_id"],
                "role": "annex",
                "source_digest": annex["source_digest"],
            },
        ],
        "role_relation_map": [
            {
                "relation_id": "rel-1",
                "relation_type": "ANNEX_OF",
                "member_id": "m-annex",
                "related_member_id": "m-body",
                "dossier_id": "dossier-clauses",
            }
        ],
        "policy_flags": {
            "egress_allowed": False,
            "use_vector": True,
            "budget_limits": {"max_processing_seconds": 300, "max_llm_calls": 20, "max_embedding_tokens": 50000},
        },
    }
    payload["service_envelope"] = build_service_envelope(
        payload, secret="test-secret", tenant_id="tenant_a", dossier_id="dossier-clauses", actor_id="test"
    )
    return payload


def test_clause_quantities_differing_between_body_and_annex_become_verified_candidates():
    _, adapted = adapt_be_ai2_processing_request(_request())
    record = adapted.record

    candidates = compare_clauses_across_files(record)

    assert [c.item_key for c in candidates] == [
        "Điều 3.1 · Tiến độ thực hiện",
        "Điều 4.1 · Giá trị hợp đồng và thanh toán",
        "Điều 4.2 · Giá trị hợp đồng và thanh toán",
        "Điều 8.3 · Bảo mật và bảo vệ dữ liệu",
        "Điều 11.1 · Xử lý vi phạm",
    ]
    by_key = {c.item_key: c for c in candidates}
    assert "08 tuần" in by_key["Điều 3.1 · Tiến độ thực hiện"].reason
    assert "10 tuần" in by_key["Điều 3.1 · Tiến độ thực hiện"].reason
    assert "30%; 40%" in by_key["Điều 4.2 · Giá trị hợp đồng và thanh toán"].reason
    assert "Điều 6.3: 05 năm" in by_key["Điều 8.3 · Bảo mật và bảo vệ dữ liệu"].reason
    # The all-caps table heading after 8.2 must not leak table values into 8.2.
    assert "Điều 11.2" not in by_key
    assert all(c.disposition.value == "COMPARABLE_DIFFERENCE" for c in candidates)
    assert all(c.review_state.value == "NEEDS_REVIEW" for c in candidates)

    resolver = CitationResolver(record.pages, record.tables)
    for candidate in candidates:
        (left,) = candidate.evidence_left
        (right,) = candidate.evidence_right
        assert left.source_file_id == "doc_body"
        assert right.source_file_id == "doc_annex"
        for citation in (left, right):
            assert resolver.verify(citation).status == "VALID"
            assert citation.line_ids and citation.bbox and citation.page


def test_context_parts_are_scoped_per_source_file():
    _, adapted = adapt_be_ai2_processing_request(_request())
    record = adapted.record

    context = build_contract_context(record, candidates=compare_clauses_across_files(record))

    assert [(part.part_id, part.page_range) for part in context.parts] == [
        ("body", [1, 2]),
        ("annex:01", [3]),
        ("annex:02:doc_annex", [1, 2]),
    ]
    # Cross-file candidates are first-class findings, never duplicated as context conflicts.
    assert not any(finding.kind == "CONTEXT_CONFLICT" for finding in context.findings)


def test_clause_candidates_survive_run_idp_and_reach_the_wire():
    request, adapted = adapt_be_ai2_processing_request(_request())
    result = run_idp(adapted.record, adapted.envelope, store=InMemorySnapshotStore(), index=IndexStore())

    wire = job_result_to_wire(result, request)
    findings = wire["result"]["findings"]
    assert len(findings) == 5
    assert {finding["disposition"] for finding in findings} == {"COMPARABLE_DIFFERENCE"}
    citations = {item["citation_id"]: item for item in wire["result"]["citations"]}
    for finding in findings:
        left = citations[finding["evidence_left_citation_ids"][0]]
        right = citations[finding["evidence_right_citation_ids"][0]]
        assert (left["source_file_id"], right["source_file_id"]) == ("doc_body", "doc_annex")
        assert left["validation_status"] == right["validation_status"] == "VALID"
