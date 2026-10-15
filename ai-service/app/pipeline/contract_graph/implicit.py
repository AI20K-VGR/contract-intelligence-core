"""Implicit substitutions (K4): an annex that changes values without naming a provision.

Only an annex part (``annex:*`` of ``StructureIndex``) that says it changes something
("nội dung điều chỉnh", "thay đổi số lượng …" with no address) and that holds no explicit
operation is considered. Each of its facts with an ``item_key`` is matched to the body facts
of the same key: one body node with a different value → a match; the same value → nothing;
several body nodes → ambiguous; none → not found. The builder turns matches into
``SUBSTITUTION`` edges that are always ``NEEDS_REVIEW`` (method ``ITEM_KEY``).
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal

from app.contracts.models import Fact, StructuralNode
from app.pipeline.contract_graph.address import parse_addresses
from app.pipeline.contract_graph.resolver import StructureIndex
from app.pipeline.relation_markers import _AMEND_EXCLUDE

_MARKER = re.compile(
    r"nội\s+dung\s+(?:điều\s+chỉnh|sửa\s+đổi|thay\s+đổi)(?![\wđ])"
    r"|(?<![\wđ])(?:thay\s+đổi|điều\s+chỉnh)\s+(?!theo(?![\wđ]))[^\W\d_]",
    re.I,
)
_SENTENCE = re.compile(r"[^.;\n]+")


@dataclass(frozen=True)
class ImplicitMatch:
    annex_fact: Fact
    body_fact: Fact
    item_key: str
    part: str


@dataclass(frozen=True)
class ImplicitIssue:
    annex_fact: Fact
    item_key: str
    kind: Literal["TARGET_AMBIGUOUS", "TARGET_NOT_FOUND"]
    candidates: tuple[str, ...]


def has_implicit_marker(text: str) -> bool:
    """A sentence announcing a change that names no provision."""

    folded = _AMEND_EXCLUDE.sub(" ", unicodedata.normalize("NFC", text or ""))
    return any(
        _MARKER.search(sentence) and not parse_addresses(sentence)
        for sentence in _SENTENCE.findall(folded)
    )


def implicit_matches(
    index: StructureIndex,
    nodes: Iterable[StructuralNode],
    facts: Iterable[Fact],
    explicit_parts: set[str],
    stats: Counter[str],
) -> tuple[list[ImplicitMatch], list[ImplicitIssue]]:
    texts: Mapping[str, str] = {node.node_id: node.text or "" for node in nodes}
    facts = list(facts)
    body_parts = index.body_parts()
    marked = sorted(
        part
        for part in index.annex_parts()
        if part not in explicit_parts
        and any(
            index.part_of(node_id) == part and has_implicit_marker(texts.get(node_id, ""))
            for node_id in index.node_ids()
        )
    )
    matches: list[ImplicitMatch] = []
    issues: list[ImplicitIssue] = []
    for part in marked:
        annex_facts = [
            f
            for f in facts
            if f.source_role == "annex" and f.item_key and index.part_of(f.citation.node_id) == part
        ]
        for annex in annex_facts:
            body = [
                f
                for f in facts
                if f.item_key == annex.item_key
                and f.source_role != "annex"
                and index.part_of(f.citation.node_id) in body_parts
            ]
            body_nodes = sorted({f.citation.node_id for f in body}, key=index.position)
            if not body_nodes:
                issues.append(ImplicitIssue(annex, annex.item_key, "TARGET_NOT_FOUND", ()))
                continue
            if len(body_nodes) > 1:
                issues.append(
                    ImplicitIssue(annex, annex.item_key, "TARGET_AMBIGUOUS", tuple(body_nodes))
                )
                continue
            if _value(annex) in {_value(f) for f in body}:
                stats["implicit_same_value"] += 1
                continue
            matches.append(ImplicitMatch(annex, body[0], annex.item_key, part))
    return matches, issues


def _value(fact: Fact) -> str:
    value = fact.normalized_value if fact.normalized_value is not None else fact.raw_value
    return " ".join(str(value).split()).casefold()
