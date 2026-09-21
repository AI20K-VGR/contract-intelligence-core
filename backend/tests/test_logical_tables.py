from copy import deepcopy

from app import table_continuity
from app.table_continuity import ContinuityDecision, ContinuityResult
from app.tables import build_logical_tables

EDGES = [0, 0.06, 0.60, 0.66, 0.72, 0.82, 0.94, 1]
HEADER = ["Stt", "Tên hàng", "SL", "ĐVT", "Đơn giá", "Thành tiền", "Ghi chú"]


def fragment(page, values, *, phantom=False, document="doc", top=0.2, bottom=0.7):
    rows = []
    for r, texts in enumerate(values):
        cells = []
        for i, text in enumerate(texts):
            left, right = EDGES[i : i + 2]
            # The detector invents four extra empty slots on page 2. Real cells
            # retain their PDF geometry, but have different col_index values.
            cells.append(
                {
                    "col_index": i + (4 if phantom and i else 0),
                    "text": text,
                    "bbox": [left, top + r * 0.02, right, top + (r + 1) * 0.02],
                }
            )
        if phantom:
            for i in range(1, 5):
                cells.append(
                    {
                        "col_index": i,
                        "text": "",
                        "bbox": [0.06, top + r * 0.02, 0.061, top + (r + 1) * 0.02],
                    }
                )
        rows.append({"row_index": r, "cells": cells})
    return {
        "id": f"t:{document}:{page}",
        "document_id": document,
        "page_number": page,
        "col_count": 11 if phantom else 7,
        "row_count": len(rows),
        "bbox": [0, top, 1, bottom],
        "rows": rows,
    }


def sample():
    return [
        fragment(
            1,
            [
                HEADER,
                ["01", "Bảng phòng Tư vấn", "04", "Cái", "1,000,000", "4,000,000", ""],
                ["02", "Bảng tên phòng, thư mục sách", "20", "Cái", "100,000", "2,000,000", ""],
            ],
        ),
        fragment(
            2,
            [
                ["", "Kích thước: 0,15m x 0,3 m - Quy cách: Mica", "", "", "", "", ""],
                ["03", "Bảng khẩu hiệu", "06", "Cái", "2,000,000", "12,000,000", ""],
                ["04", "Bảng sinh hoạt", "02", "Cái", "1,500,000", "3,000,000", ""],
                ["05", "Cổng thư viện", "01", "Cái", "4,900,000", "4,900,000", ""],
                ["06", "Bảng trang trí phòng thư viện", "04", "Cái", "2,000,000", "8,000,000", ""],
                [
                    "07",
                    "Bảng trang trí phòng truyền thống",
                    "08",
                    "Cái",
                    "2,000,000",
                    "16,000,000",
                    "",
                ],
                ["Tổng cộng", "", "", "", "49,900,000", "", ""],
            ],
            phantom=True,
        ),
    ]


def test_screenshot_split_description_phantom_columns_and_provenance():
    tables = sample()
    original = deepcopy(tables)
    result = build_logical_tables(tables)
    assert len(result) == 1
    table = result[0]
    assert table["status"] == "RECONSTRUCTED"
    assert table["col_count"] == 7
    assert (table["page_start"], table["page_end"]) == (1, 2)
    assert len(table["rows"]) == 9  # header + seven items + original total
    row = table["rows"][2]
    assert row["cells"][1]["text"] == (
        "Bảng tên phòng, thư mục sách Kích thước: 0,15m x 0,3 m - Quy cách: Mica"
    )
    assert [s["page_number"] for s in row["cells"][1]["sources"]] == [1, 2]
    assert row["cells"][5]["text"] == "2,000,000"
    assert table["rows"][-1]["kind"] == "total"
    # Preserve the total's source column; do not shift it to a guessed amount column.
    assert table["rows"][-1]["cells"][4]["text"] == "49,900,000"
    assert tables == original
    assert build_logical_tables(tables) == result


