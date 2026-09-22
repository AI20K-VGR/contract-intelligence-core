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


def test_native_table_extraction_ignores_a_signature_block(tmp_path):
    # Real hard case: a scanned Vietnamese contract's own signature block ("ĐẠI DIỆN
    # BÊN A | ĐẠI DIỆN BÊN B" over "(Ký, ghi rõ họ tên và đóng dấu" x2), at the bottom
    # of virtually every page of a multi-page document, is exactly as grid-shaped as
    # a real 2x2 data table to PyMuPDF's own find_tables() -- and got detected as its
    # own spurious table on every single page it appeared on, polluting the review
    # UI with tables that carry no actual data.
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=600, height=800)
        x0, y0, col_w, row_h = 50, 50, 200, 30
        for r in range(3):
            page.draw_line((x0, y0 + r * row_h), (x0 + 2 * col_w, y0 + r * row_h))
        for c in range(3):
            page.draw_line((x0 + c * col_w, y0), (x0 + c * col_w, y0 + 2 * row_h))
        labels = [
            ["DAI DIEN BEN A", "DAI DIEN BEN B"],
            ["(Ky, ghi ro ho ten va dong dau", "(Ky, ghi ro ho ten va dong dau"],
        ]
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
    assert result["tables"] == []


def test_is_signature_block_recognizes_a_real_two_party_signature_row():
    from app.document_processing import _is_signature_block

    rows = [
        {"cells": [
            {"col_index": 0, "text": "ĐẠI DIỆN NHÀ CUNG CẤP HÀNG HÓA"},
            {"col_index": 1, "text": "ĐẠI DIỆN ĐƠN VỊ SỬ DỤNG NGÂN SÁCH"},
        ]},
        {"cells": [
            {"col_index": 0, "text": "(Ký, ghi rõ họ tên và đóng dấu"},
            {"col_index": 1, "text": "(Ký, ghi rõ họ tên và đóng dấu"},
        ]},
    ]

    assert _is_signature_block(rows) is True


def test_is_signature_block_rejects_a_real_data_row():
    # A real data row never has EVERY one of its cells open with "Đại diện"/"(" --
    # only one accidental match must not be enough to reject a genuine table.
    from app.document_processing import _is_signature_block

    rows = [
        {"cells": [
            {"col_index": 0, "text": "Khoản mục"},
            {"col_index": 1, "text": "(theo hợp đồng)"},  # one coincidental match
            {"col_index": 2, "text": "Số tiền"},
        ]},
        {"cells": [
            {"col_index": 0, "text": "Cọc"},
            {"col_index": 1, "text": "Đợt 1"},
            {"col_index": 2, "text": "10.000.000 VND"},
        ]},
    ]

    assert _is_signature_block(rows) is False


def test_native_table_extraction_ignores_a_sparse_noise_fragment(tmp_path):
    # Real hard case: a stray line (a barcode/serial number followed by a lone "."
    # a few pixels away) that PyMuPDF's own find_tables() grid-detection picked up as
    # a 1-row, 2-column table -- _plausible_row (the same noise guard _ocr_tables
    # already relies on for its own geometry-based detection) correctly recognizes
    # this has nowhere near enough real content to trust as a table row.
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=600, height=800)
        x0, y0, col_w, row_h = 50, 50, 200, 30
        page.draw_line((x0, y0), (x0 + 2 * col_w, y0))
        page.draw_line((x0, y0 + row_h), (x0 + 2 * col_w, y0 + row_h))
        page.draw_line((x0, y0), (x0, y0 + row_h))
        page.draw_line((x0 + col_w, y0), (x0 + col_w, y0 + row_h))
        page.draw_line((x0 + 2 * col_w, y0), (x0 + 2 * col_w, y0 + row_h))
        page.insert_text((x0 + 5, y0 + 20), "5007205033781")
        page.insert_text((x0 + col_w + 5, y0 + 20), ".")
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
    assert result["tables"] == []


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


def test_small_logo_alongside_native_text_stays_native(tmp_path, monkeypatch):
    import io

    from PIL import Image

    import app.document_processing as processing

    def fail_if_called(*args, **kwargs):
        raise AssertionError("OCR should not run: page has a full native text layer")

    monkeypatch.setattr(processing.pytesseract, "image_to_data", fail_if_called)
    logo = Image.new("RGB", (60, 40), "blue")
    png = io.BytesIO()
    logo.save(png, format="PNG")
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=600, height=800)
        page.insert_text((100, 150), "100.000.000 VND")
        # A corner logo covering a small fraction of the page (60x40 of 600x800,
        # ~0.5%) -- well under _SCAN_IMAGE_COVERAGE_THRESHOLD -- must not disqualify
        # the page's own real text layer from the fast native path.
        page.insert_image(pymupdf.Rect(10, 10, 70, 50), stream=png.getvalue())
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


def test_mostly_scanned_image_with_some_text_still_routes_to_ocr(tmp_path, monkeypatch):
    import io

    from PIL import Image

    import app.document_processing as processing

    called = []

    def mock_ocr(*args, **kwargs):
        called.append(kwargs)
        return {"text": []}

    monkeypatch.setattr(processing.pytesseract, "image_to_data", mock_ocr)
    scan = Image.new("RGB", (500, 700), "white")
    png = io.BytesIO()
    scan.save(png, format="PNG")
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=600, height=800)
        page.insert_text((100, 750), "Trang 1/1")
        # A scanned-looking image covering ~73% of the page: real scans, not a
        # decorative logo/stamp -- must still fall back to OCR even though the page
        # also carries a sliver of real native text (e.g. a stamped page number).
        page.insert_image(pymupdf.Rect(50, 50, 550, 700), stream=png.getvalue())
        source = pdf.tobytes()
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
    assert called
    assert result["engine"] == "tesseract"


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


def test_zero_area_tesseract_word_is_dropped_not_cited(tmp_path, monkeypatch):
    # Real failure mode: Tesseract occasionally reports a phantom word with width or
    # height 0 alongside real ones. Before clamping/filtering existed, that word's
    # degenerate bbox survived into page["lines"] untouched, and evidence.citation()
    # rejected it with CITATION_ANCHOR_INVALID -- failing the ENTIRE job (worker.py
    # builds every page's citations in one batch), not just the one page with the
    # stray word.
    import app.document_processing as processing

    def mock_ocr(*args, **kwargs):
        # "Ghost" is its own line (line_num=2): before the fix, its degenerate
        # zero-width bbox WAS the entire line's bbox, not just diluted into a wider
        # real line's min/max -- the exact shape that made citation() raise.
        return {
            "text": ["Hello", "Ghost"],
            "left": [10, 60],
            "top": [10, 30],
            "width": [40, 0],
            "height": [15, 15],
            "block_num": [1, 1],
            "par_num": [1, 1],
            "line_num": [1, 2],
        }

    monkeypatch.setattr(processing.pytesseract, "image_to_data", mock_ocr)
    store, payload = _scan_pdf_payload(tmp_path)
    result = process_page(
        payload, {"dpi": 72, "max_pixels": 2_000_000, "ocr_languages": "vie+eng",
                   "ocr_timeout_seconds": 5},
        store,
    )
    assert [line["text"] for line in result["lines"]] == ["Hello"]
    for line in result["lines"]:
        citation(result, line, "run")  # must not raise CITATION_ANCHOR_INVALID


def test_edge_overflowing_tesseract_word_is_clamped_not_rejected(tmp_path, monkeypatch):
    # Real failure mode: Tesseract's own internal padding can report a word extending
    # a few pixels past the rendered image's own edge, which -- without clamping --
    # normalizes to a coordinate above 1.0 and fails evidence.citation()'s bounds
    # check for the whole job, same as the zero-area case above.
    import app.document_processing as processing

    def mock_ocr(*args, **kwargs):
        return {
            "text": ["Edge"], "left": [190], "top": [10], "width": [20], "height": [15],
            "block_num": [1], "par_num": [1], "line_num": [1],
        }

    monkeypatch.setattr(processing.pytesseract, "image_to_data", mock_ocr)
    store, payload = _scan_pdf_payload(tmp_path)  # 200x100 page; dpi=72 keeps pix == page pixels
    result = process_page(
        payload, {"dpi": 72, "max_pixels": 2_000_000, "ocr_languages": "vie+eng",
                   "ocr_timeout_seconds": 5},
        store,
    )
    assert len(result["lines"]) == 1
    bbox = result["lines"][0]["bbox"]
    assert bbox[2] == 1.0
    assert bbox[0] < bbox[2]
    citation(result, result["lines"][0], "run")  # must not raise CITATION_ANCHOR_INVALID


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
    # _ocr_tables groups line["words"], never line["text"] -- GPT vision's better
    # reading (Vietnamese diacritics especially) only helps table cells if it lands
    # there too, not just in the line's own display string.
    assert [w["text"] for w in result["lines"][0]["words"]] == ["Xin", "chào"]
    assert [w["text"] for w in result["lines"][1]["words"]] == ["Tạm", "biệt"]
    # Word bbox is still Tesseract's own, unmoved by the text substitution.
    assert [w["bbox"] for w in result["lines"][0]["words"]] == \
        [w["bbox"] for w in baseline["lines"][0]["words"]]


