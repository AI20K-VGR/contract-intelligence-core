#!/usr/bin/env python3
"""context_surface_config.py — the HUMAN-facing systemMessage layer over the
build_context reminder injection.

The MODEL always receives the full reminder context (load-bearing — inject_prompt_context
on UserPromptSubmit, reinject_stop_context on a /goal Stop). These knobs never gate
that off; they only add/shape the OPTIONAL human-visible `systemMessage` mirror and
pick the Stop model_channel. SSOT: harness/data/context-surface.yaml (tracked ship
defaults); a dev points HARNESS_CONTEXT_SURFACE at .harness-dev/context-surface.yaml
to diverge (dev = verbose + double render; ship = summary + single).

Hard CC constraint this encodes (probe-verified 2.1.201): UserPromptSubmit
additionalContext is SILENT to the human, so a UPS systemMessage adds a clean human
mirror with no double. A Stop model channel (decision:block/reason OR additionalContext)
ALWAYS prints, so a Stop systemMessage is a DOUBLE render — on by default only in dev.

Fail-open: a malformed/missing/env-bogus file degrades to the code defaults below and
logs nothing fatal — a visibility layer must never break a hook.
"""
import os
from pathlib import Path

_NAME = "context-surface.yaml"
_SHIP = Path(__file__).resolve().parent.parent / "data" / _NAME

_VALID_CHANNELS = ("reason", "additionalContext")
_VALID_VERBOSITY = ("summary", "full")

# Code defaults = ship posture (single render, summary). A file merges OVER these.
# `system_message` is named after the CC output field it toggles (`{"systemMessage":…}`)
# — a concrete on/off for the human mirror, distinct from the nudge `user` axis (which
# is one of several independent model/user/stderr flags). Self-documenting on purpose.
_DEFAULTS = {
    "user_prompt_submit": {"system_message": False, "verbosity": "summary"},
    "stop": {"system_message": False, "verbosity": "summary", "model_channel": "reason"},
    "session_start": {"system_message": False, "verbosity": "summary"},
    "subagent_start": {"system_message": False, "verbosity": "summary"},
}

# The CC hookEventName each config-key emits under. The SSOT config keys are
# snake_case (they read cleanly in YAML); the CC payload needs the CamelCase event
# name so the additionalContext is accepted for THAT event (a mismatched name is
# silently dropped by CC). `stop` is special: it has no passive additionalContext-
# only mode — its model text rides either `decision:block/reason` or a Stop
# additionalContext, chosen by the per-event model_channel knob.
_EVENT_HOOKNAME = {
    "user_prompt_submit": "UserPromptSubmit",
    "session_start": "SessionStart",
    "subagent_start": "SubagentStart",
    "stop": "Stop",
}

_cache = None  # None = not yet loaded


def _path() -> Path:
    override = os.environ.get("HARNESS_CONTEXT_SURFACE")
    return Path(override) if override else _SHIP


def _coerce(event, key, value):
    """Validate one knob → a safe value, or None to keep the default. Bool knobs
    accept real bools; enum knobs accept their listed strings; anything else drops."""
    if key == "system_message":
        return value if isinstance(value, bool) else None
    if key == "verbosity":
        return value if value in _VALID_VERBOSITY else None
    if key == "model_channel" and event == "stop":
        return value if value in _VALID_CHANNELS else None
    return None


