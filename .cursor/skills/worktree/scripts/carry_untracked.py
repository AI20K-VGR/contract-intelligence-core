#!/usr/bin/env python3
"""Carry untracked harness config into a freshly-created worktree.

`git worktree add` shares tracked files through the shared git-dir but never
carries untracked / gitignored content. A per-project install can leave
`harness/` and `.claude/` untracked in the host repo, so a new worktree would
start without the harness wiring it needs.

Rule: copy a carry entry ONLY when git cannot — i.e. the entry has NO tracked
files under it. A tracked `harness/` is git's job; re-copying would also drag
its ignored `state/`/pycache noise into the clean worktree. A fully
untracked/ignored dir (`.claude/`, an uncommitted `harness/` install) is
copied wholesale.

Carry-list precedence (mirrors the harness `explicit > $HARNESS_XXX > shipped`
loader): --carry flag  >  $HARNESS_WORKTREE_CARRY  >  DEFAULT_CARRY.

The shipped default is end-user-safe. Dogfood-only paths (`.harness-dev`) are
NOT shipped here — this repo appends them via HARNESS_WORKTREE_CARRY in its
gitignored .claude/settings.local.json (scrubbed at push).

Advisory: always exits 0. A failed carry must never block worktree creation.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

# End-user-safe carry entries present in any harness-installed repo.
DEFAULT_CARRY = ["harness", ".claude"]

_ENV = "HARNESS_WORKTREE_CARRY"


def resolve_carry(flag: str | None) -> list[str]:
    """--carry flag > $HARNESS_WORKTREE_CARRY > DEFAULT_CARRY (colon-separated)."""
    raw = flag if flag is not None else os.environ.get(_ENV)
    if raw is None:
        return list(DEFAULT_CARRY)
    return [e.strip() for e in raw.split(":") if e.strip()]


def _is_safe_entry(entry: str) -> bool:
    """Reject anything that could escape the source root."""
    if not entry or entry == ".git":
        return False
    if os.path.isabs(entry):
        return False
    parts = Path(entry).parts
    return ".." not in parts and not parts[0].startswith("/")


def _has_tracked_files(source: Path, entry: str) -> bool:
    """True if git already carries this entry (any tracked file under it)."""
    out = subprocess.run(
        ["git", "-C", str(source), "ls-files", "-z", "--", entry],
        capture_output=True,
        text=True,
    )
    return bool(out.stdout.strip("\x00").strip())


def _copy(src: Path, dst: Path) -> None:
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True, symlinks=True)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def carry(source: Path, dest: Path, entries: list[str], dry_run: bool) -> list[str]:
    carried: list[str] = []
    for entry in entries:
        if not _is_safe_entry(entry):
            print(f"carry: refused unsafe entry {entry!r}", file=sys.stderr)
            continue
        src = source / entry
        if not src.exists():
            continue  # not present in this repo → skip silently
        if _has_tracked_files(source, entry):
            # git carries tracked entries; copying would also drag ignored noise
            continue
        if dry_run:
            print(f"carry: would carry {entry}")
            carried.append(entry)
            continue
        try:
            _copy(src, dest / entry)
        except OSError as exc:  # advisory — never abort worktree creation
            print(f"carry: failed {entry}: {exc}", file=sys.stderr)
            continue
        print(f"carry: {entry}")
        carried.append(entry)
    return carried


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Carry untracked config into a worktree")
    ap.add_argument("--source", required=True, help="source repo root")
    ap.add_argument("--dest", required=True, help="destination worktree root")
    ap.add_argument("--carry", help="colon-separated carry entries (overrides env)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    source = Path(args.source).resolve()
    dest = Path(args.dest).resolve()
    entries = resolve_carry(args.carry)
    carry(source, dest, entries, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
