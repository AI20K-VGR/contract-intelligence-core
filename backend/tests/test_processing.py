import json
import os
import subprocess
import sys

import pymupdf
import pytest

from app.document_processing import _nfc, process_page
from app.evidence import citation, validate_result
from app.storage import ArtifactStore, digest


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_rotated_cropped_native_geometry(tmp_path, rotation):
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=600, height=800)
        page.insert_text((100, 150), "100.000.000 VND")
        page.set_cropbox(pymupdf.Rect(40, 50, 550, 750))
        page.set_rotation(rotation)
        source = pdf.tobytes()
    store = ArtifactStore(tmp_path)
    payload = {
        "document_id": "doc",
        "role": "contract",
        "sha256": digest(source),
        "storage_key": store.put(source, "pdf"),
        "page_number": 1,
    }
    page = process_page(payload, {"dpi": 100, "max_pixels": 2_000_000}, store)
    assert page["engine"] == "pymupdf"
    cit = citation(page, page["lines"][0], "run")
    assert 0 <= cit["bbox"][0] < cit["bbox"][2] <= 1
    assert 0 <= cit["bbox"][1] < cit["bbox"][3] <= 1
    validate_result({"citations": [cit], "pages": [page], "facts": [], "findings": []})


def test_native_table_extraction(tmp_path):
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=600, height=800)
        x0, y0, col_w, row_h = 50, 50, 150, 30
        for r in range(3):
            page.draw_line((x0, y0 + r * row_h), (x0 + 2 * col_w, y0 + r * row_h))
        for c in range(3):
            page.draw_line((x0 + c * col_w, y0), (x0 + c * col_w, y0 + 2 * row_h))
        labels = [["Khoan muc", "So tien"], ["Coc", "10.000.000 VND"]]
        for r in range(2):
            for c in range(2):
                page.insert_text((x0 + c * col_w + 5, y0 + r * row_h + 20), labels[r][c])
        source = pdf.tobytes()
    store = ArtifactStore(tmp_path)
    payload = {
        "document_id": "doc",
        "role": "contract",
        "sha256": digest(source),
        "storage_key": store.put(source, "pdf"),
        "page_number": 1,
    }
    result = process_page(payload, {"dpi": 100, "max_pixels": 2_000_000}, store)
    assert result["engine"] == "pymupdf"
    assert len(result["tables"]) == 1
    table = result["tables"][0]
    assert table["row_count"] == 2 and table["col_count"] == 2
    assert table["rows"][0]["cells"][0]["text"] == "Khoan muc"
    assert table["rows"][1]["cells"][1]["text"] == "10.000.000 VND"
    for row in table["rows"]:
        for cell in row["cells"]:
            assert 0 <= cell["bbox"][0] < cell["bbox"][2] <= 1
            assert 0 <= cell["bbox"][1] < cell["bbox"][3] <= 1


def _table(document_id, page_number, bbox, col_count, row_count=1, index=0):
    return {
        "id": f"table:{document_id}:{page_number}:{index}",
        "document_id": document_id,
        "page_number": page_number,
        "row_count": row_count,
        "col_count": col_count,
        "bbox": bbox,
        "rows": [],
    }


def test_table_continuation_linked_high_confidence_when_columns_match():
    from app.tables import link_continuations

    # Table on page 1 ends near the page bottom (y1=0.92); the next page's table
    # starts near the top (y0=0.05) and has the same column count — the layout
    # signature of a table split by a page break with only the first page's header.
    page1 = _table("doc", 1, [0.1, 0.3, 0.9, 0.92], col_count=7)
    page2 = _table("doc", 2, [0.1, 0.05, 0.9, 0.8], col_count=7)
    link_continuations([page1, page2])
    assert page2["continues_table_id"] == page1["id"]
    assert page1["continued_by_table_id"] == page2["id"]
    assert page2["continuation_confidence"] == "high"


def test_table_continuation_linked_low_confidence_when_columns_differ():
    from app.tables import link_continuations

    # Same page-edge layout as above (the exact screenshot the user reported: 7 cols
    # on page 1, 11 cols detected on page 2 for what is visually the same table) —
    # still linked, since PyMuPDF's column detection can shift across a page break,
    # but flagged low-confidence instead of silently presented as certain.
    page1 = _table("doc", 1, [0.1, 0.3, 0.9, 0.92], col_count=7)
    page2 = _table("doc", 2, [0.1, 0.05, 0.9, 0.8], col_count=11)
    link_continuations([page1, page2])
    assert page2["continues_table_id"] == page1["id"]
    assert page2["continuation_confidence"] == "low"


def test_table_continuation_not_linked_when_not_near_page_edges():
    from app.tables import link_continuations

    # A table that merely happens to exist on two consecutive pages, but isn't
    # anchored to the bottom/top edge, is not a continuation candidate.
    page1 = _table("doc", 1, [0.1, 0.3, 0.9, 0.5], col_count=7)
    page2 = _table("doc", 2, [0.1, 0.4, 0.9, 0.6], col_count=7)
    link_continuations([page1, page2])
    assert page2["continues_table_id"] is None
    assert page1["continued_by_table_id"] is None
    assert page2["continuation_confidence"] is None


def test_table_continuation_ignores_different_documents_and_page_gaps():
    from app.tables import link_continuations

    same_doc_gap = [
        _table("doc", 1, [0.1, 0.3, 0.9, 0.92], col_count=7),
        _table("doc", 3, [0.1, 0.05, 0.9, 0.8], col_count=7),  # page 2 missing/failed
    ]
    different_docs = [
        _table("doc-a", 1, [0.1, 0.3, 0.9, 0.92], col_count=7),
        _table("doc-b", 2, [0.1, 0.05, 0.9, 0.8], col_count=7),
    ]
    link_continuations(same_doc_gap + different_docs)
    assert all(t["continues_table_id"] is None for t in same_doc_gap + different_docs)


def test_nfc_normalizes_decomposed_vietnamese_diacritics():
    # Some PDF fonts store "ề" as "ê" (U+00EA) followed by a separate combining grave
    # accent (U+0300) instead of the single precomposed codepoint (U+1EC1) — renders
    # identically, but only the precomposed form byte-matches structure.py's literal
    # "Điều"/"Khoản" regexes. This is the exact codepoint split PyMuPDF was observed
    # to produce for one contract's "Điều 5" heading, causing it to be missed and
    # mis-nested as a fragment instead of a new top-level article.
    decomposed = "Điều 5"
    assert decomposed != "Điều 5"
    assert _nfc(decomposed) == "Điều 5"


