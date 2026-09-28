#!/usr/bin/env python3
"""affected_tests.py — pick the test files a change can break (import-graph reverse-BFS).

A focused subset beats re-running the whole suite on every small edit. Given the changed
files (explicit, or computed from a git ref), this builds the import graph over the repo's
Python files, walks it in REVERSE (who imports whom, transitively), and prints the test
files that depend — directly or through a chain — on anything that changed.

    affected_tests.py --changed src/foo.py src/bar.py
    affected_tests.py --base main                     # changed = git diff --name-only main...HEAD
    affected_tests.py --base HEAD~1 --pytest          # emit a ready-to-run pytest command

Resolution matches the harness's flat-import convention: `import hook_runtime` resolves to
the file whose stem is `hook_runtime` (modules reached via sys.path). It is a SUPERSET
selector — when in doubt it includes a test; it never claims a focused run replaces the
full suite before merge. A changed file that is itself a test is always included.

LIMITS (run the full suite before merge): it follows the IMPORT graph only, so a test
reaching the changed code ONLY via a conftest fixture or a subprocess call (no `import`)
is not captured. Same-basename modules share a stem, so an importer of one links to both
(over-, not under-selection — the safe direction).

Exit: 0 (prints selected tests, possibly none); 2 = usage error (incl. a --base git can't diff).
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "state",
               ".tox", ".mypy_cache", "build", "dist"}

# Dynamic loads carry the module name as a STRING a plain `import X` parser misses —
# the harness loads its hooks this way, so the test→hook edge lives here.
_DYNAMIC_RE = re.compile(
    r"(?:spec_from_file_location|import_module|__import__)\(\s*[\"']([\w.]+)[\"']")


def parse_imports(text: str) -> set:
    """Top-level module names imported by `text` (first dotted segment), including
    string names passed to dynamic loaders. Relative imports (`from . import x`)
    are skipped — they are not stem-resolvable."""
    mods = set()
    for m in _DYNAMIC_RE.finditer(text):
        mods.add(m.group(1).split(".")[0])
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("import "):
            for part in line[len("import "):].split(","):
                tok = part.strip().split()  # 'x as y' -> ['x','as','y']
                if tok:
                    head = tok[0].split(".")[0]
                    if head:
                        mods.add(head)
        elif line.startswith("from "):
            rest = line[len("from "):]
            if rest.startswith("."):
                continue  # relative import — intra-package, not stem-resolvable
            head = rest.split()[0].split(".")[0] if rest.split() else ""
            if head:
                mods.add(head)
    return mods


def build_stem_index(paths) -> dict:
    """{module_stem: [paths]} — a bare `import <stem>` can resolve to any of these."""
    index = {}
    for p in paths:
        stem = os.path.splitext(os.path.basename(p))[0]
        index.setdefault(stem, []).append(p)
    return index


def build_reverse_deps(paths, read, stem_index) -> dict:
    """{target_path: {paths that import it}} — the edge a reverse-BFS walks."""
    reverse = {}
    for f in paths:
        try:
            mods = parse_imports(read(f))
        except (OSError, UnicodeError):
            continue
        for m in mods:
            for target in stem_index.get(m, ()):
                if target != f:
                    reverse.setdefault(target, set()).add(f)
    return reverse


def affected(changed, reverse) -> set:
    """Every path reachable from `changed` by following reverse-dependency edges
    (the transitive set of files that import something changed). Excludes the
    changed files themselves."""
    seen = set()
    stack = list(changed)
    while stack:
        cur = stack.pop()
        for dep in reverse.get(cur, ()):
            if dep not in seen:
                seen.add(dep)
                stack.append(dep)
    return seen


def is_test_file(path: str) -> bool:
    base = os.path.basename(path)
    return (base.startswith("test_") or base.endswith("_test.py")) and base.endswith(".py")


def _scan_py(root: str) -> list:
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fn in filenames:
            if fn.endswith(".py"):
                out.append(os.path.relpath(os.path.join(dirpath, fn), root))
    return out


def _changed_from_base(base: str, root: str):
    """Changed .py paths from `git diff` against `base`, or None if git cannot diff
    (bad ref / not a repo). A None MUST surface as a loud error — never a silent
    'no tests affected', which a caller would misread as 'safe, run nothing'."""
    res = subprocess.run(["git", "-C", root, "diff", "--name-only", "%s...HEAD" % base],
                         capture_output=True, text=True)
    if res.returncode != 0:  # fall back to a plain diff (base may be a worktree state)
        # NOTE: plain diff changes semantics from merge-base→HEAD to base→worktree.
        # The triple-dot form (`main...HEAD`) shows changes since the fork point;
        # two-dot (`main`) shows everything different between the two snapshots.
        res = subprocess.run(["git", "-C", root, "diff", "--name-only", base],
                             capture_output=True, text=True)
    if res.returncode != 0:
        return None
    return [l.strip() for l in res.stdout.splitlines() if l.strip().endswith(".py")]


def parse_args(argv):
    root = "."
    base = None
    changed = []
    as_pytest = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--root":
            if i + 1 >= len(argv):
                raise ValueError("--root needs a path")
            root = argv[i + 1]
            i += 2
        elif a == "--base":
            if i + 1 >= len(argv):
                raise ValueError("--base needs a git ref")
            base = argv[i + 1]
            i += 2
        elif a == "--changed":
            i += 1
            while i < len(argv) and not argv[i].startswith("--"):
                changed.append(argv[i])
                i += 1
        elif a == "--pytest":
            as_pytest = True
            i += 1
        else:
            raise ValueError("unknown argument %r" % a)
    if not base and not changed:
        raise ValueError("provide --changed <files...> or --base <ref>")
    return root, base, changed, as_pytest


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        root, base, changed, as_pytest = parse_args(argv)
    except ValueError as e:
        print("usage: affected_tests.py [--root <dir>] (--changed <files...> | --base <ref>) "
              "[--pytest]", file=sys.stderr)
        print("error: %s" % e, file=sys.stderr)
        return 2

    root = os.path.abspath(root)
    if base:
        diffed = _changed_from_base(base, root)
        if diffed is None:
            print("error: could not `git diff` against %r (bad ref, or not a git repo). "
                  "Pass --changed <files...> instead." % base, file=sys.stderr)
            return 2
        changed += diffed
    # normalise to root-relative, keep only Python files that exist
    norm = []
    for c in changed:
        abs_c = os.path.abspath(c) if os.path.isabs(c) else os.path.join(root, c)
        rel = os.path.relpath(abs_c, root)
        if rel.startswith(".."):
            print("warning: path escapes repo root, skipping: %s" % c, file=sys.stderr)
            continue
        if rel.endswith(".py"):
            norm.append(rel)
    changed = sorted(set(norm))

    files = _scan_py(root)
    def _read_file(path):
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    reverse = build_reverse_deps(
        files, lambda p: _read_file(os.path.join(root, p)),
        build_stem_index(files))

    hit = affected(set(changed), reverse)
    hit |= {c for c in changed if is_test_file(c)}  # a changed test selects itself
    tests = sorted(p for p in hit if is_test_file(p))

    if not tests:
        # an empty result must not read as "safe, run nothing": this is a SUPERSET
        # selector over the IMPORT graph — a test reaching the change only via a
        # conftest fixture or a subprocess call (no import) is not captured.
        print("(no affected test files found — this is a superset selector over the "
              "import graph; run the full suite before merge.)", file=sys.stderr)

    if as_pytest and tests:
        print("python3 -m pytest -q " + " ".join(tests))
    else:
        for t in tests:
            print(t)
    return 0


if __name__ == "__main__":
    sys.exit(main())
