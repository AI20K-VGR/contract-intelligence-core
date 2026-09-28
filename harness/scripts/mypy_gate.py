#!/usr/bin/env python3
"""mypy_gate.py — strict-per-file mypy baseline (ratchet) gate for harness/.

Why this exists instead of a bare `mypy harness/`: no directory under harness/
carries `__init__.py` (code-standards §1 — package-con import TƯƠNG ĐỐI, by
design) and 56/128 skill directories use a hyphen in their name (e.g.
`ai-artist`, `ui-ux`) — not a valid Python identifier component. mypy's
module-name inference walks up looking for a package root and, hitting either
gap, falls back to the bare filename as the module name. With 11 duplicate
basenames across harness/ (`core.py`, `search.py`, `generate.py`, ...) a
single whole-tree invocation hits "Duplicate module named" / "Source file
found twice" and refuses to check ANYTHING past the first collision — this is
not a flake, it reproduces on every run (see the two files this docstring's
author diffed by hand: harness/plugins/hs/skills/ui-ux/scripts/core.py vs
harness/plugins/hs/skills/ai-artist/scripts/core.py).

The fix is to never let two same-basename files share one mypy invocation.
This module discovers every harness/**/*.py file, groups them by their
immediate parent directory (duplicates only ever occur ACROSS directories,
never within one — verified empirically over the current tree), and runs one
`mypy --follow-imports=skip` call per group. `--follow-imports=skip` also
matters on its own: it stops mypy from walking into a same-named module
imported by a DIFFERENT explicitly-checked file's dependency graph, which
would reintroduce the collision one layer down.

Ratchet baseline (the enforced gate): a JSON snapshot
(harness/data/mypy-baseline.json) records the mypy error COUNT per file at
the moment the gate went live. A file absent from the baseline must have
ZERO errors — introducing a NEW error in a previously-clean file is a
regression, not "one of the pre-existing 440". A file present in the
baseline must not gain MORE errors than its frozen count — the baseline can
only shrink (by hand, via --update-baseline, a reviewable git diff), never
grow silently. This protects the ~87% of the tree that is already clean
today and lets the ~13% with pre-existing debt be paid down file by file
without a "clean everything then flip the switch" all-or-nothing gate that
never ships.

Usage:
    python3 harness/scripts/mypy_gate.py                 # gate: exit 0 pass, 1 regression, 2 mypy/tooling error
    python3 harness/scripts/mypy_gate.py --update-baseline  # ratchet: overwrite the baseline with today's counts
    python3 harness/scripts/mypy_gate.py --paths a.py b.py  # scope to specific files (fast local loop)
"""

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent
_DEFAULT_BASELINE = _HERE.parent / "data" / "mypy-baseline.json"
_DEFAULT_SCAN_ROOT = _HERE.parent  # harness/

# Directories that are never source-of-truth code to gate: stashed/disabled
# skill copies (co-present with a live counterpart, would double-count) and
# any future __pycache__/build noise.
_EXCLUDE_DIR_PARTS = {"disabled-skills", "__pycache__", ".mypy_cache"}

_MYPY_ARGS = ["--ignore-missing-imports", "--follow-imports=skip", "--show-error-codes",
              "--no-error-summary"]


def search_path_dirs() -> List[Path]:
    """Where the checker looks for OUR modules, mirroring what conftest.py puts
    on sys.path for pytest.

    harness/scripts is not a package and nothing installs it, so `import yaml_io`
    resolves at runtime only because conftest inserts that directory. mypy never
    loads conftest, so the same line read as import-not-found and the file failed
    the ratchet for a problem that does not exist when the test actually runs.
    --ignore-missing-imports does not cover it: that flag silences THIRD-PARTY
    stubs, and a module we ship is not one.
    """
    return [_HERE.parent / "scripts", _HERE.parent / "hooks"]

