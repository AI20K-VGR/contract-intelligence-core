#!/usr/bin/env python3
"""partner_core.py — provider-AGNOSTIC primitives shared by every partner lane
(gemini today, a future CCS-driven lane next). Holds only what has no engine
opinion: the outcome shape (Result/Inert/Degraded), the append-only job
registry, and the two tiny helpers (transient-error match, git plumbing) any
lane's write path needs.

Deliberately excluded (stays lane-specific, see gemini_companion.py): config
resolution, transport/engine construction, prompt composition, the chokepoint
itself. Import direction is one-way — a lane imports this module; this module
never imports a lane, so gemini and a future partner lane never depend on each
other through here.
"""
import os
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_HERE = Path(__file__).resolve()
_HARNESS = _HERE.parents[3]                     # scripts→hs→plugins→harness
for _p in (_HARNESS / "scripts", _HARNESS / "hooks"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import harness_paths  # noqa: E402

try:
    from hook_runtime import resolve_actor
except Exception:  # pragma: no cover - resolve_actor is always importable in-tree
    def resolve_actor(session_id=None):
        return "user:%s" % os.environ.get("USER", "unknown")


# --- outcome types (a common .status keeps a lane's job registry uniform) ---
@dataclass
class Result:
    content: Any
    provenance: dict
    session: Optional[str] = None
    status: str = "ok"


@dataclass
class Inert:
    reason: str
    provenance: dict
    status: str = "inert"


@dataclass
class Degraded:
    provenance: dict
    reason: str
    status: str = "degraded"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_transient(err, markers) -> bool:
    msg = str(err).lower()
    return any(m in msg for m in markers)


# --- job registry (append-only JSONL, gitignored state) ---------------------
import fcntl  # noqa: E402
import json  # noqa: E402


class JobRegistry:
    """Append-only JSONL of a lane's jobs. One record per state transition; the
    latest record for a job_id is its current state. Never rewrites a line
    (code-standards §4: no read-modify-write). Lives under the project's
    `.harness/state/<subdir>/` (resolved via tool_state_dir(); gitignored,
    never committed), dir 0o700.
    `subdir` isolates
    lanes sharing this registry shape (gemini vs a future partner lane) under
    separate state trees — default "gemini" keeps the existing gemini call
    sites (`JobRegistry()`) unchanged."""

    def __init__(self, state_dir=None, subdir="gemini"):
        # tool_state_dir(): a lane companion runs via the Bash tool, whose env
        # carries no CLAUDE_PROJECT_DIR — under a global layout it resolves its
        # own project's state home from CWD rather than crashing on the
        # fail-closed marker. Guards stay fail-closed (they never call this).
        base = Path(state_dir) if state_dir else harness_paths.tool_state_dir()
        self._dir = base / subdir
        self._dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self._dir, 0o700)
        except OSError:
            pass  # best-effort on platforms without POSIX modes
        self.path = str(self._dir / "jobs.jsonl")

    def append(self, record):
        rec = dict(record)
        rec.setdefault("actor", resolve_actor())
        rec.setdefault("ts", _now_iso())
        line = json.dumps(rec, ensure_ascii=False) + "\n"
        # O_APPEND + flock: concurrent writers never interleave or clobber.
        # TODO research: flock is a no-op on Windows — a portable cross-platform
        # lock is deferred (code-standards §4).
        fd = os.open(self.path, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            # os.write may write fewer bytes than requested; loop so a large record
            # (a full diff / assembled review) is never torn into a bad JSONL line.
            buf = line.encode("utf-8")
            while buf:
                buf = buf[os.write(fd, buf):]
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
        return rec

    def read_all(self):
        """Every intact record, torn lines skipped (mirrors
        lens_partner._iter_records's fail-soft pattern). append() only ever
        writes whole lines, but a line can still land malformed on disk (a
        crash mid os.write, a hand-edited file) — one bad line must never
        take the whole read down with it."""
        try:
            with open(self.path, encoding="utf-8") as fh:
                rows = []
                for ln in fh:
                    ln = ln.strip()
                    if not ln:
                        continue
                    try:
                        rows.append(json.loads(ln))
                    except json.JSONDecodeError:
                        continue  # torn/partial line — skip, never crash
                return rows
        except FileNotFoundError:
            return []

    def latest(self, job_id):
        found = None
        for r in self.read_all():
            if r.get("job_id") == job_id:
                found = r
        return found


def _new_job_id() -> str:
    return uuid.uuid4().hex[:12]


def _git_out(root, *args) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True,
                          capture_output=True, text=True).stdout
