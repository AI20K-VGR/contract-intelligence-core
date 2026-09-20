"""Debug tool: reconstruct tables from a saved `/dossiers/{id}/results` JSON using
whatever code is CURRENTLY on disk — no live app, no worker restart needed to check
whether a fix actually works on real OCR output.

For each page whose `engine` is a tesseract variant, table DETECTION
(document_processing._ocr_tables) is re-run fresh from that page's own `lines` —
this is exactly what the worker would produce if it reprocessed the page right now.
A native ("pymupdf") page's table detection needs the live PDF page object (PyMuPDF's
own find_tables), which a JSON export can't provide, so its already-stored `tables`
are reused as-is instead (unaffected by these fixes anyway — they only touch
_ocr_tables). Cross-page COMBINING (tables.build_logical_tables) always runs fresh,
matching what the live API's /tables endpoint does on every request.

Usage (from backend/, with `uv sync` already run once):
    uv run python scripts/reconstruct_tables.py path/to/results.json

`results.json` is the saved body of `GET /api/v1/dossiers/{id}/results` — either the
full envelope ({"machine": {...}, "effective": {...}, ...}) or just its "machine"
object directly both work.
"""

import json
import sys
from pathlib import Path

from app.document_processing import _column_gap_threshold, _ocr_tables, _row_cells
from app.tables import build_logical_tables


def _diagnose_line(line):
    words = sorted(line.get("words") or [], key=lambda w: w["bbox"][0])
    cells = _row_cells(line)
    gaps = [words[k + 1]["bbox"][0] - words[k]["bbox"][2] for k in range(len(words) - 1)]
    threshold = _column_gap_threshold(gaps) if gaps else None
    return words, cells, threshold


def _diagnose_page(page):
    lines = page.get("lines") or []
    print(f"\n  --- Chi tiet trang {page['page_number']} ({len(lines)} dong) ---")
    for i, line in enumerate(lines):
        words, cells, threshold = _diagnose_line(line)
        threshold_str = f"{threshold:.4f}" if threshold is not None else "-"
        if cells is None:
            preview = (line.get("text") or "")[:70]
            print(f"  [{i:3}] {len(words):2} tu -> None nhom (nguong={threshold_str})  {preview}")
            continue
        print(f"  [{i:3}] {len(words):2} tu -> {len(cells)} nhom (nguong={threshold_str}):")
        for cell in cells:
            left = cell["bbox"][0]
            print(f"        x0={left:.4f}  \"{cell['text'][:40]}\"")


def _cell_text(row, col_index):
    return next((c["text"] for c in row["cells"] if c["col_index"] == col_index), "")


def _render_table(table):
    page_label = (
        f"Trang {table['page_start']}"
        if table["page_start"] == table["page_end"]
        else f"Trang {table['page_start']}-{table['page_end']}"
    )
    data_rows = [r for r in table["rows"] if r["kind"] == "data"]
    header_rows = [r for r in table["rows"] if r["kind"] == "header"]
    print(f"[{table['status']}] {page_label} - {len(data_rows)} dong du lieu x {table['col_count']} cot")
    if table["status"] == "RECONSTRUCTED":
        print(f"  -> Da noi {len(table['fragment_ids'])} manh thanh 1 bang.")
    if not table["rows"]:
        print()
        return

    widths = [
        min(max((len(_cell_text(r, c)) for r in table["rows"]), default=0), 28)
        for c in range(table["col_count"])
    ]

    def render_row(row, label):
        cells = [_cell_text(row, c).replace("\n", " ")[:28].ljust(widths[c]) for c in range(table["col_count"])]
        return f"  {label:8}| " + " | ".join(cells)

    for row in header_rows:
        print(render_row(row, "HEADER"))
        print("  " + "-" * (10 + sum(widths) + 3 * table["col_count"]))
    for row in data_rows:
        print(render_row(row, "data"))
    print()


def main(path: str) -> None:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    machine = payload.get("machine", payload)
    pages = machine.get("pages")
    if pages is None:
        raise SystemExit(
            "Khong tim thay 'pages' trong file JSON. Dam bao day la output cua "
            "GET /dossiers/{id}/results (ca envelope hoac chi phan 'machine')."
        )

    print(f"So trang: {len(pages)}\n")
    fragments = []
    for page in sorted(pages, key=lambda p: (p["document_id"], p["page_number"])):
        engine = page.get("engine") or ""
        lines = page.get("lines") or []
        stored = page.get("tables") or []
        if engine.startswith("tesseract"):
            fresh = _ocr_tables(lines, {"document_id": page["document_id"], "page_number": page["page_number"]})
            source = "chay lai _ocr_tables voi code hien tai"
        else:
            fresh = stored
            source = "dung nguyen ket qua da luu (native PyMuPDF, khong the chay lai tu JSON)"
        print(
            f"- Trang {page['page_number']} (engine={engine or '?'}, issue={page.get('issue')}): "
            f"{len(lines)} dong OCR -> {len(fresh)} manh bang [{source}]"
        )
        fragments.extend(fresh)

    print()
    if not fragments:
        print(
            "KHONG co manh bang nao duoc phat hien tren bat ky trang nao.\n"
            "=> Van de nam o buoc PHAT HIEN bang tu hinh hoc OCR (_ocr_tables), "
            "chua toi buoc ghep trang. In chi tiet tung dong duoi day: so tu, so "
            "nhom cot ma _row_cells tach duoc (can >= 3 va >= _OCR_TABLE_MIN_ROWS=3 "
            "dong lien tiep CUNG so nhom/tuong thich de tao thanh bang)."
        )
        for page in sorted(pages, key=lambda p: (p["document_id"], p["page_number"])):
            if (page.get("engine") or "").startswith("tesseract"):
                _diagnose_page(page)
        return

    result = build_logical_tables(fragments)
    print(f"So bang sau khi ghep trang (logical_items): {len(result)}\n")
    for table in result:
        _render_table(table)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Dung: uv run python scripts/reconstruct_tables.py <duong-dan-results.json>")
    main(sys.argv[1])