# `path:line: error: message  [code]` — the one line shape we count. Notes
# ("note: See https://...") and the trailing "Found N errors" summary line
# are deliberately NOT matched; --no-error-summary already suppresses the
# latter but the regex stays defensive against a future flag change.
_ERROR_LINE_RE = re.compile(r"^(?P<file>[^:]+\.py):\d+: error: ")


class MypyDidNotRun(RuntimeError):
    """mypy exited outside 0/1, so its silence proves nothing about the code."""


def discover_files(root: Path = _DEFAULT_SCAN_ROOT) -> List[Path]:
    """Every harness/**/*.py file, minus stashed/build noise."""
    out = []
    for p in sorted(root.rglob("*.py")):
        if any(part in _EXCLUDE_DIR_PARTS for part in p.parts):
            continue
        out.append(p)
    return out


def group_by_dir(files: Iterable[Path]) -> Dict[Path, List[Path]]:
    """Group files by immediate parent directory — the unit that never
    contains an internal basename collision, so one mypy call per group
    never trips the whole-tree duplicate-module wall."""
    groups: Dict[Path, List[Path]] = defaultdict(list)
    for f in files:
        groups[f.parent].append(f)
    return groups


def parse_mypy_errors(output: str) -> Dict[str, int]:
    """Count `error:` lines per file path, exactly as mypy printed them
    (relative-to-cwd, matching what the caller passed on argv)."""
    counts: Dict[str, int] = defaultdict(int)
    for line in output.splitlines():
        m = _ERROR_LINE_RE.match(line)
        if m:
            counts[m.group("file")] += 1
    return dict(counts)


def run_mypy_group(files: List[Path], *, cwd: Path = _ROOT,
                    mypy_args: Optional[List[str]] = None) -> str:
    """Run one mypy invocation over FILES (all from the same directory —
    caller's responsibility, see group_by_dir) and return combined output.

    Exit 0 and exit 1 both mean mypy RAN: 0 is clean, 1 is "found type errors", and
    the errors are parsed out of stdout. Anything else means it did not run — mypy
    uses 2 for a usage error, and a missing module or a crashed interpreter lands
    outside 0/1 too. Those raise `MypyDidNotRun`.

    Without that split the gate could not tell "no type errors" from "the checker
    never started": both produced empty output, which parsed to zero errors, which
    read as PASS. A gate that reports success when its tool is broken is worse than
    no gate, because it also silences the person who would have noticed.
    """
    if not files:
        return ""
    args = mypy_args if mypy_args is not None else _MYPY_ARGS
    rel = [str(f.resolve().relative_to(cwd)) if f.is_absolute() else str(f) for f in files]
    env = dict(os.environ)
    # An operator-set MYPYPATH is appended to, never replaced.
    parts = [str(d) for d in search_path_dirs()]
    if env.get("MYPYPATH"):
        parts.append(env["MYPYPATH"])
    env["MYPYPATH"] = os.pathsep.join(parts)
    proc = subprocess.run(
        [sys.executable, "-m", "mypy", *args, *rel],
        cwd=str(cwd), capture_output=True, text=True, env=env,
    )
    if proc.returncode not in (0, 1):
        raise MypyDidNotRun(
            "mypy exited %d (neither 0=clean nor 1=type errors) on %s\n%s"
            % (proc.returncode, ", ".join(rel[:5]), (proc.stderr or proc.stdout)[:800]))
    return proc.stdout + proc.stderr


def run_mypy_tree(files: List[Path], *, cwd: Path = _ROOT,
                   mypy_args: Optional[List[str]] = None) -> Dict[str, int]:
    """Discover-free entry: run mypy over an explicit file list, grouped by
    parent directory so no invocation sees two same-basename files."""
    counts: Dict[str, int] = {}
    for _dir, group in group_by_dir(files).items():
        out = run_mypy_group(group, cwd=cwd, mypy_args=mypy_args)
        for f, n in parse_mypy_errors(out).items():
            counts[f] = counts.get(f, 0) + n
    return counts


