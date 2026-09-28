#!/usr/bin/env python3
"""courier_tree.py — build the plugin *courier* tree from a scrubbed pack tarball.

The courier is the cache payload a Claude Code marketplace ships: a thin plugin
whose job is to CARRY the engine to the machine, not to run skills from the cache.
Its shape is:

    <out>/.claude-plugin/plugin.json   # name "harness", version from release.json
    <out>/bin/                         # dispatcher lives here (filled in phase 3)
    <out>/engine/harness/...           # the engine, copied to the stable home by setup

INPUT CONTRACT (red-team F1, enforced by mechanism, not discipline): the ONLY
accepted input is a tarball produced by release/pack.build_tarball — which has
ALREADY restored the protective protected-branches floor and seeded LESSONS.md.
Handing this builder the live repo directory is REFUSED: a dev tree carries an
empty floor / accumulated LESSONS entries that must never reach a published
payload. Reading a tarball (already scrubbed) is the only path in.

The engine's own test tree (harness/tests/**) and any stashed disabled skills
(harness/plugins/hs/disabled-skills/**) are dropped from the courier — they are
dev/CI weight, not runtime.
"""
import argparse
import json
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve()
_SCRIPTS = _HERE.parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import harness_paths  # noqa: E402
from build_manifest import serialize_manifest  # noqa: E402
from harness_release import compute_kit_digest  # noqa: E402

# Members under these prefixes never ship in the courier payload — dev/CI weight,
# not runtime. harness/e2e/ carries the slice scripts + a fixture-mini tree that
# includes a nested plans/ dir (which the publish leak-scan's top-level plans/ gate
# would not see), so it must not ship.
_DROP_PREFIXES = (
    "harness/tests/",
    "harness/e2e/",
    "harness/plugins/hs/disabled-skills/",
)
# Defensive: dev/runtime noise that should never be in a manifest tarball anyway.
_DROP_SEGMENTS = ("__pycache__", "harness/state/")

_RELEASE_MEMBER = "harness/release.json"
_MARKER_REL = Path(".claude-plugin") / "plugin.json"
_PAYLOAD_SLOTS = ("engine", "bin", ".claude-plugin")


class CourierError(ValueError):
    """Actionable, caller-facing failure — never a raw traceback."""


def _owns_out(out: Path) -> bool:
    """True when `out` already carries OUR ownership marker (a prior build's
    <out>/.claude-plugin/plugin.json with name=='harness') — safe to idempotently
    rmtree + recreate the three payload slots. `--out` is free-form operator argv
    (F-red-team L7-05): the only prior guard rejected a path INSIDE the repo, so a
    typo like `--out ~/.local` walked straight into `shutil.rmtree(~/.local/bin)`
    with no check that ~/.local/bin was ever ours. A marker-less `out` that already
    has one of the payload slot names present is presumed to be someone/something
    ELSE's directory, not a prior courier build."""
    marker = out / _MARKER_REL
    if not marker.is_file():
        return False
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return False
    return isinstance(data, dict) and data.get("name") == "harness"


def _safe_members(tar: tarfile.TarFile):
    """Yield only regular-file members with a repo-relative, traversal-free name.
    Rejects absolute paths and any '..' component (a poisoned tarball)."""
    for m in tar.getmembers():
        if not m.isfile():
            continue
        name = m.name
        p = Path(name)
        # `Path("").parts == Path(".").parts == ()` — an empty/dot member name would
        # collapse `stage / name` onto the staging dir and make write_bytes() raise a
        # raw IsADirectoryError; reject it as unsafe (a poisoned tarball).
        if not p.parts or p.is_absolute() or ".." in p.parts:
            raise CourierError(
                "refusing tarball member with unsafe path: %r" % name)
        yield m


def _dropped(rel: str) -> bool:
    if any(rel.startswith(pref) for pref in _DROP_PREFIXES):
        return True
    return any(seg in rel for seg in _DROP_SEGMENTS)


def _assert_out_outside_repo(out: Path, repo_root: Path) -> None:
    out_r = out.resolve()
    repo_r = repo_root.resolve()
    try:
        out_r.relative_to(repo_r)
    except ValueError:
        return  # out is outside repo_root — good
    raise CourierError(
        "refusing --out %s: it is inside the repo %s (the courier must never "
        "self-nest into its own source tree)" % (out_r, repo_r))


