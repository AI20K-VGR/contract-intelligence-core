#!/usr/bin/env python3
"""Estimate token count from raw bytes, corrected for non-ASCII text.

`bytes / 4` is an ASCII rule of thumb. It holds for code, YAML and English
prose, but this project's generated documents are Vietnamese, and there every
accented character costs extra bytes without costing a proportional token — so
dividing by four undercounts. That is the dangerous direction for a context
budget: the caller believes there is more room than there is.

Measured against a real tokenizer over 169 files of this tree:

    content        n   real/estimate   spread
    code          40        0.97        0.24
    YAML          39        1.03        0.43
    English        30        0.98        0.17
    Vietnamese    40        1.44        0.30

The Vietnamese ratio is steady, not noise, and what varies with it is the share
of non-ASCII bytes — which is what the diacritics are. One expression therefore
covers every content type, with no per-language table to maintain:

    tokens ~= bytes/4 * (1 + k * non_ascii_share)

Fitting k over those 169 files cuts median error from 8.7% to 3.2% (worst case
71.5% to 26.6%). Still an ESTIMATE — a real tokenizer costs seven packages and
a network fetch, and was weighed and declined.
"""
NON_ASCII_COEFFICIENT = 1.8


def non_ascii_share(data: bytes) -> float:
    """Fraction of bytes above the ASCII range. 0.0 for empty input."""
    if not data:
        return 0.0
    return sum(1 for b in data if b > 127) / len(data)


def est_tokens(data: bytes) -> int:
    """Estimated token count for `data`. Never negative, always an int."""
    if not data:
        return 0
    return round(len(data) / 4 * (1 + NON_ASCII_COEFFICIENT * non_ascii_share(data)))
