"""Resolve an ``Address`` to an existing structural node; never creates one.

``StructureIndex.build`` gives every addressable node an address from its label and its
parent chain (sequential context in the same part when the chain has none). A *part* is
``body:<source_file_id>``, ``annex:<node_id>`` (subtree of an annex heading) or
``annex:file:<source_file_id>`` (a file with role ``annex`` and no annex heading).

``resolve`` answers ``UNIQUE`` / ``AMBIGUOUS(candidates)`` / ``NOT_FOUND``. Falling back to
the nearest existing ancestor (``ANCESTOR``) needs the missing labels at line starts in the
ancestor text; an INSERTION resolves to its container, never to its anchor, and an
insertion whose new address equals its anchor is ``NOT_FOUND`` (RT-02).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import TYPE_CHECKING

from app.pipeline.contract_graph.address import (
    Address,
    address_levels,
    annex_value,
    canonical,
    normalize,
    number_value,
    point_value,
)

if TYPE_CHECKING:
    from app.contracts.models import StructuralNode


class Status(StrEnum):
    UNIQUE = "UNIQUE"
    AMBIGUOUS = "AMBIGUOUS"
    NOT_FOUND = "NOT_FOUND"


class Method(StrEnum):
    EXACT = "EXACT"
    ANCESTOR = "ANCESTOR"
    SELF = "SELF"
    ORDER_INFERENCE = "ORDER_INFERENCE"


@dataclass(frozen=True)
class Resolution:
    status: Status
    node_id: str | None = None
    candidates: tuple[str, ...] = ()
    method: Method | None = None
    canonical: str | None = None
    residual: tuple[str, ...] = ()  # levels missing below ``node_id``, finest first ("diem c",)


_FINE_TO_COARSE = ("diem", "khoan", "dieu")
_RANK = {"diem": 0, "khoan": 1, "dieu": 2}
_SKIPPED_TYPES = frozenset({"FIELD", "TABLE"})
_ANNEX_LABEL = re.compile(r"phụ\s+lục(?:\s+(?:số\s+)?(\d+|[ivx]+))?(?![\wđ])")
_ARTICLE_LABEL = re.compile(r"(?:điều|article)\s+(\d+[a-zđ]?)(?:\.(\d+[a-zđ]?))?(?![\wđ])")
_DOTTED_LABEL = re.compile(r"(\d+[a-zđ]?)\.(\d+[a-zđ]?)(?![\wđ])")
_CLAUSE_LABEL = re.compile(r"(?:khoản\s+(\d+[a-zđ]?)(?![\wđ])|(\d+[a-zđ]?)\.(?!\d))")
_POINT_LABEL = re.compile(r"(?:điểm\s+([a-zđ]\d*)(?![\wđ])|\(([a-zđ]\d*)\)|([a-zđ]\d*)\))")
# a line opening any unit of that level: the end of the scope of the previous one
_ANY_LINE_LABEL = {
    "dieu": re.compile(r"điều\s+\d"),
    "khoan": re.compile(r"(?:khoản\s+)?\d+[a-zđ]?\.(?!\d)"),
    "diem": re.compile(r"(?:điểm\s+[a-zđ]\d*(?![\wđ])|\(?[a-zđ]\d*\))"),
}

Key = tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class _Entry:
    part: str
    levels: dict[str, str] | None  # None: not addressable; {} : annex heading
    up: str | None  # parent in the input, else the sequential context node


class StructureIndex:
    """Address → node ids per part, built once from the evidence nodes of one dossier."""

    def __init__(
        self,
        entries: dict[str, _Entry],
        positions: dict[str, int],
        texts: dict[str, str],
        annex_numbers: dict[str, str | None],
        roles: Mapping[str, str],
    ) -> None:
        self._entries = entries
        self._positions = positions
        self._texts = texts
        self._annex_numbers = annex_numbers
        self._roles = dict(roles)
        self._by_key: dict[tuple[str, Key], list[str]] = {}
        self._ends = dict(positions)  # last position inside each node's subtree
        for node_id in sorted(entries, key=positions.__getitem__):
            entry = entries[node_id]
            if entry.levels is not None:
                self._by_key.setdefault((entry.part, _key(entry.levels)), []).append(node_id)
            seen = {node_id}
            walk = entry.up
            while walk is not None and walk in entries and walk not in seen:
                self._ends[walk] = max(self._ends[walk], positions[node_id])
                seen.add(walk)
                walk = entries[walk].up

    @classmethod
    def build(cls, nodes: Iterable[StructuralNode], roles: Mapping[str, str]) -> StructureIndex:
        ordered = sorted(nodes, key=lambda n: (n.source_file_id or "", n.order, n.node_id))
        by_id = {node.node_id: node for node in ordered}
        entries: dict[str, _Entry] = {}
        annex_numbers: dict[str, str | None] = {}
        # sequential context per part: (last article node, last clause node)
        sequence: dict[str, tuple[str | None, str | None]] = {}

        def visit(node: StructuralNode, trail: frozenset[str]) -> _Entry:
            if node.node_id in entries:
                return entries[node.node_id]
            parent_id = node.parent_id if node.parent_id in by_id else None
            parent = None
            if parent_id is not None and parent_id not in trail:
                parent = visit(by_id[parent_id], trail | {node.node_id})
            kind, own = _label(node)
            file_id = node.source_file_id or ""
            if kind == "annex":
                part = f"annex:{node.node_id}"
                annex_numbers[part] = own.get("phu_luc")
                sequence[part] = (None, None)
                sequence[f"body:{file_id}"] = (None, None)  # body numbering stops here
                entry = _Entry(part, {}, parent_id)
            else:
                if parent is not None:
                    part = parent.part
                elif roles.get(file_id) == "annex":
                    part = f"annex:file:{file_id}"
                else:
                    part = f"body:{file_id}"
                if part.startswith("annex:file:"):
                    annex_numbers.setdefault(part, None)
                levels, context = _place(kind, own, parent_id, entries, sequence.get(part))
                entry = _Entry(part, levels, parent_id or context)
                article, _ = sequence.get(part, (None, None))
                if node.type in _SKIPPED_TYPES:
                    entry = replace(entry, levels=None)  # never a target, never a context
                elif kind == "article":
                    sequence[part] = (node.node_id, None)
                elif kind == "clause" and levels is not None:
                    sequence[part] = (article, node.node_id)
            entries[node.node_id] = entry
            return entry

        for node in ordered:
            visit(node, frozenset())
        positions = {node.node_id: pos for pos, node in enumerate(ordered)}
        texts = {node.node_id: node.text or "" for node in ordered}
        return cls(entries, positions, texts, annex_numbers, roles)

    # -- read API ---------------------------------------------------------------------------

    def node_ids(self) -> list[str]:
        return sorted(self._entries, key=self._positions.__getitem__)

    def parts(self) -> set[str]:
        return {entry.part for entry in self._entries.values()}

    def part_of(self, node_id: str) -> str | None:
        entry = self._entries.get(node_id)
        return entry.part if entry else None

    def position(self, node_id: str) -> int:
        return self._positions[node_id]

    def span(self, node_id: str) -> tuple[int, int]:
        """First and last position of the node's subtree."""

        return self._positions[node_id], self._ends[node_id]

    def levels_of(self, node_id: str) -> dict[str, str] | None:
        entry = self._entries.get(node_id)
        return dict(entry.levels) if entry and entry.levels is not None else None

    def canonical_of(self, node_id: str) -> str | None:
        levels = self.levels_of(node_id)
        if levels is None:
            return None
        return canonical(
            Address(**levels, phu_luc=self._annex_numbers.get(self._entries[node_id].part))
        )

    def has_body_role(self) -> bool:
        return "body" in self._roles.values()

    def body_parts(self) -> set[str]:
        bodies = {p for p in self.parts() if p.startswith("body:")}
        if self.has_body_role():
            return {p for p in bodies if self._roles.get(p.removeprefix("body:")) == "body"}
        return bodies

    def annex_parts(self) -> set[str]:
        return {p for p in self.parts() if p.startswith("annex:")}

    # -- resolution -------------------------------------------------------------------------

    def resolve(
        self,
        addr: Address,
        *,
        parts: Iterable[str],
        source_node_id: str | None = None,
        require_existing: bool = True,
    ) -> Resolution:
        """``require_existing=False`` marks an INSERTION: the answer is its container."""

        parts = set(parts)
        if addr.self_level:
            return self._resolve_self(addr, source_node_id)
        if addr.insert_after is not None and canonical(addr) == canonical(addr.insert_after):
            return Resolution(
                Status.NOT_FOUND, canonical=canonical(addr), residual=("insert_equals_anchor",)
            )
        if not (addr.dieu or addr.phu_luc):
            return Resolution(Status.NOT_FOUND, canonical=canonical(addr) or None)
        if addr.khoan is None and addr.khoan_options:
            return self._resolve_options(addr, parts, source_node_id, require_existing)
        if addr.insert_after is not None or not require_existing:
            return self._resolve_insertion(addr, parts, source_node_id)
        return self._resolve_existing(addr, parts, source_node_id)

    def _resolve_options(
        self, addr: Address, parts: set[str], source: str | None, require_existing: bool
    ) -> Resolution:
        results = [
            self.resolve(
                _with_clause(addr, option),
                parts=parts,
                source_node_id=source,
                require_existing=require_existing,
            )
            for option in addr.khoan_options
        ]
        found = [r for r in results if r.status != Status.NOT_FOUND]
        if not found:
            return Resolution(Status.NOT_FOUND, canonical=canonical(addr))
        if len(found) == 1 and found[0].status == Status.UNIQUE:
            return found[0]
        candidates: list[str] = []
        for r in found:
            ids = (r.node_id,) if r.status == Status.UNIQUE else r.candidates
            candidates += [i for i in ids if i is not None and i not in candidates]
        return Resolution(Status.AMBIGUOUS, candidates=tuple(candidates), canonical=canonical(addr))

    def _resolve_insertion(self, addr: Address, parts: set[str], source: str | None) -> Resolution:
        new = canonical(addr)
        if addr.insert_after is not None:
            anchor = self._resolve_existing(addr.insert_after, parts, source)
            if anchor.status == Status.NOT_FOUND:
                return Resolution(Status.NOT_FOUND, canonical=new, residual=("anchor_not_found",))
            if anchor.status == Status.AMBIGUOUS:
                return Resolution(Status.AMBIGUOUS, candidates=anchor.candidates, canonical=new)
        levels = address_levels(addr)
        levels.pop("phu_luc", None)
        finest = min(levels, key=_RANK.__getitem__) if levels else None
        container = {k: v for k, v in levels.items() if k != finest}
        if not container and not (addr.phu_luc and levels):
            # a new article / annex: its container is the document part, no node to point at
            if not parts:
                return Resolution(Status.NOT_FOUND, canonical=new)
            return Resolution(Status.UNIQUE, method=Method.EXACT, canonical=new)
        found = self._resolve_existing(Address(**container, phu_luc=addr.phu_luc), parts, source)
        return replace(found, canonical=new)

    def _resolve_existing(self, addr: Address, parts: set[str], source: str | None) -> Resolution:
        want = address_levels(addr)
        want.pop("phu_luc", None)
        scoped = self._parts_for(addr, parts)
        full = canonical(replace(addr, khoan_options=(), insert_after=None))
        hits = self._lookup(scoped, want, source)
        if hits:
            return _answer(hits, Method.EXACT, full, ())
        residual: list[tuple[str, str]] = []
        for level in _FINE_TO_COARSE:
            if level not in want:
                continue
            residual.append((level, want.pop(level)))
            if not want and not addr.phu_luc:
                break
            hits = self._lookup(scoped, want, source)
            if hits:
                proven = [h for h in hits if self._labels_in_text(h, residual)]
                if not proven:
                    break
                labels = tuple(f"{lv} {v}" for lv, v in residual)
                return _answer(proven, Method.ANCESTOR, full, labels)
        return Resolution(Status.NOT_FOUND, canonical=full)

    def _resolve_self(self, addr: Address, source: str | None) -> Resolution:
        node_id = source if source in self._entries else None
        while node_id is not None:
            levels = self._entries[node_id].levels
            if levels and min(levels, key=_RANK.__getitem__) == addr.self_level:
                break
            node_id = self._entries[node_id].up
        if node_id is None:
            return Resolution(Status.NOT_FOUND, canonical=canonical(addr))
        finer = {
            k: v
            for k, v in address_levels(addr).items()
            if k in _RANK and _RANK[k] < _RANK[addr.self_level]
        }
        if not finer:
            return Resolution(
                Status.UNIQUE,
                node_id=node_id,
                method=Method.SELF,
                canonical=self.canonical_of(node_id),
            )
        part = self._entries[node_id].part
        target = Address(
            **{**self._entries[node_id].levels, **finer}, phu_luc=self._annex_numbers.get(part)
        )
        return self._resolve_existing(target, {part}, source)

    def _parts_for(self, addr: Address, parts: set[str]) -> set[str]:
        if addr.phu_luc:
            return {p for p in parts if self._annex_numbers.get(p) == addr.phu_luc}
        return parts

    def _lookup(self, parts: set[str], levels: dict[str, str], source: str | None) -> list[str]:
        key = _key(levels)
        hits = [n for part in sorted(parts) for n in self._by_key.get((part, key), [])]
        if source is not None:
            hits = [n for n in hits if not self._within(n, source)]
        return sorted(hits, key=self._positions.__getitem__)

    def _within(self, node_id: str, ancestor: str) -> bool:
        seen: set[str] = set()
        walk: str | None = node_id
        while walk is not None and walk not in seen:
            if walk == ancestor:
                return True
            seen.add(walk)
            walk = self._entries[walk].up if walk in self._entries else None
        return False

    def _labels_in_text(self, node_id: str, residual: list[tuple[str, str]]) -> bool:
        """Each missing level opens a line of the ancestor text, nested coarse → fine."""

        lines = [normalize(line).strip() for line in self._texts.get(node_id, "").splitlines()]
        start, end = 0, len(lines)
        for level, value in reversed(residual):
            own = _line_label(level, value)
            at = next((i for i in range(start, end) if own.match(lines[i])), None)
            if at is None:
                return False
            stop = [
                i
                for i in range(at + 1, end)
                if any(
                    _ANY_LINE_LABEL[lv].match(lines[i])
                    for lv in _FINE_TO_COARSE
                    if _RANK[lv] >= _RANK[level]
                )
            ]
            start, end = at + 1, stop[0] if stop else end
        return True


