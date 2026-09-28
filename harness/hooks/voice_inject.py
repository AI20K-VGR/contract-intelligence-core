#!/usr/bin/env python3
"""voice_inject.py — SessionStart hook (telemetry-class) injecting the resolved
terminal-voice guidance as additionalContext.

The harness had no model-context injection before this: session_init.py only
caches the actor and continues. This is that new plumbing, kept SEPARATE from
session_init (single responsibility, fail-open). It reads the resolved
terminal-voice knobs PLUS the output-config register knobs (audience / code_style
/ humanize) via output_config.resolve_all() and emits an additionalContext that
POINTS at harness/rules/terminal-voice.md, states the active knob values, AND
carries the audience / code_style profile BODY (the MANDATORY/FORBIDDEN
directives) — built by the shared register_block builder so this surface and the
SubagentStart surface cannot drift. Live for the whole session and re-fires on
/compact (source=compact — the right cadence for a persistent register).

Advisory only: it never blocks (telemetry contract). On any error — or when
telemetry is disabled — it emits no context (fail-open: a broken voice hook
degrades to "natural voice", never to a blocked session). The emit logic lives
here rather than in the shared hook_runtime so the protected runtime stays
untouched; hook_runtime is used read-only (stdin / enabled / continue / audit).
"""

import json
import os
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(str(Path(__file__).resolve().parent.parent / "scripts"))
import hook_runtime    # noqa: E402
import voice_prefs     # noqa: E402,F401 - kept importable: tests monkeypatch voice_inject.voice_prefs.load
import output_config   # noqa: E402
import register_block  # noqa: E402

HOOK_CLASS = "telemetry"

# The register builder lives in register_block (SSOT shared with subagent_init).
# build_context is kept as a public alias for tests/callers that reference it;
# core() calls it and then appends the MAIN-ONLY persona-bundle block below.
# (inject_prompt_context.py defines its OWN build_context(root) and never imports
# this module — it is a separate builder, not this alias.)
build_context = register_block.build_register

# Ladder-anchor parity tests reference voice_inject._register / ._depth; alias to
# the shared definitions rather than copy (DRY — register_block is the home).
_register = register_block._register
_depth = register_block._depth


def core(data: dict):
    # Source = resolve_all(): terminal-voice axes + output-config register knobs
    # in one fail-open read (honors HARNESS_TERMINAL_VOICE + HARNESS_OUTPUT). The
    # terminal voice alone never carried audience/humanize — resolve_all does.
    prefs = output_config.resolve_all()
    text = build_context(prefs)
    # MAIN-ONLY append: NAME/SOUL/RELATIONSHIP go here, NOT through build_register,
    # so the SubagentStart surface (which calls build_register directly) never sees
    # them. Empty when no bundle is active → byte-identical to today (null path).
    extra = _persona_bundle_block(prefs)
    if extra:
        text = text + "\n" + extra
    return text


def _persona_bundle_block(prefs) -> str:
    """The MAIN-SESSION-ONLY persona-bundle append.

    NAME + characteristic + SOUL when a bundle is active; RELATIONSHIP only under a
    DOUBLE gate — a bundle is active AND a per-user PII file exists. This text is
    appended in core() (SessionStart, main + /compact re-fire) and NEVER reaches
    build_register, so subagent_init cannot inject it into a subagent surface (the
    security invariant). Returns "" for no active bundle (byte-identical null path)
    or a stale id — never raises (the callers are fail-open telemetry)."""
    bundle_id = prefs.get("persona_bundle")
    if not bundle_id:
        return ""
    # Everything past the null guard is wrapped fail-open: this helper is
    # telemetry-class and MUST NOT raise (the dispatcher can call core() directly,
    # bypassing run()'s outer try). Any registry/import/read failure degrades to ""
    # (natural voice) — mirrors build_register's defensive resolve().
    try:
        import persona_bundle
        bundle = persona_bundle.resolve(bundle_id)
        if bundle is None:
            return ""  # stale id → inert (build_register already fell back to the persona knob)

        lines = []
        name = bundle.get("name")
        if name:
            char = bundle.get("characteristic") or ""
            lines.append(
                "[Persona - who you are this session; MAIN session only, never a subagent surface]")
            lines.append("You are %s%s" % (name, (" - " + char) if char else ""))
        soul = bundle.get("soul")
        if soul:
            lines.append("SOUL (your character's core motivation; MAIN only): %s" % soul)

        # RELATIONSHIP — the SECOND gate: a PII file must exist. persona_me.load()
        # returns None when absent/corrupt, so a missing file simply omits this block.
        import persona_me
        rel = persona_me.load()
        if rel is not None:
            fields = {k: v for k, v in rel.items() if k != "_diag"}
            if fields:
                lines.append(
                    "[Who you're speaking with - RELATIONSHIP (user-declared); MAIN "
                    "session only, NEVER a subagent surface]")
                for k in sorted(fields):
                    lines.append("  %s: %s" % (k, fields[k]))
        return "\n".join(lines)
    except Exception:  # noqa: BLE001 — never raise from the injector (fail-open telemetry)
        return ""


def _emit_context(text: str) -> None:
    # Route through the shared co-emit chokepoint so the voice register mirrors to a
    # human systemMessage on the SAME config surface as UPS/Stop (dev sees "SessionStart
    # says: [Terminal voice…]"; ship stays model-only). Fail-open to the raw
    # additionalContext so a config-layer hiccup never drops the voice register.
    try:
        import context_surface_config as _cs
        _cs.emit("session_start", text)
        return
    except Exception:  # noqa: BLE001 — visibility layer must never drop the register
        pass
    sys.stdout.write(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": text,
        }
    }))
    sys.stdout.flush()


def run(raw=None) -> None:
    """Telemetry-class + fail-open context injector. Enabled -> build + emit the
    additionalContext; disabled or any exception -> plain continue (no context).
    Never raises, never exits 2."""
    data = hook_runtime.read_stdin_json() if raw is None else hook_runtime._parse(raw)
    try:
        if hook_runtime.hook_enabled("voice_inject", "telemetry"):
            text = core(data)
            if text:
                _emit_context(text)
                return
    except Exception as e:  # noqa: BLE001 - injection must never break the session
        hook_runtime.log_hook_error("voice_inject", e)
    hook_runtime.emit_continue()


def main(raw=None) -> None:
    run(raw=raw)


if __name__ == "__main__":
    main()
