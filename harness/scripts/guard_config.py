#!/usr/bin/env python3
"""guard_config.py — inspect and change guard posture, with an audit trail.

Three subcommands:
  show                       resolve and print every registered guard's
                             EFFECTIVE mode (the "rà toàn bộ" view).
  set <guard> <off|warn|block>   override one guard.
  set-preset <strict|balanced|lenient|solo>   change the baseline for all guards.

Every `set`/`set-preset` does two things atomically under a best-effort lock:
rewrites guard-policy.yaml (the change is a git-visible diff) AND appends a
`guard_config_changed` audit line (actor + ts + old->new). Lowering a
safety-FLOOR guard below block is a break-glass: it is still honored, but the
operator is warned on stderr and the trace line is tagged break_glass.

This is the human-facing twin of guard_policy.py — that module RESOLVES posture;
this one CHANGES it and records who/when. Validation lives in guard_policy
(GUARD_REGISTRY / preset names / mode names) so both agree on what is legal.
"""

import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent / "hooks"))

import guard_policy  # noqa: E402
import trace_log  # noqa: E402
import hook_runtime  # noqa: E402

_CATEGORY_ORDER = ("safety", "enforcement", "advisory")


def _guards_by_category():
    for cat in _CATEGORY_ORDER:
        ids = sorted(g for g, m in guard_policy.GUARD_REGISTRY.items()
                     if m["category"] == cat)
        yield cat, ids


def _preserved_header(path: Path) -> str:
    """Leading comment/blank header of the policy file, kept across a CLI write
    (shared extractor in config_io). Missing file -> a minimal self-documenting
    header naming the file."""
    import config_io
    return config_io.leading_comment_block(
        path,
        "# guard-policy.yaml — off/warn/block posture for every configurable "
        "guard.\n# Edit by hand or via guard_config.py (which also writes an "
        "audit line).\n")


def _render(header: str, preset: str, overrides: dict) -> str:
    # Quote scalar values: the mode `off` is a YAML 1.1 boolean unquoted, and
    # would round-trip back as False. Quoting keeps every value a string.
    body = ['schema_version: "1.0"', 'preset: "%s"' % preset]
    if overrides:
        body.append("overrides:")
        for gid in sorted(overrides):
            body.append('  %s: "%s"' % (gid, overrides[gid]))
    else:
        body.append("overrides: {}")
    return header + "\n".join(body) + "\n"


def _locked_update(path: Path, *, gid=None, mode=None, preset=None):
    """Atomic read-modify-write of the policy file under one lock: load the
    CURRENT file, apply the change (set a guard override, or change the preset),
    and rewrite — all inside the lock so a concurrent CLI edit cannot clobber an
    override (the load must not sit outside the lock). Returns (old, breach)."""

    def _apply():
        cfg = guard_policy.load_guard_policy(path)
        if gid is not None:
            meta = guard_policy.GUARD_REGISTRY[gid]
            if gid in cfg["overrides"]:
                old = cfg["overrides"][gid]
            else:
                base = guard_policy._PRESET_TABLE[meta["category"]][cfg["preset"]]
                if meta["floor"] == "block" and guard_policy._MODE_RANK[base] < guard_policy._MODE_RANK["block"]:
                    old = "block"
                else:
                    old = base
            overrides = dict(cfg["overrides"])
            overrides[gid] = mode
            new_preset = cfg["preset"]
            breach = guard_policy.is_floor_breach(gid, mode)
        else:
            old = cfg["preset"]
            new_preset = preset
            overrides = cfg["overrides"]
            breach = False
        # Atomic + durable write: a crash mid-truncate would otherwise leave an empty
        # file that loads as the balanced default, silently dropping overrides — and
        # a plain rename-without-fsync leaves the same empty file after power loss.
        text = _render(_preserved_header(path), new_preset, overrides)
        import artifact_io
        artifact_io.atomic_write_text(path, text)
        return old, breach

    lock = hook_runtime._state_dir() / "locks" / "guard-policy.lock"
    try:
        from register_store import register_lock
    except Exception:  # noqa: BLE001 — no lock primitive: still apply the edit
        return _apply()
    with register_lock(lock):
        return _apply()


def _trace_change(*, target: str, note: str, break_glass: bool) -> None:
    trace_log.append_event(
        "guard_config", "guard_config_changed",
        actor=hook_runtime.resolve_actor(),
        target=target,
        status="break_glass" if break_glass else "set",
        note=note + (" break_glass" if break_glass else ""))


def cmd_show(args) -> int:
    path = guard_policy.policy_path()
    try:
        cfg = guard_policy.load_guard_policy(path)
    except guard_policy.GuardPolicyError as e:
        sys.stderr.write("guard-policy invalid: %s\n" % e)
        return 2
    print("guard policy: %s" % path)
    print("preset: %s    fingerprint: %s"
          % (cfg["preset"], guard_policy.policy_fingerprint(path)))
    for cat, ids in _guards_by_category():
        print("\n[%s]" % cat)
        for gid in ids:
            mode = guard_policy.resolve_mode(gid, path)
            src = "override" if gid in cfg["overrides"] else "preset"
            floor = "  (floor:block)" if guard_policy.GUARD_REGISTRY[gid]["floor"] else ""
            print("  %-26s %-5s  [%s]%s" % (gid, mode, src, floor))
    return 0


def cmd_set(args) -> int:
    gid, mode = args.guard, args.mode
    if gid not in guard_policy.GUARD_REGISTRY:
        sys.stderr.write(
            "unknown guard %r — run `guard_config.py show` for valid ids\n" % gid)
        return 2
    if mode not in guard_policy._MODES:
        sys.stderr.write(
            "mode must be one of %s (got %r)\n" % (", ".join(guard_policy._MODES), mode))
        return 2
    path = guard_policy.policy_path()
    try:
        guard_policy.load_guard_policy(path)  # validate before mutating
    except guard_policy.GuardPolicyError as e:
        sys.stderr.write("guard-policy invalid: %s\n" % e)
        return 2

    old, breach = _locked_update(path, gid=gid, mode=mode)
    _trace_change(target=gid, note="%s: %s -> %s" % (gid, old, mode),
                  break_glass=breach)
    if breach:
        sys.stderr.write(
            "WARNING break-glass: %s is a safety-floor guard; setting it to "
            "%r removes a host/secret/history protection. Logged.\n" % (gid, mode))
    print("set %s = %s (was %s)" % (gid, mode, old))
    return 0


def cmd_set_preset(args) -> int:
    preset = args.preset
    if preset not in guard_policy._PRESETS:
        sys.stderr.write(
            "preset must be one of %s (got %r)\n"
            % (", ".join(guard_policy._PRESETS), preset))
        return 2
    path = guard_policy.policy_path()
    try:
        guard_policy.load_guard_policy(path)  # validate before mutating
    except guard_policy.GuardPolicyError as e:
        sys.stderr.write("guard-policy invalid: %s\n" % e)
        return 2
    old, _ = _locked_update(path, preset=preset)
    _trace_change(target="preset", note="preset: %s -> %s" % (old, preset),
                  break_glass=False)
    print("set preset = %s (was %s)" % (preset, old))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="guard_config.py", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show", help="print every guard's effective mode")
    s = sub.add_parser("set", help="override one guard's mode")
    s.add_argument("guard")
    s.add_argument("mode")
    sp = sub.add_parser("set-preset", help="change the baseline preset")
    sp.add_argument("preset")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "show":
        return cmd_show(args)
    if args.cmd == "set":
        return cmd_set(args)
    if args.cmd == "set-preset":
        return cmd_set_preset(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