def _finalize_engine_manifest(engine: Path) -> None:
    """Drop the dropped-prefix entries from the engine's manifest.json and
    re-stamp release.json's kit_digest to the filtered manifest. ``engine`` is
    the engine's harness/ dir."""
    manifest_path = engine / "manifest.json"
    if not manifest_path.is_file():
        raise CourierError("engine is missing harness/manifest.json")
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except ValueError as e:
        raise CourierError("engine manifest.json is not valid JSON: %s" % e)
    # A valid-JSON but wrong-SHAPE manifest (a top-level list, or a non-object `files`)
    # would raise a raw AttributeError on .get()/.items() — the one poisoned-manifest
    # vector left unguarded. Fail loud with the module's actionable error instead.
    if not isinstance(data, dict):
        raise CourierError(
            "engine manifest.json is not a JSON object (got %s)" % type(data).__name__)
    files = data.get("files", {})
    if not isinstance(files, dict):
        raise CourierError(
            "engine manifest 'files' is not a JSON object (got %s)" % type(files).__name__)
    kept = {rel: h for rel, h in files.items() if not _dropped(rel)}
    # Reject a traversal/absolute manifest KEY: verify_install resolves `root / rel`,
    # so a key like `harness/../../etc/hostname` would make it hash a file OUTSIDE the
    # engine tree. _safe_members guards member NAMES; this guards manifest KEYS.
    for rel in kept:
        pr = Path(rel)
        if pr.is_absolute() or ".." in pr.parts:
            raise CourierError(
                "engine manifest has an unsafe (traversal/absolute) path key: %r" % rel)
    # Every KEPT manifest file must actually be on disk. A poisoned/malformed tarball
    # can pack a manifest-listed path as a symlink/hardlink (dropped by _safe_members)
    # or omit it — leaving the manifest lying while kit_digest is re-stamped over it.
    # Fail loud instead of shipping a manifest that does not match the tree.
    engine_root = engine.parent  # <out>/engine
    missing = [rel for rel in kept if not (engine_root / rel).is_file()]
    if missing:
        raise CourierError(
            "engine manifest lists %d file(s) not present on disk (poisoned/"
            "malformed tarball?): %s" % (len(missing), ", ".join(sorted(missing)[:5])))
    data["files"] = kept
    manifest_path.write_text(serialize_manifest(data), encoding="utf-8")

    release_path = engine / "release.json"
    if release_path.is_file():
        rel = json.loads(release_path.read_text(encoding="utf-8"))
        # compute_kit_digest reads <root>/harness/manifest.json
        rel["kit_digest"] = compute_kit_digest(engine.parent)
        rel["manifest_files_count"] = len(kept)
        release_path.write_text(json.dumps(rel, indent=2) + "\n", encoding="utf-8")


def _inject_dispatcher(out: Path) -> None:
    """Copy the engine's harness/bin/harness wrapper to <out>/bin/harness and
    mark it executable. Absent (older engine) → leave the bin/ slot empty; a
    courier without a dispatcher is degraded but not corrupt."""
    src = out / "engine" / "harness" / "bin" / "harness"
    if not src.is_file():
        return
    dst = out / "bin" / "harness"
    shutil.copy2(src, dst)
    dst.chmod(dst.stat().st_mode | 0o111)