def default_target_parts(
    index: StructureIndex, source_node_id: str | None, addr: Address
) -> set[str]:
    """Where an address written in ``source_node_id`` may point when it names no document.

    Annex address → annex parts; source in an annex → the body (files with role ``body``, or
    every part not holding the source when no file has a role); source in the body → its own
    part (``resolve`` then excludes the source subtree).
    """

    if addr.phu_luc:
        return index.annex_parts()
    part = index.part_of(source_node_id) if source_node_id else None
    if part is None:
        return index.body_parts()
    if part.startswith("annex:"):
        if index.has_body_role():
            return index.body_parts()
        return {p for p in index.parts() if p != part}
    return {part}


def disambiguate_by_order(
    resolutions: Sequence[Resolution], index: StructureIndex
) -> list[Resolution]:
    """Sub-items of one multi-clause parent, in amending-text order.

    A candidate is locked when it is the only choice left for its item in every assignment
    whose target positions are non-decreasing (``UNIQUE`` siblings are fixed points). A target
    that is the node itself sits at the node position; a target inside a node (an insertion
    container, an ancestor with residual labels) may sit anywhere in that node's subtree. The
    "listed in source order" premise is an assumption: the result is ``ORDER_INFERENCE``.
    """

    slots: list[tuple[int, list[tuple[str, int, int]]]] = []
    for i, res in enumerate(resolutions):
        if res.status == Status.UNIQUE and res.node_id is not None:
            slots.append((i, [_interval(res, res.node_id, index)]))
        elif res.status == Status.AMBIGUOUS and len(set(res.candidates)) > 1:
            ids = dict.fromkeys(res.candidates)
            slots.append((i, [_interval(res, c, index) for c in ids]))
    lows: list[float] = []
    low = float("-inf")
    for _, options in slots:
        reachable = [max(lo, low) for _, lo, hi in options if hi >= low]
        if not reachable:
            return list(resolutions)  # the order premise does not hold here: decide nothing
        low = min(reachable)
        lows.append(low)
    highs: list[float] = [0.0] * len(slots)
    high = float("inf")
    for k in range(len(slots) - 1, -1, -1):
        high = max(min(hi, high) for _, lo, hi in slots[k][1] if lo <= high)
        highs[k] = high
    out = list(resolutions)
    for k, (i, options) in enumerate(slots):
        res = resolutions[i]
        if res.status != Status.AMBIGUOUS:
            continue
        before = lows[k - 1] if k else float("-inf")
        after = highs[k + 1] if k + 1 < len(slots) else float("inf")
        feasible = [c for c, lo, hi in options if max(lo, before) <= min(hi, after)]
        if len(feasible) == 1:
            out[i] = _locked(res, feasible[0], index) or res
    return out


