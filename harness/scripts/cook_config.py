#!/usr/bin/env python3
"""cook_config.py — read/write cook.yaml execution knobs (human-edited config).

cook.parallel opts into multi-agent execution for independent phases;
cook.parallel_max caps concurrency. The full override chain stays
`--parallel` flag > HARNESS_COOK_PARALLEL env > cook.yaml > default — this writer
only persists the file layer so hs:setup can offer it as a validated choice
instead of a hand edit. Parallelism never weakens a gate (see hs:cook's
parallel-execution reference).

DELIBERATELY no env override in THIS writer: cook.yaml is tracked config, so a
change is a git-visible diff. The read path resolves the tracked file off
__file__ (never CWD); tests pass `path=` explicitly.
"""

from pathlib import Path

_COOK_DEFAULT = Path(__file__).resolve().parent.parent / "data" / "cook.yaml"

_KNOBS = ("parallel", "parallel_max")


class CookConfigError(Exception):
    """Raised when cook.yaml is malformed or a write is rejected. The message
    names the file/key so the fix is a config edit, not a debug session."""


def load_cook(path=None) -> dict:
    """Parse cook.yaml → {parallel: bool, parallel_max: int}.

    Missing keys take the shipped defaults (parallel False, parallel_max 4). A
    missing file is treated as all-defaults so a fresh tree reads cleanly; a
    non-mapping document or a bad type raises CookConfigError.
    """
    import yaml_io  # lazy: keep importable without PyYAML until used

    p = Path(path) if path else _COOK_DEFAULT
    try:
        raw = yaml_io.safe_load(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raw = {}
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise CookConfigError(
            "cook config %s is malformed — expected a YAML mapping with keys "
            "`parallel`, `parallel_max`" % p)

    parallel = raw.get("parallel", False)
    if not isinstance(parallel, bool):
        raise CookConfigError(
            "key `parallel` in %s must be true or false (got %r)" % (p, parallel))

    pmax = raw.get("parallel_max", 4)
    if not isinstance(pmax, int) or isinstance(pmax, bool) or pmax <= 0:
        raise CookConfigError(
            "key `parallel_max` in %s must be a positive integer (got %r)"
            % (p, pmax))
    return {"parallel": parallel, "parallel_max": pmax}


def _preserved_header(path: Path) -> str:
    import config_io
    return config_io.leading_comment_block(
        path, "# cook.yaml — cook execution knobs (human-edited config).\n")


def save_cook(updates: dict, path=None) -> Path:
    """Validate + write cook.yaml, merging ``updates`` over current values.

    Accepts ONLY `parallel` (bool) and `parallel_max` (positive int). An unknown
    key / bad type raises CookConfigError BEFORE any write, so the file stays
    canonical. The header comment block is preserved."""
    p = Path(path) if path else _COOK_DEFAULT
    current = load_cook(path=p)
    unknown = set(updates) - set(_KNOBS)
    if unknown:
        raise CookConfigError(
            "unknown cook knob(s) %s — valid: %s"
            % (", ".join(sorted(unknown)), ", ".join(_KNOBS)))
    merged = dict(current)
    merged.update(updates)

    if not isinstance(merged["parallel"], bool):
        raise CookConfigError(
            "key `parallel` must be true or false (got %r)" % merged["parallel"])
    pmax = merged["parallel_max"]
    if not isinstance(pmax, int) or isinstance(pmax, bool) or pmax <= 0:
        raise CookConfigError(
            "key `parallel_max` must be a positive integer (got %r)" % pmax)

    body = "parallel: %s\nparallel_max: %d\n" % (
        "true" if merged["parallel"] else "false", pmax)
    p.parent.mkdir(parents=True, exist_ok=True)
    from register_store import atomic_write
    atomic_write(p, _preserved_header(p) + body)
    return p


def _coerce(key: str, value: str):
    if key == "parallel":
        low = value.strip().lower()
        if low in ("true", "yes", "on", "1"):
            return True
        if low in ("false", "no", "off", "0"):
            return False
        raise CookConfigError("parallel must be true/false (got %r)" % value)
    if key == "parallel_max":
        try:
            return int(value)
        except ValueError:
            raise CookConfigError(
                "parallel_max must be an integer (got %r)" % value)
    return value


def main(argv=None) -> int:
    import argparse
    import sys
    ap = argparse.ArgumentParser(
        description="read/write cook.yaml (parallel execution knobs)")
    ap.add_argument("--file", default=None,
                    help="explicit cook.yaml path (default: shipped tracked file)")
    ap.add_argument("--set", dest="sets", action="append", metavar="KEY=VALUE",
                    help="write parallel=<bool> or parallel_max=<int>; repeatable")
    args = ap.parse_args(argv)
    path = args.file
    if not args.sets:
        import json
        print(json.dumps(load_cook(path=path), indent=2, ensure_ascii=False))
        return 0
    updates = {}
    for pair in args.sets:
        if "=" not in pair:
            sys.stderr.write("--set expects KEY=VALUE, got %r\n" % pair)
            return 2
        key, value = pair.split("=", 1)
        try:
            updates[key] = _coerce(key, value)
        except CookConfigError as e:
            sys.stderr.write("%s\n" % e)
            return 2
    try:
        p = save_cook(updates, path=path)
    except CookConfigError as e:
        sys.stderr.write("CookConfigError: %s\n" % e)
        return 1
    print("saved cook → %s" % p)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
