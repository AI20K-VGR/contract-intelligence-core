import base64
import difflib
import re
import unicodedata
from collections import defaultdict
from io import BytesIO

import pymupdf
import pytesseract
from PIL import Image

from app.config import settings
from app.domain import DomainError, require
from app.table_continuity import is_annex_heading


def _nfc(text: str) -> str:
    """Normalize to NFC (precomposed diacritics).

    PyMuPDF's native text extraction reproduces whatever Unicode form is
    embedded in the PDF's own font/glyph table: some fonts (and some
    Tesseract/vision outputs) yield NFD (a base letter plus a separate
    combining accent, e.g. "e" + U+0300) which renders identically to NFC
    but does not byte-match literal Vietnamese regexes elsewhere in the
    codebase (structure.py's "Điều"/"Khoản"/"Điểm" patterns, facts.py's
    "Bên"/"ngày" patterns). Normalizing once, here, at the point text enters
    the system, keeps every downstream consumer consistent instead of
    requiring each one to normalize defensively.
    """
    return unicodedata.normalize("NFC", text)


# A line-pair below this text similarity (0..1, difflib ratio) is not trusted as a
# match even if the alignment below places them opposite each other — see
# _align_gpt_lines.
_LINE_MATCH_FLOOR = 0.35
# Cost of skipping a line on either side during alignment. Kept well under
# _LINE_MATCH_FLOOR's typical genuine-match scores (0.55-1.0 on real contract pages;
# see the docstring below) so two truly corresponding lines are never cheaper to skip
# past than to align, while a near-zero-similarity pair is.
_LINE_ALIGN_GAP_PENALTY = 0.3


def _align_gpt_lines(tess_texts: list[str], gpt_texts: list[str]) -> dict[int, str]:
    """Globally aligns Tesseract's lines with GPT vision's re-transcribed lines (a
    Needleman-Wunsch alignment over per-line text similarity) and returns
    `{tess_index: gpt_text}` for the pairs it trusts enough to substitute.

    Only used when the two sources disagree on line count — see process_page, which
    still does a plain position-for-position swap when the counts already match, since
    there's no ambiguity to resolve there. A count mismatch is usually one specific
    real cause: a stamp, seal, or watermark on the scanned page that Tesseract misreads
    as one or more extra "lines" of garbled text, which GPT vision (a vision model, not
    a pixel-pattern matcher) correctly recognizes as decoration and leaves out. Global
    alignment finds this even when the extra line sits in the MIDDLE of the page —
    naively zipping the two lists by index would then silently pair every later line
    with the wrong text (right words, wrong bbox) instead of just the one that's off. A
    real hard case (690758295-Scan-HỢP-ĐỒNG-Feddy.pdf, trang 1: 60 Tesseract lines vs 57
    GPT lines) had 3 pure-noise Tesseract lines (fragments of a company stamp)
    interleaved among genuine ones scoring 0.55-1.0 similarity to their true GPT
    counterpart; this correctly aligned all 56 genuine lines and dropped the 3 noise
    ones, rather than falling back to the noisier, diacritic-mangled Tesseract text for
    the whole page as before.

    A Tesseract line with no confident match is omitted from the result (the caller
    drops it) rather than kept as-is: that shape is consistently stamp/watermark noise
    in practice, not content GPT missed — keeping it would readmit exactly the garbage
    this re-transcription exists to remove.
    """
    n, m = len(tess_texts), len(gpt_texts)
    if n == 0 or m == 0:
        return {}
    similarity = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            similarity[i][j] = difflib.SequenceMatcher(
                None, tess_texts[i - 1].lower(), gpt_texts[j - 1].lower()
            ).ratio()

    score = [[0.0] * (m + 1) for _ in range(n + 1)]
    back = [[""] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        score[i][0] = score[i - 1][0] - _LINE_ALIGN_GAP_PENALTY
        back[i][0] = "up"
    for j in range(1, m + 1):
        score[0][j] = score[0][j - 1] - _LINE_ALIGN_GAP_PENALTY
        back[0][j] = "left"
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            diag = score[i - 1][j - 1] + similarity[i][j] - _LINE_ALIGN_GAP_PENALTY
            up = score[i - 1][j] - _LINE_ALIGN_GAP_PENALTY
            left = score[i][j - 1] - _LINE_ALIGN_GAP_PENALTY
            best = max(diag, up, left)
            score[i][j] = best
            back[i][j] = "diag" if best == diag else ("up" if best == up else "left")

    pairs: dict[int, str] = {}
    i, j = n, m
    while i > 0 or j > 0:
        move = back[i][j]
        if move == "diag":
            if similarity[i][j] >= _LINE_MATCH_FLOOR:
                pairs[i - 1] = gpt_texts[j - 1]
            i, j = i - 1, j - 1
        elif move == "up":
            i -= 1
        else:
            j -= 1
    return pairs


# Shared with ai-service/src/contract_ocr/infrastructure/ocr/prompts.py (kept as a plain
# copy, not an import: these are two independent projects in this repo by design). Ordered
# by priority and deliberately repetitive on "don't guess", since that is the single most
# common failure mode of vision LLMs used for transcription of legal text.
_GPT_VISION_SYSTEM_PROMPT = """\
You are a precise OCR transcription engine for legal contracts, not a document \
assistant. Your only task is to reproduce the exact text visible in the image. Follow \
these rules in order of priority:

1. Never invent, guess, or auto-complete text you cannot clearly read. If a word, \
character, digit, or stamp is illegible, smudged, cut off, or ambiguous, output the \
literal marker [illegible] in its place instead of a plausible-looking replacement. An \
honest gap is always better than a confident wrong guess.
2. Do not "correct" spelling, grammar, punctuation, or apparent typos in the source. \
Transcribe exactly what is printed or handwritten, including errors and unusual \
spacing or capitalization.
3. Numbers, dates, money amounts, percentages, tax codes, contract/article/clause \
numbers, and proper names demand the highest precision — a single misread digit or \
character changes the legal meaning of the document. If any of these are unclear, mark \
that exact span [illegible] rather than approximating a nearby-looking value.
4. Do not add anything that is not visually present on the page: no titles you \
inferred, no summaries, no translations, no explanations, no markdown formatting, no \
commentary about the document's purpose or content. Never merge separate lines or \
reorder them for readability.
5. Preserve reading order, line breaks, and Vietnamese diacritics exactly as shown. The \
document may be Vietnamese, English, or both in the same page.
6. Output only the transcribed text, one visible line per output line. Nothing else — \
no preamble, no closing remarks.

When in doubt about any specific character, word, or number: mark it [illegible]. Do \
not guess."""


def _gpt_vision_lines(image: Image.Image, config: dict) -> list[str] | None:
    """Re-transcribes the full page image with a GPT vision model, returning one string
    per visible line in reading order — or None if the call is unavailable or fails.

    Never raises: this is an optional accuracy layer on top of Tesseract (which already
    anchors bbox/line order), not a required engine, so a provider outage should degrade
    to the local text rather than fail the page. A transient failure (rate limit,
    timeout, dropped connection, 5xx) is retried by the OpenAI SDK itself — see
    Settings.ocr_vision_max_retries — before this function gives up and returns None; a
    permanent one (bad key, unknown model) is not retried and fails on the first try.
    """
    if not settings.openai_api_key:
        return None
    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=settings.openai_api_key,
            max_retries=config.get("ocr_vision_max_retries", 5),
        )
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        data_url = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
        response = client.chat.completions.create(
            model=config.get("ocr_vision_model", "gpt-5.6-terra"),
            # gpt-5.6+ rejects the legacy max_tokens param; temperature is left at the
            # model default (no override) since these models reject non-default values.
            max_completion_tokens=4096,
            messages=[
                {"role": "system", "content": _GPT_VISION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url, "detail": "high"}},
                    ],
                },
            ],
        )
        text = response.choices[0].message.content or ""
        return [_nfc(line) for line in text.splitlines() if line.strip()]
    except Exception:
        return None