def _interval(res: Resolution, node_id: str, index: StructureIndex) -> tuple[str, int, int]:
    first, last = index.span(node_id)
    node_levels = index.levels_of(node_id) or {}
    asked = _levels_of_canonical(res.canonical or "")
    asked.pop("phu_luc", None)
    if res.residual or any(k not in node_levels for k in asked):
        return node_id, first, last
    return node_id, first, first


def _locked(res: Resolution, node_id: str, index: StructureIndex) -> Resolution | None:
    node_levels = index.levels_of(node_id) or {}
    asked = _levels_of_canonical(res.canonical or "")
    if "khoan" not in asked and "khoan" not in node_levels and "diem" in asked:
        return None  # the clause that was ambiguous is still not named by this node
    merged = {**asked, **node_levels}
    residual = tuple(
        f"{lv} {merged[lv]}" for lv in _FINE_TO_COARSE if lv in merged and lv not in node_levels
    )
    return Resolution(
        Status.UNIQUE,
        node_id=node_id,
        method=Method.ORDER_INFERENCE,
        canonical=canonical(Address(**merged)),
        residual=residual,
    )


def _answer(hits: list[str], method: Method, full: str, residual: tuple[str, ...]) -> Resolution:
    if len(hits) == 1:
        return Resolution(
            Status.UNIQUE, node_id=hits[0], method=method, canonical=full, residual=residual
        )
    return Resolution(Status.AMBIGUOUS, candidates=tuple(hits), canonical=full, residual=residual)


