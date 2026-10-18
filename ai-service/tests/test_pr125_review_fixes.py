"""PR #125 review findings (nguyenddung, Chuongpham2004): reviewer's own example sentences."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from test_ai1_snapshot_adapter import _page, _snapshot
from test_contract_graph_pair_classifier import answer, classify, pair
from test_frame_context_runtime import _batch_setup

from app.contracts.models import Citation, Fact
from app.pipeline.ai1_snapshot_adapter import adapt_ai1_input, adapt_snapshot
from app.pipeline.citations import CitationResolver, canonical_page_text
from app.pipeline.compare import _context_key
from app.pipeline.contract_graph.pair_candidates import PairCandidate, PairSource, _cites
from app.pipeline.contract_graph.pair_classifier import ClassifierPair
from app.pipeline.frame_context import _is_heading_only
from app.pipeline.outline import citation_for_node
from app.reasoning.ask_intent import parse_ask

ROOT = Path(__file__).resolve().parents[2]

# -- 1a: heading-only filter ------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Điều chỉnh giá hợp đồng được thực hiện khi có biến động giá vật liệu",
        "Phần lớn khối lượng công việc do nhà thầu phụ thực hiện",
        "Điều 15. Hợp đồng có hiệu lực kể từ ngày ký",
    ],
)
def test_1a_sentences_are_not_headings(text):
    assert _is_heading_only(text) is False


@pytest.mark.parametrize(
    "text",
    [
        "Điều 15. Hiệu lực hợp đồng",
        "Điều 5. Thanh toán",
        "ĐIỀU 3. QUYỀN VÀ NGHĨA VỤ CỦA CÁC BÊN",
        "Chương IV. Điều khoản chung",
        "Mục 2",
    ],
)
def test_1a_real_headings_stay_headings(text):
    assert _is_heading_only(text) is True


# -- 1b: conflict_no_value_difference keeps CONFLICTs whose wording differs ---------------


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("Bên A thanh toán trong 30 ngày làm việc.", "Bên A thanh toán trong 30 ngày."),
        ("Bên A chịu phạt 8% giá trị hợp đồng.", "Bên B chịu phạt 8% giá trị hợp đồng."),
        (
            "Bảo hành 12 tháng kể từ ngày nghiệm thu.",
            "Bảo hành 12 tháng kể từ ngày giao hàng.",
        ),
    ],
)
def test_1b_conflict_with_different_wording_keeps_model_label(a, b):
    result = classify([pair(a, b)], {"results": [answer(span_a=a, span_b=b)]})
    assert result.stats["rejected"]["conflict_no_value_difference"] == 0
    assert [d.label.value for d in result.decisions] == ["CONFLICT"]


def test_1b_same_wording_same_values_is_still_rejected():
    a = "2. Bên A thanh toán trong vòng 05 ngày kể từ ngày nhận hóa đơn."
    b = "3.1. Bên A thanh toán trong vòng 5 ngày kể từ ngày nhận hóa đơn"
    result = classify([pair(a, b)], {"results": [answer(span_a=a[:40], span_b=b[:40])]})
    assert not result.decisions


# -- 1c: "khoản 4.21" is not a citation of 4.2 ------------------------------------------


@pytest.mark.parametrize(
    ("other", "expected"),
    [
        ("theo khoan 4.21 cua hop dong", False),
        ("theo khoan 4.2 cua hop dong", True),
        ("khoan 4.2.1", False),
        ("theo khoan 4.2", True),
    ],
)
def test_1c_cites_requires_number_boundary(other, expected):
    assert _cites("4.2. Bên A thanh toán.", other) is expected


# -- 1d: compare.py installment key ------------------------------------------------------


def _fact(fact_id: str, raw: str, span: str) -> Fact:
    return Fact(
        fact_id=fact_id,
        raw_value=raw,
        item_key="payment_schedule",
        citation=Citation(node_id="n", page_revision_id="p", text_span=span),
    )


def test_1d_unmarked_advance_is_not_forced_into_an_installment():
    from app.pipeline.compare import _installment

    assert _installment(_fact("f1", "30%", "Bên A tạm ứng 30% giá trị hợp đồng")) is None


def test_1d_multi_installment_sentence_keys_each_value_by_its_own_installment():
    sentence = "Đợt 1: 30% giá trị hợp đồng; đợt 2: 40% giá trị hợp đồng."
    second = _fact("f1", "40%", sentence)
    annex_second = _fact("f2", "45%", "Đợt 2: 45% giá trị hợp đồng")
    annex_first = _fact("f3", "25%", "Đợt 1: 25% giá trị hợp đồng")
    assert _context_key(second, True) == _context_key(annex_second, True)
    assert _context_key(second, True) != _context_key(annex_first, True)


def test_1d_split_groups_receive_unmarked_facts():
    from app.pipeline.compare import compare_facts

    advance = _fact("f1", "30%", "Bên A tạm ứng 30% giá trị hợp đồng")
    first = _fact("f2", "25%", "Đợt 1: 25% giá trị hợp đồng").model_copy(
        update={"source_role": "annex"}
    )
    candidates, _ = compare_facts([advance, first], split_installments=True)
    assert {(c.left_id, c.right_id) for c in candidates} & {("f1", "f2"), ("f2", "f1")}


# -- 1d: ask_intent "khác nhau" ----------------------------------------------------------


@pytest.mark.parametrize(
    "question",
    [
        "Điều 5 hợp đồng và Phụ lục 1 khác nhau thế nào?",
        "Thanh toán giữa hợp đồng và phụ lục khác nhau ở đâu?",
    ],
)
def test_1d_khac_nhau_with_a_source_stays_compare(question):
    assert parse_ask(question)["type"] == "compare"


# -- 1d: pair_classifier explicit-reference fallback ------------------------------------


@pytest.mark.parametrize("label", ["CONFLICT", "DUPLICATE"])
def test_1d_conflict_with_off_span_is_not_relabelled_reference(label):
    referrer = "Bên B lập báo cáo sự cố theo khoản 2 Điều 3 của Hợp đồng trong vòng 24 giờ."
    target = "3.2. Bên B phải khắc phục sự cố trong vòng 04 giờ kể từ khi nhận thông báo."
    candidate = PairCandidate("b", "a", frozenset({PairSource.EXPLICIT_REF}), 4, None, referrer="a")
    off = {"span_a": target[:30] + " (lệch)", "span_b": referrer[:30] + " (lệch)"}
    result = classify(
        [ClassifierPair(candidate, target, referrer, "Điều 3", "Điều 6")],
        {"results": [answer(label=label, **off)]},
    )
    assert [d.label.value for d in result.decisions] == []
    assert result.stats["rejected"]["ungrounded_span"] == 1
    assert result.stats["pairs_unclassified"] == 1


# -- 1d: frame_context slot batch output budget ------------------------------------------


def test_1d_slot_batch_output_budget_scales_with_frames(monkeypatch):
    seen: list[dict] = []
    _batch_setup(
        monkeypatch,
        8,
        lambda payload: {"frames": [{"id": f["id"], "slots": []} for f in payload["frames"]]},
        seen,
    )
    from test_frame_job import semantic_record

    per_frame = semantic_record().semantic_profile.context_bounds.max_output_tokens
    assert seen[0]["max_output_tokens"] == min(per_frame * 8, 8192)
    assert seen[0]["max_output_tokens"] > per_frame or per_frame * 8 > 8192


# -- 1d: lease outlives the child kill ---------------------------------------------------


def test_1d_job_lease_outlives_the_isolated_child_kill():
    from app.api import main

    budget = 310
    lease_ms = main._job_lease_ms(budget)
    # Child is killed at spawn + budget + grace; the claim happens after spawn, so the lease
    # (claim + lease_ms) must still be live at the kill or the sweep wins with WORKER_RESTARTED.
    assert lease_ms >= (budget + main._JOB_KILL_GRACE_SECONDS + 30) * 1000


def test_1d_worker_claims_with_the_long_lease(monkeypatch, tmp_path):
    from test_a1_query_digest import _body_only_request

    from app.api import main
    from app.tools.jobs import SQLiteJobStore

    monkeypatch.setenv("AI2_SERVICE_HMAC_SECRET", "test-secret")
    monkeypatch.setenv("AI2_PROCESSING_EGRESS_ALLOWED", "false")
    store = SQLiteJobStore(tmp_path / "lease.sqlite")
    monkeypatch.setattr(main, "JOB_STORE", store)
    monkeypatch.setattr(main, "WIRE_JOBS", {})
    payload = _body_only_request()
    job, _ = store.create_or_get(
        tenant_id="tenant_a",
        dossier_id=payload["dossier_id"],
        request_id=payload["request_id"],
        idempotency_key=payload["idempotency_key"],
        attempt=1,
        request=payload,
        wire={"status": "QUEUED", "result": None, "errors": []},
    )
    seen = {}

    def claim(job_id, **kwargs):
        seen.update(kwargs)
        return None

    monkeypatch.setattr(store, "claim", claim)
    main._execute_wire_job(job["job_id"], payload)
    budget = payload["policy_flags"]["budget_limits"]["max_processing_seconds"]
    assert seen["lease_ms"] > (budget + main._JOB_KILL_GRACE_SECONDS) * 1000


# -- Section 2: merged line nodes against AI1 page text -----------------------------------

WRAP = [
    "x" * 100 + ".",
    "1.1. Bên B cung cấp 20 máy quét mã vạch, cài đặt phần mềm quản lý kho và hướng dẫn",
    "sử dụng cho Bên A.",
]


def _wrapped_record(separator: str | None):
    lines = [
        {
            "line_id": f"l{i}",
            "raw_text": text,
            "bbox": [0.1, 0.1 + i * 0.05, 0.9 - (0.5 if i == 2 else 0), 0.14 + i * 0.05],
            "geometry_status": "measured",
            "bbox_source": "native",
            "words": [],
        }
        for i, text in enumerate(WRAP)
    ]
    extra = {} if separator is None else {"text": separator.join(WRAP)}
    return adapt_snapshot(_snapshot(pages=[_page(lines=lines, **extra)])).record


@pytest.mark.parametrize("separator", [None, "\n", "\r\n", " "])
def test_2_merged_node_text_is_exact_page_substring_for_any_ai1_separator(separator):
    record = _wrapped_record(separator)
    page = record.pages[0]
    (merged,) = [n for n in record.nodes if len(n.source_line_ids) > 1]
    assert merged.text in canonical_page_text(page)
    citation = citation_for_node(record.evidence_nodes(), record.pages, merged.node_id)
    assert citation["validation_status"] == "VALID"
    assert citation["text_span"] == merged.text


@pytest.mark.parametrize("separator", [None, "\r\n", " "])
def test_2_frame_evidence_of_merged_node_resolves(separator):
    from app.contracts.clause_frames import Evidence
    from app.pipeline.frame_context import _evidence

    record = _wrapped_record(separator)
    (merged,) = [n for n in record.nodes if len(n.source_line_ids) > 1]
    record.semantic_snapshots = {merged.source_file_id: "snap"}
    evidence = Evidence(merged.source_file_id, "snap", merged.node_id, merged.text)
    citation = _evidence(record, evidence).citation
    assert citation.char_start is not None
    assert citation.validation_status == "VALID"
    assert (
        CitationResolver(record.pages, record.tables, record.evidence_nodes())
        .verify(Citation.model_validate(citation.model_dump()))
        .valid
    )


def test_2_merged_node_keeps_per_line_bboxes_and_union_is_only_the_envelope():
    record = _wrapped_record("\n")
    page = record.pages[0]
    (merged,) = [n for n in record.nodes if len(n.source_line_ids) > 1]
    per_line = [page.line_bboxes[line_id] for line_id in merged.source_line_ids]
    # page.line_bboxes is AI1's own geometry, untouched.
    assert per_line == [pytest.approx([0.1, 0.15, 0.9, 0.19]), pytest.approx([0.1, 0.2, 0.4, 0.24])]
    citation = citation_for_node(record.evidence_nodes(), record.pages, merged.node_id)
    assert citation["bbox_fragments"] == per_line
    assert merged.bbox == pytest.approx([0.1, 0.15, 0.9, 0.24])


@pytest.mark.parametrize(
    "path",
    [
        "ai1/examples/dossier-001/contract-001/ocr-run-demo-contract-001-001.json",
        "ai1/examples/dossier-001/annex-001/ocr-run-demo-annex-001-001.json",
    ],
)
def test_2_stored_ai1_snapshot_line_geometry_and_text_are_untouched(path):
    payload = json.loads((ROOT / path).read_text(encoding="utf-8"))
    record = adapt_ai1_input(payload).record
    for raw_page, page in zip(payload["pages"], record.pages, strict=True):
        assert page.text == raw_page["text"]
        assert page.line_texts == {line["line_id"]: line["text"] for line in raw_page["lines"]}
        assert page.line_bboxes == {
            line["line_id"]: line["bbox_normalized"] for line in raw_page["lines"]
        }
    for node in record.evidence_nodes():
        if node.type == "TABLE" or not node.text:
            continue
        page = next(p for p in record.pages if p.page_revision_id == node.page_revision_id)
        assert node.text in page.text
        citation = citation_for_node(record.evidence_nodes(), record.pages, node.node_id)
        assert citation["validation_status"] == "VALID", node.node_id


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
