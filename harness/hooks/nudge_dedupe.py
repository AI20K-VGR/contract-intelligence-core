#!/usr/bin/env python3
"""nudge_dedupe.py — per-(session, kind, subject) marker so a repeated breach nudges
ONCE per session.

Rationale: memory_gap_hook (~397 fires/3wk) and standards_drift_nudge re-print the SAME
subject every turn. The OBSERVATION trace still records every occurrence — only the
repeated stderr nudge is suppressed. Markers are ephemeral temp files.

Fail-open by construction: any marker error degrades to "not yet nudged" (i.e. it
nudges) rather than crashing a turn-end hook — a redundant nudge is harmless, a crash is not.
"""
import hashlib
import os
import tempfile
from pathlib import Path


def _temp_dir() -> Path:
    # Read $TMPDIR fresh each call (tempfile caches its first read, breaking per-test
    # TMPDIR isolation). Mirrors memory_gap_hook._temp_dir.
    return Path(os.environ.get("TMPDIR") or tempfile.gettempdir())


def _marker(session_id, kind, subject) -> Path:
    key = hashlib.sha256(
        ("%s|%s|%s" % (session_id, kind, subject)).encode("utf-8")).hexdigest()[:16]
    return _temp_dir() / ("harness-nudge-%s-%s" % (kind, key))


def already_nudged(session_id, kind, subject) -> bool:
    """True when (session, kind, subject) was already nudged this session. Fail-open:
    any error → False (nudge), never raises."""
    try:
        return _marker(session_id, kind, subject).exists()
    except Exception:  # noqa: BLE001 — a marker read must never break the turn
        return False


def mark_nudged(session_id, kind, subject) -> None:
    """Record that (session, kind, subject) was nudged. Best-effort; a write failure
    is swallowed (the marker is an optimization, not correctness)."""
    try:
        _marker(session_id, kind, subject).write_text("1", encoding="utf-8")
    except OSError:
        pass
