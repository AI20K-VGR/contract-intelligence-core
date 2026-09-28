from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from decimal import Decimal, InvalidOperation

from benchmark.metrics.text import normalize_text
from benchmark.schemas import GroundTruthField


def normalize_money(value: str) -> str:
    cleaned = re.sub(r"[^0-9,.-]", "", value)
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif re.fullmatch(r"-?\d{1,3}(?:[.,]\d{3})+", cleaned):
        cleaned = cleaned.replace(".", "").replace(",", "")
    try:
        return format(Decimal(cleaned).normalize(), "f")
    except InvalidOperation:
        return cleaned


def normalize_date(value: str) -> str:
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    return normalize_text(value)


def normalize_contract_number(value: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFC", value)).casefold()


def normalize_tax_code(value: str) -> str:
    return re.sub(r"[^0-9]", "", value)


def normalize_field(kind: str, value: str) -> str:
    kind = kind.casefold()
    if kind in {"total_amount", "amount", "money", "vat"}:
        return normalize_money(value)
    if kind in {"contract_date", "effective_date", "date", "deadline"}:
        return normalize_date(value)
    if kind in {"contract_number", "appendix_reference", "clause_number"}:
        return normalize_contract_number(value)
    if kind == "tax_code":
        return normalize_tax_code(value)
    return normalize_text(value)


def _candidate_values(kind: str, text: str) -> list[str]:
    key = kind.casefold()
    if key in {"total_amount", "amount", "money", "vat"}:
        return re.findall(r"(?<!\d)\d[\d.,\s]{0,30}(?!\d)", text)
    if key in {"contract_date", "effective_date", "date", "deadline"}:
        return re.findall(r"(?<!\d)(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/.-]\d{1,2}[/.-]\d{4})(?!\d)", text)
    if key == "tax_code":
        return re.findall(r"(?<!\d)\d(?:[\s-]?\d){7,13}(?!\d)", text)
    if key in {"contract_number", "appendix_reference", "clause_number"}:
        return re.findall(r"(?<!\w)[\wÀ-ỹ]+(?:\s*[-/.]\s*[\wÀ-ỹ]+)+(?!\w)", text)
    return [text]


def evaluate_fields(fields: list[GroundTruthField], prediction: str) -> tuple[dict, list[dict]]:
    rows = []
    for field in fields:
        exact = field.raw_value in prediction
        target = field.normalized_value or normalize_field(field.field_type, field.raw_value)
        candidates = _candidate_values(field.field_type, prediction)
        normalized = any(normalize_field(field.field_type, value) == target for value in candidates)
        rows.append(
            {
                "field_type": field.field_type,
                "ground_truth": field.raw_value,
                "normalized_ground_truth": target,
                "exact_match": int(exact),
                "normalized_match": int(normalized),
            }
        )
    total = len(rows)
    return (
        {
            "critical_field_total": total,
            "critical_field_exact_accuracy": sum(r["exact_match"] for r in rows) / total if total else None,
            "critical_field_accuracy": sum(r["normalized_match"] for r in rows) / total if total else None,
        },
        rows,
    )
