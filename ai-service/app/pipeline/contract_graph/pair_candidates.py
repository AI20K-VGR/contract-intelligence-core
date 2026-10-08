"""Deterministic clause-pair candidates for the implicit-relation flow (luồng 2), no LLM.

Four sources propose unordered pairs of eligible nodes (not FIELD/TABLE, text ≥
``MIN_CLAUSE_CHARS``): ``SAME_ARTICLE`` (same Điều or same Phụ lục), ``EXPLICIT_REF`` (an
address in the text resolved ``UNIQUE`` by ``StructureIndex``; addresses into another named
document are dropped — RT-09), ``SAME_KEY`` (same lexicon topic across articles) and
``REFERENCE_CUE`` ("nêu trên", "theo quy định về …" with no number → the nearest preceding
same-topic nodes). Luồng-1 pairs and container pairs never come out. Pairs are scored by their
sources, ordered ``(-score, position(a), position(b))`` and cut at ``top_k``. Pure: no I/O, no
env; frozen once ``PAIRS_TOP_K`` is chosen on dev (``CANDIDATES_VERSION``).
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import Enum

from app.contracts.models import StructuralNode
from app.pipeline.contract_graph import address as _address
from app.pipeline.contract_graph.documents import named_document
from app.pipeline.contract_graph.resolver import Status, StructureIndex, default_target_parts

PAIRS_TOP_K = 40
CONTEXT_CHARS_MAX = 300
MIN_CLAUSE_CHARS = 25
CUE_LOOKBACK = 3
EXTERNAL_WINDOW = 60
CANDIDATES_VERSION = "pairs-cand-v1"

_SKIPPED_TYPES = frozenset({"FIELD", "TABLE"})


class PairSource(str, Enum):
    SAME_ARTICLE = "SAME_ARTICLE"
    EXPLICIT_REF = "EXPLICIT_REF"
    SAME_KEY = "SAME_KEY"
    REFERENCE_CUE = "REFERENCE_CUE"


ALL_SOURCES = frozenset(PairSource)
WEIGHTS = {
    PairSource.EXPLICIT_REF: 4,
    PairSource.REFERENCE_CUE: 3,
    PairSource.SAME_KEY: 2,
    PairSource.SAME_ARTICLE: 1,
}


@dataclass(frozen=True)
class PairCandidate:
    node_a: str  # earlier in document order
    node_b: str
    sources: frozenset[PairSource]
    score: float
    topic: str | None


@dataclass(frozen=True)
class PairCandidateSet:
    candidates: tuple[PairCandidate, ...]
    stats: dict = field(default_factory=dict)


def _fold(text: str) -> str:
    value = unicodedata.normalize("NFD", (text or "").casefold())
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", value.replace("đ", "d"))


# Folded, word-bounded; first match by position wins, ties by this order. "Quyền và nghĩa vụ"
# is deliberately absent: it names who acts, not what about.
_TOPICS: tuple[tuple[str, str], ...] = (
    ("FORCE_MAJEURE", r"bat kha khang"),
    ("PENALTY", r"phat vi pham|phat hop dong|muc phat|tien phat|boi thuong thiet hai"),
    ("PAYMENT", r"thanh toan"),
    ("PRICE", r"gia ca|don gia|gia tri hop dong|gia hang hoa|gia ban|bang gia"),
    ("DELIVERY", r"giao hang|giao nhan|van chuyen|thoi han giao"),
    ("QUALITY", r"chat luong|quy cach|tieu chuan ky thuat"),
    ("WARRANTY", r"bao hanh"),
    ("TERMINATION", r"cham dut|thanh ly hop dong|don phuong|huy bo hop dong"),
    ("TERM", r"hieu luc|thoi han hop dong"),
    ("DISPUTE", r"tranh chap|toa an|trong tai"),
    ("CONFIDENTIALITY", r"bao mat"),
)
_TOPIC_RES = tuple((name, re.compile(rf"\b(?:{pattern})\b")) for name, pattern in _TOPICS)
_TEXT_HEAD = 80

_CUE = re.compile(
    r"\b(?:neu tren|noi tren|ke tren|nhu tren|da neu|quy dinh o tren"
    r"|cac truong hop (?:neu|quy dinh) (?:o )?tren"
    r"|theo (?:quy dinh|thoa thuan) ve (?P<about>[^.;:\n]{1,60})"
    r"|tai phu luc(?! (?:so )?(?:\d|[ivx]+\b)))"
)
_EXTERNAL = re.compile(r"\b(?:bo luat|luat|nghi dinh|thong tu|quyet dinh|phap lenh|nghi quyet)\b")
_SENTENCE = re.compile(r"[^.;\n]+")
_ARTICLE_LABEL = re.compile(r"^(?:dieu|phu luc)\b")


def topic_of(context: str, text: str) -> str | None:
    """Lexicon topic of the inherited context (headings first), else of the clause head."""

    for chunk in (context or "", (text or "")[:_TEXT_HEAD]):
        found = _first_topic(_fold(chunk))
        if found is not None:
            return found
    return None


def _first_topic(folded: str) -> str | None:
    best: tuple[int, int, str] | None = None
    for rank, (name, pattern) in enumerate(_TOPIC_RES):
        m = pattern.search(folded)
        if m is not None and (best is None or (m.start(), rank) < best[:2]):
            best = (m.start(), rank, name)
    return best[2] if best else None


def clause_context(
    index: StructureIndex, nodes_by_id: Mapping[str, StructuralNode], node_id: str
) -> str:
    """Article/annex headings above ``node_id`` + its container's lead (before the last ``:``),
    coarse → fine, never the node's own text; at most ``CONTEXT_CHARS_MAX`` characters."""

    return _context(_containers(index, nodes_by_id), nodes_by_id, node_id)


