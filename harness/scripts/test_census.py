#!/usr/bin/env python3
"""test_census.py — count this repo's tests through declared roots, never the whole tree.

A tree-wide `find . -name 'test_*.py'` here answers a different question than the one
anyone means. It once overcounted by ~2.9x and the number reached a plan as a denominator.
The contaminants are legitimate files that are simply not this repo's tests: a
mutation-testing working copy of the whole tree (since deleted, which is exactly why the
figures below are ratios rather than the counts they were measured as), and a vendored
research harness under docs/research/ carrying its own suite.

Excluding `mutants/` is the obvious fix and it is the wrong SHAPE of fix — it still
overcounts by roughly 1.5x, and a deny-list is only ever as complete as the last person's
memory of what to add. The allow-list is the durable form: the suite roots this repo
already declares in `harness/data/test-strategy.yaml` and runs as separate CI cells, which
cannot silently gain a member. The count is deliberately not written here — it was "three"
for as long as the constant was missing a fourth suite, and a prose number is exactly what
nobody re-checks.

Every reported number carries its roots. A bare count is what let the inflated figure read
as authoritative on the page — `counting-discipline.md` states the rule ("an absence claim is
only as strong as the scope scanned; put the scope in the sentence"); this module makes it
impossible to state one without it.

Files and callables are reported separately, never interchangeably: they are different
denominators and the original error mixed them.

    python3 harness/scripts/test_census.py [--root .] [--json]
"""

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Dict, List, Sequence

# The suites this repo declares, mirroring `harness/data/test-strategy.yaml` — the SSOT CI
# reads to build its cells. An allow-list cannot gain a silent member, which was the reason
# for choosing one; what it CAN do is lose one, and that is what happened: the plugin-skills
# suite ran as its own CI cell for the whole time this tuple named three roots, so its 12
# files were invisible to every count taken through here.
#
# `test_the_roots_match_the_suites_the_strategy_file_declares` now reads that YAML and fails
# on any suite missing here, so the next addition cannot go unnoticed the same way. Keep the
# tuple explicit rather than deriving it: a literal is reviewable in a diff, and deriving it
# would make the gate compare the file to itself.
CENSUS_ROOTS = ("harness/plugins/hs/skills", "harness/tests",
                "orchestrator/tests", "release/tests", "rops/tests")


def census_roots() -> Sequence[str]:
    return CENSUS_ROOTS


def test_files(root: Path, roots: Sequence[str]) -> List[str]:
    """Repo-relative paths of test files under `roots`.

    Matches both naming conventions (`test_*.py` and `*_test.py`) because a census that
    silently covers one is an undercount wearing the same face as a correct number.
    """
    root = Path(root)
    out = set()
    for r in roots:
        base = root / r
        if not base.is_dir():
            continue
        for pat in ("test_*.py", "*_test.py"):
            for p in base.rglob(pat):
                if "__pycache__" in p.parts:
                    continue
                out.add(p.relative_to(root).as_posix())
    return sorted(out)


def callables_in(path: Path) -> int:
    """`test_*` callables at any depth — a class-nested test counts the same as a
    module-level one. An unparseable file contributes zero rather than raising: one bad
    file must not turn a census into an exception."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, OSError):
        return 0
    return sum(1 for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
               and n.name.startswith("test_"))


def census(root: Path, roots: Sequence[str] = CENSUS_ROOTS) -> Dict:
    root = Path(root)
    files = test_files(root, roots)
    per_root = {}
    for r in roots:
        sub = [f for f in files if f.startswith(r.rstrip("/") + "/")]
        per_root[r] = {"files": len(sub),
                       "callables": sum(callables_in(root / f) for f in sub)}
    return {
        "roots": list(roots),
        "files": len(files),
        "callables": sum(v["callables"] for v in per_root.values()),
        "per_root": per_root,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=".", help="repo root (default: cwd)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    a = ap.parse_args(argv)
    res = census(Path(a.root).resolve())
    if a.json:
        print(json.dumps(res, indent=2, sort_keys=True))
        return 0
    # The roots print WITH the number, always. A count whose scope is elsewhere on the
    # page is a count the next reader will quote without it.
    print("test census over %s" % ", ".join(res["roots"]))
    for r, v in sorted(res["per_root"].items()):
        print("  %-22s %5d files  %6d callables" % (r, v["files"], v["callables"]))
    print("  %-22s %5d files  %6d callables" % ("TOTAL", res["files"], res["callables"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
