#!/usr/bin/env python3
"""
anti_tautology — deterministic, 0-token AST scan that flags a verification
artifact (a test / rule / claim-check file) importing the very application
module it is meant to verify. A checker that reaches into the code it is
supposed to validate can be self-consistent and still wrong: it is no longer
an independent source of truth.

Anchor: `docs/product/_refs/frankcode-src/qa/methodology/qa/rule-based-verification.md`
lines 100-108, "Anti-tautology mechanism" -> "No code reuse: Rule engine uses
AST/regex/semgrep. It does not call application code."

Distinct from `harness/rules/testability-triad.md:43` (that `anti-tautology`
branch is about an acceptance criterion's WORDING restating the
implementation) -- this scans the checker's IMPORT GRAPH, a different failure
mode with a name collision on purpose. See `harness/rules/anti-tautology-
detection.md` for the boundary and how to read a finding.

CLI:
    anti_tautology.py <checker_path> --target <module|glob> [--allow <module> ...]

Verdict: `clean` (no import of `target` found) or `tainted` (>=1 match).
Exit code advises the caller (0 clean/advisory-only, 1 tainted) -- it never
hard-blocks by itself; the calling gate reads it advisory-first.
"""

import argparse
import ast
import fnmatch
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def _package_parts(checker_path: Path) -> List[str]:
    """Dotted package path containing `checker_path`, derived by walking up
    parent directories while each still has an `__init__.py`. Used to resolve
    a relative import (`from .target import x`) to its absolute dotted name.
    A checker that is not inside any package (no `__init__.py` in its parent)
    resolves to an empty package -- relative imports then resolve to just the
    module name given after the dots."""
    parts: List[str] = []
    cur = checker_path.resolve().parent
    while (cur / "__init__.py").is_file():
        parts.insert(0, cur.name)
        parent = cur.parent
        if parent == cur:
            break
        cur = parent
    return parts


def _resolve_relative(package_parts: List[str], level: int, module: Optional[str]) -> str:
    """Absolute dotted module name for a relative import. `level=1` resolves
    relative to the checker's own package (Python's `__package__` semantics);
    each extra level walks one package up. Clips at zero levels rather than
    raising when a level exceeds the known package depth -- the caller only
    needs a best-effort absolute name to compare against `target`, not a fully
    faithful import resolver."""
    if level <= 0:
        return module or ""
    up = level - 1
    base = package_parts[: len(package_parts) - up] if up < len(package_parts) else []
    parts = list(base)
    if module:
        parts.extend(module.split("."))
    return ".".join(parts)


def _is_glob(target: str) -> bool:
    return any(ch in target for ch in ("*", "?", "["))


def _module_matches(module_name: str, target: str) -> bool:
    """A checker importing `module_name` counts as importing `target` when
    they are equal, when `module_name` is a submodule of `target`
    (`target.sub`), or -- for a glob target -- when the module's dotted name,
    rendered as a `pkg/sub/mod.py` path, matches the glob. Prefix matching
    uses a `.` boundary so `myapp` never falsely matches `myapplication`."""
    if not module_name:
        return False
    if _is_glob(target):
        path_form = module_name.replace(".", "/") + ".py"
        return fnmatch.fnmatch(path_form, target)
    return module_name == target or module_name.startswith(target + ".")


def _finding(file_str: str, line: int, imported_module: str, severity: str) -> Dict[str, Any]:
    return {
        "file": file_str,
        "line": line,
        "imported_module": imported_module,
        "severity": severity,
    }