def _context(
    chains: Mapping[str, tuple[str, ...]], nodes_by_id: Mapping[str, StructuralNode], node_id: str
) -> str:
    chain = chains.get(node_id, ())
    parts = [_heading(nodes_by_id[c]) for c in chain if _is_heading(nodes_by_id[c])]
    if chain and not _is_heading(nodes_by_id[chain[-1]]):
        lead = _lead(nodes_by_id[chain[-1]].text)
        if lead:
            parts.append(lead)
    return " · ".join(p for p in parts if p)[:CONTEXT_CHARS_MAX]


def generate_pair_candidates(
    index: StructureIndex,
    nodes: Iterable[StructuralNode],
    *,
    excluded_pairs: frozenset = frozenset(),
    top_k: int = PAIRS_TOP_K,
    sources: frozenset[PairSource] = ALL_SOURCES,
) -> PairCandidateSet:
    by_id = {n.node_id: n for n in nodes}
    ordered = sorted(by_id, key=lambda nid: (index.position(nid), nid))
    stats: Counter[str] = Counter()
    eligible: list[str] = []
    for nid in ordered:
        node = by_id[nid]
        if node.type in _SKIPPED_TYPES:
            continue
        if len((node.text or "").strip()) < MIN_CLAUSE_CHARS:
            stats["excluded_short"] += 1
            continue
        eligible.append(nid)
    eligible_set = set(eligible)
    chains = _containers(index, by_id)
    topics = {nid: topic_of(_context(chains, by_id, nid), by_id[nid].text) for nid in eligible}
    articles = {nid: _article_key(index, chains, nid) for nid in eligible}
    pos = {nid: index.position(nid) for nid in eligible}
    found: dict[tuple[str, str], set[PairSource]] = {}
    adjacent: set[tuple[str, str]] = set()

    def add(x: str, y: str, source: PairSource) -> None:
        if source not in sources or x == y:
            return
        found.setdefault(_ordered(x, y, pos), set()).add(source)

    if PairSource.SAME_ARTICLE in sources:
        groups: dict[tuple[str, str], list[str]] = {}
        for nid in eligible:
            if articles[nid] is not None:
                groups.setdefault(articles[nid], []).append(nid)
        for members in groups.values():
            for i, x in enumerate(members):
                for y in members[i + 1:]:
                    add(x, y, PairSource.SAME_ARTICLE)
            adjacent.update(_ordered(x, y, pos) for x, y in zip(members, members[1:]))
    if PairSource.EXPLICIT_REF in sources:
        for nid in eligible:
            for target in _explicit_targets(index, by_id[nid], stats):
                if target in eligible_set:
                    add(nid, target, PairSource.EXPLICIT_REF)
    if PairSource.SAME_KEY in sources:
        by_topic: dict[str, list[str]] = {}
        for nid in eligible:
            if topics[nid] is not None:
                by_topic.setdefault(topics[nid], []).append(nid)
        for members in by_topic.values():
            for i, x in enumerate(members):
                for y in members[i + 1:]:
                    if articles[x] is None or articles[x] != articles[y]:
                        add(x, y, PairSource.SAME_KEY)
    if PairSource.REFERENCE_CUE in sources:
        for i, nid in enumerate(eligible):
            topic = _cue_topic(by_id[nid].text, topics[nid])
            if topic is None:
                continue
            earlier = [e for e in reversed(eligible[:i]) if topics[e] == topic]
            for target in earlier[:CUE_LOOKBACK]:
                add(target, nid, PairSource.REFERENCE_CUE)

    excluded = {tuple(sorted(p)) for p in excluded_pairs}
    candidates: list[PairCandidate] = []
    for (a, b), srcs in found.items():
        if tuple(sorted((a, b))) in excluded:
            stats["excluded_luong1"] += 1
            continue
        if _nested(index, a, b):
            stats["excluded_ancestor"] += 1
            continue
        score = sum(WEIGHTS[s] for s in srcs)
        score += 1 if PairSource.SAME_ARTICLE in srcs and (a, b) in adjacent else 0
        score += 1 if _body_annex(index, a, b) else 0
        topic = topics[a] if topics[a] == topics[b] else None
        candidates.append(PairCandidate(a, b, frozenset(srcs), float(score), topic))
    candidates.sort(key=lambda c: (-c.score, pos[c.node_a], pos[c.node_b], c.node_a, c.node_b))
    kept = candidates[: max(0, top_k)]
    by_source = Counter(s.value for c in candidates for s in c.sources)
    out = {
        "candidates_total": len(candidates),
        "candidates_by_source": dict(sorted(by_source.items())),
        "excluded_luong1": stats["excluded_luong1"],
        "excluded_ancestor": stats["excluded_ancestor"],
        "excluded_short": stats["excluded_short"],
        "excluded_external_ref": stats["excluded_external_ref"],
        "candidates_capped": len(candidates) - len(kept),
        "candidates_kept": len(kept),
    }
    return PairCandidateSet(tuple(kept), out)


