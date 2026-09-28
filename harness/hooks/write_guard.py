#!/usr/bin/env python3
"""write_guard.py — tool-mediated config-edit gate (compliance, fail-closed).

PreToolUse(Write|Edit|MultiEdit|NotebookEdit): block when the target is one of
the files the gate posture depends on. Under a GLOBAL install one shared binary
serves many projects, so the gate resolves TWO roots and guards TWO zones:

  bin zone (read-only, shared)   — the ENTIRE bin_root() tree. When bin≠project a
      tool-Write to ANY path under the bin is blocked for every actor: the bin
      holds .claude/settings.json (the guard on/off switch), CLAUDE.md,
      scripts/, orchestrator/ — a harness/-only fence would let a foreign project
      overwrite the hook registration and disable ALL guards (red-team F1).
  project zone (writeable, per-project) — the project-lane GUARD_LIST patterns
      (docs/decisions.*, plans/*/artifacts/plan-approval.*) matched relative to
      the PROJECT root so they stay guarded even when the binary lives elsewhere
      (C3).

Self-host / dogfood (bin==project) collapses to today's single-root behavior:
detected by HARNESS_BIN_ROOT being UNSET (a global bin is itself a git checkout,
so a `.git` walk-up would wrongly collapse it — red-team F2). Under a global
layout with an unresolved project root the gate FAILS CLOSED (blocks a guarded
project-tail write, never a silent allow — C5/F2). Containment is case-insensitive
(F6) so a case-variant bin path cannot dodge it on macOS/Windows.

GUARD_LIST is a CODE CONSTANT: config can only ADD paths (write-guard.yaml
`extra_guarded`), never remove one — a config knob that can shrink the guard is a
guard that does not exist.

HONESTY — the name is the scope: this is a tool-mediated CONFIG-EDIT gate. It sees
Write/Edit/MultiEdit/NotebookEdit tool calls and nothing else. It does NOT see a
Bash redirect (`echo > file`), a `cp`/`sed -i` into the bin, or an editor outside
the session — those paths are the documented tamper-EVIDENT floor (git diff,
manifest verify, pre-push scrub). For a SHARED bin the git-diff floor evaporates
(the diff lands in the bin's repo, which the foreign operator never reviews), so
true shared-binary integrity requires the bin be OS-level read-only to the runtime
user — that is the real fence, documented in the phase-7 install doc, NOT a claim
this gate makes.

Enable-path autonomy — WIRED REALITY: `check()` itself only ever consults
_switch_config() (write-guard.yaml in the bin tree's harness/data/, tracked in
git, or the dev-only HARNESS_WRITE_GUARD_CONFIG override) and never reads
HARNESS_HOOK_CONFIG — that half of the claim holds. But `check()` is never
called standalone in production: the only registration is hook_dispatch.py
(harness/data/hook-dispatch.yaml `entry: check`), and the dispatcher decides
WHETHER to call it at all via hook_runtime.hook_enabled() BEFORE `check()` ever
runs — the same env-driven precedence every other compliance guard's dispatch
is gated by. So HARNESS_HOOK_CONFIG CAN skip this guard entirely on the wired
path, same as its siblings (bash_safety_guard, privacy_read_guard); it just
does so by never invoking `check()`, not by `check()` honoring the env itself.
That is a declared, accepted gap (harness/rules/harness-contract.md: an
HARNESS_* env repoint is "a known gap ... guards accidental drift, NOT an
insider"), not an exemption unique to this guard. Fail-closed is local:
`check()`/`main()` reimplement the run_compliance_hook exception→exit-2
discipline rather than reusing it (that wrapper carries the env-driven
dispatch-gate the dispatcher applies here too).
"""

import fnmatch
import json
import os
import re
import sys
from pathlib import Path

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:
    sys.path.append(_HOOKS_DIR)