def test_clause_hierarchy_parent_child_and_per_document_reset():
    from app.structure import clauses

    pages = [
        {
            "document_id": "doc-a",
            "lines": [
                {"id": "a1", "text": "Article 1. Term"},
                {"id": "a2", "text": "within 30 days"},
            ],
        },
        {
            "document_id": "doc-b",
            "lines": [
                {"id": "b1", "text": "Standalone note before any article"},
                {"id": "b2", "text": "Article 1. Term"},
                {"id": "b3", "text": "within 45 days"},
            ],
        },
    ]
    result = clauses(pages, "run")
    by_id = {c["id"]: c for c in result}
    assert by_id["clause:a1"]["type"] == "article" and by_id["clause:a1"]["parent_id"] is None
    assert by_id["clause:a2"]["type"] == "fragment" and by_id["clause:a2"]["parent_id"] == "clause:a1"
    assert "clause:b1" not in by_id
    assert by_id["clause:b2"]["type"] == "article"
    assert by_id["clause:b3"]["parent_id"] == "clause:b2"


def test_clause_hierarchy_detects_khoan_and_diem_sublevels():
    from app.structure import clauses

    pages = [
        {
            "document_id": "doc",
            "lines": [
                {"id": "l1", "text": "Điều 3. Giá trị hợp đồng và phương thức thanh toán"},
                {"id": "l2", "text": "1. Giá trị hợp đồng là 100.000.000 VND"},
                {"id": "l3", "text": "2. Phương thức thanh toán được thực hiện như sau:"},
                {"id": "l4", "text": "a) Đợt 1: thanh toán 50% ngay khi ký hợp đồng."},
                {"id": "l5", "text": "b) Đợt 2: thanh toán phần còn lại trong vòng 30 ngày."},
                {"id": "l6", "text": "Việc thanh toán chậm sẽ chịu lãi suất theo quy định."},
            ],
        }
    ]
    result = clauses(pages, "run")
    by_id = {c["id"]: c for c in result}
    assert by_id["clause:l1"]["type"] == "article" and by_id["clause:l1"]["parent_id"] is None
    assert by_id["clause:l2"]["type"] == "clause" and by_id["clause:l2"]["parent_id"] == "clause:l1"
    assert by_id["clause:l3"]["type"] == "clause" and by_id["clause:l3"]["parent_id"] == "clause:l1"
    assert by_id["clause:l4"]["type"] == "point" and by_id["clause:l4"]["parent_id"] == "clause:l3"
    assert by_id["clause:l5"]["type"] == "point" and by_id["clause:l5"]["parent_id"] == "clause:l3"
    # Running text after a point stays anchored to that point, not back up to the clause.
    assert by_id["clause:l6"]["type"] == "fragment" and by_id["clause:l6"]["parent_id"] == "clause:l5"
    assert all(c["document_id"] == "doc" for c in result)


def test_clause_hierarchy_merges_a_sentence_wrapped_across_lines():
    from app.structure import clauses

    pages = [
        {
            "document_id": "doc",
            "lines": [
                {"id": "l1", "text": "Điều 5: Điều khoản chung"},
                {"id": "l2", "text": "- Sau khi lắp đặt xong các bên cùng tiến hành làm biên bản"},
                {"id": "l3", "text": "nghiệm thu bàn giao và thanh toán như điều 3 đã ghi rõ."},
                {"id": "l4", "text": "- Trong quá trình thực hiện nếu có phát sinh vướng mắc"},
                {"id": "l5", "text": "các bên cùng nhau giải quyết trên tinh thần hợp tác."},
            ],
        }
    ]
    result = clauses(pages, "run")
    # l2+l3 wrap one bullet's sentence and must merge into a single fragment; l4+l5
    # are a second, separate bullet and must not be pulled into the first.
    assert [c["id"] for c in result] == ["clause:l1", "clause:l2", "clause:l4"]
    merged = next(c for c in result if c["id"] == "clause:l2")
    assert merged["label"] == (
        "- Sau khi lắp đặt xong các bên cùng tiến hành làm biên bản "
        "nghiệm thu bàn giao và thanh toán như điều 3 đã ghi rõ."
    )
    assert merged["citation_ids"] == ["run:l2", "run:l3"]
    second = next(c for c in result if c["id"] == "clause:l4")
    assert second["label"] == (
        "- Trong quá trình thực hiện nếu có phát sinh vướng mắc "
        "các bên cùng nhau giải quyết trên tinh thần hợp tác."
    )
    assert second["citation_ids"] == ["run:l4", "run:l5"]


def test_clause_hierarchy_does_not_merge_fragments_from_different_parents():
    from app.structure import clauses

    pages = [
        {
            "document_id": "doc",
            "lines": [
                {"id": "l1", "text": "Điều 1. Mở đầu"},
                {"id": "l2", "text": "một câu chưa kết thúc"},
                {"id": "l3", "text": "1. Giá trị hợp đồng"},
                {"id": "l4", "text": "một câu khác chưa kết thúc"},
            ],
        }
    ]
    result = clauses(pages, "run")
    by_id = {c["id"]: c for c in result}
    # l2 hangs off the article directly; l3 opens a new clause node, so l4 (also
    # unterminated) must attach to the clause, not silently merge into l2's fragment.
    assert by_id["clause:l2"]["parent_id"] == "clause:l1"
    assert by_id["clause:l4"]["parent_id"] == "clause:l3"
    assert "clause:l4" in by_id  # kept as its own node, not merged into l2


def test_clause_hierarchy_recognizes_headers_without_diacritics():
    # Real hard case: a degraded scan (or ASCII-only source text) that lost every
    # Vietnamese diacritic entirely — "DIEU 1." instead of "Điều 1." — not just a
    # different Unicode form of already-accented text (that's what _nfc handles).
    # Before strip_diacritics, ARTICLE_PATTERN never matched "Dieu" at all, so
    # state["article"] was never set and EVERY line in the document — not just the
    # headers — fell through to "else: continue" and produced no structure at all.
    from app.structure import clauses

    pages = [
        {
            "document_id": "doc",
            "lines": [
                {"id": "l1", "text": "DIEU 1. NOI DUNG VA PHAM VI CONG VIEC"},
                {"id": "l2", "text": "Ben B cung cap thiet bi, dich vu trien khai va ho tro van hanh."},
                {"id": "l3", "text": "DIEU 2. GIA TRI HOP DONG"},
                {"id": "l4", "text": "Tong gia tri tam tinh: 486.750.000 VND (Da bao gom VAT)."},
                {"id": "l5", "text": "DIEU 3. THANH TOAN VA NGHIEM THU"},
                {"id": "l6", "text": "1. Dot 1: 30% sau khi ky hop dong va tiep nhan ke hoach trien khai."},
                {"id": "l7", "text": "2. Dot 2: 50% sau khi hoan thanh ban giao thiet bi va nghiem thu."},
            ],
        }
    ]

    result = clauses(pages, "run")
    by_id = {c["id"]: c for c in result}

    assert by_id["clause:l1"]["type"] == "article" and by_id["clause:l1"]["parent_id"] is None
    assert by_id["clause:l2"]["type"] == "fragment" and by_id["clause:l2"]["parent_id"] == "clause:l1"
    assert by_id["clause:l3"]["type"] == "article"
    assert by_id["clause:l4"]["parent_id"] == "clause:l3"
    assert by_id["clause:l5"]["type"] == "article"
    assert by_id["clause:l6"]["type"] == "clause" and by_id["clause:l6"]["parent_id"] == "clause:l5"
    assert by_id["clause:l7"]["type"] == "clause" and by_id["clause:l7"]["parent_id"] == "clause:l5"
    # Matching is diacritic-insensitive, but the stored label is the original text,
    # unaccented or not — never silently rewritten.
    assert by_id["clause:l1"]["label"] == "DIEU 1. NOI DUNG VA PHAM VI CONG VIEC"


