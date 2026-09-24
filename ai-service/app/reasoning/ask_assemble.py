from __future__ import annotations

import re
from collections import OrderedDict
from typing import Any

from app.pipeline.ai1_snapshot_adapter import fold_for_match
from app.reasoning.fact_link import digits_only, group_hits
from app.reasoning.relations import doc_side

ROLE_LETTER = {"a": "A", "b": "B", "c": "C", "y": "Y"}
MENTION_SKIP = re.compile(r"thanh toán|phạt chậm|ngày làm việc|nghiệm thu", re.I)


def assemble_party(
    role_letter: str,
    outline: list[dict[str, Any]],
    party_hits: list[dict[str, Any]],
    mst_hits: list[dict[str, Any]],
    get_node=None,
) -> dict[str, Any]:
    letter = ROLE_LETTER.get((role_letter or "a").lower(), "A")
    # Match on a folded view so normal Vietnamese and ASCII OCR are handled
    # without changing the immutable source text.
    role_pat = re.compile(rf"\bben\s+{letter.lower()}\b", re.I)
    role_key = f"party_{letter.lower()}"
    role_mst_keys = {
        "A": {"mst_seller", "mst_party_a"},
        "B": {"mst_party_b", "mst_buyer"},
        "C": {"mst_party_c"},
        "Y": {"mst_party_y"},
    }.get(letter, {f"mst_party_{letter.lower()}"})
    names: OrderedDict[str, int] = OrderedDict()
    cites: list[dict[str, Any]] = []
    mst_for_role: list[dict[str, Any]] = []
    appearances: list[str] = []

    def consider(nid: str | None, blob: str, value: str | None = None, citation: dict | None = None) -> None:
        if not nid or not role_pat.search(fold_for_match(blob)):
            return
        party_blob = _party_segment(blob, letter)
        if MENTION_SKIP.search(party_blob) and not re.search(r"\bMST\b|\d{8,14}|công ty", party_blob, re.I):
            return
        appearances.append(nid)
        name = value or _name_from_blob(party_blob)
        if name:
            names[name] = names.get(name, 0) + 1
        tax_match = re.search(r"\b(?:mst|ma so thue|tax\s*(?:id|code))\s*[:\-]?\s*(\d{10}(?:-?\d{3})?)(?!\d)", fold_for_match(party_blob), re.I)
        code = tax_match.group(1) if tax_match else ""
        if code:
            mst_for_role.append({"node_id": nid, "value": code, "citation": {"node_id": nid, "text_span": code}})
        cites.append(citation or {"node_id": nid, "text_span": (value or blob)[:200]})

    for n in outline or []:
        # Clauses may mention several roles. Only declaration fields can
        # establish a party identity for this card.
        if n.get("type") != "FIELD" or n.get("structured_key") != role_key:
            continue
        blob = f"Bên {letter}: {n.get('structured_value') or n.get('text') or ''}"
        consider(n.get("node_id"), blob, n.get("structured_value") or None)
    # OCR-lab snapshots often keep party declarations in clause text instead
    # of party_* fields. Preserve those role mentions as evidence; do not
    # invent a company name when the handoff contains only placeholders.
    for n in outline or []:
        if n.get("type") == "FIELD" and n.get("structured_key") == role_key:
            continue
        full = get_node(n.get("node_id")) if get_node and n.get("node_id") else None
        blob = f"{(full or {}).get('raw_label') or n.get('raw_label') or ''}\n{(full or {}).get('text') or n.get('text') or ''}"
        if role_pat.search(fold_for_match(blob)):
            consider(n.get("node_id"), blob, citation=(full or {}).get("citation"))
    for h in party_hits or []:
        nid = h.get("node_id")
        blob = f"Bên {letter}: {h.get('value') or ''}"
        if nid:
            appearances.append(str(nid))
        name = str(h.get("value") or "") or _name_from_blob(blob)
        if name:
            names[name] = names.get(name, 0) + 1
        cites.append(h.get("citation") or {"node_id": nid, "text_span": name or blob[:200]})
    for h in mst_hits or []:
        if str(h.get("structured_key") or "") not in role_mst_keys:
            continue
        mst_for_role.append(h)
        nid = h.get("node_id")
        if nid:
            cites.append(h.get("citation") or {"node_id": nid, "text_span": h.get("value")})

    groups = group_hits(mst_for_role, canonical=digits_only) if mst_for_role else []
    uniq_names = list(names)
    if not uniq_names and not groups and not appearances:
        return {
            "review_state": "INSUFFICIENT_EVIDENCE",
            "notes": "party_card_none",
            "answer": f"Không thấy hồ sơ Bên {letter} trên snapshot. Không suy đoán.",
            "citations": [],
        }

    mst_bits = []
    for g in groups:
        mst_bits.append(f"{g['canonical']} ({g['count']} vị trí)")
    lines = [
        f"Bên {letter} trên snapshot (không khẳng định tư cách pháp lý, không chọn bên đúng):",
        f"- Tên/alias: {', '.join(uniq_names) if uniq_names else '(không tách được tên)'}",
        f"- MST: {'; '.join(mst_bits) if mst_bits else '(không gắn MST trên cùng dòng Bên ' + letter + ')'}",
        f"- Xuất hiện: {', '.join(dict.fromkeys(appearances))}",
    ]
    if len(groups) > 1:
        lines.append("- Nhiều MST cùng vai — NEEDS_REVIEW, không chọn MST đúng.")
    state = "NEEDS_REVIEW" if len(groups) > 1 or len(uniq_names) > 1 or not uniq_names else "ANSWERED"
    return {
        "review_state": state,
        "notes": "party_card",
        "answer": "\n".join(lines),
        "citations": cites[:12],
    }


