from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from decimal import Decimal
from uuid import uuid4

from app.contracts.models import (
    Candidate,
    ComparisonScope,
    Disposition,
    EvidenceIssue,
    Fact,
    FindingType,
    ModelDisposition,
    ReviewState,
)
from app.pipeline.ai1_snapshot_adapter import fold_for_match
from app.pipeline.relation_markers import annex_amendment_title_targets

AMEND_RE = re.compile(r"sửa|sua|thay thế|thay the|điều chỉnh|dieu chinh|amends?", re.I)
ANNEX_REF_RE = re.compile(r"(?:phụ lục|phu luc)\s+(\d+)", re.I)
MAX_PAIRINGS_PER_ITEM = 500


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
    require_relation_for_cross_document: bool = False,
    split_installments: bool = False,
) -> tuple[list[Candidate], list[EvidenceIssue]]:
    """One finding = two sources in the same contract context. No legal winner."""
    annex_labels_present = annex_labels_present or set()
    relation_pairs = {_relation_key(*pair) for pair in (relation_pairs or set())}
    issues = _missing_annex_issues(facts, annex_labels_present)
    keyed: dict[tuple, list[Fact]] = defaultdict(list)
    for f in facts:
        if _is_identity_fact(f):
            continue
        ck = _context_key(f, split_installments)
        if ck[0] is None or ck[0] == "mst_seller":
            continue
        keyed[ck].append(f)
    if split_installments:
        _share_unmarked_installments(keyed)

    out: list[Candidate] = _compare_contract_identities(facts)
    for ctx, group in keyed.items():
        item = ctx[0]
        compact = _dedupe_facts(group)
        issues.extend(_missing_pairing_evidence(compact, item, relation_pairs))
        if _pairing_count(compact) > MAX_PAIRINGS_PER_ITEM:
            issues.append(
                EvidenceIssue(
                    issue_id=f"pairing-cap:{item}",
                    missing="PAIRING_COVERAGE_CAPPED",
                    reason=f"Pairing cap {MAX_PAIRINGS_PER_ITEM} reached for item {item}; remaining pairs need review.",
                    citation=compact[0].citation if compact else None,
                    review_state=ReviewState.NEEDS_REVIEW,
                )
            )
        out.extend(
            _pair_two_sources(
                compact,
                item,
                relation_pairs,
                require_relation_for_cross_document=require_relation_for_cross_document,
            )
        )

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
    if split_installments:
        # Defensive: an unmarked fact joins one group, but keep one finding per fact pair.
        seen: set[tuple[str, str, str]] = set()
        unique = []
        for cand in out:
            key = (*sorted((cand.left_id, cand.right_id)), str(cand.finding_type))
            if key not in seen:
                seen.add(key)
                unique.append(cand)
        out = unique
        # Several installment groups of one item raise the same item-level issue.
        issues = list({issue.issue_id: issue for issue in issues}.values())
    return out, issues


def _is_identity_fact(fact: Fact) -> bool:
    """Keep legacy term routing; unit identities use their own comparison lane."""

    role = str(fact.role or "").casefold()
    key = str(fact.item_key or "").casefold()
    return (
        role.startswith(("party_", "mst_party_"))
        or key.startswith("party_")
        or bool(
            fact.scope and fact.scope.startswith("contract-unit:") and key.startswith("mst_party_")
        )
    )


def _compare_contract_identities(facts: list[Fact]) -> list[Candidate]:
    grouped: dict[tuple[str, str], dict[str, list[Fact]]] = defaultdict(lambda: defaultdict(list))
    for fact in facts:
        if (
            not _is_identity_fact(fact)
            or not fact.scope
            or not fact.scope.startswith("contract-unit:")
        ):
            continue
        if not fact.citation.source_file_id or fact.source_role == "annex":
            continue
        item = fact.item_key or fact.role
        if item:
            grouped[(fact.citation.source_file_id, item)][fact.scope].append(fact)
    output: list[Candidate] = []
    for (_, item), units in grouped.items():
        representatives: list[Fact] = []
        for values in units.values():
            unique = {" ".join(f.raw_value.split()).casefold(): f for f in values}
            # Ambiguous identities inside one unit must not be chosen silently.
            if len(unique) == 1:
                representatives.append(next(iter(unique.values())))
        for index, left in enumerate(representatives):
            for right in representatives[index + 1 :]:
                if (
                    " ".join(left.raw_value.split()).casefold()
                    == " ".join(right.raw_value.split()).casefold()
                ):
                    continue
                output.append(
                    _cand(
                        left,
                        right,
                        FindingType.COMPARABLE_DIFFERENCE,
                        Disposition.COMPARABLE_DIFFERENCE,
                        ReviewState.NEEDS_REVIEW,
                        ModelDisposition.UNCLEAR,
                        "Định danh khác nhau giữa hai hợp đồng trong cùng PDF; cần người duyệt, "
                        "AI2 không kết luận bên nào thắng.",
                        ComparisonScope.CONTRACT_CONTRACT,
                        item,
                    )
                )
    return output


