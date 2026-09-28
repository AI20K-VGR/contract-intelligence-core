#!/usr/bin/env python3
"""shape_paths — the canonical script-path containment helper for hs:shape (BA).

There is a hard boundary between the PO's spec tree (`docs/product/`, owned
by hs:spec) and the BA sidecar (`docs/product/shape/`, owned by hs:shape).
The BA layer reads the PO story graph but never writes into it —
`shape_path()` is the single mechanism that enforces that, not a prose
convention: every hs:shape writer (`task_model.py`, and later
`roadmap_rollup.py`/`poc_gate.py`/`loop_handoff.py`) resolves its target
through this function before touching disk. (`effort_map.py` is not a writer --
it is a pure stdout calculator and never touches disk.)

Resolve-then-contain, same shape as hs:spec's own `fs_guard.py` and the
sibling `experiment_spec.experiment_path()`: collapse `..`/symlinks first,
THEN test containment under the resolved sidecar root — a naive string
`startswith` would miss a `..` traversal, a sibling directory, or a prefix
look-alike (`docs/product/shape-extra`).

Honesty caveat (same one `fs_guard.py` states for its own scope): this is a
SCRIPT-path guard. It disciplines every hs:shape script writer; it cannot —
and is not meant to — stop a raw LLM `Write` composing a body directly to
disk. That is a caller-discipline hazard the SKILL.md prose only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

RootLike = Any  # str | Path, kept untyped to avoid a PEP-604 union annotation


class ShapeContainmentError(PermissionError):
    """Raised when an hs:shape write would land outside `docs/product/shape/`.

    Subclasses PermissionError (the same exception family the sibling
    `experiment_spec.experiment_path()` raises) so a caller that already
    catches PermissionError on the sibling containment helper catches this
    one too, without needing a second except clause.
    """


def shape_dir(root: RootLike) -> Path:
    """The BA sidecar root: `<root>/docs/product/shape/`."""
    return Path(root) / "docs" / "product" / "shape"


def shape_path(root: RootLike, rel: str) -> Path:
    """Resolve `rel` under the BA sidecar, raising on any escape attempt.

    `strict=False` on both sides: the leaf (and its intermediate dirs) may
    not exist yet — the write hasn't happened — but any path segment that DOES
    already exist still has its symlinks followed, so a symlink planted
    inside `shape/` pointing back out to `docs/product/stories/` is still
    caught.

    Escaping is not limited to `..` traversal: a caller passing an absolute
    `rel` that names a path outside the sidecar (e.g.
    `/abs/path/docs/product/stories/x.md`) is caught the same way, because
    `(base / rel)` treats a POSIX absolute `rel` as replacing `base`
    entirely, and the post-resolve containment check then fails.

    docs/product/stories/ (the PO-owned story tree) is never a legal target:
    it sits OUTSIDE `docs/product/shape/`, so any attempt to write there —
    via `..`, an absolute override, or a symlink — necessarily fails the
    containment check below and raises. There is no schema-level "stories"
    special-case; the same one invariant covers it.
    """
    base = shape_dir(root).resolve(strict=False)
    candidate = (base / rel).resolve(strict=False)
    try:
        candidate.relative_to(base)
    except ValueError:
        raise ShapeContainmentError(
            "hs:shape write escapes containment: %r resolves to %s, which is "
            "outside the BA sidecar %s. hs:shape never writes into the PO "
            "spec tree (e.g. docs/product/stories/)."
            % (rel, candidate, base)
        )
    return candidate
