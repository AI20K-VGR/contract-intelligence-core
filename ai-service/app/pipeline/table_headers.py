"""Conservative header recognition; raw rows and cell coordinates stay intact."""
import re
import unicodedata
from decimal import Decimal, InvalidOperation


def fold(value: str) -> str:
    value = unicodedata.normalize("NFD", str(value).lower())
    return " ".join("".join(c for c in value if unicodedata.category(c) != "Mn").replace("đ", "d").split())


def amount_column(header: list[str]) -> int | None:
    matches = [i for i, value in enumerate(header) if fold(value) in {"amount", "thanh tien", "total amount", "line total"}]
    return matches[0] if len(matches) == 1 else None


def identify_header(rows):
    for index, row in enumerate(rows[:3]):
        header = [str(value or "") for value in row]
        if amount_column(header) is not None and any(fold(v) in {"description", "mo ta", "noi dung", "noi dung / dien giai", "unit", "dvt", "qty", "sl"} for v in header):
            return header, [index]
    return [], []


def parse_amount(raw):
    text = str(raw or "").strip().replace(" ", "")
    # Multiple three-digit groups are unambiguous Vietnamese thousands.
    if re.fullmatch(r"-?\d{1,3}(?:\.\d{3}){2,}", text):
        text = text.replace(".", "")
    elif re.fullmatch(r"-?\d{1,3}(?:,\d{3})+", text):
        text = text.replace(",", "")
    elif re.fullmatch(r"-?\d+\.\d{3}", text):
        return None  # Ambiguous decimal/thousands without a locale contract.
    try:
        value = Decimal(text)
        return str(value) if value.is_finite() else None
    except InvalidOperation:
        return None
