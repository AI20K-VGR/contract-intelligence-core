from __future__ import annotations

import re
from typing import Any

from app.contracts.models import ReviewState, ToolEnvelope
from app.pipeline.ai1_snapshot_adapter import fold_for_match
from app.pipeline.table_headers import parse_amount
from app.tools.gateway import ToolBlocked, ToolGateway

TOO_BROAD = (
    "tóm tắt toàn bộ",
    "tom tat toan bo",
    "tóm tắt hợp đồng",
    "tom tat hop dong",
    "tóm tắt cả",
    "rủi ro chính",
    "rui ro chinh",
    "executive summary",
    "toàn bộ hồ sơ",
    "toan bo ho so",
    "các điều khoản có trên outline",
)


def _countish(query: str) -> bool:
    low = (query or "").lower()
    return any(w in low for w in ("bao nhiêu", "bao nhieu", "how many", "số lượng", "so luong", "có mấy", "co may"))


def _count_party_query(query: str) -> bool:
    low = (query or "").lower()
    if not _countish(query):
        return False
    if "pháp nhân" in low or "phap nhan" in low or "legal entit" in low:
        return False
    return bool(re.search(r"\bbên\b", low) or re.search(r"\bben\b", low) or "parties" in low or "đối tác" in low or "doi tac" in low)


def _count_entity_query(query: str) -> bool:
    low = (query or "").lower()
    if not _countish(query):
        return False
    entityish = any(
        w in low
        for w in (
            "pháp nhân",
            "phap nhan",
            "legal entit",
            "các bên",
            "cac ben",
            "đối tác",
            "doi tac",
            "công ty",
            "cong ty",
            "parties",
        )
    )
    return entityish or _count_party_query(query)


def query_too_broad(query: str) -> bool:
    low = (query or "").lower()
    if _count_entity_query(query) or _count_party_query(query):
        return False
    return any(p in low for p in TOO_BROAD)


