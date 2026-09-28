#!/usr/bin/env python3
"""track_script_execution.py — PostToolUse:Bash hook (telemetry-class).

Records harness-script Bash runs to state/telemetry/hook-telemetry.jsonl.
Filters to commands that run a harness/scripts/<f>.(py|sh) or
harness/e2e/<f>.(py|sh) in execution position (hook_runtime.SCRIPT_RE) — ignores
plain git/ls/grep. group(1) is the harness-relative path recorded as `script`.

ADAPT note: the source corpus hard-codes a skill-tree path-shape
(skills/<skill>/scripts/<f>) in both the matcher and its tests; the harness has
no such tree (its scripts live flat under harness/scripts and harness/e2e), and
that literal is barred from harness/ by the ownership-boundary invariant. The
filter is re-homed to the harness layout; only the matched path-shape changed —
the exit inference, pairing, and fail-open contract are ported as-is.

Exit signal: this host exposes no reliable numeric exit code in the PostToolUse
payload, so `exit` is inferred. The AUTHORITATIVE signal is tool_response
(is_error / interrupted). When both are absent the fallback anchors ONLY on an
explicit non-zero exit phrase ("exit code 1", "returned non-zero exit status 2")
— never a bare Error|Exception|Traceback, which over-matched benign output and
inflated the failure rate the reliability lens reads. Unknown ⇒ success.

Duration: if the PreToolUse:Bash counterpart (mark_bash_start) stamped a start
mark for this command, `ms` (wall-clock milliseconds) is included; otherwise the
record degrades gracefully without `ms`.

Fail-open + non-blocking + config gate are owned by hook_runtime.run_telemetry_hook;
this file holds only the record-building logic.

Hook stdin protocol: { tool_name, tool_input: { command }, tool_response, session_id }.
"""

import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
_LIB_DIR = os.path.join(_HOOKS_DIR, "..", "scripts")
sys.path.insert(0, _LIB_DIR)
if _HOOKS_DIR not in sys.path:
    sys.path.append(_HOOKS_DIR)
import hook_runtime  # noqa: E402

HOOK_CLASS = "telemetry"

# Shared matcher (single home in hook_runtime) — paired with mark_bash_start.
# group(1) = the harness-relative path scripts/<f>.py|sh | e2e/<f>.py|sh.
SCRIPT_RE = hook_runtime.SCRIPT_RE

_STEM = Path(__file__).stem


# Only an EXPLICIT non-zero exit phrase counts when the host gives no is_error:
# a successful run never prints "exit code 1" / "non-zero exit status 2". Bare
# Error|Exception|Traceback are deliberately NOT here — they fire on "Error
# handling OK", a help string that says "Traceback", a "0 errors" summary, and
# turn clean runs into phantom failures.
_NONZERO_EXIT_RE = re.compile(
    r"\b(?:exit (?:code|status)|returned non-zero exit status)\s+[1-9]",
    re.IGNORECASE,
)


def infer_exit(resp, stderr: str) -> int:
    # Authoritative host signal first; it overrides any stderr text.
    if isinstance(resp, dict) and (resp.get("interrupted") or resp.get("is_error")):
        return 1
    # No host exit code: anchor on an explicit non-zero exit phrase only.
    # Unknown ⇒ success (0) — a false 0 understates failures far less harmfully
    # than a false 1 overstates them across the reliability lens.
    if stderr and _NONZERO_EXIT_RE.search(stderr):
        return 1
    return 0


def core(data: dict) -> None:
    from telemetry_paths import append_event, read_and_clear_bash_start  # lazy
    tool_input = data.get("tool_input") or {}
    cmd = tool_input.get("command") or ""
    m = SCRIPT_RE.search(cmd)
    # A test run is recorded too, under its own `pytest:` namespace. SCRIPT_RE
    # cannot see `python3 -m pytest ...` (the runner is a MODULE, not a path in
    # execution position), so the one command class whose red/green transition
    # carries a TDD claim was the one class this recorder never wrote a row for.
    # The namespace keeps a test FILE from colliding with a script PATH in the
    # same field, so a lens counting script runs does not silently absorb them.
    test_target = hook_runtime.test_run_target(cmd)
    if not m and not test_target:
        return
    resp = data.get("tool_response")
    stderr = (resp.get("stderr") or "") if isinstance(resp, dict) else ""
    session = data.get("session_id") or os.environ.get("HARNESS_SESSION_ID") or ""
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "source": "hook:bash",
        "script": m.group(1) if m else "pytest:%s" % test_target,
        "exit": infer_exit(resp, stderr),
        "session": session,  # join key — the other sinks carry it; lenses join on it.
    }
    # Pair with the PreToolUse start mark, if present. Missing → no `ms`.
    ms = read_and_clear_bash_start(session, cmd)
    if ms is not None:
        record["ms"] = ms
    append_event("hook-telemetry.jsonl", record)


def main(raw=None) -> None:
    hook_runtime.run_telemetry_hook(_STEM, core, raw=raw)


if __name__ == "__main__":
    main()
