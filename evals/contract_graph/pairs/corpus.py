"""Public SALES / SUPPLY_SERVICE contract templates → normalized, segmented docs.

Also the two split guards of RT-13: near-duplicate clusters (a template copied across domains
must not land in both splits) and contamination by the clause-key spike (its URLs, ``repo:``
fixtures, or any spike clause contained in the text) which forces a cluster to ``dev``.

Words for shingles are ``\\w+`` runs of the ``fold_for_match`` text: whitespace is collapsed by
construction and punctuation never splits a match.

Web pages carry the site after the contract (commentary, FAQ, comments, footer). ``trim_tail`` cuts
it at the first reliable boundary after the last Điều — the end of the signature block, else the
first site-chrome line — and keeps the text when neither is found. docx sources are never cut.
"""

from __future__ import annotations

import functools
import hashlib
import json
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from evals.contract_graph.dataset import fetch_cached
from evals.contract_graph.normalize import docx_to_text, html_to_text
from evals.contract_graph.segment import segment

REPO_ROOT = Path(__file__).resolve().parents[3]
AI_SERVICE = REPO_ROOT / "ai-service"
SPIKE_DIR = REPO_ROOT / "evals" / "spikes" / "clause_key"
SPIKE_SOURCES = ("heldout_sources.json", "heldout2_sources.json")
SPIKE_CLAUSES = ("clauses_heldout.jsonl", "clauses_heldout2.jsonl")
PROFILES = ("SALES", "SUPPLY_SERVICE")
MIN_ARTICLES = 5
MIN_NODE_CHARS = 20
HEADING_MAX = 120
SHINGLE = 5
JACCARD_MIN = 0.8
CONTAINMENT_MIN = 0.5

_ARTICLE_HEAD = re.compile(r"^\s*(?:ĐIỀU|Điều|DIEU)\s+(\d+[a-zđA-ZĐ]?)\s*[:.\-–]\s*")
_ANNEX_HEAD = re.compile(r"^\s*(?:PHỤ\s+LỤC|Phụ\s+lục|PHU\s+LUC)(?![\w])")
_WORD = re.compile(r"\w+")

# A signature line holds only party labels, "(Ký …)" notes and "Chức vụ"; a block names ≥ 2 parties.
_PARTY = re.compile(
    r"(?:đại\s+diện\s+)?bên\s+(?:[abc]|mua|bán|cho\s+thuê|giao|nhận"
    r"|(?:cung\s+(?:cấp|ứng)|sử\s+dụng|thuê)(?:\s+dịch\s+vụ)?)\b",
    re.IGNORECASE,
)
_SIGNATURE_LINE = re.compile(
    rf"(?:(?:{_PARTY.pattern}|\([^()]*\)|chức\s+vụ)[\s:.,]*)+", re.IGNORECASE
)
SIGNATURE_LINE_MAX = 120
SIGNATURE_PARTIES_MIN = 2
ANNEX_AFTER_SIGNATURE_LINES = 3
# Site chrome that never opens a contract line: the whole line, or the line's opening words.
_SITE_MARKER = re.compile(
    r"(?:đánh giá bài viết|chia sẻ:?|tải về|tham khảo thêm|(?:\d+\s+)?bình luận"
    r"|nội dung bài viết:?)$"
    r"|\d+(?:[.,]\d+)?\s+sao của\s+\d+\s+đánh giá|bạn thấy nội dung này"
    r"|bài viết (?:liên quan|cùng chủ đề)|tham khảo dịch vụ|mời bạn đọc|hãy để lại thông tin"
    r"|bài viết này được đăng",
    re.IGNORECASE,
)


class RejectedDocument(ValueError):
    """A source that does not segment into at least ``MIN_ARTICLES`` articles."""

    def __init__(self, url: str, n_articles: int) -> None:
        super().__init__(f"{url}: {n_articles} Điều after segmentation (< {MIN_ARTICLES})")
        self.url = url
        self.n_articles = n_articles


@dataclass(frozen=True)
class Tail:
    """Where the page text was cut: ``signature`` / ``marker``; ``None`` = no reliable boundary
    (text kept); ``docx`` = not a web page, never cut."""

    boundary: str | None
    trimmed_chars: int


def fetch(source: dict, cache_dir: Path, offline: bool = False) -> tuple[str, Tail]:
    return page_text(fetch_cached(source["url"], cache_dir, offline))


def page_text(raw: bytes) -> tuple[str, Tail]:
    if raw[:2] == b"PK":
        return docx_to_text(raw), Tail("docx", 0)
    return trim_tail(html_to_text(raw))