def test_scan_routes_to_local_ocr_and_empty_is_not_blank(tmp_path, monkeypatch):
    import io

    from PIL import Image

    import app.document_processing as processing

    image = Image.new("RGB", (200, 100), "white")
    png = io.BytesIO()
    image.save(png, format="PNG")
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=200, height=100)
        page.insert_image(page.rect, stream=png.getvalue())
        source = pdf.tobytes()
    called = []

    def mock_ocr(*args, **kwargs):
        called.append(kwargs)
        return {"text": []}

    monkeypatch.setattr(processing.pytesseract, "image_to_data", mock_ocr)
    store = ArtifactStore(tmp_path)
    payload = {
        "document_id": "doc",
        "role": "contract",
        "sha256": digest(source),
        "storage_key": store.put(source, "pdf"),
        "page_number": 1,
    }
    result = process_page(
        payload,
        {"dpi": 100, "max_pixels": 2_000_000, "ocr_languages": "vie+eng", "ocr_timeout_seconds": 5},
        store,
    )
    assert called[0]["lang"] == "vie+eng"
    assert result["status"] == "needs_review"
    assert result["issue"] == "EMPTY_OCR_REQUIRES_REVIEW"


def _scan_pdf_payload(tmp_path):
    import io

    from PIL import Image

    image = Image.new("RGB", (200, 100), "white")
    png = io.BytesIO()
    image.save(png, format="PNG")
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=200, height=100)
        page.insert_image(page.rect, stream=png.getvalue())
        source = pdf.tobytes()
    store = ArtifactStore(tmp_path)
    return store, {
        "document_id": "doc",
        "role": "contract",
        "sha256": digest(source),
        "storage_key": store.put(source, "pdf"),
        "page_number": 1,
    }


def _mock_two_tesseract_lines(*args, **kwargs):
    return {
        "text": ["Hello", "World", "Foo", "Bar"],
        "left": [10, 60, 10, 60],
        "top": [10, 10, 30, 30],
        "width": [40, 40, 30, 30],
        "height": [15, 15, 15, 15],
        "block_num": [1, 1, 1, 1],
        "par_num": [1, 1, 1, 1],
        "line_num": [1, 1, 2, 2],
    }


def test_gpt_vision_replaces_text_but_keeps_tesseract_bbox_on_line_match(tmp_path, monkeypatch):
    import app.document_processing as processing

    monkeypatch.setattr(processing.pytesseract, "image_to_data", _mock_two_tesseract_lines)
    base_config = {
        "dpi": 100, "max_pixels": 2_000_000, "ocr_languages": "vie+eng", "ocr_timeout_seconds": 5,
    }
    store, payload = _scan_pdf_payload(tmp_path)
    baseline = process_page(payload, base_config, store)

    monkeypatch.setattr(processing, "_gpt_vision_lines", lambda image, config: ["Xin chào", "Tạm biệt"])
    store, payload = _scan_pdf_payload(tmp_path)
    result = process_page(
        payload, {**base_config, "ocr_engine": "gpt_vision", "ocr_vision_model": "gpt-5.6-terra"}, store,
    )

    assert [line["text"] for line in result["lines"]] == ["Xin chào", "Tạm biệt"]
    assert result["engine"] == "tesseract+gpt-5.6-terra"
    assert result["status"] == "completed"
    assert result["issue"] is None
    # bbox still comes from Tesseract geometry, unaffected by the (untrusted) vision text.
    assert [line["bbox"] for line in result["lines"]] == [line["bbox"] for line in baseline["lines"]]


def test_gpt_vision_falls_back_to_tesseract_text_on_line_count_mismatch(tmp_path, monkeypatch):
    import app.document_processing as processing

    monkeypatch.setattr(processing.pytesseract, "image_to_data", _mock_two_tesseract_lines)
    monkeypatch.setattr(processing, "_gpt_vision_lines", lambda image, config: ["Only one line"])
    store, payload = _scan_pdf_payload(tmp_path)
    result = process_page(
        payload,
        {"dpi": 100, "max_pixels": 2_000_000, "ocr_languages": "vie+eng", "ocr_timeout_seconds": 5,
         "ocr_engine": "gpt_vision"},
        store,
    )
    assert [line["text"] for line in result["lines"]] == ["Hello World", "Foo Bar"]
    assert result["engine"] == "tesseract"
    assert result["status"] == "needs_review"
    assert result["issue"] == "GPT_VISION_LINE_COUNT_MISMATCH"


def test_gpt_vision_unavailable_falls_back_to_tesseract_text(tmp_path, monkeypatch):
    import app.document_processing as processing

    monkeypatch.setattr(processing.pytesseract, "image_to_data", _mock_two_tesseract_lines)
    monkeypatch.setattr(processing, "_gpt_vision_lines", lambda image, config: None)
    store, payload = _scan_pdf_payload(tmp_path)
    result = process_page(
        payload,
        {"dpi": 100, "max_pixels": 2_000_000, "ocr_languages": "vie+eng", "ocr_timeout_seconds": 5,
         "ocr_engine": "gpt_vision"},
        store,
    )
    assert [line["text"] for line in result["lines"]] == ["Hello World", "Foo Bar"]
    assert result["status"] == "needs_review"
    assert result["issue"] == "GPT_VISION_UNAVAILABLE"


def test_align_gpt_lines_drops_a_stamp_fragment_in_the_middle_without_shifting_later_lines():
    from app.document_processing import _align_gpt_lines

    # A 6-line slice of a real scanned page (690758295-Scan-HỢP-ĐỒNG-Feddy.pdf, trang 1):
    # Tesseract invented one extra "line" (index 2) out of a company stamp overlapping
    # the address block; GPT vision correctly left it out. Naive index-by-index zipping
    # would from this point on pair every later Tesseract line with the WRONG GPT text
    # (right words, wrong bbox) — global alignment must instead single out just the one
    # bad line.
    tess = [
        "Quan Lién Chiểu, Thanh phố Da Ning af C",
        "Sé tai khoản : 2013201354667 tai Ngan hang Nông Nghiép va Phat Triển Nông Thôn Viét Nam — C i an UON AN",
        "5 i DICH VỤ VÀ",
        "KCN Hoa Khanh -Nam Da Nang. ae N PHONG",
        "Điệnthoại : 0935404692 SVAN EE",
        "Mãsốthuế : 0402004822 v pe OF",
    ]
    gpt = [
        "Quận Liên Chiểu, Thành phố Đà Nẵng",
        "Số tài khoản   : 2013201354667 tại Ngân hàng Nông Nghiệp và Phát Triển Nông Thôn Việt Nam – Chi nhánh",
        "KCN Hoà Khánh -Nam Đà Nẵng.",
        "Điện thoại     : 0935404692",
        "Mã số thuế     : 0402004822",
    ]

    matches = _align_gpt_lines(tess, gpt)

    assert 2 not in matches  # the stamp-fragment line: no confident GPT counterpart
    assert matches[0] == "Quận Liên Chiểu, Thành phố Đà Nẵng"
    assert matches[1].startswith("Số tài khoản")
    # The lines AFTER the dropped one still land on their true counterpart, not shifted:
    assert matches[3] == "KCN Hoà Khánh -Nam Đà Nẵng."
    assert matches[4].startswith("Điện thoại")
    assert matches[5].startswith("Mã số thuế")


