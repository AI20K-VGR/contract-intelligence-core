"""OCR lines that wrap one clause become one evidence node (plans/261016-1524-ai2-paragraph-nodes)."""

from __future__ import annotations

import pytest

from app.pipeline.ai1_snapshot_adapter import adapt_be_ai2_processing_request
from app.pipeline.outline import citation_for_node
from fixtures.seeded import hd_test_2026_001 as hd

WIDE = "x" * 100  # sets the page's full-line width so short lines read as short


def _nodes(monkeypatch, pages):
    monkeypatch.setenv("AI2_SEMANTIC_CONTEXT_CAPS", hd.context_caps_env())
    payload = hd.request(body_pages=pages, annex_pages=[["PHỤ LỤC 01", WIDE]])
    env = payload["service_envelope"]
    record = adapt_be_ai2_processing_request(payload, tenant_id=env["tenant_id"], actor_id=env["actor_id"])[1].record
    body = [n for n in record.evidence_nodes() if n.source_file_id and "doc_body" in (n.source_file_id or "")
            and n.text]
    return record, body


def _texts(nodes):
    return [" ".join(n.text.split()) for n in nodes]


def test_seeded_wrapped_clauses_are_single_nodes(monkeypatch):
    record, body = _nodes(monkeypatch, hd.BODY_PAGES)
    texts = _texts(body)
    assert ("1.1. Bên B cung cấp 20 máy quét mã vạch, cài đặt phần mềm quản lý kho và hướng dẫn "
            "sử dụng cho Bên A.") in texts
    assert any(t.startswith("4.1. Tổng giá trị") and t.endswith("thuế giá trị gia tăng.") for t in texts)
    assert "Bên A." not in texts and "thuế giá trị gia tăng." not in texts
    merged = next(n for n in body if n.text.startswith("1.1."))
    assert len(merged.source_line_ids) == 2
    assert merged.node_id == f"line:1:{merged.source_line_ids[0]}"


def test_merged_node_text_is_exact_page_substring_and_cites_valid(monkeypatch):
    record, body = _nodes(monkeypatch, hd.BODY_PAGES)
    merged = next(n for n in body if n.text.startswith("4.1."))
    page = next(p for p in record.pages if p.page_revision_id == merged.page_revision_id)
    assert merged.text in page.text
    citation = citation_for_node(record.evidence_nodes(), record.pages, merged.node_id)
    assert citation["validation_status"] == "VALID"
    assert citation["text_span"] == merged.text
    assert citation["line_ids"] == merged.source_line_ids


@pytest.mark.parametrize("lines", [
    # short heading followed by a table cell
    [WIDE + ".", "1. Bảng giá hạng mục", "Hạng mục"],
    # previous line ends a sentence
    [WIDE + ".", WIDE + " hết câu.", "Bên A thanh toán đúng hạn cho Bên B theo hóa đơn."],
    # next line opens a numbered clause / point / bullet
    [WIDE, "2.1. Khoản kế tiếp bắt đầu bằng số thứ tự."],
    [WIDE, "a) Điểm kế tiếp."],
    [WIDE, "- Gạch đầu dòng kế tiếp."],
    # next line is a structural heading or an all-caps line (footer/title)
    [WIDE, "Điều 7. Bảo hành"],
    [WIDE, "TÀI LIỆU MẪU KIỂM THỬ AI2 - KHÔNG CÓ GIÁ TRỊ GIAO DỊCH"],
    [WIDE, "Trang 1"],
    # a running header (all caps) is never continued by the first sentence below it
    ["TÀI LIỆU MẪU KIỂM THỬ AI2 - KHÔNG CÓ GIÁ TRỊ GIAO DỊCH", "lịch kể từ ngày nhận đủ hồ sơ hợp lệ."],
    # a page of only short lines: relative width alone would call a heading "full"
    ["Điều 1. Các bên", "Bên A thanh toán.", "Điều 2. Phạm vi"],
    # tab-separated table rows, and Roman-numbered clauses ("IV.1.") open a new block
    ["ĐT-70\tĐợt 70 – bản sao hợp đồng liên quan đến công trình\t25%\tngày thứ 151\t405.000.000",
     "ĐT-71\tĐợt 71 – bản sao hợp đồng liên quan đến công trình\t25%\tngày thứ 152\t406.000.000"],
    [WIDE, "IV.1. Mức khả dụng cam kết theo thang đo liên tục 24x7 là 99,5%."],
    # AI1 renders table rows as "| a | b |" lines: rows stay rows, prose after a table stays apart
    ["| STT | Hạng mục / Mô tả | DVT | SL | Đơn giá | Thành tiền | Thuế suất | Ghi chú |",
     "| 1 | Máy chủ ứng dụng cấu hình tiêu chuẩn doanh nghiệp | bộ | 2 | 12.150.000 | 24.300.000",
     "| 2 | Thiết bị lưu trữ và phụ kiện mở rộng | bộ | 3 | 13.500.000 | 40.500.000 | 10% |",
     "| P4 - Thấp | Yêu cầu hỗ trợ / cải tiến nhỏ | 1 ngày làm việc | Theo kế hoạch phát hành",
     "Thời gian khắc phục là mục tiêu dịch vụ và có thể phụ thuộc vào mức độ phức tạp."],
])
def test_block_starts_and_finished_lines_are_not_merged(monkeypatch, lines):
    _, body = _nodes(monkeypatch, [lines])
    assert len(body) == len(lines), _texts(body)


