#!/usr/bin/env python3
"""emit_disabled_demand.py — record demand for an install-disabled (off) skill.

Closes the re-enable feedback loop: when an off skill is actually reached — run through
the `hs:use` proxy (`via=proxy_run`), or blocked by the router (`via=router_block`) — a
demand row is appended to invocations.jsonl KEYED ON THE TARGET skill, not on "hs:use".
lens_skill_usage aggregates by `skill`, so a target-keyed row lets it count how many
DISTINCT sessions wanted the skill back and raise a re-enable hint past a threshold.

Dedup is PER-SESSION: one demand / skill / session, so a session that hammers the
proxy cannot inflate the "N distinct sessions" signal. Keying is the whole-session tuple
`(session|skill)`, NOT per-minute — a legitimately long session still counts once.

Telemetry-class: emit MUST fail-open. A broken sink, an unavailable telemetry_paths, a
malformed record — none may raise into the caller. The proxy/router behavior never hinges
on whether the demand landed.

CLI:
    emit_disabled_demand.py --skill hs:critique --via proxy_run   [--session <id>]
    emit_disabled_demand.py --skill ask         --via router_block --session s1
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

_VIA = ("proxy_run", "router_block")


def _current_session_from_state():
    """Recover the live session id when the caller has none in its env.

    The hs:use proxy runs this emitter as a bare Bash CLI — no hook payload, no
    HARNESS_SESSION_ID — so the PRIMARY demand path would otherwise write every row
    with an empty session, collapsing the whole distinct-session count. session_init
    writes state/sessions/<id>.json once at SessionStart; the newest by mtime is the live
    session. Personal-first assumption: one active session at a time — concurrent sessions
    may collide onto the newest, which under-counts but never crashes. Fail-soft → None."""
    try:
        import harness_paths
        d = harness_paths.state_dir() / "sessions"
        files = [p for p in d.glob("*.json") if p.is_file()]
        if not files:
            return None
        return max(files, key=lambda p: p.stat().st_mtime).stem or None
    except Exception:
        return None


def emit(skill: str, via: str, session: str = None) -> None:
    """Append one target-keyed demand row, deduped per (session, skill). Fail-open.

    Session resolution order: explicit arg > $HARNESS_SESSION_ID > newest state session.
    """
    try:
        skill = (skill or "").strip()
        if not skill or via not in _VIA:
            return
        session = ((session or "").strip()
                   or os.environ.get("HARNESS_SESSION_ID")
                   or _current_session_from_state())
        import telemetry_paths
        rec = {"skill": skill, "proxy_invoked": True, "via": via}
        if session:
            rec["session"] = session
        # Per-session dedup key. append_event_once collapses a repeat within the
        # marker TTL; the session dimension makes the collapse whole-session, not
        # per-minute. append_event_once is itself fully fail-open.
        dedup = "demand|%s|%s" % (session or "", skill)
        telemetry_paths.append_event_once("invocations.jsonl", rec, dedup)
    except Exception:
        pass  # fail-open: demand telemetry must never break the observed op


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="record demand for an off skill (fail-open)")
    ap.add_argument("--skill", required=True, help="the off TARGET skill (e.g. hs:critique)")
    ap.add_argument("--via", required=True, choices=_VIA,
                    help="how the off skill was reached")
    ap.add_argument("--session", default=None,
                    help="session id (dedup dimension); when omitted, emit resolves "
                         "$HARNESS_SESSION_ID then the newest state session")
    try:
        args = ap.parse_args(argv)
    except SystemExit:
        # argparse validation error is a caller bug, not a telemetry failure — but even
        # so, never propagate a non-zero into a fail-open call site.
        return 0
    emit(args.skill, args.via, args.session)
    return 0


if __name__ == "__main__":
    sys.exit(main())
