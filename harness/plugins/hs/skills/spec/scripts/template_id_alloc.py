"""
template_id_alloc — parent-scoped ID allocation for generate_templates.

Owns the `allocate_id` function and the ID-grammar constants derived from
id_grammar (the SSOT). Kept in a separate module so the allocation logic can
be tested and reasoned about independently from template rendering and file
I/O.
"""

import re
from typing import Any, Dict, List, Optional

from id_grammar import ID_PATTERN_BY_TYPE


# Strict parent-ID patterns — derived from spec_graph.ID_PATTERN_BY_TYPE (the
# single authoritative home) so a parent passed at generate time fast-fails the
# same way it would be flagged at validate time.
PARENT_PATTERN_FOR_PRD = ID_PATTERN_BY_TYPE["prd"]   # PRD-<SLUG>, slug ≤50 chars
PARENT_PATTERN_FOR_EPIC = ID_PATTERN_BY_TYPE["epic"]  # PRD-<SLUG>-E<n>

# A trailing -E<n> or -E<n>-S<n> means the ID is an epic or story shape — reject
# when a PRD ID is expected so callers can't accidentally pass an epic/story.
# End-anchored with \Z (not $) to match id_grammar's SSOT: `$` also matches
# before a final newline, so a trailing-newline slug/id would slip.
PRD_PARENT_LOOKS_LIKE_EPIC_OR_STORY = re.compile(r"-E\d+(-S\d+)?\Z")

# Bare PRD slug fast-fail (uppercase ASCII letter start, digits/hyphens, ≤50 chars).
SLUG_PATTERN_FOR_PRD = re.compile(r"^[A-Z][A-Z0-9-]{0,49}\Z")

# Caller-supplied `--id` override patterns — keyed from spec_graph.ID_PATTERN_BY_TYPE
# so an --auto batch caller that pre-allocates IDs cannot smuggle an invalid one
# past the generator.
ID_PATTERN_OVERRIDE: Dict[str, re.Pattern] = {
    # product/vision now live in the canonical ID_PATTERN_BY_TYPE (spread above); only the
    # types absent from it are added here.
    **ID_PATTERN_BY_TYPE,
    "brd": re.compile(r"^BRD\Z"),
    "exec_summary": re.compile(r"^EXEC-SUMMARY\Z"),
    "sign_off": re.compile(r".+"),
    "change_log_entry": re.compile(r".+"),
}


def reject_prd_collision(normalised_slug: str, source: str) -> None:
    """Raise ValueError when `normalised_slug` (an upper-cased PRD slug --
    either a bare `--slug` or the `PRD-<slug>` id's tail) ends in an
    epic/story suffix (-E<n> or -E<n>-S<n>), which collides with the
    epic/story ID grammar under PRD-<slug>.

    The single home for this check: allocate_id()'s slug path calls it below,
    and generate_templates._run()'s `--id` override path calls it too, so a
    caller-supplied `--id PRD-AUTH-E9` is rejected the exact same way a
    `--slug AUTH-E9` mint would be — no separate copy of the grammar to drift.
    """
    m = PRD_PARENT_LOOKS_LIKE_EPIC_OR_STORY.search(normalised_slug)
    if m:
        # Name the actual matched suffix (`m.group()`, e.g. "-E9" or "-E9-S1"),
        # not `normalised_slug.split('-E', 1)[-1]` — that split drops the "-E"
        # itself, so "AUTH-E9" reported the misleading "-'9'" instead of "-E9".
        raise ValueError(
            f"{source} produces an ID (PRD-{normalised_slug}) that collides "
            f"with the epic/story ID grammar (suffix {m.group()!r} "
            f"matches -E<n> or -E<n>-S<n>). Use a slug/id without a trailing -E<n> sequence."
        )


def allocate_id(graph: Dict[str, Any], target_type: str,
                slug: Optional[str], parent: Optional[str],
                session_used: List[str]) -> str:
    """Allocate the next parent-scoped ID for `target_type`.

    `session_used` lists IDs already handed out this session so siblings under
    the same parent don't collide (the CLI passes [] for a single-invocation
    call; batch callers accumulate the list).
    """
    existing_ids = {n["id"] for n in graph["nodes"]} | set(session_used)
    if target_type == "goal":
        return _next_with_prefix(existing_ids, "BRD-G")
    if target_type == "prd":
        if not slug:
            raise ValueError("--slug is required for type=prd")
        normalised = slug.upper()
        if not SLUG_PATTERN_FOR_PRD.match(normalised):
            raise ValueError(
                f"--slug must be uppercase ASCII (A-Z, 0-9, hyphen), start with "
                f"a letter, and be ≤50 chars (matches {SLUG_PATTERN_FOR_PRD.pattern}); "
                f"got {slug!r}"
            )
        # A slug like AUTH-E1 mints PRD-AUTH-E1, which collides with the epic-1
        # ID grammar under PRD-AUTH.
        reject_prd_collision(normalised, f"--slug {slug!r}")
        return f"PRD-{normalised}"
    if target_type == "epic":
        if (
            not parent
            or not PARENT_PATTERN_FOR_PRD.match(parent)
            or PRD_PARENT_LOOKS_LIKE_EPIC_OR_STORY.search(parent)
        ):
            raise ValueError(
                f"--parent must be a valid PRD ID for type=epic "
                f"(PRD-<SLUG>, slug ≤50 chars, no -E<n>/-S<n> suffix); got {parent!r}"
            )
        return _next_with_prefix(existing_ids, f"{parent}-E")
    if target_type == "story":
        if not parent or not PARENT_PATTERN_FOR_EPIC.match(parent):
            raise ValueError(
                f"--parent must be a valid epic ID for type=story "
                f"(pattern {PARENT_PATTERN_FOR_EPIC.pattern}); got {parent!r}"
            )
        return _next_with_prefix(existing_ids, f"{parent}-S")
    if target_type == "product":
        return "PRODUCT"
    if target_type == "vision":
        return "VISION"
    if target_type == "brd":
        return "BRD"
    if target_type == "exec_summary":
        return "EXEC-SUMMARY"
    return ""


def _next_with_prefix(existing: set, prefix: str) -> str:
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)\Z")
    used = []
    for x in existing:
        m = pattern.match(x or "")
        if m:
            used.append(int(m.group(1)))
    n = (max(used) + 1) if used else 1
    return f"{prefix}{n}"
