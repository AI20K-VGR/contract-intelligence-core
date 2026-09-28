#!/usr/bin/env python3
"""build_manifest.py — write harness/manifest.json: sha256 per file.

Coverage rule: hash ONLY git-tracked files under harness/ — generated
state, RUN-LOG and untracked junk must not poison verify --strict — and never
manifest.json itself (a self-hash is unstable by construction).

THREE SOURCES, and picking the wrong one is a real defect this file has already
caused. `build` hashes the WORKING TREE, which is correct exactly when the worktree
is what you are about to commit. Split one worktree across several commits and it
stops being true: at batch k the worktree already carries batches k+1..n, so the
manifest stamps hashes of content that commit does not contain. Measured over 32
consecutive commits, the manifest was wrong-then-right-then-wrong in a sawtooth,
peaking at 12 missing files and 73 wrong hashes, and every test stayed green.

Nothing caught it because `verify_install --strict` compares the manifest against
the worktree — the same tree it was just built from — so it agrees with itself
however far both have drifted from the commit. Two inputs sharing an origin cannot
separate each other.

    build(root)                  hash the worktree        (default; single-commit flow)
    build_from_index(root)       hash the staged blobs    (--from-index; split commits)
    verify_commit(root, rev)     re-derive a commit's manifest from that commit's own
                                 tree and diff it against the manifest the commit carries

Usage:
    python3 harness/scripts/build_manifest.py [--root <repo-root>]
    python3 harness/scripts/build_manifest.py --from-index
    python3 harness/scripts/build_manifest.py --verify-commit HEAD
"""

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import sys
from pathlib import Path

MANIFEST_REL = "harness/manifest.json"
# release.json is the version identity (version + channel + kit_digest), kept
# SEPARATE from the pure integrity manifest: hashing it here would make
# the manifest churn on every version bump AND be circular — release.json holds
# kit_digest = sha256(manifest.json). Excluded like manifest.json's self-hash.
RELEASE_REL = "harness/release.json"


def tracked_harness_files(root: Path) -> list:
    """Git-tracked paths under harness/, relative to repo root.

    `-z` (NUL-delimited) + core.quotepath=false keep non-ASCII filenames
    literal: under the default quotepath, git C-quotes such a name
    (``"harness/caf\\303\\251.md"``), which then misses on disk and is silently
    dropped from the manifest — leaving drift on it undetectable.
    """
    out = subprocess.run(
        ["git", "-C", str(root), "-c", "core.quotepath=false",
         "ls-files", "-z", "--", "harness/"],
        capture_output=True, text=True, check=True,
    )
    return [l for l in out.stdout.split("\0")
            if l.strip() and l not in (MANIFEST_REL, RELEASE_REL)]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def build(root: Path) -> dict:
    files = {}
    for rel in sorted(tracked_harness_files(root)):
        p = root / rel
        if p.is_file():  # tracked-but-deleted paths are verify's job, not ours
            files[rel] = sha256_file(p)
    # No wall-clock field: the manifest is a content-integrity map, so an
    # unchanged tree must rebuild to byte-identical output (no diff churn).
    return {"files": files}


def _git_bytes(root: Path, *args: str):
    """Run git under `root` and return raw stdout, or None on a non-zero exit.

    Bytes, not text: these carry file contents, and decoding them would change the
    hash of anything that is not valid UTF-8.
    """
    out = subprocess.run(["git", "-C", str(root), "-c", "core.quotepath=false", *args],
                         capture_output=True)
    return out.stdout if out.returncode == 0 else None


def build_from_index(root: Path) -> dict:
    """Hash the STAGED blobs — exactly the bytes the pending commit will carry.

    `git cat-file blob :<path>` reads the index entry, so a file edited on disk after
    being staged hashes to its staged content, which is the whole point. A path that
    cannot be read (staged-deleted, never added) is skipped rather than guessed at:
    the manifest describes what the commit HAS.
    """
    files = {}
    for rel in sorted(tracked_harness_files(root)):
        blob = _git_bytes(root, "cat-file", "blob", ":" + rel)
        if blob is not None:
            files[rel] = hashlib.sha256(blob).hexdigest()
    return {"files": files}