def scan(checker_path: Any, target: str) -> List[Dict[str, Any]]:
    """Parse `checker_path` and return one finding per import that matches
    `target` (a dotted module name, a dotted-name prefix, or a glob such as
    `harness/scripts/grid/*.py`), plus an `advisory` finding per call that
    looks like the checker computing an "expected" value via a call on the
    already-imported target module (the golden-value heuristic). Stdlib
    `ast` only -- deterministic, 0-token: the same file + target always
    yields the same finding list, in the same order."""
    path = Path(checker_path)
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    package_parts = _package_parts(path)
    file_str = str(checker_path)

    findings: List[Dict[str, Any]] = []
    # local binding name -> resolved absolute dotted module, for every import
    # that matched target -- feeds the golden-value call heuristic below.
    matched_locals: Dict[str, str] = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                resolved = alias.name
                if _module_matches(resolved, target):
                    findings.append(_finding(file_str, node.lineno, resolved, "block"))
                    local_name = alias.asname or alias.name.split(".")[0]
                    matched_locals[local_name] = resolved
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                resolved = _resolve_relative(package_parts, node.level, node.module)
            else:
                resolved = node.module or ""
            for alias in node.names:
                # `from pkg import sub` imports the SUBMODULE pkg.sub — so test
                # the combined dotted path too, not just the parent `pkg`.
                # Without this the most common import idiom slips past the
                # detector (e.g. `from harness.scripts.grid import loop` when
                # the target is harness.scripts.grid.loop). A `from pkg import
                # some_symbol` never falsely matches: pkg.some_symbol only
                # equals a module target when it genuinely names that module.
                submodule = (resolved + "." + alias.name) if resolved else alias.name
                if _module_matches(resolved, target):
                    matched_mod = resolved
                elif _module_matches(submodule, target):
                    matched_mod = submodule
                else:
                    continue
                findings.append(_finding(file_str, node.lineno, matched_mod, "block"))
                local_name = alias.asname or alias.name
                matched_locals[local_name] = matched_mod

    if matched_locals:
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute):
                continue
            value = func.value
            if isinstance(value, ast.Name) and value.id in matched_locals:
                findings.append(
                    _finding(file_str, node.lineno, matched_locals[value.id], "advisory")
                )

    return findings


def verdict(findings: List[Dict[str, Any]]) -> str:
    """`tainted` when at least one `block`-severity finding is present.
    Advisory-only findings never escalate the verdict on their own -- the
    golden-value heuristic is a hint, not proof of reuse."""
    if any(f.get("severity") == "block" for f in findings):
        return "tainted"
    return "clean"


def _apply_allow(findings: List[Dict[str, Any]], allow: List[str]) -> List[Dict[str, Any]]:
    """Drop findings whose `imported_module` matches an allowlisted pattern
    (exact name or glob, same matching rule as `target`). This is the
    documented escape hatch for a legitimate import (e.g. a fixture that must
    construct a real object) -- see `harness/rules/anti-tautology-
    detection.md` for when to reach for it instead of silencing the finding
    another way."""
    if not allow:
        return findings
    return [
        f for f in findings
        if not any(_module_matches(f["imported_module"], pattern) for pattern in allow)
    ]


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Flag a checker file importing the app module it verifies.",
    )
    ap.add_argument("checker_path", help="path to the verification artifact to scan")
    ap.add_argument("--target", required=True, help="module name, dotted prefix, or glob to detect")
    ap.add_argument(
        "--allow", action="append", default=[],
        help="module name/glob to exempt from findings (repeatable)",
    )
    args = ap.parse_args(argv)

    try:
        findings = scan(args.checker_path, args.target)
    except (FileNotFoundError, IsADirectoryError, OSError, SyntaxError, UnicodeDecodeError) as exc:
        # a nonexistent/unreadable/unparseable checker path is a user error —
        # a half-edited file (SyntaxError) or non-UTF8 bytes (UnicodeDecodeError)
        # must yield a clean stderr line + exit 2, not a raw traceback.
        sys.stderr.write("anti_tautology: %s\n" % exc)
        return 2
    findings = _apply_allow(findings, args.allow)

    for f in findings:
        print(f"{f['file']}:{f['line']}  {f['imported_module']}  [{f['severity']}]")
    result = verdict(findings)
    print(f"verdict: {result}")

    return 1 if result == "tainted" else 0


if __name__ == "__main__":
    sys.exit(main())
