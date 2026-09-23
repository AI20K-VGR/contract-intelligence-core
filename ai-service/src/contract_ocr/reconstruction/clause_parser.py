"""Clause / numbering marker parsing.

Pure string -> `ClauseMarker | None` parsing, with no knowledge of pages,
blocks or hierarchy. `hierarchy_builder` uses `TIER` to place a parsed
marker in the clause tree.

Supported forms (section 8 of the reconstruction spec):
    Điều 1 / ĐIỀU 12 / Article 1 / ARTICLE 10 / Section 3   -> "section"
    Khoản 2                                                  -> "khoan_label"
    1. / 1.1 / 1.1.1 / 12.3.4                                -> "decimal"
    (a) (b) (c)                                              -> "alpha_paren"
    (i) (ii) (iii) (iv)                                      -> "roman_paren"
    1) 2)                                                     -> "number_paren"
    a) b)                                                     -> "alpha_close_paren"
"""

from __future__ import annotations

import re

from .models import ClauseMarker

SECTION = "section"
KHOAN_LABEL = "khoan_label"
DECIMAL = "decimal"
ALPHA_PAREN = "alpha_paren"
ROMAN_PAREN = "roman_paren"
NUMBER_PAREN = "number_paren"
ALPHA_CLOSE_PAREN = "alpha_close_paren"

# Tier 0 = numeric family, own level_hint is an absolute depth.
# Tier 1 = letter family (alpha and "1)"-style peers).
# Tier 2 = roman family, nests under the nearest open letter-family node.
TIER: dict[str, int] = {
    SECTION: 0,
    KHOAN_LABEL: 0,
    DECIMAL: 0,
    ALPHA_PAREN: 1,
    NUMBER_PAREN: 1,
    ALPHA_CLOSE_PAREN: 1,
    ROMAN_PAREN: 2,
}

_SECTION_RE = re.compile(
    r"^(?:Điều|ĐIỀU|Article|ARTICLE|Section|SECTION)\s+(\d+)\b", re.UNICODE
)
_KHOAN_RE = re.compile(r"^(?:Khoản|KHOẢN)\s+(\d+)\b", re.UNICODE)
# Multi-segment ("5.1", "12.3.4") is unambiguous on its own. A bare single
# integer ("1", "30") is NOT treated as a marker unless immediately followed
# by a literal "." — otherwise an ordinary quantity in a sentence ("30 ngay
# ke tu...") would be misread as a level-1 clause marker.
_DECIMAL_RE = re.compile(r"^(\d+(?:\.\d+)+)(?=[\s.]|$)|^(\d+)\.(?=\s|$)")
_ALPHA_OR_ROMAN_PAREN_RE = re.compile(r"^\(([A-Za-z]+)\)(?=[\s.,;:)]|$)")
_NUMBER_CLOSE_PAREN_RE = re.compile(r"^(\d+)\)(?=\s|$)")
_ALPHA_CLOSE_PAREN_RE = re.compile(r"^([A-Za-z])\)(?=\s|$)")

# Single letters that are far more commonly seen as roman numerals (i, v, x)
# than as the 9th/22nd/24th item of an alpha list; see README limitations.
_ROMAN_SINGLE_LETTERS = frozenset({"i", "v", "x"})
_ROMAN_TOKEN_RE = re.compile(r"^x{0,3}(ix|iv|v?i{0,3})$")


def _is_roman_token(token: str) -> bool:
    lowered = token.lower()
    if not lowered:
        return False
    if len(lowered) == 1:
        return lowered in _ROMAN_SINGLE_LETTERS
    return bool(_ROMAN_TOKEN_RE.fullmatch(lowered))


def parse_marker(text: str) -> ClauseMarker | None:
    """Parse the leading numbering marker of a block's text, if any."""
    stripped = text.strip()
    if not stripped:
        return None

    if match := _SECTION_RE.match(stripped):
        number = match.group(1)
        return ClauseMarker(
            raw=match.group(0), normalized=number, level_hint=1, marker_type=SECTION
        )

    if match := _KHOAN_RE.match(stripped):
        number = match.group(1)
        return ClauseMarker(
            raw=match.group(0), normalized=number, level_hint=2, marker_type=KHOAN_LABEL
        )

    if match := _ALPHA_OR_ROMAN_PAREN_RE.match(stripped):
        token = match.group(1)
        if len(token) == 1 and token.lower() not in _ROMAN_SINGLE_LETTERS:
            return ClauseMarker(
                raw=match.group(0),
                normalized=token.lower(),
                level_hint=None,
                marker_type=ALPHA_PAREN,
            )
        if _is_roman_token(token):
            return ClauseMarker(
                raw=match.group(0),
                normalized=token.lower(),
                level_hint=None,
                marker_type=ROMAN_PAREN,
            )
        return ClauseMarker(
            raw=match.group(0), normalized=token.lower(), level_hint=None, marker_type=ALPHA_PAREN
        )

    if match := _DECIMAL_RE.match(stripped):
        normalized = match.group(1) or match.group(2)
        level_hint = normalized.count(".") + 1
        return ClauseMarker(
            raw=match.group(0), normalized=normalized, level_hint=level_hint, marker_type=DECIMAL
        )

    if match := _NUMBER_CLOSE_PAREN_RE.match(stripped):
        return ClauseMarker(
            raw=match.group(0),
            normalized=match.group(1),
            level_hint=None,
            marker_type=NUMBER_PAREN,
        )

    if match := _ALPHA_CLOSE_PAREN_RE.match(stripped):
        return ClauseMarker(
            raw=match.group(0),
            normalized=match.group(1).lower(),
            level_hint=None,
            marker_type=ALPHA_CLOSE_PAREN,
        )

    return None
