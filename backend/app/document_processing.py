import base64
import difflib
import json
import re
import unicodedata
from collections import defaultdict
from io import BytesIO

import pymupdf
import pytesseract
from PIL import Image

from app.config import settings
from app.domain import DomainError, require
from app.structure import strip_diacritics
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
# Below this, a Tesseract line resembles NOTHING anywhere in GPT's transcription (not
# just at its own aligned position -- see _align_gpt_lines' docstring on why the
# alignment's own up/diag choice is too easily swayed by a coincidental low-but-
# nonzero score to use as the noise signal by itself) and is dropped as noise rather
# than kept at its own text. Real dossier data backs the gap this sits in: genuine
# lines (even ones the alignment can't confidently place) scored 0.55-0.96 against
# their true counterpart, while real Tesseract misreads of a stamp/watermark/table-
# ruling artifact topped out at 0.44 against anything at all in the same GPT output.
_LINE_NOISE_CEILING = 0.45
# Cost of skipping a line on either side during alignment. Kept well under
# _LINE_MATCH_FLOOR's typical genuine-match scores (0.55-1.0 on real contract pages;
# see the docstring below) so two truly corresponding lines are never cheaper to skip
# past than to align, while a near-zero-similarity pair is.
_LINE_ALIGN_GAP_PENALTY = 0.3


def _align_gpt_lines(
    tess_texts: list[str], gpt_texts: list[str]
) -> tuple[dict[int, str], set[int]]:
    """Globally aligns Tesseract's lines with GPT vision's re-transcribed lines (a
    Needleman-Wunsch alignment over per-line text similarity) and returns
    `({tess_index: gpt_text}, noise_indices)`.

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
    counterpart; this correctly aligned all 56 genuine lines and identified the 3 noise
    ones as having no GPT counterpart at all.

    A Tesseract line the alignment doesn't confidently substitute (score below
    `_LINE_MATCH_FLOOR`) falls into one of two very different buckets, and the caller
    must not treat them the same:
    - It resembles SOMETHING in GPT's transcription, just not enough to trust as a
      substitution, or not at the position this one global path happened to pick —
      this is usually real content the two sources disagree on the wording of, most
      often GPT splitting or merging a table row's own multi-line description
      differently than Tesseract's own line segmentation. These indices are simply
      absent from the returned `pairs` dict; the caller keeps the line at its own
      original Tesseract text. An earlier version conflated this with the case below
      and dropped both, which silently lost real page text often enough (visible in
      "Toàn văn theo trang" and in _ocr_tables, which runs on this exact list) to be
      worth fixing.
    - It resembles NOTHING in GPT's transcription at all (below `_LINE_NOISE_CEILING`
      against every single GPT line, not just the one this alignment path happens to
      pair it with) — GPT vision, looking at the actual pixels, produced nothing
      corresponding to it anywhere, the clearest available signal that it's decoration
      (a stamp/seal/watermark/table-ruling fragment), not text. These indices are
      returned separately as `noise_indices`; the caller drops the line entirely
      rather than keep its garbled Tesseract text. This check deliberately does NOT
      rely on the alignment's own "up" (skip) vs "diag" (pair) choice at that cell:
      with a large line-count mismatch (a table-heavy page can easily have GPT
      emitting 2-3x Tesseract's line count), the monotonic path very often still
      threads a noise line through a coincidental low-but-nonzero "diag" pairing —
      cheaper for the DP than skipping — purely because gap penalties make ANY
      nonzero similarity look better than none, not because the pairing means
      anything. A real dossier line ("A ae ar Ị el", from a misread page decoration)
      landed exactly there: diag-paired at 0.29 similarity to an unrelated real GPT
      line, comfortably below the trust floor but NOT flagged by the old "was it an
      up move" check, so it kept surviving as garbled Tesseract text. Checking the
      BEST similarity against every GPT line, independent of the path's own choices,
      catches this: that line's best possible match anywhere in the same GPT output
      was still only 0.44, while every genuine (if imperfectly aligned) line in this
      same real data scored 0.55 or higher against its true counterpart.
    """
    n, m = len(tess_texts), len(gpt_texts)
    if n == 0 or m == 0:
        return {}, set()
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

    noise = {
        idx
        for idx in range(n)
        if idx not in pairs
        and max(similarity[idx + 1][1:], default=0.0) < _LINE_NOISE_CEILING
    }
    return pairs, noise


def _align_gpt_words(
    tess_words: list[str], gpt_words: list[str]
) -> tuple[dict[int, str], str, str]:
    """`({tess_index: gpt_word}, leading_extra, trailing_extra)` for one already-
    line-matched line: a sequence alignment (difflib, the same technique
    _align_gpt_lines uses across whole lines) of GPT vision's word-for-word reading
    against Tesseract's own — not just when the two word lists happen to be the
    exact same length.

    _ocr_tables' column splitting reads word["text"], never the line's own display
    string, so requiring an EXACT word-count match before trusting any substitution
    (the previous rule) meant one single word Tesseract lost entirely — not misread,
    genuinely absent from its own word list, with no bbox for it at all — silently
    kept the WHOLE line on Tesseract's garbled text, including every other word GPT
    read correctly. Real hard case: Tesseract's own line for an item row was missing
    its leading "09" (swallowed into an unrelated garbled line next to it) while
    correctly detecting the other 13 words; GPT's 14-word reading of the same line
    differed only by that leading word. Aligning instead of requiring equal length
    still substitutes all 13 matched/near-matched words (recovering, on this exact
    line, two Tesseract words so badly misread — "en", "lap" — that they'd become
    meaningless English, back to their real "Không", "lặp").

    Only "equal" and "replace" opcodes ever produce a mapping, and only where the
    matched span is the SAME length on both sides — a "replace" block of differing
    length means the two sources also disagree on how many words belong there at all
    (a compound word split differently), not a confident one-for-one correspondence,
    so it's left alone exactly like today's whole-line mismatch already is. A
    "delete" (a Tesseract word GPT has no counterpart for) is skipped outright: it
    already has a bbox and text, just no confirmation either way.

    An "insert" AT THE VERY START (GPT words with no Tesseract counterpart at all,
    "09" above) is returned separately as `leading_extra`, space-joined, instead of
    silently discarded: it has real text but no bbox of its own to be placed at
    directly — _ocr_tables can still recover it using the table's own already-known
    STT column position (see _inject_leading_gpt_word) rather than lose it outright.
    Symmetrically, an "insert" AT THE VERY END is returned as `trailing_extra` — real
    hard case: a row's "Đơn giá"/"Thành tiền" cells were both a plain "0" rendered so
    faintly Tesseract detected no word box for either at all, while GPT vision (built
    to transcribe, not merely detect ink) still read them; _row_cells recovers these
    the same way _inject_leading_gpt_word recovers a leading one, borrowing bbox from
    a known column instead of leaving the row's own numbers silently blank. An insert
    anywhere else in the line (not at either end) is discarded: which of its
    neighboring columns it belongs to is genuinely ambiguous without a bbox, unlike
    the two ends, which the table's own first/last column position reliably explains.
    """
    matcher = difflib.SequenceMatcher(
        None, [w.lower() for w in tess_words], [w.lower() for w in gpt_words], autojunk=False
    )
    mapping: dict[int, str] = {}
    leading_extra = ""
    trailing_extra = ""
    opcodes = matcher.get_opcodes()
    if opcodes and opcodes[0][0] == "insert" and opcodes[0][1] == 0:
        leading_extra = " ".join(gpt_words[opcodes[0][3]:opcodes[0][4]])
    if (
        opcodes
        and opcodes[-1] is not opcodes[0]
        and opcodes[-1][0] == "insert"
        and opcodes[-1][2] == len(tess_words)
    ):
        trailing_extra = " ".join(gpt_words[opcodes[-1][3]:opcodes[-1][4]])
    for tag, i1, i2, j1, j2 in opcodes:
        if tag in ("equal", "replace") and (i2 - i1) == (j2 - j1):
            for offset in range(i2 - i1):
                mapping[i1 + offset] = gpt_words[j1 + offset]
    return mapping, leading_extra, trailing_extra


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


