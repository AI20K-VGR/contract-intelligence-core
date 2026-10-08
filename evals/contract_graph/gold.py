"""Auto-gold from VBHN footnotes: "[n] Điểm này được bổ sung theo quy định tại <src> <doc>".

Each record is one amendment edge: source address in the amending document, op, and the
target address where the marker ``[n]`` sits in the consolidated body. Records are
``approved: false`` until a person reviews them (D13); only approved records may ever
count as business accuracy.

Canonical address (shared with P2): lowercase NFC, level words folded to ASCII
(``diem``/``khoan``/``dieu``/``phu luc``), the point letter keeps ``đ`` (D12), leading
zeros dropped from the number part, smallest level first:
``diem đ khoan 2 dieu 1``, ``khoan 5a dieu 18``, ``diem d1 khoan 2 dieu 3``, ``phu luc 1``.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

from evals.contract_graph.normalize import split_notes
from evals.contract_graph.segment import ANNEX, ARTICLE, CLAUSE, DIVISION, POINT

EXTRACTOR_VERSION = "p1-vbhn-notes-1"
CITE = "theo quy định tại"
# Order matters: the longer phrase wins ("sửa đổi, bổ sung" is a substitution, not an insertion).
OPS = (
    ("sửa đổi, bổ sung", "SUBSTITUTION"),
    ("sửa đổi", "SUBSTITUTION"),
    ("bổ sung", "INSERTION"),
    ("bãi bỏ", "REPEAL"),
    ("thay thế", "SUBSTITUTION"),
    ("thay cụm từ", "SUBSTITUTION"),
    ("bỏ cụm từ", "REPEAL"),
)
OTHER = "OTHER"
_UNNUMBERED = "?"

_LEVEL_WORDS = {"điểm": "diem", "khoản": "khoan", "điều": "dieu", "phụ lục": "phu luc"}
_LEVEL_ORDER = ("điểm", "khoản", "điều", "phụ lục")
_ADDRESS_TOKEN = re.compile(r"(?<!\w)(điểm|khoản|điều|phụ lục)\s+([0-9a-zđ]+)(?!\w)")
_POINT_VALUE = re.compile(r"([a-zđ])(\d*)")
_NUMBER_VALUE = re.compile(r"(\d+)([a-zđ]?)")
_ROMAN = re.compile(r"[ivxlc]+")
_DOC_NO = re.compile(r"\d+/\d{4}/[A-Za-zĐđ0-9][A-Za-zĐđ0-9-]*")
_NOTE = re.compile(r"^\[(\d+)\]\s*(.*?)(?=^\[\d+\]|\Z)", re.M | re.S)
_LEVEL = re.compile(r"(?<!\w)(điểm|khoản|điều|cụm từ|phụ lục|mục|chương|mẫu)\s+này(?!\w)")
_CITE = re.compile(re.escape(CITE), re.I)


@dataclass(frozen=True)
class Note:
    no: int
    text: str


@dataclass(frozen=True)
class Citation:
    head: str  # wording before this "theo quy định tại": carries the op
    src_address: str | None
    amending_doc: str | None


def canonical_address(text: str | None) -> str | None:
    """First điểm/khoản/điều/phụ lục value in ``text``, in the canonical form above."""

    if not text:
        return None
    found: dict[str, str] = {}
    for m in _ADDRESS_TOKEN.finditer(unicodedata.normalize("NFC", text).lower()):
        level, value = m.group(1), _canonical_value(m.group(1), m.group(2))
        if value is not None and level not in found:
            found[level] = value
    if not found:
        return None
    return " ".join(
        f"{_LEVEL_WORDS[level]} {found[level]}" for level in _LEVEL_ORDER if level in found
    )


def canonical_doc(number: str | None) -> str | None:
    return number.strip().upper() if number else None


def extract_notes(text: str) -> list[Note]:
    """Footnotes of the note block that cite an amending provision ("theo quy định tại")."""

    _, block = split_notes(text)
    notes = []
    for m in _NOTE.finditer(block):
        body = " ".join(m.group(2).split())
        if _CITE.search(body):
            notes.append(Note(int(m.group(1)), body))
    return sorted(notes, key=lambda n: n.no)


def citations(note: Note) -> list[Citation]:
    parts = _CITE.split(note.text)
    out: list[Citation] = []
    head = parts[0]
    for index, part in enumerate(parts[1:]):
        doc = _DOC_NO.search(part)
        address_text = part[: doc.start()] if doc else part
        if index:
            head = _last_clause(head)
        out.append(
            Citation(
                head, canonical_address(address_text), canonical_doc(doc.group()) if doc else None
            )
        )
        head = part[doc.end() :] if doc else part
    return out


def note_op(note: Note, amending_doc: str | None = None) -> str:
    """Op from the wording before "theo quy định tại" only: the decree title after it repeats
    "sửa đổi, bổ sung" and must not decide the op (spike bug #1)."""

    cites = citations(note)
    cite = _pick(cites, amending_doc)
    if cite is None:
        return OTHER
    return _op_of(cite.head) or _op_of(cites[0].head) or OTHER


def note_source(note: Note, amending_doc: str | None = None) -> tuple[str | None, str | None]:
    cite = _pick(citations(note), amending_doc)
    return (cite.src_address, cite.amending_doc) if cite else (None, None)


def note_level(note: Note) -> str | None:
    head = _CITE.split(note.text, maxsplit=1)[0].lower()
    m = _LEVEL.search(head)
    return m.group(1) if m else None


def anchor_target(vbhn_body: str, note_no: int, level: str | None) -> str | None:
    """Address of the unit holding the first ``[note_no]`` of the body, at the note's level.

    "Điểm/Khoản/Điều/Phụ lục này" pick that level; "Cụm từ" or no level picks the smallest
    unit holding the marker. Missing unit at the asked level → None (never a guess).
    """

    marker = f"[{note_no}]"
    ctx: dict[str, str | None] = {"điều": None, "phụ lục": None, "khoản": None, "điểm": None}
    for line in vbhn_body.split("\n"):
        _advance(ctx, line)
        if marker in line:
            return _address_at(ctx, level)
    return None


def build_gold(pair_id: str, vbhn_text: str, amending_doc: str) -> list[dict]:
    body, _ = split_notes(vbhn_text)
    records = []
    for note in extract_notes(vbhn_text):
        src, doc = note_source(note, amending_doc)
        if doc is None:
            continue  # the note cites another amending document of the same VBHN
        level = note_level(note)
        records.append(
            {
                "pair_id": pair_id,
                "note_no": note.no,
                "op": note_op(note, amending_doc),
                "level": level,
                "src_address": src,
                "amending_doc": doc,
                "target_address": anchor_target(body, note.no, level),
                "note_text": note.text[:200],
                "approved": False,
                "extractor_version": EXTRACTOR_VERSION,
            }
        )
    return records


def gold_summary(records: list[dict]) -> dict[str, int]:
    counts = Counter(r["op"] for r in records)
    return {op: counts[op] for op in sorted(counts)}


def _canonical_value(level: str, value: str) -> str | None:
    if level == "điểm":
        m = _POINT_VALUE.fullmatch(value)
        return f"{m.group(1)}{int(m.group(2)) if m.group(2) else ''}" if m else None
    if level == "phụ lục":
        if value.isdigit():
            return str(int(value))
        return value if _ROMAN.fullmatch(value) else None
    m = _NUMBER_VALUE.fullmatch(value)
    return f"{int(m.group(1))}{m.group(2)}" if m else None


def _pick(cites: list[Citation], amending_doc: str | None) -> Citation | None:
    if amending_doc is None:
        return cites[0] if cites else None
    want = canonical_doc(amending_doc)
    return next((c for c in cites if c.amending_doc == want), None)


def _op_of(head: str) -> str | None:
    low = head.lower()
    return next((op for phrase, op in OPS if phrase in low), None)


def _last_clause(head: str) -> str:
    """Wording that belongs to a later citation: after the last ';', from its last "được"."""

    clause = head.rsplit(";", 1)[-1]
    at = clause.lower().rfind("được")
    return clause[at:] if at >= 0 else clause


def _advance(ctx: dict[str, str | None], line: str) -> None:
    if m := ARTICLE.match(line):
        ctx.update({"điều": m.group(1).lower(), "phụ lục": None, "khoản": None, "điểm": None})
    elif m := ANNEX.match(line):
        annex = m.group(1).lower() if m.group(1) else _UNNUMBERED
        ctx.update({"điều": None, "phụ lục": annex, "khoản": None, "điểm": None})
    elif DIVISION.match(line):
        ctx.update(dict.fromkeys(ctx))  # a chapter/section heading is outside every article
    elif m := CLAUSE.match(line):
        ctx.update({"khoản": m.group(1).lower(), "điểm": None})
    elif m := POINT.match(line):
        ctx["điểm"] = m.group(1)


def _address_at(ctx: dict[str, str | None], level: str | None) -> str | None:
    if ctx["phụ lục"] == _UNNUMBERED:
        return None  # inside "PHỤ LỤC" without a number: no canonical address to give
    if level in (None, "cụm từ"):
        level = next((lv for lv in _LEVEL_ORDER if ctx[lv]), None)
        if level is None:
            return None
    if level not in _LEVEL_WORDS or not ctx[level]:
        return None  # "Mục/Chương này", or the asked unit is not where the marker sits
    start = _LEVEL_ORDER.index(level)
    parts = [f"{lv} {ctx[lv]}" for lv in _LEVEL_ORDER[start:] if ctx[lv]]
    return canonical_address(" ".join(parts))
