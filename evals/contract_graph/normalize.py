"""Turn a legal-document page (HTML or DOCX) into one line-per-paragraph text form.

HTML and DOCX end up in the same shape: footnote references are inline ``[n]``
markers and the footnote bodies are ``[n] ...`` lines in a block at the end, so
the gold extractor never needs to know which format a page came from.
"""

from __future__ import annotations

import html
import io
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
import zipfile

_BLOCK_TAGS = r"p|div|li|tr|h[1-6]|table|thead|tbody|tfoot|ul|ol|dl|dt|dd|section|article|header|footer|blockquote|pre"
_DROP = re.compile(
    r"<!--.*?-->|<head\b.*?</head\s*>|<(script|style|noscript|template)\b.*?</\1\s*>", re.S | re.I
)
_SCRIPT = re.compile(r"<script\b[^>]*>(.*?)</script\s*>", re.S | re.I)
_JSON_STRING = re.compile(r'"((?:[^"\\]|\\.)*)"', re.S)
_ESCAPED_TAG = "\\u003c"
_SPACES = re.compile(r"[ \t\r\f\v\u00a0\u2000-\u200b\u202f\u205f\u3000\ufeff]+")
# A line that opens a point/clause label must stay on its own line even after an unterminated line.
_LABEL_LINE = re.compile(r"^(?:[a-zđ]\d*\)|\d+[a-zđ]?\.(?=\s|\[|$))")
_NOTE_LINE = re.compile(r"^\[(\d+)\]", re.M)
_QUOTES = re.compile(r"[“”\"]")
# substantive = long enough that two documents sharing it by accident is unlikely
_SUBSTANTIVE_LINE = 20

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_DOCX_SKIP_NOTE_TYPES = {"separator", "continuationSeparator", "continuationNotice"}


def html_to_text(raw: str | bytes) -> str:
    """Visible text of an HTML page, plus any HTML the page ships JSON-escaped inside scripts.

    Next.js pages (vcci.com.vn) repeat the document as ``\\u003cp\\u003e…`` strings in
    ``self.__next_f.push`` payloads, next to unrelated documents. A payload chunk is merged
    only when it re-renders the visible document (it contains at least half of the visible
    substantive lines); its lines missing from the visible page are appended in order.
    """

    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    visible = _render(raw)
    lines = list(visible)
    seen = set(visible)
    substantive = [line for line in visible if len(line) >= _SUBSTANTIVE_LINE]
    for chunk in _escaped_payloads(raw):
        chunk_lines = _render(chunk)
        if substantive:
            present = set(chunk_lines)
            shared = sum(1 for line in substantive if line in present)
            if shared * 2 < len(substantive):
                continue  # another document carried by the page, not this one
        for line in chunk_lines:
            if line not in seen:
                lines.append(line)
                seen.add(line)
    return _finish(lines)


def docx_to_text(data: bytes) -> str:
    """Paragraph text of ``word/document.xml``; footnotes become ``[n]`` markers + a closing note block."""

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = set(zf.namelist())
        bodies: dict[str, str] = {}
        if "word/footnotes.xml" in names:
            for note in ET.fromstring(zf.read("word/footnotes.xml")).iter(_W + "footnote"):
                if note.get(_W + "type") in _DOCX_SKIP_NOTE_TYPES:
                    continue
                bodies[note.get(_W + "id", "")] = " ".join(
                    _docx_runs(p, {}) for p in note.iter(_W + "p")
                )
        document = ET.fromstring(zf.read("word/document.xml"))

    numbering: dict[
        str, int
    ] = {}  # footnote id -> number shown to the reader (order of first reference)
    lines = [_docx_runs(p, numbering) for p in document.iter(_W + "p")]
    lines.extend(f"[{no}] {bodies.get(fid, '')}" for fid, no in numbering.items())
    return _finish(line for chunk in lines for line in chunk.split("\n"))


