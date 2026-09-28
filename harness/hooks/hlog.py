#!/usr/bin/env python3
"""hlog.py — diagnostic / performance log helper (stdlib-only, fail-open).

A thin diag stream for the harness's own perf + debug signal, kept strictly SEPARATE
from the audit trace: the trace (trace_log) never rotates and is hash-chained;
hlog rotates at 8MB like telemetry (one generation, no chain) and carries no audit
weight. It writes JSONL to state/diag/diag.jsonl.

  - level DEBUG / INFO / WARN. DEBUG is dropped unless HARNESS_DEBUG is set, so verbose
    per-core detail is zero-cost by default; INFO/WARN always land.
  - fail-open: a missing dir, an unwritable path, a disk error — every failure is
    swallowed. A diag write must never break, or slow to a crawl, the op it observes.
  - stdlib ONLY: no hook_runtime, no trace_log, no loguru/structlog (the +42ms stack) —
    that budget is about the LOGGING stack, not path resolution, so this still mirrors
    hook_runtime._state_dir()'s tier order without importing it: HARNESS_STATE_DIR,
    else HARNESS_DATA_ROOT + "state" (the per-project data home under a global
    install), else next to this module (harness/state, self-host).

O_APPEND + a best-effort flock keep concurrent hook processes from interleaving a line
(~0.035ms/write, research §2.3).
"""

import json
import os
import time
from pathlib import Path

_LEVELS = {"DEBUG": 10, "INFO": 20, "WARN": 30}
_ROTATE_BYTES = 8 * 1024 * 1024  # telemetry law: rotate at 8MB, one generation
_FILENAME = "diag.jsonl"


def _state_dir() -> Path:
    """HARNESS_STATE_DIR > HARNESS_DATA_ROOT/state > module-relative (self-host).
    Mirrors hook_runtime._state_dir()'s tier order without importing harness_paths
    (or hook_runtime) — under a global install neither env is set for hlog's
    caller by default, so this closes the gap where the diag stream would
    otherwise land in the shared, read-only bin tree instead of the project."""
    raw = os.environ.get("HARNESS_STATE_DIR")
    if raw:
        return Path(raw)
    raw_data = os.environ.get("HARNESS_DATA_ROOT")
    if raw_data:
        return Path(raw_data) / "state"
    return Path(__file__).resolve().parent.parent / "state"


def _diag_path() -> Path:
    return _state_dir() / "diag" / _FILENAME


def _threshold() -> int:
    """DEBUG when HARNESS_DEBUG is set, else INFO — the verbose gate."""
    return _LEVELS["DEBUG"] if os.environ.get("HARNESS_DEBUG") else _LEVELS["INFO"]


def _rotate(p: Path) -> None:
    """At >=8MB, move the file to a single .1 generation and start fresh. Best-effort."""
    try:
        if p.exists() and p.stat().st_size >= _ROTATE_BYTES:
            os.replace(str(p), str(p) + ".1")
    except OSError:
        pass


def _append(p: Path, line: str) -> None:
    try:
        import fcntl
    except Exception:  # noqa: BLE001 — non-POSIX: append without the lock
        fcntl = None
    fh = open(p, "a", encoding="utf-8")
    try:
        if fcntl is not None:
            try:
                fcntl.flock(fh, fcntl.LOCK_EX)
            except Exception:  # noqa: BLE001 — lock unavailable, still append
                pass
        fh.write(line)
        fh.flush()
    finally:
        fh.close()


def log(level: str, event: str, **fields) -> None:
    """Append a diag record when `level` clears the active threshold. Never raises."""
    try:
        if _LEVELS.get(level, _LEVELS["INFO"]) < _threshold():
            return
        p = _diag_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        _rotate(p)
        rec = {"ts": _now_iso(), "level": level, "event": event}
        rec.update(fields)
        _append(p, json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001 — diag must never break the caller
        pass


def _now_iso() -> str:
    # gmtime-based ISO-8601 (UTC), stdlib-only — no datetime import needed for a stamp.
    return time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())


def debug(event: str, **fields) -> None:
    log("DEBUG", event, **fields)


def info(event: str, **fields) -> None:
    log("INFO", event, **fields)


def warn(event: str, **fields) -> None:
    log("WARN", event, **fields)
