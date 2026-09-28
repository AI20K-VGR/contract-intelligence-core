#!/usr/bin/env python3
"""track_subagent_outcome.py — SubagentStop hook (telemetry-class).

Records one line per finished subagent to state/telemetry/subagent-outcomes.jsonl:
  {ts, agent_type, outcome, session, transcript?}

outcome ∈ {success, api_error, timeout, blocked, unknown}. Powers the
reliability / subagent_outcomes lenses.

Why a `transcript` path is stored: the subagent's own transcript
(<session>/subagents/agent-<id>.jsonl) is typically NOT flushed yet when
SubagentStop fires — reading it here usually yields `unknown`. So the hook
records the authoritative transcript path and the read-time lens reclassifies
the `unknown` later, when the file IS flushed (its terminal stop_reason is then
available). See lens_subagent_outcomes.gather.

Outcome inference at stop time (priority order):
  1. An explicit `outcome` enum in the payload, if known.
  2. Race-free: an ERROR ending visible in the in-payload `last_assistant_message`
     (api_error / timeout / blocked) — needs no file.
  3. Classify the subagent transcript tail IF already flushed (usually not).
  4. Default `unknown` — NEVER fabricate `success` when the signal is absent.

The subagent transcript is located from `agent_transcript_path` (authoritative,
handed by the host), else reconstructed from `transcript_path` (the MAIN session
transcript) + `agent_id`. The main transcript is never classified as the
subagent's outcome.

agent_type comes from the payload (`agent_type`/`subagent_type`) or the
transcript filename (agent-<type>-<id>.jsonl).

Fail-open + non-blocking + config gate are owned by hook_runtime.run_telemetry_hook
(no-op under HARNESS_TELEMETRY_DISABLED / pytest / config-disabled).

Hook stdin protocol:
  { session_id, transcript_path, agent_transcript_path?, agent_id?,
    agent_type?, last_assistant_message?, outcome? }.
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
_LIB_DIR = os.path.join(_HOOKS_DIR, "..", "scripts")
sys.path.insert(0, _LIB_DIR)
if _HOOKS_DIR not in sys.path:
    sys.path.append(_HOOKS_DIR)
import hook_runtime  # noqa: E402
import subagent_classify  # noqa: E402
from subagent_classify import OUTCOMES, classify_from_transcript, classify_text  # noqa: E402,F401

HOOK_CLASS = "telemetry"

_STEM = Path(__file__).stem


def _subagent_transcript(data: dict):
    """Authoritative subagent transcript path, or None.

    Prefer the host-supplied `agent_transcript_path`; else reconstruct from the
    MAIN session transcript (`transcript_path`, stripped of its extension to get
    the session dir) plus `agent_id`: <session>/subagents/agent-<agent_id>.jsonl.
    Never returns the main transcript.
    """
    direct = data.get("agent_transcript_path")
    if direct:
        return str(direct)
    agent_id = data.get("agent_id") or data.get("agentId") or data.get("subagent_id")
    main_tp = data.get("transcript_path")
    if agent_id and main_tp:
        session_dir = os.path.splitext(str(main_tp))[0]
        return os.path.join(session_dir, "subagents", "agent-%s.jsonl" % agent_id)
    return None


def _classify_target(data: dict):
    """The transcript path to classify (and to store for deferred lens classify).

    A real subagent stop resolves to the subagent transcript. Only on a legacy
    host that carries NO agent context (`agent_id`/`agent_transcript_path`) does
    `transcript_path` itself point at the subagent transcript.
    """
    sub = _subagent_transcript(data)
    if sub is not None:
        return sub
    if not (data.get("agent_id") or data.get("agentId") or data.get("subagent_id")):
        return data.get("transcript_path")
    return None


def infer_outcome(data: dict) -> str:
    explicit = str(data.get("outcome") or "").strip().lower()
    if explicit in OUTCOMES:
        return explicit
    # Race-free: an error ending is visible in the in-payload final message even
    # when the transcript file is not flushed yet.
    err = classify_text(data.get("last_assistant_message") or "")
    if err != "unknown":
        return err
    # Transcript tail — usually unknown at stop time (terminal record unflushed);
    # the lens reclassifies later from the stored path.
    return classify_from_transcript(_classify_target(data))


def core(data: dict) -> None:
    from telemetry_paths import append_event  # lazy: skipped when disabled
    target = _classify_target(data)
    agent_type = str(
        data.get("agent_type") or data.get("subagent_type")
        or subagent_classify.agent_type_from_filename(target or "")
    ) or "unknown"
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "agent_type": agent_type,
        "outcome": infer_outcome(data),
        "session": data.get("session_id") or os.environ.get("HARNESS_SESSION_ID") or "",
    }
    if target:
        record["transcript"] = target  # lets the lens reclassify once flushed
    append_event("subagent-outcomes.jsonl", record)


def main(raw=None) -> None:
    hook_runtime.run_telemetry_hook(_STEM, core, raw=raw)


if __name__ == "__main__":
    main()
