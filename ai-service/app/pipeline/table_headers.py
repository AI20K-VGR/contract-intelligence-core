"""Conservative header recognition; raw rows and cell coordinates stay intact."""
import re
import unicodedata
from decimal import Decimal, InvalidOperation


def fold(value: str) -> str:
    value = unicodedata.normalize("NFD", str(value).lower())
    return " ".join("".join(c for c in value if unicodedata.category(c) != "Mn").replace("đ", "d").split())


def amount_column(header: list[str]) -> int | None:
    aliases = ("amount", "thanh tien", "total amount", "line total", "tong cong", "gia tri", "subtotal", "total")
    matches = [i for i, value in enumerate(header) if any(alias == fold(value) or alias in fold(value) for alias in aliases)]
    return matches[0] if len(matches) == 1 else None


def identify_header(rows):
    """Return a conservative header and contiguous unit/continuation rows."""
    for index, row in enumerate(rows[:5]):
        header = [str(value or "") for value in row]
        folded = [fold(v) for v in header]
        aliases = ("description", "mo ta", "noi dung", "dien giai", "hang muc", "item", "unit", "dvt", "qty", "sl", "quantity", "don gia", "unit price")
        if amount_column(header) is not None and any(
            any(alias == value or alias in value for alias in aliases) for value in folded
        ):
            header_rows = [index]
            for continuation_index, continuation in enumerate(rows[index + 1:index + 3], index + 1):
                values = [str(value or "").strip() for value in continuation]
                non_empty = [fold(value) for value in values if value]
                if not non_empty or all(
                    value.startswith(("(", "[")) or any(token in value for token in ("vnd", "usd", "don vi", "quantity", "price", "amount"))
                    for value in non_empty
                ):
                    header_rows.append(continuation_index)
                    continue
                break
            return header, header_rows
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