def test_align_gpt_lines_no_confident_match_returns_empty():
    from app.document_processing import _align_gpt_lines

    assert _align_gpt_lines(["Hello World", "Foo Bar"], ["Xin chào", "Tạm biệt"]) == {}


def test_process_page_uses_alignment_when_gpt_vision_line_count_differs(tmp_path, monkeypatch):
    import app.document_processing as processing

    def mock_ocr(*args, **kwargs):
        return {
            "text": ["Alpha", "STAMP", "Beta"],
            "left": [10, 10, 10],
            "top": [10, 30, 50],
            "width": [40, 40, 40],
            "height": [15, 15, 15],
            "block_num": [1, 1, 1],
            "par_num": [1, 1, 1],
            "line_num": [1, 2, 3],
        }

    monkeypatch.setattr(processing.pytesseract, "image_to_data", mock_ocr)
    monkeypatch.setattr(processing, "_gpt_vision_lines", lambda image, config: ["Alpha clean", "Beta clean"])
    store, payload = _scan_pdf_payload(tmp_path)
    result = process_page(
        payload,
        {"dpi": 100, "max_pixels": 2_000_000, "ocr_languages": "vie+eng", "ocr_timeout_seconds": 5,
         "ocr_engine": "gpt_vision"},
        store,
    )
    assert [line["text"] for line in result["lines"]] == ["Alpha clean", "Beta clean"]
    assert result["engine"] == "tesseract+gpt-5.6-terra"
    assert result["status"] == "completed"
    assert result["issue"] is None


def _word(text, x0, y0, x1, y1):
    return {"text": text, "bbox": [x0, y0, x1, y1]}


def _ocr_line(index, words):
    boxes = [w["bbox"] for w in words]
    return {
        "id": f"doc:1:{index}",
        "text": " ".join(w["text"] for w in words),
        "words": words,
        "bbox": [
            min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes),
        ],
    }


def _work_history_row(index, y, period, activity, org, title):
    # Four columns at fixed x-bands, each cell carrying two OCR word tokens (a small
    # within-cell gap) so the row also has three much larger between-cell gaps for
    # _row_cells to tell apart — mirrors how Tesseract actually tokenizes a Vietnamese
    # scanned table cell into more than one "word".
    words = [
        _word(period[0], 0.05, y, 0.09, y + 0.02),
        _word(period[1], 0.095, y, 0.14, y + 0.02),
        _word(activity[0], 0.20, y, 0.23, y + 0.02),
        _word(activity[1], 0.235, y, 0.27, y + 0.02),
        _word(org[0], 0.50, y, 0.54, y + 0.02),
        _word(org[1], 0.545, y, 0.57, y + 0.02),
        _word(title[0], 0.65, y, 0.70, y + 0.02),
        _word(title[1], 0.705, y, 0.73, y + 0.02),
    ]
    return _ocr_line(index, words)


def test_ocr_tables_detects_a_scanned_work_history_table():
    from app.document_processing import _ocr_tables

    lines = [
        _work_history_row(0, 0.10, ("Tháng", "10/2007-"), ("Làm", "việc"),
                           ("Trung", "tâm"), ("Nghiên", "cứu")),
        _work_history_row(1, 0.14, ("Tháng", "9/2009-"), ("Học", "thạc"),
                           ("Viện", "NC"), ("Học", "viên")),
        _work_history_row(2, 0.18, ("Tháng", "9/2010-"), ("Làm", "việc"),
                           ("Trung", "tâm"), ("Nghiên", "cứu")),
    ]

    tables = _ocr_tables(lines, {"document_id": "doc", "page_number": 1})

    assert len(tables) == 1
    table = tables[0]
    assert table["row_count"] == 3
    assert table["col_count"] == 4
    for row in table["rows"]:
        assert [c["col_index"] for c in row["cells"]] == [0, 1, 2, 3]
    assert table["rows"][0]["cells"][1]["text"] == "Làm việc"
    assert table["rows"][1]["cells"][1]["text"] == "Học thạc"


def test_ocr_tables_ignores_prose_paragraph():
    from app.document_processing import _ocr_tables

    sentence = "Tôi xin cam đoan những lời khai trên là đúng sự thực".split()
    lines = []
    for i in range(4):
        x = 0.08
        words = []
        for w in sentence:
            width = 0.02 + 0.006 * len(w)
            words.append(_word(w, x, 0.10 + i * 0.02, x + width, 0.10 + i * 0.02 + 0.015))
            x += width + 0.006  # ordinary single-space gap between every word
        lines.append(_ocr_line(i, words))

    assert _ocr_tables(lines, {"document_id": "doc", "page_number": 1}) == []


def test_ocr_tables_ignores_two_column_key_value_block():
    from app.document_processing import _ocr_tables

    lines = [
        _ocr_line(i, [
            _word("Tên", 0.08, 0.10 + i * 0.02, 0.11, 0.12 + i * 0.02),
            _word("công", 0.115, 0.10 + i * 0.02, 0.15, 0.12 + i * 0.02),
            _word("ty:", 0.155, 0.10 + i * 0.02, 0.18, 0.12 + i * 0.02),
            _word("ABC", 0.40, 0.10 + i * 0.02, 0.45, 0.12 + i * 0.02),
        ])
        for i in range(3)
    ]

    assert _ocr_tables(lines, {"document_id": "doc", "page_number": 1}) == []