def test_gpt_vision_word_mismatch_within_a_line_keeps_that_word_tesseracts(tmp_path, monkeypatch):
    # Same line-level match as above (2 lines both sides), but GPT's own transcription
    # of one line tokenizes differently (e.g. a compound word GPT wrote as one token
    # where Tesseract split it in two) -- no confident one-for-one correspondence
    # exists for that whole line at all (unequal lengths with no usable alignment), so
    # it falls back to Tesseract's own per-word text exactly as before word-level
    # substitution existed, rather than guessing which Tesseract word each GPT word
    # replaces. The line's own display text still gets GPT's (generally more
    # accurate) version regardless.
    import app.document_processing as processing

    monkeypatch.setattr(processing.pytesseract, "image_to_data", _mock_two_tesseract_lines)
    monkeypatch.setattr(processing, "_gpt_vision_lines", lambda image, config: ["HelloWorld", "Fizz Buzz"])
    store, payload = _scan_pdf_payload(tmp_path)
    result = process_page(
        payload,
        {"dpi": 100, "max_pixels": 2_000_000, "ocr_languages": "vie+eng", "ocr_timeout_seconds": 5,
         "ocr_engine": "gpt_vision"},
        store,
    )

    assert [line["text"] for line in result["lines"]] == ["HelloWorld", "Fizz Buzz"]
    # Line 1: GPT's single token vs Tesseract's two words -- no safe correspondence,
    # so the words stay Tesseract's own.
    assert [w["text"] for w in result["lines"][0]["words"]] == ["Hello", "World"]
    # Line 2: counts agree (2 vs 2) -- words DO get replaced, proving line 1's
    # fallback above is really about the mismatch, not that substitution never fires.
    assert [w["text"] for w in result["lines"][1]["words"]] == ["Fizz", "Buzz"]


def test_gpt_vision_recovers_aligned_words_despite_one_tesseract_missed_entirely(tmp_path, monkeypatch):
    # Real hard case (dossier 9f889e79, trang 2, dòng "09 Gói giám sát..."): Tesseract's
    # own line for an item row was missing its leading "09" entirely (swallowed into an
    # unrelated garbled line next to it, no bbox for it anywhere) while correctly
    # detecting the other 13 words -- two of which it still misread badly enough to
    # become meaningless English ("en", "lap" for "Không", "lặp"). A raw word-count
    # check (14 vs 13, purely because of GPT's extra leading "09") would trust NONE of
    # the 14 words over the one word the two sources disagree about the position of.
    # Alignment recovers the genuinely misread word ("World" -> "Cleaned" here) and
    # simply leaves the unmatched leading word ("Extra") unplaced, with no bbox to
    # give it, while an already-correct word ("Hello") is left as itself either way.
    import app.document_processing as processing

    monkeypatch.setattr(processing.pytesseract, "image_to_data", _mock_two_tesseract_lines)
    monkeypatch.setattr(
        processing, "_gpt_vision_lines", lambda image, config: ["Extra Hello Cleaned", "Foo Bar"],
    )
    store, payload = _scan_pdf_payload(tmp_path)
    result = process_page(
        payload,
        {"dpi": 100, "max_pixels": 2_000_000, "ocr_languages": "vie+eng", "ocr_timeout_seconds": 5,
         "ocr_engine": "gpt_vision"},
        store,
    )

    assert result["lines"][0]["text"] == "Extra Hello Cleaned"
    assert [w["text"] for w in result["lines"][0]["words"]] == ["Hello", "Cleaned"]


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


def test_gpt_vision_line_alignment_keeps_every_line_not_just_matched_ones(tmp_path, monkeypatch):
    # Real hard case: a line-count mismatch is common whenever GPT vision splits or
    # merges a table row's own multi-line description differently than Tesseract's
    # own line segmentation -- costing several genuine lines their confident match,
    # not just the odd stamp/watermark artifact _align_gpt_lines was designed
    # around. Dropping every unmatched Tesseract line entirely (the previous
    # behavior) silently lost real page text from BOTH "Toàn văn theo trang" and
    # _ocr_tables (which runs on this exact list). A line with no confident match
    # must still survive, just at its own original Tesseract text.
    import app.document_processing as processing

    def mock_ocr(*args, **kwargs):
        return {
            "text": ["Hello", "World", "Foo", "Bar", "Baz", "Qux"],
            "left": [10, 60, 10, 60, 10, 60],
            "top": [10, 10, 30, 30, 50, 50],
            "width": [40, 40, 30, 30, 30, 30],
            "height": [15, 15, 15, 15, 15, 15],
            "block_num": [1, 1, 1, 1, 1, 1],
            "par_num": [1, 1, 1, 1, 1, 1],
            "line_num": [1, 1, 2, 2, 3, 3],
        }

    monkeypatch.setattr(processing.pytesseract, "image_to_data", mock_ocr)
    monkeypatch.setattr(processing, "_gpt_vision_lines", lambda image, config: ["x", "y"])
    # Only the first of three Tesseract lines gets a confident alignment; lines 1 and
    # 2 simulate the common real case (GPT splitting/merging the rest of the page
    # differently than Tesseract's own line segmentation) rather than depending on
    # difflib's actual fuzzy-matching behavior, already covered elsewhere.
    monkeypatch.setattr(
        processing, "_align_gpt_lines", lambda tess, gpt: ({0: "Hello World"}, set())
    )
    store, payload = _scan_pdf_payload(tmp_path)
    result = process_page(
        payload,
        {"dpi": 100, "max_pixels": 2_000_000, "ocr_languages": "vie+eng", "ocr_timeout_seconds": 5,
         "ocr_engine": "gpt_vision"},
        store,
    )

    assert len(result["lines"]) == 3  # all three Tesseract lines survive
    assert result["lines"][0]["text"] == "Hello World"  # confidently matched: GPT's text
    assert result["lines"][1]["text"] == "Foo Bar"  # unmatched: kept at Tesseract's own text
    assert result["lines"][2]["text"] == "Baz Qux"  # unmatched: kept at Tesseract's own text
    assert result["issue"] is None


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


def test_mistral_vision_replaces_text_but_keeps_tesseract_bbox_on_line_match(tmp_path, monkeypatch):
    # Mirrors test_gpt_vision_replaces_text_but_keeps_tesseract_bbox_on_line_match --
    # same dispatch shape, different provider function/model label/engine tag. The
    # actual word/line alignment (_align_gpt_words/_align_gpt_lines) is unchanged,
    # provider-agnostic code already covered by the gpt_vision tests above; this
    # confirms the mistral_vision branch wires into it the same way, not that the
    # alignment algorithm itself works (already proven).
    import app.document_processing as processing

    monkeypatch.setattr(processing.pytesseract, "image_to_data", _mock_two_tesseract_lines)
    base_config = {
        "dpi": 100, "max_pixels": 2_000_000, "ocr_languages": "vie+eng", "ocr_timeout_seconds": 5,
    }
    store, payload = _scan_pdf_payload(tmp_path)
    baseline = process_page(payload, base_config, store)

    monkeypatch.setattr(processing, "_mistral_vision_lines", lambda image, config: ["Xin chào", "Tạm biệt"])
    store, payload = _scan_pdf_payload(tmp_path)
    result = process_page(
        payload, {**base_config, "ocr_engine": "mistral_vision", "ocr_mistral_model": "mistral-ocr-4"}, store,
    )

    assert [line["text"] for line in result["lines"]] == ["Xin chào", "Tạm biệt"]
    assert result["engine"] == "tesseract+mistral-ocr-4"
    assert result["status"] == "completed"
    assert result["issue"] is None
    assert [line["bbox"] for line in result["lines"]] == [line["bbox"] for line in baseline["lines"]]
    assert [w["text"] for w in result["lines"][0]["words"]] == ["Xin", "chào"]
    assert [w["text"] for w in result["lines"][1]["words"]] == ["Tạm", "biệt"]


def test_mistral_vision_falls_back_to_tesseract_text_on_line_count_mismatch(tmp_path, monkeypatch):
    import app.document_processing as processing

    monkeypatch.setattr(processing.pytesseract, "image_to_data", _mock_two_tesseract_lines)
    monkeypatch.setattr(processing, "_mistral_vision_lines", lambda image, config: ["Only one line"])
    store, payload = _scan_pdf_payload(tmp_path)
    result = process_page(
        payload,
        {"dpi": 100, "max_pixels": 2_000_000, "ocr_languages": "vie+eng", "ocr_timeout_seconds": 5,
         "ocr_engine": "mistral_vision"},
        store,
    )
    assert [line["text"] for line in result["lines"]] == ["Hello World", "Foo Bar"]
    assert result["engine"] == "tesseract"
    assert result["status"] == "needs_review"
    assert result["issue"] == "MISTRAL_VISION_LINE_COUNT_MISMATCH"


def test_mistral_vision_unavailable_falls_back_to_tesseract_text(tmp_path, monkeypatch):
    import app.document_processing as processing

    monkeypatch.setattr(processing.pytesseract, "image_to_data", _mock_two_tesseract_lines)
    monkeypatch.setattr(processing, "_mistral_vision_lines", lambda image, config: None)
    store, payload = _scan_pdf_payload(tmp_path)
    result = process_page(
        payload,
        {"dpi": 100, "max_pixels": 2_000_000, "ocr_languages": "vie+eng", "ocr_timeout_seconds": 5,
         "ocr_engine": "mistral_vision"},
        store,
    )
    assert [line["text"] for line in result["lines"]] == ["Hello World", "Foo Bar"]
    assert result["status"] == "needs_review"
    assert result["issue"] == "MISTRAL_VISION_UNAVAILABLE"


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

    matches, noise = _align_gpt_lines(tess, gpt)

    assert 2 not in matches  # the stamp-fragment line: no confident GPT counterpart
    assert 2 in noise  # ... because it has no counterpart in the alignment at all
    assert matches[0] == "Quận Liên Chiểu, Thành phố Đà Nẵng"
    assert matches[1].startswith("Số tài khoản")
    # The lines AFTER the dropped one still land on their true counterpart, not shifted:
    assert matches[3] == "KCN Hoà Khánh -Nam Đà Nẵng."
    assert matches[4].startswith("Điện thoại")
    assert matches[5].startswith("Mã số thuế")


