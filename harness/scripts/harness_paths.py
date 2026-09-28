#!/usr/bin/env python3
"""harness_paths.py — single home for root + state-dir resolution.

Two roots, one shared binary serving many projects:

  bin_root()   — where the programs live (hooks, scripts, skills, rules, data
                 templates). Read-only at runtime for every actor. A global
                 install points every project at ONE bin.
  data_root()  — a project's private data home `.harness/`. All per-project
                 state, telemetry, trace, writeable config land here.

`root()` is kept as a back-compat alias for `bin_root()` so the shipped-binary
readers are untouched by the split. Resolution is PURE (no mkdir): writers own
their own mkdir, readers never create what they inspect.

Precedence (exact):
  bin_root():   HARNESS_BIN_ROOT > HARNESS_ROOT (legacy alias) > __file__-relative
                > upward walk(harness/manifest.json | harness/hooks/) > CWD
  data_root():  HARNESS_DATA_ROOT > CLAUDE_PROJECT_DIR/.harness
                > (self-host, ONLY when HARNESS_BIN_ROOT UNSET) bin_root()/.harness
                > FAIL-CLOSED marker (caller-visible) — never a silent CWD
  state_dir():  HARNESS_STATE_DIR > data_root()/state
  tool_data_root(): data_root() strict tiers first; only under a global layout
                (HARNESS_BIN_ROOT set) with a still-unresolved result does a
                Bash-tool script walk up from CWD to its own project's
                `.harness/` — still unresolved -> the same FAIL-CLOSED marker.
  tool_state_dir(): HARNESS_STATE_DIR > tool_data_root()/state
  bin_state_dir(): bin_root()/harness/state   # install metadata, never project-side

FAIL-CLOSED (red-team F2/F5/F7): under a global layout (HARNESS_BIN_ROOT set) a
data_root() that cannot resolve a project returns the unresolved marker instead
of decaying to CWD — guards MUST treat it as "no project root" and BLOCK. Self-host
is detected by HARNESS_BIN_ROOT being UNSET (a global bin is itself a git checkout,
so a `.git` walk-up would wrongly collapse it). A data root whose parent is the
filesystem root (e.g. HARNESS_DATA_ROOT=/data) is not a real project (F7).

data_root()/state_dir() are STRICT-ONLY — no CWD walk, ever; a guard/hook always
calls these bare. The CWD walk-up lives ONLY behind the named tool_data_root()/
tool_state_dir() functions, for a tool invoked via the Bash tool (whose env
carries no CLAUDE_PROJECT_DIR): a NAMED function keeps this trust boundary
grep-enforceable (an absence-guard on harness/hooks/ + fs_guard.py bans the
`tool_data_root`/`tool_state_dir` tokens outright) — a boolean opt-in on the
strict functions would not be lintable and nothing would stop a future guard
from passing True and widening its own fail-closed lane.
"""

import os
from pathlib import Path
from typing import Optional

# Fail-closed sentinel: a global-layout data_root() that cannot resolve a
# project returns this. Absolute + non-existent so an accidental write under it
# fails loudly rather than silently landing in CWD/home. Callers/guards detect
# it via data_root_unresolved() and BLOCK.
_UNRESOLVED = Path("/__harness_data_root_unresolved__")

# --- linked-worktree host redirect (F2) ------------------------------------- #
# A git worktree carries only tracked files, so it would otherwise open its own
# state store and fragment/lose runtime data when removed. worktree_host_root()
# detects a linked worktree by its `.git` FILE (`gitdir: <host>/.git/worktrees/
# <name>`) + the `commondir` beside it, and returns the HOST repo root so both
# state flavours point back there. Reads a FILE (never spawns git — hot path),
# memoized per start dir, and fail-open ABSOLUTE: any surprise layout returns
# None and the caller keeps its legacy behaviour.
_WORKTREE_CACHE: dict = {}


def _reset_worktree_cache() -> None:
    """Test hook: drop the memoized worktree-detection results."""
    _WORKTREE_CACHE.clear()