def assemble_field(key: str, hits: list[dict[str, Any]]) -> dict[str, Any]:
    groups = group_hits(hits, canonical=lambda v: str(v or "").strip().lower())
    cites = []
    for g in groups:
        for m in g["hits"]:
            cites.append(m.get("citation") or {"node_id": m.get("node_id"), "text_span": m.get("value")})
    if not groups:
        return {
            "review_state": "INSUFFICIENT_EVIDENCE",
            "notes": "field_none",
            "answer": f"Không có structured key «{key}» trên snapshot.",
            "citations": [],
        }
    bits = [f"{g['display']} ({g['count']} vị trí)" for g in groups]
    conflict = len(groups) > 1
    ans = f"Trường {key}: " + "; ".join(bits) + (". Không chọn giá trị đúng." if conflict else ".")
    return {
        "review_state": "NEEDS_REVIEW" if conflict else "ANSWERED",
        "notes": "field_card",
        "answer": ans,
        "citations": cites,
    }


def assemble_mst(hits: list[dict[str, Any]]) -> dict[str, Any]:
    """Return all role-labelled MSTs without selecting one as authoritative."""

    role_labels = {
        "mst_seller": "Bên A",
        "mst_party_a": "Bên A",
        "mst_party_b": "Bên B",
        "mst_party_c": "Bên C",
        "mst_party_y": "Bên Y",
        "mst_buyer": "Bên B",
        "mst_supplier": "Nhà cung cấp",
    }
    by_role: OrderedDict[str, OrderedDict[str, list[dict[str, Any]]]] = OrderedDict()
    for hit in hits or []:
        value = digits_only(str(hit.get("value") or ""))
        if not value:
            continue
        role = role_labels.get(str(hit.get("structured_key") or ""), "Không rõ vai")
        by_role.setdefault(role, OrderedDict()).setdefault(value, []).append(hit)
    if not by_role:
        return {
            "review_state": "INSUFFICIENT_EVIDENCE",
            "notes": "mst_none",
            "answer": "Không có MST trên snapshot. Không suy đoán.",
            "citations": [],
        }

    citations = []
    lines = ["MST trên snapshot (liệt kê theo vai, không chọn bên đúng):"]
    conflict = False
    for role, values in by_role.items():
        rendered = []
        if len(values) > 1:
            conflict = True
        for value, members in values.items():
            rendered.append(value)
            for member in members:
                citation = dict(member.get("citation") or {"node_id": member.get("node_id"), "text_span": value})
                citations.append(citation)
        lines.append(f"- {role}: {'; '.join(rendered)}")
    if conflict:
        lines.append("- Một vai có nhiều MST khác nhau — NEEDS_REVIEW, không chọn giá trị đúng.")
    return {
        "review_state": "NEEDS_REVIEW" if conflict else "ANSWERED",
        "notes": "mst_by_role",
        "answer": "\n".join(lines),
        "citations": citations[:16],
    }