def test_blank_notes_does_not_swallow_next_numbered_row():
    tables = sample()
    tables[1]["rows"].pop(0)
    result = build_logical_tables(tables)[0]
    assert result["rows"][2]["cells"][1]["text"] == "Bảng tên phòng, thư mục sách"
    assert result["rows"][3]["cells"][0]["text"] == "03"


def test_repeated_header_removed_but_source_retained():
    tables = sample()
    tables[1] = fragment(2, [HEADER, ["03", "C", "6", "Cái", "2", "12", ""]])
    result = build_logical_tables(tables)[0]
    assert len(result["repeated_headers"]) == 1
    assert len(result["rows"]) == 4


def test_new_table_number_restart_not_joined():
    tables = sample()
    tables[1] = fragment(2, [HEADER, ["01", "Other", "", "", "", "", ""]])
    assert len(build_logical_tables(tables)) == 2
    tables[0]["bbox"][3] = 0.95
    tables[1]["bbox"][1] = 0.05
    assert len(build_logical_tables(tables)) == 2


def test_page_gap_and_document_boundary_never_join():
    for change in [{"page_number": 3}, {"document_id": "another"}]:
        tables = sample()
        tables[1].update(change)
        assert len(build_logical_tables(tables)) == 2


def test_nonempty_ambiguous_spanning_cell_kept_for_review():
    tables = sample()
    tables[1]["rows"][0]["cells"][1]["bbox"] = [0, 0.2, 1, 0.22]
    result = build_logical_tables(tables)
    assert len(result) == 2
    assert result[1]["status"] == "NEEDS_REVIEW"
    assert any("Mica" in c["text"] for c in result[1]["rows"][0]["cells"])


def test_column_boundary_straddle_resolved_by_row_order_not_pixels():
    # Real hard_case document (744287578-Hợp-đồng.pdf, trang 1→2): the "SL" cell on the
    # continuation page sat ~3% of the page width left of where page 1's grid expected
    # it, straddling the Tên hàng/SL boundary at ~54%/46% instead of landing inside one
    # band. Naively trusting the overlap-argmax here picks whichever band the cell
    # overlaps MORE — Tên hàng (54%), the wrong column — which would silently append the
    # SL digits to the end of the item description and leave the real SL cell blank
    # (caught by hand against the live reconstructed rows, not by any prior unit test).
    # The fix isn't a looser threshold: every OTHER cell in this same row already landed
    # exactly on its own left-to-right rank (STT, Tên hàng, ĐVT, Đơn giá, Thành tiền all
    # unambiguous), so the row's own order — not the disputed pixels — settles which
    # column the "06" belongs to.
    tables = sample()
    sl_cell = next(c for c in tables[1]["rows"][1]["cells"] if c["text"] == "06")
    x0, _, x1, _ = tables[1]["bbox"]
    width = x1 - x0
    drift = 0.0325 * width
    sl_cell["bbox"][0] -= drift
    sl_cell["bbox"][2] -= drift

    result = build_logical_tables(tables)
    assert len(result) == 1
    assert result[0]["status"] == "RECONSTRUCTED"
    row = next(r for r in result[0]["rows"] if r["cells"][0]["text"] == "03")
    assert row["cells"][1]["text"] == "Bảng khẩu hiệu"
    assert row["cells"][2]["text"] == "06"


def test_column_boundary_straddle_without_row_order_support_stays_needs_review():
    # Same SL/Tên hàng straddle as above, but this time the STT cell of the same row has
    # ALSO drifted enough to confidently (dominantly) overlap the Tên hàng column instead
    # of its own — so the row no longer shows a single other cell confirming "rank ==
    # column index" for the tiebreak to lean on. With nothing left to settle the tie,
    # the SL cell must stay NEEDS_REVIEW rather than guess.
    tables = sample()
    row = tables[1]["rows"][1]["cells"]
    sl_cell = next(c for c in row if c["text"] == "06")
    stt_cell = next(c for c in row if c["text"] == "03")
    x0, _, x1, _ = tables[1]["bbox"]
    width = x1 - x0
    sl_cell["bbox"][0] -= 0.0325 * width
    sl_cell["bbox"][2] -= 0.0325 * width
    stt_cell["bbox"][0] += 0.04 * width
    stt_cell["bbox"][2] += 0.04 * width

    result = build_logical_tables(tables)
    assert len(result) == 2
    assert result[1]["status"] == "NEEDS_REVIEW"