def test_align_gpt_lines_distinguishes_noise_from_real_but_dissimilar_text():
    # Two very different reasons a line can end up unmatched, and the caller must
    # not treat them the same (see the reported bug: garbage like "2 _ ~ Z x 4 ^`"
    # surviving into "Toàn văn theo trang" because both cases were being kept).
    from app.document_processing import _align_gpt_lines

    tess = [
        "Alpha Beta Gamma",
        "x9 z7 q3 stamp noise blob",  # no GPT counterpart anywhere: pure noise
        "Delta Epsilon Zeta",
    ]
    gpt = [
        "Alpha Beta Gamma Real",
        "Delta Epsilon Zeta Real",
    ]

    matches, noise = _align_gpt_lines(tess, gpt)

    assert matches[0] == "Alpha Beta Gamma Real"
    assert matches[2] == "Delta Epsilon Zeta Real"
    assert noise == {1}  # only the noise line is flagged for dropping


def test_align_gpt_lines_keeps_real_content_the_order_constraint_cant_place():
    # A real Tesseract line can genuinely resemble a GPT line (0.70 similarity here)
    # that the alignment still can't confidently pair it with, because doing so would
    # violate the surrounding anchors' own order (GPT happened to transcribe this one
    # out of sequence relative to Tesseract). The noise check must look at the BEST
    # similarity against every GPT line, not just whatever this one global path
    # happened to align it with, or a real line like this would be wrongly dropped as
    # noise right alongside actual stamp/watermark garbage.
    from app.document_processing import _align_gpt_lines

    tess = [
        "Start Anchor One",
        "ambiguous middle content wording here",
        "Middle Anchor Two",
        "End Anchor Three",
    ]
    gpt = [
        "Start Anchor One",
        "Middle Anchor Two",
        "End Anchor Three",
        "ambiguous middle content phrased quite differently over here",
    ]

    matches, noise = _align_gpt_lines(tess, gpt)

    assert 1 not in matches  # not confidently placed by the order-constrained path
    assert 1 not in noise  # but not noise either: real resemblance exists elsewhere


def test_align_gpt_lines_no_confident_match_returns_empty():
    from app.document_processing import _align_gpt_lines

    matches, _noise = _align_gpt_lines(["Hello World", "Foo Bar"], ["Xin chào", "Tạm biệt"])
    assert matches == {}


def test_process_page_uses_alignment_when_gpt_vision_line_count_differs(tmp_path, monkeypatch):
    # "STAMP" has no counterpart anywhere in GPT's transcription (GPT read the page
    # as just two real lines, correctly leaving the stamp decoration out) -- see
    # _align_gpt_lines' docstring: a line with NO alignment counterpart at all is
    # dropped, not kept at its own garbled Tesseract text, since GPT vision is the
    # stronger signal that there's no real text there.
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


def test_parse_vision_table_rows_pads_ragged_rows_and_drops_bad_types():
    from app.document_processing import _parse_vision_table_rows, _rectangularize

    raw = json.dumps({"rows": [["STT", "Ten", "DVT"], ["1", "Item"], "not a row", ["2", "Item2", 3]]})
    rows = _parse_vision_table_rows(raw)
    # The malformed row ("not a row", a plain string) is dropped, not fatal to the rest.
    assert rows == [["STT", "Ten", "DVT"], ["1", "Item"], ["2", "Item2", None]]
    rectangular, col_count = _rectangularize(rows)
    assert col_count == 3
    assert rectangular == [["STT", "Ten", "DVT"], ["1", "Item", None], ["2", "Item2", None]]


def test_parse_vision_table_rows_returns_none_for_unusable_response():
    from app.document_processing import _parse_vision_table_rows

    assert _parse_vision_table_rows("not json at all") is None
    assert _parse_vision_table_rows(json.dumps({"cells": ["x"]})) is None
    assert _parse_vision_table_rows(json.dumps({"rows": "not a list"})) is None
    assert _parse_vision_table_rows(json.dumps({"rows": ["also not a list"]})) is None


def test_gpt_vision_table_recovers_a_column_ocr_tables_geometry_dropped(tmp_path, monkeypatch):
    # Real hard case (Hop_dong_scan_stress_bang_lien_trang_khong_header.pdf, trang 1):
    # _ocr_tables' column grid comes entirely from Tesseract's own word x-positions --
    # its ĐVT column's words sat close enough to a neighboring column's x-band that the
    # whole column silently vanished from every row (col_count 6 instead of 7).
    # Reconstructing straight from the vision model's own read of the table region,
    # instead of trusting that geometry, recovers the missing column.
    import app.document_processing as processing

    def mock_ocr(*args, **kwargs):
        # 3 rows x 3 well-separated word groups each -- enough for _ocr_tables to
        # detect one plain table, whatever its (here irrelevant) column count.
        text, left, top, width, line_num = [], [], [], [], []
        rows = [["1", "Item one", "100"], ["2", "Item two", "200"], ["3", "Item three", "300"]]
        for r, cells in enumerate(rows):
            # Include a small within-cell word gap so column boundaries are
            # distinguishable from uniformly spaced prose.
            for value, x, w in zip(
                [cells[0], *cells[1].split(), cells[2]], [10, 70, 100, 180], [25, 25, 25, 30]
            ):
                text.append(value)
                left.append(x)
                top.append(10 + r * 20)
                width.append(w)
                line_num.append(r)
        return {
            "text": text, "left": left, "top": top, "width": width,
            "height": [15] * len(text), "block_num": [1] * len(text),
            "par_num": [1] * len(text), "line_num": line_num,
        }

    monkeypatch.setattr(processing.pytesseract, "image_to_data", mock_ocr)
    monkeypatch.setattr(processing, "_gpt_vision_lines", lambda image, config: None)
    monkeypatch.setattr(
        processing,
        "_gpt_vision_table",
        lambda image, bbox, config: [
            ["STT", "Ten hang", "DVT", "So luong"],
            ["1", "Item one", "Cai", "100"],
            ["2", "Item two", "Bo", "200"],
            ["3", "Item three", "Goi", "300"],
        ],
    )
    store, payload = _scan_pdf_payload(tmp_path)
    result = process_page(
        payload,
        {"dpi": 100, "max_pixels": 2_000_000, "ocr_languages": "vie+eng", "ocr_timeout_seconds": 5,
         "ocr_engine": "gpt_vision"},
        store,
    )

    assert len(result["tables"]) == 1
    table = result["tables"][0]
    # Recovered the 4th column _ocr_tables' own geometry-based grid never had.
    assert table["col_count"] == 4
    assert table["row_count"] == 4
    assert [c["text"] for c in table["rows"][0]["cells"]] == ["STT", "Ten hang", "DVT", "So luong"]
    assert [c["text"] for c in table["rows"][2]["cells"]] == ["2", "Item two", "Bo", "200"]
    # Every cell's bbox is an even split of the table's region, not a real per-cell
    # detection -- marked "inferred" so tables.py skips citing it (see
    # _apply_gpt_vision_table), even though the text itself is fully trusted.
    assert all(c["inferred"] for row in table["rows"] for c in row["cells"])


def test_gpt_vision_table_unavailable_keeps_the_geometry_based_table(tmp_path, monkeypatch):
    import app.document_processing as processing

    def mock_ocr(*args, **kwargs):
        text, left, top, width, line_num = [], [], [], [], []
        rows = [["1", "Item one", "100"], ["2", "Item two", "200"], ["3", "Item three", "300"]]
        for r, cells in enumerate(rows):
            # Include a small within-cell word gap so column boundaries are
            # distinguishable from uniformly spaced prose.
            for value, x, w in zip(
                [cells[0], *cells[1].split(), cells[2]], [10, 70, 100, 180], [25, 25, 25, 30]
            ):
                text.append(value)
                left.append(x)
                top.append(10 + r * 20)
                width.append(w)
                line_num.append(r)
        return {
            "text": text, "left": left, "top": top, "width": width,
            "height": [15] * len(text), "block_num": [1] * len(text),
            "par_num": [1] * len(text), "line_num": line_num,
        }

    monkeypatch.setattr(processing.pytesseract, "image_to_data", mock_ocr)
    monkeypatch.setattr(processing, "_gpt_vision_lines", lambda image, config: None)
    monkeypatch.setattr(processing, "_gpt_vision_table", lambda image, bbox, config: None)
    store, payload = _scan_pdf_payload(tmp_path)
    result = process_page(
        payload,
        {"dpi": 100, "max_pixels": 2_000_000, "ocr_languages": "vie+eng", "ocr_timeout_seconds": 5,
         "ocr_engine": "gpt_vision"},
        store,
    )

    assert len(result["tables"]) == 1
    assert result["tables"][0]["col_count"] == 3
    assert not any(
        c["inferred"] for c in result["tables"][0]["rows"][0]["cells"]
    )


