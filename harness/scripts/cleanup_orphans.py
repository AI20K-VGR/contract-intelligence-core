"""cleanup_orphans — safely remove files an over-install left behind.

When a harness install lands over an older one, files dropped from the new
version linger on disk. This module classifies those orphans and removes the
safe ones, while protecting anything the user added or modified.

It does NOT grow a second disk scanner: the disk-vs-manifest scan reuses
verify_install.orphan_problems (which already excludes harness/state/). Layered
on top:

  - symlinks are handled FIRST and never hashed — orphan_problems follows links
    (is_file / sha256_file both follow), so broken/→dir symlinks slip past it and
    →file symlinks would hash their external target. We scan os.path.islink
    ourselves and classify by manifest membership (same rule as files): a symlink
    the OLD version shipped but the new one dropped -> UNLINK; one absent from both
    manifests is user-added -> KEEP (never the installer's to delete).
  - real-file orphans are classified against the OLD manifest snapshot: a
    version-dropped file that still hashes to its old value is pristine -> REMOVE;
    a changed one -> PROMPT (left for the manual door); a file absent from the old
    manifest is user-added -> KEEP.

The planner is pure (no fs writes). apply_cleanup is the only mutator: it backs
up everything first, verifies the backup, then deletes — so a failure mid-delete
rolls back atomically and a failure mid-backup never deletes at all.
"""
import argparse
import json
import os
import shutil
import sys
import time
import uuid
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import build_manifest  # noqa: E402  (reuse sha256_file + MANIFEST_REL)
import verify_install  # noqa: E402  (reuse orphan_problems — the ONE disk scan)

MANIFEST_REL = build_manifest.MANIFEST_REL
_STATE_PREFIX = "harness/state/"
_BUCKETS = ("remove", "unlink", "prompt", "keep_user", "keep_exception")


def render_plan(plan):
    """One bucket-labeled line per classified path (shared by the CLI + hs-cli)."""
    return ["%-15s %s" % (bucket, rel) for bucket in _BUCKETS for rel in plan[bucket]]


# Monkeypatch seams (so apply's backup/delete steps are injectable in tests).
def _copy(src, dst):
    shutil.copy2(src, dst)


def _unlink(path):
    # os.unlink removes the link itself and never follows a symlink.
    os.unlink(path)


def _timestamp():
    return time.strftime("%Y%m%d-%H%M%S")


def _new_tracked(target_root: Path) -> set:
    """The freshly-installed manifest's tracked set (the ground truth for what is
    legitimately shipped). Refuse to classify without it: an empty set would make
    every shipped symlink look like an orphan and route it to unlink."""
    mpath = target_root / MANIFEST_REL
    if not mpath.is_file():
        raise SystemExit("cleanup refused: new manifest missing at %s — cannot "
                         "tell shipped files from orphans" % mpath)
    try:
        return set(json.loads(mpath.read_text(encoding="utf-8")).get("files", {}))
    except (ValueError, OSError) as e:
        raise SystemExit("cleanup refused: new manifest unreadable (%s)" % e)


def plan_cleanup(target_root, old_manifest, exception_map=None):
    """Classify orphans into 5 buckets without touching the fs.

    target_root  : install root (holds harness/).
    old_manifest : the pre-overwrite manifest dict ({"files": {rel: hash}}) or
                   None for a first install (-> empty plan, no-op).
    exception_map: rel paths to always KEEP even if orphaned.
    """
    target_root = Path(target_root)
    exceptions = set(exception_map or [])
    plan = {bucket: [] for bucket in _BUCKETS}

    if old_manifest is None:
        return plan
    harness_dir = target_root / "harness"
    if not harness_dir.is_dir():
        return plan

    new_tracked = _new_tracked(target_root)
    old_files = (old_manifest or {}).get("files", {})

    # 1) symlinks first — classify ALL orphan symlinks as UNLINK, never hash one.
    symlink_rels = set()
    for dirpath, dirnames, filenames in os.walk(harness_dir, followlinks=False):
        for name in list(dirnames) + filenames:
            full = os.path.join(dirpath, name)
            if not os.path.islink(full):
                continue
            rel = Path(full).relative_to(target_root).as_posix()
            if rel.startswith(_STATE_PREFIX):
                continue
            symlink_rels.add(rel)
            if rel in new_tracked:
                continue  # a legitimately shipped symlink
            if rel in exceptions:
                plan["keep_exception"].append(rel)
            elif rel in old_files:
                plan["unlink"].append(rel)      # version-dropped, ours to remove
            else:
                plan["keep_user"].append(rel)   # user-added — never the installer's

    # 2) real-file orphans via the reused scanner.
    for rel, _msg in verify_install.orphan_problems(target_root):
        if rel in symlink_rels:
            continue  # a symlink — already handled, never hashed
        if rel in exceptions:
            plan["keep_exception"].append(rel)
            continue
        if rel in old_files:
            actual = build_manifest.sha256_file(target_root / rel)
            if actual == old_files[rel]:
                plan["remove"].append(rel)      # version-dropped, pristine
            else:
                plan["prompt"].append(rel)      # version-dropped, modified
        else:
            plan["keep_user"].append(rel)       # user-added
    return plan


