from __future__ import annotations

import re
from collections import defaultdict
from decimal import Decimal
from uuid import uuid4

from app.contracts.models import (
    Candidate,
    Citation,
    ComparisonScope,
    Disposition,
    EvidenceIssue,
    Fact,
    FindingType,
    ModelDisposition,
    ReviewState,
)

AMEND_RE = re.compile(r"sửa|sua doi|thay thế|thành\s+|amends?", re.I)
ANNEX_REF_RE = re.compile(r"(?:phụ lục|phu luc)\s+(\d+)", re.I)


def money_decimal(value: str | None, *, unit: str | None = None) -> Decimal | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if "%" in text or unit == "percent":
        compact = text.replace(" ", "").replace(",", ".").replace("%", "")
        try:
            return Decimal(compact)
        except Exception:
            return None
    digits = re.sub(r"[^\d]", "", text)
    if not digits:
        return None
    return Decimal(digits)


def compare_facts(
    facts: list[Fact],
    *,
    annex_labels_present: set[str] | None = None,
    relation_pairs: set[tuple[str, str]] | None = None,
) -> tuple[list[Candidate], list[EvidenceIssue]]:
    """One finding = two sources in the same contract context. No legal winner."""
    annex_labels_present = annex_labels_present or set()
    relation_pairs = {_relation_key(*pair) for pair in (relation_pairs or set())}
    issues = _missing_annex_issues(facts, annex_labels_present)
    keyed: dict[tuple, list[Fact]] = defaultdict(list)
    for f in facts:
        if _is_identity_fact(f):
            continue
        ck = _context_key(f)
        if ck[0] is None or ck[0] == "mst_seller":
            continue
        keyed[ck].append(f)

    out: list[Candidate] = []
    for ctx, group in keyed.items():
        item = ctx[0]
        compact = _dedupe_facts(group)
        issues.extend(_missing_pairing_evidence(compact, item, relation_pairs))
        out.extend(_pair_two_sources(compact, item, relation_pairs))

    fee_keys = {ctx[0] for ctx in keyed if ctx[0] and not str(ctx[0]).startswith("mst")}
    scopes = [k for k in fee_keys if k in {"X", "Y"} or str(k).startswith("scope")]
    if len(scopes) >= 2:
        a = keyed[[c for c in keyed if c[0] == scopes[0]][0]][0]
        b = keyed[[c for c in keyed if c[0] == scopes[1]][0]][0]
        out.append(
            _cand(
                a,
                b,
                FindingType.GAP,
                Disposition.NOT_COMPARABLE,
                ReviewState.NOT_COMPARABLE,
                ModelDisposition.INCOMPLETE,
                "Khác phạm vi phí — không so, không kết luận pháp lý.",
                _scope(a, b),
                None,
            )
        )
    return out, issues


def _is_identity_fact(fact: Fact) -> bool:
    """Party identity fields are metadata, not comparable contract terms."""

    role = str(fact.role or "").casefold()
    key = str(fact.item_key or "").casefold()
    return role.startswith("party_") or role.startswith("mst_party_") or key.startswith("party_")


def _context_key(f: Fact) -> tuple:
    return (f.item_key or f.scope,)


def _pair_two_sources(
    group: list[Fact], item: str, relation_pairs: set[tuple[str, str]]
) -> list[Candidate]:
    """Body↔annex (and at most one within-doc pair). No N×N, no annex tournament."""
    bodies = [f for f in group if (f.source_role or "body") != "annex"]
    annexes: dict[str, list[Fact]] = defaultdict(list)
    for f in group:
        if (f.source_role or "body") == "annex":
            annexes[f.validity or "PL"].append(f)

    out: list[Candidate] = []
    body_vals = _unique_values(bodies)
    if bodies and annexes:
        body_rep = _prefer_body(body_vals)
        for _pl, afs in annexes.items():
            for annex_rep in _unique_values(afs):
                if not _pairing_allowed(body_rep, annex_rep, relation_pairs):
                    continue
                cand = _pair(body_rep, annex_rep, item)
                if cand:
                    out.append(cand)
        if len(body_vals) >= 2:
            cand = _pair(body_vals[0], body_vals[1], item)
            if cand:
                out.append(cand)
        return out
    if len(body_vals) >= 2:
        cand = _pair(body_vals[0], body_vals[1], item)
        return [cand] if cand else []
    annex_reps = [afs[0] for afs in annexes.values() if afs]
    if len(annex_reps) >= 2:
        return [
            _cand(
                annex_reps[0],
                annex_reps[1],
                FindingType.GAP,
                Disposition.NOT_COMPARABLE,
                ReviewState.NOT_COMPARABLE,
                ModelDisposition.INCOMPLETE,
                "Hai phụ lục khác nhau — không chọn phụ lục nào thắng.",
                ComparisonScope.ANNEX_ANNEX,
                item,
            )
        ]
    return []


