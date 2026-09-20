import re

from app.domain import Disposition

# Signals an annex clause states it revises/replaces a contract clause, per
# docs/architecture.md §9.3: "candidate_amendment | Khác biệt kèm evidence điều khoản
# sửa/thay thế". Detecting this from keywords is a candidate for reviewer confirmation,
# never an automatic conclusion that the newer text takes precedence.
AMENDMENT_PATTERN = re.compile(
    r"sửa đổi|sửa lại|thay đổi|thay thế|điều chỉnh|amend|modif(?:y|ied|ication)|replaces?",
    re.IGNORECASE,
)


def _values_equal(fact_type, a_value, b_value):
    """Field-specific equality with no epsilon/implicit conversion (docs §9.4).

    Returns None when the two values are not on directly comparable units (e.g.
    different currencies) rather than silently treating them as unequal.
    """
    if fact_type == "amount":
        if a_value["currency"] != b_value["currency"]:
            return None
        return a_value["amount"] == b_value["amount"]
    return a_value == b_value


def _mentions_amendment(fact):
    haystack = f"{fact['context']['source_line']} {fact['context'].get('clause_label') or ''}"
    return bool(AMENDMENT_PATTERN.search(haystack))


def compare(facts):
    findings = []
    contract = [f for f in facts if f["source_role"] == "contract"]
    annex = [f for f in facts if f["source_role"] == "appendix"]
    for a in contract:
        for b in annex:
            if a["type"] != b["type"]:
                continue
            clause_a, clause_b = a["context"].get("clause_ref"), b["context"].get("clause_ref")
            values_equal = a["normalized"] == b["normalized"]
            if clause_a is None or clause_b is None or clause_a != clause_b:
                # Same fact type alone never establishes subject/scope — only a shared,
                # identified clause anchor does. Otherwise two "amount" facts could be a
                # deposit and a penalty; comparing them would be a false conflict/match.
                disposition = Disposition.INSUFFICIENT
                rationale = (
                    "Không xác định được cùng điều khoản giữa hai phía; "
                    "thiếu evidence phạm vi để kết luận quan hệ."
                )
            else:
                equal = _values_equal(a["type"], a["normalized"], b["normalized"])
                if equal is None:
                    disposition = Disposition.INSUFFICIENT
                    rationale = "Cùng điều khoản nhưng khác đơn vị tiền tệ; không tự quy đổi tỷ giá."
                elif equal:
                    disposition = Disposition.MATCH
                    rationale = "Cùng điều khoản, cùng giá trị đã chuẩn hoá."
                elif _mentions_amendment(b):
                    disposition = Disposition.AMENDMENT
                    rationale = (
                        "Cùng điều khoản, giá trị khác nhau; phụ lục có từ khoá sửa đổi/thay thế "
                        "— cần reviewer xác nhận hiệu lực, không tự kết luận."
                    )
                else:
                    disposition = Disposition.DIFFERENCE
                    rationale = "Cùng điều khoản, giá trị khác nhau; chưa có bằng chứng điều khoản sửa đổi."
            findings.append(
                {
                    "id": f"finding:{len(findings)}",
                    "topic": a["type"],
                    "disposition": disposition.value,
                    "comparison_kind": "structured",
                    "scope": "contract_annex",
                    "fact_ids": [a["id"], b["id"]],
                    "rule_version": "local-v2",
                    "values_equal": values_equal,
                    "rationale": rationale,
                    "citations_a": a["citation_ids"],
                    "citations_b": b["citation_ids"],
                }
            )
    return findings
