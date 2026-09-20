import re
import unicodedata
from collections import defaultdict
from copy import deepcopy

# A table's last row sitting this close to the page bottom, immediately followed by
# another table starting this close to the next page's top, is the layout signature of
# one table split by a hard page break — no repeated header, the exact case in
# docs/architecture.md's "bảng dài hàng trăm dòng qua nhiều trang (chỉ có tiêu đề ở
# trang đầu)". Thresholds are deliberately loose (not "touching" 0/1): PyMuPDF's own
# find_tables() rarely reports a bbox flush against the physical page edge.
BOTTOM_EDGE_THRESHOLD = 0.85
TOP_EDGE_THRESHOLD = 0.15

# A cell must overlap its best-matching grid column by at least this fraction of its own
# width to be considered plausibly IN that column at all — a low sanity floor (a cell
# barely grazing a column's edge is never that column's value), not the bar for trusting
# the match unsupervised. COLUMN_DOMINANCE_RATIO below is what gates that.
COLUMN_OVERLAP_THRESHOLD = 0.35

# A cell wider than this many times its target column's own width is a cell spanning
# several columns (garbled OCR, a merged cell), never a single value that just drifted —
# reject it outright, whatever its overlap ratio says.
COLUMN_WIDTH_DRIFT_RATIO = 1.4

# The best-matching column must beat the runner-up by this ratio to be trusted on
# overlap alone; below it, _map_rows falls back to each row's own left-to-right cell
# order (see its docstring) instead of guessing from pixels. A real hard case (744287578-
# Hợp-đồng.pdf, trang 1→2) had an "SL" cell straddling the Tên hàng/SL boundary at
# 54.2%/45.8% — clearing a loosened overlap floor, but the overlap-argmax alone then
# picks the *wrong* column outright (54 > 46), silently gluing the SL digits onto the end
# of the item description and leaving the real SL cell blank. Caught by re-fetching the
# reconstructed rows, not by a unit test.
COLUMN_DOMINANCE_RATIO = 1.5


def link_continuations(tables):
    """Flags pairs of per-page tables that look like one logical table split across a
    page break, by page position only — it never merges cell data, only sets
    `continues_table_id` / `continued_by_table_id` (plus `continuation_confidence`) so a
    reviewer or the UI can choose to present them as one table.

    Position-only on purpose: PyMuPDF's column detection is not always stable across a
    page break (a wrapped/merged row can shift the detected col_count), so a mismatched
    col_count only downgrades confidence to "low" instead of ruling the pair out — ruling
    it out would silently hide the exact case this exists to catch.
    """
    for table in tables:
        table.setdefault("continues_table_id", None)
        table.setdefault("continued_by_table_id", None)
        table.setdefault("continuation_confidence", None)

    by_document = defaultdict(list)
    for table in tables:
        by_document[table["document_id"]].append(table)

    for document_tables in by_document.values():
        document_tables.sort(key=lambda t: (t["page_number"], t["bbox"][1]))
        for previous, current in zip(document_tables, document_tables[1:]):
            if current["page_number"] != previous["page_number"] + 1:
                continue
            if previous["bbox"][3] < BOTTOM_EDGE_THRESHOLD or current["bbox"][1] > TOP_EDGE_THRESHOLD:
                continue
            current["continues_table_id"] = previous["id"]
            current["continuation_confidence"] = (
                "high" if current["col_count"] == previous["col_count"] else "low"
            )
            previous["continued_by_table_id"] = current["id"]
    return tables


def _label(text):
    text = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    return re.sub(r"\s+", "", "".join(c for c in text if not unicodedata.combining(c)))


# The description column's header is checked by PREFIX, not exact match: a real
# contract's header cell is often a longer phrase — "Nội dung hàng hóa / dịch vụ",
# "Tên hàng hóa/dịch vụ" — not the bare single word these prefixes suggest. The STT
# column's own labels ({"stt", "sott", "no", "no."} below) stay exact-match: they're
# short enough that prefix matching would false-positive on unrelated words (a "Note"
# column starts with "no").
_DESCRIPTION_LABEL_PREFIXES = ("tenhang", "hangmuc", "mota", "description", "item", "noidung")


def _header(row):
    labels = {_label(c["text"]) for c in row["cells"]}
    return bool(labels & {"stt", "sott", "no", "no."}) and any(
        label.startswith(prefix) for label in labels for prefix in _DESCRIPTION_LABEL_PREFIXES
    )


def _total(row):
    return any(_label(c["text"]) in {"tongcong", "tong", "total", "grandtotal"}
               for c in row["cells"])


def _source(table, row, cell):
    return {"table_id": table["id"], "document_id": table["document_id"],
            "page_number": table["page_number"], "row_index": row["row_index"],
            "col_index": cell["col_index"], "bbox": list(cell["bbox"]),
            "text": cell["text"]}


