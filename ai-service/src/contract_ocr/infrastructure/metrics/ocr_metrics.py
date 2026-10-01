import re
import unicodedata
from collections import Counter
from datetime import datetime

import numpy as np
from rapidfuzz.distance import Levenshtein
from scipy.optimize import linear_sum_assignment

from contract_ocr.domain.bbox import BBox
from contract_ocr.domain.entities import CriticalField


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def base(text: str) -> str:
    return "".join(
        c
        for c in unicodedata.normalize("NFD", text.replace("\u0111", "d").replace("\u0110", "D"))
        if not unicodedata.combining(c)
    )


def error_rate(reference: str | list, hypothesis: str | list) -> float:
    return Levenshtein.distance(reference, hypothesis) / max(1, len(reference))


class OCRMetrics:
    def text(self, reference: str, hypothesis: str) -> dict:
        ref, hyp = nfc(reference), nfc(hypothesis)
        # Keep source characters attached to base units, including non-Vietnamese Unicode.
        ref_units = [(unit, char) for char in ref for unit in base(char)]
        hyp_units = [(unit, char) for char in hyp for unit in base(char)]
        rb = "".join(unit for unit, _ in ref_units)
        hb = "".join(unit for unit, _ in hyp_units)
        errors, aligned = 0, 0
        # Align base-letter strings first; count accent differences only on equal letters.
        for op in Levenshtein.opcodes(rb, hb):
            if op.tag == "equal":
                for i, j in zip(
                    range(op.src_start, op.src_end), range(op.dest_start, op.dest_end), strict=True
                ):
                    if rb[i].isalpha():
                        aligned += 1
                        errors += ref_units[i][1] != hyp_units[j][1]
        return {
            "cer": error_rate(ref, hyp),
            "wer": error_rate(ref.split(), hyp.split()),
            "exact_match": int(ref == hyp),
            "diacritic_error_rate": errors / aligned if aligned else None,
            "diacritic_errors": errors,
            "diacritic_aligned_letters": aligned,
        }


def normalize_value(kind: str, value: str) -> str:
    value = nfc(value).strip()
    if kind == "DATE":
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
            try:
                return datetime.strptime(value, fmt).date().isoformat()
            except ValueError:
                pass
        return value
    if kind in {"MONEY", "QUANTITY", "PERCENTAGE"}:
        # Vietnamese convention: dot grouping, comma decimal; preserve decimal significance.
        value = re.sub(r"[^0-9,.-]", "", value)
        if "," in value:
            value = value.replace(".", "").replace(",", ".")
        elif re.fullmatch(r"-?\d{1,3}(?:\.\d{3})+", value):
            value = value.replace(".", "")
        from decimal import Decimal, InvalidOperation

        try:
            return format(Decimal(value).normalize(), "f")
        except InvalidOperation:
            return value
    if kind == "TAX_CODE":
        return re.sub(r"[\s-]", "", value)
    return " ".join(value.casefold().split())


def critical_accuracy(fields: list[CriticalField], prediction: str) -> dict:
    """Annotation-guided transcription retention, not semantic field extraction."""
    text = nfc(prediction)
    used = Counter()
    correct = 0
    for field in fields:
        kind = field.type
        target = normalize_value(kind, field.value)
        if kind == "DATE":
            candidates = re.findall(
                r"(?<!\d)(?:\d{4}-\d{2}-\d{2}|\d{1,2}[/.-]\d{1,2}[/.-]\d{4})(?!\d)", text
            )
        elif kind in {
            "MONEY",
            "QUANTITY",
            "PERCENTAGE",
            "ARTICLE_NUMBER",
            "CLAUSE_NUMBER",
            "TAX_CODE",
        }:
            candidates = re.findall(r"(?<![\w])\d+(?:[.,-]\d+)*(?![\w])", text)
        else:
            # Whole token boundaries prevent partial contract-number/name matches.
            pattern = r"(?<!\w)" + re.escape(nfc(field.raw_text)) + r"(?!\w)"
            candidates = re.findall(pattern, text, flags=re.IGNORECASE)
            target = normalize_value(kind, field.raw_text)
        count = sum(normalize_value(kind, c) == target for c in candidates)
        key = (kind, target)
        if count > used[key]:
            correct += 1
            used[key] += 1
    return {
        "critical_field_correct": correct,
        "critical_field_total": len(fields),
        "critical_field_accuracy": correct / len(fields) if fields else None,
    }


def bbox_metrics(reference: list[BBox], prediction: list[BBox], threshold: float = 0.5) -> dict:
    """Maximum-IoU one-to-one assignment; missed reference boxes receive zero."""
    if not 0 <= threshold <= 1:
        raise ValueError("IoU threshold must be in 0..1")
    scores = np.zeros(len(reference))
    if reference and prediction:
        matrix = np.array([[r.iou(p) for p in prediction] for r in reference])
        rows, cols = linear_sum_assignment(-matrix)
        scores[rows] = matrix[rows, cols]
    return {
        "n": len(reference),
        "prediction_n": len(prediction),
        "mean_iou": float(scores.mean()) if len(scores) else None,
        "hit_rate": float((scores >= threshold).mean()) if len(scores) else None,
    }
