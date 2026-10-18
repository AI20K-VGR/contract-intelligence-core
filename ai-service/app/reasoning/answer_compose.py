"""Turn retrieved evidence into a direct, cited answer with the LLM.

L0/L1 pick the evidence; this step only writes the answer. It never widens the
evidence: every citation must point at a node that was handed to the model,
and a span the model invents falls back to the node's own text. Any failure
returns ``None`` so the caller keeps its deterministic answer.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from app.tools.gateway import ToolGateway

MAX_EVIDENCE = 40
NODE_CHARS = 700
SUMMARY_CHILDREN = 2
SUMMARY_EVIDENCE = 80
PREAMBLE_BLOCKS = 24

_FURNITURE = re.compile(r"^(trang|page)\s*\d+\s*/\s*\d+$", re.IGNORECASE)


def _kind(node: Any) -> str:
    return str(getattr(node.type, "value", node.type))


_CONFLICT_WORDS = ("xung dot", "mau thuan", "sai lech", "khong khop", "trai nhau", "conflict")
_SKIP_TYPES = {"lookup_clause"}

_SYSTEM = (
    "Bạn là trợ lý đọc hợp đồng. Trả lời câu hỏi CHỈ dựa trên các đoạn nguồn được cung cấp. "
    "Viết bằng tiếng Việt, trả lời thẳng vào câu hỏi trước (con số, thời hạn, tên điều khoản), "
    "sau đó giải thích ngắn gọn. Ghi số hiệu điều/khoản khi nhắc tới. "
    "Nếu các nguồn mâu thuẫn, nêu rõ cả hai bên và nói là cần người rà soát; "
    "không kết luận bên nào có hiệu lực pháp lý. Nếu nguồn không đủ để trả lời, nói rõ là không đủ. "
    "Không bịa nội dung ngoài nguồn. "
    'Trả về JSON {"answer": str, "citations": [{"node_id": str, "text_span": str}], "sufficient": bool}. '
    "text_span phải là đoạn trích nguyên văn từ nguồn có node_id đó."
)


def fold(value: str) -> str:
    text = unicodedata.normalize("NFD", (value or "").casefold())
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn").replace("đ", "d")


def is_conflict_query(query: str) -> bool:
    folded = fold(query)
    return any(word in folded for word in _CONFLICT_WORDS)


def is_relation_query(task: dict[str, Any]) -> bool:
    if task.get("type") == "relation_ask":
        return True
    folded = fold(str(task.get("query") or ""))
    return "phu luc" in folded and any(w in folded for w in ("sua doi", "lien quan", "thay doi"))


_REF = re.compile(r"\b(dieu|khoan|muc|phu luc)\s+(\d+(?:\.\d+)*)")
# Lexical recall misses a concept the contract words differently.
_EXPANSIONS = {
    "trong tai": "giải quyết tranh chấp",
    "toa an": "giải quyết tranh chấp",
    "cham tien do": "phạt vi phạm tiến độ",
    "boi thuong": "bồi thường thiệt hại",
}


def eligible(task: dict[str, Any]) -> bool:
    if str(task.get("type") or "") not in _SKIP_TYPES:
        return True
    # "điều 1" stays the clause text; "điều 5 quy định gì về nghiệm thu" is a question.
    rest = _REF.sub(" ", fold(str(task.get("query") or "")))
    return len(re.findall(r"\w+", rest)) >= 2


def expanded_query(query: str) -> str:
    folded = fold(query)
    extra = [phrase for key, phrase in _EXPANSIONS.items() if key in folded]
    return " ".join([query, *extra])


def referenced_nodes(record: Any, query: str) -> list[str]:
    """Nodes whose own label is the article/clause/annex the question names."""

    wanted = _REF.findall(fold(query))
    if not wanted:
        return []
    out: list[str] = []
    for node in record.evidence_nodes():
        head = fold((node.raw_label or node.text or "").strip())[:40]
        for kind, number in wanted:
            if kind in {"dieu", "phu luc"}:
                match = re.match(rf"{kind}\s+0*{re.escape(number.lstrip('0') or '0')}\b", head)
            else:
                match = re.match(rf"{re.escape(number)}(\.|\s|$)", head)
            if match:
                out.append(node.node_id)
                break
    return out[:6]


def _node(
    gateway: ToolGateway, envelope: Any, node_id: str, chars: int = NODE_CHARS
) -> dict[str, Any] | None:
    try:
        full = gateway.call("get_node", envelope, node_id=node_id)
    except Exception:
        return None
    text = str(full.get("text") or "").strip()
    if not text:
        return None
    path = " › ".join([*(full.get("ancestors") or []), str(full.get("raw_label") or "")]).strip(
        " ›"
    )
    return {
        "node_id": node_id,
        "path": path,
        "text": text[:chars],
        "citation": full.get("citation") or {"node_id": node_id},
    }


def evidence_from_citations(
    gateway: ToolGateway,
    envelope: Any,
    citations: list[dict[str, Any]],
    *,
    chars: int = NODE_CHARS,
    limit: int = MAX_EVIDENCE,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for citation in citations:
        node_id = str((citation or {}).get("node_id") or "")
        if not node_id or node_id in seen or len(out) >= limit:
            continue
        seen.add(node_id)
        node = _node(gateway, envelope, node_id, chars)
        if node:
            out.append(node)
    return out


def evidence_from_outline(gateway: ToolGateway, envelope: Any, record: Any) -> list[dict[str, Any]]:
    """The preamble (title, number, parties), then each article/annex heading with its
    first sub-clauses, in document order. Page furniture and repeats are skipped."""

    nodes = list(record.evidence_nodes())
    known = {n.node_id for n in nodes}
    by_parent: dict[str | None, list[Any]] = {}
    for node in nodes:
        by_parent.setdefault(node.parent_id if node.parent_id in known else None, []).append(node)
    seen_text: set[str] = set()

    def keep(node: Any) -> bool:
        text = _norm_ws(node.text or "")
        if not text or _FURNITURE.match(text) or text in seen_text:
            return False
        seen_text.add(text)
        return True

    picked: list[str] = []
    for root in by_parent.get(None, []):
        children = by_parent.get(root.node_id, [])
        preamble = [c for c in children if _kind(c) in {"UNNUMBERED_BLOCK", "FIELD"}]
        # Preamble: blocks before the first numbered article.
        for child in children:
            if _kind(child) not in {"UNNUMBERED_BLOCK", "FIELD"}:
                break
            if child in preamble[:PREAMBLE_BLOCKS] and keep(child):
                picked.append(child.node_id)
        for child in children:
            if _kind(child) not in {"CLAUSE", "SECTION"}:
                continue
            if keep(child):
                picked.append(child.node_id)
            grand = [g for g in by_parent.get(child.node_id, []) if keep(g)]
            picked.extend(g.node_id for g in grand[:SUMMARY_CHILDREN])
    return evidence_from_citations(
        gateway, envelope, [{"node_id": nid} for nid in picked], chars=280, limit=SUMMARY_EVIDENCE
    )


def evidence_from_pairs(
    gateway: ToolGateway, envelope: Any, pairs: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[str]]:
    """Evidence nodes for stored pair relations, conflicts first, plus one line per pair."""

    order = {"CONFLICT": 0, "DUPLICATE": 1, "GENERAL_SPECIFIC": 2, "REFERENCE": 3}
    ranked = sorted(pairs, key=lambda p: order.get(str(p.get("label")), 9))
    ids: list[dict[str, Any]] = []
    lines: list[str] = []
    for pair in ranked[:12]:
        a, b = str(pair.get("node_a_id") or ""), str(pair.get("node_b_id") or "")
        if a and b:
            ids.extend([{"node_id": a}, {"node_id": b}])
            lines.append(f"- {pair.get('label')}: {a} <-> {b}")
    return evidence_from_citations(gateway, envelope, ids), lines


def _user_prompt(query: str, evidence: list[dict[str, Any]], notes: list[str]) -> str:
    parts = [f"Câu hỏi: {query}", "", "Nguồn:"]
    for item in evidence:
        parts.append(f"node_id: {item['node_id']}\n{item['path']}\n{item['text']}")
    if notes:
        parts += ["", "Quan hệ hệ thống đã phát hiện giữa các nguồn (cần người xác nhận):", *notes]
    return "\n\n".join(parts)


def _norm_ws(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def compose(
    llm: Any,
    query: str,
    evidence: list[dict[str, Any]],
    notes: list[str] | None = None,
) -> dict[str, Any] | None:
    if not llm or not evidence:
        return None
    try:
        data = llm.complete_json(_SYSTEM, _user_prompt(query, evidence, notes or []))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    answer = data.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        return None
    by_id = {item["node_id"]: item for item in evidence}
    citations: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in data.get("citations") or []:
        if not isinstance(raw, dict):
            continue
        # Models echo the id the way the prompt framed it ("[id]", "`id`").
        node_id = str(raw.get("node_id") or "").strip().strip("[]()<>`'\" ")
        item = by_id.get(node_id)
        if item is None or node_id in seen:
            continue
        seen.add(node_id)
        span = str(raw.get("text_span") or "")
        if not span or _norm_ws(span) not in _norm_ws(item["text"]):
            span = item["text"][:300]
        citations.append({**item["citation"], "node_id": node_id, "text_span": span})
    if not citations:
        return None
    return {
        "answer": answer.strip(),
        "citations": citations,
        "sufficient": data.get("sufficient") is True,
    }
