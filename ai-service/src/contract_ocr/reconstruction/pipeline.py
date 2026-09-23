"""The reconstruction pipeline: pages in, `ReconstructedDocument` out.

See the module README for the full flow diagram. In short:

    normalize blocks -> header/footer detection -> per-boundary resolution
    (rule engine, falling back to the LLM resolver only when unsure,
    threading the live `DocumentState` through both) -> deterministic
    execution of the proposed action (merge text / attach child / stitch
    table) -> ReconstructedDocument (with review items for anything the
    pipeline refused to guess).

This is the deterministic executor side of "LLM decides relationship. Code
performs mutation." — `rule_engine`/`llm_resolver` only ever *propose* a
`ReconstructionAction`; this module is what actually mutates state.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import clause_parser
from .boundary_detector import detect_boundary
from .clause_parser import TIER
from .config import compute_final_confidence, is_confident
from .header_footer_detector import HeaderFooterProfile, detect_header_footer
from .hierarchy_builder import LogicalSegment, build_hierarchy
from .llm_resolver import BoundaryLLMResolver, MockLLMResolver
from .logging_events import log_event
from .models import (
    Action,
    BoundaryContext,
    DocumentState,
    ReasonCode,
    ReconstructionAction,
    Relationship,
    ResolutionMethod,
    ScoreBreakdown,
    SourceBlockRef,
)
from .paragraph_merger import extend_merge
from .provenance import TextFragment
from .rule_engine import resolve_by_rule
from .schemas.block import TABLE_ROW, Block
from .schemas.document import DocumentMetadata, ReconstructedDocument, ReviewItem, Table
from .schemas.page import Page
from .table_merger import RawTable, build_table, extract_raw_tables, tables_continue

__all__ = ["reconstruct_document", "resolve_boundary"]

_TABLE_CONTINUATION_RELATIONSHIPS = frozenset({Relationship.TABLE_CONTINUE, Relationship.ROW_CONTINUE})


def _resolve(context: BoundaryContext, resolver: BoundaryLLMResolver) -> ReconstructionAction:
    """The section-19 decision procedure: try the rule engine; if (and only
    if) it isn't confident enough, consult the LLM resolver; if the blended
    result still isn't confident enough, surface `NEEDS_REVIEW` rather than
    guessing (section 20)."""
    rule_action = resolve_by_rule(context)

    if rule_action is not None and is_confident(rule_action.confidence):
        log_event(
            "boundary.rule_resolved",
            document_id=context.document_id,
            page_from=context.previous_page,
            page_to=context.next_page,
            action=rule_action.action.value,
            confidence=rule_action.confidence,
        )
        return rule_action

    log_event(
        "boundary.detected",
        document_id=context.document_id,
        page_from=context.previous_page,
        page_to=context.next_page,
        rule_confidence=rule_action.confidence if rule_action else 0.0,
    )

    base_scores = rule_action.scores if rule_action is not None else ScoreBreakdown()
    llm_action = resolver.resolve(context)
    combined_scores = base_scores.model_copy(update={"model_score": llm_action.scores.model_score})
    final_score = compute_final_confidence(combined_scores)

    reason_codes = list(
        dict.fromkeys((rule_action.reason_codes if rule_action else []) + llm_action.reason_codes)
    )

    if not is_confident(final_score):
        candidates = {llm_action.relationship}
        if rule_action is not None:
            candidates.add(rule_action.relationship)
        candidates.discard(None)
        candidates.discard(Relationship.UNKNOWN)
        possible_relationships = sorted(candidates, key=lambda r: r.value)
        log_event(
            "boundary.needs_review",
            document_id=context.document_id,
            page_from=context.previous_page,
            page_to=context.next_page,
            possible_relationships=[r.value for r in possible_relationships],
            confidence=final_score,
        )
        return ReconstructionAction(
            action=Action.NEEDS_REVIEW,
            relationship=Relationship.UNKNOWN,
            entity_type=llm_action.entity_type,
            source_blocks=llm_action.source_blocks,
            target=None,
            reason_codes=reason_codes or [ReasonCode.INSUFFICIENT_EVIDENCE],
            confidence=final_score,
            requires_review=True,
            method=ResolutionMethod.LLM,
            scores=combined_scores,
            possible_relationships=possible_relationships,
        )

    log_event(
        "boundary.llm_resolved",
        document_id=context.document_id,
        page_from=context.previous_page,
        page_to=context.next_page,
        action=llm_action.action.value,
        confidence=final_score,
    )
    return llm_action.model_copy(
        update={
            "confidence": final_score,
            "scores": combined_scores,
            "reason_codes": reason_codes,
            "requires_review": False,
        }
    )


def resolve_boundary(
    previous_page: Page,
    next_page: Page,
    *,
    header_footer: HeaderFooterProfile | None = None,
    document_state: DocumentState | None = None,
    llm_resolver: BoundaryLLMResolver | None = None,
) -> ReconstructionAction:
    """Resolve the relationship between the end of `previous_page` and the
    start of `next_page`. Public API.

    Rule-based resolution always runs first; the LLM resolver (a
    deterministic mock by default, so calling this never makes a network
    request unless the caller opts in) is only consulted when the rule
    engine is not confident enough. `document_state` may be omitted for a
    standalone call — the boundary is then resolved with no hierarchy
    context (as if nothing were open yet).
    """
    profile = header_footer or detect_header_footer([previous_page, next_page])
    resolver = llm_resolver or MockLLMResolver()
    context = detect_boundary(previous_page, next_page, profile, document_state)
    return _resolve(context, resolver)


def _content_blocks(page: Page, header_footer: HeaderFooterProfile) -> list[Block]:
    return [
        b for b in page.blocks if not header_footer.is_noise(b, page) and b.type != TABLE_ROW
    ]


class _DocumentStateTracker:
    """Tracks the live active section/clause/list markers by scanning
    content blocks in document order — independent of, and simpler than,
    `hierarchy_builder`'s full tree (which is built separately, after all
    boundaries are resolved). Table state is tracked alongside it by the
    pipeline's main loop, since tables are a wholly separate structure.
    """

    def __init__(self) -> None:
        self._section: str | None = None
        self._clause: str | None = None
        self._list: str | None = None

    def observe(self, text: str) -> None:
        marker = clause_parser.parse_marker(text)
        if marker is None:
            return
        tier = TIER[marker.marker_type]
        if tier == 0:
            if marker.marker_type == clause_parser.SECTION:
                self._section = marker.normalized
                self._clause = None
            else:
                self._clause = marker.normalized
            self._list = None
        else:
            self._list = marker.raw

    def state(self, active_table: str | None) -> DocumentState:
        return DocumentState(
            active_section=self._section,
            active_clause=self._clause,
            active_list=self._list,
            active_table=active_table,
        )


@dataclass
class _PendingSegment:
    """The tail of the pages processed so far: not yet finalized, because it
    might still absorb the first block of the next page. Kept as its own
    accumulating state — not a raw `Block` — so a paragraph that keeps
    continuing across three or more pages merges correctly instead of
    silently losing the earlier pages' contribution."""

    text: str
    refs: list[SourceBlockRef]
    page_start: int
    page_end: int
    was_merged: bool
    method: ResolutionMethod
    confidence: float

    def to_segment(self) -> LogicalSegment:
        return LogicalSegment(
            text=self.text,
            page_start=self.page_start,
            page_end=self.page_end,
            source_blocks=self.refs,
            was_merged=self.was_merged,
            method=self.method,
            confidence=self.confidence,
        )


