from __future__ import annotations

import re
import unicodedata

from rapidfuzz.distance import Levenshtein


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return " ".join(text.casefold().split())


def _rate(reference: str | list[str], prediction: str | list[str]) -> float:
    return Levenshtein.distance(reference, prediction) / max(1, len(reference))


def evaluate_text(reference: str, prediction: str) -> dict[str, float]:
    raw_ref = unicodedata.normalize("NFC", reference)
    raw_pred = unicodedata.normalize("NFC", prediction)
    norm_ref, norm_pred = normalize_text(reference), normalize_text(prediction)
    return {
        "raw_cer": _rate(raw_ref, raw_pred),
        "normalized_cer": _rate(norm_ref, norm_pred),
        "raw_wer": _rate(re.findall(r"\S+", raw_ref), re.findall(r"\S+", raw_pred)),
        "normalized_wer": _rate(norm_ref.split(), norm_pred.split()),
    }