# "Đợt 1"/"lần 2"/"giai đoạn 3": one schedule's installments are different terms, so they are
# compared only with the same installment (30% for đợt 1 vs 40% for đợt 2 is not a conflict, #121).
_INSTALLMENT = re.compile(r"\b(?:dot|lan|giai doan)\s+(\d{1,2})\b")
_INSTALLMENT_KEYS = frozenset({"payment_schedule", "payment_term"})


def _installment(f: Fact) -> str | None:
    """The installment this value belongs to: the last "đợt N" before the value.

    A sentence naming several installments ("đợt 1: 30%; đợt 2: 40%") keys each value by
    its own one; when the value cannot be located among several, the fact stays unmarked.
    """
    span = fold_for_match(f.citation.text_span or f.raw_value or "")
    marks = list(_INSTALLMENT.finditer(span))
    numbers = {m.group(1).lstrip("0") or "0" for m in marks}
    if len(numbers) <= 1:
        return next(iter(numbers), None)
    at = span.find(fold_for_match(f.raw_value or "")) if f.raw_value else -1
    before = [m for m in marks if m.end() <= at] if at >= 0 else []
    return before[-1].group(1).lstrip("0") or "0" if before else None


def _context_key(f: Fact, split_installments: bool = False) -> tuple:
    # Split only with the contract graph pairs on: the flag-off output is pinned byte-for-byte.
    split = split_installments and f.item_key in _INSTALLMENT_KEYS
    return (f.item_key or f.scope, _installment(f) if split else None)


def _share_unmarked_installments(keyed: dict[tuple, list[Fact]]) -> None:
    """A schedule fact naming no installment ("tạm ứng 30%") joins one installment group.

    It goes to the installment holding the same value, else to the first installment, so
    "tạm ứng 30%" is still compared with "Đợt 1: 25%" (PR #125 review 1d) but never with
    "Đợt 2: 40%" (#121). Without installment groups it stays put.
    """
    for (item, number), facts in list(keyed.items()):
        if number is not None:
            continue
        marked = sorted(
            (key for key in keyed if key[0] == item and key[1] is not None),
            key=lambda key: (int(key[1]), key[1]),
        )
        if not marked:
            continue
        for fact in facts:
            value = fact.normalized_value or fact.raw_value
            target = next(
                (
                    key
                    for key in marked
                    if any(
                        (other.normalized_value or other.raw_value) == value for other in keyed[key]
                    )
                ),
                marked[0],
            )
            keyed[target] = [*keyed[target], fact]
        del keyed[(item, number)]


