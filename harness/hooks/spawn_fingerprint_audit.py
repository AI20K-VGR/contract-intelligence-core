#!/usr/bin/env python3
"""spawn_fingerprint_audit.py — P9 (Ask-3 C3) group-fingerprint post-run
audit (nudge-class, OBSERVATION-only).

C3's second half — the "early-write + grouping" enforcement. A pre-spawn
hook cannot see files that do not exist yet, so this is a two-phase design:
P7 is the pre-spawn token (the BLOCK form, EP0-gated, not built here); this
is P9 — the POST-run file audit. On Stop, for the active orchestrate
strategy token (`spawn_provenance.load_active_token`), each declared group
must have >=1 early-written finding file under the token's `report_dir`
(`spawn_provenance.groups_missing_early_write`). A missing group records ONE
closed-vocab `emit_observation` — never a live nudge, never a block.

Channel honesty (m11): a Stop hook that emits `additionalContext` FORCES a
re-invocation of the model (memory `cc-stop-additionalcontext-causes-
continuation`). This audit must NOT do that, so `handle_stop` NEVER returns a
value — the dispatcher only routes a nudge/additionalContext off a truthy
core() return, so a hard-coded `return None` on every path is what keeps
this silent by construction, not a config toggle. `main()` mirrors the same
contract standalone: it always emits a plain `{"continue": true}`.

Today NO token producer exists (that is Layer-1b, EP0-gated), so
`load_active_token` never finds an active token and this audit is INERT in
practice — it ships the post-run capability + reader now; it activates once
1b writes tokens. Fail-open throughout: a crash here must never break Stop.
"""

import os
import sys
from pathlib import Path

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS_DIR = os.path.join(os.path.dirname(_HOOKS_DIR), "scripts")
for _p in (_SCRIPTS_DIR, _HOOKS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import hook_runtime      # noqa: E402
import spawn_provenance  # noqa: E402

HOOK_CLASS = "nudge"
_NAME = Path(__file__).stem
_SKILL = "hs:workflow-orchestrate"
_SIGNAL = "spawn-group-early-write-missing"


def _record_observation(missing, token, *, store=None, vocab=None) -> None:
    """Append ONE closed-vocab observation naming the missing group keys.
    Best-effort/fail-open — an observation-store hiccup must never surface
    to the model or break Stop."""
    try:
        import emit_observation
        v = vocab if vocab is not None else emit_observation.load_vocab()
        payload = "missing early-write for group(s): %s (run_id=%s)" % (
            ", ".join(missing), token.get("run_id") or "")
        emit_observation.emit(_SKILL, _SIGNAL, payload, vocab=v, store=store)
    except Exception as e:  # noqa: BLE001 — observation-only, never raise into Stop
        hook_runtime.log_hook_error(_NAME, e)


def handle_stop(payload, *, env=None, store=None, vocab=None):
    """Load the active orchestrate token for this session; if any declared
    group has no early-written file under `report_dir`, record ONE
    closed-vocab observation naming it. ALWAYS returns None — this hook must
    never surface additionalContext / a live nudge / a block; it is silent
    post-hoc bookkeeping only. Fail-open throughout (no token / unreadable
    dir / a crash -> silent, never raises)."""
    try:
        if not isinstance(payload, dict):
            return None
        session = payload.get("session_id") or ""
        token = spawn_provenance.load_active_token(session, env=env)
        if not token:
            return None
        missing = spawn_provenance.groups_missing_early_write(token)
        if missing:
            _record_observation(missing, token, store=store, vocab=vocab)
    except Exception as e:  # noqa: BLE001 — fail-open: this audit never blocks Stop
        hook_runtime.log_hook_error(_NAME, e)
    return None  # ALWAYS None — never routed as a nudge/additionalContext


def main() -> int:
    if not hook_runtime.hook_enabled(_NAME, HOOK_CLASS):
        hook_runtime.emit_continue()
        return 0
    data = hook_runtime.read_stdin_json()
    d = data if isinstance(data, dict) else {}
    try:
        handle_stop(d)
    except Exception as e:  # noqa: BLE001 — fail-open: a hook crash must never break Stop
        hook_runtime.log_hook_error(_NAME, e)
    hook_runtime.emit_continue()
    return 0


if __name__ == "__main__":
    sys.exit(main())