def _seed_pending(page_number: int, block: Block) -> _PendingSegment:
    text, refs = extend_merge("", [], TextFragment(page_number, block.block_id, block.text))
    return _PendingSegment(
        text=text,
        refs=refs,
        page_start=page_number,
        page_end=page_number,
        was_merged=False,
        method=ResolutionMethod.RULE,
        confidence=1.0,
    )


def _build_segments(
    pages: list[Page],
    header_footer: HeaderFooterProfile,
    boundary_actions: dict[tuple[int, int], ReconstructionAction],
) -> list[LogicalSegment]:
    """Deterministically execute every `MERGE_BLOCKS` action: splice the raw
    text of the last block of page N with the first block of page N+1.
    Every other action (`NEW_CLAUSE`, `ATTACH_CHILD`, `CONTINUE_LIST`, ...)
    leaves both blocks as their own segments — `clause_parser` and
    `hierarchy_builder` place them from their own numbering afterward.
    """
    segments: list[LogicalSegment] = []
    pending: _PendingSegment | None = None

    def flush() -> None:
        nonlocal pending
        if pending is not None:
            segments.append(pending.to_segment())
            pending = None

    for page in pages:
        blocks = _content_blocks(page, header_footer)
        if not blocks:
            continue

        start_index = 0
        if pending is not None:
            action = boundary_actions.get((pending.page_end, page.page))
            if action is not None and action.action == Action.MERGE_BLOCKS:
                first_block = blocks[0]
                text, refs = extend_merge(
                    pending.text,
                    pending.refs,
                    TextFragment(page.page, first_block.block_id, first_block.text),
                )
                pending = _PendingSegment(
                    text=text,
                    refs=refs,
                    page_start=pending.page_start,
                    page_end=page.page,
                    was_merged=True,
                    method=action.method,
                    confidence=min(pending.confidence, action.confidence),
                )
                start_index = 1
            else:
                flush()

        for block in blocks[start_index:-1]:
            segments.append(_seed_pending(page.page, block).to_segment())

        if start_index >= len(blocks):
            # This page's only content block was just merged into `pending`;
            # it also stands as this page's tail, so leave it pending.
            continue

        flush()
        pending = _seed_pending(page.page, blocks[-1])

    flush()
    return segments


