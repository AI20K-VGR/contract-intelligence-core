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

import math
import re
import unicodedata
from collections import Counter, deque
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
CANDIDATES_VERSION = "pairs-cand-v6"

_SKIPPED_TYPES = frozenset({"FIELD", "TABLE"})


class PairSource(str, Enum):
    SAME_ARTICLE = "SAME_ARTICLE"
    EXPLICIT_REF = "EXPLICIT_REF"
    SAME_KEY = "SAME_KEY"
    REFERENCE_CUE = "REFERENCE_CUE"
    VALUE_MISMATCH = "VALUE_MISMATCH"
    STRUCTURED_KEY = "STRUCTURED_KEY"
    VERBATIM = "VERBATIM"  # same text once numbering is stripped, anywhere in the dossier


ALL_SOURCES = frozenset(PairSource)
# VERBATIM is core: a repeated clause is rare and is exactly what the cap must not drop.
_CORE_SOURCES = frozenset({PairSource.SAME_ARTICLE, PairSource.EXPLICIT_REF, PairSource.STRUCTURED_KEY,
                           PairSource.VERBATIM})
_BASE_CORE_SOURCES = frozenset({PairSource.SAME_ARTICLE, PairSource.EXPLICIT_REF})
_CORE_TOP_K_SHARE = 1.0
WEIGHTS = {
    PairSource.EXPLICIT_REF: 4,
    PairSource.REFERENCE_CUE: 3,
    PairSource.SAME_KEY: 2,
    PairSource.SAME_ARTICLE: 1,
    PairSource.VALUE_MISMATCH: 3,
    PairSource.STRUCTURED_KEY: 8,
    PairSource.VERBATIM: 4,
}

_VALUE_WITH_UNIT = re.compile(r"(?<!\w)(\d+(?:[.,]\d+)*)(?!\w)\s*(%|[a-z]+)?")
# Folded clause numbering / addresses: "2.1. ...", "khoan 1 dieu 6", "phu luc 01" are positions,
# not values; counting them made every two clauses citing different articles a "mismatch".
_CLAUSE_NUMBERING = re.compile(r"^\s*\d+(?:\.\d+)*\.?\s+")
_CLAUSE_ADDRESS = re.compile(r"\b(?:khoan|diem|dieu|muc|chuong|phu luc)\s+[\w.]+")
# Near-verbatim clauses (token Jaccard) are duplicate/conflict suspects regardless of source.
_NEAR_DUPLICATE_JACCARD = 0.85
_NEAR_DUPLICATE_BONUS = 2
# A line repeated on several pages of one file is page furniture (header/footer).
_FURNITURE_MIN_PAGES = 2
_FURNITURE_EDGE_LINES = 5
# SAME_ARTICLE/SAME_KEY pair each member only with its next N group members. Small groups
# are unchanged; a flat 10k-block article no longer yields O(k^2) pairs before top-K.
_GROUP_PAIR_WINDOW = 12
_CONTENT_WORD = re.compile(r"\b[a-z]{3,}\b")
# A pair found only because both clauses sit in one article is sent to the classifier only
# with a sign the two are about the same thing. Tuned on fixtures/seeded/pruning_set (dev),
# checked on its held-out dossiers: 0 gold relations lost, ~1/3 of the pairs cut.
_SAME_ARTICLE_MIN_JACCARD = 0.2
_SAME_ARTICLE_SHORT_CHARS = 30  # a heading or a wrapped fragment pairs with its body
_LEADING_NUMBER = re.compile(r"^\s*(\d+(?:\.\d+)*)\.?\s")
_VALUE_MISMATCH_MIN_SHARED = 4
_VALUE_MISMATCH_MIN_JACCARD = 0.12
VALUE_MISMATCH_POSTING_WINDOW = 8
_VALUE_STOPWORDS = frozenset({
    "ben", "cac", "cho", "cua", "duoc", "khi", "mot", "nay", "nguoi", "nhan",
    "sau", "theo", "trong", "tu", "voi", "va", "ve", "tai", "thoi", "han",
})


