---
name: hs:cleanup
injectable: false
description: "Remove files an over-install left behind, safely: auto-clear pristine version-dropped files, and decide modified ones interactively (keep or change). Use after upgrading the harness or when verify reports orphans."
allowed-tools: [Bash, Read, AskUserQuestion]
argument-hint: "[--apply]"
disable-model-invocation: true
metadata:
  compliance-tier: workflow
---

# hs:cleanup — clear orphaned files after an over-install (interactive)

`install.sh` auto-clears the safe layer on upgrade. This skill is the
**manual door** for everything it deferred: files the previous version shipped that **you then modified**. It wraps `hs-cli cleanup` (engine: `cleanup_orphans.py`) and decides the modified layer with you.

## What the engine classifies

| Bucket | Meaning | Action |
|---|---|---|
| remove | version-dropped, untouched (hash matches old manifest) | auto-removed (backed up first) |
| unlink | orphaned symlink | unlinked (never hashed/followed) |
| prompt | version-dropped, **modified by you** | **left for you to decide** |
| keep_user | not in the old manifest (you added it) | kept |
| keep_exception | in the keep-exceptions map | kept |

`harness/state/` is never touched. A first install (no old manifest) is a no-op.

## Flow

1. Dry-run to see the buckets:

   ```bash
   hs-cli cleanup --dry-run
   ```

2. The safe layers (remove/unlink) clear on `--apply`. For each **prompt** file, ask the operator with AskUserQuestion — non-technical Vietnamese, recommended first:

   - **Giữ** (giữ nguyên file bạn đã sửa) — recommended
   - **Xóa** (bỏ file cũ, đã backup trước khi xóa)

3. Apply: safe layers always; promote any "Xóa" choices with `--remove`:

   ```bash
   hs-cli cleanup --apply --remove <path> ...
   ```

Everything removed is backed up first to
`harness/state/cleanup-backup/<ts>-<pid>-<id>/` — restorable if you change your mind. Details: `references/buckets.md`.

## hs:cleanup vs install.py --prune

`--prune` is the **coarse** path: it unlinks every orphan with no backup, no hash check, no user-added distinction — fine when a deployer knows the tree is disposable. `hs:cleanup` is the **safe default**: classify, back up, defer modified. Prefer this; reach for `--prune` only to wipe a throwaway tree.

## Boundaries

- Never touch `harness/state/` (runtime data).
- Never delete a modified file without an explicit keep/change decision.
- Backups are kept — point the operator at the backup dir, don't delete it.
