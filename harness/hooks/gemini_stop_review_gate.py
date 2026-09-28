#!/usr/bin/env python3
"""gemini_stop_review_gate.py — Stop-event hook: an optional gemini review of the
assistant's last turn. REWRITTEN fail-open (NOT the vendored fail-closed .mjs).

RT-02 is defused by STRUCTURE, not just try/except: a Stop hook's `decision: block`
re-invokes the model with `reason` as its context (documented Stop channel;
probe-verified CC 2.1.201), so the SHIPPED mode `advisory` emits its review to STDERR
and NEVER emits a block — a hook that cannot re-invoke the model cannot brick a
session. Only the opt-in `enforce` mode emits the block, and only when a /goal is NOT
active (S3), a per-session circuit-breaker has not tripped, and gemini returned a FAIL.

Two independent OFF layers ship the gate asleep: (a) HOOK_CLASS=nudge defaults OFF
in harness-hooks.yaml; (b) the lane config `stop_review_gate: off`. Either keeps it
inert. Every failure path — down gemini, /goal live, crashing config — fails OPEN
(exit 0, {"continue": true}); a config crash is caught explicitly (SystemExit too),
so a malformed lane file never exits 2.
"""
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_HARNESS = os.path.dirname(_HERE)
for _p in (_HERE,
           os.path.join(_HARNESS, "scripts"),
           os.path.join(_HARNESS, "plugins", "hs", "scripts")):
    if _p not in sys.path:
        sys.path.append(_p)

import hook_runtime  # noqa: E402

HOOK_CLASS = "nudge"
_STEM = "gemini_stop_review_gate"
_BREAKER_MAX = 3
_TAIL_BYTES = 256 * 1024


def _last_goal_status(transcript_path):
    """The attachment of the LAST goal_status record, else None (bounded tail;
    any error → None). Mirrors reinject_stop_context._last_goal_status."""
    if not transcript_path:
        return None
    try:
        with open(transcript_path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - _TAIL_BYTES))
            chunk = fh.read()
        last = None
        for line in chunk.splitlines():
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if (isinstance(rec, dict) and isinstance(rec.get("attachment"), dict)
                    and rec["attachment"].get("type") == "goal_status"):
                last = rec["attachment"]
        return last
    except Exception:
        return None


def _last_assistant_text(transcript_path):
    """Best-effort text of the last assistant turn (for the review prompt). Any
    parse failure → "" (the review just runs on empty context; never fatal)."""
    if not transcript_path:
        return ""
    try:
        with open(transcript_path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - _TAIL_BYTES))
            chunk = fh.read()
        text = ""
        for line in chunk.splitlines():
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if not isinstance(rec, dict):
                continue
            if rec.get("type") == "assistant" or rec.get("role") == "assistant":
                msg = rec.get("message", rec)
                content = msg.get("content") if isinstance(msg, dict) else None
                if isinstance(content, list):
                    text = "".join(b.get("text", "") for b in content
                                   if isinstance(b, dict) and b.get("type") == "text")
                elif isinstance(content, str):
                    text = content
        return text
    except Exception:
        return ""


def _breaker_file():
    import harness_paths
    return harness_paths.state_dir() / "gemini" / "stop_breaker.json"


def _breaker_read():
    try:
        return json.loads(_breaker_file().read_text(encoding="utf-8"))
    except Exception:
        return {}


def _breaker_count(session):
    try:
        return int(_breaker_read().get(session, 0))
    except Exception:
        return 0


def _breaker_bump(session):
    try:
        import harness_paths
        if harness_paths.writable_state_dir() is None:
            return  # unresolved root: dropping a breaker tick beats writing to /
        p = _breaker_file()
        p.parent.mkdir(parents=True, exist_ok=True)
        data = _breaker_read()
        data[session] = int(data.get(session, 0)) + 1
        p.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        pass  # breaker is best-effort; its failure must not break the loop