@dataclass(frozen=True)
class PairCandidate:
    node_a: str  # earlier in document order
    node_b: str
    sources: frozenset[PairSource]
    score: float
    topic: str | None
    referrer: str | None = None  # the node whose "khoản X Điều Y" resolved to the other one


@dataclass(frozen=True)
class PairCandidateSet:
    candidates: tuple[PairCandidate, ...]
    stats: dict = field(default_factory=dict)


def _window(members: list[str], i: int, stats: Counter[str]) -> list[str]:
    """The next ``_GROUP_PAIR_WINDOW`` members after ``members[i]``; counts what is skipped."""
    rest = len(members) - i - 1
    if rest > _GROUP_PAIR_WINDOW:
        stats["group_pairs_windowed"] += rest - _GROUP_PAIR_WINDOW
    return members[i + 1:i + 1 + _GROUP_PAIR_WINDOW]


def _value_text(text: str) -> str:
    return _CLAUSE_ADDRESS.sub(" ", _CLAUSE_NUMBERING.sub("", _fold(text)))


def unit_values(text: str) -> dict[str, frozenset[str]]:
    """Numbers keyed by the unit word after them ("07 ngay" -> {"ngay": {"07"}}, "30 %")."""
    by_unit: dict[str, set[str]] = {}
    for match in _VALUE_WITH_UNIT.finditer(_value_text(text)):
        by_unit.setdefault(match.group(2) or "", set()).add(match.group(1))
    return {unit: frozenset(numbers) for unit, numbers in by_unit.items()}


def values_differ(left: Mapping[str, frozenset[str]], right: Mapping[str, frozenset[str]]) -> bool:
    # "07 ngày" vs "02 bản" measure different things; only a shared unit can disagree.
    return any(left[unit] != right[unit] for unit in left.keys() & right.keys())


def _jaccard(left: frozenset[str] | None, right: frozenset[str] | None) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _cites(text: str, other: str) -> bool:
    """``other`` names ``text``'s own number as "khoản 4.2"."""
    match = _LEADING_NUMBER.match(text)
    return bool(match) and re.search(
        r"\bkhoan\s+" + re.escape(match.group(1)) + r"(?![\d.]\d)", _fold(other)) is not None


def _same_article_related(text_a: str, text_b: str, words_a: frozenset[str], words_b: frozenset[str]) -> bool:
    return (_cites(text_a, text_b) or _cites(text_b, text_a)
            or text_a.rstrip().endswith(":") or text_b.rstrip().endswith(":")
            or min(len(text_a.strip()), len(text_b.strip())) <= _SAME_ARTICLE_SHORT_CHARS
            or (bool(unit_values(text_a)) and bool(unit_values(text_b)))
            or _jaccard(words_a, words_b) >= _SAME_ARTICLE_MIN_JACCARD)


def _page_furniture(nodes: Iterable[StructuralNode]) -> set[str]:
    """Unnumbered lines that recur on ≥ 2 pages of the same file (running headers/footers).

    Scoped per file so body/annex restating one clause stays comparable; numbered lines are
    never furniture, so a clause duplicated across pages is still a candidate.
    """
    nodes = list(nodes)
    # Furniture sits at a page edge; templated body lines that differ only in numbers
    # ("Đơn giá ... 1.000.000") recur across pages too and must stay clauses.
    by_page: dict[tuple[str | None, int], list[int]] = {}
    for node in nodes:
        if node.page_range:
            by_page.setdefault((node.source_file_id, node.page_range[0]), []).append(node.order)
    edges = {key: (sorted(orders)[:_FURNITURE_EDGE_LINES], sorted(orders)[-_FURNITURE_EDGE_LINES:])
             for key, orders in by_page.items()}
    pages: dict[tuple[str | None, str], set[tuple[str | None, int]]] = {}
    members: dict[tuple[str | None, str], list[str]] = {}
    for node in nodes:
        text = (node.text or "").strip()
        if not text or _CLAUSE_NUMBERING.match(_fold(text)) or not node.page_range:
            continue
        head, tail = edges[(node.source_file_id, node.page_range[0])]
        if node.order not in head and node.order not in tail:
            continue
        folded = _fold(text)  # verbatim: templated body lines differ in their numbers
        # An all-caps running header/footer recurs across the dossier's files too (one
        # page per file is common); restated prose is never all caps, so it stays apart.
        scope = None if _all_caps(text) else node.source_file_id
        page = (node.source_file_id, node.page_range[0])
        pages.setdefault((scope, folded), set()).add(page)
        members.setdefault((scope, folded), []).append(node.node_id)
    return {nid for key, seen in pages.items() if len(seen) >= _FURNITURE_MIN_PAGES for nid in members[key]}


