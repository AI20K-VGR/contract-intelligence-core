"""Cross-page table continuity (section 11): hard guards -> deterministic score ->
merge/split/needs_review.

No LLM gray-zone agent in this pass -- deterministic only, by explicit choice (see
docs/ai1-decisions.md D8). Anything the deterministic score cannot confidently resolve
becomes NEEDS_REVIEW rather than guessing or calling an API; that is a complete, honest
capability in its own right per the target design's own NEEDS_REVIEW state, not a stub
waiting on a gray-zone agent to be "really" finished.

Deliberately does NOT merge rows or cells across pages -- only records a decision +
reason codes linking two page-level `Table` objects. This is the same conservative
"link, don't merge" call `backend/app/tables.py`'s `link_continuations` already makes,
independently, for the identical real-world problem (see that module's own docstring).
Physically stitching rows together is left to whatever consumes this link, same as
`backend/app/tables.py` leaves it to the reviewer/UI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from contract_ocr.domain.entities import Table

Decision = Literal["MERGE", "SPLIT", "NEEDS_REVIEW"]

# Deliberately not fine-tuned against real scans (no ground truth exists yet -- see
# docs/ai1-decisions.md). A starting default in the same spirit as
# backend/app/tables.py's own thresholds for the same problem.
HIGH_THRESHOLD = 0.75
LOW_THRESHOLD = 0.35

# A table's bbox is normalized [0, 1] against its own page. These mirror
# backend/app/tables.py's BOTTOM_EDGE_THRESHOLD/TOP_EDGE_THRESHOLD -- loose on purpose
# (not "touching" 0/1): a detector's own bbox rarely sits flush against the physical
# page edge.
BOTTOM_EDGE_THRESHOLD = 0.85
TOP_EDGE_THRESHOLD = 0.15


@dataclass(frozen=True)
class ContinuityLink:
    from_table_id: str
    from_page: int
    to_table_id: str
    to_page: int
    decision: Decision
    confidence: float
    reason_codes: list[str] = field(default_factory=list)


def link_continuities(pages_tables: list[tuple[int, list[Table]]]) -> list[ContinuityLink]:
    """`pages_tables`: every page's `(page_number, tables_on_that_page)` in page order,
    tableless pages included as an empty list -- required so a table on page 3 and one
    on page 5 with nothing on page 4 are never compared as if adjacent."""
    links: list[ContinuityLink] = []
    previous_page: int | None = None
    previous_table: Table | None = None
    for page_number, tables in pages_tables:
        if not tables:
            previous_page, previous_table = None, None
            continue
        if previous_table is not None and page_number == previous_page + 1:
            links.append(_resolve(previous_table, previous_page, tables[0], page_number))
        previous_page, previous_table = page_number, tables[-1]
    return links


def _column_count(table: Table) -> int:
    if table.header:
        return len(table.header)
    return len(table.rows[0].cells) if table.rows else 0


def _link(
    prev: Table, prev_page: int, nxt: Table, nxt_page: int, decision, confidence, codes
) -> ContinuityLink:
    return ContinuityLink(
        prev.table_id, prev_page, nxt.table_id, nxt_page, decision, confidence, codes
    )


def _resolve(prev: Table, prev_page: int, nxt: Table, nxt_page: int) -> ContinuityLink:
    prev_cols, next_cols = _column_count(prev), _column_count(nxt)
    if prev_cols == 0 or next_cols == 0 or prev_cols != next_cols:
        return _link(prev, prev_page, nxt, nxt_page, "SPLIT", 1.0, ["INCOMPATIBLE_COLUMN_SCHEMA"])

    if prev.bbox is None or nxt.bbox is None:
        return _link(prev, prev_page, nxt, nxt_page, "NEEDS_REVIEW", 0.0, ["MISSING_GEOMETRY"])

    near_bottom = prev.bbox.y2 >= BOTTOM_EDGE_THRESHOLD
    near_top = nxt.bbox.y1 <= TOP_EDGE_THRESHOLD
    if not (near_bottom and near_top):
        return _link(prev, prev_page, nxt, nxt_page, "SPLIT", 1.0, ["NOT_AT_PAGE_EDGES"])

    reason_codes = ["TABLE_COLUMN_MATCH"]
    score = 0.5  # column schema matches AND both tables sit at the page's own edge
    header_repeated = bool(prev.header) and [c.strip().lower() for c in prev.header] == [
        c.strip().lower() for c in nxt.header
    ]
    if header_repeated:
        reason_codes.append("REPEATED_TABLE_HEADER")
        score += 0.3  # 0.8: strong evidence -> MERGE
    else:
        score += 0.1  # 0.6: plausible but unconfirmed -> NEEDS_REVIEW, not a guess

    if score >= HIGH_THRESHOLD:
        decision: Decision = "MERGE"
    elif score <= LOW_THRESHOLD:
        decision = "SPLIT"
    else:
        decision = "NEEDS_REVIEW"
        reason_codes.append("INSUFFICIENT_EVIDENCE")
    return _link(prev, prev_page, nxt, nxt_page, decision, score, reason_codes)