def test_column_gap_threshold_finds_the_smallest_real_column_boundary_not_the_biggest():
    # Real hard case (Hop_dong_scan_stress_bang_lien_trang_khong_header.pdf, trang 1,
    # dong "01 |May chu ung dung..."): a genuine item row's own column gaps are rarely
    # all the same width -- here STT sits close to the description (gap 0.0238), while
    # the wide description trails into a much bigger gap before SL (0.1589), and the
    # SL/DonGia/ThanhTien/GhiChu gaps land in between (0.044, 0.0484). The single
    # BIGGEST ratio jump anywhere in the row is the last one (0.0484 -> 0.1589) --
    # picking that as the sole cutoff lumped the earlier 0.0238/0.044/0.0484 column
    # boundaries in with ordinary ~0.008 word spacing, collapsing 6 real columns down
    # to 2 groups and making _row_cells reject the entire row as not table-shaped.
    # The fix scans from the smallest gap upward and locks onto the FIRST boundary
    # confidently seen, so every later (bigger) real gap only adds evidence, never
    # grounds to reclassify an earlier one back into "spacing".
    from app.document_processing import _column_gap_threshold

    within_cell_gaps = [0.0077, 0.0089, 0.0085, 0.0085, 0.0081, 0.0085, 0.0093]
    gaps = [0.0238, *within_cell_gaps, 0.1589, 0.044, 0.0484, 0.002, 0.0056, 0.0056]

    threshold = _column_gap_threshold(gaps)

    # The threshold must fall strictly between the largest within-cell gap (0.0093)
    # and the smallest real column boundary (0.0238) -- not up near 0.1, which would
    # merge STT, the description and several real columns into one group.
    assert 0.0093 < threshold < 0.0238


def test_ocr_tables_requires_minimum_consecutive_rows():
    from app.document_processing import _ocr_tables

    lines = [
        _work_history_row(0, 0.10, ("Tháng", "10/2007-"), ("Làm", "việc"),
                           ("Trung", "tâm"), ("Nghiên", "cứu")),
        _work_history_row(1, 0.14, ("Tháng", "9/2009-"), ("Học", "thạc"),
                           ("Viện", "NC"), ("Học", "viên")),
    ]

    assert _ocr_tables(lines, {"document_id": "doc", "page_number": 1}) == []


def test_ocr_tables_survives_one_row_interrupted_by_a_stamp():
    # Real hard case (Hop_dong_scan_testcase_bang_dut_doan_con_dau): a company seal
    # overlapping one row adds a stray OCR word-group to just that row, so its group
    # count (5) no longer matches the rest of the table's (4) exactly. The stray
    # word doesn't overlap any of the table's real columns, so it's dropped as noise
    # and the row is kept with its own genuine 4 values intact — losing the whole row
    # (or worse, merging it into its neighbor) over one unrelated stray mark would be
    # a worse outcome than just ignoring that one mark.
    from app.document_processing import _ocr_tables

    good_rows = [
        _work_history_row(0, 0.10, ("Tháng", "10/2007-"), ("Làm", "việc"),
                           ("Trung", "tâm"), ("Nghiên", "cứu")),
        _work_history_row(1, 0.14, ("Tháng", "9/2009-"), ("Học", "thạc"),
                           ("Viện", "NC"), ("Học", "viên")),
        _work_history_row(3, 0.22, ("Tháng", "9/2011-"), ("Làm", "việc"),
                           ("Chi", "nhánh"), ("Kỹ", "sư")),
        _work_history_row(4, 0.26, ("Tháng", "9/2012-"), ("Nghỉ", "việc"),
                           ("Trung", "tâm"), ("Trưởng", "phòng")),
    ]
    stamped_row = _work_history_row(2, 0.18, ("Tháng", "9/2010-"), ("Làm", "việc"),
                                     ("Trung", "tâm"), ("Nghiên", "cứu"))
    stamped_row["words"].append(_word("[MỘC]", 0.80, 0.18, 0.85, 0.20))
    stamped_row["bbox"][2] = 0.85
    lines = [good_rows[0], good_rows[1], stamped_row, good_rows[2], good_rows[3]]

    tables = _ocr_tables(lines, {"document_id": "doc", "page_number": 1})

    assert len(tables) == 1
    table = tables[0]
    assert table["col_count"] == 4
    assert table["row_count"] == 5
    assert [row["cells"][1]["text"] for row in table["rows"]] == [
        "Làm việc", "Học thạc", "Làm việc", "Làm việc", "Nghỉ việc",
    ]
    # The stamp mark itself never appears anywhere in the reconstructed table.
    assert not any("MỘC" in c["text"] for row in table["rows"] for c in row["cells"])


def test_ocr_tables_ignores_page_top_noise_before_the_real_table():
    # Real hard case (Hop_dong_scan_bang_lien_trang_OCR_test.pdf, trang 2): a faint
    # watermark/margin artifact right at the top of the page gets misread as a handful
    # of isolated single-glyph tokens scattered across the row ("2 _", "~", "Z", "x",
    # "4", "^`") -- enough of them, far enough apart, to clear _row_cells' >=3-groups
    # bar despite being pure noise. Before _plausible_row existed, this noise line was
    # crowned as the block's reference simply because it came first (nothing to filter
    # against yet); every real row after it then correctly failed to match it via
    # _matching_cells, but got silently absorbed as its "wrapped continuation" instead
    # (a single word coincidentally overlapping one of the noise row's several scattered
    # cells is all _merge_wrapped_continuation needed) -- so the block never grew past
    # that one bogus row and the entire real table underneath it was discarded (a real
    # 11-row, 7-column item table produced zero detected tables on that page).
    from app.document_processing import _ocr_tables

    noise = _ocr_line(0, [
        _word("2", 0.05, 0.02, 0.06, 0.035),
        _word("_", 0.065, 0.02, 0.07, 0.035),
        _word("~", 0.30, 0.02, 0.31, 0.035),
        _word("Z", 0.50, 0.02, 0.51, 0.035),
        _word("x", 0.62, 0.02, 0.63, 0.035),
        _word("4", 0.75, 0.02, 0.76, 0.035),
        _word("^`", 0.85, 0.02, 0.86, 0.035),
    ])
    lines = [
        noise,
        _work_history_row(1, 0.10, ("Tháng", "10/2007-"), ("Làm", "việc"),
                           ("Trung", "tâm"), ("Nghiên", "cứu")),
        _work_history_row(2, 0.14, ("Tháng", "9/2009-"), ("Học", "thạc"),
                           ("Viện", "NC"), ("Học", "viên")),
        _work_history_row(3, 0.18, ("Tháng", "9/2010-"), ("Làm", "việc"),
                           ("Trung", "tâm"), ("Nghiên", "cứu")),
    ]

    tables = _ocr_tables(lines, {"document_id": "doc", "page_number": 1})

    assert len(tables) == 1
    table = tables[0]
    assert table["col_count"] == 4
    assert table["row_count"] == 3
    assert [row["cells"][1]["text"] for row in table["rows"]] == [
        "Làm việc", "Học thạc", "Làm việc",
    ]


