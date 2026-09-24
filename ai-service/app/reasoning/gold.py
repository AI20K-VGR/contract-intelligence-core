from __future__ import annotations

from typing import Any

from app.contracts.models import StructuralNode


LABEL_CITE: dict[str, str] = {
    "cl_9": "Điều 9",
    "cl_1_1": "Điều 1.1",
    "cl_8": "Điều 8",
    "cl_5_body": "Điều 5",
    "a_5_pl1": "Điều 5",
    "a_5_pl2": "Điều 5",
    "pl13_def": "Định nghĩa mới",
    "unnum_pay": "Thanh toán",
}


def node_by_label(nodes: list[StructuralNode], label: str) -> StructuralNode | None:
    for n in nodes:
        raw = (n.raw_label or "").strip()
        if raw == label or raw.startswith(label + " ") or raw.startswith(label + "."):
            return n
    return None


def remap_must_cite(must: list[str], nodes: list[StructuralNode]) -> list[str]:
    out: list[str] = []
    ids = {n.node_id for n in nodes}
    for mid in must:
        if mid in ids:
            out.append(mid)
            continue
        lab = LABEL_CITE.get(mid)
        if lab:
            n = node_by_label(nodes, lab)
            if n:
                out.append(n.node_id)
                continue
        out.append(mid)
    return out


