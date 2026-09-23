"""Deterministic boundary resolution (section 7 / section 19 decision
procedure). Runs before any LLM call.

`resolve_by_rule` returns `None` when the available signals are not
conclusive — the caller (pipeline) then decides whether to fall back to the
LLM resolver or mark the boundary for human review. It never guesses.
"""

from __future__ import annotations

import re

from . import clause_parser
from .clause_parser import (
    ALPHA_CLOSE_PAREN,
    ALPHA_PAREN,
    DECIMAL,
    KHOAN_LABEL,
    NUMBER_PAREN,
    ROMAN_PAREN,
    SECTION,
)
from .config import compute_final_confidence
from .models import (
    Action,
    BoundaryContext,
    ClauseMarker,
    EntityType,
    ReasonCode,
    ReconstructionAction,
    ReconstructionTarget,
    Relationship,
    ResolutionMethod,
    ScoreBreakdown,
    SourceBlockRef,
)
from .schemas.block import TABLE_ROW, Block
from .table_merger import RawTable, RawTableRow, is_incomplete_row, parse_cells, tables_continue

_ELLIPSIS_RE = re.compile(r"(\.\s*){3,}$|…\s*$")
_TERMINAL_RE = re.compile(r"[.!?:;][\"'”’)\]]*$")

_ALPHA_FAMILY = {ALPHA_PAREN, ALPHA_CLOSE_PAREN}
_ROMAN_FAMILY = {ROMAN_PAREN}
_NUMBER_FAMILY = {NUMBER_PAREN}
_CLAUSE_TIER0_TYPES = {DECIMAL, KHOAN_LABEL}

_ROMAN_VALUES = {
    "i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10,
    "xi": 11, "xii": 12, "xiii": 13, "xiv": 14, "xv": 15, "xvi": 16, "xvii": 17, "xviii": 18,
    "xix": 19, "xx": 20,
}


def ends_with_sentence_punctuation(text: str) -> bool:
    """True if `text` ends with clear terminal punctuation. A trailing
    ellipsis ("...", "…") signals the sentence trails off / continues, so it
    is treated as NOT terminal."""
    stripped = text.rstrip()
    if not stripped:
        return False
    if _ELLIPSIS_RE.search(stripped):
        return False
    return bool(_TERMINAL_RE.search(stripped))


def starts_like_new_sentence(text: str) -> bool:
    """True only when the text clearly opens a brand-new sentence (starts
    with an uppercase letter). Digits and lowercase letters are treated as
    compatible with continuing the previous sentence/phrase."""
    stripped = text.lstrip()
    if not stripped:
        return False
    return stripped[0].isupper()


def _typography_compatible(previous: Block, next_block: Block) -> bool:
    if previous.font_size is not None and next_block.font_size is not None:
        if abs(previous.font_size - next_block.font_size) > 1.0:
            return False
    if previous.bold is not None and next_block.bold is not None:
        if previous.bold != next_block.bold:
            return False
    return True


def _near_bottom(block: Block, page_height: float, band: float = 0.2) -> bool:
    return page_height > 0 and block.y1 >= (1 - band) * page_height


def _near_top(block: Block, page_height: float, band: float = 0.2) -> bool:
    return page_height > 0 and block.y0 <= band * page_height


def _list_family(marker_type: str) -> set[str] | None:
    if marker_type in _ALPHA_FAMILY:
        return _ALPHA_FAMILY
    if marker_type in _ROMAN_FAMILY:
        return _ROMAN_FAMILY
    if marker_type in _NUMBER_FAMILY:
        return _NUMBER_FAMILY
    return None


