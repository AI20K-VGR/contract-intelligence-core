#!/usr/bin/env python3
"""reinject_config.py — reader for reinject-strategy.yaml (the reinject cadence +
slim-budget posture consumed by harness/hooks/inject_prompt_context.py).

Lifts the two previously welded-shut module constants (_INJECT_EVERY_TURNS,
SLIM_BUDGET_CHARS) into config with named presets (aggressive/balanced/lazy).
Mirrors model_policy.py's fail-open config-reader shape: an env-override test
seam (HARNESS_REINJECT_STRATEGY, same idea as HARNESS_MODEL_POLICY), never
raises, and degrades to the current shipped default on anything broken.

Resolution order: presets[active preset] provides the base values; a top-level
every_turns/slim_budget_chars key (if present) OVERRIDES the preset per-key —
so a single knob can be tuned without inventing a whole new preset row.

Fail-open by design: a missing file, unparseable YAML, missing PyYAML, a
non-mapping document, or an unknown active preset all degrade to the shipped
default (every_turns=5, slim_budget_chars=1100) — the exact values the module
constants held before this file existed. inject_prompt_context.decide() stays
PURE; it never imports this module — callers (run()/core_gated()) resolve here
and pass the value in.
"""
import json
import os
from pathlib import Path


def _yaml_load(text):
    """The one shared YAML read (yaml_io.py, ruamel.yaml, C-accelerated) — see
    that module's docstring for why ruamel replaced PyYAML and hook_runtime.py
    for the parse-cost measurements.

    This module sits on a per-EVENT path, so its parse cost is paid per tool
    call / prompt, not once per CLI run. `import yaml_io` stays lazy and is a
    same-directory sibling import (harness/scripts/), so this file stays
    runnable as a standalone CLI without the hooks dir on sys.path.
    """
    import yaml_io
    return yaml_io.yaml_load(text)

_ENV_OVERRIDE = "HARNESS_REINJECT_STRATEGY"
_REL = ("data", "reinject-strategy.yaml")

# fill_ratio(): bounded tail-read, mirroring reinject_stop_context._last_goal_status —
# a transcript's usage markers live in the trailing lines, never a multi-MB slurp.
_TAIL_BYTES = 256 * 1024

# window (tokens) for a model id: the `[1m]` context-window tag (matching
# model_policy's dated-id convention, e.g. "claude-opus-4-8[1m]") -> 1,000,000;
# any other concrete id -> the standard 200,000. No family substring (opus/sonnet)
# is consulted — this is a tag check only, per the phase spec.
_WINDOW_1M = 1_000_000
_WINDOW_DEFAULT = 200_000

# The shipped default (`balanced` preset) — also the fail-open fallback so a
# broken/missing config reproduces today's behavior exactly, never a crash.
_DEFAULT_EVERY_TURNS = 5
_DEFAULT_SLIM_BUDGET_CHARS = 1100
_DEFAULT_PRESET = "balanced"

_KEYS = ("every_turns", "slim_budget_chars")


def _config_path(env) -> Path:
    raw = env.get(_ENV_OVERRIDE)
    if raw:
        return Path(raw)
    # off __file__: harness/scripts/reinject_config.py -> harness/data/reinject-strategy.yaml
    return Path(__file__).resolve().parent.parent.joinpath(*_REL)


