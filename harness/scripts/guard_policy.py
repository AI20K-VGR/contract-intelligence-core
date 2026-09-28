#!/usr/bin/env python3
"""guard_policy.py — one off/warn/block posture for every configurable guard.

The harness ships many gates: host-safety, secret-read, stage presence, file
ownership, protected-branch refusal, advisory nudges. Before this module each
gate decided "block or not" its own way (compliance hooks had a 3-state via
harness-hooks.yaml; CLI gates had none). That made posture impossible to tune
from one place and impossible to scale beginner -> power user.

This module is that one place. A guard resolves its mode from:
  1. an explicit per-guard `overrides:` entry, if present, ELSE
  2. the active `preset` (strict | balanced | lenient | solo) applied to the guard's
     CATEGORY (safety | enforcement | advisory), THEN
  3. a safety FLOOR clamp: a guard whose floor is `block` can never be lowered
     by a preset. Only an explicit override lowers it — that write is a
     break-glass, recorded separately by guard_config (see is_floor_breach).

WHAT IS DELIBERATELY NOT HERE (always-on correctness invariants — making any
of these warn/off would corrupt state, so they are NOT registered and have no
off/warn/block knob): input-validation grammars (claims task-id,
decision_register id), path containment (fs_guard.assert_under), every config
loader's own validation, plan_approval's role-consistency of a written
artifact, and the CI bug-class invariants. Posture tunes ENFORCEMENT, never
correctness.

Loader idiom: resolve off __file__, typed error, lazy yaml. This gate DOES
honor an env override
(HARNESS_GUARD_POLICY) so tests and ephemeral runs can point at a scratch file;
the committed default still lives next to the data dir.
"""

import hashlib
import os
import sys
import traceback
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "hooks"))
import trace_log  # noqa: E402

_POLICY_DEFAULT = Path(__file__).resolve().parent.parent / "data" / "guard-policy.yaml"

_PRESETS = ("strict", "balanced", "lenient", "solo")
_MODES = ("off", "warn", "block")
_MODE_RANK = {"off": 0, "warn": 1, "block": 2}  # higher = stricter


class GuardPolicyError(Exception):
    """Raised when guard-policy.yaml is malformed. Message names the file and
    the offending key so the fix is a config edit, not a debug session."""


# --- the registry: the single source of truth for WHICH guards are tunable ---
# category drives the preset table; floor == "block" marks a guard a preset may
# not lower (only a logged override break-glass can). A guard absent here has
# no posture knob (it is a correctness invariant — see module docstring).
_SAFETY = {"category": "safety", "floor": "block"}
_ENFORCE = {"category": "enforcement", "floor": None}
_ADVISORY = {"category": "advisory", "floor": None}

GUARD_REGISTRY = {
    # safety FLOOR — most dangerous; stays blocking under every preset.
    "bash_safety_guard": _SAFETY,
    "privacy_read_guard": _SAFETY,
    "write_guard": _SAFETY,            # also keeps its own write-guard.yaml switch
    "protected_ref_force_push": _SAFETY,
    "merge_gate": _SAFETY,
    # enforcement — the SDLC posture; relaxes to warn only under lenient.
    "gate_stage": _ENFORCE,
    "standards_strict_gate": _ENFORCE,
    "protected_ref_commit": _ENFORCE,
    "test_policy_dod": _ENFORCE,       # DoD-by-change-class; block strict/balanced, warn lenient
    # advisory — informational reports; warn by default, silent under lenient.
    # (No member registered right now; the category + preset column stay so a
    # future informational guard can join without re-wiring the preset table.)
    # nudges are NOT a guard-policy category — their on/off lives on the
    # harness-hooks.yaml plane (hook_enabled plane-1), the single nudge surface.
}

# category x preset -> baseline mode. Floor guards already block under every
# column (the clamp in resolve_mode is belt-and-suspenders should this change).
# `solo` is the single-person posture: it keeps safety AND enforcement at block
# (so every safety floor stays enforcing) and only
# silences advisory noise. Solo's human-side no-friction is achieved at
# the stage-policy / team / protected-branches layer — NOT by relaxing any
# enforcement guard here.
_PRESET_TABLE = {
    "safety":      {"strict": "block", "balanced": "block", "lenient": "block", "solo": "block"},
    "enforcement": {"strict": "block", "balanced": "block", "lenient": "warn",  "solo": "block"},
    "advisory":    {"strict": "warn",  "balanced": "warn",  "lenient": "off",   "solo": "off"},
}


def _policy_path(path=None) -> Path:
    if path is not None:
        return Path(path)
    raw = os.environ.get("HARNESS_GUARD_POLICY")
    return Path(raw) if raw else _POLICY_DEFAULT


def policy_path(path=None) -> Path:
    """The resolved policy file path (explicit arg > HARNESS_GUARD_POLICY >
    shipped default). Public so guard_config edits the same file gate reads."""
    return _policy_path(path)