def test_ocr_tables_skips_an_unrelated_line_with_only_one_coincidental_overlap():
    # Real hard case (Hop_dong_scan_testcase_bang_dut_doan_con_dau_v2.pdf, trang 3): an
    # unrelated line (a section heading, a stray test-case note) sitting right after a
    # table row can have a single word's bbox coincidentally overlap one of that row's
    # cells purely by chance ("PHỤ LỤC 02 - BẢNG DỊCH VỤ VẬN HÀNH (BẢNG B)" landed a
    # word inside the row above's wide description column). Before this floor existed,
    # that one coincidence was enough for _merge_wrapped_continuation to glue the ENTIRE
    # unrelated sentence onto the row's cell. Requiring at least half the line's words
    # to find a home fixes that while still accepting a genuine wrapped continuation
    # mixed with a stray noise character or two (see
    # test_ocr_tables_survives_one_row_interrupted_by_a_stamp).
    from app.document_processing import _ocr_tables

    unrelated = _ocr_line(10, [
        _word("PHỤ", 0.30, 0.16, 0.34, 0.18),
        _word("LỤC", 0.35, 0.16, 0.39, 0.18),
        _word("02", 0.40, 0.16, 0.42, 0.18),
        _word("-", 0.43, 0.16, 0.44, 0.18),
        _word("BẢNG", 0.45, 0.16, 0.49, 0.18),
        _word("nhánh", 0.545, 0.16, 0.57, 0.18),
    ])
    lines = [
        _work_history_row(0, 0.10, ("Tháng", "10/2007-"), ("Làm", "việc"),
                           ("Trung", "tâm"), ("Nghiên", "cứu")),
        _work_history_row(1, 0.14, ("Tháng", "9/2009-"), ("Học", "thạc"),
                           ("Viện", "NC"), ("Học", "viên")),
        unrelated,
        _work_history_row(2, 0.22, ("Tháng", "9/2011-"), ("Làm", "việc"),
                           ("Chi", "nhánh"), ("Kỹ", "sư")),
    ]

    tables = _ocr_tables(lines, {"document_id": "doc", "page_number": 1})

    assert len(tables) == 1
    table = tables[0]
    assert table["col_count"] == 4
    assert table["row_count"] == 3
    # Row 1's "org" cell (col_index 2) stays exactly "Viện NC" -- untouched by the
    # unrelated line's stray "nhánh" word, which shares its column purely by chance.
    org_cell = next(c for c in table["rows"][1]["cells"] if c["col_index"] == 2)
    assert org_cell["text"] == "Viện NC"
    assert not any(
        "PHỤ" in c["text"] or "LỤC" in c["text"] or "BẢNG" in c["text"]
        for row in table["rows"] for c in row["cells"]
    )


def _cells_line(index, y, cells_by_column):
    """One OCR line built from `(x0, x1, [word_texts])` per column, skipping any
    column whose word list is empty — the shape of one physical scanned line where
    some columns are blank (a legitimately empty cell) or simply don't have any
    wrapped continuation text on this particular visual line."""
    words = []
    for x0, x1, texts in cells_by_column:
        if not texts:
            continue
        step = (x1 - x0) / len(texts)
        x = x0
        for text in texts:
            width = max(step - 0.003, 0.005)
            words.append(_word(text, x, y, min(x + width, x1), y + 0.018))
            x += step
    return _ocr_line(index, words)


# Column x-bands reconstructing the real hard_case screenshot's layout: STT | Nội
# dung hàng hóa/dịch vụ | ĐVT | SL | Đơn giá (VND) | Thành tiền (VND) | Ghi chú.
_STT = (0.02, 0.07)
_NOIDUNG = (0.09, 0.52)
_DVT = (0.54, 0.60)
_SL = (0.62, 0.67)
_DONGIA = (0.69, 0.80)
_THANHTIEN = (0.82, 0.93)
_GHICHU = (0.95, 0.99)


def test_ocr_tables_reconstructs_a_real_scanned_item_table():
    # Reconstructs the hard_case screenshot itself: a 7-column item table where BOTH
    # the item description and (on row 1 only) the "Ghi chú" note wrap onto extra
    # physical OCR lines, and row 2's "Ghi chú" is simply blank — three different ways
    # a row can fail to produce the same raw word-group count as the row before it,
    # all in one small table.
    from app.document_processing import _ocr_tables

    lines = [
        _cells_line(0, 0.10, [
            (*_STT, ["01"]),
            (*_NOIDUNG, ["Máy", "chủ", "ứng", "dụng", "rack", "2U;", "CPU", "16"]),
            (*_DVT, ["Bộ"]),
            (*_SL, ["2"]),
            (*_DONGIA, ["86.500.000"]),
            (*_THANHTIEN, ["173.000.000"]),
            (*_GHICHU, ["Bảo", "hành"]),
        ]),
        _cells_line(1, 0.12, [
            (*_STT, []),
            (*_NOIDUNG, ["nhân;", "RAM", "128", "GB;", "02", "nguồn", "dự", "phòng;",
                         "kèm", "thanh", "ray", "lắp", "tủ."]),
            (*_DVT, []), (*_SL, []), (*_DONGIA, []), (*_THANHTIEN, []),
            (*_GHICHU, ["36", "tháng"]),
        ]),
        _cells_line(2, 0.16, [
            (*_STT, ["02"]),
            (*_NOIDUNG, ["Thiết", "bị", "lưu", "trữ", "NAS", "8", "khay,", "dung"]),
            (*_DVT, ["Bộ"]),
            (*_SL, ["1"]),
            (*_DONGIA, ["74.800.000"]),
            (*_THANHTIEN, ["74.800.000"]),
            (*_GHICHU, []),
        ]),
        _cells_line(3, 0.18, [
            (*_STT, []),
            (*_NOIDUNG, ["lượng", "hữu", "dụng", "tối", "thiểu", "32", "TB", "sau"]),
            (*_DVT, []), (*_SL, []), (*_DONGIA, []), (*_THANHTIEN, []), (*_GHICHU, []),
        ]),
        _cells_line(4, 0.20, [
            (*_STT, []),
            (*_NOIDUNG, ["RAID;", "hỗ", "trợ", "snapshot", "và", "replication."]),
            (*_DVT, []), (*_SL, []), (*_DONGIA, []), (*_THANHTIEN, []), (*_GHICHU, []),
        ]),
        _cells_line(5, 0.24, [
            (*_STT, ["03"]),
            (*_NOIDUNG, ["Switch", "mạng", "24", "cổng", "1GbE", "+", "4"]),
            (*_DVT, ["Cái"]),
            (*_SL, ["3"]),
            (*_DONGIA, ["18.950.000"]),
            (*_THANHTIEN, ["56.850.000"]),
            (*_GHICHU, ["Serial", "ghi"]),
        ]),
        _cells_line(6, 0.26, [
            (*_STT, []),
            (*_NOIDUNG, ["cổng", "SFP+", "10GbE,", "quản", "trị", "L2/L3", "cơ", "bản."]),
            (*_DVT, []), (*_SL, []), (*_DONGIA, []), (*_THANHTIEN, []),
            (*_GHICHU, ["riêng"]),
        ]),
    ]

    tables = _ocr_tables(lines, {"document_id": "doc", "page_number": 1})

    assert len(tables) == 1
    table = tables[0]
    assert table["col_count"] == 7
    assert table["row_count"] == 3
    row0, row1, row2 = table["rows"]

    def text(row, col_index):
        return next(c["text"] for c in row["cells"] if c["col_index"] == col_index)

    assert text(row0, 0) == "01"
    assert text(row0, 1) == (
        "Máy chủ ứng dụng rack 2U; CPU 16 nhân; RAM 128 GB; 02 nguồn dự phòng; "
        "kèm thanh ray lắp tủ."
    )
    assert text(row0, 6) == "Bảo hành 36 tháng"
    assert text(row1, 0) == "02"
    assert text(row1, 1) == (
        "Thiết bị lưu trữ NAS 8 khay, dung lượng hữu dụng tối thiểu 32 TB sau "
        "RAID; hỗ trợ snapshot và replication."
    )
    assert not any(c["col_index"] == 6 for c in row1["cells"])  # blank Ghi chú stays blank
    assert text(row2, 0) == "03"
    assert text(row2, 1) == (
        "Switch mạng 24 cổng 1GbE + 4 cổng SFP+ 10GbE, quản trị L2/L3 cơ bản."
    )
    assert text(row2, 6) == "Serial ghi riêng"