def _is_list_successor(previous: ClauseMarker, next_marker: ClauseMarker) -> bool:
    family = _list_family(previous.marker_type)
    if family is None or next_marker.marker_type not in family:
        return False
    if family is _NUMBER_FAMILY:
        try:
            return int(next_marker.normalized) == int(previous.normalized) + 1
        except ValueError:
            return False
    if family is _ROMAN_FAMILY:
        prev_val = _ROMAN_VALUES.get(previous.normalized)
        next_val = _ROMAN_VALUES.get(next_marker.normalized)
        return prev_val is not None and next_val is not None and next_val == prev_val + 1
    # alpha family: single-letter successor (a -> b, ..., y -> z)
    if len(previous.normalized) == 1 and len(next_marker.normalized) == 1:
        return ord(next_marker.normalized) == ord(previous.normalized) + 1
    return False


def _decision(
    action: Action,
    relationship: Relationship | None,
    entity_type: EntityType,
    context: BoundaryContext,
    scores: ScoreBreakdown,
    reason_codes: list[ReasonCode],
    source_blocks: list[SourceBlockRef],
    target: ReconstructionTarget | None = None,
) -> ReconstructionAction:
    confidence = compute_final_confidence(scores)
    return ReconstructionAction(
        action=action,
        relationship=relationship,
        entity_type=entity_type,
        source_blocks=source_blocks,
        target=target,
        reason_codes=reason_codes,
        confidence=confidence,
        requires_review=False,
        method=ResolutionMethod.RULE,
        scores=scores,
    )


def _block_ref(page: int, block: Block) -> SourceBlockRef:
    return SourceBlockRef(page=page, block_id=block.block_id, bbox=block.bbox)


def _resolve_table(context: BoundaryContext) -> ReconstructionAction | None:
    previous_rows = [b for b in context.previous_blocks if b.type == TABLE_ROW]
    next_rows = [b for b in context.next_blocks if b.type == TABLE_ROW]
    if not previous_rows or not next_rows:
        return None

    previous_table = RawTable(
        page=context.previous_page,
        rows=[RawTableRow(block=b, cells=parse_cells(b.text)) for b in previous_rows],
    )
    next_table = RawTable(
        page=context.next_page,
        rows=[RawTableRow(block=b, cells=parse_cells(b.text)) for b in next_rows],
    )
    is_continuation, table_confidence = tables_continue(previous_table, next_table)
    if not is_continuation:
        return None

    last_row = previous_table.rows[-1]
    first_row = next_table.rows[0]
    table_id = context.document_state.active_table

    reason_codes = [ReasonCode.TABLE_COLUMN_MATCH, ReasonCode.BOTTOM_TO_TOP]
    if table_confidence >= 0.9:
        reason_codes.append(ReasonCode.TABLE_HEADER_MATCH)
    else:
        reason_codes.append(ReasonCode.TABLE_LAYOUT_MATCH)

    # Broadcast the single table-continuity signal across all four
    # deterministic dimensions: for a table, column-count/header alignment
    # *is* the layout, numbering and continuity evidence all at once.
    scores = ScoreBreakdown(
        rule_score=table_confidence,
        layout_score=table_confidence,
        numbering_score=table_confidence,
        text_continuity_score=table_confidence,
    )

    if is_incomplete_row(last_row.cells):
        # A specific row was split by the page break (section 7/16): the
        # more precise ROW_CONTINUE/CONTINUE_ROW signal, scoped to that row.
        reason_codes.append(ReasonCode.INCOMPLETE_TABLE_ROW)
        source_blocks = [
            SourceBlockRef(page=context.previous_page, table_id=table_id, row_id=last_row.block.block_id),
            SourceBlockRef(page=context.next_page, table_id=table_id, row_id=first_row.block.block_id),
        ]
        return _decision(
            Action.CONTINUE_ROW,
            Relationship.ROW_CONTINUE,
            EntityType.TABLE_ROW,
            context,
            scores,
            reason_codes,
            source_blocks,
            target=ReconstructionTarget(table_id=table_id),
        )

    # Whole-table continuation with no row actually split: MERGE_TABLE the
    # first time two table objects are fused, CONTINUE_TABLE for a later
    # page that simply extends an already-unified table (`active_table`
    # already set — section 6's "previous active structural node").
    action = Action.CONTINUE_TABLE if table_id else Action.MERGE_TABLE
    source_blocks = [_block_ref(context.previous_page, last_row.block), _block_ref(context.next_page, first_row.block)]
    return _decision(
        action,
        Relationship.TABLE_CONTINUE,
        EntityType.TABLE,
        context,
        scores,
        reason_codes,
        source_blocks,
        target=ReconstructionTarget(table_id=table_id),
    )