def _pair_two_sources(
    group: list[Fact],
    item: str,
    relation_pairs: set[tuple[str, str]],
    *,
    require_relation_for_cross_document: bool = False,
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
        emitted = 0
        for _pl, afs in annexes.items():
            for annex_rep in _unique_values(afs):
                if emitted >= MAX_PAIRINGS_PER_ITEM:
                    break
                cand = _pair(body_rep, annex_rep, item)
                if cand:
                    relation_confirmed = _relation_confirmed(body_rep, annex_rep, relation_pairs)
                    if require_relation_for_cross_document and not relation_confirmed:
                        continue
                    if not relation_confirmed:
                        cand = cand.model_copy(
                            update={
                                "reason": "relation_unconfirmed; " + cand.reason,
                                "review_state": ReviewState.NEEDS_REVIEW,
                            }
                        )
                    out.append(cand)
                    emitted += 1
            if emitted >= MAX_PAIRINGS_PER_ITEM:
                break
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


def _relation_confirmed(left: Fact, right: Fact, relation_pairs: set[tuple[str, str]]) -> bool:
    left_file, right_file = left.citation.source_file_id, right.citation.source_file_id
    return (
        not left_file
        or not right_file
        or left_file == right_file
        or _relation_key(left.citation.node_id, right.citation.node_id) in relation_pairs
    )


def _missing_pairing_evidence(
    group: list[Fact], item: str, relation_pairs: set[tuple[str, str]]
) -> list[EvidenceIssue]:
    bodies = [fact for fact in group if (fact.source_role or "body") != "annex"]
    annexes = [fact for fact in group if (fact.source_role or "body") == "annex"]
    if not bodies or not annexes:
        return []
    missing: list[tuple[Fact, Fact]] = []
    scanned = 0
    for body in bodies:
        for annex in annexes:
            if scanned >= MAX_PAIRINGS_PER_ITEM:
                break
            scanned += 1
            if not _relation_confirmed(body, annex, relation_pairs):
                missing.append((body, annex))
        if scanned >= MAX_PAIRINGS_PER_ITEM:
            break
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
    if left.tax_basis and right.tax_basis and left.tax_basis != right.tax_basis:
        return _cand(
            left,
            right,
            FindingType.GAP,
            Disposition.NOT_COMPARABLE,
            ReviewState.NOT_COMPARABLE,
            ModelDisposition.INCOMPLETE,
            "Khác cơ sở thuế; không so trực tiếp các giá trị.",
            scope,
            item,
        )
    if bool(left.tax_basis) != bool(right.tax_basis) and (left.currency or right.currency):
        return _cand(
            left,
            right,
            FindingType.NEEDS_EVIDENCE,
            Disposition.NEEDS_EVIDENCE,
            ReviewState.INSUFFICIENT_EVIDENCE,
            ModelDisposition.INCOMPLETE,
            "Thiếu căn cứ xác định giá trị đã gồm thuế hay chưa.",
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
    cite_blob = (
        f"{right.citation.text_span} {left.citation.text_span} {right.raw_value} {left.raw_value}"
    )
    subject_is_evidence = str(item).startswith("penalty") or str(item) in {"A", "B"}
    if subject_is_evidence:
        cite_blob += f" {right.subject or ''} {left.subject or ''}"
    is_amend = _explicit_amend_pair(left, right) or (
        subject_is_evidence
        and any(
            annex_amendment_title_targets(annex.subject, body.subject)
            for annex, body in ((left, right), (right, left))
            if annex.source_role == "annex" and body.source_role == "body"
        )
    )
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


def _explicit_amend_pair(left: Fact, right: Fact) -> bool:
    def clause_number(fact: Fact) -> str | None:
        text = f"{fact.subject or ''} {fact.citation.text_span}"
        match = re.search(r"(?:điều|dieu|article)\s+(\d+(?:\.\d+)?)", text, re.I)
        return match.group(1) if match else None

    for source, target in ((left, right), (right, left)):
        number = clause_number(target)
        source_text = f"{source.subject or ''} {source.citation.text_span}"
        folded = unicodedata.normalize("NFD", source_text.casefold())
        folded = "".join(char for char in folded if unicodedata.category(char) != "Mn")
        if re.search(r"\b(?:khong|chua)\s+(?:duoc\s+)?(?:sua|thay the|dieu chinh)\b", folded):
            continue
        has_replacement_phrase = bool(re.search(r"\b(?:duoc\s+)?thay\s+bang\b", folded))
        targets_clause = bool(
            number
            and re.search(
                rf"(?:sửa|sua|sửa đổi|sua doi|thay thế|thay the|điều chỉnh|dieu chinh|amends?)\s+(?:điều\s+|dieu\s+|article\s+)?{re.escape(number)}\b",
                source_text,
                re.I,
            )
        )
        if number and (
            targets_clause
            or (has_replacement_phrase and re.search(rf"\b{re.escape(number)}\b", folded))
        ):
            return True
        item = str(target.item_key or "")
        if (
            item
            and AMEND_RE.search(source_text)
            and re.search(
                rf"(?:sửa|sua)\s+(?:mục\s+|item\s+)?{re.escape(item)}\s+(?:thành|thanh|to)\b",
                source_text,
                re.I,
            )
        ):
            return True
    return False


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


_ANNEX_NUMBER = re.compile(r"(?:phụ lục|phu luc)\s+(?:số\s+|so\s+)?(\d+)\b", re.I)


def annex_keys_from_labels(labels: set[str] | list[str]) -> set[str]:
    """Numbered annex identities only.

    A sentence that merely starts with \"Phụ lục này\" is boilerplate, not an
    annex. Live dossier dos_01M3BPQFSXW68FGZJ1RPFMYXTY stored that sentence as
    an annex label and the coverage list treated it as a fifth annex.
    """

    out: set[str] = set()
    for lab in labels:
        text = (lab or "").strip()
        match = _ANNEX_NUMBER.match(text)
        if match:
            out.add(f"Phụ lục {match.group(1)}")
    return out


def _pairing_count(group: list[Fact]) -> int:
    bodies = [fact for fact in group if (fact.source_role or "body") != "annex"]
    annexes: dict[str, list[Fact]] = defaultdict(list)
    for fact in group:
        if (fact.source_role or "body") == "annex":
            annexes[fact.validity or "PL"].append(fact)
    if bodies and annexes:
        emitted = sum(len(_unique_values(values)) for values in annexes.values())
        relation_checks = len(bodies) * sum(len(values) for values in annexes.values())
        return max(emitted, relation_checks)
    if len(bodies) > 1:
        return 1
    return 1 if len(annexes) > 1 else 0


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