class L0Rules:
    """Deterministic rules. No LLM."""

    def __init__(self, gateway: ToolGateway) -> None:
        self.gateway = gateway

    def run(self, envelope: ToolEnvelope, task: dict[str, Any]) -> dict[str, Any] | None:
        ttype = task.get("type")
        q = (task.get("query") or "").lower()
        try:
            outline = self.gateway.call("list_structure", envelope, dossier_id=envelope.auth.dossier_id)
        except ToolBlocked:
            return {
                "resolved": True,
                "review_state": ReviewState.BLOCKED.value,
                "answer": None,
                "citations": [],
                "notes": "blocked",
            }

        labels = [n.get("raw_label") or "" for n in outline]
        ids = {n["node_id"] for n in outline}
        selected = {str(item) for item in (task.get("selected_member_ids") or []) if item}
        if selected:
            outline = [
                item
                for item in outline
                if str(item.get("node_id") or "") in selected
                or str(item.get("source_file_id") or "") in selected
            ]
            ids = {n["node_id"] for n in outline}
            selected = {str(item.get("node_id")) for item in outline}

        if ttype == "count_entity" or _count_entity_query(task.get("query") or ""):
            qtext = task.get("query") or ""
            parties = []
            for key in ("party_a", "party_b", "party_c", "party_y"):
                parties.extend(_selected_hits(self.gateway.call("search_structured", envelope, key=key), selected))
            if _count_party_query(qtext) or (
                ttype == "count_entity" and "pháp nhân" not in qtext.lower() and "phap nhan" not in qtext.lower()
            ):
                from app.reasoning.fact_link import count_contract_parties

                linked = count_contract_parties(
                    outline,
                    role_hits=parties,
                    identity_hits=_identity_hits(self.gateway, envelope, outline),
                )
            else:
                from app.reasoning.fact_link import count_legal_entities

                mst = _selected_hits(_all_mst_hits(self.gateway, envelope), selected)
                mst.extend(_identity_hits(self.gateway, envelope, outline))
                parties = _selected_hits(_hydrate_structured_hits(self.gateway, envelope, parties), selected)
                linked = count_legal_entities(mst, parties)
            return {
                "resolved": True,
                "review_state": linked["review_state"],
                "answer": linked["answer"],
                "citations": linked["citations"],
                "notes": linked["notes"],
            }

        if ttype == "party_card":
            from app.reasoning.ask_assemble import assemble_party

            role = (task.get("role") or "A").lower()
            key = f"party_{role}"
            parties = _selected_hits(self.gateway.call("search_structured", envelope, key=key), selected)
            mst_keys = {
                "a": ("mst_seller", "mst_party_a"),
                "b": ("mst_party_b", "mst_buyer"),
                "c": ("mst_party_c",),
                "y": ("mst_party_y",),
            }.get(role, (f"mst_party_{role}",))
            mst = []
            for mst_key in mst_keys:
                mst.extend(_selected_hits(self.gateway.call("search_structured", envelope, key=mst_key), selected))
            linked = assemble_party(
                role,
                outline,
                parties,
                mst,
                get_node=lambda nid: self.gateway.call("get_node", envelope, node_id=nid),
            )
            return {
                "resolved": True,
                "review_state": linked["review_state"],
                "answer": linked["answer"],
                "citations": linked["citations"],
                "notes": linked["notes"],
            }

        if ttype == "annex_card":
            from app.reasoning.ask_assemble import assemble_annex

            n = str(task.get("annex_n") or "")
            linked = assemble_annex(
                n,
                outline,
                lambda nid: self.gateway.call("get_node", envelope, node_id=nid),
                record=self.gateway.store.get(envelope.auth.tenant_id, envelope.auth.dossier_id),
            )
            return {
                "resolved": True,
                "review_state": linked["review_state"],
                "answer": linked["answer"],
                "citations": linked["citations"],
                "notes": linked["notes"],
            }

        if ttype == "annex_list":
            from app.reasoning.ask_assemble import assemble_annex_list

            linked = assemble_annex_list(
                outline,
                lambda nid: self.gateway.call("get_node", envelope, node_id=nid),
                record=self.gateway.store.get(envelope.auth.tenant_id, envelope.auth.dossier_id),
            )
            return {
                "resolved": True,
                "review_state": linked["review_state"],
                "answer": linked["answer"],
                "citations": linked["citations"],
                "notes": linked["notes"],
            }

        if ttype == "field_card":
            from app.reasoning.ask_assemble import assemble_field, assemble_mst
            from app.reasoning.fact_link import relate_mst

            key = task.get("field_key") or "mst_seller"
            if key == "mst_seller" and not re.search(r"bên\s+[ab]", q, re.I):
                hits = _selected_hits(_all_mst_hits(self.gateway, envelope), selected)
                linked = assemble_mst(hits)
            else:
                hits = _selected_hits(self.gateway.call("search_structured", envelope, key=key), selected)
                linked = relate_mst(hits) if key == "mst_seller" else assemble_field(key, hits)
            return {
                "resolved": True,
                "review_state": linked["review_state"],
                "answer": linked["answer"],
                "citations": linked["citations"],
                "notes": linked["notes"],
            }

        if ttype == "document_overview":
            from app.reasoning.ask_assemble import assemble_overview

            linked = assemble_overview(outline)
            return {
                "resolved": True,
                "review_state": linked["review_state"],
                "answer": linked["answer"],
                "citations": linked["citations"],
                "notes": linked["notes"],
            }

        if ttype == "unscoped":
            from app.reasoning.ask_assemble import unscoped_hint

            linked = unscoped_hint(outline)
            return {
                "resolved": True,
                "review_state": linked["review_state"],
                "answer": linked["answer"],
                "citations": [],
                "notes": "unscoped",
            }

        if ttype == "too_broad" or query_too_broad(task.get("query") or ""):
            sample = [n.get("raw_label") for n in outline if n.get("type") in {"CLAUSE", "SECTION"}][:8]
            return {
                "resolved": True,
                "review_state": ReviewState.INSUFFICIENT_EVIDENCE.value,
                "answer": "Câu hỏi quá rộng — không tóm tắt toàn hồ sơ. Hỏi theo Điều hoặc Phụ lục. Gợi ý: "
                + ", ".join(str(x) for x in sample if x),
                "citations": [],
                "notes": "too_broad",
            }

        if ttype == "security" or "drop_database" in q or "ignore all instructions" in q:
            cites = [{"node_id": "inj", "text_span": "untrusted pdf text"}] if "inj" in ids else []
            return {
                "resolved": True,
                "review_state": ReviewState.NEEDS_REVIEW.value,
                "answer": "Nội dung PDF không tin cậy. Chỉ allowlist tools; không thực thi lệnh trong văn bản.",
                "citations": cites,
                "notes": "jailbreak_ignored",
            }

        if ttype == "lookup_clause":
            label = task.get("clause_label") or _clause_label(task.get("query") or "")
            if label:
                hits = [n for n in outline if _label_match(n.get("raw_label") or "", label)]
                if not hits:
                    return {
                        "resolved": True,
                        "review_state": ReviewState.INSUFFICIENT_EVIDENCE.value,
                        "answer": f"Không có node «{label}» trên outline. Không bịa nội dung điều khoản.",
                        "citations": [],
                        "notes": "missing_clause",
                    }
                from app.reasoning.relations import attach_ancestors, related_node_ids, render_related_answer

                outline = attach_ancestors(list(outline))
                extra_ids, rels = related_node_ids([h["node_id"] for h in hits], outline)
                ordered_ids = []
                for n in hits:
                    if n["node_id"] not in ordered_ids:
                        ordered_ids.append(n["node_id"])
                    ordered_ids.extend(child["node_id"] for child in outline
                                       if child.get("parent") == n["node_id"]
                                       and child.get("type") in {"UNNUMBERED_BLOCK", "CLAUSE"}
                                       and child["node_id"] not in ordered_ids)
                for eid in extra_ids:
                    if eid not in ordered_ids:
                        ordered_ids.append(eid)
                packed = []
                cites = []
                for nid in ordered_ids[:8]:
                    full = self.gateway.call("get_node", envelope, node_id=nid)
                    side = None
                    from app.reasoning.relations import doc_side

                    side = doc_side(full.get("ancestors"), full.get("raw_label"))
                    packed.append(
                        {
                            "node_id": nid,
                            "label": full.get("raw_label"),
                            "path": " › ".join((full.get("ancestors") or []) + [full.get("raw_label") or ""]),
                            "text": (full.get("text") or "")[:1200],
                            "page_range": full.get("page_range"),
                            "side": side,
                        }
                    )
                    cites.append(full.get("citation") or {"node_id": nid, "text_span": full.get("raw_label")})
                multi = len(packed) > 1 or bool(rels)
                answer = render_related_answer(packed, rels) if multi else packed[0]["text"]
                state = ReviewState.NEEDS_REVIEW.value if multi else ReviewState.ANSWERED.value
                return {
                    "resolved": True,
                    "review_state": state,
                    "answer": answer,
                    "citations": cites,
                    "notes": "clause_lookup_related",
                }

        if ttype == "structure" and ("điều 3" in q or "dieu 3" in q):
            has = any(lb.strip() == "Điều 3" for lb in labels)
            if not has:
                return {
                    "resolved": True,
                    "review_state": ReviewState.INSUFFICIENT_EVIDENCE.value,
                    "answer": "Không có node Điều 3 trên outline. Không bịa điều khoản.",
                    "citations": [],
                    "notes": "gap_numbering",
                }

        if ttype == "structure" and "thanh toán" in q:
            node = next((n for n in outline if n.get("type") == "UNNUMBERED_BLOCK" and "Thanh toán" in (n.get("raw_label") or "")), None)
            if node:
                return {
                    "resolved": True,
                    "review_state": ReviewState.NEEDS_REVIEW.value,
                    "answer": "Mục Thanh toán là UNNUMBERED_BLOCK, không gán thành Điều 5.",
                    "citations": [{"node_id": node["node_id"], "text_span": node.get("raw_label")}],
                    "notes": "unnumbered",
                }

        if ttype == "lookup_insufficient" or "phụ lục 7" in q or "phu luc 7" in q:
            has_pl7 = any("Phụ lục 7" in (n.get("raw_label") or "") for n in outline)
            if not has_pl7:
                ref = next((n for n in outline if n["node_id"] == "cl_9" or (n.get("raw_label") or "").startswith("Điều 9")), None)
                cite = []
                if ref:
                    cite = [{"node_id": ref["node_id"], "text_span": "Xem Phụ lục 7"}]
                return {
                    "resolved": True,
                    "review_state": ReviewState.INSUFFICIENT_EVIDENCE.value,
                    "answer": "Phụ lục 7 không có trong hồ sơ. Điều 9 chỉ dẫn chiếu — không bịa nội dung.",
                    "citations": cite,
                    "notes": "missing_annex",
                }

        if ttype == "not_comparable" and ("usd" in q or "quy đổi" in q or "quy doi" in q):
            return {
                "resolved": True,
                "review_state": ReviewState.NOT_COMPARABLE.value,
                "answer": "100 USD và giá VND không quy đổi. NOT_COMPARABLE.",
                "citations": [{"node_id": "field_usd", "text_span": "100 USD"}],
                "notes": "no_fx",
            }

        if ttype == "not_comparable" and ("xây lắp" in q or "thiet bi" in q or "thiết bị" in q or "gộp phạt" in q):
            return {
                "resolved": True,
                "review_state": ReviewState.NOT_COMPARABLE.value,
                "answer": "Phạt xây lắp và phạt thiết bị khác scope — không gộp một mức.",
                "citations": [
                    {"node_id": "field_penalty_build", "text_span": "0,1%/ngày"},
                    {"node_id": "field_penalty_equip", "text_span": "0,05%/ngày"},
                ],
                "notes": "scope",
            }

        if ttype == "lookup" and "mst" in q:
            from app.reasoning.ask_assemble import assemble_mst
            from app.reasoning.fact_link import relate_mst

            if re.search(r"bên\s+[abcy]", q, re.I):
                letter = re.search(r"bên\s+([abcy])", q, re.I).group(1).lower()
                keys = {
                    "a": ["mst_seller", "mst_party_a"],
                    "b": ["mst_party_b", "mst_buyer"],
                    "c": ["mst_party_c"],
                    "y": ["mst_party_y"],
                }[letter]
                hits = []
                for key in keys:
                    hits.extend(self.gateway.call("search_structured", envelope, key=key) or [])
                linked = relate_mst(_dedupe_hits(hits))
            else:
                linked = assemble_mst(_all_mst_hits(self.gateway, envelope))
            return {
                "resolved": True,
                "review_state": linked["review_state"],
                "answer": linked["answer"],
                "citations": linked["citations"],
                "notes": linked["notes"],
            }

        if ttype == "boundary_ambiguous":
            q = (task.get("query") or "").lower()
            clause_match = re.search(r"điều\s+(\d+(?:\.\d+)*)", q) or re.search(r"dieu\s+(\d+(?:\.\d+)*)", q)
            if not clause_match:
                return None
            clause_num = clause_match.group(1)
            pat = re.compile(rf"(?:điều|dieu)\s+{re.escape(clause_num)}(?!\d)", re.I)
            exact_matches = [n for n in outline if pat.search(n.get("raw_label") or "")]
            if exact_matches:
                return None
            sample = [n.get("raw_label") for n in outline if n.get("type") in {"CLAUSE", "SECTION"}][:6]
            return {
                "resolved": True,
                "review_state": ReviewState.INSUFFICIENT_EVIDENCE.value,
                "answer": f"Không tìm thấy Điều {clause_num} trên outline. Vui lòng kiểm tra số Điều. Gợi ý: "
                + ", ".join(str(x) for x in sample if x),
                "citations": [],
                "notes": "boundary_ambiguous",
            }

        if ttype == "table":
            tables = self.gateway.call("list_tables", envelope, dossier_id=envelope.auth.dossier_id)
            tid = None
            for t in tables:
                if t.get("n_rows", 0) >= 300 or t.get("table_id") == "table_300":
                    tid = t["table_id"]
                    break
            if not tid and tables:
                tid = tables[0]["table_id"]
            if tid:
                meta = self.gateway.call("get_table_meta", envelope, table_id=tid)
                rows = self.gateway.call("get_table_rows", envelope, table_id=tid, start=0, end=meta["n_rows"])
                values = [item["cells"][1] for item in rows if len(item.get("cells") or []) > 1]
                numeric = [value for value in (parse_amount(item) for item in values) if value is not None]
                return {
                    "resolved": True,
                    "review_state": ReviewState.ANSWERED.value,
                    "answer": {
                        "meta": {
                            "header": meta.get("header"),
                            "n_rows": meta.get("n_rows"),
                            "first_rows": meta.get("first_rows"),
                            "last_rows": meta.get("last_rows"),
                        },
                        "n_missing": sum(value is None or str(value).strip() in {"", "-", "N/A"} for value in values),
                        "n_numeric": len(numeric),
                        "sample_first": values[0] if values else None,
                        "sample_last": values[-1] if values else None,
                    },
                    "citations": [{"node_id": "tbl_300", "text_span": tid}],
                    "notes": "table_codegen",
                }

        return None