def _resolve_list(
    context: BoundaryContext,
    previous: Block,
    next_block: Block,
    previous_marker: ClauseMarker | None,
    next_marker: ClauseMarker | None,
) -> ReconstructionAction | None:
    if previous_marker is None or next_marker is None:
        return None
    if not _is_list_successor(previous_marker, next_marker):
        return None
    # An exact successor in the same marker family (a -> b, i -> ii, 1 -> 2)
    # is as unambiguous as boundary signals get.
    scores = ScoreBreakdown(
        rule_score=1.0, layout_score=1.0, numbering_score=1.0, text_continuity_score=1.0
    )
    parent = context.document_state.active_clause or context.document_state.active_section
    node_id = f"{parent}.{next_marker.normalized}" if parent else next_marker.normalized
    return _decision(
        Action.CONTINUE_LIST,
        Relationship.LIST_CONTINUE,
        EntityType.LIST_ITEM,
        context,
        scores,
        [ReasonCode.LIST_SEQUENCE, ReasonCode.NUMBERING_SEQUENCE],
        [_block_ref(context.previous_page, previous), _block_ref(context.next_page, next_block)],
        target=ReconstructionTarget(node_id=node_id, parent_id=parent),
    )


def _resolve_new_marker(
    context: BoundaryContext, previous: Block, next_block: Block, next_marker: ClauseMarker
) -> ReconstructionAction:
    # A leading numbering token that clause_parser recognizes unambiguously
    # is itself strong evidence for *all* four dimensions: it is precisely
    # the discontinuity (a fresh marker, an implied layout/indent reset)
    # that makes this a confident call.
    scores = ScoreBreakdown(
        rule_score=1.0, layout_score=1.0, numbering_score=1.0, text_continuity_score=1.0
    )
    reason_codes = [ReasonCode.NEW_NUMBERING]
    source_blocks = [_block_ref(context.previous_page, previous), _block_ref(context.next_page, next_block)]
    state = context.document_state

    if next_marker.marker_type == SECTION:
        target = ReconstructionTarget(node_id=next_marker.normalized, parent_id=None)
        return _decision(
            Action.NEW_SECTION, Relationship.NEW_SECTION, EntityType.SECTION, context, scores,
            [*reason_codes, ReasonCode.NEW_HEADING], source_blocks, target,
        )

    if next_marker.marker_type in _CLAUSE_TIER0_TYPES:
        target = ReconstructionTarget(node_id=next_marker.normalized, parent_id=state.active_section)
        return _decision(
            Action.NEW_CLAUSE, Relationship.NEW_CLAUSE, EntityType.CLAUSE, context, scores,
            reason_codes, source_blocks, target,
        )

    # A list-family marker (alpha/roman/number-paren) that isn't a sequence
    # successor of the previous block (checked earlier) is the first item of
    # a fresh list: attach it under whatever clause/section is open now
    # (section 6's priority order: numbering, then the active structural
    # node — never semantic guessing).
    parent = state.active_clause or state.active_section
    node_id = f"{parent}.{next_marker.normalized}" if parent else next_marker.normalized
    target = ReconstructionTarget(node_id=node_id, parent_id=parent)
    return _decision(
        Action.ATTACH_CHILD, Relationship.NEW_CLAUSE, EntityType.LIST_ITEM, context, scores,
        reason_codes, source_blocks, target,
    )