def _probe_worktree_host_root(start: Path) -> Optional[Path]:
    """Uncached detection. Walk up from `start` to the nearest dir holding a
    `.git` entry: a `.git` DIR is the main worktree (no redirect -> None); a
    `.git` FILE is a linked worktree -> resolve its `commondir` to `<host>/.git`
    and return `<host>`. Any read/parse failure -> None (fail-open)."""
    try:
        cur = Path(start).resolve()
    except (OSError, RuntimeError):
        return None
    git_file = None
    for cand in (cur, *cur.parents):
        g = cand / ".git"
        try:
            if g.is_file():
                git_file = g
                break
            if g.is_dir():
                return None  # main worktree — never redirect
        except OSError:
            continue
    if git_file is None:
        return None
    try:
        content = git_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    gitdir_raw = None
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("gitdir:"):
            gitdir_raw = line[len("gitdir:"):].strip()
            break
    if not gitdir_raw:
        return None
    gitdir = Path(gitdir_raw)
    try:
        if not gitdir.is_absolute():
            gitdir = (git_file.parent / gitdir).resolve()
        else:
            gitdir = gitdir.resolve()
        common_raw = (gitdir / "commondir").read_text(encoding="utf-8").strip()
        common = Path(common_raw)
        if not common.is_absolute():
            common = (gitdir / common).resolve()
        else:
            common = common.resolve()
    except (OSError, RuntimeError):
        return None
    # commondir resolves to the shared `<host>/.git`; the host root is its parent.
    if common.name != ".git" or not (common.parent / ".git").is_dir():
        return None
    return common.parent


def worktree_host_root(start: Path) -> Optional[Path]:
    """Host repo root when `start` sits inside a linked git worktree, else None.
    Memoized per raw start dir; fail-open. Each state flavour passes ITS OWN
    anchor (R4): the script flavour CLAUDE_PROJECT_DIR-or-bin_root(), the hook
    flavour _hooks_dir() — never a single shared CLAUDE_PROJECT_DIR."""
    key = str(start)
    if key in _WORKTREE_CACHE:
        return _WORKTREE_CACHE[key]
    result = _probe_worktree_host_root(start)
    _WORKTREE_CACHE[key] = result
    return result


def _bin_root_from_file() -> Optional[Path]:
    """The bin root inferred from this file's own location: harness_paths.py
    lives at <bin>/harness/scripts/harness_paths.py. Returns the candidate only
    when it actually carries the harness markers (so a relocated copy falls
    through to the CWD walk-up)."""
    here = Path(__file__).resolve()
    cand = here.parent.parent.parent  # scripts -> harness -> <bin>
    if (cand / "harness" / "manifest.json").is_file() or (cand / "harness" / "hooks").is_dir():
        return cand
    return None


def bin_root() -> Path:
    raw = os.environ.get("HARNESS_BIN_ROOT") or os.environ.get("HARNESS_ROOT")
    if raw:
        return Path(raw).resolve()
    from_file = _bin_root_from_file()
    if from_file is not None:
        return from_file
    cur = Path.cwd().resolve()
    for candidate in (cur, *cur.parents):
        if (candidate / "harness" / "manifest.json").is_file():
            return candidate
        if (candidate / "harness" / "hooks").is_dir():
            return candidate
    return cur


def root() -> Path:
    """Back-compat alias for bin_root() — the shipped-binary readers keep using
    root() and transparently see the bin root."""
    return bin_root()


def _valid_project_dir(data_dir: Path) -> bool:
    """A data root is a real project only when its enclosing project dir is not
    the filesystem root (F7): HARNESS_DATA_ROOT=/data → project "/" is rejected."""
    parent = data_dir.parent
    return parent != Path(parent.anchor)


def _project_from_cwd() -> Optional[Path]:
    """Tool-context project resolver: walk up from CWD to the nearest dir that
    already carries a `.harness/` data home, return `<dir>/.harness`. Keyed on an
    existing `.harness/` (NOT a `.git` walk-up, per F2) so a global bin — itself a
    git checkout with NO per-project `.harness/` — is never mistaken for a project.
    Returns None when no initialized project encloses CWD; the caller then fails
    closed. This is for a TOOL invoked via the Bash tool (whose env carries no
    CLAUDE_PROJECT_DIR) — never for a guard, which runs in a hook env that always
    has CLAUDE_PROJECT_DIR and stays fail-closed."""
    try:
        cur = Path.cwd().resolve()
    except OSError:
        return None
    for cand in (cur, *cur.parents):
        dh = cand / ".harness"
        if dh.is_dir() and _valid_project_dir(dh):
            return dh
    return None