def test_total_ends_table_even_if_next_page_has_matching_grid():
    tables = sample()
    tables.append(fragment(3, [HEADER, ["08", "Other", "", "", "", "", ""]], top=0.05))
    assert len(build_logical_tables(tables)) == 2


def test_headerless_table_still_reconstructs_via_numbered_rows():
    # Real hard case (Hop_dong_scan_stress_bang_lien_trang_khong_header): a table
    # split across a page break where NEITHER page has a recognizable header row at
    # all (OCR missed it, or the scan genuinely has none) — before this fallback,
    # _grid() unconditionally required table["rows"][0] to match the STT/description
    # header whitelist, so a table like this could never even bootstrap a grid on
    # page 1, and page 2 was left as a second, disconnected fragment instead of one
    # reconstructed table.
    headerless = [
        fragment(
            1,
            [
                ["01", "Bảng phòng Tư vấn", "04", "Cái", "1,000,000", "4,000,000", ""],
                ["02", "Bảng tên phòng, thư mục sách", "20", "Cái", "100,000", "2,000,000", ""],
            ],
        ),
        fragment(
            2,
            [
                ["03", "Bảng khẩu hiệu", "06", "Cái", "2,000,000", "12,000,000", ""],
                ["04", "Bảng sinh hoạt", "02", "Cái", "1,500,000", "3,000,000", ""],
            ],
        ),
    ]

    result = build_logical_tables(headerless)

    assert len(result) == 1
    table = result[0]
    assert table["status"] == "RECONSTRUCTED"
    assert (table["page_start"], table["page_end"]) == (1, 2)
    assert [row["cells"][0]["text"] for row in table["rows"]] == ["01", "02", "03", "04"]
    assert table["rows"][2]["cells"][1]["text"] == "Bảng khẩu hiệu"


def test_headerless_unrelated_block_stays_raw():
    # The numbered-rows fallback must not fire just because SOME row happens to
    # start with a number — it requires a real majority across the fragment.
    signature_block = fragment(
        1,
        [
            ["Bên A", "Nguyễn Văn A", "", "", "", "", ""],
            ["1 bản chính", "Bên B", "Trần Thị B", "", "", "", ""],
        ],
    )
    result = build_logical_tables([signature_block])
    assert len(result) == 1
    assert result[0]["status"] == "STANDALONE"


def test_third_page_continues_with_original_canonical_columns():
    tables = sample()
    tables[1]["rows"].pop()
    tables.append(fragment(3, [["08", "Next", "1", "Cái", "2", "2", ""]]))
    result = build_logical_tables(tables)
    assert len(result) == 1
    assert result[0]["page_end"] == 3


def test_annex_heading_between_forces_split_even_with_matching_columns_and_sequence():
    # Real risk case: two annexes share an identical item-table header/geometry, and
    # the second annex's numbering happens to continue the first's -- every
    # deterministic signal a pure geometry/sequence check relies on says MERGE, but
    # "Phụ lục 02" between them means this is a NEW table (app/table_continuity.py's
    # Tier-1 hard guard exists specifically for this).
    tables = sample()
    tables[1] = fragment(2, [HEADER, ["03", "C", "6", "Cái", "2", "12", ""]])
    tables[1]["heading_before"] = "Phụ lục 02"
    result = build_logical_tables(tables)
    assert len(result) == 2


