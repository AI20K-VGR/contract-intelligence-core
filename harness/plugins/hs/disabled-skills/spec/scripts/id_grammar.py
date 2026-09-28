#!/usr/bin/env python3
"""Parent-scoped ID grammar — the single authoritative home for hs:spec.

Every artifact under ``docs/product/`` carries a parent-scoped ID that is globally
unique by construction (lineage readable, no central allocator). This module is the
SSOT for those patterns: ``spec_graph`` imports ``ID_PATTERN_BY_TYPE`` /
``COMP_ID_PATTERN`` from here instead of re-encoding the regex, and the validate /
template / dec-ledger layers import the same home so the grammar cannot drift.

Grammar (frontmatter-and-id-spec.md):
    BRD goal   BRD-G<n>                 e.g. BRD-G1
    PRD        PRD-<SLUG>               e.g. PRD-AUTH        (<SLUG> = ^[A-Z][A-Z0-9-]{0,49}$)
    Epic       PRD-<SLUG>-E<n>          e.g. PRD-AUTH-E1
    Story      PRD-<SLUG>-E<n>-S<n>     e.g. PRD-AUTH-E1-S1
    Competitor COMP-<SLUG>              e.g. COMP-SHOPIFY
    Decision   DEC-<n>                  parent-free, globally monotonic
    Outcome    OUT-<n>                  parent-free, globally monotonic
"""

from __future__ import annotations

import re
from typing import Dict, Optional, Pattern

# Slug: uppercase ASCII letter start, then up to 49 letters/digits/hyphens (≤50 total).
# End-anchored with \Z, NOT $: Python's `$` also matches immediately before a
# single trailing newline, so `id: |` block-scalar frontmatter parsing to
# 'PRD-AUTH\n' would otherwise validate as a well-formed id, then silently fail
# every downstream dict-key / equality lookup ('PRD-AUTH\n' != 'PRD-AUTH').
SLUG_RE: Pattern = re.compile(r"^[A-Z][A-Z0-9-]{0,49}\Z")
# The bare (unanchored) slug body, reused to COMPOSE every slug-bearing pattern
# below instead of re-encoding the character class — so valid_slug() and
# is_valid_id() can never drift apart from each other. Derived by stripping
# SLUG_RE's own leading `^` and trailing `\Z` (2 chars) anchors, keeping ONE
# literal definition of the character class (the DRY guard test enforces exactly
# one re.compile-site occurrence).
_SLUG_BODY = SLUG_RE.pattern[1:-2]

# Parent-scoped ID grammar keyed by artifact type. Singletons (product/vision) carry a
# fixed id so a missing/typo'd one is caught. Consumed by spec_graph, check_consistency
# and generate_templates — the one home so the checkers cannot drift. Every pattern
# END-anchors with \Z (see SLUG_RE above) so a trailing-newline id never validates.
ID_PATTERN_BY_TYPE: Dict[str, Pattern] = {
    "product": re.compile(r"^PRODUCT\Z"),
    "vision": re.compile(r"^VISION\Z"),
    "goal": re.compile(r"^BRD-G[0-9]+\Z"),
    "prd": re.compile(r"^PRD-%s\Z" % _SLUG_BODY),
    "epic": re.compile(r"^PRD-%s-E[0-9]+\Z" % _SLUG_BODY),
    "story": re.compile(r"^PRD-%s-E[0-9]+-S[0-9]+\Z" % _SLUG_BODY),
}

# Competitor ID grammar: COMP-<SLUG> (same parent-scoped discipline).
COMP_ID_PATTERN: Pattern = re.compile(r"^COMP-%s\Z" % _SLUG_BODY)

# Parent-free, globally monotonic ledgers (max+1 allocation, never reused).
DEC_ID_PATTERN: Pattern = re.compile(r"^DEC-[0-9]+\Z")
OUT_ID_PATTERN: Pattern = re.compile(r"^OUT-[0-9]+\Z")

# Most-specific-first so id_type infers the narrowest matching kind: the prd pattern
# also matches epic/story ids (its slug class spans hyphens), so story and epic must
# be tested before prd.
_INFER_ORDER = ("story", "epic", "prd", "goal", "product", "vision")


def valid_slug(slug: str) -> bool:
    """True iff ``slug`` matches the ≤50-char uppercase slug rule."""
    return isinstance(slug, str) and SLUG_RE.match(slug) is not None


def is_valid_id(node_id: str, node_type: str) -> bool:
    """True iff ``node_id`` matches the grammar for its declared ``node_type``."""
    pattern = ID_PATTERN_BY_TYPE.get(node_type)
    return bool(pattern and isinstance(node_id, str) and pattern.match(node_id))


def id_type(node_id: str) -> Optional[str]:
    """Infer the artifact type from an ID, or None when it matches no grammar."""
    if not isinstance(node_id, str):
        return None
    for kind in _INFER_ORDER:
        if ID_PATTERN_BY_TYPE[kind].match(node_id):
            return kind
    return None


def normalize_serves(value: object) -> "tuple[list, list]":
    """Split a raw ``serves`` frontmatter value into ``(valid_ids, invalid)``.

    The ONE shared reading of the ``serves`` field so the PO gate
    (``strict_gate``), the BA resolver (``serves_resolver``) and the roadmap
    rollup cannot disagree about what a malformed ``serves`` means:

    - an ABSENT ``serves`` (``None``) is a no-op → ``([], [])``;
    - any non-list value (a bare string ``serves: STORY-1``, a mapping) is
      wholly malformed → ``([], ["<repr>"])`` — it can never resolve to a story;
    - inside a list, every string entry is a candidate id; every non-string
      entry (an int, or a YAML-auto-resolved ``datetime.date`` from
      ``serves: [2026-07-13]``) is invalid.

    Invalid entries are returned ``str``-coerced so a caller can json.dumps the
    result without a "date is not JSON serializable" crash.
    """
    if value is None:
        return [], []
    if not isinstance(value, list):
        return [], [str(value)]
    valid, invalid = [], []
    for entry in value:
        if isinstance(entry, str):
            valid.append(entry)
        else:
            invalid.append(str(entry))
    return valid, invalid


def as_str_list(value: object) -> "list":
    """Coerce any raw frontmatter value into a list of strings — the canonical
    reader for a list-ish field (``depends_on``, ``acceptance``, ...) that a hand
    edit may have left as a bare scalar. ``None`` -> ``[]``; a list -> its entries
    ``str``-coerced (so a YAML-auto ``datetime.date`` is join-safe); any other
    scalar (a bare ``depends_on: MS-2``) -> ``[str(value)]`` (one element,
    recovering the likely intent) rather than char-splitting a string or raising
    on a non-iterable. This is the ONE shared coercer so a new list-ish reader
    cannot re-introduce the char-split / TypeError class per field."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]
