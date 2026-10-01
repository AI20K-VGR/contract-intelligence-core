from __future__ import annotations

import re
from collections import OrderedDict
from typing import Any, Callable

from app.pipeline.ai1_snapshot_adapter import fold_for_match


Relation = str  # SAME_VALUE | CONFLICT | SINGLE


def digits_only(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


def group_hits(
    hits: list[dict[str, Any]],
    *,
    canonical: Callable[[Any], str] = digits_only,
) -> list[dict[str, Any]]:
    """Collapse facts that share a canonical value; keep every occurrence as evidence."""
    buckets: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for h in hits:
        key = canonical(h.get("value")) or str(h.get("value") or "").strip()
        if not key:
            key = str(h.get("node_id") or id(h))
        buckets.setdefault(key, []).append(h)
    groups: list[dict[str, Any]] = []
    for key, members in buckets.items():
        nids = [str(m.get("node_id") or (m.get("citation") or {}).get("node_id") or "") for m in members]
        groups.append(
            {
                "canonical": key,
                "display": str(members[0].get("value") or key),
                "count": len(members),
                "node_ids": [n for n in nids if n],
                "hits": members,
                "relation": "SAME_VALUE" if len(members) > 1 else "SINGLE",
            }
        )
    return groups


def relate_mst(hits: list[dict[str, Any]]) -> dict[str, Any]:
    groups = group_hits(hits, canonical=digits_only)
    unique = len(groups)
    cites = []
    for g in groups:
        for m in g["hits"]:
            c = dict(m.get("citation") or {"node_id": m.get("node_id"), "text_span": m.get("value")})
            c["same_as"] = g["node_ids"]
            c["canonical"] = g["canonical"]
            cites.append(c)
    if unique == 0:
        return {
            "review_state": "INSUFFICIENT_EVIDENCE",
            "notes": "mst_none",
            "answer": "Không có MST trên snapshot.",
            "citations": [],
            "groups": groups,
        }
    if unique == 1:
        g = groups[0]
        if g["count"] == 1:
            ans = f"MST {g['display']}."
        else:
            locs = ", ".join(g["node_ids"])
            ans = (
                f"MST {g['display']} xuất hiện {g['count']} lần — cùng một mã, các vị trí: {locs}. "
                "Không phải nhiều MST khác nhau."
            )
        return {
            "review_state": "ANSWERED",
            "notes": "mst_same",
            "answer": ans,
            "citations": cites,
            "groups": groups,
        }
    lines = []
    for g in groups:
        if g["count"] > 1:
            lines.append(f"{g['display']} (cùng mã, {g['count']} vị trí: {', '.join(g['node_ids'])})")
        else:
            lines.append(g["display"])
    ans = (
        f"Có {unique} MST khác nhau trên hồ sơ ({sum(g['count'] for g in groups)} lần xuất hiện). "
        + "; ".join(lines)
        + ". Các vị trí trùng mã là cùng một fact, không đếm thêm. Không chọn MST đúng."
    )
    return {
        "review_state": "NEEDS_REVIEW",
        "notes": "mst_conflict",
        "answer": ans,
        "citations": cites,
        "groups": groups,
    }


def _norm_name(value: Any) -> str:
    s = re.sub(r"\d{8,14}", " ", str(value or ""))
    s = s.lower()
    s = re.sub(r"\b(mst|mã số thuế|bên\s+[abcy]|công ty|cong ty|tnhh|cổ phần|co\.,?ltd)\b", " ", s)
    s = re.sub(r"[^a-z0-9à-ỹ\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def count_legal_entities(
    mst_hits: list[dict[str, Any]],
    party_hits: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Identity = unique MST. Same MST = one pháp nhân even if names/aliases differ. No legal winner."""
    mst_hits = list(mst_hits)
    for p in party_hits or []:
        text = " ".join(
            [
                str(p.get("value") or ""),
                str((p.get("citation") or {}).get("text_span") or ""),
            ]
        )
        for code in re.findall(r"\d{8,14}", text):
            mst_hits.append(
                {
                    "node_id": p.get("node_id"),
                    "value": code,
                    "citation": p.get("citation") or {"node_id": p.get("node_id"), "text_span": code},
                }
            )
    mst_groups = group_hits(mst_hits, canonical=digits_only)
    party_hits = party_hits or []
    names_by_mst: dict[str, set[str]] = {g["canonical"]: set() for g in mst_groups}
    orphan_names: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()

    for p in party_hits:
        text = " ".join(
            [
                str(p.get("value") or ""),
                str((p.get("citation") or {}).get("text_span") or ""),
            ]
        )
        mst_in = digits_only(text)
        name = _norm_name(p.get("value")) or str(p.get("value") or "").strip()
        if mst_in and mst_in in names_by_mst:
            if name:
                names_by_mst[mst_in].add(name)
        elif name:
            orphan_names.setdefault(name, []).append(p)

    n = len(mst_groups)
    cites = []
    for g in mst_groups:
        for m in g["hits"]:
            c = dict(m.get("citation") or {"node_id": m.get("node_id"), "text_span": m.get("value")})
            c["canonical"] = g["canonical"]
            c["same_as"] = g["node_ids"]
            cites.append(c)
    for members in orphan_names.values():
        for p in members:
            cites.append(p.get("citation") or {"node_id": p.get("node_id"), "text_span": p.get("value")})

    if n == 0 and not orphan_names:
        return {
            "review_state": "INSUFFICIENT_EVIDENCE",
            "notes": "entity_none",
            "answer": "Không thấy MST hoặc tên pháp nhân trên snapshot. Không đếm bằng suy đoán.",
            "citations": [],
            "count": 0,
        }

    if n == 0:
        names = list(orphan_names)
        return {
            "review_state": "NEEDS_REVIEW",
            "notes": "entity_names_only",
            "answer": (
                f"Không có MST. Có {len(names)} tên xuất hiện: {', '.join(names)}. "
                "Không khẳng định số pháp nhân. Không gộp alias."
            ),
            "citations": cites,
            "count": len(names),
        }

    bits = []
    for g in mst_groups:
        aliases = sorted(names_by_mst.get(g["canonical"]) or [])
        extra = f", tên/alias: {', '.join(aliases)}" if aliases else ""
        occ = f"{g['count']} vị trí" if g["count"] > 1 else "1 vị trí"
        bits.append(f"{g['canonical']} ({occ}{extra})")
    tail = ""
    if orphan_names:
        tail = f" Thêm {len(orphan_names)} tên chưa gắn MST: {', '.join(orphan_names)} — không cộng vào số pháp nhân."
    ans = (
        f"Có {n} pháp nhân phân biệt theo MST trên snapshot (không suy ra tư cách pháp lý, không chọn bên đúng). "
        + "; ".join(bits)
        + ". Trùng MST = cùng một pháp nhân."
        + tail
    )
    return {
        "review_state": "NEEDS_REVIEW" if n > 1 or orphan_names else "ANSWERED",
        "notes": "entity_count",
        "answer": ans,
        "citations": cites,
        "count": n,
    }


ROLE_RE = re.compile(r"\bbên\s+([a-zy])\b", re.I)
ROLE_RE_FOLDED = re.compile(r"\bben\s+([abcy])\b", re.I)


def count_parties(outline: list[dict[str, Any]], party_hits: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Count unique party roles (Bên A/B/C), not unique MST. Same role many times = one bên."""
    roles: OrderedDict[str, list[str]] = OrderedDict()
    cites: list[dict[str, Any]] = []

    def add(role: str, nid: str | None, span: str) -> None:
        role = role.strip()
        if not role:
            return
        roles.setdefault(role, [])
        if nid and nid not in roles[role]:
            roles[role].append(nid)
            # Count answers need representative evidence, not one citation
            # for every repeated role mention in a long contract.
            if len(roles[role]) <= 3:
                cites.append({"node_id": nid, "text_span": span[:200]})

    for n in outline or []:
        # Production outlines expose type/structured_key; legacy lightweight
        # test/adapter outlines may omit both, so retain those as compatible
        # declaration evidence.
        # OCR-lab party declarations are usually CLAUSE/SECTION nodes rather
        # than normalized party_* fields. Scan all structural evidence and
        # count only explicit role tokens.
        blob = f"{n.get('raw_label') or ''} {n.get('text') or ''}"
        nid = n.get("node_id")
        matches = list(ROLE_RE.finditer(blob))
        matches.extend(ROLE_RE_FOLDED.finditer(fold_for_match(blob)))
        for m in matches:
            add(f"Bên {m.group(1).upper()}", nid, m.group(0))
    for p in party_hits or []:
        text = str(p.get("value") or "")
        nid = str(p.get("node_id") or (p.get("citation") or {}).get("node_id") or "")
        found = False
        matches = list(ROLE_RE.finditer(text))
        matches.extend(ROLE_RE_FOLDED.finditer(fold_for_match(text)))
        for m in matches:
            add(f"Bên {m.group(1).upper()}", nid, m.group(0))
            found = True
        if not found and nid:
            span = str((p.get("citation") or {}).get("text_span") or text)
            matches = list(ROLE_RE.finditer(span))
            matches.extend(ROLE_RE_FOLDED.finditer(fold_for_match(span)))
            for m in matches:
                add(f"Bên {m.group(1).upper()}", nid, m.group(0))
                found = True

    n = len(roles)
    if n == 0:
        return {
            "review_state": "INSUFFICIENT_EVIDENCE",
            "notes": "party_none",
            "answer": "Không thấy vai trò Bên A/B/C trên snapshot. Không đếm bằng suy đoán.",
            "citations": [],
            "count": 0,
        }
    bits = [
        f"{role} ({len(ids)} node evidence, ví dụ: {', '.join(ids[:3])}"
        + (", …)" if len(ids) > 3 else ")")
        for role, ids in roles.items()
    ]
    ans = (
        f"Có {n} bên theo vai trò trên snapshot: " + "; ".join(bits) + ". "
        "Cùng vai trò lặp lại vẫn là một bên. Không đồng nhất với số pháp nhân/MST. Không chọn bên đúng."
    )
    return {
        "review_state": "ANSWERED" if n >= 1 else "INSUFFICIENT_EVIDENCE",
        "notes": "party_count",
        "answer": ans,
        "citations": cites,
        "count": n,
    }


def count_contract_parties(
    outline: list[dict[str, Any]],
    *,
    role_hits: list[dict[str, Any]] | None = None,
    identity_hits: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Answer the user-facing ``bên`` count without conflating roles and entities.

    A template can contain ``Bên A`` and ``Bên B`` while carrying no actual
    party identity.  In that case returning ``ANSWERED`` for two parties is
    misleading.  Prefer distinct, source-backed MST identities; otherwise
    expose the role count as a review hint and keep the answer conservative.
    """

    role_result = count_parties(outline, role_hits)
    entity_result = count_legal_entities(identity_hits or [], [])
    if entity_result.get("count", 0):
        count = int(entity_result["count"])
        answer = str(entity_result.get("answer") or "")
        answer = answer.replace(
            f"Có {count} pháp nhân phân biệt",
            f"Có {count} bên/pháp nhân được nhận diện",
            1,
        )
        roles = re.findall(r"Bên [A-Z]", str(role_result.get("answer") or ""))
        if roles:
            answer += " Vai trò quan sát được: " + ", ".join(dict.fromkeys(roles)) + "."
        return {
            **entity_result,
            "review_state": "ANSWERED",
            "notes": "contract_party_count_by_identity",
            "answer": answer,
        }

    if role_result.get("count", 0):
        roles = re.findall(r"Bên [A-Z]", str(role_result.get("answer") or ""))
        role_text = ", ".join(dict.fromkeys(roles)) or "các vai trò trong hợp đồng"
        return {
            **role_result,
            "review_state": "NEEDS_REVIEW",
            "notes": "contract_party_roles_without_identity",
            "answer": (
                f"Snapshot chỉ xác nhận {role_result['count']} vai trò hợp đồng ({role_text}). "
                "Chưa có tên pháp nhân hoặc MST đủ tin cậy để kết luận số bên thực tế. "
                "Không đếm vai trò thay cho pháp nhân."
            ),
        }
    return entity_result if entity_result.get("review_state") != "INSUFFICIENT_EVIDENCE" else role_result