# harness_paths lives in the sibling scripts/ dir; add it so bin/data root
# resolution rides the single shared resolver. Imported lazily in the resolvers
# so a missing sibling can never brick the module at import time (a bricked
# compliance hook would fail-closed and reject writes indiscriminately).
_SCRIPTS_DIR = os.path.join(_HOOKS_DIR, "..", "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.append(_SCRIPTS_DIR)

HOOK_CLASS = "compliance"

_GUARDED_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")

# --- H4: MCP blind spot -------------------------------------------------------
# A `mcp__<server>__<method>` tool call is invisible to the native
# Write|Edit|MultiEdit|NotebookEdit matcher above — an MCP server exposing a
# write-capable method (e.g. a devtool's `write`/`insert`/`update` query) could
# edit a guarded path with NO gate in the way (INV-3 F-8c, DECISIONS.md H4).
# Threat-modeled, not a blanket new gate: this hook polices WRITE TARGETS, so a
# read-shaped method (query/get/list/search/describe/read/fetch/select — e.g. a
# devtool `query` in its read-only Safe Mode) is a documented non-issue and
# passes untouched; only a write-shaped method is gated on its extractable
# target path, or fails CLOSED when no target can be found at all (an MCP write
# this gate cannot see the destination of is never silently allowed).
_MCP_WRITE_VERB_RE = re.compile(
    r"(write|insert|update|delete|remove|create|exec|execute|mutate|patch|"
    r"put|upsert|apply|migrate|drop|truncate|alter|modify)", re.IGNORECASE)
_MCP_PATH_KEYS = ("file_path", "notebook_path", "path", "filepath", "file",
                  "target", "target_path", "output_path", "dest",
                  "destination", "filename")


def is_mcp_tool(tool_name) -> bool:
    return isinstance(tool_name, str) and tool_name.startswith("mcp__")


def mcp_write_shaped(tool_name: str) -> bool:
    """True when the MCP tool's method segment (the part after the LAST `__` in
    `mcp__<server>__<method>`) looks like a write verb. A method with no
    recognizable verb is treated conservatively as NOT write-shaped (read-only-
    safe) — this deliberately favors the documented-non-issue path over an
    unbounded new gate; a server that names its write method something this
    regex misses is a documented gap (mirrors the rest of this file's honesty
    notes), not a silent guarantee."""
    method = tool_name.rsplit("__", 1)[-1] if "__" in tool_name else tool_name
    return bool(_MCP_WRITE_VERB_RE.search(method))


def mcp_candidate_path(tool_input):
    """The first plausible write-target path in an MCP tool_input dict, else
    None. MCP server schemas vary server-to-server; this is a best-effort scan
    over common key names, checked in a fixed, predictable order."""
    if not isinstance(tool_input, dict):
        return None
    for key in _MCP_PATH_KEYS:
        val = tool_input.get(key)
        if isinstance(val, str) and val.strip():
            return val
    return None

# Repo-root-relative globs (fnmatch). Constant by design. The full guarded set
# (both zones) — kept as one tuple so bash_write_guard reuses the identical set
# (one guarded set, two observers). The two lanes below partition it by root.
GUARD_LIST = (
    # decisions SSOT: the register CLI (atomic_write via Bash) is the ONLY
    # sanctioned write path; a direct agent tool-edit would bypass the
    # cross-scope confirm gate, so the SSOT + its rendered view are guarded.
    "docs/decisions.yaml",
    "docs/decisions.md",
    "harness/hooks/*.py",
    # the three planes that decide whether a hook actually runs. Keep them
    # together: they are one decision, not three list entries.
    #   hook-dispatch.yaml — is it wired at all (the SOLE production registration
    #     for every hook, so one edit can silence all of them at once; a mistyped
    #     key in it was measured turning a blocking gate into an allow at exit 0);
    #   guard-policy.yaml  — its off/warn/block posture. The sanctioned writer is
    #     the guard_config CLI, which traces the change with an actor and leaves a
    #     git diff; a direct tool-edit skips both;
    #   harness-hooks.yaml — its per-hook enabled flag.
    # Only the third was guarded before. All three are already closed on the Bash
    # and subagent lanes by the harness/** floor, so what these two entries add is
    # exactly one lane: the main session's tool-Write. No sanctioned writer breaks
    # — install.py, dev_skill_farm.py and guard_config.py all reach these files
    # through a Bash-run Python process, which this tool-lane guard never sees.
    "harness/data/hook-dispatch.yaml",
    "harness/data/guard-policy.yaml",
    "harness/data/harness-hooks.yaml",
    "harness/data/write-guard.yaml",
    "harness/data/stage-policy.yaml",
    "harness/data/simplify-policy.yaml",
    "harness/data/ownership.yaml",
    # the write deny-list cage: its policy modules, the soft config, and the schema —
    # an agent must not weaken the floor it is held to (the cage self-protection set).
    "harness/scripts/write_deny_policy.py",
    "harness/scripts/deny_matcher.py",
    "harness/scripts/deny_audit.py",
    "harness/data/write-deny-policy.yaml",
    "harness/schemas/write-deny-policy.json",
    "harness/scripts/artifact_check.py",
    "harness/scripts/stage_detector.py",
    "harness/scripts/fs_guard.py",
    "harness/scripts/claims.py",
    "harness/scripts/component_config.py",
    "harness/data/components.yaml",
    "harness/data/component-policy.yaml",
    "harness/scripts/plan_approval.py",
    "harness/scripts/output_config.py",
    "harness/scripts/register_block.py",
    "harness/scripts/voice_prefs.py",
    "harness/install/git-pre-push-hook.sh",
    "harness/install/hooks-registration.yaml",
    "plans/*/artifacts/plan-approval.json",
    "plans/*/artifacts/plan-approval.yaml",
)

# Project-lane: matched relative to the PROJECT root (docs/plans are per-project).
_PROJECT_LANE = (
    "docs/decisions.yaml",
    "docs/decisions.md",
    "plans/*/artifacts/plan-approval.json",
    "plans/*/artifacts/plan-approval.yaml",
)
# Bin-lane: everything else — the shared binary's own gate files, matched
# relative to the bin root. Derived from GUARD_LIST so the two lanes can never
# drift from the constant.
_BIN_LANE = tuple(p for p in GUARD_LIST if p not in _PROJECT_LANE)

_SWITCH_NAME = "write-guard.yaml"


def _bin_root() -> Path:
    """The shared-binary root: HARNESS_BIN_ROOT > HARNESS_ROOT > __file__ >
    walk-up. Delegates to the shared resolver; falls back to a local self-resolve
    if the sibling import is unavailable so the gate never bricks."""
    try:
        import harness_paths
        return harness_paths.bin_root()
    except Exception:
        raw = os.environ.get("HARNESS_BIN_ROOT") or os.environ.get("HARNESS_ROOT")
        if raw:
            return Path(raw).resolve()
        return Path(__file__).resolve().parent.parent.parent


def _root() -> Path:
    """Back-compat alias for _bin_root() — bash_write_guard + the switch loader
    resolve the shared binary through here."""
    return _bin_root()


def _self_host() -> bool:
    """Self-host / dogfood is detected by HARNESS_BIN_ROOT being UNSET. A global
    bin is itself a git checkout, so this must NOT key off a `.git` walk-up (F2):
    that would collapse a global layout with an unset project dir and unlock the
    shared bin."""
    return not os.environ.get("HARNESS_BIN_ROOT")


def _project_root(bin_root: Path):
    """The project root the project-lane patterns anchor to. Under self-host the
    bin IS the project (ignore a stray CLAUDE_PROJECT_DIR — in a self-hosted
    checkout the two are the same tree). Under a global layout it is the external
    project; None (fail-closed) when it cannot be resolved."""
    if _self_host():
        return bin_root
    proj = os.environ.get("CLAUDE_PROJECT_DIR")
    if proj:
        return Path(proj).resolve()
    try:
        import harness_paths
        dr = harness_paths.data_root()
        if harness_paths.data_root_unresolved(dr):
            return None
        return dr.parent
    except Exception:
        return None


def _switch_config() -> dict:
    """Parse the write-guard switch. Default source: write-guard.yaml in the bin
    tree's harness/data/ (the tracked break-glass file). A repo owner MAY point
    the DEDICATED HARNESS_WRITE_GUARD_CONFIG env at an override file (e.g. under
    .harness-dev/) to disarm the tool-cage in a single-owner dev repo; the
    override wins when set + readable.

    Two deliberate scope choices: (1) the BROAD HARNESS_HOOK_CONFIG still does
    NOT reach this gate — only this single-purpose var does, so a general config
    can never silently disarm the cage. (2) SECURITY TRADEOFF: the override lives
    in a writeable zone, re-exposing the F3 self-disarm surface the tracked-file
    design closes — intended ONLY for a single-owner dev sandbox, and scrubbed at
    push (HARNESS_* env never ships), so ship/downstream always fall back to the
    tracked write-guard.yaml (enabled: true). Malformed / missing override →
    fall through to the tracked file; a broken switch never opens the gate."""
    override = os.environ.get("HARNESS_WRITE_GUARD_CONFIG")
    if override:
        op = Path(override)
        if op.is_file():
            try:
                import hook_runtime  # for yaml_load (C loader + mandatory fallback)
                raw = hook_runtime.yaml_load(op.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    return raw
            except Exception:
                pass  # unparsable override → fall through to the tracked switch
    p = _bin_root() / "harness" / "data" / _SWITCH_NAME
    if not p.is_file():
        return {}
    try:
        import hook_runtime  # for yaml_load (C loader + mandatory fallback)
        raw = hook_runtime.yaml_load(p.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}  # unparsable switch = guard stays on


def _extra_guarded(cfg) -> tuple:
    extra = cfg.get("extra_guarded")
    if isinstance(extra, list):
        return tuple(str(x) for x in extra if isinstance(x, str) and x.strip())
    return ()


def _rel_target(file_path, root: Path):
    """Target as a root-relative POSIX path, resolved (`..` collapsed, symlinks
    followed) so traversal cannot dodge the match. None when the target lies
    outside `root` entirely."""
    target = Path(file_path)
    if not target.is_absolute():
        target = root / target
    resolved = target.resolve(strict=False)
    try:
        return resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        return None


def _match(rel, patterns):
    """First guarded pattern matching `rel`, case-insensitively (on a
    case-insensitive FS `harness/HOOKS/gate_stage.py` opens the REAL guarded
    file), else None."""
    if rel is None:
        return None
    low = rel.lower()
    return next((pat for pat in patterns
                 if fnmatch.fnmatch(low, pat.lower())), None)


def _match_tail(file_path, patterns):
    """First pattern matching the TAIL of an absolute path — the fail-closed
    fallback when the project root is unresolved under a global bin: we cannot
    anchor the project-lane patterns, so a path whose tail looks like a guarded
    SSOT is blocked rather than silently allowed."""
    p = str(Path(file_path)).replace(os.sep, "/").lower()
    for pat in patterns:
        low = pat.lower()
        if fnmatch.fnmatch(p, "*/" + low) or fnmatch.fnmatch(p, low):
            return pat
    return None


def _under(file_path, root: Path) -> bool:
    """True when the resolved target lies inside `root` (the whole-bin catch-all).
    Case-insensitive realpath containment (F6) so a case-variant path cannot dodge
    it on a case-insensitive FS. On a resolution error this catch-all BLOCKS
    (returns True): it exists precisely for bin paths the lane checks did not
    match, so failing open here would let an unresolvable bin-zone write slip."""
    try:
        target = Path(file_path)
        if not target.is_absolute():
            target = root / target
        rt = str(target.resolve(strict=False)).lower()
        rr = str(root.resolve()).lower()
        return rt == rr or rt.startswith(rr.rstrip(os.sep) + os.sep)
    except Exception:
        return True


def check(data) -> "str | None":
    """None = allow; string = block reason (the compliance core contract)."""
    tool = data.get("tool_name")
    tool_input = data.get("tool_input") or {}
    mcp_unresolvable = False
    if tool in _GUARDED_TOOLS:
        # NotebookEdit carries notebook_path, not file_path (F4) — read both so a
        # .ipynb write to the bin cannot slip past the catch-all.
        file_path = tool_input.get("file_path") or tool_input.get("notebook_path")
        if not file_path:
            return None
    elif is_mcp_tool(tool):
        # H4: gate a write-shaped MCP call the same way; a read-shaped one
        # (query/get/list/...) is out of scope for this path-containment gate.
        if not mcp_write_shaped(tool):
            return None
        file_path = mcp_candidate_path(tool_input)
        mcp_unresolvable = file_path is None
    else:
        return None

    cfg = _switch_config()
    disabled = cfg.get("enabled") is False

    if mcp_unresolvable:
        return _decide_mcp_unresolvable(disabled, tool, data)
    extra = _extra_guarded(cfg)
    bin_root = _bin_root()
    proj_root = _project_root(bin_root)
    collapse = _self_host()  # global layout never collapses, even if realpath-equal (F7)

    # 1. Bin-lane: the shared binary's own gate files, resolved rel to bin_root.
    #    Fires in BOTH modes (they name the bin's files either way).
    rel_bin = _rel_target(file_path, bin_root)
    hit = _match(rel_bin, _BIN_LANE + extra)
    if hit:
        return _decide(disabled, rel_bin, hit, data)

    # 2. Project-lane: docs/plan-approval, resolved rel to the project root.
    if proj_root is not None:
        rel_proj = _rel_target(file_path, proj_root)
        hit = _match(rel_proj, _PROJECT_LANE + extra)
        if hit:
            return _decide(disabled, rel_proj, hit, data)
    elif os.environ.get("HARNESS_BIN_ROOT"):
        # C5/F2 fail-closed: global layout, project unresolved → cannot anchor the
        # project lane. Block a guarded-SSOT-tail write rather than allow it.
        hit = _match_tail(file_path, _PROJECT_LANE + extra)
        if hit:
            return _decide(disabled, str(file_path), hit, data,
                           note="project root unresolved under global bin")

    # 3. Bin-zone whole-bin catch-all (F1): when bin≠project, any tool-Write under
    #    the shared bin is blocked for every actor. Skipped on self-host collapse
    #    so the dev can edit its own tree.
    if not collapse and _under(file_path, bin_root):
        return _decide(disabled, str(file_path),
                       "${bin}/** (shared-binary read-only zone)", data)

    return None


# Guarded path -> the CLI that writes it from inside the session.
#
# Every entry was run for real against a scratch copy of the tree, with the file
# hashed before and after: it is here only if that hash changed. An earlier version
# of this map was built by reading `--help` output instead, which cannot tell a verb
# that writes from a verb that reports — five of its twelve entries named a tool
# that never touched the file (`check_fence.py` has no write path at all;
# `findings_store.py --promote` answers "nothing was written"; `hs-cli components`
# rewrites harness-hooks.yaml, not components.yaml). A route line naming the wrong
# tool is worse than no route line: the reader runs it, nothing changes, and the
# guard looks broken rather than the advice. When adding an entry, run it and diff.
#
# Keyed by the GUARD_LIST pattern so the two stay aligned by eye. Paths absent from
# this map get the generic "edit it outside the session" line — that is the honest
# answer for the twenty-eight guarded paths no CLI writes.
_SANCTIONED_WRITER = {
    "docs/decisions.yaml": "decision_register.py --append --title … --rationale …",
    "docs/decisions.md":
        "decision_register.py --append --title … --rationale … (it renders this view)",
    "harness/data/guard-policy.yaml": "guard_config.py set <guard> off|warn|block",
    "harness/data/component-policy.yaml": "component_config.py --set NAME=enabled",
    # `hs-cli components --enable/--disable` writes component-policy.yaml (above)
    # and harness-hooks.yaml — never components.yaml, which is the group->skill map
    # an install reads, not a state file.
    "harness/data/harness-hooks.yaml": "hs-cli components --enable/--disable GROUP",
    # Restores a hand-drifted dispatch file in an INSTALLED target back to the
    # shipped copy. It does not edit the harness's own; that one is a source file.
    "harness/data/hook-dispatch.yaml": "hs-cli install --target <dir>",
    "plans/*/artifacts/plan-approval.json":
        "plan_approval.py --plan … --verdict APPROVED|REJECTED --rationale …",
    "plans/*/artifacts/plan-approval.yaml":
        "plan_approval.py --plan … --verdict APPROVED|REJECTED --rationale …",
}


def _decide(disabled, target, hit, data, note=None):
    """Emit the trace + reason for a matched guard, honoring the tracked
    break-glass (write-guard.yaml enabled:false)."""
    if disabled:
        _trace("gate_skip", target, data,
               note="write_guard disabled via %s (tracked break-glass; the flip "
                    "is a git diff)" % _SWITCH_NAME)
        return None
    _trace("gate_block", target, data,
           note=("matched %s" % hit) + (" — %s" % note if note else ""))
    writer = _SANCTIONED_WRITER.get(hit)
    route = ("Run `%s` instead — that is the sanctioned writer and it works from "
             "inside this session." % writer) if writer else (
             "There is no CLI for this one: change it with a normal editor outside "
             "the agent session. The file is tracked, so the diff stays visible.")
    return (
        "%s is gate config (matched %r) — agent tools may not edit it. %s"
        % (target, hit, route)
    )


def _decide_mcp_unresolvable(disabled, tool_name, data) -> "str | None":
    """H4 fail-closed arm: an MCP tool_name matched a write verb but no
    candidate path field was found in tool_input — the write target is
    unknowable, so this blocks rather than silently letting an MCP write past
    every path-containment check (honoring the same tracked break-glass as
    every other guard_list hit)."""
    if disabled:
        _trace("gate_skip", tool_name, data,
               note="write_guard disabled via %s (tracked break-glass; the flip "
                    "is a git diff)" % _SWITCH_NAME)
        return None
    _trace("gate_block", tool_name, data,
           note="MCP tool matched a write verb but no path field was found "
                "among %s — target unknowable" % ", ".join(_MCP_PATH_KEYS))
    return (
        "%s looks write-shaped (matched a write verb in its method name) but "
        "no recognizable path field was found in its tool_input (checked: %s) "
        "— the write target is unknowable, so this is blocked fail-closed. If "
        "this MCP tool is read-only-safe, name its verb outside the guard's "
        "write-verb pattern, or add its path field name to _MCP_PATH_KEYS."
        % (tool_name, ", ".join(_MCP_PATH_KEYS))
    )


def _trace(event, target, data, note=None) -> None:
    try:
        import trace_log
        trace_log.append_event("write_guard", event,
                               session=data.get("session_id"),
                               tool=data.get("tool_name"), target=target,
                               note=note)
    except Exception:
        pass  # tracing must not break the gate decision


def main() -> None:
    """Fail-closed shell (the run_compliance_hook discipline, minus its
    env-driven enable path): every internal error blocks with exit 2."""
    try:
        try:
            data = json.loads(sys.stdin.read() or "{}")
        except ValueError:
            data = {}
        if not isinstance(data, dict):
            data = {}

        reason = check(data)
        if reason:
            sys.stderr.write("[write_guard] BLOCKED: %s\n" % reason)
            sys.exit(2)
        try:
            sys.stdout.write(json.dumps({"continue": True}))
            sys.stdout.flush()
        except Exception:
            pass
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001 — a broken gate must gate
        try:
            import hook_runtime
            hook_runtime.log_hook_error("write_guard", e)
        except Exception:
            pass
        sys.stderr.write(
            "[write_guard] BLOCKED: gate crashed (%s: %s). Fail-closed by "
            "policy. Emergency off-switch: set `enabled: false` in "
            "harness/data/write-guard.yaml with an editor OUTSIDE the "
            "agent session (tracked file, diff visible).\n"
            % (type(e).__name__, e))
        sys.exit(2)


if __name__ == "__main__":
    main()