# _ocr_tables' column grid comes entirely from Tesseract's own word x-positions --
# accurate for row segmentation, but a real hard case showed it can silently merge or
# drop a whole column (an ĐVT column's words sat close enough to the neighboring
# column's x-band that the whole column vanished from every row, not just one). Rather
# than trying to fix that clustering heuristic, this asks the vision model to determine
# the table's own row/column structure directly from the image -- no pre-supposed grid
# to get wrong. Content correctness matters more right now than bbox precision (see
# _apply_gpt_vision_table): every cell this produces is trusted and kept, but marked
# "inferred" since its bbox is an even split of the table's own region, not a real
# per-cell detection.
_GPT_VISION_TABLE_PROMPT = """\
You are a precise OCR transcription engine reading ONE TABLE cropped from a scanned \
Vietnamese contract page. Determine the table's own row and column structure yourself \
from the image -- do not assume any particular row or column count.

Rules, in order of priority:
1. Transcribe every visible cell's text EXACTLY as printed -- verbatim. Never compute, \
round, reformat, translate, or correct anything. Preserve Vietnamese diacritics exactly \
as shown.
2. Include the header row as the first row if the table has one.
3. Every row must have the same number of cells as every other row: pad a row that has \
fewer visible cells (a merged cell, a short row) with null at the position(s) where \
nothing is printed, so all rows line up column-for-column.
4. An empty or blank cell -> null.
5. A cell whose text cannot be confidently read (illegible, cut off, smudged, stamped \
over) -> the literal string "UNREADABLE". An honest "UNREADABLE" is always better than a \
confident wrong guess.
6. Never invent, guess, or auto-complete a value you cannot clearly read.
7. Return JSON only, shaped exactly as {"rows": [["cell", "cell", ...], ...]} -- one \
inner array per visible row, top-to-bottom, cells in left-to-right column order. No \
markdown, no code fences, no commentary outside the JSON object.
"""


def _parse_vision_table_rows(raw: str) -> list[list[str | None]] | None:
    """Best-effort parse of the {"rows": [[...], ...]} shape _GPT_VISION_TABLE_PROMPT
    asks for. A malformed top-level response (not JSON, no "rows" list) yields None --
    the caller keeps its existing bbox-based table. A malformed individual ROW (not a
    list) is dropped rather than failing the whole table, matching the same
    keep-what-parsed tradeoff as ai-service's VisionAdapter(mode="cells").
    """
    try:
        payload = json.loads(raw)
        raw_rows = payload["rows"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return None
    if not isinstance(raw_rows, list):
        return None
    rows = [
        [v if isinstance(v, str) else None for v in raw_row]
        for raw_row in raw_rows
        if isinstance(raw_row, list)
    ]
    return rows or None


def _rectangularize(rows: list[list[str | None]]) -> tuple[list[list[str | None]], int]:
    """Pads every row to the widest row's length so the table is a rectangular grid --
    a row the model reported with fewer cells than another (a merged cell it didn't
    pad itself, despite the prompt) gets trailing blanks rather than shifting every
    later row's columns out of alignment."""
    col_count = max(len(row) for row in rows)
    return [row + [None] * (col_count - len(row)) for row in rows], col_count


def _gpt_vision_table(image: Image.Image, table_bbox: list[float], config: dict) -> list[list[str | None]] | None:
    """Re-transcribes one detected table region as structured rows/columns, letting
    the vision model determine the grid itself from the cropped image -- see
    _GPT_VISION_TABLE_PROMPT. Never raises: an unavailable or failed call just means
    the caller keeps its existing (Tesseract-geometry-based) table instead, exactly
    like _gpt_vision_lines does for page text.
    """
    if not settings.openai_api_key:
        return None
    try:
        from openai import OpenAI

        x0, y0, x1, y1 = table_bbox
        crop = image.crop((
            x0 * image.width, y0 * image.height, x1 * image.width, y1 * image.height,
        ))
        client = OpenAI(
            api_key=settings.openai_api_key,
            max_retries=config.get("ocr_vision_max_retries", 5),
        )
        buffer = BytesIO()
        crop.save(buffer, format="PNG")
        data_url = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
        response = client.chat.completions.create(
            model=config.get("ocr_vision_model", "gpt-5.6-terra"),
            max_completion_tokens=4096,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _GPT_VISION_TABLE_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url, "detail": "high"}},
                    ],
                },
            ],
        )
        text = response.choices[0].message.content or ""
        return _parse_vision_table_rows(text)
    except Exception:
        return None


def _apply_gpt_vision_table(table: dict, image: Image.Image, config: dict) -> dict:
    """Replaces `table`'s rows with GPT vision's own reading of the whole table region
    when available (see _gpt_vision_table), keeping the original bbox-based table
    unchanged if vision is unavailable, fails, or returns nothing usable.

    Every cell's bbox is an even split of the table's own region by row/column index --
    not a real per-cell detection, so every cell is marked "inferred" (see
    _inject_leading_gpt_word): tables.py already knows to skip citing an inferred cell
    rather than pointing a reviewer at a page position that isn't really where the text
    sits, while still trusting and showing the text itself normally. Precise per-cell
    bbox is a later concern; a correct table now is the point of this function.
    """
    vision_rows = _gpt_vision_table(image, table["bbox"], config)
    if not vision_rows:
        return table
    rows, col_count = _rectangularize(vision_rows)
    if col_count == 0:
        return table
    x0, y0, x1, y1 = table["bbox"]
    row_height = (y1 - y0) / len(rows)
    col_width = (x1 - x0) / col_count
    return {
        **table,
        "row_count": len(rows),
        "col_count": col_count,
        "rows": [
            {
                "row_index": row_index,
                "cells": [
                    {
                        "col_index": col_index,
                        "text": text or "",
                        "bbox": [
                            x0 + col_index * col_width,
                            y0 + row_index * row_height,
                            x0 + (col_index + 1) * col_width,
                            y0 + (row_index + 1) * row_height,
                        ],
                        "inferred": True,
                    }
                    for col_index, text in enumerate(row)
                ],
            }
            for row_index, row in enumerate(rows)
        ],
    }


_TABLE_ROW_RE = re.compile(r"^\s*\|(.*)\|\s*$")
_TABLE_SEPARATOR_RE = re.compile(r"^[\s|:-]+$")
_MARKDOWN_HEADING_RE = re.compile(r"^#{1,6}\s+")
_MARKDOWN_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]*)\)")
_MARKDOWN_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_LATEX_ESCAPE_RE = re.compile(r"\\([%$_&#{}])")


def _clean_vision_markdown_text(text: str) -> str:
    """Strips Markdown/LaTeX artifacts that Mistral's OCR endpoint's own output style
    introduces, which this codebase's plain-text pipeline was never built to expect --
    confirmed against a real page: a heading came back as "# DIEU 1. ..." (breaking
    structure.py's ARTICLE_PATTERN, which anchors on `^Dieu` and silently never
    matches a line starting with "# " instead, so the whole clause tree never forms
    for a vision-sourced page) and a payment percentage came back as "\\(30\\%\\)"
    (LaTeX inline-math escaping wrapped around a plain "30%", corrupting a legally
    meaningful number for any downstream percentage-matching fact extractor). Also
    unwraps `**bold**` (seen on a table's own totals row) and replaces a Markdown
    image reference (Mistral's way of saying "there was a non-text visual element
    here" -- a stamp/signature in the one real case seen) with a plain, honest
    `[image: ...]` marker instead of leaking raw `![...](...)` syntax as if it were
    transcribed text. Never drops real content, only the syntax Mistral wrapped
    around it -- applied to every line/cell this module builds from raw Mistral
    markdown (_mistral_vision_lines, _split_table_row, and vision-only prose lines).
    """
    text = _MARKDOWN_HEADING_RE.sub("", text)
    text = _MARKDOWN_IMAGE_RE.sub(lambda m: f"[image: {m.group(1) or m.group(2)}]", text)
    text = _MARKDOWN_BOLD_RE.sub(r"\1", text)
    text = text.replace("\\(", "").replace("\\)", "")
    text = _LATEX_ESCAPE_RE.sub(r"\1", text)
    return text.strip()