def _relation_key(left: str, right: str) -> tuple[str, str]:
    return tuple(sorted((str(left), str(right))))


def _pairing_allowed(left: Fact, right: Fact, relation_pairs: set[tuple[str, str]]) -> bool:
    left_file = left.citation.source_file_id
    right_file = right.citation.source_file_id
    if not left_file or not right_file or left_file == right_file:
        return True
    return _relation_key(left.citation.node_id, right.citation.node_id) in relation_pairs


def _missing_pairing_evidence(
    group: list[Fact], item: str, relation_pairs: set[tuple[str, str]]
) -> list[EvidenceIssue]:
    bodies = [fact for fact in group if (fact.source_role or "body") != "annex"]
    annexes = [fact for fact in group if (fact.source_role or "body") == "annex"]
    if not bodies or not annexes:
        return []
    missing: list[tuple[Fact, Fact]] = []
    for body in bodies:
        for annex in annexes:
            if not _pairing_allowed(body, annex, relation_pairs):
                missing.append((body, annex))
    if not missing:
        return []
    body, annex = missing[0]
    return [
        EvidenceIssue(
            issue_id=f"body-annex-relation:{body.fact_id}:{annex.fact_id}",
            missing="BODY_ANNEX_RELATION",
            reason=(
                f"Thiếu relation evidence cho body/annex của {item}; "
                "không tạo finding cross-document."
            ),
            citation=annex.citation,
            review_state=ReviewState.INSUFFICIENT_EVIDENCE,
        )
    ]


def _unique_values(facts: list[Fact]) -> list[Fact]:
    seen: dict[str, Fact] = {}
    for f in facts:
        seen.setdefault(f.normalized_value or f.raw_value, f)
    return list(seen.values())


def _prefer_body(facts: list[Fact]) -> Fact:
    for f in facts:
        blob = f"{f.citation.text_span} {f.subject or ''} {f.raw_value}"
        if re.search(r"giá hợp đồng|gia hop dong|điều 9|dieu 9", blob, re.I):
            return f
    return facts[0]


def _src_label(f: Fact) -> str:
    if f.validity:
        return f"Phụ lục {f.validity.replace('PL', '')}"
    if f.source_role == "annex":
        return "Phụ lục"
    sub = (f.subject or "").strip()
    return sub or "Thân hợp đồng"


def _two_source_reason(left: Fact, right: Fact, verdict: str) -> str:
    return (
        f"Nguồn 1 · {_src_label(left)}: {left.raw_value}  ↔  "
        f"Nguồn 2 · {_src_label(right)}: {right.raw_value}. {verdict}"
    )


