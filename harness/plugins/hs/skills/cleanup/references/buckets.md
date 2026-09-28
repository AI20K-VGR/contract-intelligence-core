# Cleanup buckets + backup/restore

## How a file lands in each bucket

The planner reuses `verify_install.orphan_problems` (disk vs the NEW manifest), then classifies each orphan against the OLD manifest snapshot taken before the over-install:

- **remove** — orphan ∈ old manifest, and its on-disk hash equals the old hash. Pristine version-dropped file → safe to delete.
- **prompt** — orphan ∈ old manifest, but its hash differs → you changed it. Never auto-deleted; you decide keep/change.
- **keep_user** — orphan ∉ old manifest → you added it. Kept.
- **unlink** — a symlink under harness/ not in the new manifest. Classified by an independent `os.path.islink` scan (orphan_problems follows links, so it would miss broken/→dir symlinks and would hash a →file symlink's external target). Always unlinked with `os.unlink`, never followed, never hashed.
- **keep_exception** — listed in the exception map (user-config that can land in the harness tree). Kept. Default map is empty.

## Atomic apply

`apply_cleanup` is the only fs mutator and runs in two phases:

1. **back up everything** to be removed/unlinked into one timestamped dir (`<ts>-<pid>-<uuid8>`, unique even for two runs in the same second), then
   **verify** every backup exists.
2. **delete** only after the full backup is verified.

Failure handling:
- raise during **backup** → nothing deleted yet; the partial backup is dropped. No data loss.
- raise during **delete** → everything already deleted is **restored from backup**, then the error re-raises. Atomic.

## Restore

Backups live under `harness/state/cleanup-backup/<id>/` mirroring the original paths. To undo, copy a file back from there (symlinks are recreated, not copied). The dir is gitignored runtime state; remove it yourself once satisfied.