def data_root() -> Path:
    """The per-project data home `.harness/`. STRICT ONLY — never walks CWD; see
    module docstring for the exact precedence and the fail-closed contract. A
    guard/hook always calls this bare. A tool that needs the CWD walk-up uses
    the named tool_data_root() instead (never a boolean opt-in here — see
    module docstring for why)."""
    raw = os.environ.get("HARNESS_DATA_ROOT")
    if raw:
        cand = Path(raw).resolve()
        return cand if _valid_project_dir(cand) else _UNRESOLVED
    proj = os.environ.get("CLAUDE_PROJECT_DIR")
    if proj:
        anchor = Path(proj).resolve()
        host = worktree_host_root(anchor)  # linked worktree -> host (F2)
        cand = (host if host is not None else anchor) / ".harness"
        return cand if _valid_project_dir(cand) else _UNRESOLVED
    # Self-host (dogfood): ONLY when HARNESS_BIN_ROOT is UNSET. A global bin is
    # itself a git checkout, so this must NOT key off a `.git` walk-up (F2).
    if not os.environ.get("HARNESS_BIN_ROOT"):
        anchor = bin_root()
        host = worktree_host_root(anchor)  # self-host in a worktree -> host (R4/T8)
        return (host if host is not None else anchor) / ".harness"
    # Global layout with no resolvable project → fail-closed, never CWD.
    return _UNRESOLVED


def tool_data_root() -> Path:
    """TOOL-context resolver: the strict tiers first (DRY — calls data_root(),
    never re-inlines them); only when that comes back unresolved AND under a
    global layout (HARNESS_BIN_ROOT set) does a Bash-tool script walk up from
    CWD to its own project's `.harness/` instead of failing closed. It runs
    with cwd == the project and only ever resolves that project's own state,
    so it cannot widen a guard lane. A guard/hook must NEVER call this — it
    always calls data_root() bare and stays fail-closed (F2); this is exactly
    the boundary the absence-guard on harness/hooks/ + fs_guard.py enforces."""
    dr = data_root()
    if not data_root_unresolved(dr):
        return dr
    if os.environ.get("HARNESS_BIN_ROOT"):
        found = _project_from_cwd()
        if found is not None:
            return found
    return dr  # still unresolved — the fail-closed marker, never CWD


def data_root_unresolved(p: Path) -> bool:
    """True when `p` is the fail-closed marker — guards must BLOCK on this."""
    return Path(p) == _UNRESOLVED


def project_root() -> Path:
    """The per-project root for gate/scan operations that must target the
    project being worked on — NOT the shared binary. Precedence:
    CLAUDE_PROJECT_DIR (the working project) > the data-home-derived project dir
    (data_root().parent) > bin root (self-host, where bin == project). Always
    concrete — a scan/gate always has a real tree to point at.

    Every high-value caller runs in a HOOK context, where CLAUDE_PROJECT_DIR is
    always set and tier 1 wins outright. Tier 2 (data_root().parent) is reached
    only from a SCRIPT context (no CLAUDE_PROJECT_DIR, e.g. a Bash-tool
    subprocess) and it deliberately INHERITS data_root()'s linked-worktree HOST
    redirect (worktree_host_root(), module docstring "F2"): under self-host,
    running from inside a linked worktree with no CLAUDE_PROJECT_DIR, tier 2
    names the HOST repo, not the worktree copy — the same tree data_root()
    already points state at, so a script that falls to tier 2 keeps state and
    project-root resolution consistent instead of splitting them across two
    trees. A caller that instead needs the literal worktree it is running from
    must read CLAUDE_PROJECT_DIR itself (tier 1) rather than rely on tier 2.

    Use root()/bin_root() for BIN-global config; use this only for project-scoped
    file operations (git diff of the project, plans/ receipts, source scans).
    Under self-host these coincide (bin == project), so switching a project-scoped
    caller from root() to project_root() is a no-op there and only diverges — the
    intended fix — under a global install."""
    proj = os.environ.get("CLAUDE_PROJECT_DIR")
    if proj:
        cand = Path(proj)
        if cand.is_dir():
            resolved = cand.resolve()
            # F7 fail-closed: never hand back the filesystem root as a project to
            # WRITE into (inject would stamp "/plans/reports/..."). data_root()
            # rejects this same case; mirror it here and fall through to the next
            # tier instead of returning "/".
            if resolved != Path(resolved.anchor):
                return resolved
    dr = data_root()
    if not data_root_unresolved(dr):
        return dr.parent
    return bin_root()


