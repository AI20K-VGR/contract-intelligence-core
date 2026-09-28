#!/usr/bin/env python3
"""fs_guard — script-path containment helper for harness script writes.

A harness script that resolves its target through `assert_under(path, zone)`
BEFORE opening the file cannot write outside the zone's declared root(s):
`..` traversal, symlink escape, and prefix look-alikes (`docs-extra`) are all
defeated by resolve-then-contain. The zone table is DATA-DRIVEN from
harness/data/ownership.yaml — adding a zone is a config edit, not a code edit.

Two-root binding (global install): a zone's base root depends on which tree the
zone lives in. Project zones (docs/plans/state) are PER-PROJECT and resolve
against the project root; the bin zone (standards) is SHIPPED and resolves
against the bin root. Under a global layout (HARNESS_BIN_ROOT set) fs_guard is
authoritative — it picks the base per zone regardless of the `root` a caller
passes, so a caller that still hands over bin-root (e.g. plan_approval) cannot
mis-zone a project write; a project zone whose project root cannot resolve fails
CLOSED (FenceError), never widening to the bin. Under a self-hosted / legacy
layout (HARNESS_BIN_ROOT unset, bin == project) the caller's explicit `root` is
honored exactly as before, preserving every existing caller and test.

Honesty caveat (carried from the source corpus, mirrors the helper's real
reach): this is a SCRIPT-path guard ONLY. It raises before a script write
lands outside its zone. It CANNOT stop a raw LLM `Write`, nor an LLM composing
a body directly to disk — those are governed by the prose contract + the
review/CI invariants, not by this assert. It is the harness disciplining its
own scripts, nothing more.

A missing or malformed ownership.yaml fails LOUD at import time: a guard that
silently degrades to "allow everything" protects nothing. Compliance hooks
importing this module turn that ImportError-time crash into exit 2 + guidance
via their fail-closed wrapper.
"""

import os
from pathlib import Path

_OWNERSHIP_DEFAULT = Path(__file__).resolve().parent.parent / "data" / "ownership.yaml"

# Zone → which tree it lives in. Project zones are per-project (resolve against
# the project root); the bin zone is shipped (resolve against the bin root). An
# unknown zone defaults to project-scoped (fail-closed) under a global layout.
_BIN_ZONES = ("standards",)


class FenceError(Exception):
    """Raised when a script-driven write would land outside its zone root(s)."""


def _ownership_path(path=None) -> Path:
    if path:
        return Path(path)
    raw = os.environ.get("HARNESS_OWNERSHIP_FILE")
    return Path(raw) if raw else _OWNERSHIP_DEFAULT


def _load_zones() -> dict:
    """zone name → list of repo-root-relative root strings. Fails LOUD."""
    import yaml_io  # lazy so the error message below owns the missing-dep case too

    p = _ownership_path()
    try:
        raw = yaml_io.safe_load(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise RuntimeError(
            "fs_guard: ownership file missing at %s — the zone table is the "
            "guard's spine; restore harness/data/ownership.yaml" % p
        )
    zones = (raw or {}).get("zones") if isinstance(raw, dict) else None
    if not isinstance(zones, dict) or not zones:
        raise RuntimeError(
            "fs_guard: ownership file %s is malformed — expected a top-level "
            "`zones:` mapping of zone -> [roots]" % p
        )
    table = {}
    for zone, roots in zones.items():
        if isinstance(roots, str):
            roots = [roots]
        if not isinstance(roots, list) or not all(isinstance(r, str) for r in roots):
            raise RuntimeError(
                "fs_guard: zone %r in %s must map to a list of path strings" % (zone, p)
            )
        table[str(zone)] = [r.strip() for r in roots if r.strip()]
    return table


# Loaded at import: a broken table must surface immediately, not at first write.
ZONES = _load_zones()


def _zone_base(zone: str, root):
    """The base root a zone's declared paths resolve against — bin vs project per
    the two-root binding. See the module docstring for the self-host vs global
    contract."""
    import harness_paths
    if not os.environ.get("HARNESS_BIN_ROOT"):
        # Self-host / legacy: honor the caller's explicit root (bin == project),
        # falling back to bin_root() when none was passed. Preserves every
        # existing caller/test byte-for-byte.
        return Path(root).resolve() if root is not None else harness_paths.bin_root()
    # Global layout: fs_guard picks the base per zone, authoritative over `root`.
    if zone in _BIN_ZONES:
        return harness_paths.bin_root()
    dr = harness_paths.data_root()
    if harness_paths.data_root_unresolved(dr):
        raise FenceError(
            "zone %r needs a project root but none resolved (CLAUDE_PROJECT_DIR "
            "unset under a global bin) — refusing to widen the fence to the bin" % zone)
    return dr.parent


def allowed_roots(zone: str, root) -> list:
    """Resolved allowed write roots for `zone` under repo `root`.

    Zone roots are declared repo-relative; a declared root that resolves
    OUTSIDE the repo root (absolute path — pathlib drops `base` when joining
    one — or `../` traversal) would silently widen the fence to anywhere on
    the filesystem, so it raises instead of being honored."""
    if zone not in ZONES:
        raise FenceError(
            "unknown zone %r; known zones: %s" % (zone, sorted(ZONES))
        )
    base = Path(root).resolve()
    out = []
    for r in ZONES[zone]:
        resolved = (base / r).resolve()
        if resolved == base or not resolved.is_relative_to(base):
            raise FenceError(
                "zone %r declares root %r which resolves outside the repo "
                "root %s — zone roots must stay repo-relative; fix "
                "harness/data/ownership.yaml" % (zone, r, base)
            )
        out.append(resolved)
    return out


def assert_under(path, zone: str, root=None) -> Path:
    """Return the resolved `path` if contained under one of `zone`'s roots,
    else raise FenceError. Raises BEFORE any write, so a blocked target never
    touches disk.

    `path` may be relative to the zone's base root or absolute; both are
    resolved (collapsing `..`, following symlinks on existing components). The
    boundary directory itself counts as in-fence. The base root is bound per zone
    (project vs bin); an explicit `root` is honored only under a self-hosted
    layout — see the module docstring.
    """
    base = _zone_base(zone, root)
    roots = allowed_roots(zone, base)

    target = Path(path)
    if not target.is_absolute():
        target = Path(base) / target
    resolved = target.resolve(strict=False)

    for r in roots:
        if resolved == r or resolved.is_relative_to(r):
            return resolved

    pretty = ", ".join(str(r) for r in roots)
    raise FenceError(
        "refusing to write outside the %r zone: %s is not under any of [%s]"
        % (zone, resolved, pretty)
    )