def _build_tables(
    pages: list[Page],
    header_footer: HeaderFooterProfile,
    boundary_actions: dict[tuple[int, int], ReconstructionAction],
    table_id_by_page: dict[int, str],
) -> list[Table]:
    raw_tables_by_page: dict[int, list[RawTable]] = {
        page.page: extract_raw_tables(page, header_footer) for page in pages
    }

    chains: list[list[RawTable]] = []
    chain_ids: list[str] = []
    open_chain: list[RawTable] | None = None
    open_chain_id: str | None = None

    for index, page in enumerate(pages):
        page_tables = raw_tables_by_page[page.page]
        if not page_tables:
            open_chain = None
            open_chain_id = None
            continue

        continues_from_previous = False
        if open_chain is not None and index > 0:
            previous_page = pages[index - 1]
            action = boundary_actions.get((previous_page.page, page.page))
            if action is not None and action.relationship in _TABLE_CONTINUATION_RELATIONSHIPS:
                is_continuation, _ = tables_continue(open_chain[-1], page_tables[0])
                if is_continuation:
                    open_chain.append(page_tables[0])
                    continues_from_previous = True

        if not continues_from_previous:
            if open_chain is not None:
                chains.append(open_chain)
                chain_ids.append(open_chain_id)
            open_chain = [page_tables[0]]
            open_chain_id = table_id_by_page.get(page.page, f"table_{len(chains) + 1:02d}")

        for table in page_tables[1:]:
            if open_chain is not None:
                chains.append(open_chain)
                chain_ids.append(open_chain_id)
            open_chain = [table]
            open_chain_id = f"table_{len(chains) + 1:02d}"

    if open_chain is not None:
        chains.append(open_chain)
        chain_ids.append(open_chain_id)

    tables: list[Table] = []
    for chain, table_id in zip(chains, chain_ids, strict=True):
        table = build_table(table_id, chain)
        tables.append(table)
        log_event(
            "table.continuation_detected" if len(chain) > 1 else "table.detected",
            page_start=table.page_start,
            page_end=table.page_end,
            table_id=table.table_id,
        )
        if len(chain) > 1:
            log_event("table.rows_merged", table_id=table.table_id, row_count=len(table.rows))
    return tables


