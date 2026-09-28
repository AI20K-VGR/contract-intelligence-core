#!/usr/bin/env python3
"""afk_output_parser.py — parse the AFK_STATUS block from Claude stdout.

The native loop controller owns the Claude subprocess, so it reads stdout and
pulls a delimited status block the AFK system prompt asks Claude to emit:

    <<<AFK_STATUS>>>{"status":"in_progress","exit_signal":false,"files_modified":2,"note":"..."}<<<END_AFK_STATUS>>>

Contract (fail-safe): a MISSING or MALFORMED block → an empty Status with
exit_signal=False. The loop must never auto-exit on a parse miss — at worst it
runs to MAX_ITERATIONS, never exits early on garbage. When
Claude emits several blocks, the LAST one wins (it reflects the final state).
Pure: no IO.
"""

import json
import re
from dataclasses import dataclass

_BLOCK_RE = re.compile(r"<<<AFK_STATUS>>>(.*?)<<<END_AFK_STATUS>>>", re.DOTALL)


@dataclass(frozen=True)
class Status:
    found: bool = False
    status: str = ""
    exit_signal: bool = False
    files_modified: int = 0
    note: str = ""


_EMPTY = Status()


def _coerce_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "yes", "y")
    return False


def _coerce_int(v) -> int:
    try:
        return int(v)
    except (ValueError, TypeError):
        return 0


def parse(stdout) -> Status:
    """Extract the last AFK_STATUS block; empty/garbage → fail-safe empty Status."""
    if not stdout or not isinstance(stdout, str):
        return _EMPTY
    matches = _BLOCK_RE.findall(stdout)
    if not matches:
        return _EMPTY
    try:
        data = json.loads(matches[-1].strip())
    except (ValueError, TypeError):
        return _EMPTY
    if not isinstance(data, dict):
        return _EMPTY
    return Status(
        found=True,
        status=str(data.get("status") or ""),
        exit_signal=_coerce_bool(data.get("exit_signal")),
        files_modified=_coerce_int(data.get("files_modified")),
        note=str(data.get("note") or ""),
    )


def is_complete(s: Status) -> bool:
    return s.status == "complete"


def is_blocked(s: Status) -> bool:
    return s.status == "blocked"
