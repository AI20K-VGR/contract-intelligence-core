"""Cross-page table continuity (section 11): hard guards -> deterministic score ->
optional LLM agent for the remaining gray zone -> merge/split/needs_review.

Deliberately does NOT merge rows or cells across pages -- only records a decision +
reason codes linking two page-level `Table` objects. This is the same conservative
"link, don't merge" call `backend/app/tables.py`'s `link_continuations` already makes,
independently, for the identical real-world problem (see that module's own docstring).
Physically stitching rows together is left to whatever consumes this link, same as
`backend/app/tables.py` leaves it to the reviewer/UI.

The LLM gray-zone agent (`_ask_agent`) mirrors `backend/app/table_continuity.py`'s own
DeepSeek agent as closely as this module's simpler (link-only) shape allows: same
system prompt, same metadata-plus-at-most-2-short-row-previews payload (never a full
table, never a page image), same DeepSeek OpenAI-wire-compatible client, same
never-raise contract (a missing key, disabled config, timeout, or malformed response
all degrade to None, and the caller then keeps its NEEDS_REVIEW decision rather than
guessing). Opt-in per call via `config={"table_continuity_agent": True}` -- off by
default, so `link_continuities(pages_tables)` with no config reproduces the exact
deterministic-only behavior this module started with.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Literal

from contract_ocr.domain.entities import Row, Table
from contract_ocr.domain.headings import is_annex_heading

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

_MAX_ROW_PREVIEW_CHARS = 60
_MAX_ROW_PREVIEWS = 2


@dataclass(frozen=True)
class ContinuityLink:
    from_table_id: str
    from_page: int
    to_table_id: str
    to_page: int
    decision: Decision
    confidence: float
    reason_codes: list[str] = field(default_factory=list)


def link_continuities(
    pages_tables: list[tuple[int, list[Table]]], config: dict | None = None
) -> list[ContinuityLink]:
    """`pages_tables`: every page's `(page_number, tables_on_that_page)` in page order,
    tableless pages included as an empty list -- required so a table on page 3 and one
    on page 5 with nothing on page 4 are never compared as if adjacent. `config` is
    opt-in-per-call settings, currently only `table_continuity_agent` (bool, default
    off) -- see module docstring."""
    config = config or {}
    links: list[ContinuityLink] = []
    previous_page: int | None = None
    previous_table: Table | None = None
    for page_number, tables in pages_tables:
        if not tables:
            previous_page, previous_table = None, None
            continue
        if previous_table is not None and page_number == previous_page + 1:
            links.append(_resolve(previous_table, previous_page, tables[0], page_number, config))
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


def _label(text: str) -> str:
    """Diacritic-stripped, whitespace-free lowercase form, for comparing a cell's text
    against a fixed set of known Vietnamese labels regardless of accents/spacing --
    mirrors `backend/app/tables.py`'s own `_label`."""
    normalized = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    return re.sub(r"\s+", "", "".join(c for c in normalized if not unicodedata.combining(c)))


_TOTAL_LABELS = {"tongcong", "tong", "cong", "total", "grandtotal"}


def _row_is_total(row: Row) -> bool:
    return any(_label(c.text) in _TOTAL_LABELS for c in row.cells if c.text.strip())


def _numeric_anchor(text: str) -> int | None:
    stripped = text.strip()
    return int(stripped) if re.fullmatch(r"\d{1,3}", stripped) else None


def _first_anchor(table: Table) -> int | None:
    """The first row's own leading-column numeric value (the STT/sequence-number
    column, assumed to be column 0 -- the common case for a Vietnamese item table).
    None when no row has one, not when it's genuinely absent from the schema."""
    for row in table.rows:
        if row.cells:
            value = _numeric_anchor(row.cells[0].text)
            if value is not None:
                return value
    return None


def _last_anchor(table: Table) -> int | None:
    for row in reversed(table.rows):
        if row.cells:
            value = _numeric_anchor(row.cells[0].text)
            if value is not None:
                return value
    return None


def _row_preview(row: Row) -> str:
    return " | ".join(c.text.strip() for c in row.cells if c.text.strip())[:_MAX_ROW_PREVIEW_CHARS]


def _hard_guard(prev: Table, nxt: Table) -> tuple[Decision, list[str]] | None:
    """Cases that never need scoring or the agent: the answer is certain from a
    single signal. Returns None when nothing here applies, so the caller falls
    through to the column/edge checks and rule score."""
    if prev.rows and _row_is_total(prev.rows[-1]):
        return "SPLIT", ["PREVIOUS_TABLE_ALREADY_TOTALED"]
    if nxt.heading_before and is_annex_heading(nxt.heading_before):
        return "SPLIT", ["NEW_SECTION_HEADING"]
    first_anchor, last_anchor = _first_anchor(nxt), _last_anchor(prev)
    if first_anchor == 1 and (last_anchor or 0) > 1:
        return "SPLIT", ["ANCHOR_RESET"]
    return None