def test_headerless_no_stt_continuation_needs_agent_to_merge(monkeypatch):
    # Real hard case: a continuation row on the next page has no STT/header at all
    # (mid-sentence table wrap) -- geometry alone lands in the genuine gray zone
    # (column match + "no header on continuation", score 5 of the 8 needed), so the
    # deterministic rule engine correctly refuses to guess without help.
    fragments = [
        fragment(
            1,
            [
                ["01", "Bảng phòng Tư vấn", "04", "Cái", "1,000,000", "4,000,000", ""],
                ["02", "Bảng tên phòng, thư mục sách", "20", "Cái", "100,000", "2,000,000", ""],
            ],
        ),
        fragment(
            2,
            [
                ["", "Dịch vụ triển khai lắp đặt", "1", "Bộ", "5,000,000", "5,000,000", ""],
                ["03", "Bảo hành 12 tháng", "1", "Bộ", "1,000,000", "1,000,000", ""],
            ],
        ),
    ]

    without_agent = build_logical_tables(fragments)
    assert len(without_agent) == 2
    assert without_agent[1]["status"] == "NEEDS_REVIEW"

    def fake_agent(evidence, score):
        return ContinuityResult(ContinuityDecision.MERGE, ["agent_merge"], score, True)

    monkeypatch.setattr(table_continuity, "_ask_agent", fake_agent)

    with_agent = build_logical_tables(fragments, {"table_continuity_agent": True})
    assert len(with_agent) == 1
    assert with_agent[0]["status"] == "RECONSTRUCTED"
    assert [row["cells"][1]["text"] for row in with_agent[0]["rows"]] == [
        "Bảng phòng Tư vấn", "Bảng tên phòng, thư mục sách",
        "Dịch vụ triển khai lắp đặt", "Bảo hành 12 tháng",
    ]


def test_real_pdf_extraction_to_logical_api_view(system):
    import pymupdf

    from app.worker import run_once

    client, factory, config = system
    with pymupdf.open() as pdf:
        contents = [
            [
                ["No", "Item", "Qty", "Unit", "Price", "Amount", "Note"],
                ["01", "First item", "4", "pc", "100", "400", ""],
                ["02", "Room sign", "20", "pc", "100", "2000", ""],
            ],
            [
                ["", "Size 0.15 x 0.3 m - Mica", "", "", "", "", ""],
                ["03", "Next item", "6", "pc", "200", "1200", ""],
            ],
        ]
        for rows in contents:
            page = pdf.new_page(width=600, height=800)
            xs = [40 + edge * 520 for edge in EDGES]
            for x in xs:
                page.draw_line((x, 80), (x, 80 + 30 * len(rows)))
            for r in range(len(rows) + 1):
                page.draw_line((40, 80 + 30 * r), (560, 80 + 30 * r))
            for r, row in enumerate(rows):
                for c, text in enumerate(row):
                    page.insert_text((xs[c] + 2, 98 + 30 * r), text, fontsize=8)
        data = pdf.tobytes()
    dossier = client.post(
        "/api/v1/dossiers",
        json={"title": "Split table"},
        headers={"Idempotency-Key": "tables-create"},
    ).json()["id"]
    response = client.post(
        f"/api/v1/dossiers/{dossier}/documents",
        files={"file": ("tables.pdf", data, "application/pdf")},
        data={"role": "contract"},
        headers={"Idempotency-Key": "tables-upload"},
    )
    assert response.status_code == 201
    job = client.post(f"/api/v1/dossiers/{dossier}/jobs", headers={"Idempotency-Key": "tables-job"})
    assert job.status_code == 202
    for _ in range(20):
        if not run_once(factory, config):
            break
    url = f"/api/v1/dossiers/{dossier}/tables"
    response = client.get(url)
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["items"]) == 2  # raw immutable fragments remain available
    assert len(body["logical_items"]) == 1
    logical = body["logical_items"][0]
    assert logical["rows"][2]["cells"][1]["text"] == "Room sign Size 0.15 x 0.3 m - Mica"
    assert [s["page_number"] for s in logical["rows"][2]["cells"][1]["sources"]] == [1, 2]
    assert body["reconstruction_version"] == "table-geometry-v1"
    assert client.get(url, params={"view": "machine"}).json()["items"] == body["items"]
