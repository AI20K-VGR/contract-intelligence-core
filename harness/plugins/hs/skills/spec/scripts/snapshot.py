#!/usr/bin/env python3
"""
snapshot — opt-in spec-artifact snapshot/restore engine.

Captures the current spec artifact tree (docs/product/** or any resolved spec
root) into a timestamped snapshot dir under a configurable snapshots home, and
restores a named snapshot back over the spec tree.

CRITICAL DESIGN: snapshot is OPT-IN ONLY.
  - Invoked explicitly via --snapshot / --restore flags in the CLI.
  - No automatic snapshot call is wired into any migrator, approve, or update
    path. That convenience hook is deferred; the sibling migrator files are
    never touched by this module.

Public API:
  make_snapshot(spec_root, snapshots_home, ts) -> Path
      Copy spec_root/** into <snapshots_home>/<ts>/ + write README.
      Timestamps are injected so tests are deterministic; CLI path uses real time.

  restore_snapshot(spec_root, snapshots_home, ts, *, confirm=False) -> None
      Restore <snapshots_home>/<ts>/ back over spec_root.
      Refuses (raises RestoreDirtyError) when spec_root is inside a git work
      tree AND has uncommitted changes AND confirm=False.
      Uses a staging dir + atomic rename so partial copies never leave the
      live tree in an inconsistent state.

  list_snapshots(snapshots_home) -> List[str]
      Return sorted timestamp strings of available snapshots.
      Returns [] when snapshots_home is absent or empty — never raises.

Thresholds (hard integers, no prose):
  None in this module — safety threshold for "dirty" is the presence of ANY
  uncommitted change returned by `git status --porcelain docs/product/`.

CLI:
  snapshot.py --root <project-dir> --snapshot [--label <label>]
  snapshot.py --root <project-dir> --restore <ts> [--confirm]
  snapshot.py --root <project-dir> --list
"""

import argparse
import datetime as dt
import re
import shutil
import subprocess
import tempfile
import sys
from pathlib import Path
from typing import List, Optional

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class RestoreDirtyError(Exception):
    """Raised when restore would clobber uncommitted changes without confirmation."""


class SnapshotNotFoundError(Exception):
    """Raised when the requested snapshot timestamp does not exist."""


class SpecRootMissingError(Exception):
    """Raised when --snapshot is invoked before the spec artifact tree exists."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# PRIVATE metadata filename — never a real spec artifact, so a spec tree that
# carries its own docs/product/README.md is neither clobbered on capture nor
# deleted on restore (both were silent data loss when this was "README.md").
# A dotfile with no `.md` extension so it stays OUTSIDE every `*.md` artifact glob
# and cannot collide with a real product artifact the tree might legitimately hold.
_SNAPSHOT_META_NAME = ".spec-snapshot-meta"

_README_TEMPLATE = """\
# Product-Spec Snapshot

Captured: {ts}
Source:   {spec_root}

This directory is an opt-in point-in-time copy of the spec artifact tree.
It was created by `snapshot.py --snapshot` and is excluded from git tracking
via the project's .gitignore.

## Restore

To restore this snapshot over the live spec tree:

    python3 snapshot.py --root <project-root> --restore {ts} --confirm

The `--confirm` flag is required when the live tree has uncommitted changes
(to prevent silent data loss). Without it the restore is refused.

## Contents

All files in this snapshot directory mirror the layout of the original
spec artifact tree at the time of capture. Files are copies — the source
tree was never moved or deleted.
"""


def _is_git_work_tree(root: Path) -> bool:
    """True only when `root` is inside a git work tree.

    Mirrors the reflect_scan._is_git_work_tree pattern: any failure (no git
    binary, not a repo) degrades to False — never raises."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(root), capture_output=True, text=True,
        )
    except (OSError, FileNotFoundError):
        return False
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def _has_uncommitted_changes(spec_root: Path) -> bool:
    """True when `spec_root` (or its parent git root) has uncommitted changes
    touching the spec_root subtree.

    Uses `git status --porcelain -- <path>` which lists untracked, modified,
    and staged-but-not-committed files under the given path. Any output line
    means there are uncommitted changes.

    Degrades to False on any subprocess error (fail-safe: if we cannot check,
    we do not block the user)."""
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain", "--", str(spec_root)],
            cwd=str(spec_root), capture_output=True, text=True,
        )
    except (OSError, FileNotFoundError):
        return False
    if proc.returncode != 0:
        return False
    return bool(proc.stdout.strip())


