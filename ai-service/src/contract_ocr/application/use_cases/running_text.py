"""Running headers, footers and page numbers on a multi-page contract.

A scanned contract repeats the same short lines on every page ("HỢP ĐỒNG CUNG
CẤP DỊCH VỤ (tiếp theo)", "25/2026/HĐDV-MH-TT", "Trang 3/12"). Left in the
reading-order line stream, they get glued onto whichever clause happens to be
open at a page break -- polluting its text and stretching its page range onto
the next page. This module only classifies lines: page text and snapshot lines
keep them verbatim (raw OCR is immutable), and only the clause structure skips
them.

A line counts as running text only when it sits at a page edge AND either
reads as a page number or repeats (fuzzily, digits masked) at the same edge on
at least half of the document's pages. Position alone is never enough -- a
clause heading at the top of a page is at an edge too, but does not repeat.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from math import ceil

from rapidfuzz import fuzz

from contract_ocr.domain.entities import Document, Line
from contract_ocr.domain.enums import Status

# Fraction of page height treated as the header/footer band for positioned lines.
EDGE_BAND = 0.1
# For lines without geometry: how many lines from each end of the page count as an edge.
EDGE_LINES = 3
MIN_REPEAT_RATIO = 0.5
FUZZY_MATCH_RATIO = 90.0

_MARKDOWN = re.compile(r"[#*_`]+")
_DIGITS = re.compile(r"\d+")
_PAGE_NUMBER = re.compile(
    r"^(?:trang|page)?\s*[-–]?\s*\d{1,4}\s*(?:(?:/|of|trên)\s*\d{1,4})?\s*[-–]?$",
    re.IGNORECASE,
)


def _plain(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", _MARKDOWN.sub("", text)).split())


def _pattern(text: str) -> str:
    return _DIGITS.sub("#", _plain(text).lower())


def _edge_positions(lines: list[Line]) -> dict[str, str]:
    positions: dict[str, str] = {}
    count = len(lines)
    for index, line in enumerate(lines):
        if line.bbox is not None:
            if line.bbox.y2 <= EDGE_BAND:
                positions[line.line_id] = "top"
            elif line.bbox.y1 >= 1 - EDGE_BAND:
                positions[line.line_id] = "bottom"
        elif index < EDGE_LINES:
            positions[line.line_id] = "top"
        elif index >= count - EDGE_LINES:
            positions[line.line_id] = "bottom"
    return positions


@dataclass
class _Cluster:
    position: str
    representative: str
    pages: set[int] = field(default_factory=set)
    members: list[tuple[int, str]] = field(default_factory=list)


def detect_running_lines(document: Document) -> set[tuple[int, str]]:
    """Return `(page_number, line_id)` for every running header/footer/page-number
    line in `document`. Pairs, not bare ids, because nothing guarantees a line id
    is unique across pages."""
    pages = [page for page in document.pages if page.status is Status.SUCCESS and page.lines]
    running: set[tuple[int, str]] = set()
    clusters: list[_Cluster] = []

    for page in pages:
        lines = [line for line in page.lines if line.text.strip()]
        positions = _edge_positions(lines)
        for line in lines:
            position = positions.get(line.line_id)
            # A repeated table header row at the top of a continuation page is
            # table structure, not a running header (see table_continuity.py).
            if position is None or line.text.lstrip().startswith("|"):
                continue
            key = (page.page_number, line.line_id)
            if _PAGE_NUMBER.match(_plain(line.text)):
                running.add(key)
                continue
            pattern = _pattern(line.text)
            if not pattern:
                continue
            for cluster in clusters:
                if cluster.position == position and (
                    cluster.representative == pattern
                    or fuzz.ratio(cluster.representative, pattern) >= FUZZY_MATCH_RATIO
                ):
                    break
            else:
                cluster = _Cluster(position=position, representative=pattern)
                clusters.append(cluster)
            cluster.pages.add(page.page_number)
            cluster.members.append(key)

    if len(pages) >= 2:
        threshold = max(2, ceil(MIN_REPEAT_RATIO * len(pages)))
        for cluster in clusters:
            if len(cluster.pages) >= threshold:
                running.update(cluster.members)
    return running