def _split_table_row(line: str) -> list[str]:
    match = _TABLE_ROW_RE.match(line)
    inner = match.group(1) if match else line
    return [_clean_vision_markdown_text(cell) for cell in inner.split("|")]


def _parse_markdown_pipe_table(text: str) -> list[list[str]] | None:
    """Finds the first GFM pipe-table (a header row immediately followed by a
    |---|---| separator row) in `text` and returns its header + body rows, header
    included as the first row -- matching _parse_vision_table_rows' output shape (one
    inner list per visible row, top-to-bottom) so _rectangularize/_apply_*_vision_table
    can consume either provider's output identically. Returns None if no such block is
    found (e.g. Mistral read the crop as prose instead of a table) -- the caller then
    keeps its existing Tesseract-geometry table, same as a GPT vision miss.
    """
    lines = text.splitlines()
    for i, line in enumerate(lines):
        nxt = lines[i + 1] if i + 1 < len(lines) else None
        if (
            _TABLE_ROW_RE.match(line)
            and nxt is not None
            and _TABLE_ROW_RE.match(nxt)
            and _TABLE_SEPARATOR_RE.match(nxt)
            and "-" in nxt
        ):
            rows = [_split_table_row(line)]
            j = i + 2
            while j < len(lines) and _TABLE_ROW_RE.match(lines[j]):
                rows.append(_split_table_row(lines[j]))
                j += 1
            return rows
    return None


def _mistral_vision_lines(image: Image.Image, config: dict) -> list[str] | None:
    """Re-transcribes the full page image with Mistral's dedicated OCR endpoint
    (client.ocr.process, not a chat completion), returning one string per visible line
    in reading order -- or None if the call is unavailable or fails. Same never-raises,
    optional-accuracy-layer contract as _gpt_vision_lines.

    table_format is deliberately left unset (API default: tables stay inline in the
    response as real markdown) -- see Settings.ocr_mistral_model's docstring for why
    "markdown"/"html" must NOT be passed here.
    """
    if not settings.mistral_api_key:
        return None
    try:
        from mistralai.client import Mistral

        client = Mistral(api_key=settings.mistral_api_key)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        data_url = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
        response = client.ocr.process(
            model=config.get("ocr_mistral_model", "mistral-ocr-4"),
            document={"type": "image_url", "image_url": data_url},
        )
        if not response.pages:
            return None
        text = response.pages[0].markdown or ""
        cleaned = [_clean_vision_markdown_text(line) for line in text.splitlines()]
        return [_nfc(line) for line in cleaned if line]
    except Exception:
        return None


def _mistral_vision_table(
    image: Image.Image, table_bbox: list[float], config: dict
) -> list[list[str]] | None:
    """Re-transcribes one detected table region via Mistral's dedicated OCR endpoint,
    parsing its returned inline markdown pipe-table back into rows/columns via
    _parse_markdown_pipe_table -- same never-raises, "caller keeps its existing table on
    failure" contract as _gpt_vision_table.
    """
    if not settings.mistral_api_key:
        return None
    try:
        from mistralai.client import Mistral

        x0, y0, x1, y1 = table_bbox
        crop = image.crop((
            x0 * image.width, y0 * image.height, x1 * image.width, y1 * image.height,
        ))
        client = Mistral(api_key=settings.mistral_api_key)
        buffer = BytesIO()
        crop.save(buffer, format="PNG")
        data_url = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
        response = client.ocr.process(
            model=config.get("ocr_mistral_model", "mistral-ocr-4"),
            document={"type": "image_url", "image_url": data_url},
        )
        if not response.pages:
            return None
        return _parse_markdown_pipe_table(response.pages[0].markdown or "")
    except Exception:
        return None


def _apply_mistral_vision_table(table: dict, image: Image.Image, config: dict) -> dict:
    """Replaces `table`'s rows with Mistral OCR's own reading of the whole table region
    when available (see _mistral_vision_table) -- identical shape/reasoning to
    _apply_gpt_vision_table, including the "inferred" bbox marking (an even grid split
    by row/column index, not a real per-cell detection).
    """
    vision_rows = _mistral_vision_table(image, table["bbox"], config)
    if not vision_rows:
        return table
    rows, col_count = _rectangularize(vision_rows)
    if col_count == 0:
        return table
    x0, y0, x1, y1 = table["bbox"]
    row_height = (y1 - y0) / len(rows)
    col_width = (x1 - x0) / col_count
    return {
        **table,
        "row_count": len(rows),
        "col_count": col_count,
        "rows": [
            {
                "row_index": row_index,
                "cells": [
                    {
                        "col_index": col_index,
                        "text": text or "",
                        "bbox": [
                            x0 + col_index * col_width,
                            y0 + row_index * row_height,
                            x0 + (col_index + 1) * col_width,
                            y0 + (row_index + 1) * row_height,
                        ],
                        "inferred": True,
                    }
                    for col_index, text in enumerate(row)
                ],
            }
            for row_index, row in enumerate(rows)
        ],
    }


def _split_markdown_into_segments(text: str) -> list[tuple[str, list]]:
    """Splits raw Mistral OCR markdown into an ORDERED list of ("text", [line, ...])
    and ("table", [row, ...]) segments, for the "no Tesseract at all" vision-only path
    (see _mistral_vision_page). ALL pipe-table blocks on the page are extracted, not
    just the first -- confirmed against a real test page with two consecutive
    appendix tables separated by only a short intro line: extracting only the first
    table (an earlier version of this function did) silently left the second table's
    own pipe-syntax sitting as unparsed "| a | b |" prose lines instead of a real
    Table, which is exactly what a vision-only page's "Toàn văn theo trang" must never
    contain. A "text" segment's lines are exactly as split from the source, not yet
    cleaned/filtered -- the caller (_mistral_vision_page) does that once per segment.
    """
    lines = text.splitlines()
    segments: list[tuple[str, list]] = []
    text_buffer: list[str] = []

    def flush_text() -> None:
        if text_buffer:
            segments.append(("text", list(text_buffer)))
            text_buffer.clear()

    i = 0
    while i < len(lines):
        line = lines[i]
        nxt = lines[i + 1] if i + 1 < len(lines) else None
        if (
            _TABLE_ROW_RE.match(line)
            and nxt is not None
            and _TABLE_ROW_RE.match(nxt)
            and _TABLE_SEPARATOR_RE.match(nxt)
            and "-" in nxt
        ):
            flush_text()
            rows = [_split_table_row(line)]
            j = i + 2
            while j < len(lines) and _TABLE_ROW_RE.match(lines[j]):
                rows.append(_split_table_row(lines[j]))
                j += 1
            segments.append(("table", rows))
            i = j
        else:
            text_buffer.append(line)
            i += 1
    flush_text()
    return segments


def _mistral_block_bbox(block, width: int, height: int) -> list[float]:
    """Normalizes one OCR block's real (measured, pixel) bounding box to [0, 1] against
    the page's own render dimensions -- the same "content:" contract as every other
    bbox this codebase produces (see _clamp01's callers), just sourced from Mistral's
    own block detection instead of Tesseract's word geometry.
    """
    return [
        _clamp01(block.top_left_x / width),
        _clamp01(block.top_left_y / height),
        _clamp01(block.bottom_right_x / width),
        _clamp01(block.bottom_right_y / height),
    ]


