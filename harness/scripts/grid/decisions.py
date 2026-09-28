"""grid/decisions.py — the human-readable decision log for one grid's lifetime.

``grid-decisions.md`` is a RECORD, never a gate: axis-selection reasons,
cost-table breakdowns when a guardrail trips, the user's AskUserQuestion
answer, an `--allow-oversize`/escalate/auto-escalate call, a below-floor HITL
result, keyword-lint findings. It is read by a human skimming the grid's
history; `coverage-grid.json` (`grid/artifact.py`) is the machine gate — the
two never merge and this module is never imported by a gate script
(`artifact_check.py` / `gate_stage.py` / `plan_approval.py`).

Append-only, mirroring ``auto_decision_log.py``'s contract: the full section
string is built (and the closed event-vocab validated) BEFORE any file is
touched, then written in a single ``open(path, "a").write(...)`` call — never
a read-modify-write of a prior section. `render_decision` returns byte-for-
byte what `append_grid_decision` would append for the same inputs (echo
before write: a caller prints `render_decision(rec)` to chat BEFORE an
AskUserQuestion, then appends the identical content after the user answers).

Actor is attribution, not authentication: resolved via
``harness/hooks/hook_runtime.py::resolve_actor`` (best-effort — a broken
resolver falls back to ``"user:unknown"``, never crashes the caller).
`run_seq` reads `HARNESS_RUN_SEQ` (null if absent), mirroring
`artifact_io.py`'s D1 boundary (tầng-1 does nothing with its semantics).

Writer-model (KISS): unlike `auto_decision_log.py`, this module does NOT walk
git-common-dir to resolve a MAIN worktree — `plan_dir` is always an explicit,
caller-supplied argument (never a session-based active-plan lookup), so the
caller (typically the cook MAIN agent, at a phase or the integration barrier)
is responsible for passing a durable path. A worktree-isolated subagent slice
should not call this directly for the same reason `auto_decision_log` avoids
it: its tree may be removed after the run.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union

# The closed event vocabulary — an event outside this set fails LOUD
# (ValueError, no write), mirroring auto_decision_log's closed-vocab discipline.
EVENT_VOCAB = frozenset({
    "axis-selection",
    "cost-table",
    "user-answer",
    "allow-oversize",
    "escalate",
    "auto-escalate",
    "below-floor-hitl",
    "keyword-lint",
})

_RUN_SEQ_ENV = "HARNESS_RUN_SEQ"
_STORE_NAME = "grid-decisions.md"

_TsArg = Union[None, str, Callable[[], str]]


# --------------------------------------------------------------------------- actor / ts / run_seq
def _hook_runtime():
    hooks_dir = str(Path(__file__).resolve().parent.parent.parent / "hooks")
    if hooks_dir not in sys.path:
        sys.path.append(hooks_dir)
    import hook_runtime
    return hook_runtime


def _resolve_actor(session: Optional[str] = None) -> str:
    """Attribution, never authentication — best-effort; a broken resolver
    chain must never crash a caller mid-grid-decision."""
    try:
        return _hook_runtime().resolve_actor(session_id=session)
    except Exception:  # noqa: BLE001 — actor is best-effort, fail open to a sentinel
        return "user:unknown"


def _resolve_ts(ts: _TsArg) -> str:
    if callable(ts):
        return ts()
    return ts or datetime.now(timezone.utc).isoformat()


def _run_seq() -> Optional[int]:
    """HARNESS_RUN_SEQ as int, or None when absent/blank/malformed — mirrors
    artifact_io.py's D1 boundary (tầng-1 does nothing with its semantics)."""
    raw = os.environ.get(_RUN_SEQ_ENV)
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return int(raw)
    except (ValueError, TypeError):
        return None


# --------------------------------------------------------------------------- section renderer
def _render_detail(detail: Any) -> str:
    """Terse, human-skimmable rendering of the free-form `detail` payload."""
    if detail is None:
        return ""
    if isinstance(detail, dict):
        if not detail:
            return ""
        return "\n".join("- %s: %s" % (k, v) for k, v in detail.items())
    if isinstance(detail, (list, tuple)):
        if not detail:
            return ""
        return "; ".join(str(x) for x in detail)
    text = str(detail).strip()
    return text


def _decision_section(rec: Dict[str, Any], actor: str, ts: str) -> str:
    """Build ONE markdown section for `rec`. Raises ValueError (no write) on
    an out-of-vocab `event` — the vocab check is the ONLY validation, and it
    runs before any I/O so `append_grid_decision` stays fail-closed."""
    event = rec.get("event")
    if event not in EVENT_VOCAB:
        raise ValueError(
            "grid decision event %r is not in the closed vocabulary (%s)"
            % (event, sorted(EVENT_VOCAB)))
    summary = str(rec.get("summary", "")).strip()
    detail_text = _render_detail(rec.get("detail"))
    parts = ["## %s · %s · %s" % (ts, actor, event), "", summary]
    if detail_text:
        parts.append("")
        parts.append(detail_text)
    return "\n".join(parts) + "\n\n"


# --------------------------------------------------------------------------- public API
def render_decision(rec: Dict[str, Any], *, actor: Optional[str] = None,
                     ts: _TsArg = None) -> str:
    """Return the EXACT markdown section `append_grid_decision` would append
    for the same `rec`/`actor`/`ts` — echo-before-write parity, so a caller
    can print this to chat before an AskUserQuestion and append the identical
    content afterward without drift."""
    resolved_actor = actor if actor is not None else _resolve_actor()
    resolved_ts = _resolve_ts(ts)
    return _decision_section(rec, resolved_actor, resolved_ts)


def append_grid_decision(plan_dir, rec: Dict[str, Any], *, session: Optional[str] = None,
                          now: _TsArg = None, actor: Optional[str] = None) -> Dict[str, Any]:
    """Append ONE markdown section to `<plan_dir>/artifacts/grid-decisions.md`
    (creating `artifacts/` if missing). Append-only: the section string is
    fully serialized before the file is ever opened, then written via a
    single `open(path, "a").write(...)` call — never a read-modify-write of
    a prior section. Returns `rec` enriched with the resolved `actor`, `ts`,
    and `run_seq` (the input `rec` is never mutated)."""
    resolved_actor = actor if actor is not None else _resolve_actor(session)
    resolved_ts = _resolve_ts(now)
    section = _decision_section(rec, resolved_actor, resolved_ts)  # raises before any I/O

    # Encoded here, not at `fh.write`. Building the section proves the string
    # can be BUILT, not that it can be WRITTEN: a lone surrogate is legal JSON
    # and legal `str`, and only fails when UTF-8 encoding runs. That happened
    # inside the `with`, after `open(..., "a")` had already created the file —
    # so a failed append left a ZERO-BYTE `grid-decisions.md` that reads as "a
    # ledger exists" to everything downstream. Encoding first moves the raise
    # to before any file is touched, which is what the append-only promise
    # above was always claiming.
    payload = section.encode("utf-8")

    art_dir = Path(plan_dir) / "artifacts"
    art_dir.mkdir(parents=True, exist_ok=True)
    path = art_dir / _STORE_NAME
    with open(path, "ab") as fh:
        fh.write(payload)

    enriched = dict(rec)
    enriched["actor"] = resolved_actor
    enriched["ts"] = resolved_ts
    enriched["run_seq"] = _run_seq()
    return enriched