def test_parse_markdown_pipe_table_extracts_header_and_body_rows():
    from app.document_processing import _parse_markdown_pipe_table

    text = (
        "Some heading text before the table.\n\n"
        "|  STT | Ten hang | DVT |\n"
        "| --- | --- | --- |\n"
        "|  1 | Item one | Cai  |\n"
        "|  2 | Item two |   |\n\n"
        "Some trailing text after."
    )
    rows = _parse_markdown_pipe_table(text)
    assert rows == [
        ["STT", "Ten hang", "DVT"],
        ["1", "Item one", "Cai"],
        ["2", "Item two", ""],
    ]


def test_parse_markdown_pipe_table_returns_none_for_unusable_response():
    from app.document_processing import _parse_markdown_pipe_table

    assert _parse_markdown_pipe_table("just plain prose, no table here") is None
    # A line that merely contains "|" without a following separator row isn't a table.
    assert _parse_markdown_pipe_table("A | B\nC | D") is None


def test_mistral_vision_table_recovers_a_column_ocr_tables_geometry_dropped(tmp_path, monkeypatch):
    # Mirrors test_gpt_vision_table_recovers_a_column_ocr_tables_geometry_dropped.
    import app.document_processing as processing

    def mock_ocr(*args, **kwargs):
        text, left, top, width, line_num = [], [], [], [], []
        rows = [["1", "Item one", "100"], ["2", "Item two", "200"], ["3", "Item three", "300"]]
        for r, cells in enumerate(rows):
            # Include a small within-cell word gap so column boundaries are
            # distinguishable from uniformly spaced prose.
            for value, x, w in zip(
                [cells[0], *cells[1].split(), cells[2]], [10, 70, 100, 180], [25, 25, 25, 30]
            ):
                text.append(value)
                left.append(x)
                top.append(10 + r * 20)
                width.append(w)
                line_num.append(r)
        return {
            "text": text, "left": left, "top": top, "width": width,
            "height": [15] * len(text), "block_num": [1] * len(text),
            "par_num": [1] * len(text), "line_num": line_num,
        }

    monkeypatch.setattr(processing.pytesseract, "image_to_data", mock_ocr)
    monkeypatch.setattr(processing, "_mistral_vision_lines", lambda image, config: None)
    monkeypatch.setattr(
        processing,
        "_mistral_vision_table",
        lambda image, bbox, config: [
            ["STT", "Ten hang", "DVT", "So luong"],
            ["1", "Item one", "Cai", "100"],
            ["2", "Item two", "Bo", "200"],
            ["3", "Item three", "Goi", "300"],
        ],
    )
    store, payload = _scan_pdf_payload(tmp_path)
    result = process_page(
        payload,
        {"dpi": 100, "max_pixels": 2_000_000, "ocr_languages": "vie+eng", "ocr_timeout_seconds": 5,
         "ocr_engine": "mistral_vision"},
        store,
    )

    assert len(result["tables"]) == 1
    table = result["tables"][0]
    assert table["col_count"] == 4
    assert table["row_count"] == 4
    assert [c["text"] for c in table["rows"][0]["cells"]] == ["STT", "Ten hang", "DVT", "So luong"]
    assert [c["text"] for c in table["rows"][2]["cells"]] == ["2", "Item two", "Bo", "200"]
    assert all(c["inferred"] for row in table["rows"] for c in row["cells"])


def test_mistral_vision_table_unavailable_keeps_the_geometry_based_table(tmp_path, monkeypatch):
    import app.document_processing as processing

    def mock_ocr(*args, **kwargs):
        text, left, top, width, line_num = [], [], [], [], []
        rows = [["1", "Item one", "100"], ["2", "Item two", "200"], ["3", "Item three", "300"]]
        for r, cells in enumerate(rows):
            # Include a small within-cell word gap so column boundaries are
            # distinguishable from uniformly spaced prose.
            for value, x, w in zip(
                [cells[0], *cells[1].split(), cells[2]], [10, 70, 100, 180], [25, 25, 25, 30]
            ):
                text.append(value)
                left.append(x)
                top.append(10 + r * 20)
                width.append(w)
                line_num.append(r)
        return {
            "text": text, "left": left, "top": top, "width": width,
            "height": [15] * len(text), "block_num": [1] * len(text),
            "par_num": [1] * len(text), "line_num": line_num,
        }

    monkeypatch.setattr(processing.pytesseract, "image_to_data", mock_ocr)
    monkeypatch.setattr(processing, "_mistral_vision_lines", lambda image, config: None)
    monkeypatch.setattr(processing, "_mistral_vision_table", lambda image, bbox, config: None)
    store, payload = _scan_pdf_payload(tmp_path)
    result = process_page(
        payload,
        {"dpi": 100, "max_pixels": 2_000_000, "ocr_languages": "vie+eng", "ocr_timeout_seconds": 5,
         "ocr_engine": "mistral_vision"},
        store,
    )

    assert len(result["tables"]) == 1
    assert result["tables"][0]["col_count"] == 3
    assert not any(
        c["inferred"] for c in result["tables"][0]["rows"][0]["cells"]
    )


def test_split_markdown_into_segments_separates_text_and_table_in_order():
    from app.document_processing import _split_markdown_into_segments

    text = (
        "Heading line\n"
        "Intro line\n\n"
        "| STT | Ten |\n"
        "| --- | --- |\n"
        "| 1 | Item one |\n"
        "| 2 | Item two |\n\n"
        "Footer line"
    )
    segments = _split_markdown_into_segments(text)
    assert segments == [
        ("text", ["Heading line", "Intro line", ""]),
        ("table", [["STT", "Ten"], ["1", "Item one"], ["2", "Item two"]]),
        ("text", ["", "Footer line"]),
    ]


def test_split_markdown_into_segments_returns_one_text_segment_when_no_table():
    from app.document_processing import _split_markdown_into_segments

    segments = _split_markdown_into_segments("Just prose\nNo table here")
    assert segments == [("text", ["Just prose", "No table here"])]


def test_split_markdown_into_segments_extracts_every_table_on_the_page():
    # Real bug this guards against: an earlier version only ever extracted the FIRST
    # table block on a page, silently leaving a second table's own pipe-syntax as
    # unparsed "| a | b |" prose lines -- confirmed against a real test page with two
    # consecutive appendix tables separated by only a short intro line.
    from app.document_processing import _split_markdown_into_segments

    text = (
        "# Bang A (tiep)\n"
        "| STT | Ten |\n"
        "| --- | --- |\n"
        "| 1 | A |\n\n"
        "# Bang B\n"
        "Intro to table B.\n"
        "| STT | Ten |\n"
        "| --- | --- |\n"
        "| 1 | B |\n"
        "| 2 | B2 |\n"
        "Trang 3/4"
    )
    segments = _split_markdown_into_segments(text)
    kinds = [kind for kind, _ in segments]
    assert kinds == ["text", "table", "text", "table", "text"]
    assert segments[1] == ("table", [["STT", "Ten"], ["1", "A"]])
    assert segments[3] == ("table", [["STT", "Ten"], ["1", "B"], ["2", "B2"]])


def test_assemble_vision_only_page_splits_bbox_proportionally_and_marks_inferred():
    from app.document_processing import _assemble_vision_only_page

    payload = {"document_id": "doc", "page_number": 1}
    segments = [
        ("text", ["Heading", "Intro"]),
        ("table", [["STT", "Ten"], ["1", "Item one"], ["2", "Item two"]]),
        ("text", ["Footer"]),
    ]
    lines, tables = _assemble_vision_only_page(segments, payload)

    # 2 prose-before + 3 table rows + 1 prose-after = 6 even vertical slots.
    assert [line["text"] for line in lines] == ["Heading", "Intro", "Footer"]
    assert all(line["inferred"] for line in lines)
    assert lines[0]["bbox"] == [0.0, 0.0, 1.0, 1 / 6]
    assert lines[1]["bbox"] == [0.0, 1 / 6, 1.0, 2 / 6]
    assert lines[2]["bbox"] == [0.0, 5 / 6, 1.0, 1.0]  # "Footer" comes after the table's 3 slots

    assert len(tables) == 1
    table = tables[0]
    assert table["row_count"] == 3
    assert table["col_count"] == 2
    assert table["bbox"] == [0.0, 2 / 6, 1.0, 5 / 6]
    assert [c["text"] for c in table["rows"][0]["cells"]] == ["STT", "Ten"]
    assert [c["text"] for c in table["rows"][2]["cells"]] == ["2", "Item two"]
    assert all(c["inferred"] for row in table["rows"] for c in row["cells"])


def test_assemble_vision_only_page_with_no_table_is_just_evenly_split_lines():
    from app.document_processing import _assemble_vision_only_page

    payload = {"document_id": "doc", "page_number": 1}
    lines, tables = _assemble_vision_only_page([("text", ["A", "B", "C", "D"])], payload)
    assert tables == []
    assert [line["bbox"] for line in lines] == [
        [0.0, 0.0, 1.0, 0.25], [0.0, 0.25, 1.0, 0.5], [0.0, 0.5, 1.0, 0.75], [0.0, 0.75, 1.0, 1.0],
    ]


def test_assemble_vision_only_page_keeps_two_tables_on_the_same_page_separate():
    from app.document_processing import _assemble_vision_only_page

    payload = {"document_id": "doc", "page_number": 3}
    segments = [
        ("table", [["STT", "Ten"], ["1", "A"]]),
        ("text", ["Intro B"]),
        ("table", [["STT", "Ten"], ["1", "B"], ["2", "B2"]]),
    ]
    lines, tables = _assemble_vision_only_page(segments, payload)
    assert len(tables) == 2
    assert tables[0]["row_count"] == 2
    assert tables[1]["row_count"] == 3
    # The two tables must not overlap and must sit in page order.
    assert tables[0]["bbox"][3] <= tables[1]["bbox"][1]
    assert [line["text"] for line in lines] == ["Intro B"]


