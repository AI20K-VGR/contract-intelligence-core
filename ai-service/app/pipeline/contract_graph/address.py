"""Vietnamese legal/contract addresses ("điểm c khoản 1 Điều 3") → ``Address``.

Pure and deterministic: NFC + casefold (diacritics kept), then one token regex per level.
Canonical form is shared with the eval gold (``evals/contract_graph/gold.py``): smallest
level first, ASCII level words, leading zeros dropped, the point letter keeps ``đ`` (D12)
and suffixes stay attached (``diem d1``, ``khoan 5a``, ``dieu 30a`` — RT-02). Every level
token ends on ``(?![\\wđ])`` so "điểm d1" is never read as "điểm d", nor "khoản 5a" as
"khoản 5". Annex numbers are arabic (``Phụ lục II`` → ``2``).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field, replace
from typing import Literal

Level = Literal["diem", "khoan", "dieu"]

_RANK = {"diem": 0, "khoan": 1, "dieu": 2, "phu_luc": 3}
_WORD = {"diem": "diem", "khoan": "khoan", "dieu": "dieu", "phu_luc": "phu luc"}
_LEVEL_OF = {"điểm": "diem", "khoản": "khoan", "điều": "dieu"}
_SELF = "này"
_INVALID = "?"  # a level word with a value we cannot read ("điểm b.7"): poisons its address
_END = r"(?![\wđ])"
_POINT = r"[a-zđ]\d*"
_NUMBER = r"\d+[a-zđ]?"
_ATOM = re.compile(
    rf"(?<![\wđ])(?:"
    rf"(?P<level>điểm|khoản|điều)\s+(?:(?P<self>{_SELF})|(?P<value>{_NUMBER}|{_POINT})"
    rf"(?:\.(?P<sub>{_NUMBER}))?){_END}"
    rf"|phụ\s+lục\s+(?:số\s+)?(?P<annex>\d+|[ivx]+){_END}"
    rf"|(?:sửa\s+đổi(?:\s*,\s*bổ\s+sung)?|bổ\s+sung|bãi\s+bỏ|thay\s+thế|thay\s+đổi|điều\s+chỉnh)"
    rf"\s+(?P<major>\d+)\.(?P<minor>{_NUMBER}){_END})"
)
# a bare value continuing a list after one level: "điểm d1, d2", "khoản 1, 2 và 3"
_LIST_NEXT = {
    "diem": re.compile(rf"\s*(?:,|và{_END})\s*(?P<value>{_POINT}){_END}(?!\.\d)"),
    "khoan": re.compile(rf"\s*(?:,|và{_END})\s*(?P<value>{_NUMBER}){_END}(?!\.\d)"),
}
_JOIN_GAP = re.compile(r"\s*(?:(?:của|thuộc)\s+)?")
_SHARE_BREAK = re.compile(r"[.;:\n]")
_INSERT = re.compile(rf"(?<![\wđ])vào(?P<after>\s+sau)?{_END}")
_POINT_VALUE = re.compile(r"([a-zđ])(\d*)")
_NUMBER_VALUE = re.compile(r"(\d+)([a-zđ]?)")
_ROMAN = {
    numeral: str(index)
    for index, numeral in enumerate(
        "i ii iii iv v vi vii viii ix x xi xii xiii xiv xv xvi xvii xviii xix xx".split(), 1
    )
}


@dataclass(frozen=True)
class Address:
    """A target address; ``None`` levels are unknown, never "any".

    ``khoan_options``: the parent item names several clauses ("khoản 1 và khoản 2 Điều 3");
    ``self_level``: "khoản/điểm/Điều này" (coarser levels come from the source node);
    ``insert_after``: the anchor of "… vào sau …" (the new address is this one).
    """

    dieu: str | None = None
    khoan: str | None = None
    diem: str | None = None
    phu_luc: str | None = None
    khoan_options: tuple[str, ...] = ()
    self_level: Level | None = None
    insert_after: Address | None = field(default=None)


@dataclass(frozen=True)
class _Atom:
    start: int
    end: int
    levels: dict[str, str]  # level -> canonical value, or _SELF

    @property
    def finest(self) -> int:
        return min(_RANK[level] for level in self.levels)

    @property
    def coarsest(self) -> int:
        return max(_RANK[level] for level in self.levels)


def normalize(text: str) -> str:
    return unicodedata.normalize("NFC", text or "").casefold()


def parse_addresses(text: str) -> list[Address]:
    """Every target address of one sentence, in text order.

    "Bãi bỏ khoản 3 và khoản 4 Điều 7" → two addresses sharing ``dieu``; "khoản 5 vào sau
    khoản 4 Điều 4" → the new address with ``insert_after`` = the anchor; "điểm đ vào khoản 2
    Điều 3" → the container levels are filled in, no anchor.
    """

    folded = normalize(text)
    atoms = _atoms(folded)
    if not atoms:
        return []
    split = _insert_split(folded, atoms)
    if split is None:
        return _addresses(_shared(folded, _chains(folded, atoms)))
    at, after = split
    new = _chains(folded, [a for a in atoms if a.end <= at.start()])
    rest = _shared(folded, _chains(folded, [a for a in atoms if a.start >= at.end()]))
    target = rest[0]
    # the new addresses borrow their coarser levels from the anchor / container
    filled = _shared(folded, new + [[_Atom(-1, -1, target)]])[:-1]
    if _INVALID in target.values():
        return _addresses(rest[1:])
    anchor = _address(target) if after else None
    out = [replace(addr, insert_after=anchor) for addr in _addresses(filled)]
    return out + _addresses(rest[1:])


def parse_parent_context(text: str) -> Address | None:
    """The scope a parent item hands to its sub-items.

    "một số điểm của khoản 1 và khoản 2 Điều 3" → ``Address(dieu="3", khoan_options=("1",
    "2"))``; "Điều 4" → ``Address(dieu="4")``. Several articles, points or self references
    → ``None`` (a relative sub-item then stays unresolved rather than guessed).
    """

    folded = normalize(text)
    found = _addresses(_shared(folded, _chains(folded, _atoms(folded))))
    if not found:
        return None
    if any(a.diem or a.self_level for a in found):
        return None
    if len({(a.dieu, a.phu_luc) for a in found}) != 1:
        return None
    first = found[0]
    clauses = list(dict.fromkeys(a.khoan for a in found))
    if None in clauses:
        return first if len(found) == 1 else None
    if len(clauses) == 1:
        return Address(dieu=first.dieu, khoan=clauses[0], phu_luc=first.phu_luc)
    return Address(dieu=first.dieu, phu_luc=first.phu_luc, khoan_options=tuple(clauses))


def inherit(child: Address, parent: Address | None) -> Address:
    """Fill the levels coarser than the child's own from the parent item, never overwriting.

    A child that names its article (or annex) or is a self reference is returned unchanged; a
    child without a clause under a multi-clause parent gets ``khoan_options``, not a guess.
    """

    if parent is None or child.self_level or child.dieu or child.phu_luc:
        return child
    filled = replace(child, dieu=parent.dieu, phu_luc=parent.phu_luc)
    if child.khoan is None and not child.khoan_options:
        filled = replace(filled, khoan=parent.khoan, khoan_options=parent.khoan_options)
    if child.insert_after is not None:
        filled = replace(filled, insert_after=inherit(child.insert_after, parent))
    return filled


def canonical(addr: Address) -> str:
    """P1 §3 form, smallest level first; ``insert_after`` and ``khoan_options`` are left out."""

    values = {"diem": addr.diem, "khoan": addr.khoan, "dieu": addr.dieu, "phu_luc": addr.phu_luc}
    if addr.self_level:
        values[addr.self_level] = "nay"
    return " ".join(f"{_WORD[level]} {value}" for level, value in values.items() if value)


def address_levels(addr: Address) -> dict[str, str]:
    """Named levels of ``addr`` (no options/self/anchor), coarse→fine order not implied."""

    values = {"diem": addr.diem, "khoan": addr.khoan, "dieu": addr.dieu, "phu_luc": addr.phu_luc}
    return {level: value for level, value in values.items() if value}


def point_value(raw: str) -> str | None:
    m = _POINT_VALUE.fullmatch(raw)
    return f"{m.group(1)}{int(m.group(2)) if m.group(2) else ''}" if m else None


def number_value(raw: str) -> str | None:
    m = _NUMBER_VALUE.fullmatch(raw)
    return f"{int(m.group(1))}{m.group(2)}" if m else None


def annex_value(raw: str) -> str | None:
    return str(int(raw)) if raw.isdigit() else _ROMAN.get(raw)


def _atoms(folded: str) -> list[_Atom]:
    atoms: list[_Atom] = []
    pos = 0
    while m := _ATOM.search(folded, pos):
        pos = m.end()
        atom = _atom_of(m)
        atoms.append(atom)
        if len(atom.levels) != 1:
            continue
        ((level, own),) = atom.levels.items()
        follow = _LIST_NEXT.get(level)
        if follow is None or own == _SELF:
            continue
        while n := follow.match(folded, pos):
            value = (point_value if level == "diem" else number_value)(n.group("value"))
            if value is None:
                break
            atoms.append(_Atom(n.start("value"), n.end(), {level: value}))
            pos = n.end()
    return atoms


def _atom_of(m: re.Match[str]) -> _Atom:
    if m.group("annex"):
        value = annex_value(m.group("annex"))
        return _Atom(m.start(), m.end(), {"phu_luc": value or _INVALID})
    if m.group("major"):
        minor = number_value(m.group("minor"))
        levels = {"dieu": str(int(m.group("major"))), "khoan": minor or _INVALID}
        return _Atom(m.start("major"), m.end(), levels)
    level = _LEVEL_OF[m.group("level")]
    if m.group("self"):
        return _Atom(m.start(), m.end(), {level: _SELF})
    raw = m.group("value")
    if level == "diem":
        value = point_value(raw) if not m.group("sub") else None
        return _Atom(m.start(), m.end(), {"diem": value or _INVALID})
    value = number_value(raw)
    if value is not None and m.group("sub"):
        # contract numbering: "Điều 5.3" / "khoản 5.3" = clause 3 of article 5
        sub = number_value(m.group("sub"))
        return _Atom(m.start(), m.end(), {"dieu": value, "khoan": sub or _INVALID})
    return _Atom(m.start(), m.end(), {level: value or _INVALID})


def _chains(folded: str, atoms: list[_Atom]) -> list[list[_Atom]]:
    """Group atoms into one address each: a finer→coarser run joined by blanks or "của"."""

    chains: list[list[_Atom]] = []
    for atom in atoms:
        last = chains[-1] if chains else None
        if (
            last is not None
            and _JOIN_GAP.fullmatch(folded, last[-1].end, atom.start)
            and atom.finest > max(a.coarsest for a in last)
        ):
            last.append(atom)
        else:
            chains.append([atom])
    return chains


def _shared(folded: str, chains: list[list[_Atom]]) -> list[dict[str, str]]:
    """Levels per chain; a chain borrows coarser levels from the next one in the same clause
    ("khoản 3 và khoản 4 Điều 7" → both under Điều 7)."""

    merged = [{k: v for a in chain for k, v in a.levels.items()} for chain in chains]
    for i in range(len(merged) - 2, -1, -1):
        gap_start, gap_end = chains[i][-1].end, chains[i + 1][0].start
        if gap_end >= 0 and _SHARE_BREAK.search(folded, gap_start, gap_end):
            continue
        merged[i] = _fill(merged[i], merged[i + 1])
    return merged


def _fill(levels: dict[str, str], donor: dict[str, str]) -> dict[str, str]:
    top = max(_RANK[level] for level in levels)
    extra = {k: v for k, v in donor.items() if _RANK[k] > top and k not in levels}
    return {**levels, **extra}


def _insert_split(folded: str, atoms: list[_Atom]) -> tuple[re.Match[str], bool] | None:
    m = _INSERT.search(folded)
    if m is None:
        return None
    if not any(a.end <= m.start() for a in atoms) or not any(a.start >= m.end() for a in atoms):
        return None
    return m, bool(m.group("after"))


def _addresses(chains: list[dict[str, str]]) -> list[Address]:
    return [_address(levels) for levels in chains if _INVALID not in levels.values()]


def _address(levels: dict[str, str]) -> Address:
    selfs = [level for level, value in levels.items() if value == _SELF]
    self_level = max(selfs, key=_RANK.__getitem__) if selfs else None
    named = {
        level: value
        for level, value in levels.items()
        if value != _SELF and (self_level is None or _RANK[level] < _RANK[self_level])
    }
    return Address(
        dieu=named.get("dieu"),
        khoan=named.get("khoan"),
        diem=named.get("diem"),
        phu_luc=named.get("phu_luc"),
        self_level=self_level,  # type: ignore[arg-type]  # only diem/khoan/dieu take "này"
    )
