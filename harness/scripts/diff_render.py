#!/usr/bin/env python3
"""diff_render — shared unified-diff renderer for `--check` drift gates.

Every gate that rebuilds a file in memory and compares it to the committed
copy used to report a bare boolean ("drift: X is out of date") — the reader
had to re-run the generator and diff by hand to see WHAT changed. One helper,
imported the same way sibling scripts import fs_guard/encoding_utils.

Capped: an uncapped diff on a near-total rewrite is a gate CI mutes. A cut is
always announced on its own trailer line — never silent (a silently-cut diff
reads as "nothing else changed").
"""
import difflib

# Matches this repo's own report-readability convention (QA report / review
# body ≤200 lines) — a diff beyond this is effectively "the file changed
# entirely," at which point re-rendering locally beats reading the hunk.
DEFAULT_MAX_LINES = 200


def render_check_diff(expected_text: str, actual_text: str, path: str,
                       *, max_lines: int = DEFAULT_MAX_LINES) -> str:
    """Unified diff of `actual_text` (committed) -> `expected_text` (freshly
    rebuilt), labelled with `path`. Empty when identical — callers print
    nothing on a clean gate, so a non-drifted run stays byte-identical."""
    diff_lines = list(difflib.unified_diff(
        actual_text.splitlines(keepends=True),
        expected_text.splitlines(keepends=True),
        fromfile="%s (committed)" % path,
        tofile="%s (rebuilt)" % path,
    ))
    if not diff_lines:
        return ""
    if len(diff_lines) <= max_lines:
        return "".join(diff_lines)

    shown = "".join(diff_lines[:max_lines])
    if not shown.endswith("\n"):
        shown += "\n"
    omitted = len(diff_lines) - max_lines
    return shown + (
        "... diff truncated: %d of %d lines shown (%d more omitted) — "
        "re-render locally for the full diff\n" % (max_lines, len(diff_lines), omitted)
    )