def tasks_from_outline(nodes: list[StructuralNode], fixture_tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    labels = {(n.raw_label or "").strip() for n in nodes}
    has_dieu = {lb for lb in labels if lb.startswith("Điều ")}
    has_pl = {lb for lb in labels if lb.startswith("Phụ lục ")}
    mapped = []
    for t in fixture_tasks:
        t = dict(t)
        t["must_cite"] = remap_must_cite(t.get("must_cite") or [], nodes)
        mapped.append(t)
    extra: list[dict[str, Any]] = []
    if any(lb.startswith("Điều 5") for lb in has_dieu):
        extra.append(
            {
                "id": "T-DIEU5-LABEL",
                "type": "compare",
                "query": "So sánh các node nhãn Điều 5",
                "expected_state": "NEEDS_REVIEW",
                "layers": ["L1", "L2", "L3"],
                "must_cite": [n.node_id for n in nodes if (n.raw_label or "").startswith("Điều 5")][:4],
                "forbidden": ["legal_winner", "precedence"],
            }
        )
    return mapped + extra


def adhoc_tasks(nodes: list[StructuralNode]) -> list[dict[str, Any]]:
    keys = {n.structured_key for n in nodes if n.structured_key}
    text = "\n".join(f"{n.raw_label} {n.text}" for n in nodes).casefold()
    has_party = bool(keys & {"party_a", "party_b", "party_c", "party_y"})
    has_mst = bool(keys & {"mst_seller", "mst_party_a", "mst_party_b", "mst_party_c", "mst_party_y", "mst_buyer", "mst_supplier"})
    has_term = any(
        term in text
        for term in (
            "ngày làm việc",
            "ngay lam viec",
            "working day",
            "thanh toán",
            "thanh toan",
            "payment",
            "nghiệm thu",
            "nghiem thu",
            "acceptance",
        )
    )
    has_relation_source = any(
        term in text
        for term in (
            "phụ lục",
            "phu luc",
            "annex",
            "định nghĩa",
            "dinh nghia",
            "defined as",
            "shall mean",
            "thanh toán",
            "thanh toan",
        )
    )
    tasks: list[dict[str, Any]] = []
    if has_mst:
        mst_keys = {"mst_seller", "mst_party_a", "mst_party_b", "mst_party_c", "mst_party_y", "mst_buyer", "mst_supplier"}
        mst_nodes = [n for n in nodes if n.structured_key in mst_keys]
        tasks.append(
            {
                "id": "T-MST",
                "kind": "product",
                "applicable": True,
                "type": "lookup",
                "query": "MST trên hồ sơ là gì?",
                "expected_state": "ANSWERED" if len({n.structured_value for n in mst_nodes}) == len(mst_nodes) else "NEEDS_REVIEW",
                "expected_reason": "Trả tất cả MST có vai; conflict cùng vai cần rà soát.",
                "layers": ["L0", "L3"],
                "must_cite": [n.node_id for n in mst_nodes][:8],
                "forbidden": ["legal_winner"],
            }
        )
    dieu = [n for n in nodes if (n.raw_label or "").startswith("Điều ")]
    if dieu:
        n = dieu[0]
        tasks.append(
            {
                "id": "T-CLAUSE-LABEL",
                "kind": "product",
                "applicable": True,
                "type": "lookup_clause",
                "query": f"{n.raw_label} nói gì?",
                "clause_label": n.raw_label.split(",")[0].strip(),
                "expected_state": "ANSWERED",
                "layers": ["L0", "L3"],
                "must_cite": [n.node_id],
                "forbidden": ["legal_winner"],
            }
        )
    tasks.append(
        {
            "id": "T-PARA",
            "kind": "product" if has_term else "probe",
            "applicable": has_term,
            "type": "lookup_term",
            "query": "How are working days defined versus payment after acceptance?",
            "expected_state": "ANSWERED" if has_term else "INSUFFICIENT_EVIDENCE",
            "expected_reason": "Không có term ngày làm việc/thanh toán thì không được lấy node không liên quan.",
            "layers": ["L1", "L3"],
            "must_cite": [],
            "forbidden": ["full_pdf_dump"],
        }
    )
    tasks.append(
        {
            "id": "T-SUMMARY",
            "kind": "probe",
            "applicable": True,
            "type": "too_broad",
            "query": "Tóm tắt toàn bộ hợp đồng và rủi ro chính",
            "expected_state": "INSUFFICIENT_EVIDENCE",
            "expected_reason": "Không tóm tắt toàn văn từ một truy vấn quá rộng.",
            "layers": ["L0", "L3"],
            "must_cite": [],
            "forbidden": ["full_pdf_dump", "legal_winner"],
        }
    )
    tasks.append(
        {
            "id": "T-CASCADE",
            "kind": "product" if has_relation_source else "probe",
            "applicable": has_relation_source,
            "type": "cascade",
            "query": "Nếu phụ lục đổi định nghĩa Ngày làm việc thì điều thanh toán bị ảnh hưởng thế nào?",
            "expected_state": "NEEDS_REVIEW" if has_relation_source else "INSUFFICIENT_EVIDENCE",
            "expected_reason": "Thiếu phụ lục/định nghĩa/ngữ cảnh thì không dựng quan hệ.",
            "layers": ["L1", "L2", "L3"],
            "must_cite": [],
            "forbidden": ["legal_winner"],
        }
    )
    tasks.append(
        {
            "id": "T-PARTY-CARD",
            "kind": "product" if has_party else "probe",
            "applicable": has_party,
            "type": "party_card",
            "role": "A",
            "query": "Thông tin bên A?",
            "expected_state": "ANSWERED",
            "layers": ["L0", "L3"],
            "must_cite": [],
            "forbidden": ["legal_winner"],
        }
    )
    tasks.append(
        {
            "id": "T-ENTITY",
            "kind": "product" if has_party or has_mst else "probe",
            "applicable": has_party or has_mst,
            "type": "count_entity",
            "query": "Có bao nhiêu pháp nhân trong hợp đồng?",
            "expected_state": "NEEDS_REVIEW" if has_party or has_mst else "INSUFFICIENT_EVIDENCE",
            "expected_reason": "Đếm theo MST nhưng luôn cần rà soát tư cách pháp lý và liên kết tên/MST.",
            "layers": ["L0", "L3"],
            "must_cite": [],
            "forbidden": ["legal_winner"],
        }
    )
    return tasks