def trim_tail(text: str) -> tuple[str, Tail]:
    """Drop what follows the contract on a web page. After the last Điều heading: cut at the end of
    the first signature block (≥ 2 party labels) unless a Phụ lục heading opens within
    ``ANNEX_AFTER_SIGNATURE_LINES`` lines after it; otherwise cut at the first site-chrome line.
    No boundary ⇒ text unchanged, ``Tail(None, 0)``."""

    lines = text.split("\n")
    last_article = max((i for i, line in enumerate(lines) if _ARTICLE_HEAD.match(line)),
                       default=None)
    if last_article is None:
        return text, Tail(None, 0)
    cut, boundary = None, None
    signature_end = _signature_end(lines, last_article + 1)
    if signature_end is not None:
        following = lines[signature_end : signature_end + ANNEX_AFTER_SIGNATURE_LINES]
        if not any(_ANNEX_HEAD.match(line) for line in following):
            cut, boundary = signature_end, "signature"
    if cut is None:
        cut = next((i for i in range(last_article + 1, len(lines))
                    if _SITE_MARKER.match(lines[i].strip())), None)
        boundary = "marker"
    if cut is None:
        return text, Tail(None, 0)
    kept = "\n".join(lines[:cut])
    return kept, Tail(boundary, len(text) - len(kept))


def _is_signature_line(line: str) -> bool:
    line = line.strip()
    return len(line) <= SIGNATURE_LINE_MAX and _SIGNATURE_LINE.fullmatch(line) is not None


def _signature_end(lines: list[str], start: int) -> int | None:
    """Index just past the first run of signature lines from ``start`` naming ≥ 2 parties."""

    i = start
    while i < len(lines):
        if not (_is_signature_line(lines[i]) and _PARTY.search(lines[i])):
            i += 1
            continue
        end = i
        while end < len(lines) and _is_signature_line(lines[end]):
            end += 1
        if sum(len(_PARTY.findall(line)) for line in lines[i:end]) >= SIGNATURE_PARTIES_MIN:
            return end
        i = end
    return None


def normalize_headings(text: str) -> str:
    """``ĐIỀU 1:`` / ``Điều 2 –`` / ``DIEU 3 -`` opening a line → ``Điều N.``; ``PHỤ LỤC`` opening a
    line → ``Phụ lục``. Mid-line references ("theo Điều 5: …") are left alone."""

    out = []
    for line in text.split("\n"):
        if m := _ARTICLE_HEAD.match(line):
            line = f"Điều {m.group(1).lower()}. {line[m.end() :]}".rstrip()
        elif m := _ANNEX_HEAD.match(line):
            line = "Phụ lục" + line[m.end() :]
        out.append(line)
    return "\n".join(out)


def doc_id_for(url: str) -> str:
    return "pd-" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:10]


def build_doc(source: dict, text: str) -> dict:
    """One source + its page text → ``{doc_id, url, profile, …, nodes}``; each node carries the
    heading (≤ ``HEADING_MAX`` chars) of its Điều / Phụ lục root. Leaves shorter than
    ``MIN_NODE_CHARS`` are dropped. Fewer than ``MIN_ARTICLES`` Điều ⇒ ``RejectedDocument``."""

    url = source["url"]
    doc_id = doc_id_for(url)
    nodes = _drop_short_leaves(segment(normalize_headings(text), doc_id))
    by_id = {n["node_id"]: n for n in nodes}
    for node in nodes:
        root = node
        while root["parent_id"] in by_id:
            root = by_id[root["parent_id"]]
        node["heading"] = _heading(root)
    articles = {n["raw_label"] for n in nodes if n["parent_id"] is None and _is_article(n)}
    if len(articles) < MIN_ARTICLES:
        raise RejectedDocument(url, len(articles))
    return {
        "doc_id": doc_id,
        "url": url,
        "profile": source["profile"],
        "title": source.get("title", ""),
        "has_annex_section": source.get("has_annex_section"),
        "has_annex": any(n["parent_id"] is None and not _is_article(n) for n in nodes),
        "n_articles": len(articles),
        "nodes": nodes,
    }


def _drop_short_leaves(nodes: list[dict]) -> list[dict]:
    while True:
        parents = {n["parent_id"] for n in nodes if n["parent_id"] is not None}
        kept = [n for n in nodes if len(n["text"]) >= MIN_NODE_CHARS or n["node_id"] in parents]
        if len(kept) == len(nodes):
            return kept
        nodes = kept