def _raw_rows(table):
    return [{"kind": "header" if _header(row) else "total" if _total(row) else "data",
             "cells": [{**deepcopy(cell), "sources": [_source(table, row, cell)]}
                       for cell in row["cells"]]} for row in table["rows"]]


def _grid_from_cells(table, cells):
    x0, _, x1, _ = table["bbox"]
    if x1 <= x0:
        return None
    return [((c["bbox"][0] - x0) / (x1 - x0),
             (c["bbox"][2] - x0) / (x1 - x0)) for c in cells]


def _looks_like_numbered_rows(table):
    """True when most rows' leftmost cell is a small integer — the STT column's own
    shape — even without any recognizable header text. Used as a fallback signal for a
    fragment whose header row wasn't captured at all: a real hard case is a table split
    across a page break with no header repeated (or even present) anywhere, e.g. one OCR
    missed on every page rather than just the continuation pages _header() already
    tolerates via the established grid. Requires a real majority, not just one lucky
    row, so an unrelated headerless block (a signature/date block, say) doesn't
    qualify just because one of its rows happens to start with a number.
    """
    numeric = 0
    total = 0
    for row in table["rows"]:
        if not row["cells"]:
            continue
        first = min(row["cells"], key=lambda c: c["bbox"][0])
        total += 1
        if re.fullmatch(r"\d{1,3}", first["text"].strip()):
            numeric += 1
    return total >= 2 and numeric / total >= 0.6


def _grid(table):
    if not table["rows"]:
        return None
    header_row = table["rows"][0]
    if _header(header_row):
        cells = sorted(header_row["cells"], key=lambda c: c["bbox"][0])
        if len(cells) != table["col_count"]:
            return None
        # This rule handles item tables with identity then description. Other schemas
        # remain raw until an explicit column-role mapping is available.
        if (len(cells) < 2 or _label(cells[0]["text"]) not in {"stt", "sott", "no", "no."}
                or not any(
                    _label(cells[1]["text"]).startswith(p) for p in _DESCRIPTION_LABEL_PREFIXES
                )):
            return None
        return _grid_from_cells(table, cells)

    # No recognizable header anywhere on this fragment — fall back to deriving column
    # bands from the widest row's own cell geometry, but only when the STT column's own
    # shape still corroborates that this really is an item table (see
    # _looks_like_numbered_rows). An arbitrary headerless block stays raw, unchanged.
    if not _looks_like_numbered_rows(table):
        return None
    widest = max(table["rows"], key=lambda r: len(r["cells"]))
    cells = sorted(widest["cells"], key=lambda c: c["bbox"][0])
    if len(cells) < 2 or len(cells) != table["col_count"]:
        return None
    return _grid_from_cells(table, cells)


def _resolve_cell(cell, rank, x0, x1, grid):
    """Geometric candidates for one nonempty cell: its best- and second-best-overlapping
    grid column, and whether the best one dominates clearly enough to trust on its own.
    Returns None if the cell doesn't sanely belong to any single column at all (too wide
    for the one it best overlaps, or barely touching it) — that failure is final, no
    fallback rescues it.
    """
    left = (cell["bbox"][0] - x0) / (x1 - x0)
    right = (cell["bbox"][2] - x0) / (x1 - x0)
    if right <= left:
        return None
    overlap = [max(0, min(right, b) - max(left, a)) for a, b in grid]
    order = sorted(range(len(grid)), key=overlap.__getitem__, reverse=True)
    best, second = order[0], order[1] if len(order) > 1 else None
    band_left, band_right = grid[best]
    if (
        overlap[best] / (right - left) < COLUMN_OVERLAP_THRESHOLD
        or right - left > (band_right - band_left) * COLUMN_WIDTH_DRIFT_RATIO
    ):
        return None
    dominant = second is None or overlap[best] >= overlap[second] * COLUMN_DOMINANCE_RATIO
    return {"cell": cell, "rank": rank, "best": best, "second": second, "dominant": dominant}


