#!/usr/bin/env python3
"""emit_observation.py — closed-vocab judgment-signal channel for skills.

Every lens today reads DETERMINISTIC data (a hook fires on every Edit/Bash). Nothing
lets a skill emit an end-of-work JUDGMENT — "the evidence I pulled was thin", "this gate
blocked me twice". That gap is the root of "low-volume telemetry reads as nothing to
improve": the counters can't see a judgment nobody recorded. This is the cooperative
half — the script appends deterministically, the skill (LLM) decides what is worth
recording.

The vocabulary is CLOSED (harness/data/observation-signals.yaml, human-edited). A signal
NOT in the vocabulary is a typo in a hand-edited config, so it fails LOUD: exit 2, no
write. Payload is capped at 2KB so the sink stays small. Each record carries actor + ts
and is APPEND-ONLY.

This is NOT a fail-open telemetry hook — it is a deterministic validator a skill invokes
on purpose, so a bad invocation must be visible, not swallowed.

CLI:
    emit_observation.py --skill hs:plan --signal thin-evidence --payload "..."
                        [--signals PATH] [--store PATH]
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Set

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

PAYLOAD_CAP_BYTES = 2048  # 2KB
_DEFAULT_VOCAB = Path(__file__).resolve().parent.parent / "data" / "observation-signals.yaml"
# Capture once at import; matches telemetry_paths._SESSION pattern so observations
# and other telemetry sinks share the same session dimension.
_SESSION = os.environ.get("HARNESS_SESSION_ID") or None


def load_vocab(path=None) -> Set[str]:
    """The set of allowed signal names from observation-signals.yaml. A missing or
    malformed file yields an empty set — which makes EVERY signal out-of-vocab and the
    emit fail loud, rather than silently accepting anything (fail-closed on the vocab)."""
    import yaml_io
    p = Path(path) if path is not None else _DEFAULT_VOCAB
    try:
        data = yaml_io.safe_load(p.read_text(encoding="utf-8")) or {}
    except (OSError, yaml_io.YAMLError):
        return set()
    names = set()
    for row in (data.get("signals") or []):
        if isinstance(row, dict) and row.get("name"):
            names.add(str(row["name"]))
        elif isinstance(row, str):
            names.add(row)
    return names


def _store_path(path=None) -> Path:
    if path is not None:
        return Path(path)
    env = os.environ.get("HARNESS_OBSERVATIONS_FILE")
    if env:
        return Path(env)
    try:
        import harness_paths
        return harness_paths.state_dir() / "telemetry" / "observations.jsonl"
    except Exception:
        # ABSOLUTE fallback — observation is telemetry-class; an unavailable harness_paths
        # must not crash the caller, and a relative path could write to the wrong place.
        return (Path(__file__).resolve().parent.parent
                / "state" / "telemetry" / "observations.jsonl")


def _actor() -> str:
    try:
        hooks_dir = Path(__file__).resolve().parent.parent / "hooks"
        if str(hooks_dir) not in sys.path:
            sys.path.append(str(hooks_dir))
        import hook_runtime
        # pass session_id so the observations sink resolves the SAME cached actor
        # as the usage/trace sinks (telemetry_paths._actor does the same); without
        # it resolve_actor re-derives from env and can disagree per session.
        return hook_runtime.resolve_actor(
            session_id=os.environ.get("HARNESS_SESSION_ID") or None)
    except Exception:
        return "user:unknown"


def emit(skill: str, signal: str, payload: str, *, vocab: Set[str],
         store=None, actor: Optional[str] = None, ts: Optional[str] = None) -> dict:
    """Validate then APPEND one record. Raises ValueError on an out-of-vocab signal or an
    over-cap payload — the caller turns that into exit 2 with a reason. Never writes on a
    validation failure."""
    if signal not in vocab:
        raise ValueError(
            "signal %r is not in the closed vocabulary (%s). Add it to "
            "observation-signals.yaml or fix the typo." % (signal, sorted(vocab)))
    payload_len = len(payload.encode("utf-8"))  # encode once (was computed twice)
    if payload_len > PAYLOAD_CAP_BYTES:
        raise ValueError("payload is %d bytes (> %d cap) — trim it."
                         % (payload_len, PAYLOAD_CAP_BYTES))
    rec = {
        "skill": str(skill),
        "signal": str(signal),
        "payload": str(payload),
        "actor": actor or _actor(),
        "ts": ts or datetime.now(timezone.utc).isoformat(),
    }
    if _SESSION:
        rec.setdefault("session", _SESSION)
    p = _store_path(store)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(rec, ensure_ascii=False) + "\n"  # serialize before opening
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(line)
    return rec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Emit a closed-vocab judgment signal.")
    ap.add_argument("--skill", required=True, help="emitting skill, e.g. hs:plan")
    ap.add_argument("--signal", required=True, help="signal name (must be in the vocabulary)")
    ap.add_argument("--payload", default="", help="short free-text context (<=2KB)")
    ap.add_argument("--signals", default=None, help="vocabulary YAML (default: harness/data/observation-signals.yaml)")
    ap.add_argument("--store", default=None, help="sink path (default: state/telemetry/observations.jsonl)")
    args = ap.parse_args(argv)

    vocab = load_vocab(args.signals)
    try:
        emit(args.skill, args.signal, args.payload, vocab=vocab, store=args.store)
    except ValueError as exc:
        sys.stderr.write("[emit_observation] REJECTED: %s\n" % exc)
        return 2
    except OSError as exc:
        # Observation is telemetry-class: a store I/O failure must fail OPEN (warn,
        # exit 0) — never crash the caller's work with a traceback.
        sys.stderr.write("[emit_observation] store write failed (ignored): %s\n" % exc)
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
