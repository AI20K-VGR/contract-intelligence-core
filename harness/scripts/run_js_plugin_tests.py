#!/usr/bin/env python3
"""run_js_plugin_tests.py — discover + run every Node/JS test file under
harness/plugins/hs/skills, each as its own `node <file>` subprocess.

This is the Node-side counterpart to ci.sh's `plugin-skills` (pytest) job: that
job only ever reached the Python tooling under this tree, so the ~11 real
Node/JS test suites sat completely un-executed (see
harness/tests/test_plugin_skill_test_dirs_are_gated.py, the mechanical
discovery guard that flagged them). Node has no pytest equivalent, so this is a
small standalone script rather than another test-strategy.yaml pytest profile
(that file's build_argv only ever emits `python3 -m pytest ...`).

Every discovered file is expected to be a self-contained entrypoint — running
via plain `node <file>` exits 0 on pass, non-zero on any failure. No shared
process state between files: each gets its own subprocess so one file's global
state (e.g. a registered describe/it suite) can never leak into another.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import List

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_ROOT = REPO_ROOT / "harness" / "plugins" / "hs" / "skills"

# Mirrors harness/tests/test_plugin_skill_test_dirs_are_gated.py's _JS_TEST_GLOBS
# exactly (that test imports JS_TEST_GLOBS from this module rather than keeping
# its own copy, so the two can never drift apart).
JS_TEST_GLOBS = ("*.test.js", "*.test.cjs", "test-*.js", "test_*.js")


def discover() -> List[Path]:
    """Real filesystem discovery — never a hand-typed file list."""
    found = []
    for pattern in JS_TEST_GLOBS:
        found.extend(SKILLS_ROOT.rglob(pattern))
    return sorted(set(found))


def main(argv: List[str] | None = None) -> int:
    files = discover()
    if not files:
        print(
            "run_js_plugin_tests: no JS test files discovered under "
            f"{SKILLS_ROOT} — check JS_TEST_GLOBS / the skills tree",
            file=sys.stderr,
        )
        return 1

    failures = []
    for f in files:
        rel = f.relative_to(REPO_ROOT).as_posix()
        print(f"\n=== node {rel} ===")
        result = subprocess.run(["node", str(f)], cwd=str(REPO_ROOT))
        if result.returncode != 0:
            failures.append(rel)

    print(f"\n{'=' * 70}")
    print(f"JS plugin-skills tests: {len(files) - len(failures)}/{len(files)} files passed")
    if failures:
        print("FAILED files:")
        for rel in failures:
            print(f"  - {rel}")
        print(f"{'=' * 70}")
        return 1

    print(f"{'=' * 70}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