# path -> (mtime_ns, size, parsed). One entry per path, so a process that reloads
# the same file repeatedly cannot grow this without bound.
#
# WHY A STAMP AND NOT JUST THE PATH: every guarded event resolves at least two
# registered gates and each resolve re-parsed the whole file — measured 0.49 ms a
# call, about 1 ms per Bash event spent re-deriving a value that had not changed.
# Keying on the path ALONE is the trap: a human edits this policy during an
# incident and a long-lived process keeps gating on what it read at startup. A
# stat costs a couple of microseconds against a 490 microsecond parse, so the
# freshness check is close to free and there is no reason to skip it.
#
# mtime_NS, not mtime: whole-second resolution cannot tell two writes inside one
# second apart, and a same-second edit is exactly what a person produces while
# fixing something in a hurry. Same reason the size is in the key — an edit that
# keeps the length would otherwise slip through a size-only check.
_POLICY_CACHE = {}


def load_guard_policy(path=None) -> dict:
    """Parse guard-policy.yaml → {schema_version, preset, overrides}.

    A MISSING file is not fatal — it degrades to the safe `balanced` baseline
    (safety + enforcement still block; advisory warns), because a harness
    with no policy file should still gate. A PRESENT-but-malformed file (bad
    preset, bad override value, unknown guard id) raises GuardPolicyError: a
    config a human wrote but typo'd must fail loudly, not silently mis-gate.

    Memoised per process against the file's stamp — see _POLICY_CACHE. Only a
    successful parse is stored, so a malformed file raises every time rather than
    caching a failure, and a returned mapping is a copy: a caller that mutates its
    result cannot reach back into the cache and change what the next gate reads.
    """
    import copy

    p = _policy_path(path)
    try:
        st = p.stat()
        stamp = (st.st_mtime_ns, st.st_size)
    except OSError:
        stamp = None            # missing/unreadable: never cached, always re-checked
    if stamp is not None:
        hit = _POLICY_CACHE.get(str(p))
        if hit is not None and hit[0] == stamp:
            return copy.deepcopy(hit[1])

    import yaml_io  # lazy: keep importable without PyYAML until actually used

    try:
        text = p.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {"schema_version": "1.0", "preset": "balanced", "overrides": {}}

    try:
        raw = yaml_io.safe_load(text)
    except yaml_io.YAMLError as e:
        raise GuardPolicyError("guard policy %s is not valid YAML: %s" % (p, e))
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise GuardPolicyError(
            "guard policy %s is malformed — expected a YAML mapping with keys "
            "`preset` and optional `overrides`" % p)

    preset = raw.get("preset", "balanced")
    if preset not in _PRESETS:
        raise GuardPolicyError(
            "key `preset` in %s must be one of %s (got %r)"
            % (p, ", ".join(_PRESETS), preset))

    overrides_raw = raw.get("overrides") or {}
    if not isinstance(overrides_raw, dict):
        raise GuardPolicyError(
            "key `overrides` in %s must be a mapping of guard-id -> "
            "off|warn|block" % p)
    overrides = {}
    for gid, mode in overrides_raw.items():
        if gid not in GUARD_REGISTRY:
            raise GuardPolicyError(
                "unknown guard id %r in `overrides` of %s — run "
                "`guard_config.py show` for the valid ids" % (gid, p))
        if mode not in _MODES:
            raise GuardPolicyError(
                "override for %r in %s must be one of %s (got %r)"
                % (gid, p, ", ".join(_MODES), mode))
        overrides[gid] = mode

    parsed = {
        "schema_version": str(raw.get("schema_version", "1.0")),
        "preset": preset,
        "overrides": overrides,
    }
    # Stored only on the success path, and only when the file could be stat'd —
    # a raise above must stay a raise on the next call, never a cached verdict.
    if stamp is not None:
        _POLICY_CACHE[str(p)] = (stamp, copy.deepcopy(parsed))
    return parsed


def _meta(guard_id: str) -> dict:
    meta = GUARD_REGISTRY.get(guard_id)
    if meta is None:
        raise GuardPolicyError(
            "unknown guard id %r — not in GUARD_REGISTRY (it may be an "
            "always-on correctness invariant with no posture knob)" % guard_id)
    return meta


def resolve_mode(guard_id, path=None) -> str:
    """Effective mode for `guard_id`: "off" | "warn" | "block".

    override (if any) wins; else the preset baseline for the guard's category;
    then a floor clamp raises a floor guard back to block when no override
    lowered it. An unknown guard id raises GuardPolicyError.
    """
    meta = _meta(guard_id)
    cfg = load_guard_policy(path)
    if guard_id in cfg["overrides"]:
        return cfg["overrides"][guard_id]  # explicit; honored (break-glass logged at write)
    base = _PRESET_TABLE[meta["category"]][cfg["preset"]]
    if meta["floor"] == "block" and _MODE_RANK[base] < _MODE_RANK["block"]:
        return "block"
    return base


