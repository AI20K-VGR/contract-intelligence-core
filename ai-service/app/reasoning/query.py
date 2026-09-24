from __future__ import annotations

import re
import unicodedata
from typing import Any

from app.contracts.models import LifecycleState, ReviewState, ToolEnvelope
from app.llm.client import NineRouterClient
from app.pipeline.ai1_snapshot_adapter import fold_for_match
from app.reasoning.l0_rules import query_too_broad
from app.reasoning.stack import FourLayerReasoner
from app.tools.gateway import ToolBlocked, ToolGateway
from app.tools.store import InMemorySnapshotStore


def classify_ask(text: str) -> dict[str, Any]:
    q = (text or "").strip()
    low = q.lower()
    spec: dict[str, Any] = {
        "id": "ask",
        "query": q,
        "must_cite": [],
        "forbidden": ["legal_winner", "full_pdf_dump"],
    }
    folded = fold_for_match(q)
    relationship_text = _plain_query(q)
    money_cues = (
        "phi ",
        "tuyen dung",
        "so tien",
        "bao nhieu tien",
        "gia tri",
        "don gia",
        "thanh tien",
        "trieu",
        "vnd",
        "usd",
    )
    if any(cue in folded for cue in money_cues):
        spec["type"] = "raw_fact_check"
        spec["fact_intent"] = "money"
        return spec
    relation_cues = (
        "moi quan he",
        "lien quan",
        "anh huong",
        "dan chieu",
        "sua",
        "thay the",
        "dinh nghia",
        "cascade",
        "so sanh",
        "khac nhau",
    )
    has_source_reference = bool(
        re.search(r"\bdieu\s+\d", relationship_text)
        or re.search(r"\b(?:phu luc|annex)\s+\d", relationship_text)
        or "hop dong" in relationship_text
    )
    if any(cue in relationship_text for cue in relation_cues) and has_source_reference:
        clause_labels = [f"Điều {match.group(1)}" for match in re.finditer(r"\bdieu\s+(\d+(?:\.\d+)?)", relationship_text)]
        annex_numbers = [match.group(1) for match in re.finditer(r"\b(?:phu luc|annex)\s+(\d+)", relationship_text)]
        spec["type"] = "cascade" if any(cue in relationship_text for cue in ("anh huong", "dinh nghia", "cascade")) else "compare"
        spec["focus_clause_labels"] = clause_labels
        spec["annex_numbers"] = annex_numbers
        spec["relation_intent"] = relationship_text
        return spec
    folded_party = re.search(r"\b(?:ben|party)\s+([abcy])\b", folded)
    if folded_party:
        spec["type"] = "party_card"
        spec["role"] = folded_party.group(1).upper()
        return spec
    folded_clause = re.search(r"\bdieu\s+(\d+(?:\.\d+)?)", folded)
    if folded_clause:
        spec["type"] = "lookup_clause"
        spec["clause_label"] = f"Điều {folded_clause.group(1)}"
        return spec
    folded_annex = re.search(r"\b(?:phu luc|annex)\s+(\d+)", folded)
    if folded_annex:
        spec["type"] = "annex_card"
        spec["annex_n"] = folded_annex.group(1)
        return spec
    if "phu luc" in folded and any(
        cue in folded for cue in ("co ", "nao", "danh sach", "bao nhieu", "may")
    ):
        spec["type"] = "annex_list"
        return spec
    if query_too_broad(q):
        spec["type"] = "too_broad"
        return spec
    if any(
        phrase in low
        for phrase in (
            "nói về gì",
            "noi ve gi",
            "nội dung chính",
            "noi dung chinh",
            "đối tượng hợp đồng",
            "doi tuong hop dong",
            "mục đích hợp đồng",
            "muc dich hop dong",
        )
    ) or ("hợp đồng" in low and any(word in low for word in ("nội dung", "noi dung", "chính", "chinh"))):
        spec["type"] = "document_overview"
        spec["overview_mode"] = "bounded"
        return spec
    if _count_entity_ask(low):
        spec["type"] = "count_entity"
        return spec
    m_party = re.search(r"\b(?:bên|ben)\s+([abcy])\b", low) or re.search(r"\bparty\s+([ab])\b", low)
    if m_party:
        spec["type"] = "party_card"
        spec["role"] = m_party.group(1).upper()
        return spec
    if any(w in low for w in ("so sánh", "khác nhau", "ảnh hưởng", "cascade")):
        spec["type"] = "compare"
        return spec
    m_cl = re.search(r"điều\s+(\d+(?:\.\d+)?)", low) or re.search(r"dieu\s+(\d+(?:\.\d+)?)", low)
    if m_cl:
        spec["type"] = "lookup_clause"
        spec["clause_label"] = f"Điều {m_cl.group(1)}"
        return spec
    m_pl = re.search(r"(?:phụ lục|phu luc|annex)\s+(\d+)", low)
    if m_pl:
        spec["type"] = "annex_card"
        spec["annex_n"] = m_pl.group(1)
        return spec
    if "phu luc" in folded and any(
        cue in folded for cue in ("co ", "nao", "danh sach", "bao nhieu", "may")
    ):
        spec["type"] = "annex_list"
        return spec
    if "mst" in low or "mã số thuế" in low or "tax id" in low:
        spec["type"] = "field_card"
        spec["field_key"] = "mst_seller"
        return spec
    if any(w in low for w in ("giá trị", "gia tri", "giá hợp đồng", "contract value")) or "gia tri" in folded:
        spec["type"] = "field_card"
        spec["field_key"] = "contract_value"
        return spec
    if any(w in low for w in ("phạt", "penalty")):
        spec["type"] = "field_card"
        spec["field_key"] = "penalty"
        return spec
    if any(
        w in low
        for w in (
            "ngày làm việc",
            "working day",
            "thanh toán",
            "nghiệm thu",
            "định nghĩa",
            "acceptance",
        )
    ) or any(w in folded for w in ("thoi han", "hieu luc", "ngay ky", "tu ngay")):
        spec["type"] = "lookup_term"
        return spec
    spec["type"] = "unscoped"
    return spec


def _count_entity_ask(low: str) -> bool:
    from app.reasoning.l0_rules import _count_entity_query

    return _count_entity_query(low)


def _plain_query(value: str) -> str:
    text = unicodedata.normalize("NFD", value.casefold())
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return text.replace("đ", "d")


class QueryRouter:
    def __init__(self, store: InMemorySnapshotStore, gateway: ToolGateway, llm: NineRouterClient | None = None) -> None:
        self.store = store
        self.gateway = gateway
        self.llm = llm
        self.stack = FourLayerReasoner(gateway, llm)

    def query(self, envelope: ToolEnvelope, text: str, task: dict[str, Any] | None = None) -> dict[str, Any]:
        rec = self.store.get(envelope.auth.tenant_id, envelope.auth.dossier_id)
        if rec is None:
            return {"review_state": ReviewState.BLOCKED.value, "hits": []}
        if rec.lifecycle != LifecycleState.ACTIVE:
            return {"review_state": ReviewState.BLOCKED.value, "hits": []}
        spec = task or classify_ask(text)
        try:
            return self.stack.run(envelope, spec)
        except ToolBlocked:
            return {"review_state": ReviewState.BLOCKED.value, "hits": []}