def _with_clause(addr: Address, clause: str) -> Address:
    anchor = addr.insert_after
    if anchor is not None and anchor.khoan is None and anchor.khoan_options:
        anchor = replace(anchor, khoan=clause, khoan_options=())
    return replace(addr, khoan=clause, khoan_options=(), insert_after=anchor)


def _key(levels: Mapping[str, str]) -> Key:
    return tuple(sorted((k, v) for k, v in levels.items() if k in _RANK))


def _levels_of_canonical(text: str) -> dict[str, str]:
    words = text.split()
    out: dict[str, str] = {}
    i = 0
    while i + 1 < len(words):
        if words[i] == "phu" and i + 2 < len(words):
            out["phu_luc"] = words[i + 2]
            i += 3
        else:
            out[words[i]] = words[i + 1]
            i += 2
    return out


def _line_label(level: str, value: str) -> re.Pattern[str]:
    v = re.escape(value)
    if level == "dieu":
        return re.compile(rf"điều\s+{v}(?![\wđ])")
    if level == "khoan":
        return re.compile(rf"(?:khoản\s+{v}(?![\wđ])|{v}\.(?!\d))")
    return re.compile(rf"(?:điểm\s+{v}(?![\wđ])|\(?{v}\))")


def _label(node: StructuralNode) -> tuple[str | None, dict[str, str]]:
    label = normalize(node.raw_label).strip()
    m = _ANNEX_LABEL.match(label)
    if node.structure_level == "ANNEX" or m:
        number = annex_value(m.group(1)) if m and m.group(1) else None
        return "annex", ({"phu_luc": number} if number else {})
    if m := _ARTICLE_LABEL.match(label):
        dieu = number_value(m.group(1))
        khoan = number_value(m.group(2)) if m.group(2) else None
        if dieu is None or (m.group(2) and khoan is None):
            return None, {}
        return "article", ({"dieu": dieu, "khoan": khoan} if khoan else {"dieu": dieu})
    if m := _DOTTED_LABEL.match(label):
        dieu, khoan = number_value(m.group(1)), number_value(m.group(2))
        return ("article", {"dieu": dieu, "khoan": khoan}) if dieu and khoan else (None, {})
    if m := _CLAUSE_LABEL.match(label):
        khoan = number_value(m.group(1) or m.group(2))
        return ("clause", {"khoan": khoan}) if khoan else (None, {})
    if m := _POINT_LABEL.match(label):
        diem = point_value(m.group(1) or m.group(2) or m.group(3))
        return ("point", {"diem": diem}) if diem else (None, {})
    return None, {}