def commit_manifest_files(root: Path, rev: str) -> dict:
    """The manifest as it exists AT `rev` — read from the commit, never from disk."""
    blob = _git_bytes(root, "show", "%s:%s" % (rev, MANIFEST_REL))
    if blob is None:
        return {}
    try:
        data = json.loads(blob.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return {}
    # A manifest that parses to a list, a string, or null is corrupt, not empty. `.get`
    # on it raises AttributeError, which is NOT in the except above — so it escapes and
    # takes the whole CI step down at a line that says nothing about manifests. Returning
    # {} keeps the failure where it belongs: every tracked file reads as `missing`, the
    # verdict is a loud, specific NO about this commit's manifest, and the caller's report
    # names the files.
    if not isinstance(data, dict):
        return {}
    files = data.get("files", {})
    return files if isinstance(files, dict) else {}


def verify_commit(root: Path, rev: str = "HEAD") -> dict:
    """Does `rev`'s manifest describe `rev`'s own tree?

    Both sides come from the commit — the file list from `ls-tree`, the contents from
    `cat-file`, the manifest from `show`. The worktree is never consulted, which is the
    one thing `verify_install --strict` cannot say for itself.

    Reports `missing` (tracked at the commit, absent from its manifest) and `wrong`
    (present but hashed differently) separately: they fail for different reasons and a
    single count hides which.
    """
    root = Path(root)
    listing = _git_bytes(root, "ls-tree", "-r", "--name-only", rev, "--", "harness/")
    if listing is None:
        raise RuntimeError("cannot read tree at %s" % rev)
    tracked = [l for l in listing.decode("utf-8", "replace").split("\n")
               if l.strip() and l not in (MANIFEST_REL, RELEASE_REL)]
    # Zero tracked files is UNMEASURABLE, never a pass. `ok` below is `not missing and
    # not wrong`, which is True over two empty lists — so a rev whose tree carries no
    # harness/ at all verifies clean and exits 0. Every way the tree can go absent (a
    # shallow or partial checkout, a rename, the wrong rev) then reads as a passing
    # integrity check. Refusing here is the same call the coverage gate makes on an
    # empty group: a gate that cannot see its subject says so.
    if not tracked:
        raise RuntimeError(
            "no harness/ files tracked at %s — nothing to verify. A tree this gate "
            "cannot see is not a tree it has cleared; check the rev and the checkout "
            "depth." % rev)

    declared = commit_manifest_files(root, rev)
    missing, wrong = [], []
    for rel in sorted(tracked):
        if rel not in declared:
            missing.append(rel)
            continue
        blob = _git_bytes(root, "cat-file", "blob", "%s:%s" % (rev, rel))
        if blob is None or hashlib.sha256(blob).hexdigest() != declared[rel]:
            wrong.append(rel)
    # The other direction. Walking only the tree asks "does the manifest know this file"
    # and never "does this file still exist" — so a SURPLUS entry verifies clean. That is
    # the same sawtooth from the other side: at batch k the manifest already declares
    # batch k+1's files while the commit carries none of them. Measured: a commit with one
    # file and a manifest declaring two returned ok:true, on the path release.yml runs
    # before a tag, which cannot be taken back.
    surplus = sorted(set(declared) - set(tracked))
    return {
        "ok": not missing and not wrong and not surplus,
        "rev": rev,
        "counted": len(tracked),
        "missing": missing,
        "wrong": wrong,
        "surplus": surplus,
    }


def serialize_manifest(manifest: dict) -> str:
    """Canonical on-disk manifest text — the ONE place the byte format lives.
    pack.py re-serializes the scrubbed-team manifest and MUST match this exactly,
    or a fresh bundle extract drifts against its own manifest. indent=2 +
    sort_keys + trailing newline = stable, diff-free rebuilds."""
    return json.dumps(manifest, indent=2, sort_keys=True) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".", help="repo root (default: cwd)")
    ap.add_argument("--from-index", action="store_true",
                    help="hash staged blobs instead of the worktree — required when one "
                         "worktree is being split across several commits")
    ap.add_argument("--verify-commit", metavar="REV",
                    help="check that REV's manifest describes REV's own tree; exit 1 if not")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()

    # `is not None`, not truthiness: `--verify-commit ""` is falsy, and falling through to
    # the build branch would overwrite the integrity map and exit 0 for a check that never
    # ran. A CI line spelled `--verify-commit "$REV"` with REV unset is exactly that.
    if args.verify_commit is not None:
        if not args.verify_commit.strip():
            ap.error("--verify-commit needs a rev; got an empty string")
        res = verify_commit(root, args.verify_commit)
        print(json.dumps(res, indent=2, sort_keys=True))
        return 0 if res["ok"] else 1

    manifest = build_from_index(root) if args.from_index else build(root)
    out = root / MANIFEST_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    # Write through a temp file in the SAME directory, then rename. The manifest is this
    # harness's integrity map, so the window where it is half-written is a window where
    # every consumer reads a file that describes nothing. `verify_install` already handles
    # a truncated manifest without crashing, which is why this is a small fix rather than
    # an urgent one — but the cost of closing it is a rename, and the alternative is that
    # an interrupted build leaves the check that guards every other file unusable.
    fd, tmp = tempfile.mkstemp(dir=str(out.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(serialize_manifest(manifest))
        # mkstemp creates 0600 and os.replace keeps the SOURCE mode, so the atomic write
        # silently narrowed the manifest from world-readable to owner-only. The installer
        # copies it with copy2, which preserves the mode — a per-project install from a
        # dev tree then ships an integrity map the next user cannot read, failing far from
        # here. Apply the process umask rather than a flat 0644: this file is public data,
        # but the deployer's umask still decides how public.
        umask = os.umask(0)
        os.umask(umask)
        os.chmod(tmp, 0o666 & ~umask)
        os.replace(tmp, out)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    print("manifest%s: %d files -> %s"
          % ("(index)" if args.from_index else "", len(manifest["files"]), out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