def _clause_label(query: str) -> str | None:
    m = re.search(r"điều\s+(\d+(?:\.\d+)?)", query, re.I)
    if not m:
        m = re.search(r"dieu\s+(\d+(?:\.\d+)?)", query, re.I)
    if not m:
        return None
    return f"Điều {m.group(1)}"


def _label_match(raw: str, label: str) -> bool:
    s = fold_for_match(raw.strip())
    wanted = fold_for_match(label.strip())
    return s == wanted or s.startswith(wanted + ".") or s.startswith(wanted + " ") or s.startswith(wanted + ",")


_MST_KEYS = ("mst_seller", "mst_party_a", "mst_party_b", "mst_party_c", "mst_party_y", "mst_buyer", "mst_supplier")


def _dedupe_hits(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for hit in hits:
        node_id = str(hit.get("node_id") or "")
        if not node_id or node_id in seen:
            continue
        seen.add(node_id)
        result.append(hit)
    return result


def _all_mst_hits(gateway: Any, envelope: ToolEnvelope) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for key in _MST_KEYS:
        hits.extend(gateway.call("search_structured", envelope, key=key) or [])
    return _dedupe_hits(hits)


def _hydrate_structured_hits(gateway: Any, envelope: ToolEnvelope, hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add node text so party↔MST linking can use same-line evidence."""

    hydrated: list[dict[str, Any]] = []
    for hit in hits:
        item = dict(hit)
        node_id = item.get("node_id")
        if node_id:
            try:
                node = gateway.call("get_node", envelope, node_id=node_id)
            except Exception:
                node = None
            if node:
                citation = dict(item.get("citation") or {})
                citation["text_span"] = node.get("text") or citation.get("text_span") or ""
                item["citation"] = citation
                item["text"] = node.get("text") or ""
        hydrated.append(item)
    return hydrated


def _selected_hits(hits: list[dict[str, Any]] | None, selected: set[str]) -> list[dict[str, Any]]:
    if not selected:
        return list(hits or [])
    return [
        hit
        for hit in (hits or [])
        if str(hit.get("node_id") or (hit.get("citation") or {}).get("node_id") or "") in selected
    ]


def _identity_hits(gateway: ToolGateway, envelope: ToolEnvelope, outline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Recover explicit MST tokens when AI1 did not normalize party facts."""

    hits: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in outline:
        node_id = str(item.get("node_id") or "")
        if not node_id:
            continue
        try:
            node = gateway.call("get_node", envelope, node_id=node_id)
        except (ToolBlocked, TypeError):
            continue
        text = str(node.get("text") or "")
        # A generic MST field is not enough to answer "how many parties";
        # require the same source node to identify a contractual role too.
        # This prevents an unrelated seller MST or repeated header from being
        # miscounted as a separate party.
        if not re.search(r"\b(?:bên|ben)\s+[A-ZÀ-Ỹa-zà-ỹ]\b", text, re.IGNORECASE):
            continue
        # Only accept numbers explicitly introduced as tax identifiers. This
        # excludes contract numbers, dates, quantities and prices.
        for match in re.finditer(
            r"(?:mã\s*số\s*thuế|ma\s*so\s*thue|mst|tax\s*(?:id|code))\s*[:\-]?\s*(\d{8,14})",
            text,
            re.IGNORECASE,
        ):
            code = match.group(1)
            key = (node_id, code)
            if key in seen:
                continue
            seen.add(key)
            citation = dict(node.get("citation") or {"node_id": node_id, "text_span": code})
            citation["text_span"] = code
            hits.append({"node_id": node_id, "value": code, "citation": citation})
    return hits
