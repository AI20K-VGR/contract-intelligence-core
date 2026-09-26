"""Accuracy-first OCR for one page: correct Vietnamese text from one Mistral
model, measured geometry from local CV, and a second/third reader only where
a deterministic gate finds a reason to doubt the first.

Measured on this codebase's own 12-page scan: `mistral-ocr-4` (and 4-1,
latest) garbled Vietnamese diacritics on 6/12 pages at any DPI, while
`mistral-ocr-2512` read every page correctly -- but 2512 returns no blocks,
bboxes or confidence. So the page is read in this order:

1. `text_reader` (mistral-ocr-2512) and local geometry (`detect_bordered_tables`
   + `detect_text_lines`) run concurrently; geometry costs no API call and
   finishes inside the network wait.
2. The transcription's lines are aligned to the measured visual-line boxes;
   bordered tables take real cell boxes from their ruling-line grid.
3. A deterministic gate looks for reasons to doubt the page: text the
   alignment could not place, ink nothing transcribed, borderless tables,
   critical fields (money/dates/ids), and lines that fail Vietnamese spelling
   checks (`vn_text.line_issues`).
4. Only then is `verifier` (mistral-ocr-4-1) called, for geometry, table
   boxes, and an independent reading of digits. Its letters are never used:
   the 4.x generation is exactly the one that drops accents.
5. Lines that still conflict (critical tokens disagree, spelling fails, amount
   in words contradicts digits) are re-read blind by `arbiter` (GPT vision) on
   crops batched into one request, then decided by vote; anything unresolved
   is flagged `needs_review` instead of guessed.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import numpy as np
from rapidfuzz import fuzz

from contract_ocr.application.ports.ocr_engine import OCREngine
from contract_ocr.domain.bbox import BBox
from contract_ocr.domain.critical_fields import amount_words_mismatch, critical_tokens
from contract_ocr.domain.entities import Cell, Context, Line, OCRResult, Row, Table
from contract_ocr.domain.enums import GeometryProvenance
from contract_ocr.domain.headings import is_annex_heading
from contract_ocr.domain.reading_agreement import disputes, implausible, tokens
from contract_ocr.domain.vn_text import char_skeleton, line_issues, skeleton
from contract_ocr.infrastructure.image.line_geometry import (
    LineBox,
    column_major_variant,
    detect_text_lines,
)
from contract_ocr.infrastructure.image.table_grid import TableGrid, detect_bordered_tables
from contract_ocr.infrastructure.observability import observation
from contract_ocr.infrastructure.ocr.markdown_tables import (
    build_table_from_block,
    clean_markdown_text,
    parse_markdown_pipe_table,
)
from contract_ocr.infrastructure.ocr.text_geometry_alignment import align

logger = logging.getLogger(__name__)

_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_SEPARATOR = re.compile(r"^[\s|:-]+$")
_HORIZONTAL_RULE = re.compile(r"^[-*_]{3,}$")
_IMAGE_ONLY = re.compile(r"^\[image: [^\]]*\]$")
_IMAGE_REF = re.compile(r"!\[[^\]]*\]\([^)]*\)|\[image: [^\]]*\]")
# Two readings of one line are about the same text when their skeletons agree
# at least this well; below it a replacement could come from the wrong region.
MIN_SAME_TEXT_RATIO = 80.0
MIN_GEOMETRY_MATCH_RATIO = 70.0
TRUSTED = (GeometryProvenance.MEASURED, GeometryProvenance.DERIVED)


@dataclass
class _Segment:
    text: str
    table_index: int | None = None
    row_index: int | None = None
    bbox: BBox | None = None
    provenance: GeometryProvenance | None = None
    review: list[str] = field(default_factory=list)


@dataclass
class _MarkdownTable:
    raw: str
    rows: list[list[str]]
    segment_indices: list[int]
    table: Table | None = None


def _parse_markdown(markdown: str) -> tuple[list[_Segment], list[_MarkdownTable]]:
    segments: list[_Segment] = []
    tables: list[_MarkdownTable] = []
    lines = markdown.splitlines()
    i = 0
    while i < len(lines):
        if _TABLE_ROW.match(lines[i]):
            j = i
            while j < len(lines) and _TABLE_ROW.match(lines[j]):
                j += 1
            block = lines[i:j]
            rows = parse_markdown_pipe_table("\n".join(block))
            if rows:
                indices, row_index = [], 0
                for raw in block:
                    if _TABLE_SEPARATOR.match(raw) and "-" in raw:
                        continue
                    text = clean_markdown_text(raw)
                    if text.replace("|", "").strip():
                        segments.append(_Segment(text, table_index=len(tables), row_index=row_index))
                        indices.append(len(segments) - 1)
                    row_index += 1
                tables.append(_MarkdownTable("\n".join(block), rows, indices))
                i = j
                continue
        text = clean_markdown_text(lines[i])
        if text and not _HORIZONTAL_RULE.match(text) and not _IMAGE_ONLY.match(text):
            segments.append(_Segment(text))
        i += 1
    return segments, tables


_PAGE_NUMBER = re.compile(
    r"^(?:trang|page)?\s*[-–]?\s*\d{1,4}\s*(?:(?:/|of|trên)\s*\d{1,4})?\s*[-–]?$", re.IGNORECASE
)


def _movable(text: str) -> bool:
    """Page furniture a transcriber may emit out of order: a page number, or a
    short code line with digits and no lowercase ("25/2026/HĐDV-MH-TT"). A
    heading ("ĐIỀU 4. YÊU CẦU...") is uppercase with a digit too, so structure
    markers and anything longer than two words never qualify."""
    stripped = text.strip()
    if _PAGE_NUMBER.match(stripped):
        return True
    return (
        not is_annex_heading(stripped)
        and len(stripped.split()) <= 2
        and any(ch.isdigit() for ch in stripped)
        and not any(ch.islower() for ch in stripped)
    )


def _norm_box(x0: float, y0: float, x1: float, y1: float, width: int, height: int) -> BBox:
    return BBox.normalize([x0, y0, x1, y1], width, height)


class VerifiedMistralOCREngine(OCREngine):
    name = "mistral_verified"

    def __init__(
        self,
        text_reader: OCREngine,
        verifier: OCREngine | None,
        arbiter: Any | None,
        fallback_reader: OCREngine | None = None,
        *,
        verify_all_pages: bool = True,
    ) -> None:
        """`verify_all_pages` runs the verifier on every page, concurrently with
        the text reader (no added latency, one extra Mistral page each): only an
        independent second reading can expose a valid-word substitution such as
        2512's "tồn tại thì điểm" for "tồn tại tại thời điểm". False falls back to
        calling it only when the gate finds geometry/table/critical-field doubt."""
        self.text_reader = text_reader
        self.verifier = verifier
        self.arbiter = arbiter
        self.fallback_reader = fallback_reader
        self.verify_all_pages = verify_all_pages
        self.model = "+".join(
            engine.model for engine in (text_reader, verifier) if engine is not None
        )
        self.runtime_info = {
            "text_reader": text_reader.runtime_info,
            "verifier": verifier.runtime_info if verifier else None,
            "arbiter": getattr(arbiter, "runtime_info", None),
        }

    # -- stage 1: read text and measure geometry concurrently -----------------

    def _read_text(self, image: np.ndarray, context: Context) -> tuple[OCRResult, list[str]]:
        try:
            return self.text_reader.recognize_page(image, context), []
        except Exception as exc:
            if self.fallback_reader is None:
                raise
            logger.warning(
                "ocr.text_reader_failed document_id=%s page=%s error=%s",
                context.document_id,
                context.page,
                f"{type(exc).__name__}: {exc}",
            )
            result = self.fallback_reader.recognize_page(image, self._sub(context, "fallback"))
            return result, [f"ocr:text_reader_fallback:{type(exc).__name__}"]

    def _verify(self, image: np.ndarray, context: Context) -> tuple[OCRResult | None, str | None]:
        try:
            return self.verifier.recognize_page(image, self._sub(context, "verify")), None
        except Exception as exc:
            logger.warning(
                "ocr.verifier_failed document_id=%s page=%s error=%s",
                context.document_id,
                context.page,
                f"{type(exc).__name__}: {exc}",
            )
            return None, f"ocr:verifier_failed:{type(exc).__name__}"

    @staticmethod
    def _measure(image: np.ndarray) -> tuple[list[TableGrid], list[LineBox]]:
        grids = sorted(detect_bordered_tables(image), key=lambda g: g.bbox[1])
        return grids, detect_text_lines(image, exclude=[g.bbox for g in grids])

    @staticmethod
    def _sub(context: Context, name: str) -> Context:
        return Context(
            document_id=context.document_id,
            page=context.page,
            output_dir=str(Path(context.output_dir) / name),
        )

    def recognize_page(self, page_image: np.ndarray, context: Context) -> OCRResult:
        height, width = page_image.shape[:2]
        with observation(
            "verify-page",
            input={"document_id": context.document_id, "page_number": context.page},
            metadata={"feature": "document-ocr", "engine": self.name},
        ) as span:
            eager = self.verify_all_pages and self.verifier is not None
            with ThreadPoolExecutor(max_workers=3) as pool:
                text_future = pool.submit(copy_context().run, self._read_text, page_image, context)
                geometry_future = pool.submit(copy_context().run, self._measure, page_image)
                verify_future = (
                    pool.submit(copy_context().run, self._verify, page_image, context)
                    if eager
                    else None
                )
                (read, warnings) = text_future.result()
                grids, boxes = geometry_future.result()
                second, verify_warning = verify_future.result() if verify_future else (None, None)

            markdown = read.raw_markdown or "\n".join(line.text for line in read.lines)
            segments, md_tables = _parse_markdown(markdown)

            # -- stage 2: geometry for tables and text --------------------------
            unmatched_tables = self._place_grid_tables(md_tables, grids, segments, width, height)
            text_indices = [
                i
                for i, s in enumerate(segments)
                if s.table_index is None or md_tables[s.table_index].table is None
            ]
            anchors = (
                self._anchors(segments, text_indices, second, width, height)
                if second is not None
                else {}
            )
            text_indices, alignment, boxes = self._best_order(
                segments, text_indices, boxes, anchors
            )
            output_order = self._output_order(len(segments), text_indices)
            line_height = sorted(b.height for b in boxes)[len(boxes) // 2] if boxes else 0
            for index, match in zip(text_indices, alignment.segments, strict=True):
                if not match.box_indices:
                    continue
                run = [boxes[b] for b in match.box_indices]
                segments[index].bbox = _norm_box(
                    min(b.x0 for b in run),
                    min(b.y0 for b in run),
                    max(b.x1 for b in run),
                    max(b.y1 for b in run),
                    width,
                    height,
                )
                segments[index].provenance = (
                    GeometryProvenance.CLAIMED
                    if match.poor
                    else GeometryProvenance.MEASURED
                    if len(run) == 1
                    else GeometryProvenance.DERIVED
                )

            # -- stage 3: gate ---------------------------------------------------
            poor_geometry = [i for i in text_indices if segments[i].provenance not in TRUSTED]
            critical = [i for i, s in enumerate(segments) if critical_tokens(s.text)]
            spelling = {i: issues for i, s in enumerate(segments) if (issues := line_issues(s.text))}
            reasons: dict[int, set[str]] = {i: {"spelling"} for i in spelling}
            for i, s in enumerate(segments):
                if amount_words_mismatch(s.text):
                    reasons.setdefault(i, set()).add("amount")
            needs_verifier = bool(
                poor_geometry or alignment.unread_ink or unmatched_tables or critical
            )

            # -- stage 4: second reader (geometry, digits, word agreement) -------
            if not eager and needs_verifier and self.verifier is not None:
                second, verify_warning = self._verify(page_image, context)
            if verify_warning:
                warnings.append(verify_warning)
            content_disputes = 0
            if second is not None:
                self._repair_geometry(segments, poor_geometry, second)
                self._place_borderless_tables(md_tables, unmatched_tables, second)
                for i in self._digit_conflicts(segments, critical, second):
                    reasons.setdefault(i, set()).add("critical")
                for dispute in disputes(
                    [t for i in output_order for t in tokens(segments[i].text, i)],
                    tokens(_IMAGE_REF.sub(" ", second.raw_markdown or "")),
                ):
                    content_disputes += 1
                    for i in dispute.owners:
                        # Codes and page numbers are covered by the critical-token
                        # check; their word-level diff is layout noise.
                        if not _movable(segments[i].text):
                            reasons.setdefault(i, set()).add("content")
            elif critical:
                for i in critical:
                    segments[i].review.append("critical_field_unverified")
            if alignment.unread_ink:
                warnings.append(f"ocr:unread_ink_lines:{len(alignment.unread_ink)}")

            # -- stage 5: blind arbitration of what still conflicts, plus a blind
            # read of ink the text reader skipped (e.g. signer names) ----------
            targets = sorted(reasons)
            ink_crops = (
                self._unread_ink_crops(
                    page_image, boxes, self._recoverable_ink(segments, alignment, boxes, second),
                    line_height,
                )
                if second is not None
                else {}
            )
            recovered: dict[str, str] = {}
            if targets or ink_crops:
                recovered = self._arbitrate(
                    page_image, context, segments, reasons, second, line_height, ink_crops
                )
            inserted = self._insert_recovered(
                segments, output_order, text_indices, alignment, boxes, recovered, second,
                width, height,
            )
            if inserted:
                warnings.append(f"ocr:recovered_unread_ink:{inserted}")

            if span is not None:
                span.update(
                    output={
                        "segments": len(segments),
                        "boxes": len(boxes),
                        "grids": len(grids),
                        "poor_geometry": len(poor_geometry),
                        "unread_ink": len(alignment.unread_ink),
                        "critical_lines": len(critical),
                        "spelling_flags": len(spelling),
                        "content_disputes": content_disputes,
                        "verifier_called": second is not None,
                        "arbitrated": len(targets),
                    }
                )

        return self._result(context, [segments[i] for i in output_order], md_tables, read, warnings)

    # -- reading order ---------------------------------------------------------

    @staticmethod
    def _anchors(
        segments: list[_Segment],
        text_indices: list[int],
        second: OCRResult,
        width: int,
        height: int,
    ) -> dict[int, tuple[float, float, float, float]]:
        """Where the verifier -- an independent reading with measured block
        boxes -- put each text segment, found by matching words on skeletons
        (its accent errors do not matter here). A segment is anchored only when
        at least half its words matched, and only to the verifier lines that
        supplied a real share of those matches."""
        ours = [t for i in text_indices for t in tokens(segments[i].text, i)]
        theirs = [t for idx, line in enumerate(second.lines) for t in tokens(line.text, idx)]
        if not ours or not theirs:
            return {}
        matcher = SequenceMatcher(
            None, [t.skeleton for t in ours], [t.skeleton for t in theirs], autojunk=False
        )
        owners: dict[int, Counter[int]] = {}
        for a, b, size in matcher.get_matching_blocks():
            for offset in range(size):
                owners.setdefault(ours[a + offset].owner, Counter())[theirs[b + offset].owner] += 1
        token_count = Counter(t.owner for t in ours)
        anchors: dict[int, tuple[float, float, float, float]] = {}

        def region(boxes: list[BBox]) -> tuple[float, float, float, float]:
            return (
                min(b.x1 for b in boxes) * width,
                min(b.y1 for b in boxes) * height,
                max(b.x2 for b in boxes) * width,
                max(b.y2 for b in boxes) * height,
            )

        for index, votes in owners.items():
            total = sum(votes.values())
            if total < 0.5 * token_count[index]:
                continue
            lines = [
                second.lines[owner].bbox
                for owner, n in votes.items()
                if n >= 0.3 * total and second.lines[owner].bbox is not None
            ]
            if lines:
                anchors[index] = region(lines)
        # The sequence match is order-aware, so a line the two readers emitted
        # in different places (a footer printed first by one of them) stays
        # unanchored there; match those by content alone.
        positioned = [line for line in second.lines if line.bbox is not None]
        for index in text_indices:
            if index in anchors or not positioned:
                continue
            target = skeleton(segments[index].text)
            best = max(positioned, key=lambda line: fuzz.ratio(target, skeleton(line.text)))
            if fuzz.ratio(target, skeleton(best.text)) >= 85:
                anchors[index] = region([best.bbox])
        return anchors

    @staticmethod
    def _best_order(
        segments: list[_Segment],
        text_indices: list[int],
        boxes: list[LineBox],
        anchors: dict[int, tuple[float, float, float, float]],
    ) -> tuple[list[int], Any, list[LineBox]]:
        """Transcribers do not always follow top-to-bottom order: 2512 put
        "25/2026/HĐDV-MH-TT / Trang 4/12" above page 4's header, and reads a
        two-column signature block down each column. A monotonic alignment
        cannot recover from either, so rotations of leading/trailing page
        furniture and a column-major box order are tried; the cheapest wins."""
        def texts(order: list[int]) -> list[str]:
            return [segments[i].text for i in order]

        def solve(order: list[int], box_order: list[LineBox]) -> Any:
            return align(texts(order), box_order, [anchors.get(i) for i in order])

        best = (text_indices, solve(text_indices, boxes), boxes)
        columns = column_major_variant(boxes)
        clean = not (
            best[1].unread_ink
            or best[1].text_without_ink
            or any(match.poor for match in best[1].segments)
        )
        # Two lines of similar length swapped between columns still align
        # "cleanly", so a column block is always worth the second try.
        if clean and columns is None:
            return best
        orders = [text_indices]
        for k in range(1, min(3, len(text_indices) - 1) + 1):
            head, tail = text_indices[:k], text_indices[-k:]
            # Only page furniture may move -- never a heading or a paragraph.
            if all(_movable(segments[i].text) for i in head):
                orders.append(text_indices[k:] + head)
            if all(_movable(segments[i].text) for i in tail):
                orders.append(tail + text_indices[:-k])
        box_orders = [boxes]
        if columns is not None:
            box_orders.append(columns)
        for box_order in box_orders:
            for order in orders:
                if order is text_indices and box_order is boxes:
                    continue
                result = solve(order, box_order)
                if result.cost < best[1].cost - 1e-9:
                    best = (order, result, box_order)
        return best

    @staticmethod
    def _recoverable_ink(
        segments: list[_Segment], alignment: Any, boxes: list[LineBox], second: OCRResult
    ) -> list[int]:
        """Skipped boxes worth a blind re-read. Only when the verifier saw real
        words the text reader did not (measured: 2512 dropped both signers'
        names under their signatures), and then down to name-length ink --
        otherwise a page's leftover specks and scribbles cost nothing."""
        ours = {t.skeleton for s in segments for t in tokens(s.text)}
        extra = [
            t
            for t in tokens(_IMAGE_REF.sub(" ", second.raw_markdown or ""))
            if t.skeleton not in ours and not implausible(t.text) and not t.text.isdigit()
        ]
        if not extra:
            return []
        rate = alignment.chars_per_pixel
        return [b for b in alignment.unmatched_boxes if boxes[b].width * rate >= 5]

    @staticmethod
    def _unread_ink_crops(
        image: np.ndarray, boxes: list[LineBox], unread: list[int], line_height: int
    ) -> dict[str, np.ndarray]:
        height, width = image.shape[:2]
        pad_y, pad_x = max(3, int(0.25 * line_height)), max(6, int(0.5 * line_height))
        crops: dict[str, np.ndarray] = {}
        for b in unread:
            crop = image[
                max(0, boxes[b].y0 - pad_y) : min(height, boxes[b].y1 + pad_y),
                max(0, boxes[b].x0 - pad_x) : min(width, boxes[b].x1 + pad_x),
            ]
            if crop.ndim == 3 and crop.size:
                r, g, bl = (crop[..., i].astype(np.int16) for i in range(3))
                # Leftover strokes inside a company seal: seal text, not content.
                if ((r - g > 50) & (r - bl > 50)).mean() > 0.15:
                    continue
            crops[f"ink{b}"] = crop
        return crops

    @staticmethod
    def _insert_recovered(
        segments: list[_Segment],
        output_order: list[int],
        text_order: list[int],
        alignment: Any,
        boxes: list[LineBox],
        recovered: dict[str, str],
        second: OCRResult | None,
        width: int,
        height: int,
    ) -> int:
        """Insert blind readings of skipped ink as new lines. Confirmed when the
        verifier read the very same word sequence (two independent readers);
        a partial match is still inserted -- dropping a signer's name is worse
        -- but flagged for review. Unreadable, misspelled, already-present or
        unrelated text is never inserted."""
        if not recovered or second is None:
            return 0
        verifier_sequence = " ".join(
            t.skeleton for t in tokens(_IMAGE_REF.sub(" ", second.raw_markdown or ""))
        )
        verifier_words = set(verifier_sequence.split())
        # Ink can go unmatched merely because the alignment gave its text to a
        # neighbouring box; recovering it would duplicate a line already read.
        page_skeleton = skeleton(" ".join(s.text for s in segments))
        last_box_of = {
            index: max(match.box_indices)
            for index, match in zip(text_order, alignment.segments, strict=True)
            if match.box_indices
        }
        inserted = 0
        for key, text in sorted(recovered.items(), key=lambda kv: int(kv[0][3:])):
            text = " ".join(text.split())
            words = tokens(text)
            if (
                len(re.sub(r"\W", "", text)) < 3
                or "[illegible]" in text
                or line_issues(text)
                or sum(1 for w in words if w.skeleton in verifier_words) < 0.5 * len(words)
                or fuzz.partial_ratio(skeleton(text), page_skeleton) >= 90
            ):
                continue
            sequence = " ".join(w.skeleton for w in words)
            confirmed = f" {sequence} " in f" {verifier_sequence} "
            box_index = int(key[3:])
            box = boxes[box_index]
            segments.append(
                _Segment(
                    text,
                    bbox=_norm_box(box.x0, box.y0, box.x1, box.y1, width, height),
                    provenance=GeometryProvenance.MEASURED,
                    review=[] if confirmed else ["recovered_text_unconfirmed"],
                )
            )
            before = [i for i, last in last_box_of.items() if last < box_index]
            anchor = max(before, key=lambda i: last_box_of[i]) if before else None
            position = output_order.index(anchor) + 1 if anchor is not None else 0
            output_order.insert(position, len(segments) - 1)
            last_box_of[len(segments) - 1] = box_index
            inserted += 1
        return inserted

    @staticmethod
    def _output_order(count: int, text_order: list[int]) -> list[int]:
        """All segment indices, text segments in their chosen order, table rows
        with a grid kept at their original position relative to the others."""
        text_set = set(text_order)
        slots = iter(text_order)
        return [next(slots) if i in text_set else i for i in range(count)]

    # -- tables ----------------------------------------------------------------

    def _place_grid_tables(
        self,
        md_tables: list[_MarkdownTable],
        grids: list[TableGrid],
        segments: list[_Segment],
        width: int,
        height: int,
    ) -> list[int]:
        """Pair markdown tables with ruling-line grids in reading order. Returns
        indices of tables left without a grid (borderless)."""
        unmatched: list[int] = []
        pending = list(grids)
        for index, md in enumerate(md_tables):
            md_cols = max(len(r) for r in md.rows)
            grid = pending[0] if pending else None
            # Both lists are in reading order, but a borderless table has no grid:
            # only consume the next grid when its shape plausibly is this table.
            if grid is None or not (
                len(grid.col_boundaries) - 1 == md_cols
                or abs(len(grid.row_boundaries) - 1 - len(md.rows)) <= 1
            ):
                unmatched.append(index)
                continue
            pending.pop(0)
            n_rows = len(grid.row_boundaries) - 1
            n_cols = len(grid.col_boundaries) - 1
            table_id = f"t{index + 1:03d}"
            table_box = _norm_box(*grid.bbox, width, height)
            if n_rows == len(md.rows) and n_cols == md_cols:
                cells = grid.cells()

                def cell(r: int, c: int, cells=cells) -> Cell:
                    text = md.rows[r][c] if c < len(md.rows[r]) else ""
                    return Cell(
                        text=text or "",
                        bbox=_norm_box(*cells[r][c], width, height),
                        geometry_provenance=GeometryProvenance.DERIVED,
                    )

                md.table = Table(
                    table_id=table_id,
                    bbox=table_box,
                    geometry_provenance=GeometryProvenance.MEASURED,
                    header=[h or "" for h in md.rows[0]],
                    rows=[
                        Row(cells=[cell(r, c) for c in range(n_cols)]) for r in range(1, n_rows)
                    ],
                )
                row_boxes = [
                    (_norm_box(grid.bbox[0], y0, grid.bbox[2], y1, width, height), GeometryProvenance.DERIVED)
                    for y0, y1 in zip(grid.row_boundaries, grid.row_boundaries[1:], strict=False)
                ]
            else:
                md.table = build_table_from_block(
                    table_id=table_id, block_bbox=table_box, block_content=md.raw
                )
                if md.table is None:
                    unmatched.append(index)
                    continue
                step = (table_box.y2 - table_box.y1) / max(1, len(md.rows))
                row_boxes = [
                    (
                        BBox(
                            x1=table_box.x1,
                            y1=table_box.y1 + r * step,
                            x2=table_box.x2,
                            y2=min(1.0, table_box.y1 + (r + 1) * step),
                        ),
                        GeometryProvenance.CLAIMED,
                    )
                    for r in range(len(md.rows))
                ]
            for seg_index in md.segment_indices:
                row = segments[seg_index].row_index
                if row is not None and row < len(row_boxes):
                    segments[seg_index].bbox, segments[seg_index].provenance = row_boxes[row]
        return unmatched

    def _place_borderless_tables(
        self, md_tables: list[_MarkdownTable], unmatched: list[int], second: OCRResult
    ) -> None:
        candidates = list(second.tables)
        for index in unmatched:
            md = md_tables[index]
            header = skeleton(" ".join(md.rows[0]))
            best, best_score = None, 0.0
            for table in candidates:
                score = fuzz.ratio(header, skeleton(" ".join(table.header)))
                if score > best_score:
                    best, best_score = table, score
            if best is None or best_score < MIN_GEOMETRY_MATCH_RATIO or best.bbox is None:
                continue
            candidates.remove(best)
            md.table = build_table_from_block(
                table_id=f"t{index + 1:03d}", block_bbox=best.bbox, block_content=md.raw
            )

    # -- verifier use ----------------------------------------------------------

    @staticmethod
    def _repair_geometry(segments: list[_Segment], indices: list[int], second: OCRResult) -> None:
        positioned = [line for line in second.lines if line.bbox is not None]
        for index in indices:
            target = skeleton(segments[index].text)
            best, best_score = None, 0.0
            for line in positioned:
                score = fuzz.ratio(target, skeleton(line.text))
                if score > best_score:
                    best, best_score = line, score
            if best is not None and best_score >= MIN_GEOMETRY_MATCH_RATIO:
                segments[index].bbox = best.bbox
                segments[index].provenance = GeometryProvenance.MEASURED

    @staticmethod
    def _digit_conflicts(segments: list[_Segment], critical: list[int], second: OCRResult) -> set[int]:
        """Critical tokens must agree between the two independent readings.
        Compared page-wide so differing line segmentation cannot fake a conflict."""
        other = critical_tokens(
            second.raw_markdown or "\n".join(line.text for line in second.lines)
        )
        mine: Counter[str] = Counter()
        for i in critical:
            mine.update(critical_tokens(segments[i].text))
        conflicts = {
            i for i in critical if any(mine[t] > other[t] for t in critical_tokens(segments[i].text))
        }
        # A token only the verifier saw: blame the segment closest in text to
        # the verifier line that holds it.
        missing = {t for t in other if other[t] > mine[t]}
        if missing:
            for line in second.lines:
                if not set(critical_tokens(line.text)) & missing:
                    continue
                target = skeleton(line.text)
                scores = [(fuzz.ratio(target, skeleton(s.text)), i) for i, s in enumerate(segments)]
                score, index = max(scores, default=(0.0, -1))
                if index >= 0 and score >= MIN_GEOMETRY_MATCH_RATIO:
                    conflicts.add(index)
        return conflicts

    # -- arbitration -----------------------------------------------------------

    def _arbitrate(
        self,
        image: np.ndarray,
        context: Context,
        segments: list[_Segment],
        reasons: dict[int, set[str]],
        second: OCRResult | None,
        line_height: int,
        extra_crops: dict[str, np.ndarray],
    ) -> dict[str, str]:
        """Decide every conflicting segment by blind vote; return the blind
        readings of `extra_crops` (skipped ink) for the caller to vet."""
        targets = sorted(reasons)
        readings, extra = self._blind_readings(
            image, context, segments, targets, line_height, extra_crops
        )
        verifier_text = (
            second.raw_markdown or "\n".join(line.text for line in second.lines)
            if second is not None
            else ""
        )
        other = critical_tokens(verifier_text)
        verifier_lines = [line.text for line in second.lines] if second is not None else []
        for index in targets:
            segment = segments[index]
            kinds = reasons[index]
            candidate = readings.get(index)
            if candidate is None:
                segment.review.append("arbiter_unavailable")
                continue
            same_text = fuzz.ratio(skeleton(candidate), skeleton(segment.text)) >= MIN_SAME_TEXT_RATIO
            mine, theirs = critical_tokens(segment.text), critical_tokens(candidate)
            if (mine or theirs) and mine != theirs:
                if same_text and theirs and all(other[t] >= n for t, n in theirs.items()):
                    # Arbiter and verifier agree against the text reader: 2 of 3.
                    segment.text = candidate
                    if line_issues(candidate):
                        segment.review.append("spelling_unverified")
                else:
                    segment.review.append("critical_field_conflict")
                continue
            # From here the critical tokens (if any) agree between the text
            # reader and the blind arbiter -- two independent readings.
            if "content" in kinds and disputes(tokens(segment.text), tokens(candidate)):
                if same_text and not line_issues(candidate) and self._closer_to_verifier(
                    candidate, segment.text, verifier_lines
                ):
                    segment.text = candidate  # arbiter sides with the verifier's words
                else:
                    segment.review.append("content_conflict")
                continue
            if amount_words_mismatch(segment.text):
                if same_text and not amount_words_mismatch(candidate):
                    segment.text = candidate
                else:
                    segment.review.append("amount_words_mismatch")
                continue
            if "spelling" in kinds:
                if same_text and not line_issues(candidate):
                    segment.text = candidate
                else:
                    segment.review.append("spelling_unverified")
        return extra

    @staticmethod
    def _closer_to_verifier(candidate: str, current: str, verifier_lines: list[str]) -> bool:
        """The arbiter's reading replaces the text reader's only when it is
        strictly closer (on skeletons) to what the verifier independently read."""
        if not verifier_lines:
            return False
        target = skeleton(current)
        reference = max(verifier_lines, key=lambda text: fuzz.ratio(target, skeleton(text)))
        reference_skeleton = skeleton(reference)
        return (
            fuzz.ratio(skeleton(candidate), reference_skeleton)
            > fuzz.ratio(target, reference_skeleton) + 1.0
        )

    def _blind_readings(
        self,
        image: np.ndarray,
        context: Context,
        segments: list[_Segment],
        targets: list[int],
        line_height: int,
        extra_crops: dict[str, np.ndarray],
    ) -> tuple[dict[int, str], dict[str, str]]:
        """Blind readings of the target segments (by segment index) and of the
        extra crops (by their key), in as few arbiter requests as possible."""
        if self.arbiter is None:
            return {}, {}
        height, width = image.shape[:2]
        # Boxes already include accents; a little margin keeps edge strokes
        # without pulling in the neighbouring lines (which the arbiter would
        # then transcribe too, spoiling the comparison).
        pad_y = max(3, int(0.25 * line_height))
        pad_x = max(6, int(0.5 * line_height))
        try:
            crops: dict[str, np.ndarray] = dict(extra_crops)
            croppable = all(segments[i].provenance in TRUSTED for i in targets)
            if croppable:
                for i in targets:
                    box = segments[i].bbox
                    x0 = max(0, int(box.x1 * width) - pad_x)
                    y0 = max(0, int(box.y1 * height) - pad_y)
                    x1 = min(width, int(box.x2 * width) + pad_x)
                    y1 = min(height, int(box.y2 * height) + pad_y)
                    crops[str(i)] = image[y0:y1, x0:x1]
            regions = self.arbiter.read_regions(crops, context) if crops else {}
            extra = {k: v for k, v in regions.items() if k in extra_crops}
            if croppable:
                readings = {int(k): " ".join(v.split()) for k, v in regions.items() if k.isdigit()}
            else:
                # Some target has no trustworthy box to crop: read the whole
                # page once and locate each target's text in it.
                page = self.arbiter.recognize_page(image, self._sub(context, "arbiter"))
                readings = self._locate(page.raw_markdown or "", segments, targets)
            return readings, extra
        except Exception as exc:
            logger.warning(
                "ocr.arbiter_failed document_id=%s page=%s error=%s",
                context.document_id,
                context.page,
                f"{type(exc).__name__}: {exc}",
            )
            return {}, {}

    @staticmethod
    def _locate(page_text: str, segments: list[_Segment], targets: list[int]) -> dict[int, str]:
        page_skeleton = char_skeleton(page_text)
        found: dict[int, str] = {}
        for index in targets:
            needle = char_skeleton(segments[index].text)
            alignment = fuzz.partial_ratio_alignment(needle, page_skeleton)
            if alignment is None or alignment.score < MIN_SAME_TEXT_RATIO:
                continue
            span = page_text[alignment.dest_start : alignment.dest_end]
            found[index] = " ".join(span.split())
        return found

    # -- output ----------------------------------------------------------------

    def _result(
        self,
        context: Context,
        segments: list[_Segment],
        md_tables: list[_MarkdownTable],
        read: OCRResult,
        warnings: list[str],
    ) -> OCRResult:
        prefix = f"{context.document_id}-p{context.page:03d}"
        lines: list[Line] = []
        last_heading: str | None = None
        headings_before: dict[int, str | None] = {}
        for segment in segments:
            if segment.table_index is not None and segment.table_index not in headings_before:
                headings_before[segment.table_index] = last_heading
            elif segment.table_index is None and is_annex_heading(segment.text):
                last_heading = segment.text
            line_id = f"{prefix}-l{len(lines) + 1:04d}"
            lines.append(
                Line(
                    line_id=line_id,
                    text=segment.text,
                    bbox=segment.bbox,
                    geometry_provenance=segment.provenance if segment.bbox else None,
                )
            )
            warnings.extend(f"needs_review:{reason}:{line_id}" for reason in segment.review)
        tables = []
        for index, md in enumerate(md_tables):
            if md.table is None:
                continue
            md.table.table_id = f"{prefix}-t{len(tables) + 1:03d}"
            md.table.heading_before = headings_before.get(index)
            tables.append(md.table)
        return OCRResult(
            lines=lines,
            tables=tables,
            raw_markdown=read.raw_markdown,
            raw_output_path=read.raw_output_path,
            warnings=warnings,
        )
