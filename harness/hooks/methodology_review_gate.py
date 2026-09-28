#!/usr/bin/env python3
"""methodology_review_gate.py — self-governance nudge on methodology edits.

PostToolUse:Write|Edit|MultiEdit nudge (class `nudge`). The harness's other
gates (code-review, verification, plan-approval) force an ARTIFACT to anchor
its claims in evidence, but none of them run when someone edits the
methodology ITSELF — `harness/rules/**`, a skill markdown, or a schema. Left
unguarded, methodology can drift into a plausible-sounding rule or skill that
doesn't earn its keep — the same confabulation shape the rest of the system
polices elsewhere.

This hook does ONLY light structural detection: does the write touch a
methodology path, and does it look HIGH-impact (a brand-new skill/rule file,
or a schema/axis edit) vs trivial (a wording edit on a file that already
exists)? The full 6-signal review protocol (UNANCHORED_HIGH, PHANTOM_EVIDENCE,
DUPLICATE_CONTENT, COORDINATE_LEAK, HEDGING_DENSITY, STUB_AVOIDANCE) is
checklist PROSE a human/LLM applies, carried in
`harness/rules/methodology-review.md` — this hook never runs that protocol
itself and never imports the grid confab-detector. Self-governance must not
brick methodology maintenance, so posture is nudge/fail-open: it advises,
never blocks.
"""

import os
import sys
from pathlib import Path

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:
    sys.path.append(_HOOKS_DIR)
import hook_runtime  # noqa: E402

HOOK_CLASS = "nudge"
_NAME = Path(__file__).stem

_RULE_DOC = "harness/rules/methodology-review.md"
_WRITE_TOOLS = frozenset({"Write", "Edit", "MultiEdit"})


def _methodology_rel(file_path):
    """The harness-relative posix path when `file_path` sits under a
    methodology tree, else None. Works for a repo-relative path (test inputs)
    or an absolute one (a real tool_input.file_path) by locating the last
    `harness/` path segment — pure string matching, no disk access."""
    posix = file_path.replace("\\", "/")
    idx = posix.rfind("/harness/")
    if idx != -1:
        posix = posix[idx + 1:]
    if not posix.startswith("harness/"):
        return None
    return posix


def _is_schema(rel):
    return rel.startswith("harness/schemas/") and rel.endswith(".json")


def _is_methodology_target(rel):
    if rel.startswith("harness/rules/"):
        return True
    if rel.startswith("harness/plugins/hs/skills/") and rel.endswith(".md"):
        return True
    if _is_schema(rel):
        return True
    return False


def core(data):
    """Return an advisory for a methodology-path Write/Edit, else None.

    HIGH-impact (port of the FrankCode trigger-list): a brand-new file
    (tool=Write) or a schema/axis edit — either way the message routes to the
    full review protocol. Trivial: an Edit/MultiEdit on a methodology file
    that already exists and isn't a schema — a lighter nudge, since most such
    edits are wording/typo fixes (the rubber-stamp path in the rule doc).
    Non-methodology paths and malformed payloads return None (silent).
    """
    if not isinstance(data, dict):
        return None
    tool_name = data.get("tool_name")
    if tool_name not in _WRITE_TOOLS:
        return None
    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str) or not file_path.strip():
        return None

    rel = _methodology_rel(file_path)
    if rel is None or not _is_methodology_target(rel):
        return None

    if tool_name == "Write" or _is_schema(rel):
        return (
            "HIGH-impact methodology edit (%s) — run the 6-signal review "
            "protocol in %s before this merges." % (rel, _RULE_DOC)
        )
    return (
        "trivial-looking methodology edit (%s) — confirm no HIGH-impact "
        "trigger applies (new skill/rule, schema/axis change, skill retire); "
        "see %s." % (rel, _RULE_DOC)
    )


def main():
    # No entry in nudge-channels.yaml (owned outside this phase) — the
    # code-level default routes to BOTH axes: the agent editing methodology
    # is exactly who should see this, and the human reviewing the diff too.
    hook_runtime.run_nudge_hook(_NAME, core, default_channel="systemMessage")
    return 0


if __name__ == "__main__":
    sys.exit(main())
