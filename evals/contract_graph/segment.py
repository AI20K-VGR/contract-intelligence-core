"""Structural tree of a consolidated text (VBHN), in ``StructuralNode`` kwargs shape.

Stdlib only, no ``app`` import: P2 builds its target tree from these dicts.
Labels with a suffix ("Điều 30a.", "5a.", "d1)") are their own units, never folded
into the base unit ("Điều 30", "5.", "d)").
"""

from __future__ import annotations

import re

from evals.contract_graph.normalize import split_notes

ARTICLE = re.compile(r"^Điều\s+(\d+[a-zđ]?)\s*\.\s*", re.I)
# "PHỤ LỤC" alone on its line is an annex heading too (no number: no canonical address)
ANNEX = re.compile(r"^Phụ\s+lục(?:\s+(?:số\s+)?([0-9]+|[IVXLC]+)\b[.:]?\s*|\s*[.:]?\s*$)", re.I)
CLAUSE = re.compile(r"^(\d+[a-zđ]?)\.(?=\s|\[|$)\s*")
POINT = re.compile(r"^([a-zđ]\d*)\)\s*")
DIVISION = re.compile(r"^(?:Chương|Mục|Phần)\s+[IVXLC\d]+\b", re.I)
NOTE_MARKER = re.compile(r"\s*\[\d+\]\s*")


def strip_markers(text: str) -> str:
    return " ".join(NOTE_MARKER.sub(" ", text).split())


def segment(text: str, doc_id: str) -> list[dict]:
    """Điều / khoản / điểm / Phụ lục nodes in document order; the note block is dropped."""

    body, _ = split_notes(text)
    nodes: list[dict] = []
    article: dict | None = None  # current Điều or Phụ lục (root)
    clause: dict | None = None
    current: dict | None = None
    lines: dict[str, list[str]] = {}

    def open_node(raw_label: str, parent: dict | None, rest: str) -> dict:
        node = {
            "node_id": f"{doc_id}:n{len(nodes)}",
            "type": "CLAUSE",
            "raw_label": raw_label,
            "parent_id": parent["node_id"] if parent else None,
            "order": len(nodes),
            "text": "",
            "source_file_id": doc_id,
            "page_range": [1],
        }
        nodes.append(node)
        lines[node["node_id"]] = [rest] if rest else []
        return node

    for line in body.split("\n"):
        line = strip_markers(line)
        if not line:
            continue
        if m := ARTICLE.match(line):
            article = current = open_node(f"Điều {m.group(1).lower()}", None, line[m.end() :])
            clause = None
        elif m := ANNEX.match(line):
            label = f"Phụ lục {m.group(1)}" if m.group(1) else "Phụ lục"
            article = current = open_node(label, None, line[m.end() :])
            clause = None
        elif DIVISION.match(line):
            current = None  # chapter/section headings belong to no unit
        elif (m := CLAUSE.match(line)) and article is not None:
            clause = current = open_node(f"{m.group(1).lower()}.", article, line[m.end() :])
        elif (m := POINT.match(line)) and article is not None:
            current = open_node(f"{m.group(1)})", clause or article, line[m.end() :])
        elif current is not None:
            lines[current["node_id"]].append(line)
    for node in nodes:
        node["text"] = "\n".join(lines[node["node_id"]])
    return nodes


def collapse_to_articles(nodes: list[dict]) -> list[dict]:
    """Root-only tree (Điều N / Phụ lục), the shape AI1 hands over: children folded into the
    root text, one per line, each line opening with the child's original label."""

    children: dict[str | None, list[dict]] = {}
    for node in nodes:
        children.setdefault(node["parent_id"], []).append(node)

    def descendant_lines(node_id: str) -> list[str]:
        out: list[str] = []
        for child in sorted(children.get(node_id, []), key=lambda n: n["order"]):
            out.append(f"{child['raw_label']} {child['text']}".strip())
            out.extend(descendant_lines(child["node_id"]))
        return out

    collapsed = []
    for root in sorted(children.get(None, []), key=lambda n: n["order"]):
        parts = ([root["text"]] if root["text"] else []) + descendant_lines(root["node_id"])
        collapsed.append({**root, "text": "\n".join(parts)})
    return collapsed
