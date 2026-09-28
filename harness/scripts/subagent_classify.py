#!/usr/bin/env python3
"""subagent_classify.py — shared outcome classification for subagent telemetry.

Pure, dependency-free classification of a finished subagent's outcome from its
transcript tail or a raw terminal-message string. Two consumers share this:
  - track_subagent_outcome.py (SubagentStop hook) — best-effort at stop time.
  - lens_subagent_outcomes.py (read-time lens) — deferred re-classification of
    records the hook could only mark `unknown` (the subagent transcript's
    terminal record is typically not flushed yet when SubagentStop fires; by
    lens-render time it is, so the authoritative stop_reason is available).

outcome ∈ {success, api_error, timeout, blocked, unknown}. NEVER fabricates
`success`: a clean stop with no pending tool_use is success; a terminal error
text maps to its taxonomy label; anything else is the honest `unknown`.
"""

import json
import re
from pathlib import Path

OUTCOMES = {"success", "api_error", "timeout", "blocked", "unknown"}
UNKNOWN = {"unknown", "", None}

# Error taxonomy — first pattern that matches the terminal error text wins.
_TAXONOMY = [
    ("api_error", re.compile(r"rate.?limit|overloaded|api error|status 5\d\d|\b429\b|\b529\b|connection error|ECONNRESET", re.I)),
    ("timeout",   re.compile(r"timed?\s?out|timeout|deadline exceeded", re.I)),
    ("blocked",   re.compile(r"permission denied|not allowed|blocked by|refused|forbidden", re.I)),
]

TAIL_BYTES = 64 * 1024


def classify_text(text: str) -> str:
    """Map a raw terminal-message string to an error label, else `unknown`.

    Race-free: callable on a payload's `last_assistant_message` without touching
    the (possibly-unflushed) transcript file. Only ever returns an ERROR label or
    `unknown` — a clean string is NOT asserted to be success here (that needs the
    transcript's stop_reason; see classify_from_transcript).
    """
    if not text:
        return "unknown"
    for label, pat in _TAXONOMY:
        if pat.search(text):
            return label
    return "unknown"


def _read_tail_records(path: str) -> list:
    try:
        with open(path, "rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - TAIL_BYTES))
            text = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    recs = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict):  # a parseable non-object line is not a record
            recs.append(obj)
    return recs


def _error_text(rec: dict) -> str:
    """Best-effort terminal-error text from a transcript record."""
    chunks = []
    msg = rec.get("message") if isinstance(rec, dict) else None
    if isinstance(msg, dict):
        content = msg.get("content")
        if isinstance(content, str):
            chunks.append(content)
        elif isinstance(content, list):
            for b in content:
                if isinstance(b, dict):
                    chunks.append(str(b.get("text") or b.get("content") or ""))
        if msg.get("error"):
            chunks.append(str(msg.get("error")))
    if isinstance(rec, dict) and rec.get("error"):
        chunks.append(str(rec.get("error")))
    return " ".join(c for c in chunks if c)


def classify_from_transcript(path) -> str:
    """Classify the outcome from a subagent transcript's tail. `unknown` when the
    file is absent/unreadable/empty or the terminal record is not yet flushed."""
    if not path:
        return "unknown"
    recs = _read_tail_records(str(path))
    if not recs:
        return "unknown"
    last = recs[-1]
    msg = last.get("message", {}) if isinstance(last.get("message"), dict) else {}
    # Clean stop with no pending tool_use → success.
    if msg.get("stop_reason") in ("end_turn", "stop_sequence"):
        content = msg.get("content") or []
        if not any(isinstance(c, dict) and c.get("type") == "tool_use" for c in content):
            return "success"
    return classify_text(_error_text(last))


def agent_type_from_filename(transcript_path) -> str:
    """agent-<type>-<id>.jsonl → keep leading pure-alpha tokens as the type."""
    try:
        stem = Path(str(transcript_path)).stem
    except Exception:
        return "unknown"
    parts = stem.split("-")
    if parts and parts[0] == "agent":
        parts = parts[1:]
    type_parts = []
    for p in parts:
        if any(ch.isdigit() for ch in p):  # id-like segment → stop
            break
        type_parts.append(p)
    return "-".join(type_parts) or "unknown"