def apply_cleanup(plan, target_root, backup_dir_base):
    """Back everything up, verify, then delete. The ONLY fs mutator.

    Returns {"backup_dir", "removed", "unlinked"}; backup_dir is None when there
    was nothing to do.
    """
    target_root = Path(target_root)
    to_remove = list(plan.get("remove", []))
    to_unlink = list(plan.get("unlink", []))
    if not to_remove and not to_unlink:
        return {"backup_dir": None, "removed": [], "unlinked": []}

    # unique backup dir even for two runs in the same second (<ts>-<pid>-<uuid>).
    backup_root = Path(backup_dir_base) / ("%s-%d-%s" % (
        _timestamp(), os.getpid(), uuid.uuid4().hex[:8]))
    backup_root.mkdir(parents=True, exist_ok=False)

    # PHASE 1 — back up ALL (files copied, symlinks recreated), then verify.
    try:
        for rel in to_remove:
            dst = backup_root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            _copy(target_root / rel, dst)
        for rel in to_unlink:
            dst = backup_root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(os.readlink(target_root / rel), dst)
        for rel in to_remove:
            if not (backup_root / rel).is_file():
                raise RuntimeError("backup incomplete for %s" % rel)
        for rel in to_unlink:
            if not os.path.islink(backup_root / rel):
                raise RuntimeError("backup incomplete for symlink %s" % rel)
    except Exception:
        # nothing deleted yet — drop the partial backup and re-raise (no loss).
        shutil.rmtree(backup_root, ignore_errors=True)
        raise

    # PHASE 2 — delete; on any failure, restore everything already removed.
    deleted = []
    try:
        for rel in to_remove:
            _unlink(target_root / rel)
            deleted.append((rel, "file"))
        for rel in to_unlink:
            _unlink(target_root / rel)
            deleted.append((rel, "symlink"))
    except Exception as delete_err:
        # best-effort rollback: one failed restore must not strand the rest. Every
        # target is still in backup_root, so surface where to recover by hand.
        failed = []
        for rel, kind in deleted:
            try:
                _restore(backup_root, target_root, rel, kind)
            except Exception:  # noqa: BLE001
                failed.append(rel)
        if failed:
            raise RuntimeError(
                "delete failed (%s) and rollback could not restore %s — recover "
                "from backup at %s" % (delete_err, failed, backup_root))
        raise

    return {"backup_dir": str(backup_root), "removed": to_remove,
            "unlinked": to_unlink}


def _restore(backup_root, target_root, rel, kind):
    src = Path(backup_root) / rel
    dst = Path(target_root) / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    if kind == "symlink":
        os.symlink(os.readlink(src), dst)
    else:
        shutil.copy2(src, dst)


def _load_manifest(path):
    if not path:
        return None
    p = Path(path)
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Classify + remove orphaned files from an over-install (safe).")
    ap.add_argument("--target", default=".", help="install root (holds harness/)")
    ap.add_argument("--old-manifest", help="pre-overwrite manifest snapshot (JSON)")
    ap.add_argument("--backup-dir", help="backup root (default: <target>/harness/state/cleanup-backup)")
    ap.add_argument("--apply", action="store_true", help="write (default: dry-run plan)")
    args = ap.parse_args(argv)

    target = Path(args.target).resolve()
    old = _load_manifest(args.old_manifest)
    plan = plan_cleanup(target, old)

    for line in render_plan(plan):
        print(line)

    if plan["prompt"]:
        print("\n%d modified file(s) left in place — run hs:cleanup to review (keep/change)"
              % len(plan["prompt"]))

    if not args.apply:
        print("\n(dry-run — re-run with --apply to back up + remove)")
        return 0

    backup_base = Path(args.backup_dir) if args.backup_dir else \
        target / "harness" / "state" / "cleanup-backup"
    result = apply_cleanup(plan, target, backup_base)
    if result["backup_dir"]:
        print("\nbacked up to %s; removed %d, unlinked %d" % (
            result["backup_dir"], len(result["removed"]), len(result["unlinked"])))
    else:
        print("\nnothing to clean up")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