def _mistral_vision_page(
    image: Image.Image, config: dict
) -> list[tuple[str, list, list[float], float | None]] | None:
    """Vision-only OCR (see Settings.ocr_engine's "..._vision_only" docstring): ONE
    Mistral OCR call for the whole page, no Tesseract involved at all -- unlike
    _mistral_vision_lines (which only ever REPLACES an already Tesseract-anchored
    line's text), this is the sole source of both the page's text and every table on
    it, INCLUDING their bbox: `include_blocks=True` (paragraph-level blocks, each
    already MEASURED by Mistral's own detector, not inferred/evenly split the way this
    module used to build vision-only bbox) and `confidence_scores_granularity="block"`
    (a real per-block confidence score, replacing the "inferred": True flag's
    all-or-nothing signal with an actual number) -- confirmed live against a real
    scanned page: a title/text/table/footer block each came back with its own correct
    pixel bbox and a `confidence_scores.average_content_confidence_score`.

    Returns an ordered list of (kind, content, bbox, confidence) segments -- "table"
    content is that block's rows (via _parse_markdown_pipe_table on its own markdown
    content, same as before); "text" content is that block's cleaned, NFC-normalized
    lines (a block can itself contain more than one visible line -- Mistral's block
    granularity is paragraph-level, not per-visible-line, so every line split from one
    block shares that one block's real bbox/confidence rather than each getting its
    own, which is not something this API call provides). A block whose content is
    empty after cleaning is dropped entirely. Returns None if the call is
    unavailable/fails (never raises).
    """
    if not settings.mistral_api_key:
        return None
    try:
        from mistralai.client import Mistral

        client = Mistral(api_key=settings.mistral_api_key)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        data_url = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
        response = client.ocr.process(
            model=config.get("ocr_mistral_model", "mistral-ocr-4"),
            document={"type": "image_url", "image_url": data_url},
            include_blocks=True,
            confidence_scores_granularity="block",
        )
        if not response.pages:
            return None
        page = response.pages[0]
        dims = page.dimensions
        segments: list[tuple[str, list, list[float], float | None]] = []
        for block in page.blocks or []:
            bbox = _mistral_block_bbox(block, dims.width, dims.height)
            scores = block.confidence_scores
            confidence = scores.average_content_confidence_score if scores else None
            content = block.content or ""
            if block.type == "table":
                rows = _parse_markdown_pipe_table(content)
                if rows:
                    segments.append(("table", rows, bbox, confidence))
                continue
            clean_lines = [
                _nfc(t) for line in content.splitlines() if (t := _clean_vision_markdown_text(line))
            ]
            if clean_lines:
                segments.append(("text", clean_lines, bbox, confidence))
        return segments
    except Exception:
        return None


# Unlike _GPT_VISION_TABLE_PROMPT (which assumes the caller already cropped to one
# table region -- from a Tesseract-detected bbox this vision-only path doesn't have),
# this reads a FULL, uncropped page and must locate the table itself, or report there
# is none. NOT live-verified against a real page (would need a real OpenAI call this
# project's own budget didn't cover for it) -- mirrors _mistral_vision_page's proven
# shape as closely as GPT's own no-markdown transcription convention allows; treat as
# best-effort until checked against a real scan.
_GPT_VISION_FULL_PAGE_TABLE_PROMPT = """\
You are a precise OCR transcription engine reading ONE FULL PAGE of a scanned \
Vietnamese contract. The page may or may not contain a table.

Rules, in order of priority:
1. If the page contains a table, transcribe ONLY that table's cells -- ignore all \
surrounding prose, headings, signatures, and stamps entirely. Determine the table's \
own row and column structure yourself from the image; do not assume any particular \
row or column count.
2. If the page contains no table at all, return {"rows": []}.
3. Transcribe every visible cell's text EXACTLY as printed -- verbatim. Never compute, \
round, reformat, translate, or correct anything. Preserve Vietnamese diacritics exactly \
as shown.
4. Include the header row as the first row if the table has one.
5. Every row must have the same number of cells as every other row: pad a row that has \
fewer visible cells (a merged cell, a short row) with null at the position(s) where \
nothing is printed, so all rows line up column-for-column.
6. An empty or blank cell -> null.
7. A cell whose text cannot be confidently read (illegible, cut off, smudged, stamped \
over) -> the literal string "UNREADABLE". An honest "UNREADABLE" is always better than a \
confident wrong guess.
8. Never invent, guess, or auto-complete a value you cannot clearly read.
9. Return JSON only, shaped exactly as {"rows": [["cell", "cell", ...], ...]} -- one \
inner array per visible row, top-to-bottom, cells in left-to-right column order (or an \
empty "rows" list per rule 2). No markdown, no code fences, no commentary outside the \
JSON object.
"""


