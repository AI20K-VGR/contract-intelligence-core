#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""advise_relay.py — the testable seam for the hs:advise relay mechanism.

A Claude Code subagent cannot call AskUserQuestion, so the advisor agent persists its working
state to a JSON file, emits a NEEDS_USER_INPUT marker carrying ONE question in the
AskUserQuestion schema, and ends its turn. The main orchestrator asks that question, then
re-spawns the advisor with the answer; the fresh advisor reads the state and resumes.

This module owns the deterministic, unit-testable half: atomic state I/O (machine-written
state is JSON, code-standards §3), the marker emit/parse, and the one-question schema check.
Pure stdlib — importable by file path with no cross-tree dependency.
"""
import json
import os
import re

MARKER = "NEEDS_USER_INPUT"
_HEADER_MAX = 12


def read_state(path) -> dict:
    """Return the parsed relay state, or {} when the file is absent/unreadable (fresh run)."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, ValueError, OSError):
        return {}


def write_state(path, state) -> None:
    """Atomically persist `state` as JSON: write a .tmp sibling, then os.replace so a re-spawned
    advisor never reads a half-written state file."""
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    tmp = "%s.tmp" % path
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, path)


def validate_question(q) -> tuple:
    """Validate a single AskUserQuestion-shaped question. Returns (ok, reason).

    Enforces exactly the shape the orchestrator will pass verbatim to AskUserQuestion:
    a question string, a header <= 12 chars, a bool multiSelect, and 2-4 options each with a
    label. (The HARD-GATE-ONE-QUESTION rule lives in the skill; here we bound the schema.)"""
    if not isinstance(q, dict):
        return False, "not a dict"
    if not isinstance(q.get("question"), str) or not q["question"].strip():
        return False, "missing question text"
    header = q.get("header")
    if not isinstance(header, str) or not header.strip():
        return False, "missing header"
    if len(header) > _HEADER_MAX:
        return False, "header exceeds %d chars" % _HEADER_MAX
    if not isinstance(q.get("multiSelect"), bool):
        return False, "multiSelect must be a bool"
    options = q.get("options")
    if not isinstance(options, list) or not (2 <= len(options) <= 4):
        return False, "options must be a list of 2-4 entries"
    for opt in options:
        if not isinstance(opt, dict) or not str(opt.get("label", "")).strip():
            return False, "each option needs a label"
    return True, ""


def emit_needs_input(question) -> str:
    """Return the advisor's relay message: the marker on its own line, then one fenced json
    block holding the question. Raises ValueError if the question is out of schema — a courier
    must never emit a malformed question the orchestrator would pass on blindly."""
    ok, reason = validate_question(question)
    if not ok:
        raise ValueError("invalid relay question: %s" % reason)
    block = json.dumps(question, ensure_ascii=False, indent=2)
    return "%s\n```json\n%s\n```" % (MARKER, block)


def parse_needs_input(text) -> dict:
    """Extract the question dict from a NEEDS_USER_INPUT relay message. Returns {} when the text
    is not a relay message or carries no parseable json block."""
    idx = text.find(MARKER)
    if idx == -1:
        return {}
    # Anchor on the marker: parse the FIRST json block that follows it, so an
    # auxiliary ```json block earlier in the reply doesn't get picked instead.
    m = re.search(r"```json\s*(\{.*?\})\s*```", text[idx:], re.DOTALL)
    if not m:
        return {}
    try:
        data = json.loads(m.group(1))
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}
