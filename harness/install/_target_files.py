#!/usr/bin/env python3
"""_target_files.py — writes into the target repo's OWN files (extracted from
install.py): the managed .gitignore block, the CLAUDE.md onboarding block, and
the standards presence check. install.py
re-exports these names, so callers and tests that reach them through the
`install` module see no change.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
# The block splice is shared with the runtime installer, which writes into a file the
# harness does not own either. One answer to that question, not two.
from artifact_io import splice_block, strip_stale_blocks  # noqa: E402

def _standards_maxloc() -> int:
    """Advisory line budget for a standards doc (tunable). Default mirrors the
    repo's docs footprint limit."""
    raw = os.environ.get("HARNESS_STANDARDS_MAXLOC", "").strip()
    try:
        return int(raw) if raw else 800
    except ValueError:
        return 800


_GITIGNORE_BEGIN = "# >>> harness (generated runtime — never commit) >>>"
_GITIGNORE_END = "# <<< harness <<<"
_GITIGNORE_PATTERNS = (
    "harness/state/",
    "harness/standards/.snapshots/",
    "harness/e2e/RUN-LOG.md",
    # The project data home under a global install (state/, trace/, telemetry/,
    # sessions/). bootstrap.py seeds it and reseeds it on SessionStart precisely
    # BECAUSE it is gitignored and so never travels with a clone — leaving it
    # trackable commits one project's runtime state into the product history.
    # Harmless under a project install, where the path simply does not exist.
    ".harness/",
    # settings.json is install-materialized and mode-specific (global wires
    # $HARNESS_BIN_ROOT, project wires $CLAUDE_PROJECT_DIR). Committing it freezes
    # wrong-mode/stale hook wiring into git history — a later `git checkout` then
    # restores dead per-script paths and bricks every hook. Never commit it.
    ".claude/settings.json",
    ".claude/settings.local.json",
)


def _write_gitignore(target_root, result, dry_run, no_track=False):
    """Ensure the target's .gitignore carries a managed harness block so the
    runtime state the harness writes never lands in the deployer's git. User lines
    OUTSIDE the markers are always preserved, and a no-change rewrite is skipped
    (idempotent). Like the CLAUDE.md block, this REPLACES between the markers so a
    version bump (a new ignore pattern such as `.claude/settings.json`) reaches an
    adopter who installed before it — a skip-if-present block would freeze the
    stale set forever. With ``no_track``, ALSO ignore the whole harness/ tree — the
    harness runs but is never committed into the adopter's product git (re-track by
    dropping --no-track and removing the line)."""
    path = target_root / ".gitignore"
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    block = "\n".join([_GITIGNORE_BEGIN, *_GITIGNORE_PATTERNS, _GITIGNORE_END])
    b = existing.find(_GITIGNORE_BEGIN)
    e = existing.find(_GITIGNORE_END, b) if b != -1 else -1
    if b != -1 and e != -1:
        # well-formed marker pair → replace between them (refresh a stale block)
        new = existing[:b] + block + existing[e + len(_GITIGNORE_END):]
        if new != existing:
            result["actions"].append("refresh harness block in .gitignore")
    else:
        sep = "" if not existing or existing.endswith("\n") else "\n"
        new = existing + sep + block + "\n"
        result["actions"].append("add harness block to .gitignore")
    if no_track and "harness/" not in new.splitlines():
        sep = "" if not new or new.endswith("\n") else "\n"
        new = new + sep + "harness/\n"
        result["actions"].append(
            "gitignore harness/ (--no-track: harness present but not committed)")
    if new != existing and not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new, encoding="utf-8")


_CLAUDE_BEGIN = "<!-- >>> harness onboarding (generated; edits between markers are overwritten on reinstall) >>> -->"
_CLAUDE_END = "<!-- <<< harness <<< -->"