def test_ocr_tables_keeps_a_row_whose_stt_landed_on_a_different_line():
    # Real hard case, found from actual Tesseract output (not a synthetic guess): a
    # row's own STT value routinely lands on a slightly different OCR "line" than the
    # rest of that row's first line (Hạng mục/Mô tả/SL/ĐVT/Đơn giá/Thành tiền), a
    # Tesseract line-segmentation artifact, not something table_reconstruct or
    # document_processing controls. Before the fix, requiring the STT cell
    # specifically to identify a new row meant such a row was rejected outright.
    from app.document_processing import _ocr_tables

    lines = [
        _cells_line(0, 0.10, [
            (*_STT, ["STT"]), (*_NOIDUNG, ["Ten", "hang"]), (*_DVT, ["DVT"]),
            (*_SL, ["SL"]), (*_DONGIA, ["Don", "gia"]), (*_THANHTIEN, ["Thanh", "tien"]),
        ]),
        _cells_line(1, 0.13, [
            (*_STT, ["1"]), (*_NOIDUNG, ["May", "chu", "ung", "dung"]),
            (*_DVT, ["Bo"]), (*_SL, ["2"]), (*_DONGIA, ["86.500.000"]), (*_THANHTIEN, ["173.000.000"]),
        ]),
        # Row 2's own STT ("2") never appears here or anywhere else on the page — an
        # exact real-world OCR miss, not merely "on a different line".
        _cells_line(2, 0.16, [
            (*_STT, []), (*_NOIDUNG, ["Thiet", "bi", "luu", "tru", "NAS"]),
            (*_DVT, ["Bo"]), (*_SL, ["1"]), (*_DONGIA, ["74.800.000"]), (*_THANHTIEN, ["74.800.000"]),
        ]),
        _cells_line(3, 0.19, [
            (*_STT, ["3"]), (*_NOIDUNG, ["Switch", "mang", "24", "port"]),
            (*_DVT, ["Cai"]), (*_SL, ["4"]), (*_DONGIA, ["4.055.000"]), (*_THANHTIEN, ["16.220.000"]),
        ]),
    ]

    tables = _ocr_tables(lines, {"document_id": "doc", "page_number": 1})

    assert len(tables) == 1
    table = tables[0]
    assert table["col_count"] == 6
    assert table["row_count"] == 4  # header + 3 data rows, all kept as ONE table

    def text(row, col_index):
        return next((c["text"] for c in row["cells"] if c["col_index"] == col_index), None)

    header, row1, row2, row3 = table["rows"]
    assert text(row1, 0) == "1"
    assert text(row2, 0) is None  # STT genuinely missing — never guessed at
    assert text(row2, 1) == "Thiet bi luu tru NAS"
    assert text(row2, 4) == "74.800.000"
    assert text(row3, 0) == "3"


def test_ocr_json_output_combines_a_headered_table_split_across_pages():
    # Full pipeline reconstruction of the real hard_case "bang_lien_trang" scenario:
    # per-page OCR table detection (_ocr_tables, including its wrapped-cell and
    # blank-cell tolerance) feeding into cross-page combining (build_logical_tables).
    # The final JSON the /tables API returns must show ONE combined table spanning
    # both pages, not two separate per-page fragments.
    from app.document_processing import _ocr_tables
    from app.tables import build_logical_tables

    page1_lines = [
        _cells_line(0, 0.10, [
            (*_STT, ["STT"]), (*_NOIDUNG, ["Ten", "hang"]), (*_DVT, ["DVT"]),
            (*_SL, ["SL"]), (*_DONGIA, ["Don", "gia"]), (*_THANHTIEN, ["Thanh", "tien"]),
            (*_GHICHU, ["Ghi", "chu"]),
        ]),
        _cells_line(1, 0.13, [
            (*_STT, ["01"]),
            (*_NOIDUNG, ["May", "chu", "ung", "dung", "rack", "2U;", "CPU", "16"]),
            (*_DVT, ["Bo"]), (*_SL, ["2"]), (*_DONGIA, ["86.500.000"]),
            (*_THANHTIEN, ["173.000.000"]), (*_GHICHU, ["Bao", "hanh"]),
        ]),
        _cells_line(2, 0.15, [
            (*_STT, []),
            (*_NOIDUNG, ["nhan;", "RAM", "128", "GB;", "02", "nguon", "du", "phong."]),
            (*_DVT, []), (*_SL, []), (*_DONGIA, []), (*_THANHTIEN, []),
            (*_GHICHU, ["36", "thang"]),
        ]),
        _cells_line(3, 0.18, [
            (*_STT, ["02"]),
            (*_NOIDUNG, ["Thiet", "bi", "luu", "tru", "NAS", "8", "khay"]),
            (*_DVT, ["Bo"]), (*_SL, ["1"]), (*_DONGIA, ["74.800.000"]),
            (*_THANHTIEN, ["74.800.000"]), (*_GHICHU, []),
        ]),
    ]
    page2_lines = [
        _cells_line(0, 0.10, [
            (*_STT, ["03"]), (*_NOIDUNG, ["Switch", "mang", "24", "cong", "1GbE"]),
            (*_DVT, ["Cai"]), (*_SL, ["3"]), (*_DONGIA, ["18.950.000"]),
            (*_THANHTIEN, ["56.850.000"]), (*_GHICHU, ["Serial"]),
        ]),
        _cells_line(1, 0.13, [
            (*_STT, ["04"]), (*_NOIDUNG, ["Goi", "trien", "khai", "ha", "tang"]),
            (*_DVT, ["Goi"]), (*_SL, ["1"]), (*_DONGIA, ["95.000.000"]),
            (*_THANHTIEN, ["95.000.000"]), (*_GHICHU, []),
        ]),
        _cells_line(2, 0.16, [
            (*_STT, ["05"]), (*_NOIDUNG, ["Cong", "thu", "vien"]),
            (*_DVT, ["Cai"]), (*_SL, ["1"]), (*_DONGIA, ["4.900.000"]),
            (*_THANHTIEN, ["4.900.000"]), (*_GHICHU, []),
        ]),
    ]

    page1_tables = _ocr_tables(page1_lines, {"document_id": "doc", "page_number": 1})
    page2_tables = _ocr_tables(page2_lines, {"document_id": "doc", "page_number": 2})
    assert len(page1_tables) == 1  # each page still detected as its own table fragment
    assert len(page2_tables) == 1

    result = build_logical_tables([page1_tables[0], page2_tables[0]])

    assert len(result) == 1  # combined into ONE table in the final JSON, not two
    table = result[0]
    assert table["status"] == "RECONSTRUCTED"
    assert (table["page_start"], table["page_end"]) == (1, 2)
    data_rows = [r for r in table["rows"] if r["kind"] == "data"]
    stts = [next(c["text"] for c in row["cells"] if c["col_index"] == 0) for row in data_rows]
    assert stts == ["01", "02", "03", "04", "05"]
    descriptions = [next(c["text"] for c in row["cells"] if c["col_index"] == 1) for row in data_rows]
    assert descriptions[0] == "May chu ung dung rack 2U; CPU 16 nhan; RAM 128 GB; 02 nguon du phong."