def _gpt_vision_page_table(image: Image.Image, config: dict) -> list[list[str]] | None:
    """Vision-only table extraction directly from a full, uncropped page image -- see
    _GPT_VISION_FULL_PAGE_TABLE_PROMPT's own caveat (not live-verified). Same
    never-raises contract as _gpt_vision_table; an empty {"rows": []} response
    (deliberately requested for a page with no table) also yields None via
    _parse_vision_table_rows' "rows or None" return.
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
            max_completion_tokens=4096,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _GPT_VISION_FULL_PAGE_TABLE_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url, "detail": "high"}},
                    ],
                },
            ],
        )
        text = response.choices[0].message.content or ""
        return _parse_vision_table_rows(text)
    except Exception:
        return None


def _assemble_vision_only_page(
    segments: list[tuple[str, list]], payload: dict
) -> tuple[list[dict], list[dict]]:
    """gpt_vision_only's page assembler: GPT has no block-level bbox API to draw on
    (see _gpt_vision_page_table's own caveat), so every bbox here is still
    "inferred" -- full page width, an even vertical split across however many "slots"
    the page has (one per prose line, `len(rows)` for a table segment so a 12-row
    table gets proportionally more vertical space than one prose line, not squeezed
    into the same sliver) -- never a real measurement. mistral_vision_only uses
    _assemble_vision_only_page_from_blocks instead, which has real bbox/confidence to
    draw on and needs none of this slot math.

    Builds `lines`/`tables` from an ORDERED list of ("text", [line, ...]) /
    ("table", [row, ...]) segments (see _split_markdown_into_segments). Shares the
    same "inferred" convention
    _apply_gpt_vision_table/_apply_mistral_vision_table already use for table cells
    (tables.py knows to skip citing one); plain lines get the same flag for the same
    honesty reason, even though nothing downstream currently branches on a LINE's
    inferred flag -- evidence.citation() only checks the bbox is in-bounds, not that
    it was measured, so an approximate but valid bbox still resolves.

    Multiple "table" segments on the same page each become their own Table -- this
    function does NOT merge them (a real page can have two genuinely different
    tables, e.g. two separate appendices with only a short intro line between them);
    deciding whether two tables anywhere in the document are really one continued
    table is table_continuity.py's job, unchanged by how many tables one page has.
    """
    total_slots = sum(len(content) for _, content in segments) or 1
    lines: list[dict] = []
    tables: list[dict] = []
    slot = 0

    def _bbox_for(span: int) -> list[float]:
        nonlocal slot
        y0, y1 = slot / total_slots, (slot + span) / total_slots
        slot += span
        return [0.0, y0, 1.0, y1]

    for kind, content in segments:
        if kind == "text":
            for text in content:
                lines.append({
                    "id": f"{payload['document_id']}:{payload['page_number']}:{len(lines)}",
                    "text": text,
                    "bbox": _bbox_for(1),
                    "inferred": True,
                })
            continue

        rows, col_count = _rectangularize(content)
        bbox = _bbox_for(len(rows))
        if col_count == 0:
            continue
        x0, y0, x1, y1 = bbox
        row_height = (y1 - y0) / len(rows)
        col_width = (x1 - x0) / col_count
        tables.append({
            "id": f"table:{payload['document_id']}:{payload['page_number']}:{len(tables)}",
            "document_id": payload["document_id"],
            "page_number": payload["page_number"],
            "row_count": len(rows),
            "col_count": col_count,
            "bbox": bbox,
            "rows": [
                {
                    "row_index": row_index,
                    "cells": [
                        {
                            "col_index": col_index,
                            "text": text or "",
                            "bbox": [
                                x0 + col_index * col_width,
                                y0 + row_index * row_height,
                                x0 + (col_index + 1) * col_width,
                                y0 + (row_index + 1) * row_height,
                            ],
                            "inferred": True,
                        }
                        for col_index, text in enumerate(row)
                    ],
                }
                for row_index, row in enumerate(rows)
            ],
            "heading_before": _nearest_heading_above(lines, y0),
            "low_confidence": False,
        })

    return lines, tables


def _assemble_vision_only_page_from_blocks(
    segments: list[tuple[str, list, list[float], float | None]], payload: dict
) -> tuple[list[dict], list[dict]]:
    """mistral_vision_only's page assembler -- unlike _assemble_vision_only_page (used
    by gpt_vision_only, which has no block-bbox API to draw on), no bbox here is
    synthesized or evenly split: every line and every table gets the REAL bbox and
    REAL confidence score of the Mistral OCR block it came from (see
    _mistral_vision_page). A "text" block containing several visible lines gives
    every one of those lines that SAME block's bbox/confidence -- Mistral's own block
    granularity is paragraph-level, not per-visible-line, and this API gives no finer
    geometry to split on. Table CELLS still get an evenly-split bbox WITHIN the
    table's own now-real bbox and stay marked "inferred" (no real per-cell detection
    exists) -- but the table's own bbox and confidence are real measurements, not
    synthesized ones, a genuine accuracy improvement over the table's own bbox before
    this function existed. Multiple "table" segments on the same page each become
    their own Table, same as _assemble_vision_only_page -- table_continuity.py still
    decides whether two tables anywhere in the document are really one continued
    table, unchanged by this function.
    """
    lines: list[dict] = []
    tables: list[dict] = []
    for kind, content, bbox, confidence in segments:
        if kind == "text":
            for text in content:
                lines.append({
                    "id": f"{payload['document_id']}:{payload['page_number']}:{len(lines)}",
                    "text": text,
                    "bbox": bbox,
                    "confidence": confidence,
                })
            continue

        rows, col_count = _rectangularize(content)
        if col_count == 0:
            continue
        x0, y0, x1, y1 = bbox
        row_height = (y1 - y0) / len(rows)
        col_width = (x1 - x0) / col_count
        tables.append({
            "id": f"table:{payload['document_id']}:{payload['page_number']}:{len(tables)}",
            "document_id": payload["document_id"],
            "page_number": payload["page_number"],
            "row_count": len(rows),
            "col_count": col_count,
            "bbox": bbox,
            "confidence": confidence,
            "rows": [
                {
                    "row_index": row_index,
                    "cells": [
                        {
                            "col_index": col_index,
                            "text": text or "",
                            "bbox": [
                                x0 + col_index * col_width,
                                y0 + row_index * row_height,
                                x0 + (col_index + 1) * col_width,
                                y0 + (row_index + 1) * row_height,
                            ],
                            "inferred": True,
                        }
                        for col_index, text in enumerate(row)
                    ],
                }
                for row_index, row in enumerate(rows)
            ],
            "heading_before": _nearest_heading_above(lines, y0),
            "low_confidence": False,
        })
    return lines, tables


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


# A signature block's own cells, diacritic-stripped: the header row's party label
# ("ĐẠI DIỆN BÊN A", "ĐẠI DIỆN NHÀ CUNG CẤP HÀNG HÓA", ...) always opens with "Đại
# diện", and the signing-instruction row underneath always opens with a literal "(" —
# "(Ký, ghi rõ họ tên và đóng dấu". Both are fixed, near-universal phrasings across
# Vietnamese contracts, not a generic "short block" guess.
_SIGNATURE_CELL_PATTERN = re.compile(r"^(Dai dien|\()", re.IGNORECASE)


def _is_signature_block(rows):
    """True if `rows` (a native-table candidate's own rows) is really a two-party
    signature block -- "ĐẠI DIỆN BÊN A | ĐẠI DIỆN BÊN B" over "(Ký, ghi rõ họ tên và
    đóng dấu | (Ký, ghi rõ họ tên và đóng dấu" -- that PyMuPDF's own find_tables()
    mistook for a data table because two side-by-side signature labels are exactly as
    grid-shaped as two real table columns.

    Real hard case: a scanned Vietnamese contract's OWN signature block, at the
    bottom of virtually every page of a multi-page document, misdetected as its own
    2-row table on every single occurrence -- polluting the review UI with tables
    that have no actual data in them, once per page. Unlike _plausible_row (which
    only guards against noise/gibberish and correctly considers these cells
    "substantial," since they're genuine, real sentences), this checks whether the
    row is tabular DATA at all: every single non-empty cell here opens with one of
    the two fixed phrasings above, something no genuine data row (item description,
    price, date, quantity) would ever do across ALL of its cells at once.
    """
    cells = [c for row in rows for c in row["cells"] if c["text"].strip()]
    return bool(cells) and all(
        _SIGNATURE_CELL_PATTERN.match(strip_diacritics(c["text"].strip())) for c in cells
    )


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
        # PyMuPDF's own grid-detection readily fires on things that are geometrically
        # table-shaped but aren't tabular data at all: a bare stray line split into
        # two fragments by whitespace (rejected by _plausible_row, the same noise
        # guard _ocr_tables already relies on), or a two-party signature block (see
        # _is_signature_block) -- both real hard cases from an actual scanned
        # contract, both would otherwise show up as spurious tables in the review UI.
        if not any(_plausible_row(row["cells"]) for row in rows) or _is_signature_block(rows):
            continue
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


def _append_trailing_gpt_numbers(cells, line):
    """Appends one inferred cell per token of `line["trailing_gpt_text"]` (see
    _align_gpt_words) that looks like a number, in place, borrowing the last real
    cell's own bbox -- the same "inherited position, not a real detection" trust
    model _inject_leading_gpt_word already uses for a leading word, mirrored onto the
    other end of the row.

    Real hard case: a row's "Đơn giá" and "Thành tiền" were both a plain "0" printed
    faintly enough that Tesseract's own OCR pass produced no word box for either --
    not misread, genuinely absent, the same failure mode _inject_leading_gpt_word was
    built for at the START of a line. Without this, _row_cells (and therefore the
    very reference this row establishes, when it's the block's first) would silently
    end two columns short, with no later mechanism able to notice or recover them:
    _extend_reference_with_confirming_row only ever adds a column a LATER row proves
    exists, and this row's own trailing values would already be gone by then. Only
    number-shaped tokens are appended -- a trailing extra word that ISN'T number-
    shaped is far more likely a genuine alignment ambiguity than a lost numeric cell,
    and is left to the existing discard behavior.
    """
    trailing = line.get("trailing_gpt_text")
    if not trailing or not cells:
        return
    last_bbox = cells[-1]["bbox"]
    for token in trailing.split():
        if not _NUMBER_TOKEN.match(token):
            return
        cells.append({"text": token, "bbox": list(last_bbox), "inferred": True})


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
    cells = [
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
    _append_trailing_gpt_numbers(cells, line)
    return cells


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


def _inject_leading_gpt_word(matched_cells, reference, line):
    """When GPT vision read an extra leading word on this line that Tesseract has no
    bbox for at all (see _align_gpt_words) -- most often a row's own STT number,
    swallowed into an unrelated garbled line next to it -- place it using the
    table's own already-established STT column position, in place, rather than leave
    the row's own identity permanently blank for want of a bbox no detector produced.

    Only ever the FIRST column, and only ever when that column is otherwise
    genuinely empty for THIS row (never overwrites a real detection): the bbox is
    borrowed wholesale from the reference's own column (x-range), narrowed to this
    row's own line (y-range) -- an inherited position, not a real detection, exactly
    the same trust model _extend_reference_with_confirming_row already uses for a
    reference column a row leaves blank.
    """
    leading = line.get("leading_gpt_text")
    if not leading or not reference or any(cell["col_index"] == 0 for cell in matched_cells):
        return
    ref_cell = next((c for c in reference if c["col_index"] == 0), None)
    if ref_cell is None:
        return
    matched_cells.append(
        {
            "col_index": 0,
            "text": leading,
            "bbox": [ref_cell["bbox"][0], line["bbox"][1], ref_cell["bbox"][2], line["bbox"][3]],
            # Not a real detection -- tables.py skips citing an "inferred" cell rather
            # than pointing a reviewer at a page position that isn't really where
            # this text sits. The text itself is still trusted and shown normally.
            "inferred": True,
        }
    )


def _gpt_tab_cells(line):
    """GPT vision sometimes preserves a table row's own column layout using literal
    tab characters when transcribing it — an emergent habit, never explicitly
    requested by _GPT_VISION_SYSTEM_PROMPT (which only asks for one visible line per
    output line), but a much more direct signal of the row's true cell boundaries
    than Tesseract's own word-gap geometry ever is. Returns None when this line's
    text has no tabs at all — GPT didn't use the convention this time, on this line
    (real observation: it appears reliably on some pages and not at all on others in
    the very same job, and even changes between two otherwise-identical reprocessing
    runs of the same page) — _reconstruct_cells_from_gpt_text falls back to
    _split_gpt_text_positionally when this returns None.
    """
    text = line.get("text") or ""
    if "\t" not in text:
        return None
    return [cell.strip() for cell in text.split("\t")]


# Matches a Vietnamese-formatted number token in isolation: digits with "." (thousands)
# or "," (decimal) separators, optionally a trailing "%" -- "480.000", "22.450.000",
# "12", "0,01%". Deliberately anchored (^...$): a token merely CONTAINING digits (a
# part number like "OM4", a unit like "3m.") must not count as a numeric column.
_NUMBER_TOKEN = re.compile(r"^\d[\d.,]*%?$")


def _split_gpt_text_positionally(tokens, col_count):
    """Splits GPT vision's own line text (already whitespace-tokenized) into exactly
    `col_count` fields by POSITION and DATA SHAPE alone, with no tab convention and no
    correspondence to Tesseract's words needed at all — the fallback of last resort in
    _reconstruct_cells_from_gpt_text, for a line whose Tesseract geometry produced
    nothing usable and that GPT vision itself didn't tab-delimit this time.

    Real hard case: Tesseract's own OCR of a short row ("08 Cáp quang LC-LC OM4 3m.
    Sợi 12 480.000 5.760.000") was so badly broken ("[os", "|cinacangtcucomeam",
    "m99|", "smoe|"...) that neither word alignment (_align_gpt_words) nor a shared
    tab count (_gpt_tab_cells) has anything to work with, while GPT vision read the
    row correctly as plain space-separated text with no tabs at all.

    An item row's own shape is what makes this safe rather than an arbitrary guess:
    the FIRST token is the row's STT (a bare small number) and the LAST several
    tokens, for however many of the table's own trailing columns are consistently
    numeric-shaped (SL/Đơn giá/Thành tiền), are read off the end by DATA SHAPE
    (_NUMBER_TOKEN) — real prose describing a part number or a unit ("OM4", "3m.",
    "Sợi") never matches that shape, so the scan from the end stops there naturally,
    not at a fixed count. Whatever's left between the two — one token (plain "STT,
    Mô tả, SL, Đơn giá, Thành tiền" shapes) or two (this table's own "STT, Mô tả,
    ĐVT, SL, Đơn giá, Thành tiền": the LAST of the two is ĐVT, the rest is Mô tả) —
    is assigned by the same reasoning. Anything else (no leading number, or more than
    two leftover slots) is genuinely ambiguous and returns None rather than guessing.
    """
    if len(tokens) < col_count or not tokens or not _NUMBER_TOKEN.match(tokens[0]):
        return None
    rest = tokens[1:]
    max_trailing = col_count - 2  # at least one slot must remain for Mô tả itself
    trailing = 0
    for token in reversed(rest):
        if trailing >= max_trailing or not _NUMBER_TOKEN.match(token):
            break
        trailing += 1
    middle = rest[: len(rest) - trailing] if trailing else rest
    middle_slots = col_count - 1 - trailing
    if middle_slots == 1:
        fields = [tokens[0], " ".join(middle)]
    elif middle_slots == 2:
        fields = [tokens[0], " ".join(middle[:-1]), middle[-1]] if middle else None
        if fields is None or not fields[1]:
            return None
    else:
        return None
    fields.extend(rest[len(rest) - trailing:] if trailing else [])
    return fields


def _reconstruct_cells_from_gpt_text(line, reference):
    """Builds one row's cells directly from GPT vision's own reading of this line,
    preferred in _ocr_tables over Tesseract's own word geometry whenever it can be
    done confidently — geometry is trusted only once GPT vision's own text doesn't
    yield a confident split, either via a shared tab count (_gpt_tab_cells) or,
    failing that, by position and data shape alone (_split_gpt_text_positionally).
    Real hard case: Tesseract's OCR of a short row read so badly its words bore no
    resemblance whatsoever to the real content, yet still landed close enough to a
    few of the table's own reference column positions to produce a plausible-LOOKING
    (wrong) geometric match instead of failing outright — nothing about that match
    being non-None reveals it's wrong, while GPT vision read the same row correctly.

    One cell per reference column, matched by POSITION (both are already
    left-to-right) rather than by geometry, since there IS no usable geometry here.
    Bbox is borrowed wholesale from the reference's own column (x-range), narrowed to
    this line's own bbox (y-range) — an inherited position, not a real detection,
    the same trust model _inject_leading_gpt_word and
    _extend_reference_with_confirming_row already use elsewhere in this module. A
    blank field (a genuinely empty cell, same as anywhere else in this module) is
    dropped rather than kept as an empty-text cell. Every cell here is marked
    "inferred" — tables.py skips citing one rather than pointing a reviewer at a page
    position that isn't really where this text sits; the text itself is still
    trusted and shown normally.
    """
    texts = _gpt_tab_cells(line)
    if texts is None or len(texts) != len(reference):
        texts = _split_gpt_text_positionally((line.get("text") or "").split(), len(reference))
    if texts is None:
        return None
    return [
        {
            "col_index": ref_cell["col_index"],
            "text": text,
            "bbox": [ref_cell["bbox"][0], line["bbox"][1], ref_cell["bbox"][2], line["bbox"][3]],
            "inferred": True,
        }
        for ref_cell, text in zip(reference, texts)
        if text
    ]


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
    # Cells _append_trailing_gpt_numbers injected (a bbox borrowed wholesale from the
    # last real cell, not a real detection) must not count either way here: they're
    # exactly the short, single-character-shaped values ("0") this function exists to
    # be suspicious of, and letting them inflate the "how many cells does this row
    # have" denominator without ever being able to satisfy the numerator would reject
    # a real row for the crime of being MORE complete than before.
    real = [cell for cell in cells if not cell.get("inferred")]
    if not real:
        return False
    substantial = sum(1 for cell in real if len(cell["text"].strip()) > 1)
    return substantial >= max(2, (len(real) + 1) // 2)


# A price table's own subtotal/VAT/total row, diacritic-stripped and matched at the
# very start of the line's label text (never the middle -- a "Ghi chú" note that
# happens to mention "cộng" partway through a sentence must not qualify). Anchored to
# the handful of labels a Vietnamese commercial contract's value table actually ends
# on; deliberately not a generic "any short label" rule, which would just as happily
# swallow an unrelated one-line sentence that happens to end in a number.
_SUMMARY_ROW_PATTERN = re.compile(r"^(Cong|Tong|VAT|Thue)\b", re.IGNORECASE)
# The row's trailing amount, split off by regex rather than by whitespace: GPT vision
# renders this same merged label+amount cell with a space, a tab, or -- observed on a
# real dossier, and non-deterministically even across identical reprocessing runs of
# the very same page -- NO separator at all ("THUẾ1.116.230.000"). Anchored at the
# string's end and requiring nothing but digits/separators from wherever it starts,
# so it finds the true label/amount boundary (the first non-digit character) even
# with zero whitespace to split on.
_SUMMARY_ROW_AMOUNT = re.compile(r"(\d[\d.,]*%?)\s*$")


def _summary_row_cells(line, reference):
    """A price table's own subtotal/VAT/grand-total row -- "CỘNG TRƯỚC THUẾ
    1.116.230.000", "VAT 10% 111.623.000", "TỔNG CỘNG 1.227.853.000" -- as two cells:
    the label at col_index 0, the amount at the reference's own LAST column (its
    "Thành tiền"/total column, by the same "rightmost is the money column" convention
    every row of the table already follows), rather than the anomaly it looks like to
    _matching_cells (its label cell spans what were several distinct columns in the
    printed table, collapsed into one by the merge; a row's ordinary column count
    never matches this shape).

    Without this, such a row satisfies neither _matching_cells nor
    _merge_wrapped_continuation (a merged label overlaps no single cell of the row
    above well enough to trust as its continuation) and reads as two back-to-back
    anomalies, which flush()es the ENTIRE table right before its own summary --
    silently dropping the item rows above it from result and citations alike, not
    just the total. Only ever tried once `reference` exists (the shape a "wrapped
    continuation" or a fresh reference could otherwise have been), and only for a
    label that starts with a genuine subtotal/tax/total keyword -- see
    _SUMMARY_ROW_PATTERN -- so an ordinary sentence that happens to end in a number
    is never mistaken for one.

    The label cell's bbox deliberately stops at the amount column's own left edge
    instead of borrowing the reference's full first-column width: a summary row is
    usually immediately followed by unrelated content (a signature block, the next
    page) that _merge_wrapped_continuation would otherwise have a wide, unearned
    target to accidentally overlap and get absorbed into.
    """
    if reference is None:
        return None
    text = (line.get("text") or "").strip()
    match = _SUMMARY_ROW_AMOUNT.search(text)
    if not match:
        return None
    amount, label = match.group(1), text[: match.start()].strip()
    if not label or not _SUMMARY_ROW_PATTERN.match(strip_diacritics(label)):
        return None
    last_col = max(reference, key=lambda cell: cell["col_index"])
    first_col = min(reference, key=lambda cell: cell["col_index"])
    return [
        {
            "col_index": first_col["col_index"],
            "text": label,
            "bbox": [line["bbox"][0], line["bbox"][1], last_col["bbox"][0], line["bbox"][3]],
            "inferred": True,
        },
        {
            "col_index": last_col["col_index"],
            "text": amount,
            "bbox": [last_col["bbox"][0], line["bbox"][1], last_col["bbox"][2], line["bbox"][3]],
            "inferred": True,
        },
    ]


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
                    {
                        "col_index": cell["col_index"],
                        "text": cell["text"],
                        "bbox": cell["bbox"],
                        # Carried through so tables.py can skip citing a cell whose
                        # bbox is an inherited position, not a real detection (see
                        # _inject_leading_gpt_word / _cells_from_gpt_tabs).
                        "inferred": cell.get("inferred", False),
                    }
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
    last_was_summary = False
    for line in lines:
        cells = None
        matched_cells = None
        # Skipped for the one row where len(block) == 1 -- the confirming row
        # _extend_reference_with_confirming_row still needs to see run its own
        # geometric matching below, since only a REAL word's bbox landing nowhere in
        # the (possibly still-incomplete) reference is trustworthy evidence that a
        # whole column is missing from it. _reconstruct_cells_from_gpt_text has no
        # such signal: given a column count to target, it always produces exactly
        # that many fields (silently folding a genuinely separate column's value
        # into its neighbor) rather than ever reporting "there should be more
        # columns than this" — safe once reference already reflects the table's true
        # shape, wrong to rely on for establishing that shape in the first place.
        if reference is not None and len(block) != 1:
            matched_cells = _reconstruct_cells_from_gpt_text(line, reference)
        if matched_cells is None:
            cells = _row_cells(line)
            if cells is None:
                # This line's own word spacing was too compressed/inconsistent for
                # _row_cells to split into cells at all — but if its words plainly
                # cover most of the table's own columns anyway, it's a fresh row that
                # failed self-segmentation, not nothing (see
                # _row_from_reference_overlap).
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
            _inject_leading_gpt_word(matched_cells, reference, line)
            block.append((line, matched_cells))
            mismatch_streak = 0
            last_was_summary = False
            continue
        # Tried before _merge_wrapped_continuation, and unconditionally skips it when
        # the row above was itself a summary row (see last_was_summary below): a
        # second summary row (e.g. "TỔNG CỘNG" right after "VAT 10%") must never be
        # tested for accidental bbox overlap against the summary row before it --
        # their labels commonly occupy similar horizontal space (both are the same
        # kind of merged, right-aligned label cell spanning most of the row's own
        # width), which would otherwise satisfy the continuation-overlap check and
        # glue two independent summary rows into one.
        summary_cells = _summary_row_cells(line, reference)
        if summary_cells is not None:
            block.append((line, summary_cells))
            mismatch_streak = 0
            last_was_summary = True
            continue
        # A subtotal/VAT/total row is always the LAST thing of its kind in a real
        # document -- nothing ever wraps FROM one onto the next line the way an item
        # description does -- so the line right after one is never treated as its
        # continuation, no matter how its words happen to land. Skipping this check
        # here (rather than relying on the label cell's own bbox to just not overlap
        # anything) matters because that label cell is deliberately wide (spanning
        # most of the row, from the line's own left edge to the amount column), so
        # almost anything positioned in the ordinary left/center of the page --
        # including a signature block right below the table -- would otherwise
        # satisfy the overlap check purely by sharing that space, not by actually
        # being a continuation of the total.
        if not last_was_summary and block and _merge_wrapped_continuation(block[-1][1], line):
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
            last_was_summary = False
        # else: one-off anomaly (e.g. a stamp mangling just this one row, badly
        # enough that it doesn't even split into word-groups at all) — drop
        # this row and keep accumulating against the same reference row.
    flush()
    return tables


def _image_coverage_ratio(page):
    """Fraction of the page's area covered by embedded raster images.

    A letterhead logo, a company stamp, or a scanned signature sitting in the
    corner of an otherwise fully native page doesn't make that page's text layer
    untrustworthy -- only an image spanning most of the page (a genuine scan)
    does. Rects are summed rather than unioned, so overlapping images only ever
    push the estimate up, never down -- the safe direction for this check, whose
    only job is deciding whether the (expensive) OCR/GPT vision fallback below is
    warranted.
    """
    page_area = page.rect.width * page.rect.height
    if page_area <= 0:
        return 0.0
    covered = sum(
        (rect := pymupdf.Rect(info["bbox"]) & page.rect).width * rect.height
        for info in page.get_image_info()
    )
    return min(1.0, covered / page_area)


# Above this fraction of the page's area covered by embedded images, the native
# text layer (if any) is no longer trusted on its own -- see _image_coverage_ratio.
# Sized well clear of a corner logo/stamp/signature (commonly under 10-15% of a
# contract page) but well under a full-page scan (~100%, modulo the odd stray
# pixel of embedded margin/whitespace image some scanners emit).
_SCAN_IMAGE_COVERAGE_THRESHOLD = 0.45


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
        # A page is only sent through OCR/GPT vision when it lacks a usable native
        # text layer, or when embedded images cover enough of it that the text
        # layer can no longer be trusted as the full page content (a real scan,
        # not just a logo/stamp/signature alongside real text) -- see
        # _image_coverage_ratio.
        native = bool(raw_words) and _image_coverage_ratio(page) <= _SCAN_IMAGE_COVERAGE_THRESHOLD
        ocr_engine_choice = config.get("ocr_engine")
        # "..._vision_only" (see Settings.ocr_engine's docstring) skips Tesseract
        # entirely for a scanned/mixed page -- the vision provider is the SOLE source
        # of both text and table structure, not just a text substitution layered on
        # top of Tesseract's own bbox/line order like gpt_vision/mistral_vision below.
        vision_only = not native and ocr_engine_choice in ("gpt_vision_only", "mistral_vision_only")
        groups = defaultdict(list)
        issue = None
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
        elif vision_only:
            image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            if ocr_engine_choice == "mistral_vision_only":
                segments = _mistral_vision_page(image, config)
                vision_model = config.get("ocr_mistral_model", "mistral-ocr-4")
                unavailable_issue = "MISTRAL_VISION_UNAVAILABLE"
            else:
                gpt_lines = _gpt_vision_lines(image, config)
                # GPT's own no-markdown transcription never demarcates a table inline
                # the way Mistral's OCR endpoint does (see _GPT_VISION_FULL_PAGE_TABLE_
                # PROMPT), so there is no real insertion point for it within the
                # prose -- it is simply appended after every prose line, unlike
                # Mistral's exact before/after placement from the same response. GPT
                # also only ever extracts ONE table this way, never several.
                if gpt_lines is None:
                    segments = None
                else:
                    table_rows = _gpt_vision_page_table(image, config)
                    segments = [("text", gpt_lines)] + ([("table", table_rows)] if table_rows else [])
                vision_model = config.get("ocr_vision_model", "gpt-5.6-terra")
                unavailable_issue = "GPT_VISION_UNAVAILABLE"

            engine = f"vision_only+{vision_model}"
            if segments is None:
                lines, vision_tables = [], []
                issue = unavailable_issue
            elif ocr_engine_choice == "mistral_vision_only":
                lines, vision_tables = _assemble_vision_only_page_from_blocks(segments, payload)
            else:
                lines, vision_tables = _assemble_vision_only_page(segments, payload)
            # _find_tables (native PDF vector tables) already ran above and is empty
            # for a scanned page -- vision_tables is the only source of a table here.
            tables = vision_tables
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

        if not vision_only:
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

        if not vision_only and lines and engine == "tesseract" and ocr_engine_choice in ("gpt_vision", "mistral_vision"):
            # Tesseract stays the source of bbox/line order; a vision re-transcription
            # only ever REPLACES the text of an already-anchored line, never its
            # position. When both sources agree on line count, pairing by position
            # needs no further evidence. When they don't, _align_gpt_lines works out
            # the correspondence (and drops whichever Tesseract lines don't confidently
            # match anything — see its docstring) instead of discarding the whole
            # re-transcription. This branch is shared verbatim between gpt_vision and
            # mistral_vision (the two are mutually exclusive, never both at once) —
            # only which function supplies vision_lines, the model label, and the two
            # issue codes below differ per provider. _align_gpt_words/_align_gpt_lines
            # and the "leading_gpt_text"/"trailing_gpt_text" line keys keep their
            # existing (GPT-era) names on purpose even for a Mistral-sourced
            # correction — they're provider-agnostic text aligners, and renaming them
            # would mean also touching _ocr_tables/_inject_leading_gpt_word/_row_cells,
            # which already read those exact keys, for no behavioral change.
            if ocr_engine_choice == "gpt_vision":
                vision_lines = _gpt_vision_lines(image, config)
                vision_model = config.get("ocr_vision_model", "gpt-5.6-terra")
                unavailable_issue = "GPT_VISION_UNAVAILABLE"
                mismatch_issue = "GPT_VISION_LINE_COUNT_MISMATCH"
            else:
                vision_lines = _mistral_vision_lines(image, config)
                vision_model = config.get("ocr_mistral_model", "mistral-ocr-4")
                unavailable_issue = "MISTRAL_VISION_UNAVAILABLE"
                mismatch_issue = "MISTRAL_VISION_LINE_COUNT_MISMATCH"

            if vision_lines is None:
                issue = unavailable_issue
            elif len(vision_lines) == len(lines):
                for line, vision_text in zip(lines, vision_lines):
                    line["text"] = vision_text
                    words = sorted(line["words"], key=lambda w: w["bbox"][0])
                    vision_words = vision_text.split()
                    # Per-word substitution (Tesseract's own bbox is always kept) via
                    # sequence alignment, not a raw word-count check — Tesseract
                    # supplies geometry unconditionally, the vision provider (generally
                    # more accurate, especially on Vietnamese diacritics) supplies the
                    # actual characters wherever the two sources' words confidently
                    # align. This is what _ocr_tables' own column splitting reads (it
                    # groups line["words"], never line["text"]), so a table's cell
                    # TEXT benefits from vision re-transcription too, not just the
                    # line's own display string. See _align_gpt_words for what
                    # "confidently" means and why a whole-line word-count mismatch no
                    # longer throws away every other word's correction along with the
                    # one word the two sources disagree about.
                    mapping, leading_extra, trailing_extra = _align_gpt_words(
                        [w["text"] for w in words], vision_words
                    )
                    for index, vision_word in mapping.items():
                        words[index]["text"] = vision_word
                    # A vision-only leading word (no Tesseract bbox at all -- most often
                    # a row's own STT number, swallowed into an unrelated garbled
                    # line next to it) has real text but nowhere of its own to live
                    # yet; _ocr_tables can still place it using the table's own
                    # already-known STT column position (see _inject_leading_gpt_word).
                    if leading_extra:
                        line["leading_gpt_text"] = leading_extra
                    # Symmetrically, a vision-only trailing word or two (e.g. a plain
                    # "0" Tesseract detected no ink for at all) -- see _row_cells.
                    if trailing_extra:
                        line["trailing_gpt_text"] = trailing_extra
                engine = f"tesseract+{vision_model}"
            else:
                matches, noise_indices = _align_gpt_lines(
                    [line["text"] for line in lines], vision_lines
                )
                if not matches:
                    issue = mismatch_issue
                else:
                    # A line that aligned to some vision line but too loosely to trust
                    # keeps its own original Tesseract text (real content, see
                    # _align_gpt_lines' docstring). A line with NO counterpart at all
                    # is dropped outright -- the vision provider saw the actual pixels
                    # and found nothing there worth transcribing (typically a stamp/
                    # seal/watermark fragment Tesseract misread as text), so keeping
                    # its garbled reading around would just be reintroducing noise
                    # into "Toàn văn theo trang" and into _ocr_tables, which reads
                    # this same list.
                    lines = [
                        {**line, "text": matches.get(i, line["text"])}
                        for i, line in enumerate(lines)
                        if i not in noise_indices
                    ]
                    engine = f"tesseract+{vision_model}"

        if not tables and engine.startswith("tesseract"):
            # No native PDF structure for find_tables to read on a scanned page — fall
            # back to detecting a table from the OCR words' own geometry.
            tables = _ocr_tables(lines, payload)

        if tables and engine.startswith("tesseract") and ocr_engine_choice == "gpt_vision":
            # _ocr_tables' own bbox is still used to locate and crop each table (that
            # part works -- see _apply_gpt_vision_table) — only the CONTENT inside it
            # is replaced, since deriving that content from Tesseract's word-position
            # clustering is exactly what can silently lose a whole column.
            tables = [_apply_gpt_vision_table(table, image, config) for table in tables]
        elif tables and engine.startswith("tesseract") and ocr_engine_choice == "mistral_vision":
            tables = [_apply_mistral_vision_table(table, image, config) for table in tables]

        # OCR empty output is not proof of a blank page. Only fills in the generic
        # issue when nothing more specific already explains the emptiness (e.g.
        # vision_only's own MISTRAL_VISION_UNAVAILABLE/GPT_VISION_UNAVAILABLE, set
        # above when the provider itself failed and there was no Tesseract to fall
        # back to) -- the old gpt_vision/mistral_vision path never reaches this
        # branch with `issue` already set, since Tesseract's own lines keep `lines`
        # non-empty regardless of whether vision succeeded.
        if not lines:
            status, issue = "needs_review", issue or "EMPTY_OCR_REQUIRES_REVIEW"
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
