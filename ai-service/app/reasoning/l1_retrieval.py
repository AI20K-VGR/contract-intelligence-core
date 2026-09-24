from __future__ import annotations

import math
import re
from typing import Any

from app.contracts.models import ToolEnvelope
from app.reasoning.relations import build_relation_graph
from app.reasoning.vector_recall import VectorRecallService
from app.tools.gateway import ToolBlocked, ToolGateway

COMPARE_TYPES = {"compare", "cascade"}
EXPAND_SEMANTIC = COMPARE_TYPES

KNOWN_STRUCTURED_KEYS = frozenset(
    {
        "mst_seller",
        "contract_value",
        "contract_value_words",
        "payment_term",
        "party_a",
        "party_b",
        "mst_party_a",
        "mst_party_b",
        "mst_party_c",
        "mst_party_y",
        "penalty",
        "validity",
        "price",
        "qty",
    }
)

SYNONYMS: dict[str, str] = {
    "working day": "ngày làm việc",
    "working days": "ngày làm việc",
    "payment": "thanh toán",
    "pay": "thanh toán",
    "penalty": "phạt",
    "annex": "phụ lục",
    "appendix": "phụ lục",
    "article": "điều",
    "clause": "điều",
    "tax id": "mst",
    "vat code": "mst",
    "acceptance": "nghiệm thu",
    "definition": "định nghĩa",
}


def expand_query(query: str) -> str:
    q = query or ""
    low = q.lower()
    extra: list[str] = []
    for en, vi in SYNONYMS.items():
        if en in low and vi not in low:
            extra.append(vi)
        if vi in low and en not in low:
            extra.append(en)
    return (q + " " + " ".join(extra)).strip()


