"""Conservative local extraction; unsupported grammar remains visible for review."""

from __future__ import annotations

import hashlib
import re
from decimal import Decimal

from app.contracts.clause_frames import SLOT_NAMES, ClauseFrame, Evidence, Slot
from app.contracts.contract_profiles import get_contract_profile, map_profile_field

_ACTION = re.compile(r"\b(thanh toán|giao hàng|bồi thường|thông báo|chấm dứt|tiết lộ)\b", re.I)
_SYMBOLS = {"thanh toán": "PAY", "giao hàng": "DELIVER", "bồi thường": "COMPENSATE",
            "thông báo": "NOTIFY", "chấm dứt": "TERMINATE", "tiết lộ": "DISCLOSE"}
_PARTY = re.compile(r"\bbên\s+([ab])\b", re.I)
_MONEY = re.compile(
    r"(?<![\d.,])(?P<amount>\d[\d.,\s]*\d|\d)\s*"
    r"(?P<currency>VND|USD|EUR|\u0111\u1ed3ng|\u0111)\b",
    re.I,
)
_TOTAL_LABEL = re.compile(
    r"(?:t\u1ed5ng\s+gi\u00e1\s+tr\u1ecb\s+h\u1ee3p\s+\u0111\u1ed3ng|"
    r"t\u1ed5ng\s+c\u1ed9ng|grand\s+total|total)",
    re.I,
)
_BARE_NUMBER = re.compile(r"(?<![\d.,])(\d[\d.,\s]*\d|\d)(?![\d.,])")


def extract_frames(source: Evidence, *, profile: str, dossier_id: str) -> tuple[ClauseFrame, ...]:
    contract_profile = get_contract_profile(profile)
    frames = []
    for clause_match in re.finditer(r"[^;]+", source.raw):
        raw = clause_match.group().strip()
        if not raw:
            continue
        evidence = Evidence(source.document_id, source.snapshot_id,
                            f"{source.source_ref}#span{clause_match.start()}", raw)
        actions = list(_ACTION.finditer(raw))
        for action in actions or [None]:
            slots = {name: Slot(None, "UNKNOWN", (evidence,), "not_assessed")
                     for name in sorted(SLOT_NAMES)}

            def grounded(name: str, value: str | Decimal) -> None:
                slots[name] = Slot(value, "GROUNDED", (evidence,))

            def absent(name: str) -> None:
                slots[name] = Slot(None, "ABSENT", (evidence,))

            prefix = raw[:action.start()].casefold() if action else raw.casefold()
            parties = list(_PARTY.finditer(prefix))
            party = parties[0] if len(parties) == 1 else None
            family = "OBLIGATION"
            modality = None
            if re.search(r"kh\u00f4ng\s+\u0111\u01b0\u1ee3c(?:\s+ph\u00e9p)?\s*$", prefix):
                family, modality = "PROHIBITION", "PROHIBITED"
            elif (re.search(r"\u0111\u01b0\u1ee3c\s+ph\u00e9p\s*$", prefix)
                  and not re.search(r"\b(?:kh\u00f4ng|ch\u01b0a|ch\u1eb3ng)\b", prefix)):
                family, modality = "RIGHT", "PERMITTED"
            elif re.search(r"(?:phải|có\s+nghĩa\s+vụ)\s*$", prefix) and "không" not in prefix:
                modality = "REQUIRED"
            passive = bool(re.search(r"được\s*$", prefix)) and modality is None
            if party:
                if passive:
                    grounded("beneficiary", party.group(1).upper())
                else:
                    grounded("actor", party.group(1).upper())
                    absent("beneficiary")
            if modality:
                grounded("modality_negation", modality)
            if action:
                symbol = _SYMBOLS[action.group().casefold()]
                grounded("action", symbol)
                if symbol in {"PAY", "DELIVER", "COMPENSATE"}:
                    object_match = re.search(
                        r"\b(?:thanh to\u00e1n|giao h\u00e0ng|b\u1ed3i th\u01b0\u1eddng)\s+(.+?)"
                        r"(?=\s+(?:trong|sau|khi|n\u1ebfu)\b|[.,;](?!\d)|$)",
                        raw,
                        re.I,
                    )
                    object_value = object_match.group(1).strip() if object_match else ""
                    # Amounts and units are separate semantic slots.  Keeping
                    # ``30%`` in object scope makes two milestones look like
                    # disjoint goods and suppresses the value comparison.
                    object_value = _MONEY.sub("", object_value)
                    object_value = re.sub(
                        r"(?<![\w.,])\d+(?:[.,]\d+)*\s*%(?!\w)",
                        "",
                        object_value,
                        flags=re.I,
                    ).strip(" ,:-")
                    if object_value and not re.match(r"(?:theo|nh\u01b0|t\u00f9y)", object_value, re.I):
                        grounded("object_scope", object_value)
                if symbol == "COMPENSATE" and family == "OBLIGATION":
                    family = "REMEDY"
                    if re.search(r'\bn\u1ebfu\s+vi\s+ph\u1ea1m\b', raw, re.I):
                        grounded("qualifier", "BREACH")
            if not actions:
                definition = re.fullmatch(r'["\u201c]([^"\u201d]+)["\u201d]\s+ngh\u0129a\s+l\u00e0\s+(.+)', raw, re.I)
                parameter = re.fullmatch(r'([^:]{1,120}):\s*(.+)', raw)
                if definition:
                    family = "DEFINITION"
                    grounded("parameter", definition.group(1))
                    grounded("definition", definition.group(2))
                elif parameter:
                    mapped = map_profile_field(contract_profile, parameter.group(1))
                    if mapped.key is not None:
                        family = "PARAMETER"
                        grounded("parameter", mapped.key)
                    elif _TOTAL_LABEL.search(raw):
                        # A parenthetical such as ``Bằng chữ: ...`` can make
                        # the whole clause look like a labelled field.  An
                        # unknown label must not suppress the stronger total
                        # signal; keep the amount comparable as total_price.
                        family = "PARAMETER"
                        grounded("parameter", "total_price")
                elif _TOTAL_LABEL.search(raw):
                    # Totals are parameters, even when the annex table has no
                    # currency/unit column. Keep the missing context UNKNOWN;
                    # the comparator will retain a review pair with citations.
                    family = "PARAMETER"
                    grounded("parameter", "total_price")
            money = list(_MONEY.finditer(raw))
            if len(money) == 1 and len(actions) <= 1:
                amount = _decimal_amount(money[0].group("amount"))
                if amount is not None:
                    grounded("amount", amount)
                currency = money[0].group("currency").casefold()
                grounded("currency", "VND" if currency in {"\u0111", "\u0111\u1ed3ng"} else currency.upper())
                grounded("unit", "money")
            elif not money and len(actions) <= 1 and _TOTAL_LABEL.search(raw):
                # A labelled total without a currency is still a grounded
                # numeric amount; do not invent the currency.
                numbers = _BARE_NUMBER.findall(raw)
                amount = _decimal_amount(numbers[-1]) if numbers else None
                if amount is not None:
                    grounded("amount", amount)
                    grounded("unit", "money")
            if len(actions) <= 1:
                percentages = list(re.finditer(r'(?<![\d.,])\b(\d+)%', raw))
                if len(percentages) == 1 and not money:
                    grounded("amount", Decimal(percentages[0].group(1)))
                    grounded("unit", "percent")
                    absent("currency")
                deadline = re.search(r'\btrong\s+(\d+)\s+(ng\u00e0y\s+l\u00e0m\s+vi\u1ec7c|ng\u00e0y|th\u00e1ng)\b', raw, re.I)
                if deadline:
                    grounded("deadline", deadline.group(1))
                    grounded("deadline_unit", _deadline_unit(deadline.group(2)))
                elif not re.search(r"\btrong\b", raw, re.I):
                    absent("deadline")
                    absent("deadline_unit")
                trigger = _payment_trigger(raw)
                if trigger:
                    grounded("temporal_trigger", trigger)
                condition = re.search(r'\bn\u1ebfu\s+([^,]+)', raw, re.I)
                exception = re.search(r'\btr\u1eeb\s+khi\s+(.+)', raw, re.I)
                if condition:
                    grounded("condition", condition.group(1).strip())
                else:
                    absent("condition")
                if exception:
                    grounded("exception", exception.group(1).strip())
                else:
                    absent("exception")
            identity = "|".join((dossier_id, source.document_id, source.snapshot_id,
                                 evidence.source_ref, str(action.start() if action else -1)))
            frame_id = hashlib.sha256(identity.encode()).hexdigest()[:24]
            frames.append(ClauseFrame(frame_id, family, profile, source.document_id,
                                      source.snapshot_id, (evidence,), tuple(slots.items()), dossier_id))
    return tuple(frames)