_AGENT_SYSTEM_PROMPT = """\
You are a Table Continuity judge for scanned contract tables. You are given ONLY a \
small metadata packet about two table fragments found on consecutive pages — never \
the full table and never an image. Decide whether fragment B is a direct continuation \
of fragment A (MERGE), a different table (SPLIT), or genuinely unclear from the \
evidence given (NEEDS_REVIEW). Prefer NEEDS_REVIEW over guessing when the evidence is \
insufficient or conflicting. Respond with strict JSON only:
{"decision": "merge" | "split" | "needs_review", "reasons": [string, ...]}"""


def _ask_agent(payload: dict) -> tuple[Decision, list[str]] | None:
    """Consults the DeepSeek-hosted agent for a genuinely ambiguous pair. Never
    raises: a missing key, timeout, rate limit, or malformed response all degrade to
    None -- the caller then keeps its NEEDS_REVIEW decision rather than guessing.
    Reads `DEEPSEEK_API_KEY`/`DEEPSEEK_BASE_URL`/`DEEPSEEK_MODEL` from the
    environment, the same convention `infrastructure/ocr/mistral_ocr.py` uses for
    `MISTRAL_API_KEY` -- ai-service has no pydantic-settings object for this.
    """
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=api_key,
            base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        )
        response = client.chat.completions.create(
            model=os.environ.get("DEEPSEEK_MODEL", "deepseek-flash"),
            temperature=0,
            max_tokens=512,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _AGENT_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        )
        data = json.loads(response.choices[0].message.content or "{}")
        decision = {"merge": "MERGE", "split": "SPLIT", "needs_review": "NEEDS_REVIEW"}.get(
            str(data.get("decision", "")).lower()
        )
        if decision is None:
            return None
        return decision, [str(r) for r in data.get("reasons") or []]
    except Exception:
        return None


def _resolve(
    prev: Table, prev_page: int, nxt: Table, nxt_page: int, config: dict
) -> ContinuityLink:
    guard = _hard_guard(prev, nxt)
    if guard is not None:
        decision, codes = guard
        return _link(prev, prev_page, nxt, nxt_page, decision, 1.0, codes)

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

    last_anchor, first_anchor = _last_anchor(prev), _first_anchor(nxt)
    anchor_continuous = (
        last_anchor is not None and first_anchor is not None and first_anchor == last_anchor + 1
    )
    if anchor_continuous:
        reason_codes.append("ANCHOR_CONTINUOUS")
        score += 0.3  # matches backend/app/table_continuity.py's own weighting: the
        # sequence-number signal is as strong as the column/header match, not a minor
        # bonus -- a fresh page picking up right where the STT column left off is
        # rarely a coincidence.
    # `confidence` is a [0, 1] field on the emitted snapshot (domain/snapshot.py) --
    # header-repeated (+0.3) and anchor-continuous (+0.3) can both fire on the same
    # pair, which would otherwise push the raw additive score to 1.1.
    score = min(score, 1.0)

    if score >= HIGH_THRESHOLD:
        decision: Decision = "MERGE"
    elif score <= LOW_THRESHOLD:
        decision = "SPLIT"
    else:
        decision = "NEEDS_REVIEW"
        reason_codes.append("INSUFFICIENT_EVIDENCE")
        if config.get("table_continuity_agent"):
            agent_result = _ask_agent(
                {
                    "page_gap": nxt_page - prev_page,
                    "column_similarity": 1.0 if prev_cols == next_cols else 0.0,
                    "header_repeated": header_repeated,
                    "last_anchor": last_anchor,
                    "first_anchor": first_anchor,
                    "anchor_continuous": anchor_continuous,
                    "previous_ends_near_bottom": near_bottom,
                    "next_starts_near_top": near_top,
                    "heading_between": nxt.heading_before,
                    "previous_tail_rows": [_row_preview(r) for r in prev.rows[-_MAX_ROW_PREVIEWS:]],
                    "next_head_rows": [_row_preview(r) for r in nxt.rows[:_MAX_ROW_PREVIEWS]],
                }
            )
            if agent_result is not None:
                decision, agent_reasons = agent_result
                reason_codes = [*reason_codes, "AGENT_CONSULTED", *agent_reasons]

    return _link(prev, prev_page, nxt, nxt_page, decision, score, reason_codes)
