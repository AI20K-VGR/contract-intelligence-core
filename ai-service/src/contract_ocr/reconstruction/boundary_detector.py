"""Extract the small, page-boundary-local slice used to resolve a boundary.

Never hands a resolver the whole page: only the last/first few meaningful
blocks, with headers, footers, page numbers, watermarks and empty blocks
already filtered out (section 6).
"""

from __future__ import annotations

from .config import BOUNDARY_WINDOW
from .header_footer_detector import HeaderFooterProfile
from .models import BoundaryContext, DocumentState
from .schemas.block import Block
from .schemas.page import Page


def _content_blocks(page: Page, header_footer: HeaderFooterProfile) -> list[Block]:
    return [b for b in page.blocks if not header_footer.is_noise(b, page)]


def detect_boundary(
    previous_page: Page,
    next_page: Page,
    header_footer: HeaderFooterProfile,
    document_state: DocumentState | None = None,
    window: int = BOUNDARY_WINDOW,
) -> BoundaryContext:
    """Build the `BoundaryContext` for the page N / page N+1 boundary.

    `document_state` carries the live active section/clause/list/table (see
    `hierarchy_builder.HierarchyBuilder.current_state`); a standalone caller
    (e.g. `resolve_boundary` on just two pages) may omit it, in which case
    the boundary is resolved with no hierarchy context at all.
    """
    previous_content = _content_blocks(previous_page, header_footer)
    next_content = _content_blocks(next_page, header_footer)
    return BoundaryContext(
        document_id=previous_page.document_id,
        document_state=document_state or DocumentState(),
        previous_page=previous_page.page,
        previous_page_height=previous_page.height,
        next_page=next_page.page,
        next_page_height=next_page.height,
        previous_blocks=previous_content[-window:],
        next_blocks=next_content[:window],
    )