class L1Retrieval:
    def __init__(self, gateway: ToolGateway, vector_recall: VectorRecallService | None = None) -> None:
        self.gateway = gateway
        self.vector_recall = vector_recall or VectorRecallService()

    def run(self, envelope: ToolEnvelope, task: dict[str, Any]) -> dict[str, Any]:
        q = task.get("query") or ""
        ttype = task.get("type")
        hits: list[dict[str, Any]] = []
        structured_keys_used: list[str] = []
        rels: list[dict[str, Any]] = []
        outline: list[dict[str, Any]] = []
        try:
            record = self.gateway.store.get(envelope.auth.tenant_id, envelope.auth.dossier_id)
            if record is not None and record.relation_graph is None:
                record.relation_graph = build_relation_graph(record)
            outline = self.gateway.call("list_structure", envelope, dossier_id=envelope.auth.dossier_id)
            exact_ids = _exact_label_ids(q, outline)
            for nid in exact_ids:
                node = self.gateway.call("get_node", envelope, node_id=nid)
                hits.append(_hit_from_node(node))
            keys = structured_keys(q, ttype)
            structured_keys_used = keys
            for key in keys:
                hits.extend(self.gateway.call("search_structured", envelope, key=key) or [])
            if ttype in EXPAND_SEMANTIC or (not hits and ttype in {"lookup_term", "unscoped", "raw_fact_check"}):
                sem = self.gateway.call("search_semantic", envelope, query=expand_query(q), k=8) or []
                hits.extend(sem)
            if ttype in COMPARE_TYPES:
                # Keep exact clause/annex targets even when their text does
                # not repeat the relation cue. Filtering them out allowed a
                # query about Điều 2 to be answered from Điều 1 only.
                filtered = _filter_relation_hits(q, hits)
                protected = [h for h in hits if str(h.get("node_id") or "") in set(exact_ids)]
                hits = _merge_hits(protected, filtered)
            from app.reasoning.relations import attach_ancestors, related_node_ids

            outline = attach_ancestors(list(outline))
            if ttype in COMPARE_TYPES:
                extra_ids, rels = related_node_ids(
                    [str(h.get("node_id") or h.get("chunk_id")) for h in hits if h.get("node_id") or h.get("chunk_id")],
                    outline,
                )
                for eid in extra_ids:
                    node = self.gateway.call("get_node", envelope, node_id=eid)
                    hits.append(_hit_from_node(node))
            # A term lookup must stay local to its matched evidence.  Expanding
            # from an empty/weak seed through the parent graph turns a missing
            # term into an answer containing the entire outline.
            if ttype == "lookup_term":
                hits = _filter_term_hits(q, hits)

            graph_edges = []
            graph_issues = []
            if record is not None and record.relation_graph is not None:
                seed_ids = {str(h.get("node_id") or h.get("chunk_id")) for h in hits}
                graph_edges = [
                    edge.model_dump()
                    for edge in record.relation_graph.edges
                    if edge.from_node_id in seed_ids or edge.to_node_id in seed_ids
                ][:32]
                graph_issues = [issue.model_dump() for issue in record.relation_graph.issues]
                if ttype in COMPARE_TYPES and seed_ids:
                    known_ids = {node.node_id for node in record.evidence_nodes()}
                    extra_graph_ids = {
                        endpoint
                        for edge in record.relation_graph.edges
                        for endpoint in (edge.from_node_id, edge.to_node_id)
                        if endpoint not in seed_ids and endpoint in known_ids
                    }
                    for eid in list(extra_graph_ids)[:12]:
                        node = self.gateway.call("get_node", envelope, node_id=eid)
                        hits.append(_hit_from_node(node))
            vector_result = self.vector_recall.recall(
                record,
                expand_query(q),
                k=12,
                filters={"source_role": task.get("source_role")} if task.get("source_role") else None,
            ) if record is not None and ttype in {"compare", "cascade", "lookup_term", "unscoped"} else None
            if vector_result and vector_result.candidates:
                for candidate in vector_result.candidates:
                    hits.append(
                        {
                            "node_id": candidate.segment.node_id,
                            "chunk_id": candidate.segment.segment_id,
                            "citation": candidate.citation.model_dump(),
                            "score": candidate.score,
                            "retrieval_method": candidate.retrieval_method,
                        }
                    )
            if ttype in COMPARE_TYPES:
                filtered = _filter_relation_hits(q, hits)
                protected = [h for h in hits if str(h.get("node_id") or "") in set(exact_ids)]
                hits = _merge_hits(protected, filtered)
        except ToolBlocked:
            return {"resolved": False, "blocked": True, "hits": [], "outline_ids": [], "structured_keys": []}

        seen: set[str] = set()
        deduped = []
        for h in hits:
            nid = str(h.get("node_id") or h.get("chunk_id"))
            if nid in seen:
                continue
            seen.add(nid)
            deduped.append(h)
        deduped = deduped[:12]

        enough_lookup = ttype not in COMPARE_TYPES and len(deduped) >= 1
        if ttype in COMPARE_TYPES and not deduped:
            relation_issue = {
                "missing": "relation target or source evidence",
                "reason": "Không đủ source để dựng quan hệ; không suy đoán từ toàn bộ outline.",
            }
            graph_issues = [*graph_issues, relation_issue]
        return {
            "resolved": bool(enough_lookup and ttype in {"lookup"}),
            "blocked": False,
            "hits": deduped,
            "outline_ids": [{"node_id": n["node_id"], "type": n["type"], "raw_label": n["raw_label"]} for n in outline],
            "structured_keys": structured_keys_used,
            "relations": rels,
            "relation_edges": graph_edges,
            "relation_issues": graph_issues,
            "retrieval_trace": vector_result.trace if vector_result else {"vector_status": "NOT_REQUESTED"},
        }


def structured_keys(query: str, ttype: str | None) -> list[str]:
    q = (query or "").lower()
    keys: list[str] = []
    if "mst" in q or "tax id" in q:
        keys.append("mst_seller")
    if "giá" in q or "gia tri" in q or "giá trị" in q or "contract value" in q:
        keys.append("contract_value")
    if "ngày làm việc" in q or "ngay lam viec" in q or "working day" in q:
        keys.append("payment_term")
    if ttype == "lookup_term" and ("bên a" in q or "party" in q):
        keys.append("party_a")
    if "phạt" in q or "penalty" in q:
        keys.append("penalty")
    return [k for k in keys if k in KNOWN_STRUCTURED_KEYS]


