import base64
import difflib
import unicodedata
from collections import defaultdict
from io import BytesIO

import pymupdf
import pytesseract
from PIL import Image

from app.config import settings
from app.domain import DomainError, require


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


def _normalized(rect, page):
    box = pymupdf.Rect(rect) * page.rotation_matrix
    return [box.x0 / page.rect.width, box.y0 / page.rect.height,
            box.x1 / page.rect.width, box.y1 / page.rect.height]


def _find_tables(page, payload):
    # Relies on the PDF's own text/vector structure (ruling lines, column alignment);
    # image-only scanned pages have no such structure, so this legitimately finds none there.
    try:
        finder = page.find_tables()
    except Exception:
        return []
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
        tables.append(
            {
                "id": f"table:{payload['document_id']}:{payload['page_number']}:{index}",
                "document_id": payload["document_id"],
                "page_number": payload["page_number"],
                "row_count": table.row_count,
                "col_count": table.col_count,
                "bbox": _normalized(table.bbox, page),
                "rows": rows,
            }
        )
    return tables


_OCR_TABLE_MIN_COLUMNS = 3
_OCR_TABLE_MIN_ROWS = 3
# A gap this many times a row's own median inter-word gap marks a column boundary
# rather than an ordinary word space. Relative to the row's own median (not a fixed
# pixel/fraction threshold) so it scales with whatever font size and DPI the page was
# scanned at, instead of needing a different constant per scan quality.
_OCR_TABLE_GAP_RATIO = 2.5
# Absolute floor (fraction of page width) below which a gap never counts as a column
# boundary, even on a near-empty row where the median gap itself is tiny.
_OCR_TABLE_MIN_GAP = 0.015

# A word must overlap one already-placed cell of the row above by at least this
# fraction of the word's own width to be trusted as that cell's wrapped continuation —
# see _merge_wrapped_continuation.
_OCR_TABLE_CONTINUATION_OVERLAP = 0.5


def _column_gap_threshold(gaps):
    """The gap size that separates ordinary within-cell word-spacing from a real
    column boundary: the biggest relative jump between consecutive sizes in the
    SORTED gap list, not a median. A median picks the wrong side once a row's cells
    average more than one word each — e.g. a real header row of "Tên hàng", "Đơn
    giá", "Ghi chú" has as many (or more) small within-cell gaps as there are actual
    columns, which can push the median onto a between-column gap and make the
    threshold too high to separate anything. The biggest-jump split doesn't care how
    many of each kind there are, only that they're sized differently.

    No jump clears _OCR_TABLE_GAP_RATIO at all (every gap is roughly the same size,
    e.g. ordinary prose with uniform word-spacing) means there's no real column
    boundary in this row — the threshold is set above every gap so the caller merges
    everything into one group and (being under _OCR_TABLE_MIN_COLUMNS) rejects it.
    """
    positive = sorted(g for g in gaps if g > 0)
    if not positive:
        return _OCR_TABLE_MIN_GAP
    best_index, best_ratio = None, _OCR_TABLE_GAP_RATIO
    for i in range(len(positive) - 1):
        ratio = positive[i + 1] / positive[i]
        if ratio > best_ratio:
            best_ratio, best_index = ratio, i
    if best_index is None:
        return positive[-1] + 1.0
    return max(_OCR_TABLE_MIN_GAP, (positive[best_index] + positive[best_index + 1]) / 2)


def _row_cells(line):
    """Splits one OCR line's words into cell-like groups by gap. Returns None if the
    line doesn't look like a table row at all (fewer than _OCR_TABLE_MIN_COLUMNS
    groups) — ordinary prose, even indented or with one wide gap, never qualifies."""
    words = sorted(line["words"], key=lambda w: w["bbox"][0])
    if len(words) < _OCR_TABLE_MIN_COLUMNS:
        return None
    gaps = [words[k + 1]["bbox"][0] - words[k]["bbox"][2] for k in range(len(words) - 1)]
    threshold = _column_gap_threshold(gaps)
    groups = [[words[0]]]
    for k in range(1, len(words)):
        if gaps[k - 1] <= threshold:
            groups[-1].append(words[k])
        else:
            groups.append([words[k]])
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
    review instead of guessing" posture as the rest of the table pipeline (tables.py);
    a row landing two of its own cells on the same reference column never reaches the
    block at all (_matching_cells rejects that row outright, as too ambiguous).
    """
    tables: list[dict] = []
    block: list[tuple[dict, list[dict]]] = []

    def _as_reference(cells):
        return [{**cell, "col_index": index} for index, cell in enumerate(cells)]

    def flush():
        if len(block) < _OCR_TABLE_MIN_ROWS:
            return
        col_count = len(block[0][1])
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
                    min(line["bbox"][1] for line, _ in block),
                    max(c["bbox"][2] for r in rows for c in r["cells"]),
                    max(line["bbox"][3] for line, _ in block),
                ],
                "rows": rows,
            }
        )

    mismatch_streak = 0
    for line in lines:
        cells = _row_cells(line)
        if cells is None:
            matched_cells = None
        elif not block:
            # Nothing to filter against yet: this becomes the reference — but only if it
            # looks like a real row (see _plausible_row). A noise line crowned as the
            # reference here would never itself get replaced: every real row after it
            # correctly fails to match, but a stray word then coincidentally overlapping
            # one of its scattered noise cells is all it takes for _merge_wrapped_continuation
            # to wrongly absorb that real row as this one's "continuation" instead — so the
            # block never grows and the entire real table beneath the noise is lost.
            matched_cells = _as_reference(cells) if _plausible_row(cells) else None
        else:
            matched_cells = _matching_cells(cells, block[0][1])
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
            block = (
                [(line, _as_reference(cells))]
                if cells is not None and _plausible_row(cells) else []
            )
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
                groups[(word[5], word[6])].append(
                    {
                        "text": _nfc(word[4]),
                        "bbox": [
                            box.x0 / page.rect.width,
                            box.y0 / page.rect.height,
                            box.x1 / page.rect.width,
                            box.y1 / page.rect.height,
                        ],
                    }
                )
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
                groups[(data["block_num"][i], data["par_num"][i], data["line_num"][i])].append(
                    {
                        "text": _nfc(text),
                        "bbox": [
                            x / pix.width,
                            y / pix.height,
                            (x + w) / pix.width,
                            (y + h) / pix.height,
                        ],
                    }
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