def _load_config(env) -> dict:
    """Parse reinject-strategy.yaml. Missing/malformed/no-PyYAML/unreadable bytes
    => {} (caller falls back to the permissive default). Never raises."""
    try:
        p = _config_path(env)
        if p.is_file():
            raw = _yaml_load(p.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return raw
    except Exception:  # noqa: BLE001 — malformed config degrades to permissive
        pass
    return {}


def _int_or_none(v):
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def resolve(env=None) -> dict:
    """Return {"every_turns": int, "slim_budget_chars": int} — the resolved
    cadence + budget for the active preset (top-level per-key overrides win).

    Fail-open: a missing/corrupt file, absent PyYAML, non-mapping document, or
    an active preset name that isn't in `presets:` all degrade to the shipped
    default. Never raises."""
    env = os.environ if env is None else env
    out = {"every_turns": _DEFAULT_EVERY_TURNS, "slim_budget_chars": _DEFAULT_SLIM_BUDGET_CHARS}
    try:
        cfg = _load_config(env)
        if not cfg:
            return out

        presets = cfg.get("presets") if isinstance(cfg.get("presets"), dict) else {}
        active = cfg.get("preset") if isinstance(cfg.get("preset"), str) else _DEFAULT_PRESET
        preset_vals = presets.get(active) if isinstance(presets.get(active), dict) else {}

        for key in _KEYS:
            v = _int_or_none(preset_vals.get(key))
            if v is not None:
                out[key] = v
        # top-level per-key overrides win over the selected preset
        for key in _KEYS:
            v = _int_or_none(cfg.get(key))
            if v is not None:
                out[key] = v
    except Exception:  # noqa: BLE001 — never wedge a caller on a broken config
        return {"every_turns": _DEFAULT_EVERY_TURNS, "slim_budget_chars": _DEFAULT_SLIM_BUDGET_CHARS}
    return out


def resolve_adaptive(env=None) -> dict:
    """Return {"mode": str|None, "threshold": float|None} for the ACTIVE preset —
    a SEPARATE resolver from resolve() so resolve()'s 2-key exact-dict contract
    (every_turns/slim_budget_chars) never gains a 3rd/4th key. Only a preset that
    carries explicit `mode`/`threshold` (the opt-in `adaptive` preset) yields
    non-None fields; the shipped default `balanced` (and aggressive/lazy) carry
    neither, so this resolves to {mode: None, threshold: None} — the caller's
    signal that adaptive is OFF and the turn-count path should decide.

    Fail-open: a missing/corrupt file, absent PyYAML, non-mapping document, or an
    unknown active preset all degrade to {mode: None, threshold: None}. Never raises."""
    env = os.environ if env is None else env
    out = {"mode": None, "threshold": None}
    try:
        cfg = _load_config(env)
        if not cfg:
            return out
        presets = cfg.get("presets") if isinstance(cfg.get("presets"), dict) else {}
        active = cfg.get("preset") if isinstance(cfg.get("preset"), str) else _DEFAULT_PRESET
        preset_vals = presets.get(active) if isinstance(presets.get(active), dict) else {}
        mode = preset_vals.get("mode")
        threshold = preset_vals.get("threshold")
        out["mode"] = mode if isinstance(mode, str) else None
        if isinstance(threshold, (int, float)) and not isinstance(threshold, bool):
            out["threshold"] = float(threshold)
    except Exception:  # noqa: BLE001 - never wedge a caller on a broken config
        return {"mode": None, "threshold": None}
    return out


def _window_for(model) -> "int | None":
    """Token window for a single concrete model id: the `[1m]` tag -> 1,000,000, any
    other non-empty id -> 200,000, an empty/missing id -> None (unclassifiable — no
    model to reason about at all). Tag-based only; no hardcoded family substring.

    This is the RAW single-id classifier, kept as the final step of `_resolve_window`
    below — it has no env access, so it cannot recover a tag a caller stripped. Use
    `_resolve_window` (through `fill_ratio`) for the env-aware resolution."""
    mid = str(model or "").strip()
    if not mid:
        return None
    return _WINDOW_1M if "[1m]" in mid.lower() else _WINDOW_DEFAULT


# env var names consulted by _resolve_window (BL-250) — the SAME convention
# model_policy.classify_tier maps through, not a reinvented reader.
_ANTHROPIC_MODEL_ENV = "ANTHROPIC_MODEL"
_TIER_DEFAULT_ENV_VARS = ("ANTHROPIC_DEFAULT_OPUS_MODEL", "ANTHROPIC_DEFAULT_SONNET_MODEL")


def _has_1m_tag(mid) -> bool:
    return "[1m]" in str(mid or "").strip().lower()


def _norm_id(mid) -> str:
    """Lowercase + drop a trailing `[..]` window tag, mirroring
    model_policy._norm_id, so a transcript's untagged id and an env id compare equal."""
    s = str(mid or "").strip().lower()
    i = s.find("[")
    return s[:i].strip() if i != -1 else s


def _resolve_window(model, msg_model, env) -> int:
    """Multi-source token-window resolver behind `fill_ratio` (BL-250 fix).

    BACKGROUND: a transcript's per-message `message.model` records the id WITHOUT the
    `[1m]` tag even on a LIVE 1M-window session (CC strips it there), so classifying the
    window from the transcript id alone under-detects a real 1M session as 200k and
    over-estimates fill ~5x. The authoritative TAGGED source is the environment: CC sets
    `ANTHROPIC_MODEL` to the live session id (confirmed to carry `[1m]` on a 1M session),
    and a `/model` switch to a mapped tier is reflected in `ANTHROPIC_DEFAULT_OPUS_MODEL`
    / `ANTHROPIC_DEFAULT_SONNET_MODEL`. Env is PREFERRED-IF-SET, not required — every step
    below degrades gracefully when its input is absent.

    Resolution order (fail-open; never guesses 1M on ambiguity):
      a. `model` — an explicit caller override — IF it carries `[1m]` -> 1,000,000.
      b. `env[ANTHROPIC_MODEL]` — the live session id: tagged -> 1,000,000; a concrete
         untagged id -> 200,000 (CC itself would have tagged it were the window 1M).
      c. `msg_model` (the transcript's untagged `message.model`) matched against
         `env[ANTHROPIC_DEFAULT_OPUS_MODEL]` / `env[ANTHROPIC_DEFAULT_SONNET_MODEL]` — a
         matching env id that itself carries `[1m]` recovers the tag the transcript
         stripped (also honors a `/model` switch to a mapped tier).
      d. the raw id's own `[1m]` tag, via `_window_for(model or msg_model)`.
      e. fail-open default: 200,000 when nothing above resolves at all.

    Never raises, never returns None — unlike `_window_for`, this always yields a window
    to divide by, biased toward the SMALLER (200k) window on any ambiguity: a wrong-low
    window at worst injects slightly early, a wrong-high window would suppress a needed
    refresh (the constraint this whole fix exists to uphold)."""
    try:
        env = env if isinstance(env, dict) or env else {}

        # a. explicit caller override, tag-positive only (a bare untagged override
        # falls through to the env-aware steps below rather than assuming 200k here).
        if model and _has_1m_tag(model):
            return _WINDOW_1M

        # b. the live session id CC sets.
        am = env.get(_ANTHROPIC_MODEL_ENV) if hasattr(env, "get") else None
        if am:
            return _WINDOW_1M if _has_1m_tag(am) else _WINDOW_DEFAULT

        # c. recover the tag via a tier-default env match on the untagged transcript id.
        nid = _norm_id(msg_model)
        if nid and hasattr(env, "get"):
            for var in _TIER_DEFAULT_ENV_VARS:
                cand = env.get(var)
                if cand and _norm_id(cand) == nid and _has_1m_tag(cand):
                    return _WINDOW_1M

        # d. the raw id's own tag (covers an untagged explicit override too).
        w = _window_for(model or msg_model)
        if w is not None:
            return w

        # e. nothing resolved at all — fail open LOW, never crash, never guess 1M.
        return _WINDOW_DEFAULT
    except Exception:  # noqa: BLE001 — a resolver hiccup must not wedge fill_ratio
        return _WINDOW_DEFAULT


def _tail_read(path) -> bytes:
    with open(path, "rb") as fh:
        fh.seek(0, os.SEEK_END)
        size = fh.tell()
        fh.seek(max(0, size - _TAIL_BYTES))
        return fh.read()


def _last_usage_record(transcript_path):
    """The `message` dict of the LAST transcript record carrying `type=="assistant"`
    and a `message.usage` mapping, or None. Bounded 256KB tail-read, mirroring
    reinject_stop_context._last_goal_status; tolerates torn/partial JSON lines at
    the head of the read window (a mid-line seek cut). Never raises — any I/O or
    parse failure yields None (fail-open for the caller)."""
    chunk = _tail_read(transcript_path)
    last = None
    for line in chunk.splitlines():
        try:
            rec = json.loads(line)
        except Exception:  # noqa: BLE001 - a torn/partial tail line is non-fatal
            continue
        if (isinstance(rec, dict) and rec.get("type") == "assistant"
                and isinstance(rec.get("message"), dict)
                and isinstance(rec["message"].get("usage"), dict)):
            last = rec["message"]
    return last


def fill_ratio(transcript_path, model=None, env=None):
    """Prompt-side context fill as a fraction of the model's window, or None.

    fill = input_tokens + cache_read_input_tokens + cache_creation_input_tokens,
    read from the LAST assistant `message.usage` record in the transcript's
    trailing 256KB (mirrors reinject_stop_context's bounded tail-read pattern).
    Missing usage keys count as 0.

    window (BL-250 fix): resolved via `_resolve_window(model, msg.get("model"), env)` —
    prefers an env-carried `[1m]` tag (ANTHROPIC_MODEL, or a tier-default env match on
    the transcript's untagged id) over the transcript's own `message.model`, because CC
    records that field WITHOUT the tag even on a live 1M session. `env` defaults to
    `os.environ` (preferred-if-set — a caller passing `env={}` or a scratch dict opts
    out cleanly, same seam as model_policy's readers). See `_resolve_window`'s docstring
    for the full resolution order.

    Fail-open, NEVER raises: a missing/unreadable transcript, no transcript_path, or no
    usage record found all return None — the caller (inject_prompt_context) falls back
    to the turn-count cadence. An empty/unclassifiable model (no override AND no
    transcript model at all) also returns None — there is nothing to reason about, not
    even a guessed window. Once ANY id is present, `_resolve_window` never returns None
    (it fails open to 200k) — a wrong-low window at worst injects slightly early."""
    env = os.environ if env is None else env
    if not transcript_path:
        return None
    try:
        msg = _last_usage_record(transcript_path)
        if msg is None:
            return None
        usage = msg.get("usage") or {}
        input_tokens = usage.get("input_tokens") or 0
        cache_read = usage.get("cache_read_input_tokens") or 0
        cache_create = usage.get("cache_creation_input_tokens") or 0
        fill = int(input_tokens) + int(cache_read) + int(cache_create)
        msg_model = msg.get("model")
        if not model and not msg_model:
            return None  # nothing to classify at all — abstain, don't guess a window
        window = _resolve_window(model, msg_model, env)
        return fill / window
    except Exception:  # noqa: BLE001 - any read/parse hiccup fails open to None
        return None


def main(argv=None) -> int:
    import argparse
    import json
    ap = argparse.ArgumentParser(
        description="resolve reinject-strategy.yaml (cadence + slim-budget preset)")
    ap.add_argument("--resolved", action="store_true",
                     help="print resolve() as JSON (default action; flag kept for CLI symmetry "
                          "with output_config.py --resolved)")
    ap.parse_args(argv)
    print(json.dumps(resolve(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