def _exact_label_ids(query: str, outline: list[dict[str, Any]]) -> list[str]:
    labels: list[str] = []
    plain = _plain_query(query)
    for m in re.finditer(r"dieu\s+(\d+(?:\.\d+)?)", plain, re.I):
        labels.append(f"Điều {m.group(1)}")
    for m in re.finditer(r"(?:phu luc|annex)\s+(\d+)", plain, re.I):
        labels.append(f"Phụ lục {m.group(1)}")
    for m in re.finditer(r"điều\s+(\d+(?:\.\d+)?)", query, re.I):
        labels.append(f"Điều {m.group(1)}")
    for m in re.finditer(r"dieu\s+(\d+(?:\.\d+)?)", query, re.I):
        labels.append(f"Điều {m.group(1)}")
    for m in re.finditer(r"phụ lục\s+(\d+)", query, re.I):
        labels.append(f"Phụ lục {m.group(1)}")
    for m in re.finditer(r"phu luc\s+(\d+)", query, re.I):
        labels.append(f"Phụ lục {m.group(1)}")
    ids: list[str] = []
    for lab in labels:
        wanted = _plain_query(lab)
        for n in outline:
            raw = (n.get("raw_label") or "").strip()
            normalized = _plain_query(raw)
            if (
                normalized == wanted
                or normalized.startswith(wanted + " ")
                or normalized.startswith(wanted + ".")
                or normalized.startswith(wanted + ",")
            ) and n["node_id"] not in ids:
                ids.append(n["node_id"])
    return ids


def _merge_hits(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for group in groups:
        for hit in group:
            key = str(hit.get("node_id") or hit.get("chunk_id") or "")
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(hit)
    return merged
def _plain_query(value: str) -> str:
    import unicodedata

    text = unicodedata.normalize("NFD", value.casefold())
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return text.replace("đ", "d")


def _hit_from_node(node: dict[str, Any]) -> dict[str, Any]:
    nid = node.get("node_id")
    text = str(node.get("text") or "")
    return {
        "node_id": nid,
        "value": node.get("structured_value"),
        "citation": node.get("citation")
        or {
            "node_id": nid,
            "text_span": (node.get("structured_value") or text)[:200],
        },
    }


def _filter_term_hits(query: str, hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reject lexical/vector hits that do not contain the requested concept."""

    normalized_query = _plain_query(expand_query(query))
    cues = (
        "ngay lam viec",
        "working day",
        "thanh toan",
        "payment",
        "nghiem thu",
        "acceptance",
        "dinh nghia",
        "definition",
        "thoi han",
        "hieu luc",
        "ngay ky",
        "tu ngay",
        "cham dut",
        "thoi han",
        "hieu luc",
        "ngay ky",
        "tu ngay",
    )
    wanted = [cue for cue in cues if cue in normalized_query]
    if not wanted:
        return hits
    kept: list[dict[str, Any]] = []
    for hit in hits:
        citation = hit.get("citation") or {}
        evidence = _plain_query(" ".join(str(value or "") for value in (hit.get("value"), citation.get("text_span"))))
        if any(cue in evidence for cue in wanted):
            kept.append(hit)
    return kept


def _filter_relation_hits(query: str, hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized_query = _plain_query(expand_query(query))
    cues = []
    if "phu luc" in normalized_query or "annex" in normalized_query:
        cues.append(("phu luc", "annex"))
    if "dinh nghia" in normalized_query or "definition" in normalized_query:
        cues.append(("dinh nghia", "definition"))
    if "thanh toan" in normalized_query or "payment" in normalized_query:
        cues.append(("thanh toan", "payment"))
    if not cues:
        return hits
    kept: list[dict[str, Any]] = []
    for hit in hits:
        citation = hit.get("citation") or {}
        evidence = _plain_query(
            " ".join(
                str(value or "")
                for value in (
                    hit.get("value"),
                    citation.get("text_span"),
                    " ".join(citation.get("breadcrumb") or []),
                    citation.get("structure_path"),
                )
            )
        )
        if any(left in evidence or right in evidence for left, right in cues):
            kept.append(hit)
    return kept


def bm25_lite_score(query: str, docs: list[str]) -> list[float]:
    """BM25-lite over whitespace tokens; used by tests and search_semantic."""
    q_toks = [t for t in expand_query(query).lower().split() if t]
    if not docs or not q_toks:
        return [0.0] * len(docs)
    N = len(docs)
    df: dict[str, int] = {}
    tok_docs = [d.lower().split() for d in docs]
    for toks in tok_docs:
        for t in set(toks):
            df[t] = df.get(t, 0) + 1
    avgdl = sum(len(t) for t in tok_docs) / N
    k1, b = 1.2, 0.75
    scores = []
    for toks in tok_docs:
        dl = len(toks) or 1
        tf: dict[str, int] = {}
        for t in toks:
            tf[t] = tf.get(t, 0) + 1
        s = 0.0
        for qt in q_toks:
            n_q = df.get(qt, 0)
            if not n_q:
                continue
            idf = math.log((N - n_q + 0.5) / (n_q + 0.5) + 1.0)
            f = tf.get(qt, 0)
            s += idf * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / avgdl))
        scores.append(s)
    return scores