def _claude_md_block() -> str:
    """The self-loading onboarding block: what the harness is, how to drive it,
    where the shared rules live. Kept short — it is a pointer, not a manual."""
    return "\n".join([
        _CLAUDE_BEGIN,
        "",
        "## SDLC harness",
        "",
        "This repo runs a file-based **SDLC harness** for Claude Code. The engine is "
        "either vendored here or shared from one global install, so every path below "
        "is written `$E/harness/...` where **`$E` is `\"${HARNESS_BIN_ROOT:-.}\"`** — "
        "spell it that way and it resolves in both layouts; a bare `harness/...` is a "
        "dead path under a global install.",
        "",
        "- **Probe before you build on a guess** — when a "
        "load-bearing assumption CAN be checked (spike a slice, run the real tool, read "
        "the source), do that FIRST, before designing on top of it. A claim you have "
        "not exercised for real is `[ASSUMED]` (unchecked training "
        "knowledge is `[PRIOR]`), never OBSERVED: label it honestly and gate it behind "
        "one real run — never report \"works\" from reasoning alone.",
        "- **Skills** — drive the workflow with `/hs:<name>` (`/hs:plan`, `/hs:cook`, "
        "`/hs:test`, `/hs:ship`, `/hs:review-pr`). `/hs:find-skills` lists them.",
        "- **Off skills** — a fresh install ships DEFAULT-OFF; the rest are stashed "
        "under `$E/harness/plugins/hs/disabled-skills/<name>/`. "
        "`/hs:find-skills --list` tags them `[OFF]`; run one with "
        "`/hs:use <name>` (not the raw `/hs:<name>`). An off reference is normal — do "
        "not hunt for a 'missing' skill.",
        "- **`hs-run`** (`$E/harness/bin/`) — the step engine: `hs-run <domain> next` "
        "returns a JSON envelope (`state`, `next_action`, `artifacts`, `refs`) and an "
        "exit rung — `0` done, `10` needs the model, `11` step remains, `2` broken. Read "
        "it; do not re-derive the step.",
        "- **`hs-cli`** (same dir) — config/admin: `skills --on/--off` (restart to "
        "apply), `components`, `migrate`, `trust`.",
        "- **Both need their roots** — `HARNESS_BIN_ROOT` (engine) and `HARNESS_DATA_ROOT` "
        "(data, default `.harness/`). Called by bare path without them, the engine "
        "walks UP for `plans/` and answers for the WRONG project.",
        "- **Rules** — shared conventions load on demand from `$E/harness/rules/` "
        "(routing in this file's project section, or ask a skill).",
        "- **Hooks** — gates/telemetry wired in `.claude/settings.json`; knobs in "
        "`$E/harness/data/*.yaml`. `/hs:setup` configures voice, policy, output.",
        "",
        _CLAUDE_END,
    ])


def _strip_stale_claude_blocks(text: str) -> str:
    """The onboarding block's binding of the shared stripper."""
    return strip_stale_blocks(text, _CLAUDE_BEGIN, _CLAUDE_END)


def _write_claude_md(target_root, result, dry_run):
    """Inject the onboarding block into the target's CLAUDE.md. Unlike the
    .gitignore block (skip-if-present), this REPLACES between markers so a
    version bump refreshes a stale block; prose OUTSIDE the markers is always
    preserved, and a no-change rewrite is skipped (idempotent)."""
    path = target_root / "CLAUDE.md"
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    new = splice_block(existing, _claude_md_block(), _CLAUDE_BEGIN, _CLAUDE_END)
    if new == existing:
        return  # already current — nothing to do (idempotent)
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new, encoding="utf-8")
    result["actions"].append("write harness onboarding block to CLAUDE.md")


_WTI_BEGIN = "# >>> harness worktree carry (generated — edits between markers are overwritten) >>>"
_WTI_END = "# <<< harness <<<"


def _write_worktreeinclude(target_root, source_root, result, dry_run):
    """Materialize the target's `.worktreeinclude` from the shipped template so
    Claude Code copies the harness runtime subtree + `.claude/settings.json` into
    every worktree it creates (closes the F1 partial-carry hard-block). Managed
    between markers — replaces a stale block so a version bump (a new harness
    subdir) reaches an adopter who installed earlier, while preserving any user
    lines outside the markers. Idempotent (a no-change rewrite is skipped).
    Per-project only — the caller gates on mode != global and source != target."""
    template = source_root / "harness" / "install" / "worktreeinclude.template"
    try:
        lines = [l.rstrip("\n") for l in
                 template.read_text(encoding="utf-8").splitlines() if l.strip()]
    except OSError:
        return  # no template shipped — nothing to materialize (fail-open)
    block = "\n".join([_WTI_BEGIN, *lines, _WTI_END])
    path = target_root / ".worktreeinclude"
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    b = existing.find(_WTI_BEGIN)
    e = existing.find(_WTI_END, b) if b != -1 else -1
    if b != -1 and e != -1:
        new = existing[:b] + block + existing[e + len(_WTI_END):]
    else:
        sep = "" if not existing or existing.endswith("\n") else "\n"
        new = existing + sep + block + "\n"
    if new == existing:
        return  # already current — idempotent
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new, encoding="utf-8")
    result["actions"].append("write .worktreeinclude (worktree carry of harness/)")


def _check_standards(target_root, result):
    base = target_root / "docs"
    maxloc = _standards_maxloc()
    for name in ("code-standards.md", "system-architecture.md"):
        p = base / name
        if not p.is_file() or len(p.read_text(encoding="utf-8").strip()) < 40:
            result["warnings"].append(
                "docs/%s missing or thin — run /hs:docs to author it (or "
                "harness/scripts/scaffold_standards.py --type %s for a TBD "
                "skeleton, or copy your org's into docs/) before relying on "
                "standards-aware skills; the installer never fabricates them"
                % (name, name[:-3]))
            continue
        loc = p.read_text(encoding="utf-8").count("\n") + 1
        if loc > maxloc:
            result["warnings"].append(
                "docs/%s is %d lines (> %d) — many skills load it, so a "
                "long file costs tokens and is easy to skim past; consider "
                "trimming or splitting it (advisory, set HARNESS_STANDARDS_MAXLOC "
                "to tune)" % (name, loc, maxloc))
