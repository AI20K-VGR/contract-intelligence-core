import re
from datetime import date
from decimal import Decimal, InvalidOperation

from app.domain import require


def validate_correction(fact, value):
    """Accept only normalized values of the original fact type; never accept source IDs."""
    kind = fact["type"]
    if kind == "amount":
        require(set(value) == {"amount", "currency"}, "INVALID_CORRECTION", 422)
        require(isinstance(value["amount"], str) and value["currency"] == "VND",
                "INVALID_CORRECTION", 422)
        require(re.fullmatch(r"(?:0|[1-9][0-9]{0,29})", value["amount"]) is not None,
                "INVALID_CORRECTION", 422)
        try:
            amount = Decimal(value["amount"])
            valid = amount.is_finite() and amount >= 0 and amount == amount.to_integral_value()
        except InvalidOperation:
            valid = False
        require(valid, "INVALID_CORRECTION", 422)
        require(len(value["amount"]) <= 40, "INVALID_CORRECTION", 422)
    elif kind == "date":
        require(set(value) == {"date"} and isinstance(value["date"], str),
                "INVALID_CORRECTION", 422)
        try:
            valid = date.fromisoformat(value["date"]).isoformat() == value["date"]
        except ValueError:
            valid = False
        require(valid, "INVALID_CORRECTION", 422)
    elif kind == "duration_days":
        require(set(value) == {"days"} and type(value["days"]) is int
                and 0 <= value["days"] <= 365000, "INVALID_CORRECTION", 422)
    elif kind in ("party_a", "party_b"):
        require(set(value) == {"name"} and isinstance(value["name"], str)
                and 0 < len(value["name"].strip()) <= 2000, "INVALID_CORRECTION", 422)
    else:
        require(False, "UNSUPPORTED_CORRECTION", 422)
    return value
