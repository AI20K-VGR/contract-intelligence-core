#!/usr/bin/env python3
"""verify_install.py — compare files on disk against harness/manifest.json.

Fails LOUD per asset (R8 install drift): every drifted/missing file is named
individually — never a bare "mismatch". --strict exits non-zero on any drift;
without it the report still prints but exit is 0 (inspection mode).

Usage:
    python3 harness/scripts/verify_install.py [--root <repo-root>] [--strict]
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Same hashing as the builder — single source for the digest algorithm.
sys.path.append(str(Path(__file__).resolve().parent))
from build_manifest import MANIFEST_REL, sha256_file  # noqa: E402
import harness_release  # noqa: E402 — compute_kit_digest, shared with the stamper

# A hook command line names its script as harness/hooks/<name>.py. Parsed by
# pattern (not YAML) so verify stays dependency-free; hooks-registration.yaml is
# the installer's input — the one place a hook gets wired to a Claude Code event.
_HOOK_CMD_RE = re.compile(r"harness/hooks/([A-Za-z0-9_]+\.py)(?![A-Za-z0-9_])")


# The harness/data/*.yaml files a deploying team is EXPECTED to tune per target —
# the documented gate-input knobs (docs/harness/config-reference.md). An EXPLICIT allowlist, not
# a whole-directory glob: everything else under harness/data/ is harness-BEHAVIOR
# data (skill-deps = the skill->dep graph + 13-skill core-immutable set, the
# components install map, decomposition/route/observation tables) that stays
# integrity-LOCKED by the manifest — a drift there is corruption/tamper, not
# customization, and must fail --strict.
_LOCALIZED_DATA = frozenset((
    "component-policy.yaml", "cook.yaml", "critique.yaml",
    "guard-policy.yaml", "output.yaml", "ownership.yaml", "protected-branches.yaml",
    "skill-chains.yaml", "stage-policy.yaml",
    "terminal-voice.yaml",
))


def is_localized(rel: str) -> bool:
    """True for files a deploying team is EXPECTED to edit per target: the
    documented gate-input knobs under harness/data/ (reviewer roster, stage/guard
    policy, protected branches, voice knobs, output language, RBAC lanes — the
    _LOCALIZED_DATA allowlist) and the hook registration. They ship in the manifest
    as a baseline, but post-install divergence is customization, not integrity
    drift — gate config is tamper-visible via git, not integrity-locked by the
    manifest. Single source of truth shared with the installer's final verify (DRY).
    Code under harness/hooks, scripts, rules, skills AND harness-behavior data
    (skill-deps, components, decomposition-map, …) is NOT localized: it still fails
    --strict on any mismatch.

    harness/data/harness-hooks.yaml is localized too: it is the per-deployment
    hook enable/mode override file (the component projector writes enabled flags
    into it, and a deployer may flip a gate in an emergency). Like the other
    gate configs it is tamper-visible via git + the gate_skip trace, not
    integrity-locked by the manifest."""
    if rel in ("harness/install/hooks-registration.yaml",
               "harness/data/harness-hooks.yaml"):
        return True
    prefix = "harness/data/"
    if rel.startswith(prefix) and "/" not in rel[len(prefix):]:
        return rel[len(prefix):] in _LOCALIZED_DATA
    return False


def split_localized(problems: list) -> tuple:
    """Partition (rel, problem) tuples into (hard_drift, localized) by
    is_localized. The installer and the CLI both classify through this — one
    rule, two callers."""
    hard, localized = [], []
    for rel, prob in problems:
        (localized if is_localized(rel) else hard).append((rel, prob))
    return hard, localized


def _omitted_skill_prefixes(root: Path) -> tuple:
    """Skill-dir path prefixes the install deliberately omitted (the dir-omit
    disable for the collapsed single-hs plugin). Files under these prefixes are
    absent BY DESIGN, so the verify loop excludes them rather than reading their
    absence as drift. Sourced from the install-recorded list under harness/state/
    (machine-written, gitignored, never in the manifest). Missing or unreadable
    -> no omits, i.e. strict as before — a broken record never silently hides a
    real missing file."""
    import omit_record
    return omit_record.skill_dir_prefixes(omit_record.read_omitted(root))


def verify(root: Path) -> list:
    """Return list of (relpath, problem) tuples; empty = clean."""
    manifest_path = root / MANIFEST_REL
    if not manifest_path.is_file():
        return [(MANIFEST_REL, "manifest missing — run build_manifest.py")]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as e:
        # A corrupt/truncated manifest (partial write, interrupted build, bad copy)
        # is named as one hard drift — never an uncaught traceback. Mirrors the
        # sibling loaders (orphan_problems, component_file_problems).
        return [(MANIFEST_REL, "unreadable: %s" % e)]
    omit_prefixes = _omitted_skill_prefixes(root)
    problems = []
    for rel, expected in sorted(manifest.get("files", {}).items()):
        if omit_prefixes and rel.startswith(omit_prefixes):
            continue  # deliberately-omitted skill dir — absence is by design
        p = root / rel
        if not p.is_file():
            problems.append((rel, "missing"))
        elif sha256_file(p) != expected:
            problems.append((rel, "hash mismatch"))
    return problems


def orphan_problems(root: Path) -> list:
    """Files present on disk under harness/ but ABSENT from the manifest — the
    inverse of verify() (which only checks manifest-listed files are present and
    hash-match). A reinstall/upgrade that drops a script never removes the stale
    copy, so the orphan lingers and can shadow the live tree. NAMED per file.

    WARN-class by decision: an orphan is customization or stale-but-harmless, not
    integrity drift — it never fails --strict by itself (the installer's --prune
    removes them on demand). Returns [] when the manifest is absent (not an
    installable tree); harness/state/ is excluded (runtime-written, gitignored,
    never manifest-tracked)."""
    manifest_path = root / MANIFEST_REL
    harness_dir = root / "harness"
    if not manifest_path.is_file() or not harness_dir.is_dir():
        return []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — verify() reports the unreadable manifest
        return []
    tracked = set(manifest.get("files", {}))
    tracked.add(MANIFEST_REL)  # excluded from its own hash map but IS shipped
    tracked.add("harness/release.json")  # shipped, excluded from the hash map
    problems = []
    for p in sorted(harness_dir.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        # harness/state/ is runtime-written and gitignored — never manifest-
        # tracked, so it is not an orphan.
        if rel.startswith("harness/state/"):
            continue
        # harness/plugins/hs/disabled-skills/ is the tracked off-skill stash, but a
        # skill DISABLED at runtime is moved here and its files are not in the shipped
        # manifest — like state/, a runtime-mutable location. Excluding it keeps the
        # parked skill from reading as an orphan (and being deleted by --prune); a
        # ship-time-disabled skill is manifest-tracked and passes as `rel in tracked`.
        if rel.startswith("harness/plugins/hs/disabled-skills/"):
            continue
        # Compiler-generated / runtime-written paths — gitignored and never
        # manifest-tracked, so noise rather than orphans: bytecode cache, hook
        # crash logs, e2e run log.
        if ("__pycache__/" in rel or rel.endswith((".pyc", ".pyo"))
                or "/.logs/" in rel or rel.endswith("/RUN-LOG.md")):
            continue
        if rel not in tracked:
            problems.append((rel, "present on disk but not in the manifest "
                             "(orphan — a prior install left it; --prune removes)"))
    return problems


def release_channel_drift_problems(root: Path) -> list:
    """Recurrence guard: a `channel: "stable"` release.json pins
    kit_digest = sha256(manifest.json) AT CUT TIME and harness_release.py never
    recomputes it on that channel — deliberately: a released kit's digest must
    keep meaning "what we shipped", not silently start tracking local drift.
    That freeze is only truthful for as long as the checkout still IS the
    pinned commit.

    This repo cuts releases directly on trunk (release/release.py commits +
    tags harness/release.json in place, no separate release branch) and nothing
    reopens the channel back to `dev` afterward, so the moment a single further
    commit touches harness/, the pin goes quietly stale — exactly what happened
    here: `channel: stable` sat pinned to 2026-07-26's manifest through 404
    further commits before anyone noticed, and every artifact stamped in that
    window inherited a digest describing a tree that no longer existed.

    Reported HARD (added to `hard`, not a WARN): a stable pin that disagrees
    with the live manifest means this checkout is not actually the release it
    claims to be — either unreleased work resumed without reopening the channel
    (`release/release.py --reopen-dev`), or the pair has been tampered with
    post-cut. Returns [] when channel != "stable", release.json is absent/
    malformed, there is no declared digest to compare, or manifest.json does not
    exist yet (bootstrap — nothing to compare against)."""
    path = root / "harness" / "release.json"
    if not path.is_file():
        return []
    try:
        rel = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return []
    if not isinstance(rel, dict) or rel.get("channel") != "stable":
        return []
    declared = rel.get("kit_digest")
    if not declared:
        return []
    live = harness_release.compute_kit_digest(root)
    if not live or live == declared:
        return []
    return [("harness/release.json",
             "channel=stable pins kit_digest=%s but the live manifest hashes to "
             "%s — this checkout has moved past the pinned release without "
             "reopening the dev channel (run `release/release.py --reopen-dev "
             "--apply`), or release.json has been tampered with post-cut"
             % (declared, live))]


def release_file_count_problems(root: Path) -> list:
    """Companion to the digest check above, for the OTHER field release.json copies
    out of the manifest.

    `manifest_files_count` is written once by release/release.py:build_release_json
    as len(manifest["files"]) and then read by nothing. The digest check cannot cover
    it: re-pinning kit_digest by hand after a manifest rebuild — the ordinary shape of
    a mid-cut fix — leaves the count at its previous value, and every existing gate
    stays green because the digest genuinely is correct. Only the shipped file's own
    self-description is wrong, and a consumer sanity-checking an unpacked kit against
    that number is told the wrong one by the release's identity file.

    Stable channel only (a dev pin is expected to move), and silent whenever there is
    nothing to compare: absent/null count, absent or malformed release.json, absent or
    malformed manifest.json. Absent must not be read as 0 — the schema declares this
    field nullable, so a kit that simply does not state a count is not lying about it.
    """
    path = root / "harness" / "release.json"
    manifest = root / "harness" / "manifest.json"
    if not path.is_file() or not manifest.is_file():
        return []
    try:
        rel = json.loads(path.read_text(encoding="utf-8"))
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return []
    if not isinstance(rel, dict) or not isinstance(data, dict):
        return []
    if rel.get("channel") != "stable":
        return []
    declared = rel.get("manifest_files_count")
    if not isinstance(declared, int) or isinstance(declared, bool):
        return []
    files = data.get("files")
    if not isinstance(files, dict):
        return []
    live = len(files)
    if declared == live:
        return []
    return [("harness/release.json",
             "channel=stable declares manifest_files_count=%d but manifest.json holds "
             "%d entries — release.json was re-pinned without regenerating this field "
             "(rebuild it via release/release.py's build_release_json, not by hand)"
             % (declared, live))]


def _git_blob_sha(root: Path, ref_path: str, *, committed: bool) -> "str | None":
    """The git blob SHA for `ref_path`, either as committed at HEAD or as it
    currently sits on disk (git's own content-addressing — no encoding/newline
    pitfalls from diffing raw bytes). None on any failure (not a git checkout,
    path never committed, git missing) — always fail-soft, never raise."""
    cmd = (["rev-parse", "HEAD:%s" % ref_path] if committed
           else ["hash-object", str(root / ref_path)])
    try:
        r = subprocess.run(["git", "-C", str(root), *cmd],
                            capture_output=True, text=True)
    except OSError:
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def release_json_uncommitted_problems(root: Path) -> list:
    """DEFECT-2 partial closure. release.json is excluded from manifest.json's
    hash map ON PURPOSE (build_manifest.py's own comment: kit_digest =
    sha256(manifest.json), so hashing release.json INTO the manifest it is
    itself derived from would be circular — pack.py's manifest_files() names
    the identical reason). Nothing else hashes or signs release.json, so anyone
    able to write both harness/release.json and harness/manifest.json in the
    working tree — without ever running `git commit` — produces a pair that
    verifies cleanly against every other check in this module, because those
    checks only ever compare bytes on disk against manifest.json, and
    manifest.json's bytes are exactly what such an edit just wrote.

    Comparing the working-tree blob against the one git already recorded at
    HEAD costs no new infrastructure and closes exactly that slice: an
    uncommitted edit is a mutation no OTHER clone (the origin remote, a
    teammate's checkout) shares yet, unlike a hand-edit that never touches git
    at all. It is NOT a full close of DEFECT 2 — a forged (release.json,
    manifest.json) pair that IS committed together still verifies clean here
    (pinned by test_committed_forgery_still_verifies_clean in
    test_verify_install_release_drift.py, so that residual cannot silently
    widen). Closing that fully needs a detached signature verified against a
    key this repo does not hold, or server-side branch protection refusing an
    unreviewed push to a protected ref — infrastructure outside this repo.

    Returns [] when the tree is not a git checkout, release.json has never been
    committed yet (a fresh bootstrap — normal, not drift), or any git call
    fails (fail-soft, mirrors prepush_copy_warnings)."""
    rel_path = "harness/release.json"
    if not (root / rel_path).is_file() or not (root / ".git").exists():
        return []
    committed = _git_blob_sha(root, rel_path, committed=True)
    if committed is None:
        return []  # never committed at HEAD — nothing to compare, not drift
    working = _git_blob_sha(root, rel_path, committed=False)
    if working is None or working == committed:
        return []
    return [(rel_path,
             "working tree differs from what HEAD committed (blob %s vs %s) — "
             "an uncommitted edit to the version-identity file. release.json has "
             "no hash/signature of its own (see this function's docstring), so "
             "this git comparison is the cheapest external check available; "
             "commit through release/release.py or revert before trusting any "
             "evidence stamped from this tree" % (working, committed))]


def entrypoint_reach_warnings(root: Path) -> list:
    """Can a user actually TYPE the harness's front door?

    `hs-run` is the command every skill body tells the operator to run. Every
    other check here verifies the inside of the tree — hooks registered, hashes
    matched, plugins present — and none of them ever asked whether the command
    resolves. That is the first thing a user meets and the one thing a clean
    `verify_install --strict` could not speak to: everything correct inside, the
    door locked, and the verifier reporting OK.

    Two failure shapes, both silent today:
      * not on PATH at all — the user types it and gets "command not found";
      * on PATH but resolving into a DIFFERENT harness tree — worse, because it
        runs and answers confidently about the wrong repo (the global-install
        trap: project B's operator silently drives project A's tree).

    Nothing in the harness owns the PATH entry, so this can only ever report,
    never repair. Warn-class by decision: reachability is a property of the
    operator's shell, not of tree integrity — a CI checkout that never installed
    a PATH entry is not a broken install and must not fail --strict.
    """
    src = root / "harness" / "bin" / "hs-run"
    if not src.is_file():
        return []  # not this check's business (partial checkout, omitted component)
    rel = "harness/bin/hs-run"
    try:
        found = shutil.which("hs-run")
        if not found:
            return [(rel,
                     "not reachable on PATH — every skill body tells the user to "
                     "type `hs-run`, so this is the first thing they hit. Add %s "
                     "to PATH, or symlink hs-run from a directory already on it"
                     % src.parent)]
        # Resolve both sides through symlinks: the reachable copy is usually a
        # link, and comparing link paths would call a correct install wrong.
        if Path(found).resolve() != src.resolve():
            return [(rel,
                     "`hs-run` on PATH resolves to %s, NOT this tree's %s — it "
                     "will run and answer about the other tree. Repoint the PATH "
                     "entry at %s" % (Path(found).resolve(), src, src.parent))]
    except Exception as exc:  # noqa: BLE001 — a warn pass must never brick verify
        return [(rel, "could not be resolved on PATH (%s: %s)"
                 % (exc.__class__.__name__, exc))]
    return []


def prepush_copy_warnings(root: Path) -> list:
    """The ACTIVE pre-push hook lives at .git/hooks/pre-push, outside the
    manifest's reach — the manifest only hashes harness/. This cheap check
    compares the installed copy against its source and NAMES a difference.
    Warn-only by decision: a repo that never installed the git hook (or has
    no .git dir at all) must not fail verification over it."""
    src = root / "harness" / "install" / "git-pre-push-hook.sh"
    installed = root / ".git" / "hooks" / "pre-push"
    if not src.is_file() or not (root / ".git").is_dir():
        return []
    if not installed.is_file():
        return [(".git/hooks/pre-push",
                 "not installed (transport gate inactive — the installer "
                 "copies harness/install/git-pre-push-hook.sh there)")]
    if sha256_file(installed) != sha256_file(src):
        return [(".git/hooks/pre-push",
                 "installed copy differs from harness/install/"
                 "git-pre-push-hook.sh — reinstall or diff the two")]
    return []


def worktreeinclude_problems(root, mode="project") -> list:
    """Per-project presence of `.worktreeinclude`. The installer materializes it
    so Claude Code carries the harness runtime subtree + `.claude/settings.json`
    into every worktree it creates (closes F1). Under a GLOBAL install there is
    no per-project harness/ tree to carry — one shared bin serves every worktree —
    so its absence is NOT a defect (R8). A per-project install that lacks it would
    silently reintroduce the partial-carry hard-block."""
    from pathlib import Path as _Path
    if mode == "global":
        return []
    if not (_Path(root) / ".worktreeinclude").is_file():
        return [(".worktreeinclude",
                 "missing — the installer materializes it so Claude Code carries "
                 "harness/ + .claude/settings.json into every worktree (F1); "
                 "reinstall per-project")]
    return []


_DISPATCH_MODULE_RE = re.compile(r"module:\s*([A-Za-z0-9_]+)")


def _dispatch_covered_hooks(root: Path, registered: set) -> set:
    """Hook filenames a REGISTERED dispatcher runs in-process, read from
    harness/data/hook-dispatch.yaml (regex-scanned to keep verify dependency-free).

    A hook migrated into the dispatcher is no longer wired by its own command, but it
    still fires — as a core of hook_dispatch.py. It counts as registered ONLY when the
    dispatcher itself is registered; otherwise the registry is inert data and its
    cores really are unwired. Returns filenames like `gate_stage.py`."""
    if "hook_dispatch.py" not in registered:
        return set()
    disp = root / "harness" / "data" / "hook-dispatch.yaml"
    if not disp.is_file():
        return set()
    try:
        text = disp.read_text(encoding="utf-8")
    except OSError:
        return set()
    return {m + ".py" for m in _DISPATCH_MODULE_RE.findall(text)}


def hook_registration_problems(root: Path) -> list:
    """Co-presence between shipped entrypoint hooks and hooks-registration.yaml.
    Two failure modes, each NAMED per file (R8 install drift):
      - a registered command names a hook file that is absent on disk — the
        installer would wire a dangling command;
      - a shipped entrypoint hook (carries `__main__`) is missing from the
        registration — it ships but never fires (a silent no-op).
    A hook library WITHOUT `__main__` (hook_runtime, trace_log) is not an
    entrypoint and is not required to be registered. A hook migrated into
    hook_dispatch.py fires as a dispatcher CORE, not its own command, so it is
    counted registered when it appears in hook-dispatch.yaml under a registered
    dispatcher. Returns [] for a layout that has no registration file or hooks dir
    (not an installable tree)."""
    reg = root / "harness" / "install" / "hooks-registration.yaml"
    hooks_dir = root / "harness" / "hooks"
    if not reg.is_file() or not hooks_dir.is_dir():
        return []
    registered = set(_HOOK_CMD_RE.findall(reg.read_text(encoding="utf-8")))
    registered |= _dispatch_covered_hooks(root, registered)
    problems = []
    for fname in sorted(registered):
        if not (hooks_dir / fname).is_file():
            problems.append(
                ("harness/install/hooks-registration.yaml",
                 "registers %s but harness/hooks/%s is absent" % (fname, fname)))
    for p in sorted(hooks_dir.glob("*.py")):
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        if "__main__" not in text:
            continue  # library module, not an entrypoint hook
        if p.name not in registered:
            problems.append(
                ("harness/hooks/%s" % p.name,
                 "entrypoint hook not registered in hooks-registration.yaml "
                 "(ships but never fires)"))
    return problems


def _live_wired_hook_names(root: Path) -> set:
    """Basenames (no path, no CLI flags) of every hook .py wired into
    .claude/settings.json's `hooks` tree. Regex-scanned over the raw text (not
    JSON-walked) so this reuses the SAME `_HOOK_CMD_RE` pattern as
    hook_registration_problems — one hook-name-from-command-string parser, not
    two. Returns an empty set (not an error) when settings.json is absent/
    unreadable — this stays advisory (H1), never crashes verify_install."""
    settings = root / ".claude" / "settings.json"
    if not settings.is_file():
        return set()
    try:
        text = settings.read_text(encoding="utf-8")
    except OSError:
        return set()
    return {m[:-3] for m in _HOOK_CMD_RE.findall(text)}  # strip the .py suffix


def _ssot_enabled_hooks(root: Path) -> dict:
    """name -> enabled(bool) from harness/data/harness-hooks.yaml's explicit
    `hooks:` map. Only EXPLICIT booleans count (a hook resting on its
    class-default is not this SSOT's concern — see the file's own header).
    Returns {} on any missing-file/parse error (advisory; never crashes
    verify_install on a machine that skipped preflight / has no PyYAML)."""
    cfg = root / "harness" / "data" / "harness-hooks.yaml"
    if not cfg.is_file():
        return {}
    try:
        import yaml_io
        raw = yaml_io.safe_load(cfg.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — a malformed/unreadable SSOT is not fatal here
        return {}
    hooks = raw.get("hooks") if isinstance(raw, dict) else None
    if not isinstance(hooks, dict):
        return {}
    out = {}
    for name, entry in hooks.items():
        if isinstance(entry, dict) and isinstance(entry.get("enabled"), bool):
            out[name] = entry["enabled"]
    return out


def ssot_live_hook_drift_problems(root: Path) -> list:
    """H1: diff the hook SSOT (harness-hooks.yaml `enabled:`) against LIVE
    wiring (.claude/settings.json) so a flipped SSOT toggle can never silently
    drift from what is actually wired — the exact "config claims ON, live is
    dead" gap INV-3 found for glossary_pointer_inject and decision_reconcile_
    nudge. Advisory/fail-soft by design (unlike hook_registration_problems,
    which stays hard — see its own docstring): a repo checkout before install
    has no .claude/settings.json yet, and that absence must never read as
    drift, so this returns [] whenever settings.json or the SSOT can't be
    read, rather than raising or forcing a --strict failure.

    The two directions are NOT symmetric bugs, so they get different wording:
      - enabled=true + unwired -> a REAL defect (the hook can never fire no
        matter what the operator believes — the case INV-3 flagged HIGH).
      - enabled=false + still wired -> NOT a defect under this repo's
        wire-everything/toggle-via-SSOT pattern (every entrypoint self-checks
        hook_enabled() and no-ops when off — that's the whole point of the
        SSOT). It is real, worth-knowing STATE (a spawned-but-inert process
        per matching event, the per-invocation cost INV-3's F-9 counts), not a
        "live still fires" bypass — the wording says so explicitly."""
    settings = root / ".claude" / "settings.json"
    if not settings.is_file():
        return []
    ssot = _ssot_enabled_hooks(root)
    if not ssot:
        return []
    live = _live_wired_hook_names(root)
    # A hook migrated into hook_dispatch.py fires as a dispatcher CORE, not by its
    # own command, so it is live whenever the dispatcher itself is wired — union
    # those in (mirrors hook_registration_problems) or every grouped hook reads as
    # "config claims ON, live is dead".
    covered = _dispatch_covered_hooks(root, {n + ".py" for n in live})
    live |= {c[:-3] for c in covered}
    problems = []
    for name, enabled in sorted(ssot.items()):
        if enabled and name not in live:
            problems.append(
                ("harness/data/harness-hooks.yaml",
                 "%s: enabled=true in the SSOT but NOT wired in "
                 ".claude/settings.json — the hook can never fire "
                 "(config claims ON, live is dead)" % name))
        elif not enabled and name in live:
            problems.append(
                ("harness/data/harness-hooks.yaml",
                 "%s: enabled=false in the SSOT but its entrypoint is still "
                 "wired in .claude/settings.json — not a bug (the process "
                 "spawns and self-no-ops each matching event under the "
                 "wire-then-toggle pattern), but it costs a spawn; unwire it "
                 "there too if you want zero per-event cost" % name))
    return problems


def _registered_wiring_pairs(root: Path) -> "set | None":
    """{(event, matcher)} declared in hooks-registration.yaml — the installer's
    INPUT, i.e. the source of truth for what SHOULD be wired.

    `matcher` is kept VERBATIM (None for a no-matcher event, exact case
    otherwise). None on a missing/unparsable registration: that is
    hook_registration_problems' business, and a parse failure here must degrade
    to silence, never to a false "nothing is wired"."""
    reg = root / "harness" / "install" / "hooks-registration.yaml"
    if not reg.is_file():
        return None
    try:
        import yaml_io
        raw = yaml_io.safe_load(reg.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — unparsable → silence, not false drift
        return None
    entries = raw.get("hooks") if isinstance(raw, dict) else None
    if not isinstance(entries, list):
        return None
    pairs = set()
    for e in entries:
        if isinstance(e, dict) and e.get("event"):
            pairs.add((str(e["event"]), e.get("matcher")))
    return pairs or None


def _live_wiring_pairs(root: Path) -> "set | None":
    """{(event, matcher)} of HARNESS-OWNED groups in .claude/settings.json.

    Scoped to harness-owned commands on purpose: merge_hooks preserves a user's
    own hooks by design, so a foreign group must never read as drift. None when
    settings.json is absent/unreadable (a pre-install checkout)."""
    settings = root / ".claude" / "settings.json"
    if not settings.is_file():
        return None
    try:
        tree = json.loads(settings.read_text(encoding="utf-8")).get("hooks")
    except Exception:  # noqa: BLE001 — unreadable → silence, not false drift
        return None
    if not isinstance(tree, dict):
        return None
    pairs = set()
    for event, groups in tree.items():
        if not isinstance(groups, list):
            continue
        for g in groups:
            if not isinstance(g, dict):
                continue
            cmds = g.get("hooks") or []
            if any(_HOOK_CMD_RE.search(str(h.get("command", "")))
                   for h in cmds if isinstance(h, dict)):
                pairs.add((str(event), g.get("matcher")))
    return pairs


def registration_wiring_problems(root: Path, project_root: Path = None) -> list:
    """F2's defect class: diff hooks-registration.yaml against .claude/
    settings.json at the granularity of the (event, matcher) PAIR.

    `root` holds the registration (the BIN under a global install); settings.json
    is read from `project_root` when given, else from `root`. Under a global
    layout the two differ — the shared bin has no .claude/ of its own — and
    reading both from one root there would compare against a file that is never
    there, i.e. silently pass. Self-host collapses them, so the default is right
    for a per-project install and for the tests.

    ── DO NOT "SIMPLIFY" THIS INTO ssot_live_hook_drift_problems ──────────────
    That check compares hook .py BASENAMES, and every dispatcher registration
    names the same file (harness/hooks/hook_dispatch.py). The whole registration
    therefore collapses to the one-element set {hook_dispatch}, so deleting an
    entire (event, matcher) group leaves it unchanged — the name-keyed check is
    STRUCTURALLY BLIND to a lost group, not merely lax. That blindness is how a
    registered PreToolUse:Workflow group sat unwired while its only blocking
    gate never fired once. The PAIR is the unit here; the file name is not.

    Matchers compare VERBATIM (no case folding): Claude Code matches tool names
    exactly, so `bash` and `Bash` are genuinely different wires and folding them
    together would hide a dead group.

    Two directions, two different defects:
      - registered but unwired -> the group never fires (the F2 class);
      - wired but unregistered -> a retired group still fires. The installer's
        _wire_settings DOES reconcile (strip_harness_hooks, then re-wire), so
        this is NOT a leak of the normal install path; it catches the states
        that path never ran over — a hand-edited settings.json, or wiring left
        by a NEWER registration than the one now on disk. This direction is what
        makes REMOVING a hook group verifiable.

    Fail-soft on ABSENCE ONLY (a pre-install checkout has no settings.json; an
    unparsable registration is another check's business). A settings.json that
    EXISTS but is missing a registered group is a real defect and reports hard —
    the same posture as hook_registration_problems, whose docstring already
    holds that a dangling wire is a real bug regardless of which file it is
    keyed to."""
    registered = _registered_wiring_pairs(root)
    if registered is None:
        return []
    live = _live_wiring_pairs(project_root if project_root is not None else root)
    if live is None:
        return []

    def _label(pair) -> str:
        event, matcher = pair
        return event if matcher is None else '%s:"%s"' % (event, matcher)

    problems = []
    for pair in sorted(registered - live, key=_label):
        problems.append(
            ("harness/install/hooks-registration.yaml",
             "%s is registered but has NO group in .claude/settings.json — the "
             "hook never fires. Re-run the installer and RESTART Claude Code."
             % _label(pair)))
    for pair in sorted(live - registered, key=_label):
        problems.append(
            (".claude/settings.json",
             "%s is wired but not registered in hooks-registration.yaml — a "
             "retired group still fires. Re-run the installer (it strips and "
             "re-wires harness-owned groups), or re-add the registration."
             % _label(pair)))
    return problems


def _dispatch_group_pairs(root: Path) -> "set | None":
    """{(event, matcher)} of the groups hook-dispatch.yaml actually defines.

    Group keys are 'Event:Matcher'; a key with no colon is a whole-event group
    and normalises to matcher '*', matching how the dispatcher itself resolves
    (it falls back to the (event, '*') entry). None on absent/unparsable — that
    is the dispatcher's own fail-closed business, not this check's."""
    p = root / "harness" / "data" / "hook-dispatch.yaml"
    if not p.is_file():
        return None
    try:
        import yaml_io
        raw = yaml_io.safe_load(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — unparsable → silence, not false drift
        return None
    groups = raw.get("groups") if isinstance(raw, dict) else None
    if not isinstance(groups, dict):
        return None
    pairs = set()
    for key in groups:
        event, _, matcher = str(key).partition(":")
        pairs.add((event, matcher or "*"))
    return pairs


def dispatch_group_problems(root: Path) -> list:
    """Every registered (event, matcher) must have a group of hooks to run, and
    every group must be reachable from a registered pair.

    ── HOW THIS DIFFERS FROM registration_wiring_problems ─────────────────────
    Both compare (event, matcher) pairs and both are hard, but they fence
    different halves of the chain, and a tree can fail either one alone:

        hooks-registration.yaml -> .claude/settings.json   (the other check)
            broken => the group NEVER FIRES.
        hooks-registration.yaml -> harness/data/hook-dispatch.yaml   (this one)
            broken => the group FIRES AND FINDS NOTHING TO RUN.

    The second is the quieter of the two. The dispatcher process starts, resolves
    zero cores, and used to emit a clean `{"continue": true}` at exit 0 — the same
    bytes a legitimate pass produces. It now fails closed at runtime, but only at
    the moment the key fires; this check surfaces the drift before that.

    Three measured registry edits land exactly here while leaving the file
    parseable and non-empty, so no "is it empty" test can see them: every group
    emptied out, a group key with the wrong case, and a matcher drifted away from
    the wired one.

    Matchers and event names compare VERBATIM. Claude Code matches tool names
    exactly, so `pretooluse:Bash` is a different key rather than a lenient
    spelling of the right one, and folding case here would hide a dead group.

    Fail-soft on ABSENCE only, the same posture as the wiring check: a
    pre-install checkout has neither file. Both present but disagreeing is a real
    defect and reports hard.

    Unlike the settings.json check, this one is NOT vacuous in CI — both files are
    git-tracked, so it runs everywhere."""
    registered = _registered_wiring_pairs(root)
    if registered is None:
        return []
    groups = _dispatch_group_pairs(root)
    if groups is None:
        return []
    # _registered_wiring_pairs keeps a no-matcher event as None; the dispatcher
    # normalises that to '*'. Normalise here so the two sets are comparable.
    registered = {(e, m if m is not None else "*") for e, m in registered}

    def _label(pair) -> str:
        event, matcher = pair
        return event if matcher == "*" else '%s:"%s"' % (event, matcher)

    problems = []
    for pair in sorted(registered - groups, key=_label):
        problems.append(
            ("harness/data/hook-dispatch.yaml",
             "%s is registered but has no group in hook-dispatch.yaml — the hook "
             "fires and finds nothing to run, so any gates on this key are "
             "skipped. Check the group key (compared exactly, including case) "
             "and the matcher spelling." % _label(pair)))
    for pair in sorted(groups - registered, key=_label):
        problems.append(
            ("harness/data/hook-dispatch.yaml",
             "%s has a group but is not registered in hooks-registration.yaml — "
             "nothing dispatches it, so those cores never run. Register the pair "
             "or remove the group." % _label(pair)))
    return problems


def component_file_problems(root: Path) -> list:
    """Each file a component DECLARES (its hooks/scripts/data) must exist on
    disk — a component that ships a dangling member would wire/enable a file
    that isn't there. NAMED per missing file (R8 install drift). SKILLS are
    informational (a skill may be a not-yet-ported placeholder) and are not
    checked. Returns [] when components.yaml is absent (not a component-aware
    tree); a malformed manifest is itself reported as drift."""
    comp_file = root / "harness" / "data" / "components.yaml"
    if not comp_file.is_file():
        return []
    sys.path.append(str(root / "harness" / "scripts"))
    try:
        import component_config
        components = component_config.load_components(comp_file)
    except Exception as e:  # noqa: BLE001 — an unreadable manifest is drift
        return [("harness/data/components.yaml", "unreadable: %s" % e)]
    member_dirs = {
        "hooks": ("harness/hooks", ".py"),
        "scripts": ("harness/scripts", ".py"),
        "data": ("harness/data", ""),
    }
    problems = []
    for name in sorted(components):
        spec = components[name]
        for kind, (subdir, suffix) in member_dirs.items():
            for member in spec.get(kind, []):
                rel = "%s/%s%s" % (subdir, member, suffix)
                if not (root / rel).is_file():
                    problems.append(
                        (rel, "declared by component %r but missing on disk"
                         % name))
    return problems


def _source_escapes(plugins_dir: Path, candidate: Path) -> bool:
    """True if a marketplace `source`, joined under harness/plugins, resolves
    outside that dir — an absolute source or a `..` climb. The marketplace is
    attacker-influenceable (a crafted bundle), so a source like `../../etc/x`
    must be refused before the is_file probes read an arbitrary location. Uses
    resolve() + is_relative_to(), the same containment shape the installer's
    path guard enforces."""
    base = plugins_dir.resolve()
    try:
        resolved = candidate.resolve()
    except (OSError, RuntimeError, ValueError):
        # an unresolvable source (e.g. a circular symlink raising ELOOP) cannot
        # be proven contained — refuse it rather than crash verify (never-crash
        # contract, mirrors the symlink guard in standards_graph.py).
        return True
    return resolved != base and not resolved.is_relative_to(base)


def plugin_presence_problems(root: Path) -> list:
    """Every plugin the local marketplace DECLARES must exist on disk: a
    `.claude-plugin/plugin.json` plus a `skills/` or `agents/` dir (a plugin
    with neither loads nothing). NAMED per offending plugin (R8 install drift) —
    a marketplace that points at a missing plugin loads silently nothing.
    Returns [] when there is no marketplace.json (not a plugin-aware tree); an
    unreadable marketplace is itself reported as drift."""
    mp = root / "harness" / "plugins" / ".claude-plugin" / "marketplace.json"
    if not mp.is_file():
        return []
    try:
        data = json.loads(mp.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001 — an unreadable marketplace is drift
        return [("harness/plugins/.claude-plugin/marketplace.json",
                 "unreadable: %s" % e)]
    plugins_dir = root / "harness" / "plugins"
    problems = []
    for entry in data.get("plugins", []):
        name = entry.get("name")
        if not name:
            continue
        # `source` is a path relative to the marketplace dir; strip the leading
        # "./" as a PREFIX (not lstrip, which is a char-set strip that would eat a
        # leading dot of a real segment like "./.internal").
        src = entry.get("source") or ("./%s" % name)
        if src.startswith("./"):
            src = src[2:]
        base = plugins_dir / src
        rel = "harness/plugins/%s" % src
        # Containment: `source` is marketplace-supplied, so a crafted entry could
        # be absolute or climb out via `..` ("../../etc/x"), pointing the is_file
        # probes below at an arbitrary filesystem location. Refuse anything that
        # resolves outside harness/plugins (mirrors the installer's path guard).
        if _source_escapes(plugins_dir, base):
            problems.append(
                (rel, "marketplace declares plugin %r with source %r that "
                 "escapes harness/plugins (absolute or `..` climb) — refused"
                 % (name, src)))
            continue
        if not (base / ".claude-plugin" / "plugin.json").is_file():
            problems.append(
                (rel, "marketplace declares plugin %r but %s/.claude-plugin/"
                 "plugin.json is absent" % (name, rel)))
            continue
        # A plugin is loadable if it ships ANY content CC loads: skills, agents,
        # commands, or hooks. A hook-only plugin is legitimate (the harness has
        # hook-only feature bundles), so do not flag it as "nothing to load".
        if not any((base / d).is_dir()
                   for d in ("skills", "agents", "commands", "hooks")):
            problems.append(
                (rel, "plugin %r has no skills/agents/commands/hooks dir "
                 "(nothing to load)" % name))
    return problems


def settings_wiring_problems(project_root: Path) -> list:
    """Global-mode only: the PROJECT's settings.json/.local wired hook commands
    must reference $HARNESS_BIN_ROOT (the shared binary), not a stale project-local
    harness/hooks path. A project-local reference means the wiring never took the
    global switch — the hooks would look for a harness/ tree the global install
    never copied. NAMED per offending command; only harness-hook invocations are
    checked (a user command that merely mentions the dir is ignored)."""
    problems = []
    for name in ("settings.json", "settings.local.json"):
        p = project_root / ".claude" / name
        if not p.is_file():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue  # verify() already reports an unreadable settings elsewhere
        for _event, groups in (data.get("hooks") or {}).items():
            for g in (groups or []):
                for h in (g.get("hooks") or []):
                    cmd = str(h.get("command", ""))
                    if _HOOK_CMD_RE.search(cmd) and "$HARNESS_BIN_ROOT" not in cmd:
                        problems.append(
                            (".claude/%s" % name,
                             "harness hook command does not reference "
                             "$HARNESS_BIN_ROOT under a global install (stale "
                             "project-local wiring): %s" % cmd[:100]))
    return problems


def tracked_settings_problems(project_root: Path) -> list:
    """Warn-only, mode-agnostic: `.claude/settings.json` (and .local) must NOT be
    git-tracked. It is install-materialized and mode-specific (global wires
    $HARNESS_BIN_ROOT, project wires $CLAUDE_PROJECT_DIR), so a committed copy
    freezes stale/wrong-mode hook wiring into git history — a later `git checkout`
    restores dead per-script paths and bricks every hook. Reported ACTIONABLE
    (name the fix). A non-git dir / missing git yields no problem (graceful)."""
    import subprocess
    problems = []
    for name in ("settings.json", "settings.local.json"):
        rel = ".claude/%s" % name
        try:
            r = subprocess.run(
                ["git", "-C", str(project_root), "ls-files", "--error-unmatch", rel],
                capture_output=True, text=True)
        except (OSError, ValueError):
            return []  # no git available → cannot check, stay silent
        if r.returncode == 0:
            problems.append(
                (rel, "is git-tracked — settings.json is install-materialized and "
                 "mode-specific; a committed copy restores stale/wrong-mode hook "
                 "wiring on `git checkout` and bricks every hook. Untrack it: "
                 "`git rm --cached %s` (the managed .gitignore block now ignores "
                 "it)." % rel))
    return problems


def recipient_skeleton_problems(project_root: Path) -> list:
    """Global-mode recipient check: the project's private `.harness/` data
    skeleton must be present (bootstrap seeds it on install / first SessionStart).
    A project that never bootstrapped has no writeable data home, so every
    per-project write would land on a missing dir. Reported ACTIONABLE (name the
    fix) rather than crashing. NAMED per missing piece. `.harness/state/` is the
    load-bearing member — trace/telemetry/sessions live under it."""
    data = project_root / ".harness"
    if not data.is_dir():
        return [(".harness/", "project data skeleton missing — run bootstrap "
                 "(install --global seeds it, or it self-seeds on first "
                 "SessionStart)")]
    if not (data / "state").is_dir():
        return [(".harness/state/", "data skeleton incomplete (no state/ dir) — "
                 "run bootstrap to reseed")]
    return []


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".", help="repo root (default: cwd)")
    ap.add_argument("--strict", action="store_true",
                    help="exit non-zero on any drift")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()

    # Under a global install the shared binary (manifest, hook scripts, components,
    # plugins) lives BIN-side while `--root` is the project; the integrity checks
    # resolve against bin_root(). Self-install (HARNESS_BIN_ROOT unset) keeps
    # everything at `--root`, unchanged. Detected by HARNESS_BIN_ROOT being set
    # (the same signal the guards use).
    global_mode = bool(os.environ.get("HARNESS_BIN_ROOT"))
    if global_mode:
        import harness_paths
        bin_root = harness_paths.bin_root()
    else:
        bin_root = root

    # Can the operator actually type `hs-run`? Warn-only: PATH is a property of
    # their shell, not of the tree, so this reports and never fails --strict.
    # Resolved against bin_root — under a global install the binary lives in the
    # shared bin tree, which is exactly where the wrong-tree case shows up.
    for rel, problem in entrypoint_reach_warnings(bin_root):
        sys.stderr.write("WARN %s: %s\n" % (rel, problem))
    # The pre-push hook is a per-project git hook — always resolved against --root.
    for rel, problem in prepush_copy_warnings(root):
        sys.stderr.write("WARN %s: %s\n" % (rel, problem))
    # Orphans (on disk but unlisted) are warn-only — they never fail --strict by
    # themselves; the installer's --prune removes them on demand.
    for rel, problem in orphan_problems(bin_root):
        sys.stderr.write("WARN %s: %s\n" % (rel, problem))
    # H1: SSOT (harness-hooks.yaml) vs LIVE (.claude/settings.json) hook-enable
    # drift is advisory too — settings.json is per-project (always `root`, never
    # bin_root under a global install), and a pre-install checkout legitimately
    # has none yet.
    for rel, problem in ssot_live_hook_drift_problems(root):
        sys.stderr.write("WARN %s: %s\n" % (rel, problem))
    # A git-tracked settings.json is a checkout-landmine regardless of mode — warn
    # so a recipient untracks it before a branch switch bricks their hooks.
    for rel, problem in tracked_settings_problems(root):
        sys.stderr.write("WARN %s: %s\n" % (rel, problem))
    # Localization applies to integrity hash drift only. Hook-registration
    # co-presence defects (a dangling wire, an unregistered entrypoint) are real
    # bugs regardless of which file they are keyed to, so they stay hard.
    hard, localized = split_localized(verify(bin_root))
    hard += hook_registration_problems(bin_root)
    # (event, matcher) wiring drift is HARD, unlike the advisory settings.json
    # checks above — and the difference is deliberate, not an oversight:
    #   * those are advisory because a pre-install checkout has no settings.json,
    #     and ABSENCE must never read as drift;
    #   * this one returns [] on that same absence, so the advisory rationale is
    #     already satisfied. What is left — a settings.json that EXISTS and is
    #     missing a registered group — is a dangling wire, the same class
    #     hook_registration_problems keeps hard.
    # settings.json is per-project => always `root`, never `bin_root` (a global
    # bin has no .claude/ of its own); the registration lives in the bin.
    hard += registration_wiring_problems(bin_root, project_root=root)
    # The other half of the same chain: registration -> hook-dispatch.yaml. Both
    # files are bin-side and both are git-tracked, so unlike the settings.json
    # comparison above this one is meaningful in CI too.
    hard += dispatch_group_problems(bin_root)
    hard += component_file_problems(bin_root)
    hard += plugin_presence_problems(bin_root)
    # release.json is bin-side (excluded from manifest.json's own hash map — see
    # its own docstring) — both checks resolve against bin_root, same as verify().
    hard += release_channel_drift_problems(bin_root)
    # The digest's blind spot: a by-hand re-pin fixes kit_digest and leaves the
    # declared file count behind, which every other check reads as clean.
    hard += release_file_count_problems(bin_root)
    # Git-repo-only (fail-soft to [] otherwise); harmless to call under a
    # non-git global bin install, prepush_copy_warnings already does the same.
    hard += release_json_uncommitted_problems(bin_root)
    if global_mode:
        # The wired form lives project-side: confirm it points at the bin.
        hard += settings_wiring_problems(root)
        # The recipient's private data skeleton lives project-side too: confirm
        # bootstrap seeded it (missing → every per-project write hits a bare dir).
        hard += recipient_skeleton_problems(root)
    # Per-project .worktreeinclude presence (F1); skipped under global (R8).
    # Warn-only (like the pre-push hook): a partial/pre-install tree legitimately
    # lacks it, so its absence must not fail --strict — the installer writes it.
    for rel, problem in worktreeinclude_problems(
            root, mode=("global" if global_mode else "project")):
        sys.stderr.write("WARN %s: %s\n" % (rel, problem))
    for rel, problem in localized:
        sys.stderr.write(
            "WARN %s: %s (deployer-localized config — expected to differ from "
            "the shipped baseline)\n" % (rel, problem))
    if not hard:
        print("verify_install OK: manifest + hook registration consistent")
        return 0
    for rel, problem in hard:
        sys.stderr.write("DRIFT %s: %s\n" % (rel, problem))
    sys.stderr.write("verify_install: %d file(s) drifted\n" % len(hard))
    return 1 if args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