def test_mistral_block_bbox_normalizes_pixel_coordinates():
    from types import SimpleNamespace

    from app.document_processing import _mistral_block_bbox

    block = SimpleNamespace(top_left_x=100, top_left_y=50, bottom_right_x=300, bottom_right_y=150)
    assert _mistral_block_bbox(block, width=1000, height=500) == [0.1, 0.1, 0.3, 0.3]


def test_assemble_vision_only_page_from_blocks_uses_real_bbox_and_confidence():
    # mistral_vision_only's assembler -- unlike _assemble_vision_only_page (evenly
    # split slots, for gpt_vision_only which has no block-bbox API), every bbox here
    # comes straight from the block Mistral itself measured, no slot math at all.
    from app.document_processing import _assemble_vision_only_page_from_blocks

    payload = {"document_id": "doc", "page_number": 2}
    segments = [
        ("text", ["Title"], [0.1, 0.05, 0.9, 0.08], 0.99),
        ("table", [["STT", "Ten"], ["1", "A"], ["2", "B"]], [0.0, 0.15, 1.0, 0.9], 0.95),
    ]
    lines, tables = _assemble_vision_only_page_from_blocks(segments, payload)

    assert lines == [{
        "id": "doc:2:0", "text": "Title", "bbox": [0.1, 0.05, 0.9, 0.08], "confidence": 0.99,
    }]
    assert len(tables) == 1
    table = tables[0]
    assert table["bbox"] == [0.0, 0.15, 1.0, 0.9]  # the block's own real bbox, untouched
    assert table["confidence"] == 0.95
    assert table["row_count"] == 3
    # Cells have no real per-cell detection -- bbox is an even split WITHIN the
    # table's own real bbox, still marked "inferred".
    assert all(c["inferred"] for row in table["rows"] for c in row["cells"])
    assert table["rows"][0]["cells"][0]["bbox"][1] == 0.15  # top of the real table bbox
    assert table["rows"][-1]["cells"][0]["bbox"][3] == 0.9  # bottom of the real table bbox


def test_assemble_vision_only_page_from_blocks_multiline_text_block_shares_one_bbox():
    # Mistral's block granularity is paragraph-level, not per-visible-line -- every
    # line split from one "text" block shares that one block's real bbox/confidence,
    # since this API gives no finer geometry to split on.
    from app.document_processing import _assemble_vision_only_page_from_blocks

    payload = {"document_id": "doc", "page_number": 1}
    segments = [("text", ["Line one", "Line two"], [0.0, 0.2, 1.0, 0.4], 0.9)]
    lines, tables = _assemble_vision_only_page_from_blocks(segments, payload)
    assert tables == []
    assert [line["bbox"] for line in lines] == [[0.0, 0.2, 1.0, 0.4], [0.0, 0.2, 1.0, 0.4]]
    assert [line["confidence"] for line in lines] == [0.9, 0.9]


def test_process_page_mistral_vision_only_never_calls_tesseract(tmp_path, monkeypatch):
    import app.document_processing as processing

    def fail_if_called(*args, **kwargs):
        raise AssertionError("Tesseract must not be called in mistral_vision_only")

    monkeypatch.setattr(processing.pytesseract, "image_to_data", fail_if_called)
    monkeypatch.setattr(
        processing,
        "_mistral_vision_page",
        lambda image, config: [
            ("text", ["Heading"], [0.0, 0.0, 1.0, 0.1], 0.97),
            ("table", [["STT", "Ten"], ["1", "Item one"]], [0.0, 0.1, 1.0, 0.6], 0.99),
            ("text", ["Footer"], [0.0, 0.9, 1.0, 1.0], 0.95),
        ],
    )
    store, payload = _scan_pdf_payload(tmp_path)
    result = process_page(
        payload,
        {"dpi": 100, "max_pixels": 2_000_000, "ocr_languages": "vie+eng", "ocr_timeout_seconds": 5,
         "ocr_engine": "mistral_vision_only", "ocr_mistral_model": "mistral-ocr-4"},
        store,
    )

    assert result["engine"] == "vision_only+mistral-ocr-4"
    assert result["status"] == "completed"
    assert result["issue"] is None
    assert [line["text"] for line in result["lines"]] == ["Heading", "Footer"]
    # Real (measured) bbox/confidence from the block, not the old evenly-split
    # "inferred" scheme -- each line carries its own source block's real values.
    assert result["lines"][0]["bbox"] == [0.0, 0.0, 1.0, 0.1]
    assert result["lines"][0]["confidence"] == 0.97
    assert result["lines"][1]["bbox"] == [0.0, 0.9, 1.0, 1.0]
    assert result["lines"][1]["confidence"] == 0.95
    assert len(result["tables"]) == 1
    assert result["tables"][0]["row_count"] == 2
    assert result["tables"][0]["bbox"] == [0.0, 0.1, 1.0, 0.6]
    assert result["tables"][0]["confidence"] == 0.99
    # Table cells still have no real per-cell detection -- bbox stays an even split
    # WITHIN the table's own now-real bbox, still marked "inferred".
    assert all(c["inferred"] for row in result["tables"][0]["rows"] for c in row["cells"])


def test_process_page_mistral_vision_only_unavailable_is_empty_ocr_needs_review(tmp_path, monkeypatch):
    import app.document_processing as processing

    monkeypatch.setattr(processing.pytesseract, "image_to_data", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("Tesseract must not be called")
    ))
    monkeypatch.setattr(processing, "_mistral_vision_page", lambda image, config: None)
    store, payload = _scan_pdf_payload(tmp_path)
    result = process_page(
        payload,
        {"dpi": 100, "max_pixels": 2_000_000, "ocr_languages": "vie+eng", "ocr_timeout_seconds": 5,
         "ocr_engine": "mistral_vision_only"},
        store,
    )

    assert result["lines"] == []
    assert result["tables"] == []
    assert result["status"] == "needs_review"
    # No Tesseract fallback exists in this mode, so the specific provider-unavailable
    # issue survives the generic EMPTY_OCR_REQUIRES_REVIEW check rather than being
    # masked by it (see process_page's own comment on this precedence).
    assert result["issue"] == "MISTRAL_VISION_UNAVAILABLE"


def test_process_page_gpt_vision_only_wires_lines_and_table(tmp_path, monkeypatch):
    import app.document_processing as processing

    def fail_if_called(*args, **kwargs):
        raise AssertionError("Tesseract must not be called in gpt_vision_only")

    monkeypatch.setattr(processing.pytesseract, "image_to_data", fail_if_called)
    monkeypatch.setattr(processing, "_gpt_vision_lines", lambda image, config: ["Heading", "Footer"])
    monkeypatch.setattr(
        processing, "_gpt_vision_page_table",
        lambda image, config: [["STT", "Ten"], ["1", "Item one"]],
    )
    store, payload = _scan_pdf_payload(tmp_path)
    result = process_page(
        payload,
        {"dpi": 100, "max_pixels": 2_000_000, "ocr_languages": "vie+eng", "ocr_timeout_seconds": 5,
         "ocr_engine": "gpt_vision_only", "ocr_vision_model": "gpt-5.6-terra"},
        store,
    )

    assert result["engine"] == "vision_only+gpt-5.6-terra"
    assert result["status"] == "completed"
    # GPT's own no-markdown transcription never embeds the table inline, so there is
    # no known insertion point within the prose -- the table is placed after every
    # prose line (see process_page's gpt_vision_only dispatch), unlike Mistral's
    # exact before/after split from the same markdown response.
    assert [line["text"] for line in result["lines"]] == ["Heading", "Footer"]
    assert len(result["tables"]) == 1
    assert [c["text"] for c in result["tables"][0]["rows"][0]["cells"]] == ["STT", "Ten"]


def test_clean_vision_markdown_text_strips_artifacts_without_losing_real_content():
    # Real cases confirmed against an actual scanned test page's Mistral OCR output:
    # a "# " heading prefix silently broke structure.py's ^-anchored ARTICLE_PATTERN
    # (a page-full of "# DIEU 1. ..." headings never formed a clause tree at all), and
    # a payment percentage came back LaTeX-escaped, corrupting a legally meaningful
    # number.
    from app.document_processing import _clean_vision_markdown_text

    assert _clean_vision_markdown_text("# DIEU 1. NOI DUNG") == "DIEU 1. NOI DUNG"
    assert _clean_vision_markdown_text("### Ghi chu:") == "Ghi chu:"
    assert _clean_vision_markdown_text(r"1. Dot 1: \(30\%\) sau khi ky.") == "1. Dot 1: 30% sau khi ky."
    assert _clean_vision_markdown_text("**TAM TINH BANG B**") == "TAM TINH BANG B"
    assert _clean_vision_markdown_text("![img-0.jpeg](img-0.jpeg)") == "[image: img-0.jpeg]"
    # Only a "#" at the very start of the line, followed by a space, is treated as a
    # Markdown heading marker -- a mid-line "#" (real content, e.g. a reference
    # number) is untouched.
    assert _clean_vision_markdown_text("Ma so #5") == "Ma so #5"
    assert _clean_vision_markdown_text("#5 khong co khoang trang") == "#5 khong co khoang trang"
    # Ordinary prose with no artifacts passes through unchanged (aside from trimming).
    assert _clean_vision_markdown_text("  Hom nay, ngay 20 thang 09  ") == "Hom nay, ngay 20 thang 09"


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