def load(path=None) -> dict:
    """Parse the config once per process (or from an explicit `path`, uncached — the
    test seam). Returns a full {event: {knobs}} map, defaults merged under any file
    values. Never raises."""
    global _cache
    if path is None and _cache is not None:
        return _cache
    cfg = {ev: dict(knobs) for ev, knobs in _DEFAULTS.items()}
    try:
        p = Path(path) if path else _path()
        # env override that points at a missing file → fall back to the tracked ship
        # file, so a stale HARNESS_CONTEXT_SURFACE never blanks the map.
        if path is None and os.environ.get("HARNESS_CONTEXT_SURFACE") and not p.is_file():
            p = _SHIP
        if p.is_file():
            import yaml_io  # lazy: missing dep degrades to defaults here
            raw = yaml_io.safe_load(p.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for ev in _DEFAULTS:
                    sub = raw.get(ev)
                    if isinstance(sub, dict):
                        for k, v in sub.items():
                            coerced = _coerce(ev, k, v)
                            if coerced is not None:
                                cfg[ev][k] = coerced
    except Exception:  # noqa: BLE001 — a visibility layer must not crash a hook
        cfg = {ev: dict(knobs) for ev, knobs in _DEFAULTS.items()}
    if path is None:
        _cache = cfg
    return cfg


def _reset() -> None:
    """Test seam: force a re-read (mirrors hook_runtime._reset_nudge_channels_cache)."""
    global _cache
    _cache = None


def event(name: str) -> dict:
    """Resolved knobs for one event ('user_prompt_submit' | 'stop' |
    'session_start' | 'subagent_start')."""
    return load().get(name, dict(_DEFAULTS.get(name, {})))


def build_payload(event_name: str, text: str) -> dict:
    """The ONE place every context-injecting hook builds its emission payload.

    Given the SSOT event key + the model-facing `text`, produce the CC hook
    output dict: the MODEL channel (additionalContext for UPS/SessionStart/
    SubagentStart; reason-or-additionalContext for Stop, per model_channel) PLUS
    an OPTIONAL human `systemMessage` mirror when the event's system_message knob
    is on. Fixing a channel here fixes it for all callers — no per-hook
    re-implementation, no drift between which hook mirrors to the human and which
    does not. Never raises (the config layer is fail-open)."""
    cfg = event(event_name)
    hook_event = _EVENT_HOOKNAME.get(event_name, event_name)
    if event_name == "stop" and cfg.get("model_channel", "reason") == "reason":
        # Stop's documented re-invoke channel: decision:block carries `reason`.
        payload = {"decision": "block", "reason": text}
    else:
        payload = {"hookSpecificOutput": {"hookEventName": hook_event,
                                          "additionalContext": text}}
    if cfg.get("system_message"):
        payload["systemMessage"] = render_human(text, cfg.get("verbosity", "summary"))
    return payload


def emit(event_name: str, text: str) -> None:
    """Serialize build_payload(event_name, text) to stdout — the hook's emission.
    A thin write so a caller that needs the dict (to fold in extra keys) can call
    build_payload directly instead."""
    import json
    import sys
    sys.stdout.write(json.dumps(build_payload(event_name, text)))
    sys.stdout.flush()


_NUDGE_TAGS = ("[goal-cycle]", "[backlog-capture]", "[decision-capture]",
               "[standards-drift]", "[memory-gap]")


def _section_labels(text: str) -> list:
    """Short section labels for the summary line, from BOTH heading styles:

      `## Header`          -> "Header"            (build_context: UPS/Stop reminder)
      `[Label - detail…]`  -> "Label"            (voice/subagent register uses bracket
      `[Label: value] …`   -> "Label"             tags, not `## ` — trimmed to the first
                                                  ` - ` / `: ` / ` — ` separator)

    Nudge tags (`[backlog-capture]`, `[goal-cycle]`, …) also open with `[` but are
    COUNTED separately by render_human, so they are skipped here — never double-surfaced
    as a section. Order-preserving de-dup keeps a repeated label from padding the line.
    """
    labels = []
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith("## "):
            label = s[3:].strip()
        elif s.startswith("[") and "]" in s:
            bracket = s[:s.index("]") + 1]         # the leading "[…]" only
            if bracket in _NUDGE_TAGS:
                continue                            # counted as a nudge, not a section
            label = bracket[1:-1].strip()
            for sep in (" - ", ": ", " — "):        # trim to the short lead label
                i = label.find(sep)
                if i != -1:
                    label = label[:i].strip()
                    break
        else:
            continue
        if label and label not in labels:
            labels.append(label)
    return labels


def render_human(text: str, verbosity: str) -> str:
    """Shape the human `systemMessage` mirror of build_context `text`.

    full    -> the text verbatim (the human sees exactly what the model got).
    summary -> a one-line "Nhóm nhắc nhở: <section labels> (+N nudge)" — names the
               `## ` sections AND `[…]` register labels, and counts any folded nudge
               tags, WITHOUT the heavy body.

    A LEADING newline is always prepended so the body renders on its own line UNDER
    CC's "<Event> says:" label instead of running on after it.
    """
    if verbosity == "full":
        return "\n" + text
    labels = _section_labels(text)
    n_nudge = sum(text.count(tag) for tag in _NUDGE_TAGS)
    parts = " · ".join(labels) if labels else "context"
    tail = " (+%d nudge)" % n_nudge if n_nudge else ""
    return "\nNhóm nhắc nhở: %s%s" % (parts, tail)
