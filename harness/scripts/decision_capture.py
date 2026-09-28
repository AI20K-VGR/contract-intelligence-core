#!/usr/bin/env python3
"""
decision_capture — deterministic "a decision was made but not recorded" detector.

SCRIPT-only, pure judgment: given the working-tree change set, it flags when a
session produced a *decision-shaped* change — a NEW hook/script/rule/agent/skill
module, or an edit to a gate-config file — without a matching record in the
decision ledger (docs/decisions.md) or a plan Validation Log (plans/**/plan.md).

This is the A-leg of memory-v2: a coarse, deterministic safety net. It makes NO
LLM judgment and never decides WHAT to record — that is the C-leg (the /hs:remember
skill). It only answers "you shipped a decision-shaped change and the ledger
didn't move — did you mean to?". By design it is sharp on the high-signal case
(a NEW module / a gate-config posture change) and silent on routine edits, so the
nudge stays useful instead of crying wolf on every commit.

Signal (or None):
    {"type": "unrecorded_decision", "subjects": [<paths>], "total": <int>}

Deterministic: same change set → same signal (subjects sorted + de-duped). The git
read is isolated in `_porcelain_changes`; the judgment is the pure `assess`,
unit-tested without a repo. ALWAYS degrades to None (never raises) outside a git
work tree — advisory is not an error.

CLI:
    decision_capture.py --root <project-dir>     # emit {signal: {...}|null}, exit 0
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

SIGNAL_TYPE = "unrecorded_decision"

# An edit to one of these gate-config files is itself a posture decision — at ANY
# status (a human flipping stage-policy / ownership / the guard list is a decision
# worth a ledger line). Matched on basename.
_GATE_CONFIGS = frozenset({
    "stage-policy.yaml", "ownership.yaml", "write-guard.yaml",
    "harness-hooks.yaml", "hooks-registration.yaml",
})

# A NEW file under one of these (prefix, suffix) trees is a new module — the
# high-signal case. A new skill is its SKILL.md appearing anywhere under a
# `/skills/` tree (handled separately).
_NEW_MODULE_RULES: Tuple[Tuple[str, str], ...] = (
    ("harness/hooks/", ".py"),
    ("harness/scripts/", ".py"),
    ("harness/rules/", ".md"),
    ("harness/plugins/hs/agents/", ".md"),
)

# Porcelain status codes that mean "this file is NEW in the working tree".
_NEW_STATUSES = frozenset({"A", "??"})

# Cap on individually-named subjects in the signal before the tail collapses to a
# count (`total`). Keeps the downstream one-line advisory readable.
_SUBJECT_CAP = 8


# ----------------------------------------------------------------------------
# Pure judgment
# ----------------------------------------------------------------------------

def _basename(posix: str) -> str:
    return posix.rsplit("/", 1)[-1]


def _is_new_module(status: str, posix: str) -> bool:
    """True when `posix` is a NEW module file (a new hook/script/rule/agent, or a
    new skill's SKILL.md). Only NEW counts — editing an existing module is routine,
    not a decision."""
    if status not in _NEW_STATUSES:
        return False
    if posix.endswith("/SKILL.md") and "/skills/" in posix:
        return True
    return any(posix.startswith(pre) and posix.endswith(suf)
               for pre, suf in _NEW_MODULE_RULES)


def _is_gate_config(posix: str) -> bool:
    """True when `posix` is one of the gate-config files (any status)."""
    return _basename(posix) in _GATE_CONFIGS


def _is_record(posix: str) -> bool:
    """True when `posix` is a decision-recording surface: the ledger itself, or a
    plan's Validation Log (where DECs are drafted before the register exists)."""
    if posix == "docs/decisions.md":
        return True
    return posix.startswith("plans/") and posix.endswith("/plan.md")


def assess(changes: Iterable[Tuple[str, str]]) -> Optional[Dict[str, Any]]:
    """Judge a change set. `changes` is an iterable of (status, path) pairs; status
    is a porcelain code ('A'/'M'/'D'/'R'/'??'...). Returns the signal dict when a
    decision-shaped change shipped without any recording surface moving, else None.

    Pure + deterministic: subjects are sorted + de-duped; same input → same output."""
    subjects: List[str] = []
    recorded = False
    for status, raw in changes:
        posix = (raw or "").replace("\\", "/").strip()
        if not posix:
            continue
        if _is_record(posix):
            recorded = True
        if _is_new_module(status, posix) or _is_gate_config(posix):
            subjects.append(posix)
    if not subjects or recorded:
        return None
    uniq = sorted(set(subjects))
    return {"type": SIGNAL_TYPE, "subjects": uniq[:_SUBJECT_CAP], "total": len(uniq)}


# ----------------------------------------------------------------------------
# Git read (isolated, degrades to [] outside a work tree)
# ----------------------------------------------------------------------------

def _status_code(xy: str) -> str:
    """Collapse the 2-char porcelain XY field to one representative code. Untracked
    ('??') wins; otherwise the strongest of A/M/D/R/C present in either column, so a
    staged-new 'A ' / 'AM' both read as 'A' (new)."""
    s = xy.strip()
    if "?" in s:
        return "??"
    for c in ("A", "M", "D", "R", "C"):
        if c in s:
            return c
    return s[:1] or " "


def _porcelain_changes(root: Path) -> List[Tuple[str, str]]:
    """(status, repo-relative POSIX path) for every changed file per
    `git status --porcelain -z -uall`. NUL-delimited so paths with spaces/newlines
    parse unambiguously; a rename/copy record carries `dest\\x00orig` — both halves
    surface as touches. Returns [] (degrades, never raises) when `root` is not a git
    work tree.

    NOTE: this keeps the status code, which check_fence._porcelain_paths deliberately
    drops — the new-vs-modified distinction is this detector's whole signal, so the
    read lives here rather than reusing that helper."""
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain", "-z", "-uall"],
            cwd=str(root), capture_output=True, text=True, timeout=30,
        )
    except (OSError, FileNotFoundError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0:
        return []

    out: List[Tuple[str, str]] = []
    fields = proc.stdout.split("\x00")
    i = 0
    while i < len(fields):
        rec = fields[i]
        if not rec:
            i += 1
            continue
        xy = rec[:2]
        path = rec[3:]
        code = _status_code(xy)
        out.append((code, path))
        # a rename/copy record is followed by its original path in the next field
        if xy and xy[0] in ("R", "C"):
            i += 1
            if i < len(fields) and fields[i]:
                out.append((code, fields[i]))
        i += 1
    return out


def collect(root) -> Optional[Dict[str, Any]]:
    """Assess the working tree at `root`. Returns the signal dict or None."""
    return assess(_porcelain_changes(Path(root)))


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    args = ap.parse_args(argv)
    try:
        signal = collect(Path(args.root).resolve())
    except Exception:  # noqa: BLE001 — advisory contract: never crash
        signal = None
    print(json.dumps({"signal": signal}, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