def _clamp01(value):
    """Real detectors (Tesseract especially) occasionally report a word/table box that
    pokes a fraction of a pixel past the page's own edge -- floating-point drift in a
    rotation matrix, or Tesseract's own internal padding on a word flush against the
    image boundary. Left alone, that produces a normalized coordinate outside [0, 1],
    which evidence.citation() then rejects outright (CITATION_ANCHOR_INVALID) -- for
    the whole job, since worker.py builds every page's citations in one batch, not
    just the one page with the stray box. Clamping at the point coordinates are
    normalized keeps a harmless rounding error from taking down an entire job's
    otherwise-good results.
    """
    return max(0.0, min(1.0, value))


def _normalized(rect, page):
    box = pymupdf.Rect(rect) * page.rotation_matrix
    return [_clamp01(box.x0 / page.rect.width), _clamp01(box.y0 / page.rect.height),
            _clamp01(box.x1 / page.rect.width), _clamp01(box.y1 / page.rect.height)]


def _nearest_heading_above(candidates, top):
    """The closest text (from `candidates`, each a {"text", "bbox"} dict) that sits
    entirely above `top` and reads as a new section/annex heading — see
    is_annex_heading. Used as table_continuity's `heading_between` evidence: only the
    matched heading text is ever retained, everything else is discarded immediately.
    """
    best = None
    for candidate in candidates:
        text = candidate["text"].strip()
        bottom = candidate["bbox"][3]
        if not text or bottom > top:
            continue
        if best is None or bottom > best["bbox"][3]:
            best = candidate
    if best is None:
        return None
    text = best["text"].strip()
    return text if is_annex_heading(text) else None


def _find_tables(page, payload):
    # Relies on the PDF's own text/vector structure (ruling lines, column alignment);
    # image-only scanned pages have no such structure, so this legitimately finds none there.
    try:
        finder = page.find_tables()
    except Exception:
        return []
    blocks = [
        {"text": block[4], "bbox": _normalized(pymupdf.Rect(block[:4]), page)}
        for block in page.get_text("blocks")
        if block[4].strip()
    ]
    tables = []
    for index, table in enumerate(finder.tables):
        extracted = table.extract()
        rows = []
        for row_index, row in enumerate(table.rows):
            texts = extracted[row_index] if row_index < len(extracted) else []
            cells = [
                {"col_index": col_index,
                 "text": _nfc(texts[col_index]) if col_index < len(texts) else "",
                 "bbox": _normalized(cell_bbox, page)}
                for col_index, cell_bbox in enumerate(row.cells)
                if cell_bbox is not None  # None marks a slot covered by a merged neighbor cell
            ]
            rows.append({"row_index": row_index, "cells": cells})
        bbox = _normalized(table.bbox, page)
        tables.append(
            {
                "id": f"table:{payload['document_id']}:{payload['page_number']}:{index}",
                "document_id": payload["document_id"],
                "page_number": payload["page_number"],
                "row_count": table.row_count,
                "col_count": table.col_count,
                "bbox": bbox,
                "rows": rows,
                "heading_before": _nearest_heading_above(blocks, bbox[1]),
            }
        )
    return tables


