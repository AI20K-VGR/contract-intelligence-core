from __future__ import annotations

import math
import re
import time
from typing import Any

from app.contracts.models import ToolEnvelope
from app.pipeline.result_structure import _is_running_furniture
from app.reasoning.relations import build_relation_graph
from app.reasoning.vector_recall import VectorRecallService
from app.tools.gateway import ToolBlocked, ToolGateway

COMPARE_TYPES = {"compare", "cascade"}
EXPAND_SEMANTIC = COMPARE_TYPES
LOGICAL_TABLE_ROW_CAP = 200
LOGICAL_TABLE_CELL_CAP = 5000
LOGICAL_TABLE_PAGE_CAP = 100
LOGICAL_TABLE_TIME_CAP_SECONDS = 2.0

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
    def __init__(
        self, gateway: ToolGateway, vector_recall: VectorRecallService | None = None
    ) -> None:
        self.gateway = gateway
        self.vector_recall = vector_recall or VectorRecallService()

    def run(self, envelope: ToolEnvelope, task: dict[str, Any]) -> dict[str, Any]:
        q = task.get("query") or ""
        ttype = task.get("type")
        hits: list[dict[str, Any]] = []
        structured_keys_used: list[str] = []
        rels: list[dict[str, Any]] = []
        outline: list[dict[str, Any]] = []
        exact_ids: list[str] = []
        structured_ids: list[str] = []
        topic_ids: list[str] = []
        coverage_groups: list[str] = []
        record = None
        logical_tables: list[dict[str, Any]] = []
        try:
            record = self.gateway.store.get(envelope.auth.tenant_id, envelope.auth.dossier_id)
            if record is not None and record.relation_graph is None:
                record.relation_graph = build_relation_graph(record)
            if record is not None and ttype in COMPARE_TYPES and _asks_payment_schedule(q):
                logical_tables = expand_logical_tables(self.gateway, envelope, q)
            outline = self.gateway.call(
                "list_structure", envelope, dossier_id=envelope.auth.dossier_id
            )
            exact_ids = _exact_label_ids(q, outline)
            for nid in exact_ids:
                node = self.gateway.call("get_node", envelope, node_id=nid)
                hits.append(_hit_from_node(node))
            keys = structured_keys(q, ttype)
            structured_keys_used = keys
            for key in keys:
                found = self.gateway.call("search_structured", envelope, key=key) or []
                structured_ids.extend(str(h.get("node_id")) for h in found if h.get("node_id"))
                hits.extend(found)
            if ttype in EXPAND_SEMANTIC or (not hits and ttype in {"lookup_term", "payment_card"}):
                sem = (
                    self.gateway.call("search_semantic", envelope, query=expand_query(q), k=8) or []
                )
                hits.extend(sem)
            if ttype in COMPARE_TYPES:
                # Keep exact clause/annex targets even when their text does
                # not repeat the relation cue. Filtering them out allowed a
                # query about Điều 2 to be answered from Điều 1 only.
                filtered = _filter_relation_hits(q, hits)
                protected = [h for h in hits if str(h.get("node_id") or "") in set(exact_ids)]
                # The body side of a body-vs-annex question rarely says "phụ
                # lục", so the relation filter drops exactly the clause being
                # compared (Điều 3 "Tiến độ") and keeps clauses that only cite
                # an annex. Keep the clear topic matches regardless.
                topic = _topic_hits(record, q) if record is not None else []
                hits = _merge_hits(protected, topic, filtered)
            from app.reasoning.relations import attach_ancestors, related_node_ids

            outline = attach_ancestors(list(outline))
            if ttype in COMPARE_TYPES:
                extra_ids, rels = related_node_ids(
                    [
                        str(h.get("node_id") or h.get("chunk_id"))
                        for h in hits
                        if h.get("node_id") or h.get("chunk_id")
                    ],
                    outline,
                )
                for eid in extra_ids:
                    node = self.gateway.call("get_node", envelope, node_id=eid)
                    hits.append(_hit_from_node(node))
            # A term lookup must stay local to its matched evidence.  Expanding
            # from an empty/weak seed through the parent graph turns a missing
            # term into an answer containing the entire outline.
            if ttype in {"lookup_term", "payment_card"}:
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
                        if edge.relation_type.value != "PARENT_OF"
                        for endpoint in (edge.from_node_id, edge.to_node_id)
                        if endpoint not in seed_ids and endpoint in known_ids
                    }
                    for eid in list(extra_graph_ids)[:12]:
                        node = self.gateway.call("get_node", envelope, node_id=eid)
                        hits.append(_hit_from_node(node))
            if not hits and record is not None:
                hits.extend(_lexical_hits(record, q))
            policy_flags = task.get("policy_flags") or {}
            vector_result = (
                self.vector_recall.recall(
                    record,
                    expand_query(q),
                    k=12,
                    filters={"source_role": task.get("source_role")}
                    if task.get("source_role")
                    else None,
                )
                if record is not None
                and policy_flags.get("use_vector") is True
                and ttype in {"compare", "cascade", "lookup_term", "unscoped"}
                else None
            )
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
            if record is not None and _is_responsibility_query(q):
                hits, coverage_groups = _expand_responsibility_groups(record, hits)
            if ttype in COMPARE_TYPES:
                filtered = _filter_relation_hits(q, hits)
                protected = [h for h in hits if str(h.get("node_id") or "") in set(exact_ids)]
                topic = _topic_hits(record, q) if record is not None else []
                candidates = _merge_hits(topic, filtered)
                # A comparison about a named topic (tax, penalty, value...) may
                # only use evidence whose node text mentions that topic. Without
                # this, a tax question was answered from penalty clauses.
                on_topic = _filter_topic_hits(q, candidates, record)
                if on_topic is not None:
                    candidates = on_topic
                    topic_ids = [str(h.get("node_id") or h.get("chunk_id")) for h in on_topic]
                hits = _drop_repeated_annex_headings(_merge_hits(protected, candidates), outline)
        except ToolBlocked:
            return {
                "resolved": False,
                "blocked": True,
                "hits": [],
                "outline_ids": [],
                "structured_keys": [],
                "logical_tables": [],
                "coverage_groups": [],
                "retrieval_trace": {"vector_status": "NOT_REQUESTED"},
            }

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
            "anchor_ids": _anchor_ids(
                deduped, [*exact_ids, *structured_ids, *topic_ids], outline
            )
            if ttype in COMPARE_TYPES
            else [],
            "outline_ids": [
                {"node_id": n["node_id"], "type": n["type"], "raw_label": n["raw_label"]}
                for n in outline
            ],
            "structured_keys": structured_keys_used,
            "relations": rels,
            "relation_edges": graph_edges,
            "relation_issues": graph_issues,
            "retrieval_trace": vector_result.trace
            if vector_result
            else {"vector_status": "NOT_REQUESTED"},
            "logical_tables": logical_tables,
            "coverage_groups": coverage_groups,
        }


