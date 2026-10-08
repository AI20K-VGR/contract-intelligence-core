"""Operation sentences ("Sửa đổi, bổ sung điểm c khoản 1 Điều 3 như sau:") → ``Operation``.

Text only, no structure: ``split_operation_units`` cuts a node text into units (line-start
labels ``1.``/``5a.``/``a)``/``d1)``; sentences where there is no label) and
``parse_operation`` reads the op, the target addresses and the new wording of one unit.
Whether an operation may become an edge (container units, the RT-06 source limit for
REJECTION/SCOPE_LIMIT, resolution) is decided by ``builder.plan_edges``.

Verb → op follows the VBHN gold convention (``evals/contract_graph/gold.py`` OPS) so the
harness can compare: "sửa đổi, bổ sung" wins over "bổ sung", "bỏ cụm từ" is a REPEAL,
"thay cụm từ" a SUBSTITUTION. The text after "như sau:" is new wording, never an operation.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

from app.contracts.contract_graph import NEW_TEXT_MAX, EdgeOp
from app.pipeline.contract_graph.address import Address, number_value, parse_addresses, point_value
from app.pipeline.relation_markers import _AMEND_EXCLUDE, has_amend_marker

UnitLevel = Literal["khoan", "diem"]

_OPEN, _CLOSE, _STRAIGHT = "“", "”", '"'
_LABEL = re.compile(r"[ \t]*(?:(?P<khoan>\d+[a-zđ]?)\.(?=[ \t]|$)|(?P<diem>[a-zđ]\d*)\))[ \t]*")
_NEW_TEXT = re.compile(r"(?:như\s+sau|nội\s+dung\s+sau)\s*:?", re.I)
_NEW_TEXT_COLON = re.compile(r"(?:như\s+sau|nội\s+dung\s+sau)\s*:$", re.I)
_EXPECTS = re.compile(r"(?:(?:như\s+sau|nội\s+dung\s+sau)\s*:?|:)\s*$", re.I)
_LEVEL_FIRST = r"(?:điểm|khoản|điều|phụ\s+lục|mục)(?![\wđ])"

_NEGATION = re.compile(
    r"không\s+(?:được|bị)\s+(?:sửa\s+đổi|bổ\s+sung|bãi\s+bỏ|thay\s+thế)(?![\wđ])", re.I
)
_SCOPE = re.compile(
    rf"^(?P<target>{_LEVEL_FIRST}.*?)\s+không\s+áp\s+dụng\s+(?:đối\s+với|cho)\s+"
    r"(?P<scope>.+?)\s*[.;]?\s*$",
    re.I | re.S,
)
_REJECTION = re.compile(r"có\s+quyền\s+từ\s+chối(?![\wđ])(?P<rest>.*)$", re.I | re.S)
_REJECTION_TARGET = re.compile(r"(?:quy\s+định\s+tại|theo|tại)\s+(?P<target>.+)$", re.I | re.S)
_ANNEX_VERB = re.compile(
    rf"^(?:điều\s+chỉnh|thay\s+đổi)\s+(?P<target>{_LEVEL_FIRST}.*?)\s+"
    r"(?:của\s+hợp\s+đồng\s+)?như\s+sau\s*:?\s*$",
    re.I | re.S,
)
_REPLACED_BY = re.compile(
    rf"^(?P<target>{_LEVEL_FIRST}.*?)\s+được\s+thay\s+bằng(?:\s+nội\s+dung\s+sau)?\s*:?\s*$",
    re.I | re.S,
)
_PASSIVE = re.compile(
    r"^(?P<target>.+?)\s+(?:được|bị)\s+"
    r"(?P<verb>sửa\s+đổi\s*,\s*bổ\s+sung|sửa\s+đổi|bổ\s+sung|bãi\s+bỏ|thay\s+thế)(?![\wđ])",
    re.I | re.S,
)
_LAPSE = re.compile(r"^(?P<target>.+?)\s+(?:không\s+còn|hết)\s+hiệu\s+lực(?![\wđ])", re.I | re.S)
_REWRITE = re.compile(
    r"(?<![\wđ])(?:sửa(?:\s+đổi)?|điều\s+chỉnh|thay\s+đổi)\s+(?P<target>.+?)\s+"
    r"(?<!hoàn\s)thành\s+\S",
    re.I | re.S,
)
# anchored heads, longest first (gold OPS order)
_HEADS = (
    (re.compile(r"^sửa\s+đổi\s*,\s*bổ\s+sung(?![\wđ])", re.I), EdgeOp.SUBSTITUTION, "amend"),
    (re.compile(r"^sửa\s+đổi(?![\wđ])", re.I), EdgeOp.SUBSTITUTION, "amend"),
    (re.compile(r"^thay\s+thế(?![\wđ])", re.I), EdgeOp.SUBSTITUTION, "replace"),
    (re.compile(r"^thay\s+cụm\s+từ(?![\wđ])", re.I), EdgeOp.SUBSTITUTION, "replace_phrase"),
    (re.compile(r"^bổ\s+sung(?![\wđ])", re.I), EdgeOp.INSERTION, "insert"),
    (re.compile(r"^bãi\s+bỏ(?![\wđ])", re.I), EdgeOp.REPEAL, "repeal"),
    (re.compile(r"^bỏ\s+cụm\s+từ(?![\wđ])", re.I), EdgeOp.REPEAL, "repeal_phrase"),
    (re.compile(r"^h(?:ủy|uỷ)\s+bỏ(?![\wđ])", re.I), EdgeOp.REPEAL, "repeal"),
)
_CLAUSE_NUMBER = re.compile(r"(\d+)([a-zđ]?)")
_BARE_ANCHOR = re.compile(
    r"(?<![\wđ])(?:tiếp\s+)?(?:sau|dưới)(?=\s+(?:điểm|khoản|điều|phụ\s+lục)(?![\wđ]))", re.I
)
_INSERT_WHERE = re.compile(r"(?<![\wđ])vào(?![\wđ])", re.I)
_PASSIVE_OPS = {
    "sửa đổi, bổ sung": EdgeOp.SUBSTITUTION,
    "sửa đổi": EdgeOp.SUBSTITUTION,
    "bổ sung": EdgeOp.INSERTION,
    "bãi bỏ": EdgeOp.REPEAL,
    "thay thế": EdgeOp.SUBSTITUTION,
}


@dataclass(frozen=True)
class Unit:
    """One operation candidate; ``text[char_start:char_end]`` of the node text, label excluded.

    ``parent`` is the index of the enclosing unit (a ``khoan`` unit for a ``diem`` unit).
    """

    label: str | None
    level: UnitLevel | None
    text: str
    char_start: int
    char_end: int
    parent: int | None = None


@dataclass(frozen=True)
class Operation:
    op: EdgeOp
    target_text: str
    addresses: tuple[Address, ...]
    new_text: str | None
    scope_text: str | None
    standard: bool
    template: str
    span: str  # the operation sentence, an exact prefix of the unit text (citation span)


def split_operation_units(text: str) -> list[Unit]:
    if not text or not text.strip():
        return []
    depth = _quote_depth(text)
    labels = _label_lines(text, depth)
    first = labels[0][0] if labels else len(text)
    units: list[Unit] = []
    for start, end in _sentences(text, 0, first, depth):
        units.append(Unit(None, None, text[start:end], start, end))
    expects = bool(units) and _expects_new_text(units[-1].text)
    chosen = _choose_labels(text, first, expects)
    stop = chosen[0][0] if chosen else len(text)
    if expects and stop > first:
        # label lines absorbed as new wording belong to the last sentence before them
        last = units[-1]
        end = last.char_start + len(text[last.char_start : stop].rstrip())
        units[-1] = Unit(None, None, text[last.char_start : end], last.char_start, end)
    clause_parent: int | None = None
    for i, (_, body_start, label, level) in enumerate(chosen):
        end = chosen[i + 1][0] if i + 1 < len(chosen) else len(text)
        end = body_start + len(text[body_start:end].rstrip())
        parent = clause_parent if level == "diem" else None
        units.append(Unit(label, level, text[body_start:end], body_start, end, parent))
        if level == "khoan":
            clause_parent = len(units) - 1
    return units


def head_of(text: str) -> str:
    """The operation sentence of a unit: first line, cut after "như sau:" or the first
    sentence end outside quotes."""

    line = text[: _line_end(text, 0)]
    m = _NEW_TEXT.search(line)
    if m:
        line = line[: m.end()]
    depth = _quote_depth(line)
    for i, ch in enumerate(line):
        if ch in ".;" and depth[i] == 0 and (i + 1 == len(line) or line[i + 1].isspace()):
            if ch == ";" and _continues_address_list(line, i + 1):
                continue
            return line[: i + 1]
    return line.rstrip()


# "…tại khoản 2 Điều 15; khoản 1 Điều 16; Điều 19" — a ';' followed by another address is a
# list separator, not a sentence end. A following verb ("; sửa đổi Điều 5") still splits.
_ADDRESS_AFTER_SEMICOLON = re.compile(r"\s*(?:khoản|điểm|điều|mục|phụ\s+lục)\s+[\wđ]", re.I)


def _continues_address_list(text: str, pos: int) -> bool:
    return bool(_ADDRESS_AFTER_SEMICOLON.match(text, pos))


def parse_operation(unit_text: str) -> Operation | None:
    """The op of one unit, or ``None`` (no template, excluded, or no target address)."""

    span = head_of(unit_text)
    head = _nfc(span).strip()
    if not head or _NEGATION.search(head):
        return None
    masked = _mask_quotes(head)
    new_text = _new_text(unit_text)
    if m := _SCOPE.match(masked):
        return _operation(
            EdgeOp.SCOPE_LIMIT,
            m.group("target"),
            None,
            True,
            "scope_limit",
            span,
            scope_text=head[m.start("scope") : m.end("scope")],
        )
    if (m := _REJECTION.search(masked)) and (t := _REJECTION_TARGET.search(m.group("rest"))):
        return _operation(EdgeOp.REJECTION, t.group("target"), None, False, "rejection", span)
    if m := _ANNEX_VERB.match(masked):
        return _operation(
            EdgeOp.SUBSTITUTION, m.group("target"), new_text, False, "annex_verb", span
        )
    if m := _REPLACED_BY.match(masked):
        return _operation(
            EdgeOp.SUBSTITUTION, m.group("target"), new_text, False, "replaced_by", span
        )
    if not has_amend_marker(_collapse_quotes(head)):
        return None
    for pattern, op, template in _HEADS:
        if m := pattern.match(masked):
            target = masked[m.end() :]
            standard = op != EdgeOp.INSERTION or bool(_INSERT_WHERE.search(target))
            if op == EdgeOp.INSERTION and not standard:
                # "Bổ sung Điều 20a dưới/sau Điều 20": the anchor, worded without "vào"
                target = _BARE_ANCHOR.sub("vào sau", target, count=1)
            return _operation(op, target, new_text, standard, template, span)
    if m := _PASSIVE.match(masked):
        op = _PASSIVE_OPS[" ".join(m.group("verb").casefold().split())]
        return _operation(op, m.group("target"), new_text, False, "passive", span)
    if m := _LAPSE.match(masked):
        return _operation(EdgeOp.REPEAL, m.group("target"), None, False, "lapse", span)
    if m := _REWRITE.search(_AMEND_EXCLUDE.sub(lambda x: " " * len(x.group()), masked)):
        return _operation(EdgeOp.SUBSTITUTION, m.group("target"), None, False, "rewrite", span)
    return None


def rejection_without_address(unit_text: str) -> bool:
    """A right to refuse ("có quyền từ chối …") naming no provision: counted, never an edge."""

    head = _mask_quotes(_nfc(head_of(unit_text)))
    m = _REJECTION.search(head)
    if m is None:
        return False
    t = _REJECTION_TARGET.search(m.group("rest"))
    return t is None or not parse_addresses(t.group("target"))


def unit_levels(units: list[Unit], index: int) -> dict[str, str]:
    """Canonical levels named by a unit and its enclosing units ("a)" under "2." → diem/khoan)."""

    levels: dict[str, str] = {}
    walk: int | None = index
    seen: set[int] = set()
    while walk is not None and walk not in seen:
        unit = units[walk]
        seen.add(walk)
        if unit.level == "diem" and unit.label:
            value = point_value(unit.label)
        elif unit.level == "khoan" and unit.label:
            value = number_value(unit.label)
        else:
            value = None
        if unit.level and value and unit.level not in levels:
            levels[unit.level] = value
        walk = unit.parent
    return levels


def _operation(
    op: EdgeOp,
    target: str,
    new_text: str | None,
    standard: bool,
    template: str,
    span: str,
    *,
    scope_text: str | None = None,
) -> Operation | None:
    addresses = tuple(parse_addresses(target))
    if not addresses:
        return None
    return Operation(op, target.strip(), addresses, new_text, scope_text, standard, template, span)


def _new_text(unit_text: str) -> str | None:
    m = _NEW_TEXT.search(unit_text)
    if m is None:
        line_end = _line_end(unit_text, 0)
        if not unit_text[:line_end].rstrip().endswith(":"):
            return None
        rest = unit_text[line_end:]
    else:
        rest = unit_text[m.end() :]
    rest = rest.lstrip(" \t:").strip()
    return rest[:NEW_TEXT_MAX] or None


def _expects_new_text(text: str) -> bool:
    return bool(_EXPECTS.search(head_of(text)))


def _label_lines(text: str, depth: list[int]) -> list[tuple[int, int, str, UnitLevel]]:
    out: list[tuple[int, int, str, UnitLevel]] = []
    pos = 0
    while pos < len(text):
        end = _line_end(text, pos)
        if depth[pos] == 0 and (m := _LABEL.match(text, pos, end)) and m.end() < end:
            if m.group("khoan"):
                out.append((pos, m.end(), m.group("khoan"), "khoan"))
            else:
                out.append((pos, m.end(), m.group("diem"), "diem"))
        pos = end + 1
    return out


def _choose_labels(text: str, start: int, expects: bool) -> list[tuple[int, int, str, UnitLevel]]:
    """Label lines that open a unit. After a unit announcing new wording ("như sau:"), a label
    line opens a unit only when it is itself an operation; label lines inside quotes never do,
    except the next clause number of the list when it is an operation: the quote left open
    above it is a source typo (a missing closing quote would swallow every later item)."""

    chosen: list[tuple[int, int, str, UnitLevel]] = []
    curly, straight = 0, False
    last_clause: str | None = None
    pos = start
    while pos < len(text):
        end = _line_end(text, pos)
        m = _LABEL.match(text, pos, end)
        if m and m.end() < end:
            level: UnitLevel = "khoan" if m.group("khoan") else "diem"
            label = m.group("khoan") or m.group("diem")
            body = text[m.end() : end]
            if curly == 0 and not straight:
                take = not expects or parse_operation(body) is not None
            else:
                take = (
                    level == "khoan"
                    and _follows(label, last_clause)
                    and parse_operation(body) is not None
                )
                if take:
                    curly, straight = 0, False
            if take:
                chosen.append((pos, m.end(), label, level))
                expects = _expects_new_text(body)
                if level == "khoan":
                    last_clause = label
        for ch in text[pos:end]:
            if ch == _OPEN:
                curly += 1
            elif ch == _CLOSE:
                curly = max(0, curly - 1)
            elif ch == _STRAIGHT:
                straight = not straight
        pos = end + 1
    return chosen


def _follows(label: str, previous: str | None) -> bool:
    """``label`` is the next clause number after ``previous`` ("4" after "3", "5a" after "5")."""

    if previous is None:
        return False
    a, b = _CLAUSE_NUMBER.fullmatch(label), _CLAUSE_NUMBER.fullmatch(previous)
    if a is None or b is None:
        return False
    (na, sa), (nb, sb) = (int(a.group(1)), a.group(2)), (int(b.group(1)), b.group(2))
    return (na == nb + 1 and not sa) or (na == nb and sa > sb)


def _sentences(text: str, start: int, end: int, depth: list[int]) -> list[tuple[int, int]]:
    """Sentences of an unlabelled stretch; after "như sau:" the rest (or the quoted block) is
    new wording of that sentence."""

    out: list[tuple[int, int]] = []
    pos = start
    while pos < end:
        while pos < end and text[pos].isspace():
            pos += 1
        if pos >= end:
            break
        stop = _sentence_end(text, pos, end, depth)
        trimmed = pos + len(text[pos:stop].rstrip())
        if trimmed > pos:
            out.append((pos, trimmed))
        pos = stop
    return out


def _sentence_end(text: str, start: int, end: int, depth: list[int]) -> int:
    i = start
    while i < end:
        ch = text[i]
        if depth[i] == 0:
            if ch in ".;" and (i + 1 == end or text[i + 1].isspace()):
                if not (ch == ";" and _continues_address_list(text[:end], i + 1)):
                    return i + 1
            if ch == "\n":
                return i
            if ch == ":" and _NEW_TEXT_COLON.search(text[start : i + 1]):
                return _after_new_text(text, i + 1, end, depth)
        i += 1
    return end


def _after_new_text(text: str, pos: int, end: int, depth: list[int]) -> int:
    """End of the new wording that follows "như sau:" in an unlabelled stretch: the quoted
    block (and its closing punctuation) when it opens with a quote, else the whole stretch."""

    j = pos
    while j < end and text[j].isspace():
        j += 1
    if j >= end or text[j] not in (_OPEN, _STRAIGHT):
        return end
    k = j
    while k < end and depth[k + 1] != 0:
        k += 1
    k = min(end, k + 1)
    if k < end and text[k] in ".;":
        k += 1
    return k


def _quote_depth(text: str) -> list[int]:
    """Quote nesting before each character (index ``len(text)`` = after the last one)."""

    depth = [0] * (len(text) + 1)
    curly, straight = 0, False
    for i, ch in enumerate(text):
        depth[i] = curly + int(straight)
        if ch == _OPEN:
            curly += 1
        elif ch == _CLOSE:
            curly = max(0, curly - 1)
        elif ch == _STRAIGHT:
            straight = not straight
    depth[len(text)] = curly + int(straight)
    return depth


def _mask_quotes(text: str) -> str:
    """Quoted literals ("Thay cụm từ “Điều 3” bằng …") keep their length but name nothing."""

    depth = _quote_depth(text)
    return "".join(
        " " if depth[i] and depth[i + 1] and ch not in (_OPEN, _CLOSE, _STRAIGHT) else ch
        for i, ch in enumerate(text)
    )


def _collapse_quotes(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"“[^”]*”|\"[^\"]*\"", "“…”", text))


def _line_end(text: str, pos: int) -> int:
    end = text.find("\n", pos)
    return len(text) if end < 0 else end


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text or "")
