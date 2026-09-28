#!/usr/bin/env python3
"""orchestration_config.py — read the shared orchestration.yaml.

orchestration.yaml holds the cross-cutting fan-out enforcement caps (group_cap /
batch_consolidate / early_write). This module is the single reader for it AND the
single home of the group-cap clamp formula (DRY): the skill-local
plan_orchestration.py never imports this module — it may sit in a different tree
after install — so a skill resolves a concrete cap through the `--group-cap` CLI
and passes the resolved integer down.

Fail-open non-breaking: an ABSENT file resolves to the shipped default (a fresh
install behaves exactly as before). A PRESENT but malformed file (non-mapping)
raises OrchestrationConfigError so the CLI can point at the typo — but any gate
consulting this policy wraps the call in try/except and treats a raise as a no-op.

Read path resolves the tracked file off __file__ (never CWD); tests pass `path=`.
"""

from pathlib import Path

_ORCHESTRATION_DEFAULT = (
    Path(__file__).resolve().parent.parent / "data" / "orchestration.yaml")


class OrchestrationConfigError(Exception):
    """Raised when orchestration.yaml is malformed; the message names the file so
    the fix is a config edit, not a debug session. Gates wrap this as a no-op."""


def _default() -> dict:
    """The shipped default returned when the file is absent. Fresh dict per call
    so callers can never mutate a shared default."""
    return {
        "group_cap": {"base": 8, "ceiling": 10, "floor": 1},
        "batch_consolidate": {"size": 8},
        "early_write": {"required": True},
    }


def load_orchestration(path=None) -> dict:
    """Parse orchestration.yaml. Missing file -> the shipped default (no raise). A
    non-mapping document raises OrchestrationConfigError. A present-but-partial
    document is filled from the default per top-level block, so every reader finds
    every knob."""
    import yaml_io  # lazy

    p = Path(path) if path else _ORCHESTRATION_DEFAULT
    try:
        raw = yaml_io.safe_load(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _default()
    if raw is None:
        return _default()
    if not isinstance(raw, dict):
        raise OrchestrationConfigError(
            "orchestration config %s is malformed — expected a YAML mapping" % p)
    merged = _default()
    for block in ("group_cap", "batch_consolidate", "early_write"):
        if isinstance(raw.get(block), dict):
            merged[block].update(raw[block])
    return merged


def group_cap(distinct_concerns, cfg=None) -> int:
    """Resolve the wave-2 spawn cap: clamp(min(base, distinct_concerns), floor,
    ceiling). The ONE place this formula lives — callers pass the resolved int
    down rather than re-deriving it. `cfg` defaults to the loaded config."""
    if cfg is None:
        cfg = load_orchestration()
    gc = cfg.get("group_cap") or {}
    base = int(gc.get("base", 8))
    ceiling = int(gc.get("ceiling", 10))
    floor = int(gc.get("floor", 1))
    try:
        concerns = int(distinct_concerns)
    except (TypeError, ValueError):
        concerns = 0
    return max(floor, min(min(base, concerns), ceiling))


def main(argv=None) -> int:
    import argparse
    import json

    ap = argparse.ArgumentParser(
        description="read the shared orchestration.yaml (cross-cutting fan-out "
                    "enforcement caps)")
    ap.add_argument("--file", default=None,
                    help="explicit orchestration.yaml path (default: shipped file)")
    ap.add_argument("--show", action="store_true",
                    help="print the resolved config as JSON")
    ap.add_argument("--group-cap", dest="group_cap", type=int, metavar="CONCERNS",
                    help="resolve the group cap for CONCERNS distinct concerns and "
                         "print the single integer (skills pass it to "
                         "plan_orchestration.py --group-cap)")
    args = ap.parse_args(argv)
    cfg = load_orchestration(path=args.file)
    if args.group_cap is not None:
        print(group_cap(args.group_cap, cfg=cfg))
        return 0
    if args.show:
        print(json.dumps(cfg, indent=2, ensure_ascii=False))
        return 0
    print(json.dumps(cfg, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