def assemble_overview(outline: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a bounded, extractive document overview from structured nodes."""

    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    priority = {"party_a": 1, "party_b": 1, "contract_value": 2, "payment_term": 3, "validity": 3, "price": 3, "qty": 3}
    for node in sorted(outline or [], key=lambda item: (priority.get(item.get("structured_key"), 9), item.get("order", 0))):
        key = node.get("structured_key")
        if key not in priority or node.get("node_id") in seen:
            continue
        seen.add(node.get("node_id"))
        selected.append(node)
        if len(selected) >= 12:
            break

    # A result may contain parties/facts but no normalized subject or value
    # field. Keep the first subject-bearing article as bounded extractive
    # evidence for questions such as "hợp đồng nói về gì?".
    subject_terms_folded = (
        "mua ban", "ban cho", "hang hoa", "dich vu", "doi tuong", "noi dung",
        "pham vi", "cung cap", "works", "service", "goods",
    )
    for node in sorted(outline or [], key=lambda item: item.get("order", 0)):
        if len(selected) >= 12 or node.get("node_id") in seen or node.get("type") not in {"CLAUSE", "SECTION"}:
            continue
        blob = fold_for_match(f"{node.get('raw_label') or ''} {node.get('text') or ''}")
        if any(term in blob for term in subject_terms_folded):
            seen.add(node.get("node_id"))
            selected.append(node)

    if not selected:
        return {
            "review_state": "INSUFFICIENT_EVIDENCE",
            "notes": "overview_no_structured_facts",
            "answer": "Snapshot chưa có fact đủ rõ để mô tả tổng quan hợp đồng.",
            "citations": [],
        }

    lines = ["Mô tả có giới hạn từ snapshot (không suy đoán mục đích pháp lý):"]
    citations: list[dict[str, Any]] = []
    for node in selected:
        label = node.get("raw_label") or node.get("structured_key") or node.get("node_id")
        value = node.get("structured_value") or node.get("text") or ""
        lines.append(f"- {label}: {value}")
        citations.append(
            {
                "node_id": node.get("node_id"),
                "page_revision_id": node.get("page_revision_id") or "",
                "bbox": node.get("bbox") or [],
                "text_span": str(value)[:240],
            }
        )

    corpus = fold_for_match("\n".join(f"{node.get('raw_label', '')} {node.get('text', '')}" for node in outline or []))
    subject_terms = (
        "doi tuong", "pham vi", "dich vu", "hang hoa", "cung cap", "muc dich", "scope", "subject", "works", "service", "goods",
    )
    if not any(term in corpus for term in subject_terms):
        lines.append("- Thiếu evidence về đối tượng/phạm vi/mục đích hợp đồng — cần rà soát.")
        state = "NEEDS_REVIEW"
    else:
        state = "ANSWERED"
    return {"review_state": state, "notes": "bounded_overview", "answer": "\n".join(lines), "citations": citations}


def assemble_annex(n: str, outline: list[dict[str, Any]], get_node, *, record=None) -> dict[str, Any]:
    label = f"Phụ lục {n}"
    roots = [
        node
        for node in outline
        if re.match(rf"^phu luc\s+0*{re.escape(str(int(n)) if n.isdigit() else n)}\b", fold_for_match(node.get("raw_label") or ""))
        or re.search(rf"(?:^|\n)\s*phu luc\s+0*{re.escape(str(int(n)) if n.isdigit() else n)}\b", fold_for_match(node.get("text") or ""))
    ]
    annex_pages: set[int] = set()
    if record is not None:
        marker_pages = []
        for page in record.pages:
            if any(re.match(rf"^\s*phu luc\s+0*{re.escape(str(int(n)) if n.isdigit() else n)}\b", fold_for_match(line)) for line in page.line_texts.values()):
                marker_pages.append(page.page_number)
        if marker_pages:
            start = min(marker_pages)
            annex_pages = set(range(start, max((page.page_number for page in record.pages), default=start) + 1))
            roots.extend(
                node
                for node in outline
                if node.get("type") == "TABLE" and set(node.get("page_range") or []).intersection(annex_pages)
            )
            roots.extend(
                node
                for node in outline
                if node.get("raw_label") in {"1.", "2.", "3."}
                and set(node.get("page_range") or []).intersection(annex_pages)
            )
            roots = [
                node
                for node in roots
                if node.get("type") == "TABLE"
                or not fold_for_match(node.get("raw_label") or "").startswith("dieu ")
            ]
    if not roots:
        return {
            "review_state": "INSUFFICIENT_EVIDENCE",
            "notes": "annex_missing",
            "answer": f"{label} không có trên outline. Không bịa nội dung phụ lục.",
            "citations": [],
        }
    root_ids = {r["node_id"] for r in roots}
    children = [node for node in outline if node.get("parent") in root_ids or node["node_id"] in root_ids]
    if annex_pages:
        children.extend(
            node
            for node in outline
            if node.get("type") == "TABLE"
            and set(node.get("page_range") or []).intersection(annex_pages)
            and node["node_id"] not in {item["node_id"] for item in children}
        )
    packed = []
    cites = []
    for node in children[:12]:
        full = get_node(node["node_id"])
        packed.append(
            {
                "node_id": node["node_id"],
                "label": full.get("raw_label") or node.get("raw_label"),
                "side": (
                    f"Phụ lục {n}"
                    if annex_pages and set(node.get("page_range") or []).intersection(annex_pages)
                    else doc_side(full.get("ancestors"), full.get("raw_label"))
                ),
                "text": (full.get("text") or "")[:400],
            }
        )
        cites.append(full.get("citation") or {"node_id": node["node_id"]})
    lines = [f"{label} trên snapshot (không tóm tắt toàn hồ sơ, không suy hiệu lực):"]
    for p in packed:
        lines.append(f"- [{p['side']}] {p['label']}: {p['text']}")
    return {
        "review_state": "NEEDS_REVIEW" if len(packed) > 1 else "ANSWERED",
        "notes": "annex_card",
        "answer": "\n".join(lines),
        "citations": cites,
    }


def assemble_annex_list(outline: list[dict[str, Any]], get_node, *, record=None) -> dict[str, Any]:
    """Inventory embedded annex headings without treating references as annexes."""

    markers: dict[str, list[int]] = OrderedDict()
    if record is not None:
        for page in record.pages:
            for line in page.line_texts.values():
                match = re.match(r"^\s*phu luc\s+([0-9]+)\b", fold_for_match(line))
                if match:
                    markers.setdefault(match.group(1), []).append(page.page_number)
    # Keep a structural fallback for canonical samples whose page line map is
    # sparse, but require a heading at the beginning of a label/text span.
    if not markers:
        for node in outline:
            match = re.match(r"^\s*phu luc\s+([0-9]+)\b", fold_for_match(node.get("raw_label") or ""))
            if match:
                markers.setdefault(match.group(1), []).extend(node.get("page_range") or [])

    if not markers:
        return {
            "review_state": "NEEDS_REVIEW",
            "notes": "annex_list_none_detected",
            "answer": "Không phát hiện tiêu đề Phụ lục <số> trong snapshot. Các chỗ chỉ dẫn Phụ lục (nếu có) không được coi là một phụ lục đã nhận diện.",
            "citations": [],
        }

    numbers = sorted(markers, key=lambda value: int(value))
    citations: list[dict[str, Any]] = []
    lines = [f"Phát hiện {len(numbers)} phụ lục trong snapshot:"]
    for number in numbers:
        pages = sorted(set(markers[number]))
        matching = [
            node for node in outline
            if set(node.get("page_range") or []).intersection(pages)
            and (
                re.match(rf"^\s*phu luc\s+0*{re.escape(number)}\b", fold_for_match(node.get("raw_label") or ""))
                or node.get("type") == "TABLE"
            )
        ]
        node = matching[0] if matching else None
        if node:
            full = get_node(node["node_id"])
            citation = full.get("citation") or {"node_id": node["node_id"], "text_span": full.get("raw_label") or f"Phụ lục {number}"}
            citations.append(citation)
        page_text = ", ".join(str(page) for page in pages)
        lines.append(f"- Phụ lục {number}: trang {page_text}.")
    return {
        "review_state": "ANSWERED",
        "notes": "annex_list",
        "answer": "\n".join(lines),
        "citations": citations[:16],
    }


def unscoped_hint(outline: list[dict[str, Any]]) -> dict[str, Any]:
    sample = [n.get("raw_label") for n in outline if n.get("type") in {"CLAUSE", "SECTION"}][:8]
    return {
        "review_state": "INSUFFICIENT_EVIDENCE",
        "notes": "unscoped",
        "answer": "Chưa khớp intent. Hỏi Bên A/B, Điều n, Phụ lục n, hoặc trường (MST, giá, phạt). Gợi ý: "
        + ", ".join(str(x) for x in sample if x),
        "citations": [],
    }


def _name_from_blob(blob: str) -> str | None:
    # A generic occurrence of "công ty" in a template introduction is not a
    # party identity. Require an explicit declaration label or role-colon
    # assignment and reject placeholder-only values.
    for line in blob.splitlines():
        folded = fold_for_match(line)
        if "ten don vi" not in folded and "ten cong ty" not in folded:
            continue
        value = line.split(":", 1)[1].strip() if ":" in line else ""
        if value and not re.fullmatch(r"[\[\(].*[\]\)]|[•·…]+", value):
            return re.sub(r"\s*(?:MST|Mã số thuế)[:\s]*\d{8,14}.*", "", value, flags=re.I).strip()[:80]
    m = re.search(r"Bên\s+[ABCY]\s*[:\-]\s*([^\.\n]{2,80})", blob, re.I)
    if m and not re.search(r"[•·…]", m.group(1)):
        return re.sub(r"\s*(?:MST|Mã số thuế)[:\s]*\d{8,14}.*", "", m.group(1), flags=re.I).strip()[:80]
    return None


def _party_segment(blob: str, letter: str) -> str:
    """Return the declaration block for one role, when a block is present."""

    lines = blob.splitlines()
    wanted = f"ben {letter.lower()}"
    other_roles = re.compile(r"^\s*ben\s+[abcy]\b", re.I)
    started = False
    selected: list[str] = []
    for line in lines:
        folded = fold_for_match(line)
        if re.search(rf"\b{re.escape(wanted)}\b", folded):
            started = True
        elif started and other_roles.search(folded) and wanted not in folded:
            break
        if started:
            selected.append(line)
    return "\n".join(selected) if selected else blob