_OCR_TABLE_MIN_COLUMNS = 3
_OCR_TABLE_MIN_ROWS = 3
# Mirrors tables.py's TOP_EDGE_THRESHOLD/BOTTOM_EDGE_THRESHOLD (duplicated, not
# imported: tables.py already imports table_continuity, which this module also
# imports, and tables.py would need _OCR_TABLE_MIN_ROWS back from here -- importing
# either direction would cycle). A block sitting this close to the page's own top or
# bottom edge is the layout signature of one table continuing across a page break, so
# it's still emitted as a candidate fragment even short of _OCR_TABLE_MIN_ROWS --
# letting build_logical_tables' Table Continuity Agent decide whether to fold it into
# the neighboring page's table (real case: a table's last row spills onto the next
# page as a single additional numbered item, with nothing else tabular left on that
# page — too few rows to ever pass _OCR_TABLE_MIN_ROWS on its own, so today it's
# dropped outright and the row is lost). A block in the MIDDLE of a page gets no such
# benefit of the doubt: a coincidentally column-shaped line or two there (e.g. a
# header/footer amid prose) is far more likely to be noise than a genuine
# continuation, and _OCR_TABLE_MIN_ROWS alone is what protects against that.
# Rescued this way is never trusted as a table on its own, either: tables.py drops it
# again, silently, if it doesn't end up confidently attached to a real table.
_OCR_TABLE_EDGE_TOP = 0.15
_OCR_TABLE_EDGE_BOTTOM = 0.85
# A gap this many times the previous (smaller) gap in a row marks a column boundary
# rather than ordinary word spacing — see _column_gap_threshold. A narrow column (a
# 1-2 digit STT) sits close enough to its neighbor that its own boundary gap clears
# this by a much smaller margin than a gap between two wide columns does; three real
# scanned rows (Hop_dong_scan_stress_bang_lien_trang_khong_header.pdf, trang 1) had
# their genuine STT-to-description boundary ratio land at 2.39-2.49 — real column
# structure, not word spacing, but just under the previous 2.5 cutoff, which pushed
# _column_gap_threshold past it to a much later (and wrong) split point, collapsing
# the whole row to 1-2 groups and rejecting it outright.
_OCR_TABLE_GAP_RATIO = 2.2
# Absolute floor (fraction of page width) below which a gap never counts as a column
# boundary, even on a near-empty row where the median gap itself is tiny.
_OCR_TABLE_MIN_GAP = 0.015

# A word must overlap one already-placed cell of the row above by at least this
# fraction of the word's own width to be trusted as that cell's wrapped continuation —
# see _merge_wrapped_continuation.
_OCR_TABLE_CONTINUATION_OVERLAP = 0.5


def _column_gap_threshold(gaps):
    """The gap size that separates ordinary within-cell word-spacing from a real
    column boundary: the FIRST relative jump, scanning the SORTED gap list from its
    smallest values upward, that (a) clears _OCR_TABLE_GAP_RATIO and (b) lands at or
    above the absolute floor _OCR_TABLE_MIN_GAP — not a median, and not simply
    whichever jump anywhere in the row happens to be biggest. A median picks the
    wrong side once a row's cells average more than one word each — e.g. a real
    header row of "Tên hàng", "Đơn giá", "Ghi chú" has as many (or more) small
    within-cell gaps as there are actual columns, which can push the median onto a
    between-column gap and make the threshold too high to separate anything.

    Picking the single BIGGEST jump (rather than the first qualifying one) fails a
    different, common way: a real item row's own column gaps are rarely all the same
    width — a narrow STT column sits close to its neighbor while a wide description
    column trails off into a much bigger gap before the next value. Real case: gaps of
    0.008 (word spacing), 0.024, 0.044, 0.048 (three genuine, differently-sized column
    boundaries) and 0.159 (the widest one, after a long description) all in one row.
    The biggest RATIO jump anywhere in that list is the LAST one (0.048 -> 0.159) —
    picking it as the sole cutoff lumps the earlier 0.024/0.044/0.048 boundaries in
    with ordinary word spacing, collapsing 6 real columns down to 2 and causing
    _row_cells to reject the entire row as not looking like a table at all. The
    smallest-first search instead locks onto the boundary between "still word
    spacing" and "definitely a gap", the moment it's confidently seen (a big enough
    ratio AND a big enough absolute size to rule out noise from a near-zero
    denominator inflating the ratio) — every larger real gap after that point is only
    further evidence of a boundary, never grounds to reclassify it as spacing.

    No jump clears _OCR_TABLE_GAP_RATIO at or above _OCR_TABLE_MIN_GAP at all (every
    gap is roughly the same size, e.g. ordinary prose with uniform word-spacing) means
    there's no real column boundary in this row — the threshold is set above every gap
    so the caller merges everything into one group and (being under
    _OCR_TABLE_MIN_COLUMNS) rejects it.
    """
    positive = sorted(g for g in gaps if g > 0)
    if not positive:
        return _OCR_TABLE_MIN_GAP
    for i in range(len(positive) - 1):
        # The floor applies to the CANDIDATE gap itself (positive[i + 1], the value that
        # would start counting as "a boundary"), not to the midpoint returned as the
        # threshold: a tiny word-spacing pair (e.g. 0.002 -> 0.0056) can still produce a
        # ratio over _OCR_TABLE_GAP_RATIO purely because both sides are minuscule, which
        # is noise, not a real column gap — but a tiny word-spacing gap followed by an
        # already-plausible column-sized gap (0.003 -> 0.02) is exactly the real signal
        # this function exists to find, even though their midpoint alone sits under the
        # floor.
        if positive[i + 1] < _OCR_TABLE_MIN_GAP:
            continue
        if positive[i + 1] / positive[i] > _OCR_TABLE_GAP_RATIO:
            return (positive[i] + positive[i + 1]) / 2
    return positive[-1] + 1.0