def test_ocr_json_output_combines_a_headerless_table_split_across_pages():
    # Real hard case (Hop_dong_scan_stress_bang_lien_trang_khong_header): neither page
    # has a recognizable header row at all — relies on tables.py's numbered-rows
    # fallback (_looks_like_numbered_rows) to bootstrap a grid without one.
    from app.document_processing import _ocr_tables
    from app.tables import build_logical_tables

    page1_lines = [
        _cells_line(0, 0.10, [
            (*_STT, ["01"]), (*_NOIDUNG, ["Bang", "phong", "Tu", "van"]),
            (*_DVT, ["Cai"]), (*_SL, ["4"]), (*_DONGIA, ["1.000.000"]),
            (*_THANHTIEN, ["4.000.000"]),
        ]),
        _cells_line(1, 0.13, [
            (*_STT, ["02"]), (*_NOIDUNG, ["Bang", "ten", "phong"]),
            (*_DVT, ["Cai"]), (*_SL, ["20"]), (*_DONGIA, ["100.000"]),
            (*_THANHTIEN, ["2.000.000"]),
        ]),
        _cells_line(2, 0.16, [
            (*_STT, ["03"]), (*_NOIDUNG, ["Bang", "khau", "hieu"]),
            (*_DVT, ["Cai"]), (*_SL, ["6"]), (*_DONGIA, ["2.000.000"]),
            (*_THANHTIEN, ["12.000.000"]),
        ]),
    ]
    page2_lines = [
        _cells_line(0, 0.10, [
            (*_STT, ["04"]), (*_NOIDUNG, ["Bang", "sinh", "hoat"]),
            (*_DVT, ["Cai"]), (*_SL, ["2"]), (*_DONGIA, ["1.500.000"]),
            (*_THANHTIEN, ["3.000.000"]),
        ]),
        _cells_line(1, 0.13, [
            (*_STT, ["05"]), (*_NOIDUNG, ["Cong", "thu", "vien"]),
            (*_DVT, ["Cai"]), (*_SL, ["1"]), (*_DONGIA, ["4.900.000"]),
            (*_THANHTIEN, ["4.900.000"]),
        ]),
        _cells_line(2, 0.16, [
            (*_STT, ["06"]), (*_NOIDUNG, ["Bang", "trang", "tri"]),
            (*_DVT, ["Cai"]), (*_SL, ["4"]), (*_DONGIA, ["2.000.000"]),
            (*_THANHTIEN, ["8.000.000"]),
        ]),
    ]

    page1_tables = _ocr_tables(page1_lines, {"document_id": "doc", "page_number": 1})
    page2_tables = _ocr_tables(page2_lines, {"document_id": "doc", "page_number": 2})
    assert len(page1_tables) == 1
    assert len(page2_tables) == 1

    result = build_logical_tables([page1_tables[0], page2_tables[0]])

    assert len(result) == 1  # combined, not left as two disconnected STANDALONE tables
    table = result[0]
    assert table["status"] == "RECONSTRUCTED"
    assert (table["page_start"], table["page_end"]) == (1, 2)
    stts = [next(c["text"] for c in row["cells"] if c["col_index"] == 0) for row in table["rows"]]
    assert stts == ["01", "02", "03", "04", "05", "06"]


def test_process_page_falls_back_to_ocr_tables_when_native_finds_none(tmp_path, monkeypatch):
    import io

    from PIL import Image

    import app.document_processing as processing

    image = Image.new("RGB", (1000, 1400), "white")
    png = io.BytesIO()
    image.save(png, format="PNG")
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=1000, height=1400)
        page.insert_image(page.rect, stream=png.getvalue())
        source = pdf.tobytes()
    store = ArtifactStore(tmp_path)
    payload = {
        "document_id": "doc",
        "role": "contract",
        "sha256": digest(source),
        "storage_key": store.put(source, "pdf"),
        "page_number": 1,
    }

    def mock_ocr(*args, **kwargs):
        rows = [
            (("Tháng", "10/2007-"), ("Làm", "việc"), ("Trung", "tâm"), ("Nghiên", "cứu")),
            (("Tháng", "9/2009-"), ("Học", "thạc"), ("Viện", "NC"), ("Học", "viên")),
            (("Tháng", "9/2010-"), ("Làm", "việc"), ("Trung", "tâm"), ("Nghiên", "cứu")),
        ]
        text, left, top, width, height, block_num, par_num, line_num = [], [], [], [], [], [], [], []
        col_x = [100, 400, 700, 900]
        for r, cells in enumerate(rows):
            for c, pair in enumerate(cells):
                x = col_x[c]
                for w in pair:
                    text.append(w)
                    left.append(x)
                    top.append(100 + r * 40)
                    width.append(35)
                    height.append(20)
                    block_num.append(1)
                    par_num.append(1)
                    line_num.append(r + 1)
                    x += 40
        return {
            "text": text, "left": left, "top": top, "width": width, "height": height,
            "block_num": block_num, "par_num": par_num, "line_num": line_num,
        }

    monkeypatch.setattr(processing.pytesseract, "image_to_data", mock_ocr)
    result = process_page(
        payload,
        {"dpi": 72, "max_pixels": 4_000_000, "ocr_languages": "vie+eng", "ocr_timeout_seconds": 5},
        store,
    )
    assert len(result["tables"]) == 1
    assert result["tables"][0]["row_count"] == 3
    assert result["tables"][0]["col_count"] == 4


def test_migration_on_empty_database(tmp_path):
    from pathlib import Path

    from sqlalchemy import create_engine, inspect

    database_url = f"sqlite:///{tmp_path / 'migration.db'}"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        env={**os.environ, "CI_DATABASE_URL": database_url},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    engine = create_engine(database_url)
    schema = json.loads(Path("migrations/versions/0001_schema.json").read_text())
    assert set(t["name"] for t in schema) <= set(inspect(engine).get_table_names())
    assert "analysis_revisions" in inspect(engine).get_table_names()
    engine.dispose()