def _all_caps(text: str) -> bool:
    letters = [ch for ch in text if ch.isalpha()]
    return len(letters) >= 4 and all(ch.isupper() for ch in letters)


# Lines that state no term: signature blocks, annex "attached to contract no." lines and
# table header rows (pipe cells without a digit). Matched on folded text.
_NON_CLAUSE = re.compile(r"^(?:dai dien ben\b|kem theo hop dong so\b)")
_TABLE_HEADER = re.compile(r"^\|(?:[^|\d]*\|)+\s*$")


def _non_clause(text: str) -> bool:
    folded = _fold(text).strip()
    return bool(_NON_CLAUSE.match(folded) or _TABLE_HEADER.match(folded))


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
    structured_fields: list[str] = []
    furniture = _page_furniture(by_id.values())
    for nid in ordered:
        if nid in furniture:
            stats["excluded_page_furniture"] += 1
            continue
        node = by_id[nid]
        if node.type == "FIELD" and node.structured_key in {
            "contract_value", "payment_schedule", "payment_term", "payment_method",
        }:
            if len((node.text or "").strip()) >= MIN_CLAUSE_CHARS:
                structured_fields.append(nid)
        if node.type in _SKIPPED_TYPES:
            continue
        if len((node.text or "").strip()) < MIN_CLAUSE_CHARS:
            stats["excluded_short"] += 1
            continue
        if _non_clause(node.text or ""):
            stats["excluded_non_clause"] += 1
            continue
        eligible.append(nid)
    eligible_set = set(eligible)
    chains = _containers(index, by_id)
    candidate_nodes = list(dict.fromkeys((*eligible, *structured_fields)))
    topics = {nid: topic_of(_context(chains, by_id, nid), by_id[nid].text) for nid in candidate_nodes}
    articles = {nid: _article_key(index, chains, nid) for nid in eligible}
    pos = {nid: index.position(nid) for nid in (*eligible, *structured_fields)}
    value_numbers = {}
    content_words = {}
    # Payment-schedule fields carry values too: an annex restating installment 1 at another
    # rate must meet the body's field, not only its plain clauses (#121).
    value_nodes = candidate_nodes
    if PairSource.VALUE_MISMATCH in sources:
        value_numbers = {nid: unit_values(by_id[nid].text or "") for nid in value_nodes}
        content_words = {
            nid: frozenset(w for w in _CONTENT_WORD.findall(_fold(by_id[nid].text or ""))
                           if w not in _VALUE_STOPWORDS)
            for nid in value_nodes
        }
    found: dict[tuple[str, str], set[PairSource]] = {}
    referrers: dict[tuple[str, str], str] = {}
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
                for y in _window(members, i, stats):
                    add(x, y, PairSource.SAME_ARTICLE)
            adjacent.update(_ordered(x, y, pos) for x, y in zip(members, members[1:]))
    if PairSource.EXPLICIT_REF in sources:
        for nid in eligible:
            for target in _explicit_targets(index, by_id[nid], stats):
                if target in eligible_set:
                    add(nid, target, PairSource.EXPLICIT_REF)
                    referrers.setdefault(_ordered(nid, target, pos), nid)
    if PairSource.SAME_KEY in sources:
        by_topic: dict[str, list[str]] = {}
        for nid in eligible:
            if topics[nid] is not None:
                by_topic.setdefault(topics[nid], []).append(nid)
        for members in by_topic.values():
            for i, x in enumerate(members):
                for y in _window(members, i, stats):
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
    if PairSource.VALUE_MISMATCH in sources:
        # Invert content terms and compare only a bounded neighborhood per posting. Expanding
        # every posting into all combinations is quadratic for common terms before top-K applies.
        postings: dict[str, list[str]] = {}
        for nid in value_nodes:
            if not value_numbers[nid]:
                continue
            for word in content_words[nid]:
                postings.setdefault(word, []).append(nid)
        stats["value_mismatch_terms"] = len(postings)
        stats["value_mismatch_pair_comparisons"] = 0
        shared_counts: Counter[tuple[str, str]] = Counter()
        for members in postings.values():
            for i, x in enumerate(members):
                for y in members[i + 1:i + 1 + VALUE_MISMATCH_POSTING_WINDOW]:
                    shared_counts[_ordered(x, y, pos)] += 1
                    stats["value_mismatch_pair_comparisons"] += 1
        for (x, y), shared in shared_counts.items():
            if shared < _VALUE_MISMATCH_MIN_SHARED or not values_differ(value_numbers[x], value_numbers[y]):
                continue
            union = len(content_words[x] | content_words[y])
            if union and shared / union >= _VALUE_MISMATCH_MIN_JACCARD and (x, y) not in found:
                add(x, y, PairSource.VALUE_MISMATCH)

    if PairSource.VERBATIM in sources:
        # Hash the numbering-free text: linear, and only exact restatements pair up.
        by_text: dict[str, list[str]] = {}
        for nid in eligible:
            key = _CLAUSE_NUMBERING.sub("", _fold(by_id[nid].text or "")).strip()
            if len(key) >= MIN_CLAUSE_CHARS:
                by_text.setdefault(key, []).append(nid)
        for members in by_text.values():
            for i, x in enumerate(members):
                for y in _window(members, i, stats):
                    add(x, y, PairSource.VERBATIM)

    if PairSource.STRUCTURED_KEY in sources:
        by_structured_key: dict[str, list[str]] = {}
        for nid in structured_fields:
            key = str(by_id[nid].structured_key or "").strip().casefold()
            if key:
                by_structured_key.setdefault(key, []).append(nid)
        for members in by_structured_key.values():
            for i, x in enumerate(members):
                for y in members[i + 1:]:
                    if not _body_annex(index, x, y):
                        continue
                    value_x = str(by_id[x].structured_value or "").strip()
                    value_y = str(by_id[y].structured_value or "").strip()
                    if value_x and value_y and _fold(value_x) != _fold(value_y):
                        add(x, y, PairSource.STRUCTURED_KEY)

    excluded = {tuple(sorted(p)) for p in excluded_pairs}
    candidates: list[PairCandidate] = []
    words = {nid: frozenset(_CONTENT_WORD.findall(_fold(by_id[nid].text or ""))) for nid in eligible}
    topical = {nid: frozenset(w for w in found_words if w not in _VALUE_STOPWORDS)
               for nid, found_words in words.items()}
    near_duplicate: set[tuple[str, str]] = set()
    for (a, b), srcs in found.items():
        if tuple(sorted((a, b))) in excluded:
            stats["excluded_luong1"] += 1
            continue
        if _nested(index, a, b):
            stats["excluded_ancestor"] += 1
            continue
        if srcs == {PairSource.SAME_ARTICLE} and not _same_article_related(
                by_id[a].text or "", by_id[b].text or "", topical[a], topical[b]):
            stats["excluded_same_article_unrelated"] += 1
            continue
        if _jaccard(words.get(a), words.get(b)) >= _NEAR_DUPLICATE_JACCARD:
            near_duplicate.add((a, b))
        score = sum(WEIGHTS[s] for s in srcs)
        score += _NEAR_DUPLICATE_BONUS if (a, b) in near_duplicate else 0
        score += 1 if PairSource.SAME_ARTICLE in srcs and (a, b) in adjacent else 0
        score += 1 if _body_annex(index, a, b) else 0
        topic = topics[a] if topics[a] == topics[b] else None
        candidates.append(PairCandidate(a, b, frozenset(srcs), float(score), topic, referrers.get((a, b))))
    candidates.sort(key=lambda c: (-c.score, pos[c.node_a], pos[c.node_b], c.node_a, c.node_b))
    limit = max(0, top_k)
    if _BASE_CORE_SOURCES <= sources and limit:
        # Broader C sources must not evict the legacy B candidates solely by adding score.
        # Preserve the legacy B candidates within the same per-document budget; fill unused
        # slots with pairs found only by exploratory sources.
        core = [candidate for candidate in candidates if candidate.sources & _CORE_SOURCES]
        exploratory = [candidate for candidate in candidates if not candidate.sources & _CORE_SOURCES]

        def core_rank(candidate: PairCandidate) -> tuple[float, int, int, str, str]:
            score = sum(WEIGHTS[source] for source in candidate.sources & _CORE_SOURCES)
            score += int(PairSource.SAME_ARTICLE in candidate.sources
                         and (candidate.node_a, candidate.node_b) in adjacent)
            score += int(_body_annex(index, candidate.node_a, candidate.node_b))
            score += _NEAR_DUPLICATE_BONUS if (candidate.node_a, candidate.node_b) in near_duplicate else 0
            return (-score, pos[candidate.node_a], pos[candidate.node_b],
                    candidate.node_a, candidate.node_b)

        core.sort(key=core_rank)
        # Round-robin equal-priority candidates by their earlier endpoint. Same-article
        # cliques otherwise fill the cap with pairs starting at the first few clauses.
        by_priority: dict[float, dict[str, deque[PairCandidate]]] = {}
        for candidate in core:
            priority = -core_rank(candidate)[0]
            by_priority.setdefault(priority, {}).setdefault(candidate.node_a, deque()).append(candidate)
        diversified_core: list[PairCandidate] = []
        for priority in sorted(by_priority, reverse=True):
            queues = by_priority[priority]
            anchors = sorted(queues, key=lambda node_id: (pos[node_id], node_id))
            while True:
                selected_in_round = False
                for anchor in anchors:
                    if queues[anchor]:
                        diversified_core.append(queues[anchor].popleft())
                        selected_in_round = True
                if not selected_in_round:
                    break
        core = diversified_core
        core_limit = min(len(core), math.ceil(limit * _CORE_TOP_K_SHARE))
        kept = core[:core_limit]
        kept.extend(exploratory[:limit - len(kept)])
        kept.sort(key=lambda c: (-c.score, pos[c.node_a], pos[c.node_b], c.node_a, c.node_b))
    else:
        kept = candidates[:limit]
    by_source = Counter(s.value for c in candidates for s in c.sources)
    out = {
        "candidates_total": len(candidates),
        "candidates_by_source": dict(sorted(by_source.items())),
        "excluded_luong1": stats["excluded_luong1"],
        "excluded_ancestor": stats["excluded_ancestor"],
        "excluded_short": stats["excluded_short"],
        "excluded_external_ref": stats["excluded_external_ref"],
        "excluded_page_furniture": stats["excluded_page_furniture"],
        "excluded_non_clause": stats["excluded_non_clause"],
        "excluded_same_article_unrelated": stats["excluded_same_article_unrelated"],
        "group_pairs_windowed": stats["group_pairs_windowed"],
        "near_duplicate_kept": sum((c.node_a, c.node_b) in near_duplicate for c in kept),
        "candidates_capped": len(candidates) - len(kept),
        "candidates_kept": len(kept),
        "value_mismatch_terms": stats["value_mismatch_terms"],
        "value_mismatch_pair_comparisons": stats["value_mismatch_pair_comparisons"],
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

