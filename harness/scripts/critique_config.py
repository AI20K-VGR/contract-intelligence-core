#!/usr/bin/env python3
"""critique_config.py — read/set the hs:critique `mode` knob in critique.yaml.

mode advisory (default) writes a human report only; mode gate ALSO writes a
machine verdict (critique-consensus.json) a stage CAN block on. Flipping mode
does NOT by itself enforce: a stage must list `critique-consensus` in its
`requires:` in stage-policy.yaml (a separate tracked, write-guarded edit). The
per-run override stays `--gate` / `--advisory` on the skill.

This writer is SURGICAL — it rewrites ONLY the `mode:` line, leaving the lenses,
loop, and verdict blocks (and every comment) byte-for-byte intact. critique.yaml
is tracked config; a change is a git-visible diff. Read path resolves the tracked
file off __file__ (never CWD); tests pass `path=` explicitly.
"""

import re
from pathlib import Path

_CRITIQUE_DEFAULT = Path(__file__).resolve().parent.parent / "data" / "critique.yaml"

VALID_MODES = {"advisory", "gate"}
_MODE_LINE = re.compile(r"(?m)^mode\s*:\s*.*$")


class CritiqueConfigError(Exception):
    """Raised when critique.yaml is malformed or a write is rejected; the message
    names the file/key so the fix is a config edit, not a debug session."""


def load_critique(path=None) -> dict:
    """Parse critique.yaml → {mode}. Missing key/file defaults to advisory; a
    non-mapping document or an out-of-enum mode raises CritiqueConfigError."""
    import yaml_io  # lazy

    p = Path(path) if path else _CRITIQUE_DEFAULT
    try:
        raw = yaml_io.safe_load(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raw = {}
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise CritiqueConfigError(
            "critique config %s is malformed — expected a YAML mapping" % p)
    mode = raw.get("mode", "advisory")
    if mode not in VALID_MODES:
        raise CritiqueConfigError(
            "key `mode` in %s must be one of %s (got %r)"
            % (p, sorted(VALID_MODES), mode))
    return {"mode": mode}


def save_critique(updates: dict, path=None) -> Path:
    """Set `mode` in critique.yaml, surgically. Accepts ONLY the `mode` key
    (advisory|gate); an unknown key / bad value raises CritiqueConfigError BEFORE
    any write. Everything else in the file is preserved exactly."""
    p = Path(path) if path else _CRITIQUE_DEFAULT
    unknown = set(updates) - {"mode"}
    if unknown:
        raise CritiqueConfigError(
            "unknown critique knob(s) %s — this writer sets only `mode`"
            % ", ".join(sorted(unknown)))
    if "mode" not in updates:
        return p  # nothing to do
    mode = updates["mode"]
    if mode not in VALID_MODES:
        raise CritiqueConfigError(
            "key `mode` must be one of %s (got %r)" % (sorted(VALID_MODES), mode))

    p.parent.mkdir(parents=True, exist_ok=True)
    import harness_paths
    from register_store import atomic_write, register_lock
    lock = harness_paths.bin_state_dir() / "locks" / "critique-config.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    # Lock the read-modify-write: two concurrent --mode writes would otherwise
    # lose an update (last-writer-wins on the single mode line). critique.yaml is
    # a bin-global config (ONE file shared across projects under a global bin), so
    # the lock lives under the bin-global state dir — NOT the per-project
    # state_dir() — so concurrent writes to the one config serialize process-wide.
    with register_lock(lock):
        text = p.read_text(encoding="utf-8")
        new_line = "mode: %s" % mode
        if _MODE_LINE.search(text):
            text = _MODE_LINE.sub(new_line, text, count=1)
        else:
            # no mode line: insert after the leading comment/blank block
            lines = text.splitlines(keepends=True)
            i = 0
            while i < len(lines) and (lines[i].lstrip().startswith("#")
                                      or not lines[i].strip()):
                i += 1
            lines.insert(i, new_line + "\n")
            text = "".join(lines)
        atomic_write(p, text)
    return p


def main(argv=None) -> int:
    import argparse
    import sys
    ap = argparse.ArgumentParser(
        description="read/set critique.yaml mode (advisory|gate)")
    ap.add_argument("--file", default=None,
                    help="explicit critique.yaml path (default: shipped tracked file)")
    ap.add_argument("--set", dest="sets", action="append", metavar="KEY=VALUE",
                    help="write mode=<advisory|gate>")
    args = ap.parse_args(argv)
    path = args.file
    if not args.sets:
        import json
        print(json.dumps(load_critique(path=path), indent=2, ensure_ascii=False))
        return 0
    updates = {}
    for pair in args.sets:
        if "=" not in pair:
            sys.stderr.write("--set expects KEY=VALUE, got %r\n" % pair)
            return 2
        key, value = pair.split("=", 1)
        updates[key] = value.strip()
    try:
        p = save_critique(updates, path=path)
    except CritiqueConfigError as e:
        sys.stderr.write("CritiqueConfigError: %s\n" % e)
        return 1
    print("saved critique → %s" % p)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
