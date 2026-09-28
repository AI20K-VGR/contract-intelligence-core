#!/usr/bin/env python3
"""harness_root.py — the ONE place `HARNESS_BIN_ROOT` / project-root resolution
lives. Shared by hs-run and hs-cli (siblings, neither imports the other — see
hs_run.py's own module docstring for why that boundary matters) so both CLIs
apply the SAME rules instead of hand-rolling their own `CLAUDE_PROJECT_DIR or
_ROOT` fallback per call site.

Two DIFFERENT questions live here, and they resolve to two DIFFERENT
directories under a global install — conflating them is exactly the bug this
module exists to close:

  `resolve_project_root()` answers "where does THIS PROJECT'S data live" —
  `.harness/`, `plans/`. Under a global install that is never the shared bin
  tree (the final guard below refuses that outright); under self-host/
  per-project install it is wherever `CLAUDE_PROJECT_DIR` (or a `.git`/`plans/`
  walk-up) lands.

  `bin_root_env()` answers "where does the shared harness INSTALLATION live" —
  scripts, skills, `harness/data/*.yaml`. Under a global install that is
  `HARNESS_BIN_ROOT`; under self-host/per-project install there is no separate
  bin tree, so callers fall back to their own `__file__`-derived root (the
  physical location of the running script IS the installation, in both of
  those modes).

A caller reading its OWN installation's catalog (hs-cli's `skills`/
`components`, which read `harness/plugins/hs/skills/`,
`harness/data/components.yaml`) wants `bin_root_env()`, never
`resolve_project_root()` — `CLAUDE_PROJECT_DIR` names the project currently
being worked on, which is a completely different directory from the shared
catalog under a global install, and reading it as if it held the catalog was
a real, reproduced bug: `hs-cli skills` silently printed 0 lines,
`hs-cli components` threw a raw traceback, and `--enable` claimed an
already-present skill needed re-fetching — all three because the CLI read
the wrong directory, not because anything was actually missing.

── vs. `harness_paths.py` — two modules, two DIFFERENT questions, NOT a merge
target ──────────────────────────────────────────────────────────────────────
`harness_paths.project_root()`/`data_root()` and THIS module's
`resolve_project_root()` both answer "what project am I working on", and both
read `CLAUDE_PROJECT_DIR`/`HARNESS_DATA_ROOT` — so on the surface they look
like the same function twice. They are not, and delegating one to the other
would be wrong, not just redundant:

  - `harness_paths` serves HOOKS: every guard/hook call runs inside a live
    Claude Code turn, where `CLAUDE_PROJECT_DIR` is ALWAYS set, and a wrong
    answer there can widen a write lane. Its contract is FAIL-CLOSED — an
    unresolvable project under a global install returns a sentinel
    (`_UNRESOLVED`) the caller MUST treat as "block", never CWD.
    `harness_paths.project_root()`'s global-install branch also falls back to
    the SHARED BIN root as a last resort — safe for a hook (which only reads
    shipped config from it), wrong for a CLI verb that would then read/write
    PROJECT state into shared binary infrastructure.

  - THIS module serves the two standalone CLIs (hs-run, hs-cli), invoked
    directly by a human or an agent's Bash tool — a context where
    `CLAUDE_PROJECT_DIR` is frequently UNSET (reproduced: a bare
    Bash-tool subprocess carries no hook env at all). Precedence here is
    CLAUDE_PROJECT_DIR-first specifically so a live session's project always
    wins when present; PLAIN CWD is the honest last resort (there is a real,
    just-typed command to answer, not a guard decision to make), and
    `bin_root_env()`'s refusal (the final guard below) is the one borrowed
    safety property: never resolve to the shared bin tree.

Net effect: given `HARNESS_DATA_ROOT=/a/.harness` and `CLAUDE_PROJECT_DIR=/b`
BOTH set, `harness_paths.data_root()` answers `/a/.harness` (HARNESS_DATA_ROOT
wins there) while THIS module's `resolve_project_root()` answers `/b`
(CLAUDE_PROJECT_DIR wins here) — a real, observable disagreement, not a bug to
converge: a hook writing state and a CLI verb resolving `plans/` in the SAME
process tree can legitimately be answering to two different `HARNESS_DATA_ROOT`
overrides for two different purposes (a hook's own state store vs. the plans/
tree of the project a human is actively typing commands in). Do not "fix" this
by making one call the other; if a caller ever needs BOTH answers to agree, it
must resolve via `harness_paths` explicitly (never assume this module's answer
already matches it).

`ProjectRootError` deliberately does NOT subclass `hs_run.RegistryError`, even
though it did before this module was extracted (hs_run.py used to define
`class ProjectRootError(RegistryError)` purely so `main()`'s existing
`except RegistryError` handled it for free). This module is now a SHARED
sibling of hs-run AND hs-cli — hs-cli has no `RegistryError` concept at all —
so subclassing hs_run's error here would be a layering violation (and a
circular import: hs_run.py imports THIS module). `hs_run.main()` instead
catches `ProjectRootError` with its own explicit `except` clause at the one
call site that can raise it — verified: both raise sites in this module are
caught explicitly by their callers, so the lost inheritance is harmless in
practice, just no longer "free."
"""
from __future__ import annotations

import os
from pathlib import Path


class ProjectRootError(Exception):
    """A stale/misconfigured project root (bad `CLAUDE_PROJECT_DIR`, a
    filesystem-root `HARNESS_DATA_ROOT`, or a resolved root that IS the shared
    bin root under a global install) — never silently degrade to CWD or the
    bin tree; name the problem instead."""


