#!/usr/bin/env python3
"""harness_release.py — harness version identity + kit-digest compute.

release.json (machine-written, git-tracked) carries the harness version that
provenance stamps consume. It is SEPARATE from manifest.json on purpose: the
manifest is a pure content-integrity map (no version/timestamp, byte-stable on
rebuild), this file is the version identity the release toolkit cuts. Keeping
them apart lets the manifest stay determinism-clean while the version moves.

kit_digest = sha256 of manifest.json = one fingerprint of the exact tree state
(the manifest already hashes every tracked file), pinnable even for an
unreleased dev checkout.

Readers (stamping, session summary) call read_release FRESH each time — never
cached — so an upgrade applied mid-session is reflected on artifacts written
afterward. On the dev channel the digest is recomputed live from the working
tree so a dev stamp never carries a stale commit-time digest.
"""

import json
import os
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import harness_paths  # noqa: E402
from build_manifest import MANIFEST_REL, sha256_file  # noqa: E402

RELEASE_REL = "harness/release.json"
DEV_VERSION = "0.0.0-dev"


def compute_kit_digest(root: Path) -> str:
    """sha256 of manifest.json — a single fingerprint of the whole tree state.

    Reuses build_manifest.sha256_file so the digest is taken over the exact
    bytes the manifest builder writes. Returns "" before the first manifest
    build (bootstrap), where there is nothing to fingerprint yet.
    """
    manifest = root / MANIFEST_REL
    return sha256_file(manifest) if manifest.is_file() else ""


def read_release(root: Path = None) -> dict:
    """The harness version identity, read fresh from release.json.

    Returns a pinned release dict as written when channel is a real release;
    falls back to a dev identity (version 0.0.0-dev) when the file is absent,
    unreadable, or malformed. On the dev channel — or when no digest is pinned —
    the kit_digest is recomputed live from the working tree so the stamp tracks
    the tree, not a stale commit. Never caches: a mid-session rewrite is seen on
    the next call.
    """
    root = root or harness_paths.root()
    path = root / RELEASE_REL
    rel = None
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("harness_version"):
                rel = data
        except (ValueError, OSError):
            rel = None  # malformed/unreadable → dev identity below
    if rel is None:
        rel = {"schema_version": "1.0", "harness_version": DEV_VERSION,
               "channel": "dev"}
    if rel.get("channel") == "dev" or not rel.get("kit_digest"):
        rel = {**rel, "kit_digest": compute_kit_digest(root)}
    return rel


def main(argv=None) -> int:
    """Print the resolved version identity as one JSON line (debug/CLI use)."""
    root = harness_paths.root()
    print(json.dumps(read_release(root), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