def reconstruct_document(
    pages: list[Page], *, llm_resolver: BoundaryLLMResolver | None = None
) -> ReconstructedDocument:
    """Reconstruct the logical structure of a contract from its page-level
    OCR output. Public API.

    Never re-OCRs the document and never rewrites its content: every
    clause/table produced here traces back to specific `(page, block_id)`
    source blocks (`source_blocks`), and any boundary the pipeline is not
    confident about is reported in `review_items` instead of being merged.
    """
    if not pages:
        raise ValueError("reconstruct_document requires at least one page")

    ordered_pages = sorted(pages, key=lambda p: p.page)
    document_id = ordered_pages[0].document_id
    resolver = llm_resolver or MockLLMResolver()
    header_footer = detect_header_footer(ordered_pages)
    raw_tables_by_page = {p.page: extract_raw_tables(p, header_footer) for p in ordered_pages}

    tracker = _DocumentStateTracker()
    active_table_id: str | None = None
    table_id_by_page: dict[int, str] = {}
    table_counter = 0

    boundary_actions: dict[tuple[int, int], ReconstructionAction] = {}
    review_items: list[ReviewItem] = []

    for index, page in enumerate(ordered_pages):
        if index > 0:
            previous_page = ordered_pages[index - 1]
            state = tracker.state(active_table_id)
            context = detect_boundary(previous_page, page, header_footer, state)
            action = _resolve(context, resolver)
            boundary_actions[(previous_page.page, page.page)] = action

            if action.relationship not in _TABLE_CONTINUATION_RELATIONSHIPS:
                active_table_id = None
            if action.requires_review:
                review_items.append(
                    ReviewItem(
                        previous_page=previous_page.page,
                        next_page=page.page,
                        possible_relationships=action.possible_relationships or [Relationship.UNKNOWN],
                        source_blocks=[
                            SourceBlockRef(page=previous_page.page, block_id=b.block_id)
                            for b in context.previous_blocks[-1:]
                        ]
                        + [
                            SourceBlockRef(page=page.page, block_id=b.block_id)
                            for b in context.next_blocks[:1]
                        ],
                        confidence=action.confidence,
                    )
                )

        if raw_tables_by_page[page.page]:
            if active_table_id is None:
                table_counter += 1
                active_table_id = f"table_{table_counter:02d}"
            table_id_by_page[page.page] = active_table_id
        else:
            active_table_id = None

        for block in _content_blocks(page, header_footer):
            tracker.observe(block.text)
        for block in page.blocks:
            header_footer_action = header_footer.action_for(block, page)
            if header_footer_action is not None:
                log_event(
                    "header.ignored" if header_footer_action.action == Action.IGNORE_HEADER else "footer.ignored",
                    document_id=document_id,
                    page=page.page,
                    block_id=block.block_id,
                )

    segments = _build_segments(ordered_pages, header_footer, boundary_actions)
    sections, clauses = build_hierarchy(segments)
    tables = _build_tables(ordered_pages, header_footer, boundary_actions, table_id_by_page)

    for clause in clauses:
        if clause.parent_id is None:
            log_event("clause.created", clause_id=clause.clause_id, level=clause.level)
        else:
            log_event(
                "clause.parent_assigned", clause_id=clause.clause_id, parent_id=clause.parent_id
            )

    return ReconstructedDocument(
        document_id=document_id,
        sections=sections,
        clauses=clauses,
        tables=tables,
        review_items=review_items,
        metadata=DocumentMetadata(total_pages=len(ordered_pages)),
    )