def _root_has_markers(path: Path) -> bool:
    """A directory is a plausible project root when it already carries a
    `plans/` dir (an already-scaffolded project) or a `.git` entry (a fresh,
    not-yet-scaffolded checkout — a DIR for a normal clone, a FILE for a
    linked worktree; `is_dir()`/`exists()` covers both)."""
    return (path / "plans").is_dir() or (path / ".git").exists()


def _walk_up_for_root(start: Path):
    """The nearest ancestor of `start` (start included) carrying a root
    marker, or None if none of start/its parents qualify."""
    try:
        cur = start.resolve()
    except OSError:
        return None
    for candidate in (cur, *cur.parents):
        if _root_has_markers(candidate):
            return candidate
    return None


def bin_root_env():
    """`HARNESS_BIN_ROOT`, resolved, ONLY when it names a real directory —
    else None. Read directly from the env (never inferred from `__file__` or
    CWD): a caller that wants "wherever THIS running script physically lives"
    already has that in its own `__file__`-derived constant and should fall
    back to it itself when this returns None (self-host / per-project install
    have no separate bin tree, so there is nothing further this function
    could usefully guess)."""
    raw = os.environ.get("HARNESS_BIN_ROOT")
    if not raw:
        return None
    try:
        p = Path(raw)
        return p.resolve() if p.is_dir() else None
    except OSError:
        return None


def resolve_project_root():
    """Returns (root: Path, source: str) — the CURRENT PROJECT's data root,
    never the shared bin tree. Precedence:

    1. `CLAUDE_PROJECT_DIR`, when it names an EXISTING directory — the working
       project of a live Claude Code session. A value that does NOT exist
       (stale/rotated/typo'd) raises `ProjectRootError` instead of silently
       falling through to CWD. The directory is then walked UP for a root
       marker (`plans/` or `.git`): `CLAUDE_PROJECT_DIR` pointing at a real,
       existing SUBdirectory of the actual project (`<proj>/src/deep`) must
       not be trusted as-is — that used to build a second `plans/` tree there
       instead of finding the real one one level up. Only when no ancestor
       carries a marker does the value stand as given (a genuinely fresh,
       non-git project — nothing higher to prefer).
    2. Otherwise, `HARNESS_DATA_ROOT` — the project's own `.harness/` data
       home under a global install, when there is no live Claude Code session
       to supply `CLAUDE_PROJECT_DIR`. Names the project directly (its
       parent — mirrors `harness_paths.data_root()`'s own `<project>/.harness`
       shape) without needing to guess from CWD, which under this exact shape
       can land on the shared bin root itself (a git checkout, so it carries
       a `.git` marker) and silently write project data into shared
       infrastructure.
    3. Otherwise, walk up from CWD looking for a `plans/` dir or a `.git`
       entry.
    4. If no marker is found anywhere up to the filesystem root, CWD itself
       is the answer — there is nothing higher to prefer.

    FINAL guard, applied to whichever tier above won: under a global install
    (`HARNESS_BIN_ROOT` set to a real directory), a resolved root that turns
    out to BE the shared bin root is refused outright (`ProjectRootError`)
    rather than silently accepted — the bin tree is read-only shared
    infrastructure (docs/harness/global-install-guide.md's two-zone model);
    project data never belongs there. Self-host (`HARNESS_BIN_ROOT` unset,
    bin == project) never trips this — `bin_root_env()` returns None there.
    """
    bin_root = bin_root_env()

    proj = os.environ.get("CLAUDE_PROJECT_DIR")
    if proj:
        cand = Path(proj)
        if not cand.is_dir():
            raise ProjectRootError(
                "CLAUDE_PROJECT_DIR=%r does not exist (or is not a directory) — "
                "refusing to silently fall back to the current directory; fix or "
                "unset CLAUDE_PROJECT_DIR before re-running" % proj)
        resolved = cand.resolve()
        found = _walk_up_for_root(resolved)
        if found is not None:
            marker = "plans-dir" if (found / "plans").is_dir() else "git"
            root, source = found, "env:CLAUDE_PROJECT_DIR-walked-up-to:%s" % marker
        else:
            root, source = resolved, "env:CLAUDE_PROJECT_DIR"
    else:
        data_root_raw = os.environ.get("HARNESS_DATA_ROOT")
        if data_root_raw:
            try:
                dr = Path(data_root_raw).resolve()
            except OSError:
                dr = Path(data_root_raw)
            parent = dr.parent
            if parent == Path(parent.anchor):
                raise ProjectRootError(
                    "HARNESS_DATA_ROOT=%r resolves to a project directory at the "
                    "filesystem root (%s) — refusing to treat the filesystem root "
                    "as a project" % (data_root_raw, parent))
            root, source = parent, "env:HARNESS_DATA_ROOT"
        else:
            cwd = Path.cwd()
            found = _walk_up_for_root(cwd)
            if found is not None:
                marker = "plans-dir" if (found / "plans").is_dir() else "git"
                root, source = found, "walked-up-to:%s" % marker
            else:
                root, source = cwd.resolve(), "cwd-no-markers-found"

    if bin_root is not None and root == bin_root:
        raise ProjectRootError(
            "resolved project root %s is the SHARED bin root (HARNESS_BIN_ROOT=%s) "
            "under a global install — refusing to read/write project data into "
            "shared binary infrastructure (docs/harness/global-install-guide.md's "
            "two-zone model: the bin tree is read-only shared infrastructure, never "
            "one project's plans/ home); set CLAUDE_PROJECT_DIR or HARNESS_DATA_ROOT "
            "to the actual project before re-running, or run from inside it"
            % (root, bin_root))

    return root, source


if __name__ == "__main__":
    root, source = resolve_project_root()
    print("root=%s source=%s" % (root, source))