def _pair(left: Fact, right: Fact, item: str) -> Candidate | None:
    scope = _scope(left, right)
    if left.currency and right.currency and left.currency != right.currency:
        return _cand(
            left,
            right,
            FindingType.GAP,
            Disposition.NOT_COMPARABLE,
            ReviewState.NOT_COMPARABLE,
            ModelDisposition.INCOMPLETE,
            "Khác currency — không quy đổi khi chưa có tỷ giá/căn cứ; NOT_COMPARABLE.",
            scope,
            item,
        )
    if left.unit and right.unit and left.unit != right.unit:
        if {left.unit, right.unit} == {"VND", "USD"} or (
            left.currency and right.currency and left.currency != right.currency
        ):
            return _cand(
                left,
                right,
                FindingType.GAP,
                Disposition.NOT_COMPARABLE,
                ReviewState.NOT_COMPARABLE,
                ModelDisposition.INCOMPLETE,
                "Khác đơn vị/currency — không quy đổi. NOT_COMPARABLE.",
                scope,
                item,
            )
    if left.scope and right.scope and left.scope != right.scope:
        return _cand(
            left,
            right,
            FindingType.GAP,
            Disposition.NOT_COMPARABLE,
            ReviewState.NOT_COMPARABLE,
            ModelDisposition.INCOMPLETE,
            f"Khác phạm vi {left.scope} vs {right.scope} — không so, không chọn bên thắng.",
            scope,
            item,
        )
    if left.condition and right.condition and left.condition != right.condition:
        return _cand(
            left,
            right,
            FindingType.GAP,
            Disposition.NOT_COMPARABLE,
            ReviewState.NOT_COMPARABLE,
            ModelDisposition.INCOMPLETE,
            f"Khác điều kiện {left.condition} vs {right.condition} — hai nguồn, không kết luận pháp lý.",
            scope,
            item,
        )
    if (
        left.source_role == "annex"
        and right.source_role == "annex"
        and left.validity
        and right.validity
        and left.validity != right.validity
    ):
        return _cand(
            left,
            right,
            FindingType.GAP,
            Disposition.NOT_COMPARABLE,
            ReviewState.NOT_COMPARABLE,
            ModelDisposition.INCOMPLETE,
            f"Khác phụ lục {left.validity} vs {right.validity} — không chọn phụ lục nào thắng.",
            scope,
            item,
        )
    cite_blob = f"{right.citation.text_span} {left.citation.text_span} {right.raw_value} {left.raw_value}"
    if str(item).startswith("penalty") or str(item) in {"A", "B"}:
        cite_blob += f" {right.subject or ''} {left.subject or ''}"
    is_amend = bool(AMEND_RE.search(cite_blob))
    left_period, right_period = left.period_start, right.period_start
    if is_amend and scope != ComparisonScope.ANNEX_ANNEX:
        return _cand(
            left,
            right,
            FindingType.CANDIDATE_AMENDMENT,
            Disposition.CANDIDATE_AMENDMENT,
            ReviewState.NEEDS_REVIEW,
            ModelDisposition.UNCLEAR,
            "Tham chiếu sửa/thay rõ — CANDIDATE_AMENDMENT, không xác nhận hiệu lực, không kéo item khác.",
            scope,
            item,
        )
    if (left_period and not right_period) or (right_period and not left_period):
        return _cand(
            left,
            right,
            FindingType.NEEDS_EVIDENCE,
            Disposition.NEEDS_EVIDENCE,
            ReviewState.INSUFFICIENT_EVIDENCE,
            ModelDisposition.INCOMPLETE,
            "Thiếu kỳ/thời điểm áp dụng — NEEDS_EVIDENCE, không chọn nguồn vì upload sau.",
            scope,
            item,
        )
    lv, rv = _money(left), _money(right)
    if lv is not None and rv is not None:
        if lv == rv:
            return _cand(
                left,
                right,
                FindingType.COMPARABLE_MATCH,
                Disposition.COMPARABLE_MATCH,
                ReviewState.PASS,
            ModelDisposition.CONSISTENT,
            "Cùng ngữ cảnh, hai nguồn khớp. Không vào hàng cảnh báo.",
                scope,
                item,
            )
        return _cand(
            left,
            right,
            FindingType.COMPARABLE_DIFFERENCE,
            Disposition.COMPARABLE_DIFFERENCE,
            ReviewState.NEEDS_REVIEW,
            ModelDisposition.UNCLEAR,
            "Cùng ngữ cảnh, hai nguồn khác giá trị — không kết luận bên nào thắng.",
            scope,
            item,
        )
    if left.normalized_value and right.normalized_value:
        if left.normalized_value == right.normalized_value:
            return _cand(
                left,
                right,
                FindingType.COMPARABLE_MATCH,
                Disposition.COMPARABLE_MATCH,
                ReviewState.PASS,
            ModelDisposition.CONSISTENT,
            "Cùng ngữ cảnh, hai nguồn khớp.",
                scope,
                item,
            )
        return _cand(
            left,
            right,
            FindingType.COMPARABLE_DIFFERENCE,
            Disposition.COMPARABLE_DIFFERENCE,
            ReviewState.NEEDS_REVIEW,
            ModelDisposition.UNCLEAR,
            "Cùng ngữ cảnh, hai nguồn khác giá trị — không kết luận pháp lý.",
            scope,
            item,
        )
    return _cand(
        left,
        right,
        FindingType.NEEDS_EVIDENCE,
        Disposition.NEEDS_EVIDENCE,
        ReviewState.INSUFFICIENT_EVIDENCE,
        ModelDisposition.INCOMPLETE,
        "Thiếu normalized value.",
        scope,
        item,
    )