def load_baseline(path: Path = _DEFAULT_BASELINE) -> Dict[str, int]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return {k: int(v) for k, v in data.get("files", {}).items()}


def save_baseline(counts: Dict[str, int], path: Path = _DEFAULT_BASELINE) -> None:
    payload = {
        "_comment": (
            "Machine-written mypy ratchet baseline — regenerate ONLY via "
            "`python3 harness/scripts/mypy_gate.py --update-baseline`. A file "
            "absent here must have 0 mypy errors; a file present here must not "
            "exceed its recorded count. Shrinks over time as debt is paid down; "
            "never hand-edit a count upward."
        ),
        "files": {k: counts[k] for k in sorted(counts)},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False, sort_keys=False)
        fh.write("\n")


def compute_regressions(current: Dict[str, int], baseline: Dict[str, int]) -> List[str]:
    """Return one message per regressing file; empty list = gate passes.

    A file is a regression when its CURRENT error count exceeds what the
    baseline allows for it (0 for a file the baseline has never seen bad).
    A file that improves (current < baseline) or matches is NOT a
    regression — it is simply not yet ratcheted down (that is a deliberate
    --update-baseline action, not something the gate does on your behalf).
    """
    regressions = []
    for f, n in sorted(current.items()):
        allowed = baseline.get(f, 0)
        if n > allowed:
            if f in baseline:
                regressions.append(
                    f"{f}: {n} errors, baseline allows {allowed} (regression, +{n - allowed})"
                )
            else:
                regressions.append(f"{f}: {n} errors, not in baseline (new file, 0 allowed)")
    return regressions


def check(root: Path = _DEFAULT_SCAN_ROOT, baseline_path: Path = _DEFAULT_BASELINE,
          *, cwd: Path = _ROOT, paths: Optional[List[Path]] = None,
          mypy_args: Optional[List[str]] = None) -> Tuple[bool, Dict[str, int], List[str]]:
    files = paths if paths is not None else discover_files(root)
    current = run_mypy_tree(files, cwd=cwd, mypy_args=mypy_args)
    baseline = load_baseline(baseline_path)
    regressions = compute_regressions(current, baseline)
    return (not regressions, current, regressions)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=str(_DEFAULT_SCAN_ROOT),
                     help="directory to scan (default: harness/)")
    ap.add_argument("--baseline", default=str(_DEFAULT_BASELINE),
                     help="baseline JSON path")
    ap.add_argument("--paths", nargs="*", default=None,
                     help="scope to explicit files instead of a full discover (fast local loop)")
    ap.add_argument("--update-baseline", action="store_true",
                     help="overwrite the baseline with today's counts (ratchet action, run by hand)")
    args = ap.parse_args(argv)

    root = Path(args.root)
    baseline_path = Path(args.baseline)
    paths = [Path(p) for p in args.paths] if args.paths else None

    files = paths if paths is not None else discover_files(root)
    try:
        current = run_mypy_tree(files, cwd=_ROOT)
    except MypyDidNotRun as exc:
        # Exit 2, never 0. The docstring already promised "2 mypy/tooling error"; before
        # this, a checker that could not start produced no output, which parsed to zero
        # errors, which printed PASS.
        sys.stderr.write("mypy_gate: TOOLING ERROR — mypy did not run, so nothing was "
                         "checked.\n%s\n" % exc)
        return 2

    if args.update_baseline:
        save_baseline(current, baseline_path)
        print(f"mypy_gate: baseline updated — {len(current)} files with errors, "
              f"{sum(current.values())} total errors -> {baseline_path}")
        return 0

    baseline = load_baseline(baseline_path)
    regressions = compute_regressions(current, baseline)
    if regressions:
        print(f"mypy_gate: FAIL — {len(regressions)} regressing file(s):", file=sys.stderr)
        for r in regressions:
            print(f"  {r}", file=sys.stderr)
        return 1

    print(f"mypy_gate: PASS — {len(current)} baselined file(s) with errors, "
          f"{sum(current.values())} total errors, 0 regressions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