def state_dir() -> Path:
    """STRICT ONLY — see data_root(). A tool needing the CWD walk-up uses
    tool_state_dir() instead."""
    raw = os.environ.get("HARNESS_STATE_DIR")
    if raw:
        return Path(raw)
    return data_root() / "state"


def writable_state_dir():
    """`state_dir()` for WRITERS, or None when no project resolves.

    Readers may take the unresolved path and simply find nothing. A writer cannot:
    `state_dir()` yields `<_UNRESOLVED>/state` on an unresolved root, so a
    `mkdir(parents=True)` materialises the fail-closed marker at the FILESYSTEM ROOT
    — the very path `bootstrap.ensure_skeleton` refuses with ValueError. That
    directory then outlives the process and leaks into unrelated runs (it broke
    `test_bootstrap`'s marker check after an `-n auto` suite run).

    Returns None rather than raising because every current caller is telemetry- or
    nudge-class: dropping one record is the cheap failure, writing to `/` is not.
    """
    sd = state_dir()
    return None if data_root_unresolved(sd.parent) else sd


def tool_state_dir() -> Path:
    """TOOL-context state dir over tool_data_root() — see its docstring. A
    guard/hook must NEVER call this; it always calls state_dir() bare."""
    raw = os.environ.get("HARNESS_STATE_DIR")
    if raw:
        return Path(raw)
    return tool_data_root() / "state"


def bin_state_dir() -> Path:
    """Bin-side state home for install metadata (install-omitted-skills.json,
    install-state.json) — describes the INSTALL, not a project, so it never
    rides data_root()."""
    return bin_root() / "harness" / "state"


def engine_home() -> Path:
    """The courier's stable engine home: where `harness setup` copies the engine
    out of the plugin cache. `<XDG_DATA_HOME|~/.local/share>/harness`. PURE — no
    mkdir (writers own their own mkdir). This is orthogonal to bin_root()/
    data_root(): it names the shared install location a global-mode bin_root()
    then points at, and does NOT touch self-host detection (a self-host repo
    leaves HARNESS_BIN_ROOT UNSET and never consults this)."""
    base = os.environ.get("XDG_DATA_HOME") or "~/.local/share"
    # A relative XDG_DATA_HOME must NOT anchor the SHARED engine home to CWD (which
    # `.resolve()` on a relative path would do — giving every project its own engine
    # under <cwd>/…). The XDG spec says a relative value is invalid and should be
    # ignored, so fall back to the ~/.local/share default.
    if base != "~/.local/share" and not os.path.isabs(os.path.expanduser(base)):
        base = "~/.local/share"
    p = Path(base).expanduser() / "harness"
    try:
        return p.resolve()
    except (OSError, RuntimeError):
        # a symlink loop / ELOOP on XDG_DATA_HOME must not crash the diagnostic verbs
        # (doctor/version) that call engine_home() before any other guard; fall back to
        # the un-resolved absolute path so downstream .is_file() checks simply report the
        # engine home as absent instead of raising RuntimeError('Symlink loop').
        return p.absolute()


def engine_current() -> Path:
    """The `current` pointer under engine_home() — the default engine a repo's
    HARNESS_BIN_ROOT resolves to when it is not pinned to a version dir."""
    return engine_home() / "current"


def trace_dir() -> Path:
    return state_dir() / "trace"


def telemetry_dir() -> Path:
    return state_dir() / "telemetry"