def _verdict(text):
    """Extract the review verdict from an explicit `VERDICT: <v>` prefix or a JSON
    `"verdict": "<v>"` field. Grepping the whole body for FAIL false-fired on prose
    like "no FAIL conditions" (review finding). No explicit verdict → PASS
    (non-blocking)."""
    t = text or ""
    m = re.search(r'VERDICT:\s*"?(PASS_WITH_RISK|PASS|FAIL)', t, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    m = re.search(r'"verdict"\s*:\s*"(PASS_WITH_RISK|PASS|FAIL)"', t, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    return "PASS"


def _emit_additional_context(text):
    # Documented Stop re-invoke channel: `decision: block` prevents the stop and
    # hands `reason` to the model (probe-verified CC 2.1.201), replacing the older
    # undocumented additionalContext-on-Stop path. enforce-only + goal-gated + breaker.
    sys.stdout.write(json.dumps({"decision": "block", "reason": text}))
    sys.stdout.flush()


def core(data: dict):
    """The Stop re-invoke text when gemini's enforce review FAILs (routed to Stop's
    decision:block model channel), else None. Advisory mode writes its `[gemini-review]`
    line to stderr and returns None. Pure — no emit/exit — so the in-process dispatcher
    can call it; the caller owns the enabled-check + terminal write. Fail-open BY DESIGN
    (a nudge lane): every internal error yields None. Makes a slow partner spawn, so its
    registry entry sets a longer per-hook timeout."""
    try:
        # Lane config imported INSIDE the try: a crashing/malformed config (SystemExit
        # from resolve) must fail OPEN (F6).
        import gemini_partner_config as cfgmod
        import gemini_companion as gc
        cfg = cfgmod.effective(cfgmod.resolve())
        if cfg["master"] == "off" or cfg["stop_review_gate"] == "off":
            return None
        # S3: a live /goal owns the Stop channel — emit NOTHING so we never fight the
        # autonomous loop (no human is watching to clear a block).
        gs = _last_goal_status(data.get("transcript_path"))
        if gs and gs.get("met") is False:
            return None
        mode = cfg["stop_review_gate"]
        assistant = _last_assistant_text(data.get("transcript_path"))
        prompt = ("Review the assistant's last turn for correctness and risk. "
                  "Start your reply with 'VERDICT: PASS' or 'VERDICT: FAIL'.\n\n"
                  + assistant)
        out = gc.partner_call("review", prompt)
        review = ""
        if getattr(out, "status", None) == "ok":
            content = out.content
            review = content.get("text", "") if isinstance(content, dict) else str(content)
        if mode == "advisory":
            # STDERR only — structurally cannot re-invoke the model (RT-02).
            note = review.strip() or "(gemini review unavailable — degraded)"
            sys.stderr.write("[gemini-review] %s\n" % note[:2000])
            return None
        if mode == "enforce":
            session = data.get("session_id") or "default"
            if _breaker_count(session) >= _BREAKER_MAX:
                return None  # breaker tripped → back off
            if getattr(out, "status", None) != "ok":
                return None  # gemini down → allow, never block
            if _verdict(review) == "FAIL":
                _breaker_bump(session)
                return "gemini review flagged the last turn:\n" + review[:2000]
    except (Exception, SystemExit) as e:  # noqa: BLE001 — nudge must never break the loop
        try:
            hook_runtime.log_hook_error(_STEM, e)
        except Exception:
            pass
    return None


def run(raw=None):
    data = hook_runtime.read_stdin_json() if raw is None else hook_runtime._parse(raw)
    try:
        if hook_runtime.hook_enabled(_STEM, "nudge"):
            text = core(data)
            if text:
                _emit_additional_context(text)
                return
    except (Exception, SystemExit) as e:  # noqa: BLE001 — nudge must never break the loop
        try:
            hook_runtime.log_hook_error(_STEM, e)
        except Exception:
            pass
    hook_runtime.emit_continue()


def main(raw=None):
    run(raw=raw)


if __name__ == "__main__":
    main()