def expand_logical_tables(
    gateway: ToolGateway,
    envelope: ToolEnvelope,
    query: str,
    *,
    max_rows: int = LOGICAL_TABLE_ROW_CAP,
    max_cells: int = LOGICAL_TABLE_CELL_CAP,
    max_pages: int = LOGICAL_TABLE_PAGE_CAP,
    max_seconds: float = LOGICAL_TABLE_TIME_CAP_SECONDS,
) -> list[dict[str, Any]]:
    """Fetch bounded, row-identified payment tables through the ACL gateway."""
    if not _asks_payment_schedule(query):
        return []
    tables = gateway.call("list_tables", envelope, dossier_id=envelope.auth.dossier_id) or []
    results = []
    for table in tables[:8]:
        table_id = str(table.get("table_id") or "")
        if not table_id:
            continue
        meta = gateway.call("get_table_meta", envelope, table_id=table_id)
        headers = [str(value or "") for value in meta.get("header", [])]
        folded = " ".join(_plain_query(value) for value in headers)
        if not any(token in folded for token in ("thanh toan", "payment", "milestone")):
            continue
        source_rows = max(0, int(meta.get("n_rows", 0)))
        n_cols = max(0, int(meta.get("n_cols", len(headers))))
        row_limit = min(source_rows, max_rows)
        if n_cols:
            row_limit = min(row_limit, max_cells // n_cols)
        elif source_rows:
            row_limit = 0
        started = time.monotonic()
        fetched = gateway.call("get_table_rows", envelope, table_id=table_id, start=0, end=row_limit)
        rows, pages, time_hit, page_hit = [], set(), False, False
        for source in fetched:
            if time.monotonic() - started > max_seconds:
                time_hit = True
                break
            row = {
                "row_index": int(source.get("row_index", len(rows))),
                "cells": [str(value) if value is not None else None for value in source.get("cells", [])[:n_cols]],
                "cell_citations": {},
            }
            for column, citation in (source.get("cell_citations") or {}).items():
                if int(column) >= len(row["cells"]):
                    continue
                page_id = citation.get("page_revision_id")
                if page_id:
                    pages.add(page_id)
                if len(pages) > max_pages:
                    page_hit = True
                    break
                row["cell_citations"][str(column)] = citation
            if page_hit:
                break
            rows.append(row)
        if time.monotonic() - started > max_seconds:
            time_hit = True
            rows = []
        reason = (
            "processing time cap reached" if time_hit else
            "page cap reached" if page_hit else
            "row or cell cap reached" if row_limit < source_rows else None
        )
        complete = not reason and len(rows) == source_rows
        results.append({
            "table_id": table_id,
            "header": headers,
            "source_role": meta.get("source_role"),
            "rows": rows,
            "coverage": {
                "complete": complete,
                "source_rows": source_rows,
                "processed_rows": len(rows),
                "source_cells": source_rows * n_cols,
                "processed_cells": sum(len(row["cells"]) for row in rows),
                "reason": reason,
            },
        })
    return results


def _asks_payment_schedule(query: str) -> bool:
    normalized = _plain_query(query)
    return any(term in normalized for term in ("thanh toan", "payment", "milestone", "cac dot"))


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
            same_annex = _same_annex_heading(wanted, normalized)
            if (
                normalized == wanted
                or normalized.startswith(wanted + " ")
                or normalized.startswith(wanted + ".")
                or normalized.startswith(wanted + ",")
                or same_annex
            ) and n["node_id"] not in ids:
                ids.append(n["node_id"])
    return ids


def _annex_heading_number(text: str) -> int | None:
    match = re.match(r"^phu luc\s+0*(\d+)\b", text)
    if match is None:
        return None
    return int(match.group(1))


def _same_annex_heading(wanted: str, label: str) -> bool:
    """Phụ lục 1 and PHỤ LỤC 01 name the same heading. Phụ lục 1 does not match 10."""

    wanted_number = _annex_heading_number(wanted)
    label_number = _annex_heading_number(label)
    return wanted_number is not None and label_number == wanted_number


def _drop_repeated_annex_headings(
    hits: list[dict[str, Any]], outline: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """A continued page repeats PHỤ LỤC 01. Keep the section, drop the copy."""

    by_id = {item.get("node_id"): item for item in outline}
    section_numbers: set[int] = set()
    for hit in hits:
        item = by_id.get(hit.get("node_id"))
        if not item or item.get("type") != "SECTION":
            continue
        number = _annex_heading_number(_plain_query(item.get("raw_label") or ""))
        if number is not None:
            section_numbers.add(number)
    if not section_numbers:
        return hits
    kept: list[dict[str, Any]] = []
    for hit in hits:
        item = by_id.get(hit.get("node_id"))
        if item and item.get("type") != "SECTION":
            number = _annex_heading_number(_plain_query(item.get("raw_label") or ""))
            if number is not None and number in section_numbers:
                continue
        kept.append(hit)
    return kept


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


_RESPONSIBILITY_QUERY_CUES = (
    "trach nhiem",
    "nghia vu",
    "phai thuc hien",
    "phai lam gi",
    "duties",
    "obligation",
    "responsibilit",
)
_RESPONSIBILITY_SECTION_CUES = (
    "quyen va nghia vu",
    "trach nhiem",
    "duties",
    "obligation",
    "responsibilit",
)


def _is_responsibility_query(query: str) -> bool:
    normalized = _plain_query(query)
    return any(cue in normalized for cue in _RESPONSIBILITY_QUERY_CUES)


def _expand_responsibility_groups(
    record: Any, hits: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[str]]:
    """Keep all children of a retrieved responsibility/obligation section.

    A vector hit commonly lands on 6.1 because it contains the word
    ``responsibility``.  6.2 and 6.3 are semantically part of the same named
    clause even when their text does not repeat that word.  Expand the section
    before the twelve-hit cap so L2 and deterministic fallback see the group.
    """

    nodes = {str(node.node_id): node for node in record.evidence_nodes()}
    children: dict[str, list[Any]] = {}
    for node in record.evidence_nodes():
        if node.parent_id:
            children.setdefault(str(node.parent_id), []).append(node)
    for group in children.values():
        group.sort(key=lambda node: node.order)

    parent_ids: list[str] = []
    for hit in hits:
        node = nodes.get(str(hit.get("node_id") or hit.get("chunk_id") or ""))
        if node is None:
            continue
        candidate_ids = [str(node.node_id)]
        if node.parent_id:
            candidate_ids.append(str(node.parent_id))
        for candidate_id in candidate_ids:
            candidate = nodes.get(candidate_id)
            if candidate is None or not children.get(candidate_id):
                continue
            label = _plain_query(" ".join((candidate.raw_label or "", candidate.text or "")))
            if any(cue in label for cue in _RESPONSIBILITY_SECTION_CUES):
                if candidate_id not in parent_ids:
                    parent_ids.append(candidate_id)
                break

    if not parent_ids:
        return hits, []

    by_id = {str(hit.get("node_id") or hit.get("chunk_id")): hit for hit in hits}
    grouped: list[dict[str, Any]] = []
    coverage: list[str] = []
    for parent_id in parent_ids[:4]:
        for child in children.get(parent_id, []):
            # A repeated page/header line can be attached to the previous
            # clause by OCR repair. It is structural furniture, not another
            # responsibility clause. Likewise, a SECTION/CLAUSE child is a
            # heading boundary, not a sibling obligation body.
            folded_label = _plain_query(child.raw_label or "")
            if (
                _is_running_furniture(child.raw_label or "")
                or "tiep theo" in folded_label
                or child.type in {"SECTION", "CLAUSE"}
            ):
                continue
            child_id = str(child.node_id)
            if child_id not in coverage:
                coverage.append(child_id)
            grouped.append(by_id.get(child_id) or _hit_from_node(child.model_dump()))
    return _merge_hits(grouped, hits), coverage


def _lexical_hits(record: Any, query: str) -> list[dict[str, Any]]:
    """Bounded local fallback over the already scoped canonical evidence tree."""
    return [hit for _, hit in _scored_lexical_hits(record, query)]


def _topic_hits(record: Any, query: str, limit: int = 3) -> list[dict[str, Any]]:
    """The few nodes that match the question's topic clearly better than the rest."""
    scored = _scored_lexical_hits(record, query)
    if not scored:
        return []
    best = scored[0][0]
    return [hit for score, hit in scored[:limit] if score >= 0.75 * best]


def _scored_lexical_hits(record: Any, query: str) -> list[tuple[float, dict[str, Any]]]:
    folded = _plain_query(expand_query(query))
    stop = {
        "hop", "dong", "dieu", "nao", "cac", "cua", "trong", "voi", "cho",
        "the", "and", "are", "what", "when", "this", "that", "with", "for",
    }
    # Words that name *where* to look (body vs annex) or the compare verb say
    # nothing about the topic; scored as topic terms they rank any clause that
    # merely mentions "phụ lục" above the clause the question is about.
    scope = {"so", "sanh", "than", "phu", "luc", "annex", "appendix", "giua", "va"}
    tokens = re.findall(r"\w+", folded)
    terms = [term for term in tokens if len(term) >= 3 and term not in stop | scope]
    # Adjacent content words ("tien do", "thuc hien") pin the topic far better
    # than their parts: "tien" alone also matches "ưu tiên".
    content = [token for token in tokens if token not in stop | scope and not token.isdigit()]
    phrases = [f"{left} {right}" for left, right in zip(content, content[1:])]
    scored: list[tuple[float, dict[str, Any]]] = []
    for node in record.evidence_nodes():
        blob = _plain_query(
            " ".join(
                str(value or "") for value in (node.raw_label, node.text, node.structured_value)
            )
        )
        # Whole words only: a substring match lets "than" hit every "thanh toán".
        score = float(sum(1 for term in terms if re.search(rf"\b{re.escape(term)}\b", blob)))
        score += 2 * sum(1 for phrase in phrases if re.search(rf"\b{re.escape(phrase)}\b", blob))
        if score and re.match(r"(?:dieu|phu luc)\s+\d", _plain_query(node.raw_label or "").strip()):
            # A matching heading carries its sub-clauses into the answer.
            score += 0.5
        if score:
            scored.append((score, _hit_from_node(node.model_dump())))
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[:12]


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
    # Topic cues name what the clause is about; timing cues only qualify it.
    # "Thời hạn thanh toán" asks about payment, so a confidentiality clause
    # that merely says "thời hạn" must not pass on the timing word alone.
    topic_cues = (
        "ngay lam viec",
        "working day",
        "thanh toan",
        "payment",
        "nghiem thu",
        "acceptance",
        "dinh nghia",
        "definition",
        "cham dut",
        "tien do",
    )
    timing_cues = ("thoi han", "hieu luc", "ngay ky", "tu ngay")
    wanted = [cue for cue in topic_cues if cue in normalized_query] or [
        cue for cue in timing_cues if cue in normalized_query
    ]
    if not wanted:
        return hits
    kept: list[dict[str, Any]] = []
    for hit in hits:
        citation = hit.get("citation") or {}
        evidence = _plain_query(
            " ".join(str(value or "") for value in (hit.get("value"), citation.get("text_span")))
        )
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
    named_annexes = {
        int(number)
        for number in re.findall(r"(?:phu luc|annex)\s+0*(\d+)", normalized_query)
    }
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
        mentioned = {
            int(number) for number in re.findall(r"(?:phu luc|annex)\s+0*(\d+)", evidence)
        }
        if named_annexes and mentioned and mentioned.isdisjoint(named_annexes):
            continue
        if any(left in evidence or right in evidence for left, right in cues):
            kept.append(hit)
    return kept


# (query cues, evidence cues), matched on accent-folded text at word boundaries.
TOPICS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "tax": (
        ("thue", "vat", "gtgt"),
        ("thue", "vat", "gtgt", "thue suat"),
    ),
    "penalty": (("phat", "penalty"), ("phat", "penalty")),
    "value": (
        ("gia tri", "gia hop dong", "contract value", "price"),
        ("gia", "gia tri", "value", "price", "vnd"),
    ),
    "working_day": (("ngay lam viec", "working day"), ("ngay lam viec", "working day")),
    "payment": (("thanh toan", "payment"), ("thanh toan", "payment")),
    "termination": (("cham dut", "terminate"), ("cham dut", "terminate", "termination")),
}
# "Mã số thuế" names a tax ID, not a tax rule.
_TAX_ID = re.compile(r"(?<!\w)(ma so thue|mst)(?!\w)")


def _has_cue(text: str, cues: tuple[str, ...]) -> bool:
    return any(re.search(rf"(?<!\w){re.escape(cue)}(?!\w)", text) for cue in cues)


def _filter_topic_hits(
    query: str, hits: list[dict[str, Any]], record: Any
) -> list[dict[str, Any]] | None:
    """Keep hits that mention every topic the query names; None when no topic."""

    plain_q = _TAX_ID.sub(" ", _plain_query(query))
    wanted = [ev for q_cues, ev in TOPICS.values() if _has_cue(plain_q, q_cues)]
    if not wanted:
        return None
    nodes = {n.node_id: n for n in record.evidence_nodes()} if record is not None else {}
    kept: list[dict[str, Any]] = []
    for hit in hits:
        node = nodes.get(str(hit.get("node_id") or ""))
        # Judge the node text that L2 will actually send to the model. A
        # semantic chunk's span can mention VAT while its parent node is only
        # "Article I. Định nghĩa"; matching on the span let such a node through.
        if node is not None:
            parts = (node.raw_label, node.text, node.structured_value)
        else:
            citation = hit.get("citation") or {}
            parts = (hit.get("value"), citation.get("text_span"))
        blob = " ".join(str(v or "") for v in parts)
        evidence = _TAX_ID.sub(" ", _plain_query(blob))
        if all(_has_cue(evidence, cues) for cues in wanted):
            kept.append(hit)
    return kept


def _anchor_ids(
    hits: list[dict[str, Any]], candidates: list[str], outline: list[dict[str, Any]]
) -> list[str]:
    """Sources a relation answer must cite: named, keyed or on-topic evidence.

    A container anchor (``Phụ lục 1``) is replaced by its descendants among the
    hits; when another anchor already sits inside it, it is dropped.
    """

    hit_ids = [str(h.get("node_id") or h.get("chunk_id")) for h in hits]
    parent = {str(n.get("node_id")): n.get("parent") for n in outline}

    def ancestors(nid: str) -> set[str]:
        seen: set[str] = set()
        cur = parent.get(nid)
        while cur and cur not in seen:
            seen.add(cur)
            cur = parent.get(cur)
        return seen

    base = [nid for nid in dict.fromkeys(candidates) if nid in hit_ids]
    anchors: list[str] = []
    for nid in base:
        inside = [h for h in hit_ids if h != nid and nid in ancestors(h)]
        if not inside:
            anchors.append(nid)
        elif not any(h in base for h in inside):
            anchors.extend(inside)
    return list(dict.fromkeys(anchors))


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