# A misread table ruling line, standalone (not glued to a real word) — see
# _merge_wrapped_continuation's own docstring on this exact class of noise
# ("a vertical border read as '|' or '›', a corner read as ':' or '\\'"). Used by
# _split_ruling_line_noise below for a DIFFERENT manifestation of the same noise: one
# that lands so close to both its real neighbors that _column_gap_threshold can't
# distinguish it from ordinary word-spacing (a real hard case: a "Thành tiền"/"Ghi
# chú" column divider read as "|", both gaps around it under 0.006 — the row's other,
# genuine column gaps are 0.02-0.05 — so it gets grouped WITH one or both real
# neighbors instead of separating them).
_RULING_LINE_NOISE_PATTERN = re.compile(r"^[|›:\\]+$")


def _split_ruling_line_noise(groups):
    """A misread vertical table rule sometimes lands close enough to both its real
    neighbors that gap-based grouping alone glues it into the same group as one or
    both of them — silently concatenating two genuinely different columns' values
    into one cell (see _RULING_LINE_NOISE_PATTERN). Once grouped, though, the noise
    token itself is trivial to recognize (pure ruling-line punctuation, never
    alphanumeric): split the group there and drop the token, rather than leaving two
    real columns fused together.
    """
    result = []
    for group in groups:
        current = []
        for word in group:
            if _RULING_LINE_NOISE_PATTERN.match(word["text"]):
                if current:
                    result.append(current)
                current = []
                continue
            current.append(word)
        if current:
            result.append(current)
    return result


def _raw_word_groups(words):
    """`words` (already sorted by x0) split into cell-like groups by gap, with no
    minimum group count enforced — shared by _row_cells (which does enforce
    _OCR_TABLE_MIN_COLUMNS on top of this) and _row_from_reference_overlap's own
    precondition. A single group back (no gap in the row clears
    _column_gap_threshold at all, or there are fewer than 2 words to have a gap
    between) means this line's own geometry shows no internal column structure
    whatsoever — plain, uniformly-spaced prose."""
    if len(words) < 2:
        return [words] if words else []
    gaps = [words[k + 1]["bbox"][0] - words[k]["bbox"][2] for k in range(len(words) - 1)]
    threshold = _column_gap_threshold(gaps)
    groups = [[words[0]]]
    for k in range(1, len(words)):
        if gaps[k - 1] <= threshold:
            groups[-1].append(words[k])
        else:
            groups.append([words[k]])
    return _split_ruling_line_noise(groups)


def _row_cells(line):
    """Splits one OCR line's words into cell-like groups by gap. Returns None if the
    line doesn't look like a table row at all (fewer than _OCR_TABLE_MIN_COLUMNS
    groups) — ordinary prose, even indented or with one wide gap, never qualifies."""
    words = sorted(line["words"], key=lambda w: w["bbox"][0])
    if len(words) < _OCR_TABLE_MIN_COLUMNS:
        return None
    groups = _raw_word_groups(words)
    if len(groups) < _OCR_TABLE_MIN_COLUMNS:
        return None
    return [
        {
            "text": " ".join(w["text"] for w in group),
            "bbox": [
                min(w["bbox"][0] for w in group),
                min(w["bbox"][1] for w in group),
                max(w["bbox"][2] for w in group),
                max(w["bbox"][3] for w in group),
            ],
        }
        for group in groups
    ]


def _best_overlapping_cell(cells, bbox):
    """The cell in `cells` that `bbox` overlaps most, by fraction of `bbox`'s own
    width — or None if nothing overlaps enough (_OCR_TABLE_CONTINUATION_OVERLAP) to
    trust the match."""
    x0, _, x1, _ = bbox
    width = x1 - x0
    if width <= 0:
        return None
    best, best_ratio = None, 0.0
    for cell in cells:
        overlap = max(0.0, min(x1, cell["bbox"][2]) - max(x0, cell["bbox"][0]))
        ratio = overlap / width
        if ratio > best_ratio:
            best, best_ratio = cell, ratio
    return best if best_ratio >= _OCR_TABLE_CONTINUATION_OVERLAP else None


def _merge_wrapped_continuation(last_cells, line):
    """True (and merges in place) if `line` looks like the wrapped continuation of one
    or more of `last_cells` — the row above's already-placed cells — rather than noise:
    each word that overlaps some cell of that row well enough to trust is merged into
    it; a word that overlaps nothing is silently dropped rather than rejecting the
    whole line over it. A long item description commonly wraps onto several visual
    lines, and a real scanned contract can also wrap a second column (e.g. a narrow
    "Ghi chú" note) on the very same wrapped line, so words are matched individually
    and grouped by whichever cell they land on, not treated as belonging to one cell.

    Real scans routinely misread a table's own ruling lines as stray characters (a
    vertical border read as "|" or "›", a corner read as ":" or "\\") scattered at
    arbitrary x-positions, including right where the anchor/STT column sits — an
    earlier version of this function treated ANY word landing there as proof this must
    be a new row and rejected the whole continuation over it, which made ordinary grid-
    line noise fragment the table. Whether a line is a continuation at all is decided
    by the caller (_fits_reference must fail first) before this is ever called, so
    dropping unmatched noise here and merging what legitimately overlaps is safe.

    Requires at least HALF the line's words to find a home, though, not just one: an
    unrelated line (a section heading, a stray test-case note) sitting right after a
    table row can easily have a single word's bbox coincidentally overlap one of that
    row's cells by chance, especially a wide "mô tả"-style cell — with no such floor,
    that one coincidence would be enough to glue an entire unrelated sentence onto the
    row's description (a real hard case: "PHỤ LỤC 02 - BẢNG DỊCH VỤ VẬN HÀNH (BẢNG B)",
    a section title, got absorbed this way by the row above it before this floor was
    added). A genuine wrapped continuation — even one mixed with a stray border-noise
    character or two, like "› chào giá. i" — always has most of its words belonging to
    the same real cell; it's specifically the noise words that don't overlap anything,
    never the majority. Returns False when fewer than half the words found a home:
    nothing to merge, or not confidently a continuation of anything.
    """
    words = sorted(line.get("words") or [], key=lambda w: w["bbox"][0])
    if not words:
        return False
    by_id = {id(cell): cell for cell in last_cells}
    groups: dict[int, list[dict]] = {}
    for word in words:
        target = _best_overlapping_cell(last_cells, word["bbox"])
        if target is None:
            continue
        groups.setdefault(id(target), []).append(word)
    placed = sum(len(group_words) for group_words in groups.values())
    if placed < len(words) / 2:
        return False
    for cell_id, group_words in groups.items():
        cell = by_id[cell_id]
        cell["text"] = (cell["text"] + " " + " ".join(w["text"] for w in group_words)).strip()
        cell["bbox"] = [
            min(cell["bbox"][0], min(w["bbox"][0] for w in group_words)),
            cell["bbox"][1],
            max(cell["bbox"][2], max(w["bbox"][2] for w in group_words)),
            max(cell["bbox"][3], max(w["bbox"][3] for w in group_words)),
        ]
    return True