def _decimal_amount(raw: str) -> Decimal | None:
    """Parse Vietnamese/European grouped money without guessing decimals."""
    value = re.sub(r"\s+", "", str(raw))
    if not value:
        return None
    if "," in value and "." in value:
        # The final separator is the decimal marker when both appear.
        decimal_sep = "," if value.rfind(",") > value.rfind(".") else "."
        thousands_sep = "." if decimal_sep == "," else ","
        value = value.replace(thousands_sep, "").replace(decimal_sep, ".")
    elif "," in value:
        parts = value.split(",")
        value = "".join(parts) if len(parts[-1]) == 3 else value.replace(",", ".")
    elif value.count(".") > 1:
        value = value.replace(".", "")
    try:
        parsed = Decimal(value)
    except Exception:
        return None
    return parsed if parsed.is_finite() else None


def _deadline_unit(raw: str) -> str:
    folded = raw.casefold()
    if "l\u00e0m vi\u1ec7c" in folded:
        return "business-day"
    return {"ng\u00e0y": "day", "th\u00e1ng": "month"}.get(folded, "unknown")


def _payment_trigger(raw: str) -> str | None:
    patterns = (
        (r"(?:k\u1ec3\s+t\u1eeb|sau\s+khi|khi)\s+(?:ng\u00e0y\s+)?k\u00fd|after\s+signing", "SIGNING"),
        (r"(?:sau\s+khi|khi)\s+giao\s+h\u00e0ng|upon\s+delivery", "DELIVERY"),
        (r"(?:sau\s+khi|khi)\s+nghi\u1ec7m\s+thu|upon\s+acceptance", "ACCEPTANCE"),
        (r"(?:sau\s+khi|khi)\s+(?:nh\u1eadn\s+)?\u0111\u1ee7\s+h\u1ed3\s+s\u01a1|after\s+complete\s+documents", "DOCUMENTS_COMPLETE"),
    )
    return next((symbol for pattern, symbol in patterns if re.search(pattern, raw, re.I)), None)
