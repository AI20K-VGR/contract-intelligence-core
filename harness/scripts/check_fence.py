#!/usr/bin/env python3
"""
check_fence — advisory soft-fence SCAN. Reports working-tree changes that land
OUTSIDE the declared ownership zones. ADVISORY ONLY: it never blocks, always
exits 0, and is not a write guard.

This is the pull-side companion to `fs_guard` (the script-path containment
helper). Where `fs_guard` refuses an out-of-zone SCRIPT write, this scan
surfaces — after the fact — any file the session touched outside the owned
zones (including raw LLM `Write`s and LLM-composed bodies the helper cannot
intercept). It feeds the memory-gap pass as a soft nudge, not a gate.

Fence boundary is DATA-DRIVEN: the in-fence prefixes are the union of every
zone root declared in ownership.yaml (the same table fs_guard reads), not a
hard-coded directory. Adding a zone is a config edit. The harness scans its own
working tree, so the zones it owns (docs/, harness/state/, harness/standards/,
plans/) are in-fence and everything else is a breach finding.

Mechanism: `git status --porcelain` over the project root lists every changed
path; any path not under a declared zone is one `fence_breach` finding
(severity `warn`). No LLM, deterministic. If `root` is not inside a git work
tree, the scan degrades to empty findings (it cannot read change state, and
advisory is not an error). Flood-control (capping a large breach set) lives one
layer up in the memory-gap collector, not here — this scan reports faithfully.

CLI:
    check_fence.py --root <project-dir>
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from encoding_utils import configure_utf8_console
from graph_core import _now

configure_utf8_console()

_OWNERSHIP_DEFAULT = Path(__file__).resolve().parent.parent / "data" / "ownership.yaml"


def _ownership_path() -> Path:
    raw = os.environ.get("HARNESS_OWNERSHIP_FILE")
    return Path(raw) if raw else _OWNERSHIP_DEFAULT


def fence_prefixes(ownership_file: Optional[Path] = None) -> List[str]:
    """The in-fence POSIX path prefixes, derived from ownership.yaml zones.

    Flattens every zone's declared root(s) into a flat prefix list, each
    normalized to POSIX separators with a trailing slash so the prefix test is
    OS-agnostic and a sibling look-alike (`docs-extra/`) is not mistaken for the
    `docs/` zone. A non-string/empty root is skipped (the consistency of the
    table itself is fs_guard's loud concern; this advisory pass stays soft)."""
    import yaml_io

    p = Path(ownership_file) if ownership_file else _ownership_path()
    raw = yaml_io.safe_load(p.read_text(encoding="utf-8"))
    zones = (raw or {}).get("zones") if isinstance(raw, dict) else None
    prefixes: List[str] = []
    for roots in (zones or {}).values():
        if isinstance(roots, str):
            roots = [roots]
        for r in roots or []:
            if not isinstance(r, str):
                continue
            r = r.strip().replace("\\", "/")
            if not r:
                continue
            if not r.endswith("/"):
                r += "/"
            if r not in prefixes:
                prefixes.append(r)
    return prefixes


def _in_fence(posix: str, prefixes: List[str]) -> bool:
    """True when `posix` is one of the declared zone roots or sits under one."""
    for pre in prefixes:
        bare = pre.rstrip("/")
        if posix == bare or posix.startswith(pre):
            return True
    return False


def _porcelain_paths(root: Path) -> List[str]:
    """Return repo-relative POSIX paths of every changed file per
    `git status --porcelain -z`. NUL-delimited so paths with spaces/newlines are
    parsed unambiguously; rename entries (`R`) carry `dest\\x00orig` — both halves
    are real touches. Returns [] (degrades, never raises) if root is not a git
    work tree."""
    try:
        # -uall: list individual untracked FILES, not collapsed parent dirs — a
        # brand-new owned tree would otherwise report as the bare parent dir and
        # be misread as an outside touch.
        proc = subprocess.run(
            ["git", "status", "--porcelain", "-z", "-uall"],
            cwd=str(root), capture_output=True, text=True, timeout=30,
        )
    except (OSError, FileNotFoundError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0:
        # Not a git repo, or git unavailable → advisory degrades to empty.
        return []

    paths: List[str] = []
    # `-z` format: each record is `XY <path>` (and for renames an extra NUL-
    # separated `<orig>` follows). Split on NUL; a record begins with the 2-char
    # status + a space, the remainder is the path.
    fields = proc.stdout.split("\x00")
    i = 0
    while i < len(fields):
        rec = fields[i]
        if not rec:
            i += 1
            continue
        status = rec[:2]
        path = rec[3:]
        paths.append(path)
        # A rename/copy record is followed by its original path in the next field.
        if status and status[0] in ("R", "C"):
            i += 1
            if i < len(fields) and fields[i]:
                paths.append(fields[i])
        i += 1
    return paths


def scan(root: Path, prefixes: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """One `fence_breach` finding (severity `warn`) per changed path outside the
    declared ownership zones. Advisory — callers must not gate on this.

    `prefixes` defaults to the ownership.yaml zone union; pass an explicit list
    to scope the fence (tests, alternate zone tables). If the zone table cannot
    be read, the scan degrades to empty findings rather than flagging the whole
    tree (advisory is not an error)."""
    if prefixes is None:
        try:
            prefixes = fence_prefixes()
        except Exception:
            return []
    findings: List[Dict[str, Any]] = []
    for rel in _porcelain_paths(Path(root)):
        # Normalize to POSIX separators so the prefix test is OS-agnostic.
        posix = rel.replace("\\", "/")
        if _in_fence(posix, prefixes):
            continue
        findings.append({
            "check": "fence_breach",
            "severity": "warn",
            "artifact_id": None,
            "file": posix,
            "detail": (
                f"{posix} was touched outside the declared ownership zones. "
                f"Advisory only — confirm this change belongs here."
            ),
            "context": None,
        })
    return findings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    # --lang accepted for CLI-contract uniformity; this is a lang-agnostic JSON
    # feeder (English keys), so it is ignored.
    ap.add_argument("--lang", default="en", choices=["en", "vi"])
    args = ap.parse_args()

    root = Path(args.root).resolve()
    findings = scan(root)
    output = {
        "schema_version": "1.0",
        "root": str(root),
        "checked_at": _now(),
        "findings": findings,
    }
    print(json.dumps(output, indent=2, ensure_ascii=False, default=str))
    # Advisory: always exit 0, even on breaches. It never gates.
    return 0


if __name__ == "__main__":
    sys.exit(main())