def _is_article(node: dict) -> bool:
    return node["raw_label"].startswith("Điều ")


def _heading(root: dict) -> str:
    title = root["text"].split("\n", 1)[0].strip()
    return (f"{root['raw_label']}. {title}" if title else root["raw_label"])[:HEADING_MAX]


def doc_text(doc: dict) -> str:
    return "\n".join(n["text"] for n in doc["nodes"])


def fold(text: str) -> str:
    return " ".join(_fold_for_match()(text).split())


def shingles(text: str) -> frozenset[str]:
    words = _WORD.findall(fold(text))
    if len(words) < SHINGLE:
        return frozenset({" ".join(words)}) if words else frozenset()
    return frozenset(" ".join(words[i : i + SHINGLE]) for i in range(len(words) - SHINGLE + 1))


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def heading_signature(doc: dict) -> str:
    """sha256 of the folded Điều headings in document order."""

    chain = "\n".join(
        fold(n["heading"]) for n in doc["nodes"] if n["parent_id"] is None and _is_article(n)
    )
    return hashlib.sha256(chain.encode("utf-8")).hexdigest()


def near_duplicate_clusters(docs: Iterable[dict]) -> list[dict]:
    """Union-find over docs: same cluster when shingle Jaccard ≥ ``JACCARD_MIN`` or the Điều
    heading chains are equal. Output sorted by ``cluster_id``; input order does not matter."""

    docs = sorted(docs, key=lambda d: d["doc_id"])
    ids = [d["doc_id"] for d in docs]
    sets = [shingles(doc_text(d)) for d in docs]
    signatures = [heading_signature(d) for d in docs]
    parent = list(range(len(docs)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(docs)):
        for j in range(i + 1, len(docs)):
            if signatures[i] == signatures[j] or jaccard(sets[i], sets[j]) >= JACCARD_MIN:
                parent[max(find(i), find(j))] = min(find(i), find(j))
    groups: dict[int, list[str]] = {}
    for i, doc_id in enumerate(ids):
        groups.setdefault(find(i), []).append(doc_id)
    clusters = [
        {"cluster_id": "cl-" + hashlib.sha256("|".join(members).encode()).hexdigest()[:10],
         "doc_ids": members}
        for members in groups.values()
    ]
    return sorted(clusters, key=lambda c: c["cluster_id"])


def normalize_url(url: str) -> str:
    url = url.strip()
    if url.startswith("repo:"):
        return url
    url = re.sub(r"^[a-z]+://", "", url, flags=re.I).split("#", 1)[0].rstrip("/")
    host, _, path = url.partition("/")
    host = host.lower().removeprefix("www.")
    return f"{host}/{path}" if path else host


@dataclass(frozen=True)
class Spike:
    """What the clause-key spike already used: URLs (normalized) and clause shingle sets."""

    urls: frozenset[str]
    clause_shingles: tuple[frozenset[str], ...]

    @classmethod
    def from_texts(cls, urls: Iterable[str], texts: Iterable[str]) -> Spike:
        return cls(
            frozenset(normalize_url(u) for u in urls),
            tuple(s for s in (shingles(t) for t in texts) if s),
        )


@functools.cache
def load_spike(spike_dir: Path = SPIKE_DIR) -> Spike:
    urls: list[str] = []
    for name in SPIKE_SOURCES:
        urls.extend(json.loads((spike_dir / name).read_text(encoding="utf-8")).values())
    texts = []
    for name in SPIKE_CLAUSES:
        for line in (spike_dir / name).read_text(encoding="utf-8").splitlines():
            if line.strip():
                texts.append(json.loads(line)["text"])
    return Spike.from_texts(urls, texts)


def contaminated(doc: dict, spike: Spike | None = None) -> bool:
    spike = spike if spike is not None else load_spike()
    url = doc["url"]
    if url.startswith("repo:") or normalize_url(url) in spike.urls:
        return True
    words = shingles(doc_text(doc))
    return any(len(c & words) / len(c) >= CONTAINMENT_MIN for c in spike.clause_shingles)


@functools.cache
def _fold_for_match():
    """``app.pipeline.ai1_snapshot_adapter.fold_for_match`` (``ai-service`` is not a package of
    the repo root, so its path is added on first use)."""

    if str(AI_SERVICE) not in sys.path:
        sys.path.insert(0, str(AI_SERVICE))
    from app.pipeline.ai1_snapshot_adapter import fold_for_match

    return fold_for_match