def _real_ts() -> str:
    """Real-time timestamp in the canonical format used for snapshot dir names.
    Tests inject a deterministic string instead of calling this."""
    return dt.datetime.now().strftime("%Y%m%dT%H%M%S")


# Canonical snapshot-id shape: `_real_ts()`'s `%Y%m%dT%H%M%S`, optionally
# followed by a `-<label>` suffix (the CLI's `--label` appends exactly this).
_TS_FORMAT_RE = re.compile(r"^\d{8}T\d{6}(-.+)?$")


def _is_within(child: Path, parent: Path) -> bool:
    """True iff `child` is `parent` or a descendant of it (mirrors the
    fs_guard.py containment pattern used elsewhere in this skill).

    `is_relative_to` already returns True for identical paths, so it covers the
    `child == parent` case on its own -- byte-for-byte the fs_guard.py twin."""
    return child.is_relative_to(parent)


def _contained_snapshot_dir(snapshots_home: Path, ts: str) -> Path:
    """Resolve <snapshots_home>/<ts> and verify it cannot escape snapshots_home.

    `ts` may carry a caller-supplied `--label` suffix (make_snapshot) or come
    straight off `--restore` — never trust it to be a plain path segment. A
    string containing `/` or `..` is still parsed by pathlib as multiple path
    components, so resolving both sides (collapsing `..`, following any
    symlinks that exist) and comparing is what actually catches `--label
    ../../../tmp/evil` and similar traversal, not a naive substring check.

    Raises ValueError (never a bare escape) when the resolved candidate lands
    outside snapshots_home.
    """
    snapshots_home = Path(snapshots_home)
    candidate = snapshots_home / ts
    resolved_home = snapshots_home.resolve(strict=False)
    resolved_candidate = candidate.resolve(strict=False)
    if not _is_within(resolved_candidate, resolved_home):
        raise ValueError(
            f"'{ts}' resolves outside the snapshots home {resolved_home} — "
            "refusing to write/read there."
        )
    return candidate