def build_courier_tree(tarball: Path, out: Path, repo_root: Path = None) -> dict:
    """Build the courier tree at ``out`` from ``tarball``. Returns a small summary
    dict. Idempotent: an existing ``out`` payload is replaced, not merged."""
    tarball = Path(tarball)
    out = Path(out)
    if repo_root is None:
        repo_root = harness_paths.bin_root()
    repo_root = Path(repo_root)

    # F1 mechanism-lock: a directory (the live repo) is not a tarball.
    if tarball.is_dir():
        raise CourierError(
            "input %s is a directory — the courier builds ONLY from a scrubbed "
            "pack tarball, never from the live repo (red-team F1)" % tarball)
    if not tarball.is_file() or not tarfile.is_tarfile(tarball):
        raise CourierError(
            "input %s is not a readable tarball produced by pack.build_tarball"
            % tarball)

    _assert_out_outside_repo(out, repo_root)

    with tempfile.TemporaryDirectory() as td:
        stage = Path(td)
        with tarfile.open(tarball, mode="r:*") as tar:
            members = list(_safe_members(tar))
            names = {m.name for m in members}
            if _RELEASE_MEMBER not in names:
                raise CourierError(
                    "tarball is missing %s — cannot resolve the courier version "
                    "(is this a pack.build_tarball bundle?)" % _RELEASE_MEMBER)
            for m in members:
                if _dropped(m.name):
                    continue
                dest = stage / m.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                src = tar.extractfile(m)
                if src is None:
                    continue
                dest.write_bytes(src.read())

        try:
            release = json.loads((stage / _RELEASE_MEMBER).read_text(encoding="utf-8"))
        except ValueError as e:
            raise CourierError("release.json in the tarball is not valid JSON: %s" % e)
        if not isinstance(release, dict):
            raise CourierError("release.json in the tarball is not a JSON object")
        version = release.get("harness_version")
        if not version:
            raise CourierError(
                "release.json carries no harness_version — refusing to build a "
                "versionless courier")

        # Ownership gate BEFORE any destructive step: refuse to rmtree a payload
        # slot name that already exists but was not built by a prior run of this
        # tool (no marker => not provably ours).
        existing = [s for s in _PAYLOAD_SLOTS if (out / s).exists()]
        if existing and not _owns_out(out):
            raise CourierError(
                "refusing to build into %s: %s already exist(s) there but the dir "
                "carries no harness courier marker (%s) — this looks like an "
                "unrelated directory, not a prior courier build, and rebuilding "
                "would delete it. Point --out at an empty directory or one this "
                "tool already built." % (out, ", ".join(existing), _MARKER_REL))

        # Idempotent rebuild: clear the three payload slots we own.
        for slot in _PAYLOAD_SLOTS:
            tgt = out / slot
            if tgt.exists():
                shutil.rmtree(tgt)
        (out / "engine").mkdir(parents=True, exist_ok=True)
        (out / "bin").mkdir(parents=True, exist_ok=True)  # dispatcher lands here (phase 3)
        (out / ".claude-plugin").mkdir(parents=True, exist_ok=True)

        # engine := the staged harness/ tree (already drop-filtered)
        shutil.copytree(stage / "harness", out / "engine" / "harness")

        # The manifest was copied verbatim, so it still lists the dropped
        # tests/ + disabled-skills/ files — verify_install would then report them
        # missing. Filter those entries out (their hashes for KEPT files are
        # untouched) and re-point release.json's kit_digest at the filtered
        # manifest so the shipped tree and its integrity stamp agree.
        _finalize_engine_manifest(out / "engine" / "harness")

        # Inject the on-PATH dispatcher: the wrapper ships inside the engine at
        # harness/bin/harness; the courier surfaces it at <plugin>/bin/harness so
        # CC's plugin-bin PATH injection puts `harness` on PATH.
        _inject_dispatcher(out)

        plugin_json = {
            "name": "harness",
            "description": "Harness courier — carries the SDLC harness engine to "
                           "your machine; run `harness setup` to install it.",
            "version": version,
            "author": {"name": "Lucas Bui"},
            "license": "AGPL-3.0",
            "homepage": "https://github.com/hieubui2409/sdlc-harness",
        }
        (out / ".claude-plugin" / "plugin.json").write_text(
            json.dumps(plugin_json, indent=2) + "\n", encoding="utf-8")

    return {"out": str(out), "version": version,
            "engine": str(out / "engine" / "harness")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tarball", required=True,
                    help="path to a pack.build_tarball bundle (scrubbed)")
    ap.add_argument("--out", required=True,
                    help="output courier tree dir (must be OUTSIDE the repo)")
    ap.add_argument("--repo-root", default=None,
                    help="repo root the --out must not nest inside "
                         "(default: resolved bin root)")
    args = ap.parse_args(argv)
    try:
        summary = build_courier_tree(
            Path(args.tarball), Path(args.out),
            Path(args.repo_root) if args.repo_root else None)
    except CourierError as e:
        sys.stderr.write("courier_tree: %s\n" % e)
        return 2
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
