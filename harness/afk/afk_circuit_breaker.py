#!/usr/bin/env python3
"""afk_circuit_breaker.py — three-state stagnation FSM for the AFK loop.

The harness has hooks/gates but no stagnation watchdog for an unattended loop.
This is it:

    CLOSED  → HALF_OPEN  (>= half_open_at consecutive no-progress iterations)
            → OPEN       (>= open_at consecutive, OR a permission denial now)

Progress this iteration resets to CLOSED. The CALLER folds its progress signals
into one bool (git diff count > 0 OR explicit completion OR files_modified > 0).
A pending question SUPPRESSES the no-progress counter — the loop must not trip
merely because Claude is blocked asking the operator something.

State is persisted as APPEND-ONLY JSONL (one record per update); `restore_from`
reads the last record (last-record-wins) so a restarted controller resumes its
breaker state. No JSON overwrite — that would violate the store invariant.
Persistence is best-effort: a write error never breaks the loop.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

CLOSED, HALF_OPEN, OPEN = "closed", "half_open", "open"

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


class CircuitBreaker:
    def __init__(self, half_open_at: int = 2, open_at: int = 3, ledger_path=None,
                 _state: str = CLOSED, _count: int = 0):
        self._half = max(1, int(half_open_at))
        self._open = max(self._half, int(open_at))
        self._state = _state
        self._count = _count
        self._ledger = Path(ledger_path) if ledger_path else None

    @property
    def state(self) -> str:
        return self._state

    @property
    def no_progress_count(self) -> int:
        return self._count

    def is_open(self) -> bool:
        return self._state == OPEN

    def update(self, progress, *, permission_denied=False, question=False) -> str:
        """Advance the FSM for one iteration; returns the new state.

        Precedence: a permission denial opens immediately (an unattended loop
        cannot clear a permission wall); else progress resets; else a pending
        question is neutral (suppressed); else a no-progress step advances."""
        if permission_denied:
            self._count += 1
            self._state = OPEN
        elif progress:
            self._count = 0
            self._state = CLOSED
        elif question:
            pass  # suppressed — neither advance nor reset
        else:
            self._count += 1
            if self._count >= self._open:
                self._state = OPEN
            elif self._count >= self._half:
                self._state = HALF_OPEN
            else:
                self._state = CLOSED
        self._append(progress, permission_denied, question)
        return self._state

    def _append(self, progress, permission_denied, question) -> None:
        if self._ledger is None:
            return
        try:
            self._ledger.parent.mkdir(parents=True, exist_ok=True)
            with self._ledger.open("a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "state": self._state,
                    "count": self._count,
                    "progress": bool(progress),
                    "permission_denied": bool(permission_denied),
                    "question": bool(question),
                    "actor": _resolve_actor(),
                    "ts": _now_ts(),
                }, ensure_ascii=False) + "\n")
        except OSError:
            pass  # best-effort audit; never break the loop on a write error

    @classmethod
    def restore_from(cls, ledger_path, **kw) -> "CircuitBreaker":
        """Reconstruct from the last JSONL record (last-record-wins). Missing or
        unreadable ledger → a fresh CLOSED breaker."""
        state, count = CLOSED, 0
        try:
            p = Path(ledger_path)
            if p.is_file():
                lines = [ln for ln in p.read_text(encoding="utf-8").splitlines()
                         if ln.strip()]
                if lines:
                    rec = json.loads(lines[-1])
                    state = rec.get("state", CLOSED)
                    count = int(rec.get("count", 0))
        except (OSError, ValueError):
            state, count = CLOSED, 0
        return cls(ledger_path=ledger_path, _state=state, _count=count, **kw)