def _resolve_continuation(
    context: BoundaryContext, previous: Block, next_block: Block, previous_marker: ClauseMarker | None
) -> ReconstructionAction | None:
    previous_terminal = ends_with_sentence_punctuation(previous.text)
    next_new_sentence = starts_like_new_sentence(next_block.text)
    typography_ok = _typography_compatible(previous, next_block)
    source_blocks = [_block_ref(context.previous_page, previous), _block_ref(context.next_page, next_block)]
    state = context.document_state

    if not previous_terminal and not next_new_sentence:
        reason_codes = [ReasonCode.NO_END_PUNCTUATION]
        if _near_bottom(previous, context.previous_page_height) and _near_top(next_block, context.next_page_height):
            reason_codes.append(ReasonCode.BOTTOM_TO_TOP)
        if typography_ok:
            reason_codes.append(ReasonCode.SAME_STYLE)
        # Clean signal (no terminal punctuation + a lowercase/neutral start)
        # with compatible typography is as confident as a mid-sentence split
        # gets. A typography mismatch is treated as weaker evidence — on its
        # own it stays below the "strong" band (no auto-merge, section 20),
        # but is not zero: a confirming LLM call can still tip it over.
        confident = 1.0 if typography_ok else 0.89
        scores = ScoreBreakdown(
            rule_score=confident, layout_score=confident, numbering_score=confident,
            text_continuity_score=confident,
        )

        if previous_marker is not None:
            # The clause is still open (its own opening block is what we're
            # splicing onto) — same clause, tight text merge.
            reason_codes.append(ReasonCode.SAME_ACTIVE_CLAUSE)
            target = ReconstructionTarget(node_id=state.active_clause, parent_id=state.active_section)
            return _decision(
                Action.MERGE_BLOCKS, Relationship.CONTINUE_CLAUSE, EntityType.CLAUSE, context,
                scores, reason_codes, source_blocks, target,
            )
        if state.active_clause is not None:
            # No marker on either block, but a clause is already open: still
            # a paragraph-level splice, scoped to that clause.
            reason_codes.append(ReasonCode.SAME_ACTIVE_CLAUSE)
            target = ReconstructionTarget(node_id=state.active_clause, parent_id=state.active_section)
            return _decision(
                Action.MERGE_BLOCKS, Relationship.CONTINUE_CLAUSE, EntityType.CLAUSE, context,
                scores, reason_codes, source_blocks, target,
            )
        target = ReconstructionTarget(node_id=state.active_section) if state.active_section else None
        return _decision(
            Action.MERGE_BLOCKS, Relationship.CONTINUE_PARAGRAPH, EntityType.PARAGRAPH, context,
            scores, reason_codes, source_blocks, target,
        )

    if previous_terminal and next_new_sentence:
        scores = ScoreBreakdown(
            rule_score=1.0, layout_score=1.0, numbering_score=1.0, text_continuity_score=1.0
        )
        reason_codes = [ReasonCode.HAS_END_PUNCTUATION, ReasonCode.NEW_HEADING]
        return _decision(
            Action.NEW_PARAGRAPH, Relationship.NEW_PARAGRAPH, EntityType.PARAGRAPH, context,
            scores, reason_codes, source_blocks,
        )

    # Mixed signals (e.g. terminal punctuation but lowercase-looking next
    # text, or vice versa): not confident enough to decide deterministically.
    return None


def resolve_by_rule(context: BoundaryContext) -> ReconstructionAction | None:
    """Apply the boundary rules (section 4-9) plus list/table continuation.
    Returns `None` when the signals are not conclusive, so the caller can
    fall back to the LLM resolver (section 19's decision procedure)."""
    if table_decision := _resolve_table(context):
        return table_decision

    if not context.previous_blocks or not context.next_blocks:
        return None

    previous = context.previous_blocks[-1]
    next_block = context.next_blocks[0]
    previous_marker = clause_parser.parse_marker(previous.text)
    next_marker = clause_parser.parse_marker(next_block.text)

    if list_decision := _resolve_list(context, previous, next_block, previous_marker, next_marker):
        return list_decision

    if next_marker is not None:
        return _resolve_new_marker(context, previous, next_block, next_marker)

    return _resolve_continuation(context, previous, next_block, previous_marker)
