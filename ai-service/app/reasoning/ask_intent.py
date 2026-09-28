"""Split a question into scope and attribute before any clause dump."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from app.reasoning.l0_rules import query_too_broad


def _plain(value: str) -> str:
    text = unicodedata.normalize("NFD", (value or "").casefold())
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return text.replace("đ", "d")


def _word(text: str, word: str) -> bool:
    return re.search(rf"\b{re.escape(word)}\b", text) is not None


def _clause_label(plain: str) -> str | None:
    match = re.search(r"\bdieu\s+(\d+(?:\.\d+)?)", plain)
    if not match:
        return None
    return f"Điều {match.group(1)}"


def _annex_numbers(plain: str) -> list[str]:
    return [match.group(1) for match in re.finditer(r"\b(?:phu luc|annex)\s+(\d+)", plain)]


def _party_roles(plain: str) -> list[str]:
    """Every role named, in order: "Bên A và bên B là ai?" asks about both."""
    return list(dict.fromkeys(m.upper() for m in re.findall(r"\b(?:ben|party)\s+([abcy])\b", plain)))


def _party_role(plain: str) -> str | None:
    roles = _party_roles(plain)
    return roles[0] if roles else None


def _attribute(plain: str, low: str) -> str:
    if any(cue in plain for cue in ("quy doi", "usd")) and "vnd" in plain:
        return "fx"
    if "gop" in plain and "phat" in plain and ("xay lap" in plain or "thiet bi" in plain):
        return "fx"
    if re.search(r"\bco phai\b", plain) and re.search(r"\d|trieu|ty\b|nghin|vnd|dong", plain):
        return "money"
    if "mst" in low or "ma so thue" in low or "tax id" in low or "tax code" in low:
        return "mst"
    if "phat" in plain or "penalty" in plain:
        return "penalty"
    if any(word in low for word in ("thanh toán", "thanh toan", "payment")) or "thanh toan" in plain:
        return "payment"
    if any(word in low for word in ("giá trị", "gia tri", "giá hợp đồng", "contract value")) or "gia tri" in plain:
        return "contract_value"
    return "none"


def _relation_question(plain: str) -> bool:
    mentions_annex = "phu luc" in plain or "annex" in plain
    mentions_body = any(phrase in plain for phrase in ("hop dong", "dieu khoan", "than hop dong", "than hd"))
    if not (mentions_annex and mentions_body):
        return False
    if "lien quan" in plain or "moi quan he" in plain or "quan he" in plain:
        return True
    return any(phrase in plain for phrase in ("co dan chieu", "co sua", "lien quan den nhau"))


def _compare_cue(plain: str) -> bool:
    phrases = (
        "moi quan he",
        "anh huong",
        "dan chieu",
        "thay the",
        "dinh nghia",
        "cascade",
        "so sanh",
        "khac nhau",
        "sua doi",
    )
    if any(phrase in plain for phrase in phrases):
        return True
    if _word(plain, "sua"):
        return True
    if "lien quan" in plain and not _relation_question(plain):
        return "dieu" in plain or "phu luc" in plain or "annex" in plain
    return False


def parse_ask(text: str) -> dict[str, Any]:
    """Return the ask task. Scope never replaces the attribute the user asked for."""

    query = (text or "").strip()
    low = query.lower()
    plain = _plain(query)
    spec: dict[str, Any] = {
        "id": "ask",
        "query": query,
        "must_cite": [],
        "forbidden": ["legal_winner", "full_pdf_dump"],
        "attribute": "none",
        "scope": None,
    }
    clause = _clause_label(plain)
    annexes = _annex_numbers(plain)
    role = _party_role(plain)
    attribute = _attribute(plain, low)
    if clause:
        spec["scope"] = {"kind": "clause", "label": clause}
        spec["clause_label"] = clause
    elif annexes:
        spec["scope"] = {"kind": "annex", "n": annexes[0]}
    elif role:
        spec["scope"] = {"kind": "party", "role": role}
    spec["attribute"] = attribute

    if _relation_question(plain):
        spec["type"] = "relation_ask"
        spec["focus_clause_labels"] = [clause] if clause else []
        spec["annex_numbers"] = annexes
        return spec

    if attribute == "fx":
        spec["type"] = "not_comparable"
        return spec

    if attribute == "money":
        spec["type"] = "raw_fact_check"
        spec["fact_intent"] = "money"
        return spec

    if attribute == "contract_value":
        spec["type"] = "field_card"
        spec["field_key"] = "contract_value"
        return spec

    has_source = bool(clause or annexes or "hop dong" in plain)
    if _compare_cue(plain) and has_source:
        spec["type"] = "cascade" if any(cue in plain for cue in ("anh huong", "dinh nghia", "cascade")) else "compare"
        spec["focus_clause_labels"] = [clause] if clause else []
        spec["annex_numbers"] = annexes
        spec["relation_intent"] = plain
        return spec

    if attribute == "payment" and role:
        spec["type"] = "lookup_term"
        spec["role"] = role
        return spec

    if attribute == "penalty" and clause:
        spec["type"] = "attribute_lookup"
        return spec

    if attribute == "contract_value":
        spec["type"] = "field_card"
        spec["field_key"] = "contract_value"
        return spec

    if attribute == "mst":
        spec["type"] = "field_card"
        spec["field_key"] = "mst_seller"
        return spec

    if attribute == "penalty":
        spec["type"] = "field_card"
        spec["field_key"] = "penalty"
        return spec

    if role and attribute == "none":
        spec["type"] = "party_card"
        spec["role"] = role
        spec["roles"] = _party_roles(plain)
        return spec

    if clause and attribute == "none":
        spec["type"] = "lookup_clause"
        return spec

    if annexes and attribute == "none":
        spec["type"] = "annex_card"
        spec["annex_n"] = annexes[0]
        return spec

    if "phu luc" in plain and any(cue in plain for cue in ("co ", "nao", "danh sach", "bao nhieu", "may")):
        spec["type"] = "annex_list"
        return spec

    if query_too_broad(query):
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

    if "bao nhieu ben" in plain or "bao nhieu phap nhan" in plain or "may ben" in plain:
        spec["type"] = "count_entity"
        return spec

    if any(word in low for word in ("ngày làm việc", "working day", "nghiệm thu", "định nghĩa", "acceptance")) or any(
        word in plain
        for word in (
            "thoi han",
            "hieu luc",
            "ngay ky",
            "tu ngay",
            "thanh toan",
            "tien do",
            "thoi gian trien khai",
            "bao lau",
        )
    ):
        spec["type"] = "lookup_term"
        return spec

    spec["type"] = "unscoped"
    return spec
