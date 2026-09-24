"""Deterministic, source-grounded contractual event extraction."""

from __future__ import annotations

import hashlib
import re

from app.contracts.models import ContractEvent, Citation, ReviewState
from app.pipeline.ai1_snapshot_adapter import fold_for_match
from app.pipeline.citations import CitationResolver, quote_digest
from app.tools.store import DossierRecord


EVENT_RULES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("PARTY_DECLARATION", "Thông tin các bên", ("ben a", "ben b", "ten don vi")),
    ("SIGNING", "Ký kết hợp đồng", ("ky hop dong", "ky ket", "ngay ky")),
    ("SCOPE", "Phạm vi/đối tượng hợp đồng", ("pham vi", "mua ban hang hoa", "cung cap thiet bi", "cung cap dich vu")),
    ("PRICE", "Giá trị/đơn giá", ("gia tri", "don gia", "gia ca", "thanh tien")),
    ("PAYMENT", "Thanh toán", ("thanh toan", "tam ung", "dot thanh toan")),
    ("DELIVERY", "Giao hàng/bàn giao", ("giao hang", "giao nhan", "ban giao", "thoi diem giao")),
    ("ACCEPTANCE", "Nghiệm thu", ("nghiem thu", "bien ban nghiem thu", "chap nhan")),
    ("CLAIM", "Khiếu nại", ("khieu nai", "thoi han khieu nai")),
    ("WARRANTY", "Bảo hành", ("bao hanh", "su co", "sua chua")),
    ("NOTICE", "Thông báo", ("thong bao", "dia chi nhan", "email")),
    ("SUSPENSION_TERMINATION", "Tạm ngừng/chấm dứt", ("tam ngung", "cham dut", "don phuong")),
    ("FORCE_MAJEURE", "Bất khả kháng", ("bat kha khang",)),
    ("CONFIDENTIALITY", "Bảo mật", ("bao mat", "thong tin mat")),
    ("DISPUTE", "Giải quyết tranh chấp", ("tranh chap", "trong tai", "toa an")),
    ("AMENDMENT", "Sửa đổi/bổ sung", ("sua doi", "bo sung", "thay the", "dieu chinh")),
    ("EFFECTIVE_TERM", "Hiệu lực/thời hạn", ("hieu luc", "thoi han", "ke tu ngay", "tu ngay ky")),
)
DATE_RE = re.compile(r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})\b")
VI_DATE_RE = re.compile(r"\bngày\s+\d{1,2}\s+tháng\s+\d{1,2}\s+năm\s+\d{4}\b", re.I)
CLAUSE_RE = re.compile(r"\bdieu\s+(\d+(?:\.\d+)?)\b", re.I)
ROLE_RE = re.compile(r"\bben\s+([a-z])\b", re.I)
TRIGGER_RE = re.compile(r"\b(?:sau khi|truoc khi|ke tu|trong thoi han|neu|khi)\b[^.\n]{0,180}", re.I)


def extract_contract_events(record: DossierRecord) -> list[ContractEvent]:
    """Extract bounded event signals without inferring dates or legal effect."""

    digest = record.pins.source_snapshot_digest
    out: list[ContractEvent] = []
    seen: set[tuple[str, str]] = set()
    for node in sorted(record.evidence_nodes(), key=lambda item: (item.order, item.node_id)):
        raw = f"{node.raw_label}\n{node.text}".strip()
        folded = fold_for_match(raw)
        if not raw or node.type == "FIELD":
            continue
        citation = _citation(record, node.node_id)
        if citation is None:
            continue
        clause_match = CLAUSE_RE.search(folded)
        actor_roles = sorted({f"Bên {match.group(1).upper()}" for match in ROLE_RE.finditer(folded)})
        dates = sorted(set([*DATE_RE.findall(raw), *VI_DATE_RE.findall(raw)]))
        trigger_match = TRIGGER_RE.search(folded)
        for event_type, label, terms in EVENT_RULES:
            if not any(term in folded for term in terms):
                continue
            key = (node.node_id, event_type)
            if key in seen:
                continue
            seen.add(key)
            event_id = "event:" + hashlib.sha256(
                f"{digest}|{node.node_id}|{event_type}".encode("utf-8")
            ).hexdigest()[:24]
            state = ReviewState.PASS if node.status == "CONFIRMED" else ReviewState.NEEDS_REVIEW
            out.append(
                ContractEvent(
                    event_id=event_id,
                    event_type=event_type,
                    label=label,
                    subject=raw[:240],
                    actor_roles=actor_roles,
                    trigger=trigger_match.group(0)[:240] if trigger_match else None,
                    raw_text=raw[:1200],
                    clause_key=f"Điều {clause_match.group(1)}" if clause_match else None,
                    date_signals=dates,
                    source_node_id=node.node_id,
                    citation=citation.model_copy(deep=True),
                    review_state=state,
                )
            )
    return out[:256]


def _citation(record: DossierRecord, node_id: str) -> Citation | None:
    node = next((item for item in record.evidence_nodes() if item.node_id == node_id), None)
    if node is None:
        return None
    page = next((item for item in record.pages if item.page_revision_id == node.page_revision_id), None)
    text = (node.text or node.raw_label or "")[:240]
    start = page.text.find(text) if page and text else -1
    citation = Citation(
        node_id=node.node_id,
        page_revision_id=node.page_revision_id or "",
        bbox=list(node.bbox),
        text_span=text,
        source_file_id=node.source_file_id,
        page=page.page_number if page else (node.page_range[0] if node.page_range else None),
        page_range=list(node.page_range),
        line_ids=list(node.source_line_ids),
        char_start=start if start >= 0 else None,
        char_end=(start + len(text)) if start >= 0 else None,
        source_hash=page.source_hash if page else None,
        quote_sha256=quote_digest(text),
        geometry_available=bool(node.bbox),
    )
    # Event extraction is advisory. Do not create a new review issue for a
    # structural node whose span crosses page revisions or whose OCR lines
    # cannot be verified on the selected page; the underlying node remains
    # available through the normal evidence tree.
    if not CitationResolver(record.pages, record.tables, record.evidence_nodes()).verify(citation).valid:
        return None
    return citation