def _snapshot_not_found(ts: str, snapshots_home: Path) -> SnapshotNotFoundError:
    return SnapshotNotFoundError(
        f"Snapshot '{ts}' not found in {snapshots_home}. "
        f"Available: {list_snapshots(snapshots_home)}"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def make_snapshot(spec_root: Path, snapshots_home: Path, ts: Optional[str] = None) -> Path:
    """Copy spec_root into <snapshots_home>/<ts>/ and write a README.

    Parameters
    ----------
    spec_root:      the spec artifact tree to capture (e.g. docs/product/)
    snapshots_home: where all snapshots live (e.g. <proj>/.product-spec-snapshots/)
    ts:             timestamp string used as the snapshot dir name; default = real
                    clock time. Tests inject a deterministic value.

    Returns the Path of the newly created snapshot dir.

    Never moves or deletes source files — always copies. Never overwrites an
    existing snapshot dir (timestamps are unique enough; if the exact ts already
    exists, the copy target is the existing dir plus the new files, matching
    copytree behaviour on Python 3.8+).

    Raises SpecRootMissingError (never a bare FileNotFoundError out of
    shutil.copytree) when `spec_root` does not exist yet — e.g. --snapshot
    run before any spec artifact has been created.

    Raises ValueError when `ts` (which embeds a CLI `--label`, if any) would
    resolve outside `snapshots_home` — e.g. a `--label ../../../tmp/evil`
    traversal attempt. Nothing is written in that case.
    """
    spec_root = Path(spec_root)
    snapshots_home = Path(snapshots_home)
    if not spec_root.is_dir():
        raise SpecRootMissingError(
            f"Spec artifact root not found: {spec_root}. Nothing to snapshot "
            "yet — create the spec tree first."
        )
    if ts is None:
        ts = _real_ts()

    dest = _contained_snapshot_dir(snapshots_home, ts)
    snapshots_home.mkdir(parents=True, exist_ok=True)

    # Copy tree — dirs_exist_ok=True so a re-run with the same ts is safe
    shutil.copytree(str(spec_root), str(dest), dirs_exist_ok=True)

    # Write snapshot metadata after the copy so it describes the captured state.
    # PRIVATE name (never a real artifact) so a real README.md is left intact.
    meta = dest / _SNAPSHOT_META_NAME
    meta.write_text(
        _README_TEMPLATE.format(ts=ts, spec_root=spec_root),
        encoding="utf-8",
    )

    return dest


def restore_snapshot(
    spec_root: Path,
    snapshots_home: Path,
    ts: str,
    *,
    confirm: bool = False,
) -> None:
    """Restore a snapshot back over the live spec tree.

    Safety contract (mirrors the migrator caution philosophy):
      - If spec_root is inside a git work tree AND has uncommitted changes AND
        confirm=False → raises RestoreDirtyError. No files are touched.
      - With confirm=True the restore proceeds even over dirty trees.

    Atomicity: copies into a staging dir first, then performs an atomic
    rename swap so the live tree is never left in a partially-restored state.

    `ts` is validated twice before any read happens: against the canonical
    snapshot-id shape (`_TS_FORMAT_RE`, the same shape `make_snapshot`
    generates) and by resolving `snapshots_home / ts` to confirm it stays
    inside `snapshots_home`. Either check failing raises the documented
    SnapshotNotFoundError — never a raw traceback — so `--restore ..` or
    `--restore ../foo` cannot walk `copytree`/`rename` outside the snapshots
    tree.

    Parameters
    ----------
    spec_root:      live spec tree to restore over
    snapshots_home: parent dir of all snapshots
    ts:             timestamp string identifying the snapshot to restore
    confirm:        set True to allow restore over uncommitted changes
    """
    spec_root = Path(spec_root)
    snapshots_home = Path(snapshots_home)

    if not _TS_FORMAT_RE.match(ts):
        raise _snapshot_not_found(ts, snapshots_home)

    try:
        snap_dir = _contained_snapshot_dir(snapshots_home, ts)
    except ValueError:
        raise _snapshot_not_found(ts, snapshots_home)

    if not snap_dir.is_dir():
        raise _snapshot_not_found(ts, snapshots_home)

    # Dirty-tree guard: refuse if inside git and has uncommitted changes
    if not confirm and _is_git_work_tree(spec_root) and _has_uncommitted_changes(spec_root):
        raise RestoreDirtyError(
            f"Refusing to restore snapshot '{ts}': the spec tree at {spec_root} "
            "has uncommitted changes. Pass confirm=True (--confirm on CLI) to "
            "override, or commit / stash your changes first."
        )

    # Scratch dirs live under ONE uniquely-created parent (mkdtemp), sibling of
    # spec_root to keep the swap renames on the same filesystem. Deriving fixed
    # `_restore_staging_<ts>` / `_restore_backup_<ts>` names and rmtree-ing them
    # was silent data loss: a pre-existing user dir of that exact name got deleted
    # by the cleanup path. mkdtemp guarantees the parent is OURS, so cleanup can
    # only ever touch our own scratch tree.
    scratch = Path(tempfile.mkdtemp(dir=str(spec_root.parent), prefix=f"_restore_{ts}_"))
    staging = scratch / "staging"
    backup = scratch / "backup"
    spec_root_existed = spec_root.exists()
    try:
        # Copy snapshot into staging (our private metadata excluded from live tree)
        shutil.copytree(str(snap_dir), str(staging), dirs_exist_ok=False)

        # Remove ONLY our private metadata file — never a real README.md the spec
        # tree may legitimately carry (deleting that was silent data loss).
        meta_in_staging = staging / _SNAPSHOT_META_NAME
        if meta_in_staging.is_file():
            meta_in_staging.unlink()

        # Atomic swap: if spec_root exists, rename it to backup first; then
        # rename staging to spec_root. On any failure AFTER the first rename,
        # the except block restores the backup so the original tree is never lost.
        if spec_root_existed:
            spec_root.rename(backup)

        staging.rename(spec_root)

    except Exception:
        # Rollback: if spec_root is missing (rename to backup already ran) and
        # backup exists, move it back so the original tree is left intact.
        if not spec_root.exists() and backup.exists():
            try:
                backup.rename(spec_root)
            except Exception:
                pass  # best-effort; the original error is re-raised below
        raise

    finally:
        # Only ever removes OUR uniquely-created scratch tree (holding leftover
        # staging on failure, or the old tree in backup after a successful swap).
        if scratch.exists():
            shutil.rmtree(scratch)


def list_snapshots(snapshots_home: Path) -> List[str]:
    """Return sorted list of snapshot timestamp strings.

    Returns [] when snapshots_home does not exist or is empty. Never raises.
    """
    snapshots_home = Path(snapshots_home)
    if not snapshots_home.is_dir():
        return []
    entries = sorted(
        d.name for d in snapshots_home.iterdir() if d.is_dir()
    )
    return entries


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _default_snapshots_home(root: Path) -> Path:
    """Conventional snapshots home: <project-root>/.product-spec-snapshots/"""
    return root / ".product-spec-snapshots"


def _default_spec_root(root: Path) -> Path:
    """Conventional spec artifact root: <project-root>/docs/product/"""
    return root / "docs" / "product"


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Opt-in snapshot/restore engine for the product spec artifact tree."
    )
    ap.add_argument("--root", default=".", help="Project root directory.")
    ap.add_argument(
        "--snapshot", action="store_true",
        help="Capture the current spec artifact tree into a timestamped snapshot.",
    )
    ap.add_argument(
        "--label", default=None,
        help="Optional label suffix appended to the snapshot timestamp dir name.",
    )
    ap.add_argument(
        "--restore", metavar="TS",
        help="Restore the snapshot identified by timestamp TS over the live spec tree.",
    )
    ap.add_argument(
        "--confirm", action="store_true",
        help="Allow --restore to proceed even when the live tree has uncommitted changes.",
    )
    ap.add_argument(
        "--list", action="store_true",
        help="List available snapshot timestamps.",
    )
    args = ap.parse_args()

    root = Path(args.root).resolve()
    spec_root = _default_spec_root(root)
    snapshots_home = _default_snapshots_home(root)

    if args.snapshot:
        ts = _real_ts()
        if args.label:
            if "/" in args.label or "\\" in args.label or ".." in args.label:
                print(
                    f"ERROR: --label '{args.label}' must be a plain slug "
                    "(no '/', '\\', or '..') — it names a directory suffix, "
                    "not a path.",
                    file=sys.stderr,
                )
                return 2
            ts = f"{ts}-{args.label}"
        try:
            dest = make_snapshot(spec_root, snapshots_home, ts=ts)
        except SpecRootMissingError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        print(f"Snapshot captured: {dest}", file=sys.stderr)
        return 0

    if args.restore:
        try:
            restore_snapshot(spec_root, snapshots_home, args.restore, confirm=args.confirm)
            print(f"Restored snapshot '{args.restore}' to {spec_root}", file=sys.stderr)
        except RestoreDirtyError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        except SnapshotNotFoundError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        return 0

    if args.list:
        snaps = list_snapshots(snapshots_home)
        if snaps:
            for s in snaps:
                print(s)
        else:
            print("(no snapshots)", file=sys.stderr)
        return 0

    ap.print_help(sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