def _place(
    kind: str | None,
    own: dict[str, str],
    parent_id: str | None,
    entries: dict[str, _Entry],
    sequence: tuple[str | None, str | None] | None,
) -> tuple[dict[str, str] | None, str | None]:
    """(levels, sequential context node) of a non-annex node."""

    if kind == "article":
        return dict(own), None
    if kind not in ("clause", "point"):
        return None, None
    own_rank = _RANK["khoan" if kind == "clause" else "diem"]
    context = _addressable_ancestor(parent_id, entries)
    via_sequence = None
    if context is None and sequence is not None:
        article, clause = sequence
        via_sequence = clause if kind == "point" and clause else article
        context = entries[via_sequence].levels if via_sequence in entries else None
    if context is None:
        return None, None
    if context and min(_RANK[k] for k in context) <= own_rank:
        return None, None  # "1." under a clause is sub-numbering, not a clause of the article
    if not context and parent_id is None and via_sequence is None:
        return None, None
    return {**context, **own}, via_sequence


def _addressable_ancestor(
    parent_id: str | None, entries: dict[str, _Entry]
) -> dict[str, str] | None:
    seen: set[str] = set()
    walk = parent_id
    while walk is not None and walk in entries and walk not in seen:
        levels = entries[walk].levels
        if levels is not None:
            return levels
        seen.add(walk)
        walk = entries[walk].up
    return None
