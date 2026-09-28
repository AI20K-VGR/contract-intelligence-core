#!/usr/bin/env python3
"""Place the harness where a second runtime reads it, per project.

The roots are MEASURED, never inferred — one per runtime, in
`harness/data/runtime-targets.yaml`, each with the control that came out negative
beside it. This module asks that table (through `_runtime_emit`) rather than naming
directories of its own, because a constant here is right for the runtime it was written
against and silently wrong for every other one: a file written to a path the runtime
never reads is still a file that got written, and the install still reports success.

Per project on purpose. Every runtime measured here also has a global home, and writing
there would change every project the user owns from inside one of them. The two runtimes
whose ONLY home is global are declared `scope: global` and refuse to install without the
user saying so for that machine.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "scripts"))

import artifact_io  # noqa: E402
import build_manifest  # noqa: E402 — reuse the tree's one hashing function
import skill_selection  # noqa: E402
import target_projection as tp  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _runtime_emit as _emit  # noqa: E402 — sibling placement resolver

# codex's own engine-root file. Declared here rather than in the table because it is a
# property of THIS wiring step (pinning the engine root through the runtime's env
# policy), not of the runtime's export surface; a runtime without one simply skips it.
CONFIG = ".codex/config.toml"
_ENGINE_ROOT_CONFIG = {"codex": CONFIG}
_ENV_HEADER = "[shell_environment_policy]"
# The block is written into a file the user owns, so it has to be removable. Markers
# give both halves: the write replaces its own block, the uninstall takes exactly that
# block out and leaves the rest of their config alone.
_ENV_BEGIN = ("# >>> harness engine root (generated; edits between markers are "
              "overwritten on reinstall) >>>")
_ENV_END = "# <<< harness engine root <<<"


def _env_block(target_root: Path) -> str:
    """The runtime's own seam for handing the engine its root.

    `hs-run` resolves the tree it answers for from the environment, falling back to a
    walk up from the working directory. Both fallback paths fail here, measured:

      - cwd OUTSIDE the project, no variable set: root resolves to the working
        directory's own ancestor and every skill in the project reads
        `target_unknown` — a wrong answer that at least announces itself.
      - cwd INSIDE the project but the shell carrying ANOTHER project's value: the
        engine answers for that other project, at the normal exit rung, with a state
        that looks entirely valid. Nothing in the output says which tree was read.

    The second is why this is written rather than left to the fallback. Pinning the
    value makes an inherited one irrelevant.

    Measured with a positive control: a value set here reaches the shell the model
    runs in, and it is read from the PROJECT's own config file, so nothing in the
    user's home directory is touched.
    """
    return (
        "%s\n"
        "# `hs-run` resolves the tree it answers for from this variable; without it\n"
        "# the engine answers for a parent directory and reports this project's own\n"
        "# skills as unknown.\n"
        "%s\n"
        'set = { HARNESS_DATA_ROOT = "%s/.harness" }\n'
        "%s"
        % (_ENV_BEGIN, _ENV_HEADER, str(target_root).rstrip("/"), _ENV_END))


def _write_env_config(runtime: str, target_root: Path, result: dict) -> None:
    """Put the engine-root block into the runtime's own config, between markers.

    Only a runtime that HAS such a file gets one. Writing a `config.toml` into a
    runtime that does not read one leaves a file nothing consults, which the next
    reader has to work out is inert.
    """
    rel = _ENGINE_ROOT_CONFIG.get(runtime)
    if not rel:
        return
    cfg = Path(target_root) / rel
    existing = cfg.read_text(encoding="utf-8") if cfg.is_file() else ""
    theirs = (artifact_io.splice_block(existing, "", _ENV_BEGIN, _ENV_END)
              if _ENV_BEGIN in existing else existing)
    if _ENV_HEADER in theirs:
        # The section cannot appear twice in one TOML file. Writing a second one
        # makes the config unparseable, which loses every setting in it — theirs
        # included — so this stops and says which line to add.
        result["warnings"].append(
            "%s: %s already declares %s, so the engine root was NOT written. Add "
            "`HARNESS_DATA_ROOT = \"%s/.harness\"` to that section yourself, or "
            "hs-run will answer for whichever tree the shell happens to name."
            % (runtime, cfg, _ENV_HEADER, str(target_root).rstrip("/")))
        return
    merged = artifact_io.splice_block(existing, _env_block(target_root),
                                      _ENV_BEGIN, _ENV_END)
    if merged != existing:
        cfg.parent.mkdir(parents=True, exist_ok=True)
        artifact_io.atomic_write_text(cfg, merged)
    result["actions"].append("wire %s (engine root)" % rel)


def _unwrite_env_config(runtime: str, target_root: Path) -> None:
    rel = _ENGINE_ROOT_CONFIG.get(runtime)
    cfg = (Path(target_root) / rel) if rel else None
    if cfg is None or not cfg.is_file():
        return
    text = cfg.read_text(encoding="utf-8")
    if _ENV_BEGIN not in text:
        return
    rest = artifact_io.splice_block(text, "", _ENV_BEGIN, _ENV_END).strip()
    if rest:
        artifact_io.atomic_write_text(cfg, rest + "\n")
        return
    cfg.unlink()   # a file that existed only to hold our block
    # And the directory that existed only to hold that file. An empty directory
    # carrying a runtime's name still answers "is this installed?" wrongly for
    # anything that looks before it looks inside.
    _prune_empty(cfg.parent, Path(target_root))


def _prune_empty(start: Path, stop: Path) -> None:
    d = start
    while d != stop and d.is_dir() and not any(d.iterdir()):
        d.rmdir()
        d = d.parent


def known_runtimes() -> list[str]:
    """Every runtime the capability table declares, minus the one we already are."""
    return sorted(t for t in tp.load_targets() if t != "claude-code")


def _merge_hooks(existing: dict, emitted: dict) -> dict:
    """Union the two registrations, keyed by (event, matcher), deduped by command.

    Order matters to nobody here and identity matters to everybody: two entries with
    the same command are the same registration written twice, and a runtime that runs
    both runs every gate twice.
    """
    out: dict = {}
    for source in (existing, emitted):
        for event, entries in ((source or {}).get("hooks") or {}).items():
            for entry in entries or []:
                key = (event, entry.get("matcher"))
                slot = out.setdefault(key, [])
                for hook in entry.get("hooks") or []:
                    if hook.get("command") not in {h.get("command") for h in slot}:
                        slot.append(hook)
    merged: dict = {}
    for (event, matcher), hooks in out.items():
        merged.setdefault(event, []).append({"matcher": matcher, "hooks": hooks})
    return {"hooks": merged}


# The ownership record for one runtime tree. A directory full of files says nothing
# about who put them there, and an uninstall that deleted a tree on the strength of its
# NAME would delete a `.omp/` the user filled themselves. Paths AND hashes: the path
# says "we wrote this", the hash says "and nobody has touched it since".
LEDGER_NAME = "ledger.json"

# The harness's own records for one runtime install: the operator notes, the
# degradation ledger, and the ownership record. Under the project data home rather
# than beside the user's files — they are the harness's account of what it did, not
# an input the runtime reads, and one runtime's declared root IS the project root.
RECORDS_REL = Path(".harness") / "runtimes"


def home_root(runtime: str) -> Path:
    """Where a home-scoped runtime keeps its own tree.

    Its own variable when it declares one — measured, one of the two resolves its
    home through `DSH_HOME` — and the user's home otherwise. Resolved from the
    environment rather than hardcoded so a test, a sandbox, or a user with a
    relocated home all land where that runtime actually reads.
    """
    env = (_emit.placement(runtime) or {}).get("home_env")
    if env and os.environ.get(env):
        return Path(os.environ[env]).expanduser()
    return Path(os.path.expanduser("~"))


def install_root(target_root, runtime: str) -> Path:
    """The root this runtime's files actually live under.

    ONE answer, because the install and the uninstall each used to derive it. `wire`
    redirected its whole target to the home for a home-scoped runtime and `unwire`
    was still handed the project root, so it looked for the ownership ledger in a
    directory the install never touched. A missing ledger is the ORDINARY answer for
    the eight runtimes not installed here, so it returned in silence: the operator
    was told the uninstall ran, and every file it wrote stayed in their home.
    """
    return home_root(runtime) if _emit.is_global(runtime) else Path(target_root)


def records_dir(target_root, runtime: str) -> Path:
    return Path(target_root) / RECORDS_REL / runtime


def ledger_path(target_root, runtime: str) -> Path:
    return records_dir(target_root, runtime) / LEDGER_NAME


def is_home_scoped(runtime: str) -> bool:
    """True when this runtime's files live in the user's home rather than a project."""
    return bool(_emit.is_global(runtime))


def installed_here(target_root, runtime: str) -> bool:
    """Whether an install of `runtime` reachable from `target_root` left a ledger."""
    return ledger_path(install_root(target_root, runtime), runtime).is_file()


def _write_ledger(target_root: Path, runtime: str, written, instructions) -> None:
    """Record every file this install wrote, by path AND hash.

    `written` is the list of destinations the placement step actually produced, so
    the ledger cannot name a file the install did not write. Deriving it instead by
    walking a directory is what let an install whose declared root was the project
    root claim 2688 files, the user's own among them — and the uninstall reads this
    to decide what to delete.
    """
    files = {}
    for dest, kind, cls in written:
        if dest.is_file():
            files[str(dest.relative_to(target_root))] = {
                "sha256": build_manifest.sha256_file(dest),
                "kind": kind, "class": cls}
    artifact_io.atomic_write_text(
        ledger_path(target_root, runtime),
        json.dumps({"target": runtime, "instructions": instructions, "files": files},
                   indent=2, sort_keys=True) + "\n")


def unwire(target_root, runtime: str, result: dict, dry_run: bool) -> None:
    """Remove what `wire` wrote for one runtime, and nothing else.

    Silent when this runtime was never installed here: an uninstall runs over every
    declared runtime, and a missing ledger is the ordinary answer for eight of nine.
    """
    target_root = install_root(target_root, runtime)
    ledger = ledger_path(target_root, runtime)
    if not ledger.is_file():
        return
    try:
        blob = json.loads(ledger.read_text(encoding="utf-8"))
    except ValueError:
        # Unreadable is not empty. Without the record there is no way to tell our
        # files from theirs, so nothing is removed and a human is told.
        result["warnings"].append(
            "%s: %s is not valid JSON, so the install was left in place — remove it "
            "by hand once you have checked what is in it." % (runtime, ledger))
        return
    if dry_run:
        result["actions"].append(
            "would remove %d file(s) of the %s install"
            % (len(blob.get("files") or {}), runtime))
        return
    kept, roots = [], set()
    for rel, rec in sorted((blob.get("files") or {}).items()):
        f = target_root / rel
        roots.add((target_root / rel).parent)
        if not f.is_file():
            continue
        # The record grew from a bare digest to a small object. Read both, because a
        # ledger written by an older install is still the only account of what that
        # install put in the user's tree, and refusing to read it would strand those
        # files with nothing able to remove them.
        digest = rec.get("sha256") if isinstance(rec, dict) else rec
        if build_manifest.sha256_file(f) != digest:
            kept.append(rel)   # theirs now — an edit is a decision, not a leftover
            continue
        f.unlink()
    # Empty directories, deepest first, and never the project root itself.
    for d in sorted(roots, key=lambda x: len(x.parts), reverse=True):
        _prune_empty(d, target_root)
    instructions = blob.get("instructions")
    if instructions:
        dest = target_root / instructions
        if dest.is_file():
            text = dest.read_text(encoding="utf-8")
            if tp.INSTRUCTIONS_BEGIN in text:
                # An empty block removes the markers with it, leaving the prose the
                # harness never owned exactly as the user wrote it.
                stripped = artifact_io.splice_block(
                    text, "", tp.INSTRUCTIONS_BEGIN, tp.INSTRUCTIONS_END).strip()
                artifact_io.atomic_write_text(dest, stripped + "\n" if stripped else "")
    _unwrite_env_config(runtime, target_root)
    shutil.rmtree(records_dir(target_root, runtime), ignore_errors=True)
    # And the shells those leave behind. A 0-byte instructions file the harness
    # created says "this project has instructions" to every reader and every runtime
    # that looks for one; an empty records directory is the same claim about an
    # install that is gone.
    if instructions:
        dest = target_root / instructions
        if dest.is_file() and not dest.read_text(encoding="utf-8").strip():
            dest.unlink()
    _prune_empty(records_dir(target_root, runtime).parent, target_root)
    if kept:
        result["warnings"].append(
            "%s: %d file(s) differ from what the install wrote and were kept: %s"
            % (runtime, len(kept), ", ".join(kept)))
    result["actions"].append("unwire %s" % runtime)


def wire(source_root, target_root, runtime: str, result: dict, dry_run: bool, *,
         allow_inert_gates: bool = False, skills=None, agents=None,
         allow_home: bool = False, engine_root=None) -> None:
    """Write `runtime`'s copy of the harness into `target_root`.

    Raises ValueError for a runtime the capability table does not declare — refusing a
    name is the only honest answer when the alternative is picking a near match and
    installing gates that were never measured against it.

    A refusal (a compliance gate that would register and never fire) is recorded in
    `result["refusals"]` and NOTHING is written, so a refused install cannot be
    mistaken for a partial one.
    """
    target_root = Path(target_root)
    targets = tp.load_targets()
    if runtime not in targets:
        raise ValueError(
            "unknown runtime %r — declared runtimes are: %s. A runtime is installable "
            "only once its capability table entry has been measured; there is no "
            "default to fall back on."
            % (runtime, ", ".join(sorted(targets))))

    proj = tp.project_target(runtime, targets=targets)
    if proj.refusals and not allow_inert_gates:
        result["refusals"].append(
            "%s: %d compliance gate(s) would register and never fire there, so "
            "nothing was written. Read them and pass allow_inert_gates once the loss "
            "is a decision: %s" % (runtime, len(proj.refusals),
                                   " | ".join(proj.refusals)))
        result["ok"] = False
        return

    if _emit.is_global(runtime):
        if not allow_home:
            result["refusals"].append(
                "%s installs into the user's home, which changes every project they "
                "own from inside one of them. Say so deliberately for this machine "
                "with --runtime-home %s; --runtime installs per project and will "
                "not write there." % (runtime, runtime))
            result["ok"] = False
            return
        # Consent given: the target of every write below is that runtime's own home,
        # not this project. Nothing is written into the project at all — a
        # home-scoped runtime reads none of it from there, so a copy would only
        # drift.
        target_root = install_root(target_root, runtime)
    elif allow_home:
        result["refusals"].append(
            "%s is a per-project runtime; --runtime-home would install it into the "
            "user's home, where it reads nothing. Use --runtime %s."
            % (runtime, runtime))
        result["ok"] = False
        return

    place = _emit.placement(runtime)
    hook_rel = place.get("hook_file")
    instructions = _emit.instructions_file(runtime)
    if dry_run:
        result["actions"].append(
            "would write %s (%s, agent roles, skills)%s for %s"
            % (", ".join(sorted(str(v) for k, v in place.items()
                                if k != "scope" and v)) or "nothing",
               "hooks" if hook_rel else "no hooks — none registrable",
               (" and %s" % instructions) if instructions else "", runtime))
        return

    if skills is None:
        # The ENABLED set, not the source catalog. A skill the user switched off must
        # not come back on because they installed for another runtime, and every extra
        # one is an entry injected into the model's list every turn. Nothing is lost:
        # the stash travels with the install and the off-skill door resolves there.
        skills = sorted(skill_selection.resolve_enabled(source_root=Path(source_root)))
    if agents is None:
        agents = sorted(f.stem for f in
                        (Path(source_root) / "harness/plugins/hs/agents").glob("*.md"))

    existing = {}
    hooks_file = (target_root / hook_rel) if hook_rel else None
    if hooks_file is not None and hooks_file.is_file():
        try:
            existing = json.loads(hooks_file.read_text(encoding="utf-8"))
        except ValueError:
            # Unreadable is not empty. Overwriting it would destroy a file we cannot
            # prove is ours, so stop and let a human look.
            result["refusals"].append(
                "%s: %s exists but is not valid JSON; refusing to overwrite it"
                % (runtime, hooks_file))
            result["ok"] = False
            return

    # Build the tree once, in a staging directory, then place each kind where the
    # TABLE says that runtime reads it. Deriving one directory and writing everything
    # under it put grok's skills in `.grok/hooks/skills`, which grok never reads, and
    # scattered a hookless runtime's tree through the project root.
    records = records_dir(target_root, runtime)
    staging = records / ".staging"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)
    tp.write_install(proj, staging, target_id=runtime, project_root=target_root,
                     engine_root=engine_root or target_root,
                     skills=skills, agents=agents)

    decl = (tp.load_targets()[runtime].get("agents") or {})
    # One staging entry may have MORE than one destination: a runtime measured here
    # reads its skills from two directories and gets 106 of them in each. Declaring
    # the second and writing only the first is the shape this table keeps producing
    # — a measurement taken and then dropped on the way out.
    # Each route also says WHAT the entry is and whether the runtime LOADS it. A path
    # and a hash answer "did we write this, untouched"; they do not answer "is this
    # live", and for the two targets that copy roles deliberately inert that is the
    # whole question. Both facts are known right here, at the moment of placing.
    routes = {
        "hooks.json": ([hook_rel], "hook", "native"),
        "skills": ([place.get("skills_dir"),
                    place.get("skills_dir_secondary")], "skill", "native"),
        (decl.get("role_dir") or "agents"): ([place.get("agents_dir")],
                                             "agent", "native"),
    }
    if place.get("rules_dir"):
        routes[Path(place["rules_dir"]).name] = ([place["rules_dir"]], "rule", "native")
    if decl.get("inert_sidecar"):
        # Measured: roles this runtime does not activate are parked in a sidecar at
        # the project root rather than in the live role directory, which is the point
        # of the sidecar. The directory carries OUR name: nothing reads it, so naming
        # it after the tool the shape was learned from would put someone else's brand
        # in a user's project for no functional reason.
        routes["harness-sidecar"] = (["harness-sidecar"], "agent", "inert")

    written = []
    for entry in sorted(staging.iterdir()):
        if instructions and entry.name == instructions:
            continue  # spliced below, into a file the harness does not own
        # Anything the table does not route is the harness's OWN record — the
        # operator notes and the degradation ledger. They belong with the records,
        # not among the user's files.
        route = routes.get(entry.name) or ([], None, None)
        rels = [r for r in route[0] if r]
        for dest in ([target_root / str(r).lstrip("~/") for r in rels]
                     or [records / entry.name]):
            dest.parent.mkdir(parents=True, exist_ok=True)
            if entry.is_dir():
                artifact_io.copy_tree(entry, dest)
                placed = [f for f in sorted(dest.rglob("*")) if f.is_file()]
            else:
                shutil.copyfile(entry, dest)
                placed = [dest]
            # The ledger means "files we put in the user's tree". Our own records are
            # not that: they live under the harness data home and the uninstall
            # removes that directory whole, so listing them here would only give the
            # hash check a second thing to disagree about.
            if rels:
                written += [(f, route[1], route[2]) for f in placed]

    if existing and hooks_file is not None:
        # Atomic: the file being replaced is the one carrying the user's own hooks, and
        # a partial write there is a config the runtime cannot parse — every gate off,
        # including the ones that were already theirs.
        artifact_io.atomic_write_text(
            hooks_file,
            json.dumps(_merge_hooks(existing, json.loads(
                hooks_file.read_text(encoding="utf-8"))), indent=2) + "\n")

    _write_env_config(runtime, target_root, result)

    emitted = (staging / instructions) if instructions else None
    if emitted is not None and emitted.is_file():
        # SPLICE, never move. A move onto an existing path replaces it, and the path
        # here is the file the user writes their own instructions in — measured, an
        # install for omp left zero lines of a project's hand-written AGENTS.md. The
        # block carries markers so prose outside them is preserved and a reinstall
        # replaces its own block instead of appending a second one.
        dest = target_root / instructions
        block = emitted.read_text(encoding="utf-8").strip()
        was = dest.read_text(encoding="utf-8") if dest.is_file() else ""
        # Another tool may already own a block in this same file. Say so: the splice
        # is safe either way because each side anchors on its own markers, but an
        # operator who does not know two tools write here will eventually hand-edit
        # one of the blocks and wonder which install undid it.
        marker = tp.foreign_block_marker(was)
        if marker:
            result["warnings"].append(
                "%s: %s already carries another tool's block (`%s`). The harness "
                "block is separate and neither deletes the other, but that file now "
                "has two owners." % (runtime, instructions, marker.strip()))
        merged = artifact_io.splice_block(was, block,
                                          tp.INSTRUCTIONS_BEGIN, tp.INSTRUCTIONS_END)
        if merged != was:
            artifact_io.atomic_write_text(dest, merged)

    shutil.rmtree(staging, ignore_errors=True)
    _write_ledger(target_root, runtime, written, instructions)
    result["actions"].append(
        "wire %s: %d file(s), %d skill(s), %d agent role(s)%s"
        % (runtime, len(written), len(skills), len(agents),
           (" + %s" % instructions) if instructions else ""))
    if not _emit.carries_gates(runtime):
        result["warnings"].append(
            "%s has no hook surface the harness can register on, so this install "
            "carries %s and NO enforceable "
            "gate. Nothing here is protecting the tree."
            % (runtime, tp._and_list(
                ["skills", "agent roles"]
                + (["project instructions"] if instructions else []))))
    if proj.refusals:
        result["warnings"].append(
            "%s: %d compliance gate(s) are NOT protecting this install; %s names "
            "them" % (runtime, len(proj.refusals),
                      records_dir(target_root, runtime) / "INSTALL.md"))
