"""Running headers, footers and page numbers on a multi-page contract.

A scanned contract repeats the same short lines on every page ("HỢP ĐỒNG CUNG
CẤP DỊCH VỤ (tiếp theo)", "25/2026/HĐDV-MH-TT", "Trang 3/12"). Left in the
reading-order line stream, they get glued onto whichever clause happens to be
open at a page break -- polluting its text and stretching its page range onto
the next page. This module only classifies lines: page text and snapshot lines
keep them verbatim (raw OCR is immutable), and only the clause structure skips
them.

A line counts as running text only when it sits at a page edge AND either
reads as a page number or repeats at the same edge on at least half of the
document's pages. Position alone is never enough -- a clause heading at the top
of a page is at an edge too, but does not repeat.

Wrongly dropping a line loses contract content, so "repeats" is strict:

- A numbered clause marker ("Điều 5.", "5.1.", "a)", "Khoản 2") is structure,
  never furniture.
- Digits must match exactly, except the page counter itself: a number after
  "Trang"/"Page" or at either end of the line that equals the page number
  (plus the document's printed-numbering offset). Masking every digit would
  make "Điều 5 ..." and "Điều 6 ..." -- or any templated body line -- look like
  one repeated line.
- A page that duplicates an earlier page (`Page.duplicate_of` /
  `near_duplicate_of`) is not evidence: its whole text "repeats" on two pages.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from math import ceil

from rapidfuzz import fuzz

from contract_ocr.domain.entities import Document, Line, Page
from contract_ocr.domain.enums import Status
from contract_ocr.reconstruction.clause_parser import parse_marker

# Fraction of page height treated as the header/footer band for positioned lines.
EDGE_BAND = 0.1
# For lines without geometry: how many lines from each end of the page count as an
# edge -- at most a third of the page, so a short page is never all "edge".
EDGE_LINES = 3
MIN_REPEAT_RATIO = 0.5
FUZZY_MATCH_RATIO = 90.0
# Printed page numbers can lag the PDF page index by a few unnumbered cover pages.
MAX_PAGE_OFFSET = 5

_MARKDOWN = re.compile(r"[#*_`]+")
_DIGITS = re.compile(r"\d+")
_PAGE_NUMBER = re.compile(
    r"^(?:trang|page)?\s*[-–]?\s*\d{1,4}\s*(?:(?:/|of|trên)\s*\d{1,4})?\s*[-–]?$",
    re.IGNORECASE,
)
_COUNTER_LABEL = re.compile(r"\b(?:trang|page|tr\.)\s*[-–:]?\s*$", re.IGNORECASE)
_TOTAL_LABEL = re.compile(r"(?:/|\bof|\btrên)\s*$", re.IGNORECASE)
_EDGE_PUNCTUATION = " -–|:.()"


def _plain(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", _MARKDOWN.sub("", text)).split())


def _edge_positions(lines: list[Line]) -> dict[str, str]:
    positions: dict[str, str] = {}
    count = len(lines)
    edge = min(EDGE_LINES, ceil(count / 3))
    for index, line in enumerate(lines):
        if line.bbox is not None:
            if line.bbox.y2 <= EDGE_BAND:
                positions[line.line_id] = "top"
            elif line.bbox.y1 >= 1 - EDGE_BAND:
                positions[line.line_id] = "bottom"
        elif index < edge:
            positions[line.line_id] = "top"
        elif index >= count - edge:
            positions[line.line_id] = "bottom"
    return positions


@dataclass
class _Candidate:
    page: Page
    line: Line
    position: str
    text: str


@dataclass
class _Cluster:
    position: str
    digits: tuple[str, ...]
    letters: str
    pages: set[int] = field(default_factory=set)
    members: list[tuple[int, str]] = field(default_factory=list)


def _counter_numbers(text: str) -> list[re.Match[str]]:
    """Numbers placed where a page counter goes: after "Trang"/"Page", or first
    or last on the line -- but not a page total ("3/12", "3 of 12"). A number
    inside running prose ("giao hàng đợt 5 theo lịch") never is, even on page 5."""
    found = []
    for match in _DIGITS.finditer(text):
        before, after = text[: match.start()], text[match.end() :]
        if _COUNTER_LABEL.search(before) or (
            not _TOTAL_LABEL.search(before)
            and (not before.strip(_EDGE_PUNCTUATION) or not after.strip(_EDGE_PUNCTUATION))
        ):
            found.append(match)
    return found


def _page_offset(edge_texts: list[tuple[int, str]]) -> int:
    """Printed page number minus PDF page number, voted by page-counter-placed
    numbers on edge lines: only the page counter keeps one constant offset
    across pages."""
    votes: Counter[int] = Counter()
    for page_number in {number for number, _ in edge_texts}:
        offsets = {
            int(match.group()) - page_number
            for number, text in edge_texts
            if number == page_number
            for match in _counter_numbers(text)
        }
        votes.update(o for o in offsets if abs(o) <= MAX_PAGE_OFFSET)
    if not votes:
        return 0
    best = max(votes.values())
    if best < 2:
        return 0
    return min((o for o, n in votes.items() if n == best), key=lambda o: (abs(o), o))


def _signature(text: str, page_counter: int) -> tuple[tuple[str, ...], str]:
    counters = {
        match.start() for match in _counter_numbers(text) if int(match.group()) == page_counter
    }
    digits = tuple(
        "#" if match.start() in counters else match.group() for match in _DIGITS.finditer(text)
    )
    return digits, _DIGITS.sub("#", text.lower())


def detect_running_lines(document: Document) -> set[tuple[int, str]]:
    """Return `(page_number, line_id)` for every running header/footer/page-number
    line in `document`. Pairs, not bare ids, because nothing guarantees a line id
    is unique across pages."""
    pages = [page for page in document.pages if page.status is Status.SUCCESS and page.lines]
    running: set[tuple[int, str]] = set()
    candidates: list[_Candidate] = []
    edge_texts: list[tuple[int, str]] = []

    for page in pages:
        lines = [line for line in page.lines if line.text.strip()]
        positions = _edge_positions(lines)
        for line in lines:
            position = positions.get(line.line_id)
            # A repeated table header row at the top of a continuation page is
            # table structure, not a running header (see table_continuity.py).
            if position is None or line.text.lstrip().startswith("|"):
                continue
            text = _plain(line.text)
            if _PAGE_NUMBER.match(text):
                running.add((page.page_number, line.line_id))
            elif text and parse_marker(text) is None:
                candidates.append(_Candidate(page, line, position, text))
            else:
                continue
            edge_texts.append((page.page_number, text))

    offset = _page_offset(edge_texts)
    clusters: list[_Cluster] = []
    for candidate in candidates:
        page = candidate.page
        digits, letters = _signature(candidate.text, page.page_number + offset)
        for cluster in clusters:
            if (
                cluster.position == candidate.position
                and cluster.digits == digits
                and (
                    cluster.letters == letters
                    or fuzz.ratio(cluster.letters, letters) >= FUZZY_MATCH_RATIO
                )
            ):
                break
        else:
            cluster = _Cluster(position=candidate.position, digits=digits, letters=letters)
            clusters.append(cluster)
        if page.duplicate_of is None and page.near_duplicate_of is None:
            cluster.pages.add(page.page_number)
        cluster.members.append((page.page_number, candidate.line.line_id))

    independent = [p for p in pages if p.duplicate_of is None and p.near_duplicate_of is None]
    if len(independent) >= 2:
        threshold = max(2, ceil(MIN_REPEAT_RATIO * len(independent)))
        for cluster in clusters:
            if len(cluster.pages) >= threshold:
                running.update(cluster.members)
    return running
