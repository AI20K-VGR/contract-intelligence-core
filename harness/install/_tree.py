#!/usr/bin/env python3
"""_tree.py — copy/manifest engine for the installer (extracted from install.py).

The git-vs-manifest file-set resolution, the path-escape backstop, the copy
loop, the omitted-skill record, and orphan pruning. install.py re-exports these
names, so callers and tests that reach them through the `install` module see no
change.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath

_HERE = Path(__file__).resolve().parent
_SCRIPTS = _HERE.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import verify_install  # noqa: E402
from _errors import InstallError  # noqa: E402


def _manifest_harness_files(source_root: Path) -> list:
    """The shipped file list straight from manifest.json — the fallback when the
    source is not a git work tree (an extracted bundle has no .git). The manifest
    enumerates exactly the tracked harness/ set, so this matches the git path."""
    manifest = Path(source_root) / "harness" / "manifest.json"
    if not manifest.is_file():
        raise InstallError(
            "%s has no .git and no harness/manifest.json — not an installable "
            "harness tree. Point --source at an extracted bundle or the harness "
            "repo." % source_root)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    rels = [rel for rel in data.get("files", {}) if rel.startswith("harness/")]
    # manifest.json is excluded from its own hash map but IS tracked (the git
    # path copies it) and the target needs it to verify — add it back so the
    # bundle and the git source install the same set.
    rels.append("harness/manifest.json")
    # release.json is excluded from the integrity manifest (kit_digest = sha256 of
    # manifest.json, so listing it there is circular) but the bundle ships it and
    # the target needs it, or an installed `hs version` falls back to 0.0.0-dev.
    # The git path copies it for free (it is tracked); add it back on the
    # bundle/manifest path when present. The .is_file guard keeps pre-fix bundles
    # that lack it installable.
    if (Path(source_root) / "harness" / "release.json").is_file():
        rels.append("harness/release.json")
    return rels


def _tracked_harness_files(source_root: Path) -> list:
    """Files to copy, preferring git (the dev/dogfood source) and falling back to
    manifest.json. The fallback fires in two cases: (1) no git work tree — an
    extracted bundle has no .git, so `git ls-files` errors; (2) a git work tree
    whose harness/ is untracked — the bundle was extracted into an existing repo
    (or the suite re-installs from a freshly installed copy), so `git ls-files`
    exits 0 with NO output. In both, the manifest is the authoritative file set;
    an empty git listing must not collapse the install to zero files."""
    try:
        # Mirror build_manifest.tracked_harness_files exactly: -z (NUL-delimited)
        # + core.quotepath=false keep non-ASCII names literal. The default
        # quotepath C-quotes such a name, so the install set and the manifest set
        # would disagree on it — a file the manifest covers but the install never
        # copies (silent drift). Split on NUL, not lines, to match.
        out = subprocess.run(
            ["git", "-C", str(source_root), "-c", "core.quotepath=false",
             "ls-files", "-z", "--", "harness/"],
            capture_output=True, text=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return _manifest_harness_files(source_root)
    files = [l for l in out.stdout.split("\0") if l.strip()]
    return files or _manifest_harness_files(source_root)


def _harness_is_tracked(source_root: Path) -> bool:
    """True if harness/ is git-tracked at source_root — the real in-repo dev
    (dogfood) source, where source == target is a legitimate copy no-op. False
    when git is absent or harness/ is untracked/ignored: the signature of a release
    bundle unpacked INSIDE the target repo, where source == target must NOT
    silently skip the copy and install nothing."""
    try:
        out = subprocess.run(
            ["git", "-C", str(source_root), "ls-files", "--", "harness/"],
            capture_output=True, text=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
    return bool(out.stdout.strip())


def _rel_escapes(rel: str) -> bool:
    """True if a manifest/listing path is absolute or climbs out of its root via
    `..`. git ls-files never emits these; the manifest fallback is attacker-
    influenced (a crafted bundle), so `harness/../../tmp/evil` must be refused
    before it is joined to the target and copied — otherwise it writes outside
    the install target (arbitrary write). Paths are posix-style in the manifest."""
    p = PurePosixPath(rel)
    return p.is_absolute() or ".." in p.parts


_SKILLS_PREFIX = "harness/plugins/hs/skills/"
# The stash is the tracked off-skill sibling of skills/ — the SAME location
# `hs-cli skills --enable` restores from, and one verify_install already excludes
# from the orphan/manifest seam, so a stashed skill passes --strict and round-trips
# without the source tree.
_STASH_PREFIX = "harness/plugins/hs/disabled-skills/"

# Prefixes NEVER shipped into an install target — the engine's own dev/CI test
# tree. It is authored against the full dev source (all skills present, dev-only
# docs/CI files), so it cannot pass against a default-off install and only
# produces guaranteed false failures there; an adopter verifies integrity via
# verify_install + the e2e slice, not this pytest suite. Mirrors the courier's
# _DROP_PREFIXES (courier_tree.py) — dropped from BOTH the copy and the target
# manifest so verify_install --strict stays clean.
_INSTALL_DROP_PREFIXES = ("harness/tests/",)


def _copy_tree(source_root: Path, target_root: Path, dry_run: bool,
               omitted_skills=frozenset()) -> str:
    rels = _tracked_harness_files(source_root)
    import omit_record
    omit_prefixes = omit_record.skill_dir_prefixes(omitted_skills)
    copied = 0
    omitted_n = 0
    stashed_n = 0
    dropped_n = 0
    for rel in rels:
        # Never ship the engine's dev/CI test tree into a target (see
        # _INSTALL_DROP_PREFIXES). Dropped before the omit/copy logic; the
        # target manifest is filtered to match in _finalize_install_manifest.
        if rel.startswith(_INSTALL_DROP_PREFIXES):
            dropped_n += 1
            continue
        # dir-omit disable: a deselected skill is NOT copied into the live skills/
        # tree, so it does not load — but its files ARE copied into the target stash
        # (harness/plugins/hs/disabled-skills/<skill>/) so hs:use can run it and
        # `hs-cli skills --enable` can restore it WITHOUT the source tree (the
        # fresh-install survival path). The verify_install omit-seam reads the
        # recorded list so the skills/ absence is not drift; verify already excludes
        # the disabled-skills stash from the orphan/manifest check, so the copies are
        # not orphans. The spine core is never omitted, so no spine dir is moved.
        if omit_prefixes and rel.startswith(omit_prefixes):
            omitted_n += 1
            if not dry_run and rel.startswith(_SKILLS_PREFIX):
                src = source_root / rel
                if src.is_file():
                    stash_rel = _STASH_PREFIX + rel[len(_SKILLS_PREFIX):]
                    dst = target_root / stash_rel
                    try:
                        dst.resolve().relative_to(target_root.resolve())
                    except (ValueError, OSError):
                        raise InstallError(
                            "refusing to stash a path that escapes the target: %r"
                            % stash_rel)
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    stashed_n += 1
            continue
        # Containment backstop: a crafted bundle manifest could list a path that
        # escapes the target; reject it before any mkdir/copy (single enforcement
        # point covering both the git and manifest file sources).
        if _rel_escapes(rel):
            raise InstallError(
                "refusing to install path that escapes the target: %r — "
                "harness/ paths must stay inside the target (a bundle manifest "
                "may be crafted)" % rel)
        src = source_root / rel
        if not src.is_file():
            continue  # tracked-but-deleted — verify's job, not ours
        copied += 1
        if not dry_run:
            dst = target_root / rel
            try:
                dst.resolve().relative_to(target_root.resolve())
            except (ValueError, OSError):
                raise InstallError(
                    "refusing to install path that escapes the target via "
                    "symlink: %r" % rel)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    msg = "copy harness/ tree (%d tracked files" % copied
    if omitted_n:
        msg += ", %d files omitted by skill selection" % omitted_n
        if stashed_n:
            msg += " (%d copied to stash)" % stashed_n
    if dropped_n:
        msg += ", %d dev/CI test files dropped" % dropped_n
    return msg + ")"


def _finalize_install_manifest(target_root: Path, result, dry_run: bool) -> None:
    """Drop the never-shipped test entries from the TARGET's manifest.json and
    re-stamp release.json's kit_digest to the filtered manifest, so the shipped
    tree and its integrity stamp agree (verify_install --strict reports neither a
    missing test file nor a kit_digest mismatch). Mirrors the courier's
    _finalize_engine_manifest. No-op when the manifest is absent (a partial tree
    is verify_install's job to name) or nothing was dropped (idempotent)."""
    manifest_path = target_root / "harness" / "manifest.json"
    if dry_run or not manifest_path.is_file():
        return
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return  # verify_install reports the unreadable manifest
    if not isinstance(data, dict) or not isinstance(data.get("files"), dict):
        return
    files = data["files"]
    kept = {rel: h for rel, h in files.items()
            if not rel.startswith(_INSTALL_DROP_PREFIXES)}
    if len(kept) == len(files):
        return  # nothing dropped — idempotent
    data["files"] = kept
    from build_manifest import serialize_manifest
    manifest_path.write_text(serialize_manifest(data), encoding="utf-8")
    result["actions"].append(
        "finalize target manifest (drop %d dev/CI test entries)"
        % (len(files) - len(kept)))
    # Re-point release.json's kit_digest at the filtered manifest (compute_kit_digest
    # reads <root>/harness/manifest.json). Absent release.json → nothing to re-stamp.
    release_path = target_root / "harness" / "release.json"
    if release_path.is_file():
        try:
            rel = json.loads(release_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return
        if isinstance(rel, dict):
            from harness_release import compute_kit_digest
            rel["kit_digest"] = compute_kit_digest(target_root)
            rel["manifest_files_count"] = len(kept)
            release_path.write_text(json.dumps(rel, indent=2) + "\n",
                                    encoding="utf-8")


def _write_omitted_skills(target_root: Path, omitted, result, dry_run) -> None:
    """Record the install-time omitted skills so verify_install's seam excludes
    them and hs-cli can later re-enable. Machine-written JSON under harness/state/
    (gitignored, never in the manifest — so the record itself is not an orphan)."""
    if dry_run:
        result["actions"].append(
            "skills: would omit %d (%s) (dry-run)"
            % (len(omitted), ", ".join(sorted(omitted)) or "none"))
        return
    import omit_record
    omit_record.write_omitted(target_root, omitted)
    result["actions"].append(
        "skills: omitted %d (%s)" % (len(omitted), ", ".join(sorted(omitted))))


def _prune_orphans(target_root, result, dry_run):
    """Remove harness/ files present on disk but absent from the manifest — the
    stale copies a reinstall/upgrade leaves when the shipped set shrinks. Only
    runs behind --prune (an explicit opt-in, since a deployer may legitimately
    drop extra files under harness/). The orphan set is verify_install's single
    source of truth (it already excludes the gitignored harness/state/)."""
    orphans = verify_install.orphan_problems(target_root)
    if not orphans:
        result["actions"].append("prune: no orphan files")
        return
    for rel, _prob in orphans:
        if dry_run:
            result["actions"].append("prune (dry-run): would remove %s" % rel)
            continue
        try:
            (target_root / rel).unlink()
            result["actions"].append("prune: removed orphan %s" % rel)
        except OSError as e:  # noqa: BLE001 — a file we could not remove is a warning
            result["warnings"].append("could not prune %s (%s)" % (rel, e))


def _remove_omitted_skill_dirs(target_root, omitted_skills, result, dry_run):
    """On a re-install that narrows the selection, an omitted skill's dir may linger
    in the live skills/ tree from a wider prior install. MOVE it into the stash
    (harness/plugins/hs/disabled-skills/<skill>/ — the shipped stash, NOT the
    gitignored harness/state/) instead of deleting it, so it stops
    loading yet stays reachable via hs:use + `hs-cli skills --enable` — the same
    survival path a fresh default-off install gets. Containment-guarded to the skills
    tree; a no-op under dry_run and for a fresh install (the dir was never copied)."""
    if not omitted_skills:
        return
    skills_root = (target_root / "harness" / "plugins" / "hs" / "skills")
    stash_root = (target_root / "harness" / "plugins" / "hs" / "disabled-skills")
    base = skills_root.resolve()
    moved = []
    for skill in sorted(omitted_skills):
        d = skills_root / skill
        try:
            d.resolve().relative_to(base)
        except (ValueError, OSError):
            continue  # never touch outside the skills tree
        if d.is_dir():
            if not dry_run:
                dst = stash_root / skill
                # The live dir is the current install's copy — it wins. Drop any
                # stale prior stash copy first so a partial/old one can't shadow it.
                if dst.exists():
                    shutil.rmtree(dst, ignore_errors=True)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(d), str(dst))
            moved.append(skill)
    if moved:
        result["actions"].append(
            "%smoved %d omitted skill dir(s) to the stash (re-install narrowing): %s"
            % ("(dry-run) " if dry_run else "", len(moved), ", ".join(moved)))
