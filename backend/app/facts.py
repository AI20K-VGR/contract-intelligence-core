import re
from datetime import datetime
from decimal import Decimal

from app.structure import ARTICLE_PATTERN, strip_diacritics


def extract(pages, run_id):
    facts = []
    clause_ref, clause_label = {}, {}
    for page in pages:
        document_id = page["document_id"]
        for line in page["lines"]:
            text = line["text"]
            header = ARTICLE_PATTERN.match(strip_diacritics(text))
            if header:
                clause_ref[document_id] = header.group(2)
                clause_label[document_id] = text
            candidates = []
            for match in re.finditer(
                r"(?<![\d.,])\d{1,3}(?:[.,]\d{3})+\s*(?:VND|VNĐ|đồng)\b", text, re.I
            ):
                amount = re.sub(r"\D", "", match.group())
                candidates.append(
                    ("amount", match.group(), {"amount": str(Decimal(amount)), "currency": "VND"})
                )
            for match in re.finditer(r"\b\d{1,2}/\d{1,2}/\d{4}\b", text):
                try:
                    value = datetime.strptime(match.group(), "%d/%m/%Y").date().isoformat()
                    candidates.append(("date", match.group(), {"date": value}))
                except ValueError:
                    pass
            match = re.search(r"(?:Bên|Party)\s+([AB])\s*:\s*(.+)", text, re.I)
            if match:
                candidates.append((f"party_{match[1].lower()}", match[2], {"name": match[2]}))
            match = re.search(r"(?:trong(?: vòng)?|within)\s+(\d+)\s+(?:ngày|days)\b", text, re.I)
            if match:
                candidates.append(("duration_days", match.group(), {"days": int(match[1])}))
            for field, raw, value in candidates:
                facts.append(
                    {
                        "id": f"fact:{line['id']}:{len(facts)}",
                        "type": field,
                        "raw": raw,
                        "normalized": value,
                        "document_id": page["document_id"],
                        "source_role": page["role"],
                        "context": {
                            "source_line": text,
                            "scope_verified": False,
                            "clause_ref": clause_ref.get(document_id),
                            "clause_label": clause_label.get(document_id),
                        },
                        "citation_ids": [f"{run_id}:{line['id']}"],
                        "confidence": {
                            "score": None,
                            "calibrated": False,
                            "review_priority": "high",
                            "signals": {"source_resolved": True, "context_complete": False},
                        },
                    }
                )
    return facts
