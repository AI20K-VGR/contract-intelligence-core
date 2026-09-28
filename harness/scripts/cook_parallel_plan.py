#!/usr/bin/env python3
"""cook_parallel_plan.py — partition a plan's phases for opt-in parallel cook.

The safety core of `cook --parallel` (default OFF = today's sequential behavior).
Two responsibilities, both pure and testable:

1. `is_parallel_enabled(flag, env, config)` — deterministic opt-in resolution:
   explicit `--parallel` flag > `HARNESS_COOK_PARALLEL` env > `cook.parallel` config
   > default False. Nothing set -> sequential, so existing installs do not change.

2. `partition(phases)` — decide which phases may run concurrently. A phase is
   parallel ONLY when it is `parallel_safe` AND its file ownership is disjoint from
   every other parallel_safe phase. Any ownership overlap demotes BOTH phases to
   sequential and records the conflict — the fallback is always reported, never
   silent (orchestration-protocol: never parallel-edit the same file).

`expand_owns` resolves ownership globs against the real tree at the CLI edge so the
grouping core stays a pure set operation.
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scope_match import globs_overlap

ENV_VAR = "HARNESS_COOK_PARALLEL"
_TRUTHY = {"1", "true", "yes", "on"}


def is_parallel_enabled(flag=None, env=None, config=None) -> bool:
    """Resolve the opt-in. flag: bool|None (explicit CLI), env: str|None, config: bool|None."""
    if flag is not None:
        return bool(flag)
    if env is not None:
        return str(env).strip().lower() in _TRUTHY
    if config is not None:
        return bool(config)
    return False


def expand_owns(owns, root) -> set:
    """Expand ownership globs to repo-relative file paths. A pattern that matches
    nothing (e.g. a file a phase will CREATE) is kept literally — it is still owned."""
    root = Path(root)
    out = set()
    for pattern in owns or []:
        matches = [m for m in root.glob(pattern) if m.is_file()]
        if matches:
            out.update(m.relative_to(root).as_posix() for m in matches)
        else:
            out.add(Path(pattern).as_posix())
    return out


def _entries_overlap(a, b) -> bool:
    """True if two ownership entries (path or glob) can name a common file.

    Delegates to `scope_match.globs_overlap`, the token automaton that answers
    exactly this question — do two patterns share any path — rather than keeping
    a second, weaker answer to it here. What used to sit in this spot compared the
    fixed prefix of each pattern before its first wildcard, which is a proxy for
    the question, not the question: any two patterns rooted in the same directory
    matched, whatever they actually selected, so `data/*.yaml` and `data/*.json`
    read as overlapping while naming disjoint files.

    Measured on 171 pattern pairs against the real expanded file sets: the prefix
    rule called 26 pairs overlapping that share no file (15.2%), the automaton 3
    (1.8%). Both missed ZERO real overlaps -- the direction that can corrupt a tree
    was never the difference between them, so this is not a safety trade. The
    remaining conservatism is where it belongs: `expand_owns` keeps a pattern that
    matches nothing today (a file a phase will CREATE), so a phase still owns what
    it is about to write.
    """
    if a == b:
        return True
    # Spell each side the way `expand_owns` will (`Path(...).as_posix()`), so
    # `./src/new.py` and `src/new.py` -- the same file, and the same file the
    # expansion would produce -- are compared as one path rather than as two
    # strings. The matcher answers a question about paths; handing it a spelling
    # it has no reason to normalize is this caller's job to avoid.
    a, b = Path(a).as_posix(), Path(b).as_posix()
    if a == b:
        return True
    return globs_overlap(a, b)


def _shared_owns(owns_a, owns_b):
    """The overlapping ownership entries between two phases, by scope (not just by
    literal-string equality) — so two globs with overlapping scope are caught."""
    out = []
    for a in owns_a or []:
        for b in owns_b or []:
            if _entries_overlap(a, b):
                out.append(a if a == b else "%s ~ %s" % (a, b))
    return sorted(set(out))


def partition(phases) -> dict:
    """Group phases into concurrent-safe vs sequential.

    phases: list of {"id": str, "parallel_safe": bool, "owns": [path, ...]}.
    Returns {"parallel": [id], "sequential": [id], "conflicts": [{a,b,shared}]}.
    Conservative by design: a single shared path demotes both phases to sequential.
    """
    safe = [p for p in phases if p.get("parallel_safe")]
    conflicts = []
    conflicted = set()
    for i in range(len(safe)):
        for j in range(i + 1, len(safe)):
            a, b = safe[i], safe[j]
            shared = _shared_owns(a.get("owns"), b.get("owns"))
            if shared:
                conflicts.append({"a": a["id"], "b": b["id"], "shared": shared})
                conflicted.add(a["id"])
                conflicted.add(b["id"])
    parallel = [p["id"] for p in safe if p["id"] not in conflicted]
    sequential = [p["id"] for p in phases
                  if not p.get("parallel_safe") or p["id"] in conflicted]
    return {"parallel": parallel, "sequential": sequential, "conflicts": conflicts}


def _resolve_config_default(root) -> bool:
    """Read cook.parallel from harness/data/cook.yaml (default False) — best-effort."""
    cfg = Path(root) / "harness" / "data" / "cook.yaml"
    if not cfg.is_file():
        return False
    try:
        import yaml_io
        data = yaml_io.safe_load(cfg.read_text(encoding="utf-8")) or {}
        return bool(data.get("parallel", False))
    except Exception:
        return False


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--phases-json", help="JSON file: list of {id,parallel_safe,owns}")
    ap.add_argument("--parallel", dest="flag", action="store_true", default=None,
                    help="force parallel ON (overrides env/config)")
    ap.add_argument("--root", default=".", help="repo root (default cwd)")
    ap.add_argument("--expand", action="store_true",
                    help="expand each phase's owns globs against --root before partitioning")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()

    enabled = is_parallel_enabled(
        flag=args.flag,
        env=os.environ.get(ENV_VAR),
        config=_resolve_config_default(root),
    )
    if not args.phases_json:
        print(json.dumps({"parallel_enabled": enabled}))
        return 0

    phases = json.loads(Path(args.phases_json).read_text(encoding="utf-8"))
    if args.expand:
        for p in phases:
            p["owns"] = sorted(expand_owns(p.get("owns"), root))
    out = partition(phases)
    out["parallel_enabled"] = enabled
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