def _map_rows(table, grid):
    """Map physical cells by horizontal geometry, never by unstable detector indices.

    Ambiguous nonempty spanning cells abort normalization; callers keep the raw
    fragment for review. Empty phantom columns are harmless, raw input stays intact.

    One exception: a cell whose column is a near-tie between two neighbors (real hard
    case — see COLUMN_DOMINANCE_RATIO) is still placed if every OTHER cell in the same
    row already landed exactly on its own left-to-right rank among that row's nonempty
    cells — i.e. the row is a plain, left-aligned "STT, tên hàng, …" line missing only
    some trailing column, and this cell's rank is one of the two the geometry itself
    proposed. A row that doesn't already show that plain shape gets no such benefit of
    the doubt.
    """
    x0, _, x1, _ = table["bbox"]
    if x1 <= x0:
        return None
    rows = []
    for raw in table["rows"]:
        nonempty = sorted(
            (c for c in raw["cells"] if c["text"].strip()), key=lambda c: (c["bbox"][1], c["bbox"][0])
        )
        resolved = []
        for rank, cell in enumerate(nonempty):
            outcome = _resolve_cell(cell, rank, x0, x1, grid)
            if outcome is None:
                return None
            resolved.append(outcome)
        prefix_consistent = len(nonempty) <= len(grid) and all(
            r["rank"] == r["best"] for r in resolved if r["dominant"]
        )
        cells = [{"col_index": i, "text": "", "bbox": [], "sources": []}
                 for i in range(len(grid))]
        for r in resolved:
            if r["dominant"]:
                index = r["best"]
            elif prefix_consistent and r["rank"] in (r["best"], r["second"]):
                index = r["rank"]
            else:
                return None
            target = cells[index]
            if target["text"] and index != 1:
                return None  # Never concatenate separate identifiers or numeric values.
            target["text"] = (target["text"] + " " + r["cell"]["text"].strip()).strip()
            target["sources"].append(_source(table, raw, r["cell"]))
            target["bbox"] = list(r["cell"]["bbox"])
        # Detector-only empty rows must not become business line items.
        if any(c["text"] for c in cells):
            rows.append({"kind": "header" if _header(raw) else
                         "total" if _total(raw) else "data", "cells": cells})
    return rows


def _number(row):
    text = row["cells"][0]["text"].strip() if row["cells"] else ""
    return int(text) if re.fullmatch(r"\d+", text) else None


def _description_only(row):
    return (row["kind"] == "data" and len(row["cells"]) > 1
            and bool(row["cells"][1]["text"].strip())
            and all(not c["text"].strip() for i, c in enumerate(row["cells"]) if i != 1))


def build_logical_tables(tables):
    """Derived view over immutable page fragments; no snapshot mutation.

    Automatic stitching requires adjacent pages in one document, a recognized
    header/grid, and row-number continuity (or a repeated matching header at page
    edges). Unknown layouts remain separate with an explicit review status.
    """
    output = []
    groups = defaultdict(list)
    for table in tables:
        groups[table["document_id"]].append(table)
    for fragments in groups.values():
        fragments = sorted(fragments, key=lambda t: (t["page_number"], t["bbox"][1]))
        active = None
        grid = None
        previous = None
        for table in fragments:
            mapped = _map_rows(table, grid) if grid else None
            adjacent = previous and table["page_number"] == previous["page_number"] + 1
            joined = False
            if active and adjacent and mapped and active["rows"]:
                last = active["rows"][-1]
                body = list(mapped)
                repeated = body[0]["kind"] == "header" and [
                    _label(c["text"]) for c in body[0]["cells"]
                ] == [_label(c["text"]) for c in active["rows"][0]["cells"]]
                if repeated:
                    body = body[1:]
                last_number = _number(last)
                first_number = _number(body[0]) if body else None
                split = bool(body and _description_only(body[0]) and last_number is not None)
                following = _number(body[1]) if split and len(body) > 1 else None
                sequence = last_number is not None and (
                    first_number == last_number + 1 or (split and following == last_number + 1)
                )
                edges = (previous["bbox"][3] >= BOTTOM_EDGE_THRESHOLD
                         and table["bbox"][1] <= TOP_EDGE_THRESHOLD)
                compatible_header = body and body[0]["kind"] != "header"
                if (last["kind"] != "total" and compatible_header
                        and (sequence or (repeated and edges and first_number is None))):
                    if repeated:
                        active["repeated_headers"].append(mapped[0])
                    if split and (sequence or edges):
                        continuation = body.pop(0)["cells"][1]
                        target = last["cells"][1]
                        target["text"] += " " + continuation["text"]
                        target["sources"].extend(continuation["sources"])
                    active["rows"].extend(body)
                    active["fragment_ids"].append(table["id"])
                    active["page_end"] = table["page_number"]
                    active["status"] = "RECONSTRUCTED"
                    joined = True
            if not joined:
                candidate = bool(adjacent and active and active["rows"]
                                 and active["rows"][-1]["kind"] != "total")
                grid = _grid(table)
                normalized = _map_rows(table, grid) if grid else None
                active = {"id": "logical:" + table["id"],
                          "document_id": table["document_id"],
                          "page_start": table["page_number"],
                          "page_end": table["page_number"],
                          "col_count": len(grid) if normalized else table["col_count"],
                          "fragment_ids": [table["id"]],
                          "status": "NEEDS_REVIEW" if candidate or
                          (grid is not None and normalized is None) else "STANDALONE",
                          "rows": normalized if normalized is not None else _raw_rows(table),
                          "repeated_headers": []}
                output.append(active)
            previous = table
    return output