def split_notes(text: str) -> tuple[str, str]:
    """(body, note block). The block starts at the last line opening with the smallest note number."""

    starts = [(int(m.group(1)), m.start()) for m in _NOTE_LINE.finditer(text)]
    if not starts:
        return text, ""
    first = min(no for no, _ in starts)
    cut = max(pos for no, pos in starts if no == first)
    return text[:cut].rstrip("\n"), text[cut:]


def operative_body(text: str, article: str = "1", next_article: str = "2") -> str:
    """Body of ``Điều <article>.`` up to the next ``Điều <next_article>.`` heading.

    Only headings outside quotation marks count: an amending article quotes the new wording
    ("“Điều 2. …”") and that quote must not end it. Of all occurrences (table of contents,
    body) the longest span wins.
    """

    start_re = _heading(article)
    end_re = _heading(next_article)
    outside = _outside_quotes(text)
    starts = [m.start() for m in start_re.finditer(text) if outside(m.start())]
    ends = [m.start() for m in end_re.finditer(text) if outside(m.start())]
    best = ""
    for start in starts:
        end = next((e for e in ends if e > start), len(text))
        if end - start > len(best):
            best = text[start:end]
    return best.rstrip()


def _heading(article: str) -> re.Pattern[str]:
    # a heading opens a line or follows a finished sentence; "khoản 3 Điều 2." mid-sentence is a reference
    return re.compile(rf"(?:^|(?<=[.:;”\"] ))Điều\s+{re.escape(article)}\s*\.", re.M)


def _outside_quotes(text: str):
    marks = [(m.start(), m.group()) for m in _QUOTES.finditer(text)]

    def outside(pos: int) -> bool:
        depth, straight = 0, False
        for at, mark in marks:
            if at >= pos:
                break
            if mark == "“":
                depth += 1
            elif mark == "”":
                depth = max(0, depth - 1)
            else:
                straight = not straight
        return depth == 0 and not straight

    return outside


def _render(fragment: str) -> list[str]:
    text = _DROP.sub(" ", fragment)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"<br\b[^>]*>", "\n", text, flags=re.I)
    text = re.sub(rf"</?(?:{_BLOCK_TAGS})\b[^>]*>", "\n", text, flags=re.I)
    text = re.sub(r"</?t[dh]\b[^>]*>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]*>", "", text)  # inline tags carry no space: "a<sub>1</sub>)" is "a1)"
    text = html.unescape(text)
    lines = (_SPACES.sub(" ", line).strip() for line in text.split("\n"))
    return [unicodedata.normalize("NFC", line) for line in lines if line]


def _escaped_payloads(raw: str):
    for script in _SCRIPT.finditer(raw):
        body = script.group(1)
        if _ESCAPED_TAG not in body:
            continue
        for literal in _JSON_STRING.finditer(body):
            if _ESCAPED_TAG not in literal.group(1):
                continue
            try:
                yield json.loads(f'"{literal.group(1)}"')
            except ValueError:
                continue  # not a JSON string literal (e.g. a JS regex); nothing to decode


def _finish(lines) -> str:
    cleaned = [unicodedata.normalize("NFC", _SPACES.sub(" ", line).strip()) for line in lines]
    return "\n".join(_join_hard_wraps([line for line in cleaned if line]))


def _join_hard_wraps(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        if (
            out
            and not out[-1].endswith((".", ";", ":"))
            and line[0].islower()
            and not _LABEL_LINE.match(line)
        ):
            out[-1] = f"{out[-1]} {line}"
        else:
            out.append(line)
    return out


def _docx_runs(paragraph: ET.Element, numbering: dict[str, int]) -> str:
    parts: list[str] = []
    for el in paragraph.iter():
        if el.tag == _W + "t":
            parts.append(el.text or "")
        elif el.tag in (_W + "tab", _W + "noBreakHyphen"):
            parts.append(" " if el.tag == _W + "tab" else "-")
        elif el.tag in (_W + "br", _W + "cr"):
            parts.append("\n")
        elif el.tag == _W + "footnoteReference":
            fid = el.get(_W + "id", "")
            parts.append(f"[{numbering.setdefault(fid, len(numbering) + 1)}]")
    return "".join(parts)