def test_clause_compare_still_sees_merged_clause(monkeypatch):
    # clause_compare maps lines to nodes; a merged node must stay reachable from each line.
    from app.pipeline.clause_compare import _build_outline

    record, body = _nodes(monkeypatch, hd.BODY_PAGES)
    outline = _build_outline(record, body[0].source_file_id)
    article4 = next(a for a in outline.articles if a.number == 4)
    first = article4.subs[0]
    assert {line.node.node_id for line in first.lines if line.node} == {
        next(n for n in body if n.text.startswith("4.1.")).node_id
    }


# -- clauses cut by a page break: flagged for review, never merged (citations stay one-page) --

FOOTER = "TÀI LIỆU MẪU KIỂM THỬ AI2 - KHÔNG CÓ GIÁ TRỊ GIAO DỊCH"
TAIL = "3.4. Bên B hoàn thành bước nghiệm thu sơ bộ với chịu trách nhiệm: Bên A, thời hạn: 6 ngày"


def _issues(monkeypatch, pages):
    record, body = _nodes(monkeypatch, pages)
    return [i for i in record.handoff_issues if i.code == "CLAUSE_CONTINUES_ON_NEXT_PAGE"], body


def test_clause_cut_by_page_break_is_flagged_with_both_nodes(monkeypatch):
    pages = [[WIDE + ".", TAIL, FOOTER, "Trang 1"],
             [FOOTER, "lịch kể từ ngày nhận đủ hồ sơ hợp lệ của Bên B.", "3.5. Khoản kế tiếp."]]
    issues, body = _issues(monkeypatch, pages)
    assert len(issues) == 1, [i.message for i in issues]
    issue = issues[0]
    ids = {n.text.split("\n")[0][:12]: n.node_id for n in body}
    assert issue.evidence_refs == [ids[TAIL[:12]], ids["lịch kể từ n"]]
    assert issue.review_state.value == "NEEDS_REVIEW"
    assert issue.document_id and "1" in issue.location and "2" in issue.location
    # never merged: each part stays citable on its own page
    assert all(n.page_range in ([1], [2]) for n in body)


@pytest.mark.parametrize("pages", [
    [[WIDE + ".", WIDE + " hết câu.", FOOTER], [FOOTER, "Bên A thanh toán đúng hạn cho Bên B theo hóa đơn."]],
    [[WIDE + ".", TAIL, FOOTER], [FOOTER, "3.5. Khoản kế tiếp bắt đầu bằng số thứ tự."]],
    [[WIDE + ".", TAIL], []],
])
def test_finished_or_new_block_at_page_break_is_not_flagged(monkeypatch, pages):
    assert _issues(monkeypatch, pages)[0] == []


def test_seeded_hd_test_has_no_page_break_cut(monkeypatch):
    assert _issues(monkeypatch, hd.BODY_PAGES)[0] == []
