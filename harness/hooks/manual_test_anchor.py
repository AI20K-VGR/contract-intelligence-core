#!/usr/bin/env python3
"""manual_test_anchor.py — PostToolUse:Bash telemetry hook (manual-test anchor).

During a manual-test session (HARNESS_MANUAL_TEST_SESSION set) it records each
Bash command as an anchor — {anchor_id, cmd_hash, output_hash?} — so a
manual-test artifact can cite a trace the HOOK witnessed, not one the agent
asserts. The DoD gate later cross-checks the cited id exists (manual_test.
anchor_exists) before counting the evidence anchored.

Scoped to a session so the sink does not flood on every Bash call. Telemetry
class: fail-open, never blocks the op. This is tamper-EVIDENCE (a real command
ran), NOT authentication — see manual_test.py.
"""

import os
import sys

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
_LIB_DIR = os.path.join(_HOOKS_DIR, "..", "scripts")
sys.path.insert(0, _LIB_DIR)
if _HOOKS_DIR not in sys.path:
    sys.path.append(_HOOKS_DIR)
import hook_runtime  # noqa: E402

HOOK_CLASS = "telemetry"
_STEM = "manual_test_anchor"


def core(data: dict) -> None:
    # Only anchor during an explicit manual-test session — keeps the sink scoped.
    # Armed by EITHER the env var OR a session marker file: the marker closes the
    # "forgot the env / subagent did not inherit it" hole (it lives under the
    # shared state dir, so it survives a subagent boundary the env does not).
    import manual_test
    session_id = data.get("session_id")
    if not os.environ.get("HARNESS_MANUAL_TEST_SESSION"):
        try:
            import harness_paths
            armed = manual_test.session_armed(harness_paths.state_dir(), session_id)
        except Exception:  # noqa: BLE001 — a gating error must never break telemetry
            armed = False
        if not armed:
            return
    command = hook_runtime.bash_command(data)
    if not command:
        return
    output = None
    resp = data.get("tool_response")
    if isinstance(resp, dict):
        output = resp.get("stdout") or resp.get("output") or resp.get("stderr")
    elif isinstance(resp, str):
        output = resp
    import telemetry_paths
    telemetry_paths.append_event(
        manual_test.ANCHOR_SINK,
        manual_test.build_anchor(command, output, session=session_id, source="hook"))


def main(raw=None) -> None:
    hook_runtime.run_telemetry_hook(_STEM, core, raw=raw)


if __name__ == "__main__":
    main()