def test_row_cells_splits_a_misread_ruling_line_out_of_the_last_column():
    # Same real hard case as the threshold test above (Hop_dong_scan_stress_bang_
    # lien_trang_khong_header.pdf, trang 1, dong "01 |May chu ung dung..."): the
    # table's own vertical rule between "Thành tiền" and "Ghi chú" gets OCR'd as a
    # standalone "|" word sitting only ~0.002-0.006 from both real neighbors -- far
    # closer than any genuine word-spacing gap elsewhere in the row. Fixing the
    # THRESHOLD (see above) correctly locks onto the row's real column boundaries, but
    # by the same token it's now too small to separate "173.000.000" from "|" or "|"
    # from "Bảo" either -- all three land in one _column_gap_threshold-sized group.
    # Left alone, that group's text becomes "173.000.000 | Bảo hành" -- Thành tiền
    # and Ghi chú silently fused into one cell -- for every row that happens to carry
    # a Ghi chú value, on every affected page.
    from app.document_processing import _row_cells

    words = [
        _word("01", 0.0548, 0.401, 0.0758, 0.4116),
        _word("|Máy", 0.0996, 0.4011, 0.1355, 0.4145),
        _word("chủ", 0.1431, 0.4014, 0.1742, 0.4116),
        _word("2", 0.5847, 0.4025, 0.5935, 0.4125),
        _word("86.500.000", 0.6375, 0.4019, 0.7238, 0.4105),
        _word("173.000.000", 0.7722, 0.4025, 0.8673, 0.4108),
        _word("|", 0.8694, 0.4002, 0.8782, 0.4185),
        _word("Bảo", 0.8839, 0.4014, 0.9069, 0.4094),
        _word("hành", 0.9125, 0.4017, 0.9431, 0.4173),
    ]
    line = _ocr_line(0, words)

    cells = _row_cells(line)

    assert [c["text"] for c in cells] == [
        "01", "|Máy chủ", "2", "86.500.000", "173.000.000", "Bảo hành",
    ]


def test_align_gpt_words_returns_trailing_extra_gpt_only_words():
    # Symmetric real hard case to the leading-word one above: a row's "Đơn giá" and
    # "Thành tiền" were both a plain "0" printed so faintly Tesseract's own OCR pass
    # produced no word box for either -- GPT vision (built to transcribe, not merely
    # detect ink) still read them. They land as an "insert" at the very END of the
    # alignment, not the start, so leading_extra must stay empty while trailing_extra
    # picks them up.
    from app.document_processing import _align_gpt_words

    tess_words = ["30", "Ho", "tro", "nghiem", "thu", "Goi", "1"]
    gpt_words = ["30", "Hỗ", "trợ", "nghiệm", "thu", "Gói", "1", "0", "0"]

    mapping, leading_extra, trailing_extra = _align_gpt_words(tess_words, gpt_words)

    assert leading_extra == ""
    assert trailing_extra == "0 0"
    assert mapping[5] == "Gói"  # ordinary word substitution still happens either side


def test_align_gpt_words_single_insert_is_leading_not_also_trailing():
    # Edge case: Tesseract found NO words at all on this line (n=0) while GPT read
    # some. The single "insert" opcode covering the whole gpt list starts at position
    # 0 (satisfying the leading check) and also ends at len(tess_words)==0 (satisfying
    # the trailing check) -- it must be reported once, as leading_extra, not counted
    # again as trailing_extra for the exact same words.
    from app.document_processing import _align_gpt_words

    mapping, leading_extra, trailing_extra = _align_gpt_words([], ["Hỗ", "trợ"])

    assert leading_extra == "Hỗ trợ"
    assert trailing_extra == ""
    assert mapping == {}


def test_row_cells_recovers_gpt_only_trailing_numbers_tesseract_never_boxed():
    # Real hard case: this row's own "Đơn giá"/"Thành tiền" cells were both a plain
    # "0" Tesseract detected no ink for at all -- see _align_gpt_words. Without
    # recovery, _row_cells would silently return a row 2 columns short, and if this
    # happens to be the block's FIRST row (as it was for real), the table's own
    # reference would permanently lack those two columns with no later mechanism able
    # to notice: _extend_reference_with_confirming_row only ever adds a column a
    # LATER row proves exists, and this row's own values would already be gone.
    from app.document_processing import _row_cells

    line = _cells_line(0, 0.10, [
        (*_STT, ["30"]), (*_NOIDUNG, ["Ho", "tro", "nghiem", "thu"]),
        (*_DVT, ["Goi"]), (*_SL, ["1"]),
    ])
    line["trailing_gpt_text"] = "0 0"

    cells = _row_cells(line)

    assert [c["text"] for c in cells] == ["30", "Ho tro nghiem thu", "Goi", "1", "0", "0"]
    assert [c.get("inferred", False) for c in cells] == [False, False, False, False, True, True]
    # The borrowed bbox comes from the last REAL cell ("1"), not a guessed position:
    assert cells[4]["bbox"] == cells[3]["bbox"]
    assert cells[5]["bbox"] == cells[3]["bbox"]


def test_row_cells_ignores_trailing_extra_that_isnt_number_shaped():
    # An insert at the end that ISN'T number-shaped is far more likely a genuine
    # alignment ambiguity (words split differently between the two sources) than a
    # lost numeric cell -- left alone, matching the existing behavior for any other
    # non-leading, non-trailing-numeric insert.
    from app.document_processing import _row_cells

    line = _cells_line(0, 0.10, [
        (*_STT, ["30"]), (*_NOIDUNG, ["Ho", "tro", "nghiem", "thu"]),
        (*_DVT, ["Goi"]), (*_SL, ["1"]),
    ])
    line["trailing_gpt_text"] = "khong tinh"

    cells = _row_cells(line)

    assert [c["text"] for c in cells] == ["30", "Ho tro nghiem thu", "Goi", "1"]


def test_plausible_row_ignores_inferred_trailing_cells():
    # _append_trailing_gpt_numbers can add cells whose own text is a single short
    # digit ("0") -- exactly the shape _plausible_row exists to be suspicious of.
    # They must not count against a row that would otherwise clear the bar on its
    # real (non-inferred) cells alone, or a row simply being MORE complete than
    # before would get it rejected as implausible.
    from app.document_processing import _plausible_row

    real_only = [
        {"text": "30 Ho tro nghiem thu", "bbox": [0, 0, 1, 1]},
        {"text": "Goi", "bbox": [0, 0, 1, 1]},
        {"text": "1", "bbox": [0, 0, 1, 1]},
    ]
    assert _plausible_row(real_only) is True

    with_inferred_trailing = [
        *real_only,
        {"text": "0", "bbox": [0, 0, 1, 1], "inferred": True},
        {"text": "0", "bbox": [0, 0, 1, 1], "inferred": True},
    ]
    assert _plausible_row(with_inferred_trailing) is True


def test_summary_row_cells_parses_space_tab_and_no_separator_forms():
    # GPT vision renders this same merged label+amount cell with a space, a tab, or --
    # observed on a real dossier, non-deterministically even across identical
    # reprocessing runs of the very same page -- NO separator at all. All three must
    # resolve to the same (label, amount) split.
    from app.document_processing import _summary_row_cells

    reference = [
        {"col_index": 0, "text": "Nội dung", "bbox": [0.05, 0.1, 0.5, 0.12]},
        {"col_index": 1, "text": "Thành tiền", "bbox": [0.8, 0.1, 0.95, 0.12]},
    ]

    for text in (
        "CỘNG TRƯỚC THUẾ 1.116.230.000",
        "CỘNG TRƯỚC THUẾ\t1.116.230.000",
        "CỘNG TRƯỚC THUẾ1.116.230.000",
    ):
        line = {"text": text, "bbox": [0.05, 0.3, 0.95, 0.32]}
        cells = _summary_row_cells(line, reference)
        assert cells is not None, text
        by_col = {c["col_index"]: c["text"] for c in cells}
        assert by_col == {0: "CỘNG TRƯỚC THUẾ", 1: "1.116.230.000"}
        assert all(c["inferred"] for c in cells)


def test_summary_row_cells_rejects_a_label_without_a_recognized_keyword():
    # A generic "label + trailing number" line must NOT be treated as a summary row --
    # only the handful of labels a Vietnamese commercial contract's value table
    # actually ends on (see _SUMMARY_ROW_PATTERN). Otherwise an ordinary one-line
    # sentence that happens to end in a number (a date, a serial, a section ref)
    # would be silently absorbed as if it were a subtotal/tax/total row.
    from app.document_processing import _summary_row_cells

    reference = [
        {"col_index": 0, "text": "Nội dung", "bbox": [0.05, 0.1, 0.5, 0.12]},
        {"col_index": 1, "text": "Thành tiền", "bbox": [0.8, 0.1, 0.95, 0.12]},
    ]
    line = {"text": "Hợp đồng có hiệu lực từ ngày 20", "bbox": [0.05, 0.3, 0.95, 0.32]}

    assert _summary_row_cells(line, reference) is None


def test_summary_row_cells_requires_a_reference():
    from app.document_processing import _summary_row_cells

    line = {"text": "TỔNG CỘNG 1.227.853.000", "bbox": [0.05, 0.3, 0.95, 0.32]}

    assert _summary_row_cells(line, None) is None


