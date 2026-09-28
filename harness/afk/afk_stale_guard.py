#!/usr/bin/env python3
"""afk_stale_guard.py — stale-loop fingerprint.

The circuit breaker detects no-progress by git diff, but a loop that makes the
SAME tool call every iteration and always gets the same result (e.g. a read-only
grep loop) makes no diff and would not trip it. This guard fills that gap: it
fingerprints each iteration's (tool, source, payload) and flags `is_stale()` when
the same signature fires `threshold` times in a row.

The decision is in-memory. An optional append-only JSONL ledger records each
observation for audit — best-effort: a write error is swallowed so a full disk or
bad path never breaks the loop. The ledger is APPEND-ONLY (never rewritten), per
the harness store invariant.
"""

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_HOOKS_DIR = Path(__file__).resolve().parent.parent / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.append(str(_HOOKS_DIR))
try:
    import hook_runtime as _hr  # noqa: E402
    _resolve_actor = _hr.resolve_actor
except Exception:  # noqa: BLE001 — audit attribution must never block the loop
    def _resolve_actor(session_id=None):  # type: ignore
        return "unknown"


def _now_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _payload_digest(payload) -> str:
    if payload is None:
        return ""
    if isinstance(payload, (dict, list)):
        try:
            payload = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        except (TypeError, ValueError):
            payload = repr(payload)
    return hashlib.sha1(str(payload).encode("utf-8")).hexdigest()[:16]


def fingerprint(tool_name, source=None, payload=None) -> str:
    """Stable 16-hex signature of an iteration's tool call. Dict/list payloads are
    canonicalized (sorted keys) so logically-equal calls fingerprint equal."""
    src = "%s|%s|%s" % (tool_name or "", source or "", _payload_digest(payload))
    return hashlib.sha1(src.encode("utf-8")).hexdigest()[:16]


class StaleGuard:
    def __init__(self, threshold: int = 3, ledger_path=None):
        self._threshold = max(2, int(threshold))
        self._history = []
        self._ledger = Path(ledger_path) if ledger_path else None

    def record(self, tool_name, source=None, payload=None) -> str:
        fp = fingerprint(tool_name, source, payload)
        self._history.append(fp)
        if self._ledger is not None:
            self._append_ledger(fp, tool_name, source)
        return fp

    def _append_ledger(self, fp, tool_name, source) -> None:
        try:
            self._ledger.parent.mkdir(parents=True, exist_ok=True)
            with self._ledger.open("a", encoding="utf-8") as f:
                f.write(json.dumps(
                    {"fp": fp, "tool": tool_name, "source": source,
                     "actor": _resolve_actor(), "ts": _now_ts()},
                    ensure_ascii=False) + "\n")
        except OSError:
            pass  # audit ledger is best-effort; never break the loop on a write error

    def is_stale(self) -> bool:
        """True when the last `threshold` signatures are all identical."""
        if len(self._history) < self._threshold:
            return False
        tail = self._history[-self._threshold:]
        return len(set(tail)) == 1

    @property
    def consecutive_identical(self) -> int:
        if not self._history:
            return 0
        n, last = 1, self._history[-1]
        for fp in reversed(self._history[:-1]):
            if fp != last:
                break
            n += 1
        return n