# -- sources -----------------------------------------------------------------------------------


def _explicit_targets(index: StructureIndex, node: StructuralNode, stats: Counter[str]) -> list[str]:
    targets: list[str] = []
    for m in _SENTENCE.finditer(node.text or ""):
        sentence = m.group(0)
        for addr, end in _addresses_with_end(sentence):
            if addr.self_level:
                continue
            tail = _fold(_address.normalize(sentence)[end:end + EXTERNAL_WINDOW])
            if named_document(sentence) is not None or _EXTERNAL.search(tail):
                stats["excluded_external_ref"] += 1
                continue
            parts = default_target_parts(index, node.node_id, addr)
            res = index.resolve(addr, parts=parts, source_node_id=node.node_id)
            if res.status == Status.UNIQUE and res.node_id and res.node_id != node.node_id:
                targets.append(res.node_id)
    return targets


def _addresses_with_end(sentence: str) -> list[tuple[_address.Address, int]]:
    """Addresses of one sentence with the end offset of each in the normalized text; references
    are never insertions, so the ``vào sau`` split of ``parse_addresses`` does not apply."""

    folded = _address.normalize(sentence)
    chains = _address._chains(folded, _address._atoms(folded))
    merged = _address._shared(folded, chains)
    return [
        (_address._address(levels), chain[-1].end)
        for chain, levels in zip(chains, merged)
        if _address._INVALID not in levels.values()
    ]


def _cue_topic(text: str | None, own_topic: str | None) -> str | None:
    for m in _SENTENCE.finditer(text or ""):
        sentence = m.group(0)
        cue = _CUE.search(_fold(sentence))
        if cue is None or _address.parse_addresses(sentence):
            continue
        about = cue.group("about")
        named = _first_topic(about) if about else None
        return named or own_topic
    return None


# -- structure helpers -------------------------------------------------------------------------


def _ordered(x: str, y: str, pos: Mapping[str, int]) -> tuple[str, str]:
    return (x, y) if (pos[x], x) < (pos[y], y) else (y, x)


def _nested(index: StructureIndex, a: str, b: str) -> bool:
    (a0, a1), (b0, b1) = index.span(a), index.span(b)
    return a0 <= b0 <= a1 or b0 <= a0 <= b1


def _body_annex(index: StructureIndex, a: str, b: str) -> bool:
    pa, pb = index.part_of(a) or "", index.part_of(b) or ""
    return pa.startswith("annex:") != pb.startswith("annex:")


def _article_key(
    index: StructureIndex, chains: Mapping[str, tuple[str, ...]], nid: str
) -> tuple[str, str] | None:
    """Same-article grouping key: ``(part, dieu)``, or ``(annex part, "")`` for a whole Phụ lục."""

    part = index.part_of(nid)
    if part is None:
        return None
    if part.startswith("annex:"):
        return (part, "")
    for c in (nid, *reversed(chains.get(nid, ()))):
        levels = index.levels_of(c)
        if levels and "dieu" in levels:
            return (part, levels["dieu"])
    return None


def _containers(
    index: StructureIndex, by_id: Mapping[str, StructuralNode]
) -> dict[str, tuple[str, ...]]:
    """Coarse → fine chain of nodes whose subtree (``index.span``) holds each node."""

    ordered = sorted(by_id, key=lambda nid: (index.position(nid), nid))
    stack: list[str] = []
    chains: dict[str, tuple[str, ...]] = {}
    for nid in ordered:
        start = index.position(nid)
        while stack and index.span(stack[-1])[1] < start:
            stack.pop()
        chains[nid] = tuple(stack)
        stack.append(nid)
    return chains


def _is_heading(node: StructuralNode) -> bool:
    return bool(_ARTICLE_LABEL.match(_fold((node.raw_label or "").strip())))


def _heading(node: StructuralNode) -> str:
    label = (node.raw_label or "").strip()
    first = next((line.strip() for line in (node.text or "").splitlines() if line.strip()), "")
    if not first or _fold(first).startswith(_fold(label)):
        return first or label
    return f"{label}. {first}"


def _lead(text: str | None) -> str:
    text = (text or "").strip()
    return text[: text.rfind(":")].strip() if ":" in text else ""