def test_ocr_tables_recovers_a_column_the_reference_row_left_blank():
    # Real hard case (a scanned "Khối lượng/Đơn giá/Thành tiền" item table): the
    # table's very first item legitimately has no value in its own "Khối lượng"
    # (quantity) column at all -- a genuinely blank field, not a missed OCR read.
    # Before this fix, the reference row (built from that first item alone) never
    # gained a column for "Khối lượng" to begin with, so EVERY other row's own
    # quantity value had nothing to overlap and was silently dropped as noise (see
    # _matching_cells) -- the whole column vanished from the reconstructed table,
    # not merely its first (blank) cell.
    from app.document_processing import _ocr_tables

    lines = [
        _cells_line(0, 0.10, [
            (0.05, 0.55, ["Khao", "sat", "hien", "trang"]),
            (0.58, 0.62, ["goi"]),
            (0.65, 0.68, []),  # Khối lượng genuinely blank on the reference row
            (0.70, 0.80, ["4.850.000"]),
            (0.82, 0.92, ["4.850.000"]),
        ]),
        _cells_line(1, 0.14, [
            (0.05, 0.55, ["Lap", "dat", "tu", "dieu", "khien"]),
            (0.58, 0.62, []),
            (0.65, 0.68, ["2"]),
            (0.70, 0.80, ["8.750.000"]),
            (0.82, 0.92, ["17.500.000"]),
        ]),
        _cells_line(2, 0.18, [
            (0.05, 0.55, ["Cap", "tin", "hieu", "chong", "nhieu"]),
            (0.58, 0.62, []),
            (0.65, 0.68, []),
            (0.70, 0.80, ["42.000"]),
            (0.82, 0.92, ["7.791.000"]),
        ]),
    ]

    tables = _ocr_tables(lines, {"document_id": "doc", "page_number": 1})

    assert len(tables) == 1
    table = tables[0]
    assert table["col_count"] == 5
    assert table["row_count"] == 3

    def cell_text(row, col_index):
        return next((c["text"] for c in row["cells"] if c["col_index"] == col_index), "")

    # Column order by x-position: Hạng mục(0), ĐVT(1), Khối lượng(2), Đơn giá(3),
    # Thành tiền(4) — Khối lượng takes its rightful place between ĐVT and Đơn giá,
    # not appended after Thành tiền.
    assert cell_text(table["rows"][0], 2) == ""  # row 0's own Khối lượng genuinely blank
    assert cell_text(table["rows"][0], 1) == "goi"
    assert cell_text(table["rows"][0], 3) == "4.850.000"
    assert cell_text(table["rows"][0], 4) == "4.850.000"
    assert cell_text(table["rows"][1], 2) == "2"
    assert cell_text(table["rows"][1], 3) == "8.750.000"
    assert cell_text(table["rows"][1], 4) == "17.500.000"
    assert cell_text(table["rows"][2], 3) == "42.000"
    assert cell_text(table["rows"][2], 4) == "7.791.000"


def test_ocr_tables_requires_minimum_consecutive_rows():
    from app.document_processing import _ocr_tables

    # Mid-page (not near either edge): the page-edge exception (see the next test)
    # must not rescue this — only two rows, nowhere near _OCR_TABLE_MIN_ROWS, with
    # nothing about the position suggesting a table continuing across a page break.
    lines = [
        _work_history_row(0, 0.45, ("Tháng", "10/2007-"), ("Làm", "việc"),
                           ("Trung", "tâm"), ("Nghiên", "cứu")),
        _work_history_row(1, 0.49, ("Tháng", "9/2009-"), ("Học", "thạc"),
                           ("Viện", "NC"), ("Học", "viên")),
    ]

    assert _ocr_tables(lines, {"document_id": "doc", "page_number": 1}) == []


def test_ocr_tables_rescues_a_short_block_at_the_page_top_as_low_confidence():
    # Real hard case (a table's last item spilling onto the next page as a single
    # extra numbered row, with nothing else tabular on that page): too few rows to
    # ever reach _OCR_TABLE_MIN_ROWS on its own, so it was silently dropped entirely
    # -- losing that row from the reconstructed table, not just misplacing it. Now
    # emitted (flagged low_confidence) so build_logical_tables' Table Continuity
    # Agent gets a chance to decide whether it belongs to the previous page's table,
    # rather than never seeing it at all.
    from app.document_processing import _ocr_tables

    lines = [
        _work_history_row(0, 0.03, ("Tháng", "10/2007-"), ("Làm", "việc"),
                           ("Trung", "tâm"), ("Nghiên", "cứu")),
        _work_history_row(1, 0.07, ("Tháng", "9/2009-"), ("Học", "thạc"),
                           ("Viện", "NC"), ("Học", "viên")),
    ]

    tables = _ocr_tables(lines, {"document_id": "doc", "page_number": 1})

    assert len(tables) == 1
    assert tables[0]["row_count"] == 2
    assert tables[0]["low_confidence"] is True


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


def test_row_from_reference_overlap_recognizes_a_row_that_failed_self_segmentation():
    # Real hard case (Hop_dong_scan_stress_bang_lien_trang_khong_header.pdf, trang 2):
    # a row whose own internal word spacing was too compressed/inconsistent for
    # _row_cells to split it into cells at all still plainly covers most of an
    # already-established table's own columns. Before this fallback existed, such a
    # line fell straight through to _merge_wrapped_continuation, which welded its
    # values onto the PREVIOUS row instead of becoming a row of its own -- two real
    # items collapsed into one garbled row, with the second item's own SL/Đơn giá/
    # Thành tiền values concatenated onto the first item's.
    from app.document_processing import _row_from_reference_overlap

    reference = [
        {"col_index": 0, "text": "11", "bbox": [0.05, 0.10, 0.07, 0.12]},
        {"col_index": 1, "text": "Thiết bị UPS online 3KVA", "bbox": [0.10, 0.10, 0.55, 0.12]},
        {"col_index": 2, "text": "Bộ", "bbox": [0.58, 0.10, 0.62, 0.12]},
        {"col_index": 3, "text": "19.750.000", "bbox": [0.65, 0.10, 0.75, 0.12]},
        {"col_index": 4, "text": "39.500.000", "bbox": [0.78, 0.10, 0.88, 0.12]},
    ]
    line = _ocr_line(0, [
        _word("12", 0.10, 0.14, 0.115, 0.16),
        _word("Tủ", 0.12, 0.14, 0.14, 0.16),
        _word("rack", 0.145, 0.14, 0.20, 0.16),
        _word("27U", 0.205, 0.14, 0.25, 0.16),
        _word("14.900.000", 0.66, 0.14, 0.73, 0.16),
        _word("29.800.000", 0.79, 0.14, 0.86, 0.16),
    ])

    result = _row_from_reference_overlap(reference, line)

    assert result is not None
    by_col = {c["col_index"]: c["text"] for c in result}
    assert by_col[1] == "12 Tủ rack 27U"
    assert by_col[3] == "14.900.000"
    assert by_col[4] == "29.800.000"


def test_row_from_reference_overlap_rejects_a_line_with_no_internal_gap_structure():
    # Real hard case (Hop_dong_scan_testcase_bang_dut_doan_con_dau_v2.pdf, trang 4): an
    # entirely unrelated paragraph sitting below a narrow (3-column) table can have one
    # of its own words coincidentally land inside a price column purely by chance, with
    # NOTHING in the line's own geometry (ordinary, uniformly-spaced prose -- a single
    # _raw_word_groups group) suggesting it's table-shaped at all. Relying on
    # reference-column overlap alone for that is what glued an unrelated "Ghi chú kiểm
    # thử" paragraph onto a real row in practice.
    from app.document_processing import _row_from_reference_overlap

    reference = [
        {"col_index": 0, "text": "Kiểm thử bộ dữ liệu mẫu", "bbox": [0.05, 0.10, 0.55, 0.12]},
        {"col_index": 1, "text": "14.500.000", "bbox": [0.60, 0.10, 0.70, 0.12]},
        {"col_index": 2, "text": "14.500.000", "bbox": [0.73, 0.10, 0.83, 0.12]},
    ]
    # 16 evenly-spaced words (uniform gap throughout -- no internal column structure
    # at all); word #15 drifts into the reference's own col1 x-range purely from
    # accumulated width, the same way an unrelated sentence can coincidentally reach a
    # price column just by running long enough.
    words = [_word(f"w{i}", 0.05 + i * 0.036, 0.14, 0.05 + i * 0.036 + 0.03, 0.16) for i in range(16)]
    line = _ocr_line(0, words)

    assert _row_from_reference_overlap(reference, line) is None


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


