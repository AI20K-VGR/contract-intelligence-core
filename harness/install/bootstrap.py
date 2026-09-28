#!/usr/bin/env python3
"""bootstrap.py — first-run seed of a project's private .harness/ data home.

A global install ships ONE shared binary; each project keeps its own writeable
data skeleton under `.harness/`. Nothing in git carries that skeleton (`.harness/`
is gitignored), so the first time the toolkit runs in a project the skeleton has
to be created. This module is the ONLY sanctioned mkdir for the data home:
the resolvers in harness_paths stay PURE (readers never create what they inspect),
while the two WRITERS that own the mkdir call ensure_skeleton() — the installer at
install time and the SessionStart safety-net for a project that was cloned fresh.

ensure_skeleton is idempotent: re-running never clobbers existing content, it only
fills what is missing, and it writes STRICTLY under the given data_root — a member
that would escape (a mis-resolved root, a `..` climb) raises ValueError instead of
landing in the parent, and the fail-closed unresolved marker is refused outright.
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "scripts"))
import harness_paths  # noqa: E402

# The skeleton seeded on first run. state/ and its children hold all per-project
# runtime writes (trace, telemetry, the per-session actor cache); a .gitkeep under
# state/ keeps the tree present for same-machine tools that list it even though the
# project gitignores `.harness/`.
_SKELETON_DIRS = ("state", "state/trace", "state/telemetry", "state/sessions")


def _contained(root: Path, child: Path) -> bool:
    root = root.resolve()
    child = child.resolve()
    return child == root or root in child.parents


def ensure_skeleton(data_root, *, dry_run=False):
    """Create the project `.harness/` skeleton idempotently under data_root.

    Returns the sorted list of paths that were (or, under dry_run, WOULD be)
    created — empty when the skeleton is already present. Only ever writes under
    data_root; a member escaping it raises ValueError, and the fail-closed
    unresolved marker is refused. Readers never call this — only the installer and
    the SessionStart net (writers)."""
    root = Path(data_root)
    if harness_paths.data_root_unresolved(root):
        raise ValueError(
            "refusing to bootstrap the fail-closed unresolved data root — no "
            "project resolved (set CLAUDE_PROJECT_DIR or HARNESS_DATA_ROOT)")
    created = []
    for rel in ("",) + _SKELETON_DIRS:
        target = root / rel if rel else root
        if not _contained(root, target):
            raise ValueError("skeleton path escapes data_root: %s" % target)
        if not target.exists():
            if not dry_run:
                target.mkdir(parents=True, exist_ok=True)
            created.append(str(target))
    keep = root / "state" / ".gitkeep"
    if not _contained(root, keep):
        raise ValueError("skeleton path escapes data_root: %s" % keep)
    if not keep.exists():
        if not dry_run:
            keep.parent.mkdir(parents=True, exist_ok=True)
            keep.write_text("", encoding="utf-8")
        created.append(str(keep))
    return sorted(created)


def ensure_current_project(*, dry_run=False):
    """Bootstrap the skeleton for the project resolved from the ambient env
    (data_root()). Returns the created list, or [] when no project resolves
    (fail-closed marker) — the SessionStart net calls this and must never raise
    on an unresolved root (telemetry-class, fail-open)."""
    root = harness_paths.data_root()
    if harness_paths.data_root_unresolved(root):
        return []
    return ensure_skeleton(root, dry_run=dry_run)


if __name__ == "__main__":
    for path in ensure_current_project():
        print("created %s" % path)