def _matching_cells(cells, reference_cells):
    """The subset of `cells` that looks like a fresh row of the same table as
    `reference_cells` (the block's first row) — or None if it doesn't. Each cell that
    overlaps a reference cell well enough to trust is kept (against a DISTINCT
    reference cell each — two of this row's own cells landing on the same column is
    ambiguous, not noise, and disqualifies the row entirely); a cell that overlaps
    nothing is dropped as noise (a stray character from a misread table ruling line)
    rather than disqualifying the whole row over it. What's left must cover a
    substantial share of the reference's own columns — at least half, and never fewer
    than 2 — to count as a new row at all; one or two coincidental matches is a wrapped
    continuation, not a new row (see _merge_wrapped_continuation). Column *count*
    deliberately doesn't have to match the reference's: a real row is very often
    missing a value somewhere (a blank trailing "Ghi chú" note is common), and that
    blank cell simply won't appear here — flush() already handles a row with fewer
    cells than the others just fine.

    Deliberately does NOT require any specific column (e.g. the STT/anchor column) to
    be present. On a real scan, OCR's own line segmentation frequently splits a row's
    sequence number onto a slightly different line than the rest of that row's first
    line — requiring it specifically would reject genuine new rows whenever that
    happens, which turns out to be routine rather than rare.

    Each kept cell is tagged with the reference cell's own position (`col_index`) —
    the column identity this overlap match just established — rather than leaving the
    caller to re-derive column positions later from raw left edges (see _ocr_tables'
    flush(), which places cells by this tag directly). A real row's own cell can start
    to the left of where its column's *label* started (a misread leading digit, or just
    a longer value, pulling a word-group's left edge further out than the reference
    cell it still clearly overlaps best) — re-clustering those raw left edges afterward
    can then see two distinct positions for what this function already correctly
    identified as the very same column, and wrongly conclude the block's shape is
    inconsistent. Trusting the overlap match's own verdict instead avoids that.
    """
    if not reference_cells:
        return None
    index_by_id = {id(cell): index for index, cell in enumerate(reference_cells)}
    matched: list[dict] = []
    seen_ids: set[int] = set()
    for cell in cells:
        target = _best_overlapping_cell(reference_cells, cell["bbox"])
        if target is None:
            continue
        if id(target) in seen_ids:
            return None
        seen_ids.add(id(target))
        matched.append({**cell, "col_index": index_by_id[id(target)]})
    if len(seen_ids) >= max(2, (len(reference_cells) + 1) // 2):
        return matched
    return None


def _row_from_reference_overlap(reference_cells, line):
    """A fresh row built directly from `line`'s raw WORDS mapped onto the already-
    established reference columns — for when the line's OWN gap segmentation
    (_row_cells) is too compressed or inconsistent to split it into cells at all,
    but its words plainly cover most of the table's width anyway.

    _matching_cells already proves that overlap against the reference, by itself, is
    a trustworthy way to recognize a new row — it just needs _row_cells to have
    produced cells to test in the first place. A row's own internal word spacing
    occasionally comes out too uniform for _row_cells to find any column boundary in
    it at all (a real hard case: an item description ending right where the next
    column starts, with no more separation than an ordinary word gap), and without
    this fallback such a line falls through to _merge_wrapped_continuation, which
    welds it onto the row above instead — silently merging two real rows into one and
    losing the second one entirely (real hard case: items 11 and 12 collapsed into a
    single row, their SL/Đơn giá/Thành tiền values concatenated together).

    Same bar as _matching_cells for calling this a row at all (at least half the
    reference's own columns, never fewer than 2) — genuine wrapped continuations
    typically touch only one column, or two when a second, narrower column wraps at
    the same visual height (see _merge_wrapped_continuation); covering most of the
    table's columns is a different signal entirely; a fresh row that happened to fail
    self-segmentation, not a wrapped fragment of the row above.

    Requires the line to show SOME internal gap structure of its own first (at least
    2 raw groups via _raw_word_groups), not just coincidental reference-column
    overlap: a table with only 2-3 columns (so "half the columns" is a low bar of 2)
    has a description column wide enough that an entirely unrelated paragraph of
    plain, uniformly-spaced prose sitting at the same horizontal position — a stray
    "Ghi chú kiểm thử" note, a signature block label — can have a couple of its own
    words coincidentally land near a narrow price column purely by chance, with
    nothing in the line's OWN geometry suggesting it's table-shaped at all. A line
    collapsing to a single raw group means _column_gap_threshold found no internal
    gap worth trusting in it whatsoever; relying on reference overlap alone for that
    case is exactly what glued an unrelated paragraph onto a real row in practice.
    """
    words = sorted(line.get("words") or [], key=lambda w: w["bbox"][0])
    if len(_raw_word_groups(words)) < 2:
        return None
    index_by_id = {id(cell): index for index, cell in enumerate(reference_cells)}
    groups: dict[int, list[dict]] = {}
    for word in words:
        target = _best_overlapping_cell(reference_cells, word["bbox"])
        if target is None:
            continue
        groups.setdefault(id(target), []).append(word)
    if len(groups) < max(2, (len(reference_cells) + 1) // 2):
        return None
    return [
        {
            "col_index": index_by_id[target_id],
            "text": " ".join(w["text"] for w in group_words),
            "bbox": [
                min(w["bbox"][0] for w in group_words),
                min(w["bbox"][1] for w in group_words),
                max(w["bbox"][2] for w in group_words),
                max(w["bbox"][3] for w in group_words),
            ],
        }
        for target_id, group_words in groups.items()
    ]


def _extend_reference_with_confirming_row(reference_cells, row0_cells, cells):
    """Adds any of `cells` that don't overlap an existing reference column as a
    brand-new one, inserted (by left edge, not appended at the end) into
    `reference_cells` in place — meant to be called only once, for the row that
    FIRST confirms the reference (the block's second row), so a column the
    reference's own first row happened to leave blank still gets captured instead of
    never existing at all.

    Real hard case: the very first item of a Khối lượng/Đơn giá/Thành tiền table had
    no value whatsoever in its own Khối lượng column (a genuinely blank field on that
    one row, not a missed OCR read) — so that column position never entered the
    reference to begin with. Every OTHER row's own quantity value then had nothing to
    overlap and was silently dropped as noise (see _matching_cells), not just on the
    first row but on every single row of the table — an entire real column vanished
    rather than merely one blank cell.

    Restricted to this one confirming moment deliberately, not tried again for every
    later row: an ordinary stray character (a misread table border, a stamp
    fragment) on some row 40 rows in must still be dropped as noise, not promoted
    into a permanent phantom column. The first confirming row is the one moment
    there's a principled reason to trust an unmatched cell as a real column instead
    of noise — two independent rows of the very same table, each internally
    consistent, disagreeing only on which columns happen to be filled in.

    A newly-found column takes its rightful place among the existing ones by x0, with
    every later column's (and `row0_cells`' matching own cells') col_index bumped up
    to make room — the block's first row is a SEPARATE object from the reference by
    design (see _ocr_tables) precisely so renumbering it here never invents a value
    it never had; its Khối lượng cell simply stays absent, rendering as blank.
    """
    for cell in cells:
        if _best_overlapping_cell(reference_cells, cell["bbox"]) is not None:
            continue
        insert_at = next(
            (i for i, ref_cell in enumerate(reference_cells) if cell["bbox"][0] < ref_cell["bbox"][0]),
            len(reference_cells),
        )
        for ref_cell in reference_cells:
            if ref_cell["col_index"] >= insert_at:
                ref_cell["col_index"] += 1
        for row0_cell in row0_cells:
            if row0_cell["col_index"] >= insert_at:
                row0_cell["col_index"] += 1
        reference_cells.insert(insert_at, {**cell, "col_index": insert_at})


def _plausible_row(cells):
    """True if `cells` has enough real textual content to trust as a fresh table
    reference — the row every later line gets matched or merged against.

    A page-top artifact (a faint watermark, a decorative rule, a margin smudge) that
    Tesseract misreads often lands as a handful of ISOLATED single-glyph tokens spread
    across the row ("~", "Z", "x", "4", "^`") — enough of them, spaced widely enough, to
    clear _row_cells' >=3-groups bar despite being pure noise, no different in shape from
    the stray characters _merge_wrapped_continuation already tolerates *inside* an
    established row. The difference here is what happens if such a line becomes the
    reference itself, at the very top of a fresh block: every real row that follows
    correctly fails to match it (its columns aren't real columns), but then gets
    silently absorbed as that garbage row's own "wrapped continuation" instead — a single
    word overlapping any one of several scattered noise cells is enough — so the block
    never grows past that one bogus row and the entire real table beneath it is
    discarded. A real column's label or value is essentially never a single glyph, so
    requiring most cells to carry more than one character rejects exactly this pattern
    without touching genuine rows (an STT column's own single digit is the only
    common one-character cell in a real row, comfortably outnumbered by the rest).
    """
    if not cells:
        return False
    substantial = sum(1 for cell in cells if len(cell["text"].strip()) > 1)
    return substantial >= max(2, (len(cells) + 1) // 2)


def _ocr_tables(lines, payload):
    """Detects tables from OCR line/word geometry alone — scanned pages have no PDF
    vector/text structure for PyMuPDF's find_tables to read (see _find_tables).

    A run of consecutive lines that each place onto the same small set of columns —
    established from the block's first (plausible-looking, see _plausible_row) row and
    matched by overlap, not by raw word-group count (see _matching_cells) — is treated
    as one table; a row's cell keeps whichever reference column it overlapped as its
    permanent `col_index` from the moment it's matched, rather than that position being
    re-derived later from raw left edges (a real row's own cell can start further left
    or right than its column's label did — a longer value, a misread leading digit — and
    still be unambiguously the same column, so column identity is decided once, by
    overlap, and never revisited). Matching by overlap against a reference row, rather
    than requiring an identical group count row to row, is what lets a row with a
    legitimately blank cell (that "Ghi chú" note again) still count as an ordinary row
    instead of breaking the run.

    A line that doesn't fit the block's reference row first gets checked against
    _merge_wrapped_continuation: a real scanned contract routinely wraps a long item
    description onto 2-3 visual lines (and sometimes a second, narrower column — e.g. a
    "Ghi chú" note — wraps at the same time), and each wrapped line is its own OCR
    "line" with far fewer word-groups than a full row. Rather than treating that as a
    new row or as noise, its words are merged into whichever cell(s) of the row above
    they horizontally line up with, extending that cell's text and bbox in place. Only
    once a line doesn't look like a continuation of anything either is it treated as a
    genuine anomaly.

    A single anomalous row is not treated as proof the run has ended, though: a stamp
    or seal overlapping one row's words routinely adds, swallows, or merges its
    word-groups badly enough that it neither fits the reference row nor overlaps the
    row above like a continuation would, and killing the whole run over it would
    silently drop the entire table (real hard case: a table interrupted mid-body by a
    company seal). Such a row is instead skipped outright — its data is never included,
    never guessed at — while the run keeps accumulating against the reference row
    already established. Two such anomalous rows back to back (no matching row or
    continuation in between) means the run has genuinely moved on to something else,
    e.g. real prose starting right after the table; that flushes whatever was
    accumulated and restarts fresh from the second anomalous row. A block shorter than
    _OCR_TABLE_MIN_ROWS drops instead of emitting a guessed table — same "surface for
    review instead of guessing" posture as the rest of the table pipeline (tables.py)
    — unless it sits right at the page's own top or bottom edge, the layout signature
    of a table continuing across a page break (see _OCR_TABLE_EDGE_TOP/_BOTTOM): that
    one is still emitted, but only build_logical_tables' Table Continuity Agent, not
    this function, ever gets to trust it as part of a real table. A row landing two of
    its own cells on the same reference column never reaches the block at all
    (_matching_cells rejects that row outright, as too ambiguous).
    """
    tables: list[dict] = []
    block: list[tuple[dict, list[dict]]] = []
    # The block's column definitions — deliberately a separate object from any one
    # row's own displayed cells (block[0][1] included), so extending it later (see
    # _extend_reference_with_confirming_row) never retroactively puts a value into a
    # row that never actually had it.
    reference: list[dict] | None = None

    def _as_reference(cells):
        return [{**cell, "col_index": index} for index, cell in enumerate(cells)]

    def flush():
        if not block:
            return
        top = min(line["bbox"][1] for line, _ in block)
        bottom = max(line["bbox"][3] for line, _ in block)
        under_min_rows = len(block) < _OCR_TABLE_MIN_ROWS
        if under_min_rows and not (top <= _OCR_TABLE_EDGE_TOP or bottom >= _OCR_TABLE_EDGE_BOTTOM):
            return
        col_count = len(reference)
        rows = [
            {
                "row_index": row_index,
                "cells": [
                    {"col_index": cell["col_index"], "text": cell["text"], "bbox": cell["bbox"]}
                    for cell in cells
                ],
            }
            for row_index, (_, cells) in enumerate(block)
        ]
        tables.append(
            {
                "id": f"table:{payload['document_id']}:{payload['page_number']}:{len(tables)}",
                "document_id": payload["document_id"],
                "page_number": payload["page_number"],
                "row_count": len(rows),
                "col_count": col_count,
                "bbox": [
                    min(c["bbox"][0] for r in rows for c in r["cells"]),
                    top,
                    max(c["bbox"][2] for r in rows for c in r["cells"]),
                    bottom,
                ],
                "rows": rows,
                "heading_before": _nearest_heading_above(lines, top),
                # Only ever True for the page-edge exception above: a real, ordinary
                # (>= _OCR_TABLE_MIN_ROWS) block is always confident on its own.
                "low_confidence": under_min_rows,
            }
        )

    mismatch_streak = 0
    for line in lines:
        cells = _row_cells(line)
        if cells is None:
            # This line's own word spacing was too compressed/inconsistent for
            # _row_cells to split into cells at all — but if its words plainly cover
            # most of the table's own columns anyway, it's a fresh row that failed
            # self-segmentation, not nothing (see _row_from_reference_overlap).
            matched_cells = _row_from_reference_overlap(reference, line) if reference else None
        elif reference is None:
            # Nothing to filter against yet: this becomes the reference — but only if it
            # looks like a real row (see _plausible_row). A noise line crowned as the
            # reference here would never itself get replaced: every real row after it
            # correctly fails to match, but a stray word then coincidentally overlapping
            # one of its scattered noise cells is all it takes for _merge_wrapped_continuation
            # to wrongly absorb that real row as this one's "continuation" instead — so the
            # block never grows and the entire real table beneath the noise is lost.
            if _plausible_row(cells):
                reference = _as_reference(cells)
                # A genuinely independent set of dicts, not a shallow copy sharing
                # reference's own cell objects — _extend_reference_with_confirming_row
                # mutates each side's col_index separately, and shared objects would
                # silently double-apply that shift (or leak a value into a row that
                # never actually had it).
                matched_cells = _as_reference(cells)
            else:
                matched_cells = None
        else:
            matched_cells = _matching_cells(cells, reference)
            if matched_cells is not None and len(block) == 1:
                # The block's very first row may have left a real column blank (see
                # _extend_reference_with_confirming_row) — this confirming second row
                # is the one moment there's principled evidence an unmatched cell is
                # that missing column rather than noise.
                before = len(reference)
                _extend_reference_with_confirming_row(reference, block[0][1], cells)
                if len(reference) != before:
                    matched_cells = _matching_cells(cells, reference)
        if matched_cells is not None:
            block.append((line, matched_cells))
            mismatch_streak = 0
            continue
        if block and _merge_wrapped_continuation(block[-1][1], line):
            block[-1][0]["bbox"][3] = max(block[-1][0]["bbox"][3], line["bbox"][3])
            mismatch_streak = 0
            continue
        mismatch_streak += 1
        if mismatch_streak >= 2:
            flush()
            if cells is not None and _plausible_row(cells):
                reference = _as_reference(cells)
                block = [(line, _as_reference(cells))]
            else:
                reference = None
                block = []
            mismatch_streak = 0
        # else: one-off anomaly (e.g. a stamp mangling just this one row, badly
        # enough that it doesn't even split into word-groups at all) — drop
        # this row and keep accumulating against the same reference row.
    flush()
    return tables


def process_page(payload, config, store):
    with pymupdf.open(store.path(payload["storage_key"])) as pdf:
        page = pdf[payload["page_number"] - 1]
        scale = config["dpi"] / 72
        require(
            page.rect.width * page.rect.height * scale * scale <= config["max_pixels"],
            "PIXEL_BUDGET_EXCEEDED",
            422,
        )
        pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
        image_key = store.put(pix.tobytes("png"), "png")
        tables = _find_tables(page, payload)
        raw_words = page.get_text("words", sort=True)
        # Any embedded image makes native coverage uncertain: OCR the rendered page once.
        native = bool(raw_words) and not page.get_images()
        groups = defaultdict(list)
        if native:
            for word in raw_words:
                box = pymupdf.Rect(word[:4]) * page.rotation_matrix
                bbox = [
                    _clamp01(box.x0 / page.rect.width),
                    _clamp01(box.y0 / page.rect.height),
                    _clamp01(box.x1 / page.rect.width),
                    _clamp01(box.y1 / page.rect.height),
                ]
                # A word that still has no real area after clamping is a degenerate
                # detection (zero-width/height, or entirely outside the page) with no
                # actual glyph to cite -- dropped here rather than left to fail
                # evidence.citation() later and take the whole job down over noise.
                if bbox[0] >= bbox[2] or bbox[1] >= bbox[3]:
                    continue
                groups[(word[5], word[6])].append({"text": _nfc(word[4]), "bbox": bbox})
            engine = "pymupdf"
        else:
            image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            try:
                data = pytesseract.image_to_data(
                    image,
                    lang=config["ocr_languages"],
                    output_type=pytesseract.Output.DICT,
                    timeout=config["ocr_timeout_seconds"],
                    # PSM 6 ("single uniform block of text") over the default PSM 3
                    # ("fully automatic"): PSM 3 tries to detect a multi-column/mixed
                    # layout and, on a plain contract page, sometimes mis-clusters
                    # words into the wrong block/paragraph, which garbles line order
                    # once words are grouped and joined below.
                    config="--psm 6",
                )
            except pytesseract.TesseractNotFoundError as exc:
                # Infra/environment error, not document content: safe to classify distinctly
                # instead of the generic PAGE_PROCESSING_FAILED every other exception gets.
                raise DomainError("OCR_ENGINE_UNAVAILABLE", 503) from exc
            for i, text in enumerate(data["text"]):
                if not text.strip():
                    continue
                x, y, w, h = (data[key][i] for key in ("left", "top", "width", "height"))
                bbox = [
                    _clamp01(x / pix.width),
                    _clamp01(y / pix.height),
                    _clamp01((x + w) / pix.width),
                    _clamp01((y + h) / pix.height),
                ]
                # Tesseract occasionally reports a zero-width/height phantom detection
                # (w or h == 0) alongside real words -- no real glyph to cite, so it's
                # dropped here rather than left to fail evidence.citation() later (see
                # _clamp01) and take the whole job down over one bad word.
                if bbox[0] >= bbox[2] or bbox[1] >= bbox[3]:
                    continue
                groups[(data["block_num"][i], data["par_num"][i], data["line_num"][i])].append(
                    {"text": _nfc(text), "bbox": bbox}
                )
            engine = "tesseract"
        lines = []
        for words in groups.values():
            text = " ".join(w["text"] for w in words)
            boxes = [w["bbox"] for w in words]
            lines.append(
                {
                    "id": f"{payload['document_id']}:{payload['page_number']}:{len(lines)}",
                    "text": text,
                    "words": words,
                    "bbox": [
                        min(b[0] for b in boxes),
                        min(b[1] for b in boxes),
                        max(b[2] for b in boxes),
                        max(b[3] for b in boxes),
                    ],
                }
            )

        issue = None
        if lines and engine == "tesseract" and config.get("ocr_engine") == "gpt_vision":
            # Tesseract stays the source of bbox/line order; a GPT vision re-transcription
            # only ever REPLACES the text of an already-anchored line, never its position.
            # When both sources agree on line count, pairing by position needs no further
            # evidence. When they don't, _align_gpt_lines works out the correspondence
            # (and drops whichever Tesseract lines don't confidently match anything —
            # see its docstring) instead of discarding the whole re-transcription.
            gpt_lines = _gpt_vision_lines(image, config)
            if gpt_lines is None:
                issue = "GPT_VISION_UNAVAILABLE"
            elif len(gpt_lines) == len(lines):
                for line, gpt_text in zip(lines, gpt_lines):
                    line["text"] = gpt_text
                engine = f"tesseract+{config.get('ocr_vision_model', 'gpt-5.6-terra')}"
            else:
                matches = _align_gpt_lines([line["text"] for line in lines], gpt_lines)
                if not matches:
                    issue = "GPT_VISION_LINE_COUNT_MISMATCH"
                else:
                    lines = [
                        {**line, "text": matches[i]} for i, line in enumerate(lines) if i in matches
                    ]
                    engine = f"tesseract+{config.get('ocr_vision_model', 'gpt-5.6-terra')}"

        if not tables and engine.startswith("tesseract"):
            # No native PDF structure for find_tables to read on a scanned page — fall
            # back to detecting a table from the OCR words' own geometry.
            tables = _ocr_tables(lines, payload)

        # OCR empty output is not proof of a blank page.
        if not lines:
            status, issue = "needs_review", "EMPTY_OCR_REQUIRES_REVIEW"
        else:
            status = "needs_review" if issue else "completed"
        return {
            **payload,
            "width": pix.width,
            "height": pix.height,
            "rotation": page.rotation,
            "image_key": image_key,
            "lines": lines,
            "tables": tables,
            "engine": engine,
            "status": status,
            "issue": issue,
        }