def test_ocr_tables_recovers_a_missing_stt_from_gpt_visions_leading_word():
    # Same real hard case as the test above (STT genuinely absent from Tesseract's own
    # word list, not merely misplaced), but now GPT vision's own re-transcription of
    # that line DID read the STT digit — process_page recorded it as
    # line["leading_gpt_text"] because it had no Tesseract bbox to attach to (see
    # _align_gpt_words). Unlike the test above, this row's identity should NOT stay
    # blank: the table's own already-established STT column position (from row 1 and
    # row 3) is a principled place to put it, not a guess from this row's own
    # (nonexistent) geometry.
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
        _cells_line(2, 0.16, [
            (*_STT, []), (*_NOIDUNG, ["Thiet", "bi", "luu", "tru", "NAS"]),
            (*_DVT, ["Bo"]), (*_SL, ["1"]), (*_DONGIA, ["74.800.000"]), (*_THANHTIEN, ["74.800.000"]),
        ]),
        _cells_line(3, 0.19, [
            (*_STT, ["3"]), (*_NOIDUNG, ["Switch", "mang", "24", "port"]),
            (*_DVT, ["Cai"]), (*_SL, ["4"]), (*_DONGIA, ["4.055.000"]), (*_THANHTIEN, ["16.220.000"]),
        ]),
    ]
    lines[2]["leading_gpt_text"] = "2"

    tables = _ocr_tables(lines, {"document_id": "doc", "page_number": 1})

    assert len(tables) == 1
    table = tables[0]

    def text(row, col_index):
        return next((c["text"] for c in row["cells"] if c["col_index"] == col_index), None)

    row2 = table["rows"][2]
    assert text(row2, 0) == "2"
    stt_cell = next(c for c in row2["cells"] if c["col_index"] == 0)
    # Borrowed bbox: the reference's own STT column x-range, this row's own y-range —
    # not a real detection, an inherited position.
    reference_stt_x = next(c for c in table["rows"][0]["cells"] if c["col_index"] == 0)
    assert stt_cell["bbox"][0] == reference_stt_x["bbox"][0]
    assert stt_cell["bbox"][1] == lines[2]["bbox"][1]


def test_ocr_tables_keeps_subtotal_vat_and_total_rows_without_losing_the_table():
    # Real dossier hard case: the value table's LAST item row is also the page's
    # first line (so it becomes the block's reference row), its own "Đơn giá"/"Thành
    # tiền" cells both a plain "0" Tesseract detected no ink for at all -- recovered
    # via _row_cells' trailing-GPT-number rescue. It's followed immediately by the
    # table's own subtotal/VAT/grand-total rows (a merged "label + amount" cell each,
    # in all three separator forms GPT vision has been observed to use for the very
    # same merge on different reprocessing runs), then by unrelated page content (a
    # signature block) that must NOT be absorbed into the table.
    #
    # Before the summary-row fix, none of the three summary lines satisfied
    # _matching_cells or _merge_wrapped_continuation, so the second of them (two
    # anomalies back to back) flushed the block -- silently dropping the item row
    # above from the reconstructed table right along with its own total, not just
    # the total itself.
    from app.document_processing import _ocr_tables

    item_row = _cells_line(0, 0.10, [
        (*_STT, ["30"]), (*_NOIDUNG, ["Ho", "tro", "nghiem", "thu"]),
        (*_DVT, ["Goi"]), (*_SL, ["1"]),
    ])
    item_row["trailing_gpt_text"] = "0 0"

    def _summary_line(index, y, text):
        # A summary row's own words are real (Tesseract does detect ink for the
        # label and the amount, just not shaped like the item table's own columns),
        # spanning most of the row's width -- only its TEXT (as GPT vision corrected
        # it) carries the merge that _row_cells' geometry-only grouping can't resolve.
        line = _ocr_line(index, [_word(text.replace(" ", "_"), 0.05, y, 0.93, y + 0.018)])
        line["text"] = text
        return line

    lines = [
        item_row,
        _summary_line(1, 0.13, "CỘNG TRƯỚC THUẾ 1.116.230.000"),
        _summary_line(2, 0.16, "VAT 10%\t111.623.000"),
        _summary_line(3, 0.19, "TỔNG CỘNG1.227.853.000"),
        _summary_line(4, 0.22, "ĐẠI DIỆN BÊN A ĐẠI DIỆN BÊN B"),
    ]

    tables = _ocr_tables(lines, {"document_id": "doc", "page_number": 5})

    assert len(tables) == 1
    table = tables[0]

    def row_text(row):
        return {c["col_index"]: c["text"] for c in row["cells"]}

    assert len(table["rows"]) == 4  # item row + 3 summary rows; signature block excluded
    last_col = table["col_count"] - 1  # STT, Nội dung, ĐVT, SL, [Đơn giá], [Thành tiền]
    assert row_text(table["rows"][0])[last_col - 1] == "0"
    assert row_text(table["rows"][0])[last_col] == "0"
    assert row_text(table["rows"][1]) == {0: "CỘNG TRƯỚC THUẾ", last_col: "1.116.230.000"}
    assert row_text(table["rows"][2]) == {0: "VAT 10%", last_col: "111.623.000"}
    assert row_text(table["rows"][3]) == {0: "TỔNG CỘNG", last_col: "1.227.853.000"}
    # The signature block never became a row, or corrupted a summary row's own text:
    assert all("ĐẠI DIỆN" not in text for row in table["rows"] for text in row_text(row).values())


def test_split_gpt_text_positionally_six_column_row_with_unit():
    # Real hard case (dossier 9f889e79, trang 2, dòng "08 Cáp quang LC-LC OM4 3m.
    # Sợi 12 480.000 5.760.000"): no tabs this run (GPT vision's own tab habit is
    # non-deterministic between calls -- see _gpt_tab_cells), so this is the only
    # signal left. STT (leading number) and the three trailing Vietnamese-formatted
    # numbers (SL/Đơn giá/Thành tiền) are read off by shape; "OM4" and "3m." don't
    # match that shape, so the scan naturally stops there, leaving the ĐVT token
    # ("Sợi") and the Mô tả text correctly split from each other.
    from app.document_processing import _split_gpt_text_positionally

    tokens = "08 Cáp quang LC-LC OM4 3m. Sợi 12 480.000 5.760.000".split()

    assert _split_gpt_text_positionally(tokens, 6) == [
        "08", "Cáp quang LC-LC OM4 3m.", "Sợi", "12", "480.000", "5.760.000",
    ]


def test_split_gpt_text_positionally_five_column_row_without_unit():
    # A table shape with no ĐVT column at all (STT, Mô tả, SL, Đơn giá, Thành tiền):
    # the same trailing-numeric scan leaves exactly ONE middle slot, so the whole
    # remaining span becomes Mô tả with no further split.
    from app.document_processing import _split_gpt_text_positionally

    tokens = "03 Bàn làm việc gỗ công nghiệp 2 1.200.000 2.400.000".split()

    assert _split_gpt_text_positionally(tokens, 5) == [
        "03", "Bàn làm việc gỗ công nghiệp", "2", "1.200.000", "2.400.000",
    ]


def test_split_gpt_text_positionally_refuses_when_ambiguous():
    from app.document_processing import _split_gpt_text_positionally

    # No leading number at all -- which column (if any) absorbs the first token is
    # genuinely ambiguous, not something to guess.
    assert _split_gpt_text_positionally("Bàn làm việc gỗ 2 1.200.000 2.400.000".split(), 5) is None
    # Too few tokens to fill every column even one-for-one.
    assert _split_gpt_text_positionally("08 Cáp quang".split(), 6) is None
    # No trailing numeric run at all -- more than two slots would be left between
    # STT and nothing, past what a single Mô tả/ĐVT pair can absorb.
    assert _split_gpt_text_positionally("08 Cáp quang LC-LC OM4 3m. Sợi mét".split(), 6) is None


def test_ocr_tables_reconstructs_a_row_gpt_vision_split_by_position_alone():
    # Full integration of the case above: Tesseract's own OCR of this exact line was
    # so badly broken that none of its "words" resemble the real content at all
    # (real observed tokens: "[os", "|cinacangtcucomeam", "m99|", "smoe|", ...), so
    # neither word alignment (_align_gpt_words) nor a shared tab count
    # (_gpt_tab_cells) has anything to work with -- yet GPT vision's own plain-text
    # reading of the row is fully recovered via position and data shape alone.
    from app.document_processing import _ocr_tables

    lines = [
        _cells_line(0, 0.10, [
            (*_STT, ["05"]), (*_NOIDUNG, ["Bản", "quyền", "hệ", "điều", "hành"]),
            (*_DVT, ["Lic"]), (*_SL, ["4"]), (*_DONGIA, ["22.450.000"]), (*_THANHTIEN, ["89.800.000"]),
        ]),
        _cells_line(1, 0.13, [
            (*_STT, ["06"]), (*_NOIDUNG, ["Dịch", "vụ", "cấu", "hình"]),
            (*_DVT, ["Gói"]), (*_SL, ["1"]), (*_DONGIA, ["32.600.000"]), (*_THANHTIEN, ["32.600.000"]),
        ]),
        _cells_line(
            2, 0.16,
            [(*_STT, ["[os"]), (*_NOIDUNG, ["|cinacangtcucomeam"]), (*_DVT, ["m99|"]), (*_THANHTIEN, ["smoe|"])],
        ),
        _cells_line(3, 0.19, [
            (*_STT, ["10"]), (*_NOIDUNG, ["Dịch", "vụ", "hardening"]),
            (*_DVT, ["Gói"]), (*_SL, ["2"]), (*_DONGIA, ["17.900.000"]), (*_THANHTIEN, ["35.800.000"]),
        ]),
    ]
    lines[2]["text"] = "08 Cáp quang LC-LC OM4 3m. Sợi 12 480.000 5.760.000"

    tables = _ocr_tables(lines, {"document_id": "doc", "page_number": 1})

    assert len(tables) == 1
    row = tables[0]["rows"][2]

    def text(col_index):
        return next((c["text"] for c in row["cells"] if c["col_index"] == col_index), None)

    assert text(0) == "08"
    assert text(1) == "Cáp quang LC-LC OM4 3m."
    assert text(2) == "Sợi"
    assert text(3) == "12"
    assert text(4) == "480.000"
    assert text(5) == "5.760.000"
    assert all(c["inferred"] for c in row["cells"])


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