def is_floor_breach(guard_id, mode) -> bool:
    """True when setting `guard_id` to `mode` lowers a safety-floor guard below
    block — i.e. this write is a break-glass that must be logged."""
    return _meta(guard_id)["floor"] == "block" and _MODE_RANK[mode] < _MODE_RANK["block"]


def policy_fingerprint(path=None) -> str:
    """`sha256:<12 hex>` of the policy file bytes — load-time provenance so a
    hand edit is visible in the trace. Missing file -> `sha256:absent`."""
    p = _policy_path(path)
    try:
        digest = hashlib.sha256(p.read_bytes()).hexdigest()[:12]
    except FileNotFoundError:
        return "sha256:absent"
    return "sha256:" + digest


# --- gate(): the DRY adapter every CLI/transport gate funnels its reason through ---

_emitted_loaded = False  # once-per-process guard for guard_policy_loaded
_downgraded_emitted = set()  # once-per-guard_id guard for guard_downgraded


def _reset_emit_state() -> None:
    """Test seam: re-arm the once-per-process loaded-fingerprint emit."""
    global _emitted_loaded
    _emitted_loaded = False
    _downgraded_emitted.clear()


def _emit_loaded_once(hook, actor, session) -> None:
    global _emitted_loaded
    if _emitted_loaded:
        return
    _emitted_loaded = True
    trace_log.append_event(hook, "guard_policy_loaded", actor=actor,
                           session=session, note=policy_fingerprint())


def _emit_downgraded_once(guard_id, mode, hook, actor, session) -> None:
    """Trace, once per guard_id, that an ENFORCEMENT guard with a would-be block
    resolved BELOW block under the active preset. This is NOT a floor breach
    (is_floor_breach only fires for floor=block guards) — it is break-glass
    PARITY visibility: the audit should show when a real gate was downgraded."""
    if guard_id in _downgraded_emitted:
        return
    _downgraded_emitted.add(guard_id)
    trace_log.append_event(
        hook, "guard_downgraded", actor=actor, session=session, target=guard_id,
        status=mode, note="enforcement guard %r resolved to %r (< block) under "
        "the active preset — a would-be block was downgraded" % (guard_id, mode))


def gate(guard_id, reason, *, hook, actor=None, session=None):
    """Funnel a computed block-reason through the guard's resolved mode.

    `reason` is the string a gate would block with (None = nothing to gate).
    Returns the reason to BLOCK on (mode block), or None to CONTINUE (mode warn
    -> stderr `[advisory] …`; mode off -> silent). Every branch appends one
    audit line (guard_block | guard_warn | guard_skip). Fail-closed: if the
    policy cannot be resolved, treat as block.

    The policy fingerprint is recorded on the first consult of the process even
    when nothing is gated (reason is None), so an all-pass session still leaves
    provenance of WHICH policy was in effect.
    """
    _emit_loaded_once(hook, actor, session)
    if reason is None:
        return None
    try:
        mode = resolve_mode(guard_id)
    except Exception as e:  # noqa: BLE001 — ANY resolve failure fails closed
        # Not just GuardPolicyError: an unexpected error (corrupt preset table,
        # an unforeseen KeyError, a bad cast) must still BLOCK, never crash the
        # hook into a fail-open. A broken policy gates.
        _tb_tail = traceback.format_exc().splitlines()[-1]
        trace_log.append_event(hook, "guard_policy_error", actor=actor,
                               session=session, target=guard_id,
                               note="%s | %s" % (str(e)[:500], _tb_tail))
        mode = "block"  # fail-closed: a broken policy still gates

    if mode != "block" and GUARD_REGISTRY.get(guard_id, {}).get("category") == "enforcement":
        _emit_downgraded_once(guard_id, mode, hook, actor, session)

    if mode != "block" and is_floor_breach(guard_id, mode):
        # A safety-floor guard resolved BELOW its floor: a hand-edited `overrides:`
        # block bypasses guard_config's break_glass log, so surface the breach at
        # gate time — it must be auditable at runtime, not only in the policy
        # fingerprint. Trace-only; the resolved mode is left as the operator set it.
        trace_log.append_event(hook, "guard_floor_breach", actor=actor,
                               session=session, target=guard_id, status=mode,
                               note="safety-floor guard resolved to %s (floor breached)"
                                    % mode)

    if mode == "block":
        trace_log.append_event(hook, "guard_block", actor=actor, session=session,
                               target=guard_id, status="block", note=reason)
        return reason
    if mode == "warn":
        trace_log.append_event(hook, "guard_warn", actor=actor, session=session,
                               target=guard_id, status="warn", note=reason)
        sys.stderr.write("[advisory] %s\n" % reason)
        return None
    # off
    trace_log.append_event(hook, "guard_skip", actor=actor, session=session,
                           target=guard_id, status="off", note=reason)
    return None