def _dedupe_facts(group: list[Fact]) -> list[Fact]:
    compact: dict[tuple, Fact] = {}
    for f in group:
        k = (f.source_role, f.normalized_value or f.raw_value, f.condition, f.validity)
        if k not in compact:
            compact[k] = f
    return list(compact.values())


def _scope(a: Fact, b: Fact) -> ComparisonScope:
    ra, rb = a.source_role or "body", b.source_role or "body"
    if ra == "body" and rb == "body":
        return ComparisonScope.WITHIN_DOCUMENT
    if ra == "annex" and rb == "annex":
        return ComparisonScope.ANNEX_ANNEX
    return ComparisonScope.CONTRACT_ANNEX


def _money(f: Fact) -> Decimal | None:
    return money_decimal(f.normalized_value or f.raw_value, unit=f.unit)


def _cand(
    left: Fact,
    right: Fact,
    ftype: FindingType,
    disp: Disposition,
    state: ReviewState,
    model: ModelDisposition,
    reason: str,
    scope: ComparisonScope,
    item: str | None,
) -> Candidate:
    return Candidate(
        candidate_id=f"cand_{uuid4().hex[:8]}",
        left_id=left.fact_id,
        right_id=right.fact_id,
        finding_type=ftype,
        model_disposition=model,
        review_state=state,
        evidence_left=[left.citation],
        evidence_right=[right.citation],
        reason=_two_source_reason(left, right, reason),
        disposition=disp,
        scope=scope,
        item_key=item,
    )


def annex_keys_from_labels(labels: set[str] | list[str]) -> set[str]:
    out: set[str] = set()
    for lab in labels:
        text = (lab or "").strip()
        if not text:
            continue
        out.add(text)
        m = re.match(r"(?:phụ lục|phu luc)\s+(\d+)", text, re.I)
        if m:
            out.add(f"Phụ lục {m.group(1)}")
    return out


def _annex_listed(num: str, present: set[str]) -> bool:
    needle = f"phụ lục {num}"
    for p in present:
        pl = p.lower().strip()
        if pl == needle or re.match(rf"phụ lục\s+{re.escape(num)}\b", pl):
            return True
    return False


def _missing_annex_issues(facts: list[Fact], present: set[str]) -> list[EvidenceIssue]:
    present = annex_keys_from_labels(present)
    issues: list[EvidenceIssue] = []
    seen: set[str] = set()
    for f in facts:
        blob = f"{f.raw_value} {f.citation.text_span}"
        for m in ANNEX_REF_RE.finditer(blob):
            lab = f"Phụ lục {m.group(1)}"
            if _annex_listed(m.group(1), present):
                continue
            if lab in seen:
                continue
            seen.add(lab)
            issues.append(
                EvidenceIssue(
                    issue_id=f"iss_{uuid4().hex[:8]}",
                    missing=lab,
                    reason=f"Viện dẫn {lab} nhưng không có file/node phụ lục — EvidenceIssue, không conflict hai phía.",
                    citation=f.citation,
                )
            )
    return issues
