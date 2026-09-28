#!/usr/bin/env python3
"""inject_prompt_context.py — context re-injection hook (telemetry-class).

CLAUDE.md is loaded near the top of each context window; within a long window it
drifts up and out of the model's working attention, and its conventions get
forgotten. This hook re-states the load-bearing rules on a decay-aware cadence —
NOT every prompt (that re-states freshly-loaded rules for no gain), but on the
two moments the working context actually goes stale:

  - SessionStart (startup / resume / clear / compact): arm a re-inject for the
    next prompt — the window just turned over, dynamic context (branch, active
    plan, paths) should be re-surfaced.
  - UserPromptSubmit: re-inject every N turns within a window, so a long stretch
    refreshes the rules before CLAUDE.md has drifted too far up.

Beyond the static rules it carries the DYNAMIC context a fixed file cannot: the
current git branch, the active plan's absolute path, and the dated report/plan
naming pattern (absolute paths so a deep CWD never spawns a stray plans/ subtree).

Ported harness-native from the upstream dev-rules-reminder + context-builder
(MIT). Rebranded on port: points at the harness rule layer (`harness/rules/`,
routed from CLAUDE.md), never `.claude/`. The upstream throttled on a 5-minute
wall-clock TTL; this uses a turns + session-boundary signal instead (decay
tracks context growth, not elapsed time). The active-plan path is salvaged from
the upstream cook-after-plan-reminder.

Telemetry-class + fail-open: advisory only, it NEVER blocks. Disabled, any
exception, or malformed stdin -> a plain continue (a broken context hook
degrades to "no reminder", never to a blocked prompt). Never raises, never
exits 2. Mirrors voice_inject's emit plumbing.
"""

import json
import os
import platform
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(str(Path(__file__).resolve().parent.parent / "scripts"))
import hook_runtime   # noqa: E402
import harness_paths  # noqa: E402
import reinject_config  # noqa: E402

HOOK_CLASS = "telemetry"

_RULES = "harness/rules/"
_DOCS_MAXLOC = 800

# Within a single context window, re-surface the rules roughly every N prompts.
# A session boundary (SessionStart, any source) always arms the next prompt.
_INJECT_EVERY_TURNS = 5
_STATE_NAME = "prompt-context.json"

# Default arm state for an unseen scope: a mid-session install injects on its
# first prompt. Shared by decide() (the cadence) and run() (the full-vs-slim
# branch) so the "was this injection armed?" question has ONE source of truth —
# a drift here would desync the two and pick the wrong block.
_ARMED_DEFAULT = True

# The refresh block: the first injection after a session boundary is the full
# ~2.3K-token block (the window just turned over); later within-window refreshes
# emit this compact slim block instead. It re-pays only for what actually decays:
# the live voice register, the active plan + branch, the absolute report/plan
# paths + dated stamp (the hook's reason-for-existing — a deep CWD must not spawn
# a stray plans/ subtree), and a pointer back to the full rule layer. Budget is a
# hard ceiling asserted by the suite; sized to fit the two UNAVOIDABLE absolute
# Reports/Plans paths (write-safety — they cannot be relativised) at realistic root
# DEPTH: the harness's own git worktrees nest the root ~50 chars deeper under
# .claude/worktrees/<name>/, and each absolute path carries that prefix. The plan
# path rides relative (read-only, safe) to spend the budget only where it must.
# Still an order of magnitude under the full block.
SLIM_BUDGET_CHARS = 1100
_SLIM_DIRECTIVE = (
    "directive: markdown only under plans/ or docs/; reports follow output.yaml "
    "language; compact early when context fills; TDD test-first is the habit; "
    "probe before building on a guess (unrun claim = [ASSUMED])"
)

# --- decay-aware cadence (pure decision + tiny transient state) ---------------

def decide(scope_state, event, source=None, current_sig=None, every_turns=None,
           fill_ratio=None, threshold=None):
    """Pure: given this scope's prior state + the firing event (+ the current
    context fingerprint), return (should_inject, new_scope_state).

    SessionStart of any source arms a re-inject (force) for the next prompt and
    emits nothing itself. UserPromptSubmit injects when (a) armed, (b) the
    meaningful context changed since the last injection (current_sig differs
    from the stored sig — a just-toggled voice/branch/plan shows up immediately,
    not N turns later), or (c) the cadence is due; otherwise it counts and stays
    quiet. An unseen scope defaults to armed, so a mid-session install still
    injects on its first prompt.

    `every_turns` (optional): the resolved turn-count cadence to compare `turns`
    against. Defaults to the module constant `_INJECT_EVERY_TURNS` when omitted.

    `fill_ratio`/`threshold` (optional, P6/B3 adaptive-by-context-fill — OPT-IN):
    when BOTH are given (non-None), the cadence check becomes
    `fill_ratio >= threshold` INSTEAD OF the turn-count comparison — the caller
    resolved the `adaptive` preset and computed a real fill_ratio. When either is
    None (adaptive preset not active, or fill_ratio unreadable/unclassifiable),
    the turn-count path decides EXACTLY as before — this is the fail-open
    fallback, never a wedge. `turns` is still tracked either way so a later
    fallback (e.g. a transcript read failing mid-session) resumes from a sane
    count. None of this reads config/transcript here — decide() stays PURE;
    callers (run()/core_gated()) resolve reinject_config.resolve_adaptive() +
    reinject_config.fill_ratio() themselves and pass the values in."""
    st = dict(scope_state or {})
    if event == "SessionStart":
        return (False, {"turns": 0, "force": True, "sig": current_sig})
    turns = int(st.get("turns", 0)) + 1
    armed = bool(st.get("force", _ARMED_DEFAULT))
    changed = current_sig is not None and st.get("sig") != current_sig
    if fill_ratio is not None and threshold is not None:
        due = fill_ratio >= threshold
    else:
        n = _INJECT_EVERY_TURNS if every_turns is None else every_turns
        due = turns >= n
    if armed or changed or due:
        return (True, {"turns": 0, "force": False, "sig": current_sig})
    return (False, {"turns": turns, "force": False, "sig": st.get("sig")})


def _every_turns() -> int:
    """The resolved cadence for the NEXT decide() call — a call-site resolution
    (not a decide()-internal read) so decide() stays pure. Fail-open to the
    module constant on any resolver hiccup (reinject_config.resolve() is
    already fail-open; this is a defensive second layer, mirroring _refresh_mode())."""
    try:
        return int(reinject_config.resolve().get("every_turns", _INJECT_EVERY_TURNS))
    except Exception:  # noqa: BLE001 - never let a config read break cadence
        return _INJECT_EVERY_TURNS


def _slim_budget() -> int:
    """The resolved slim-refresh budget ceiling (a test assertion ceiling, NOT a
    truncation point — build_slim_context never cuts its block). Fail-open to
    the module constant SLIM_BUDGET_CHARS on any resolver hiccup."""
    try:
        return int(reinject_config.resolve().get("slim_budget_chars", SLIM_BUDGET_CHARS))
    except Exception:  # noqa: BLE001 - never let a config read break the budget
        return SLIM_BUDGET_CHARS


def _adaptive_params(transcript_path):
    """Resolve (fill_ratio, threshold) for decide()'s adaptive branch (P6/B3,
    OPT-IN). Returns (None, None) — the turn-count fallback signal — unless the
    active preset is mode=='fill' (the `adaptive` preset), so the shipped default
    (`balanced`) never touches the transcript at all. Fail-open: any resolver or
    fill_ratio hiccup also yields (None, None). All config/transcript I/O lives
    here, at the call site — decide() itself stays pure."""
    try:
        cfg = reinject_config.resolve_adaptive()
        if cfg.get("mode") != "fill" or cfg.get("threshold") is None:
            return (None, None)
        return (reinject_config.fill_ratio(transcript_path, None), cfg.get("threshold"))
    except Exception:  # noqa: BLE001 - never let a config read break cadence
        return (None, None)


def _state_path() -> Path:
    return harness_paths.state_dir() / _STATE_NAME


def _load_state() -> dict:
    try:
        return json.loads(_state_path().read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001 - missing/corrupt state -> empty (fail-open)
        return {}


def _save_state(state: dict) -> None:
    try:
        p = _state_path()
        # state_dir() hands back <_UNRESOLVED>/state when no project resolves, and
        # mkdir(parents=True) would then materialise the fail-closed marker at the
        # FILESYSTEM ROOT — the same path bootstrap.ensure_skeleton refuses outright.
        # This hook is telemetry-class, so drop the write instead of raising: losing a
        # cadence counter costs one redundant injection, writing to / costs a stray
        # directory that outlives the process and leaks into unrelated runs.
        if harness_paths.data_root_unresolved(p.parent.parent):
            return
        p.parent.mkdir(parents=True, exist_ok=True)
        # Atomic publish with a per-writer-unique temp name: two Claude Code sessions
        # open on the SAME project share this one per-project file, so a fixed
        # `<name>.tmp` would let concurrent writers race on the same temp path and
        # torn-write each other. os.replace is atomic once each writer owns its own
        # temp file — a reader never observes a half-written state.
        tmp = p.parent / (".%s.%d.%s.tmp" % (p.name, os.getpid(), uuid.uuid4().hex[:8]))
        try:
            tmp.write_text(json.dumps(state), encoding="utf-8")
            os.replace(tmp, p)
        finally:
            try:
                tmp.unlink()
            except OSError:
                pass  # already renamed onto p, or never created
    except Exception:  # noqa: BLE001 - state is best-effort coordination
        pass


# Bound the per-cwd scope map: without this it grows one entry per distinct cwd
# ever seen (git worktrees, CI checkouts, temp clones) and is re-serialized in
# full on every prompt. _MAX_SCOPES caps the survivor count; _SCOPE_TTL_SECONDS
# evicts anything untouched for a month even under the cap.
_MAX_SCOPES = 200
_SCOPE_TTL_SECONDS = 30 * 24 * 3600


def _prune_scopes(state: dict, now: float = None) -> dict:
    """Bound `state` before it is persisted: drop scope entries untouched past
    _SCOPE_TTL_SECONDS, then cap survivors to the _MAX_SCOPES most-recently-touched
    (by their `ts` stamp). Fail-open shape: an entry missing `ts` is treated as
    freshly touched (age 0), never surprise-evicted — but `ts: 0.0` (epoch) is a
    real, ancient timestamp and must NOT be conflated with "missing" (an `or`
    fallback would do exactly that, since 0.0 is falsy)."""
    now = time.time() if now is None else now

    def _age(v) -> float:
        ts = v.get("ts") if isinstance(v, dict) else None
        return 0.0 if ts is None else max(0.0, now - float(ts))

    fresh = {k: v for k, v in state.items() if _age(v) <= _SCOPE_TTL_SECONDS}
    if len(fresh) <= _MAX_SCOPES:
        return fresh
    ranked = sorted(fresh.items(), key=lambda kv: _age(kv[1]))
    return dict(ranked[:_MAX_SCOPES])


# --- context builders ---------------------------------------------------------

def _git_branch(root: Path):
    """Current branch name, or None when git is absent / detached / errors.

    Reads .git/HEAD instead of spawning git: 0.02 ms against 1.67 ms, paid on
    every prompt and every session start. Two details the short version gets
    wrong, both pinned by tests:

    * a branch may contain slashes, so the `refs/heads/` PREFIX is stripped
      rather than the ref cut at its last segment — `feature/x` is not `x`;
    * in a LINKED WORKTREE `.git` is a file holding `gitdir: <path>`. Treating
      that as an error would silently drop the branch for every worktree, and
      worktree isolation is a normal mode of work here. The pointer may be
      relative, so it is resolved against the worktree root.

    Detached HEAD now yields None instead of the literal "HEAD" the subprocess
    reported. That matches what this docstring always claimed, and every caller
    already renders a missing branch as "" or "?" — "HEAD" is not a branch name.
    """
    try:
        gitdir = Path(root) / ".git"
        if gitdir.is_file():
            pointer = gitdir.read_text(encoding="utf-8").strip()
            if not pointer.startswith("gitdir:"):
                return None
            target = Path(pointer.split(":", 1)[1].strip())
            gitdir = target if target.is_absolute() else Path(root) / target
        head = (gitdir / "HEAD").read_text(encoding="utf-8").strip()
    except OSError:  # missing, unreadable, or a path component that is not a dir
        return None
    if not head.startswith("ref:"):
        return None  # a bare object id: detached, and not a branch
    ref = head.split(":", 1)[1].strip()
    if ref.startswith("refs/heads/"):
        ref = ref[len("refs/heads/"):]
    return ref or None


def _naming_stamp() -> str:
    """YYMMDD-HHMM stamp for report/plan naming, matching the repo convention."""
    return datetime.now().strftime("%y%m%d-%H%M")


def _second_tier_section() -> list:
    """One line, and only for a POSITIVELY recognised second-tier family.

    The skill bodies were thinned for a reader who infers the rest — which is what a
    frontier model does and what a smaller one does worse. The step-by-step layer was
    not deleted when they were thinned; it lives in each skill's `references/`. So the
    fallback is not a second copy of the prose to maintain, it is a pointer to the copy
    that is already there.

    Unknown families take the thin default: a new vendor or a typo must not silently
    inflate every prompt, which is the cost this whole pass removed.
    """
    try:
        import model_policy
        model = os.environ.get("ANTHROPIC_MODEL") or ""
        if not model_policy.is_second_tier(model):
            return []
    except Exception:  # noqa: BLE001 - a resolver hiccup takes the thin default
        return []
    return [
        "## Reading mode",
        "- Skill bodies here state the CONTRACT and leave the procedure to each skill's "
        "`references/`. When the next step is not obvious from the body, open the "
        "reference it names and follow it rather than inferring the steps.",
        "",
    ]


def _rule_routing_section(root: Path) -> list:
    """The load-on-demand INDEX, kept fresh so the agent never forgets which
    rules exist or that they must be loaded before the matching task. Globbed
    live from harness/rules/ — never a hand-maintained copy, so it cannot drift
    from the actual rule layer (the per-rule 'when' detail stays in CLAUDE.md)."""
    try:
        names = sorted(p.stem for p in (Path(root) / "harness" / "rules").glob("*.md"))
    except Exception:  # noqa: BLE001 - routing index is best-effort context
        names = []
    if not names:
        return []
    return [
        "## Rule routing (load on demand)",
        "Available in harness/rules/ — load the relevant one BEFORE the matching "
        "task (full 'when' mapping in CLAUDE.md): " + ", ".join(names),
        "",
    ]


def _active_plan(root: Path):
    """Absolute path of the most-recently-touched plans/<slug>/plan.md, or None.

    Salvaged from the upstream cook-after-plan-reminder: surfacing the plan path
    is the one durable bit of value (a fresh session after /clear can find where
    work lives). Mtime is the cheap proxy for 'active' — good enough, and far
    better than the static 'none' a file cannot keep current."""
    try:
        candidates = list((Path(root) / "plans").glob("*/plan.md"))
        if not candidates:
            return None
        return str(max(candidates, key=lambda p: p.stat().st_mtime))
    except Exception:  # noqa: BLE001 - plan lookup is best-effort context
        return None


def _context_sig(root: Path) -> str:
    """A stable fingerprint of the MEANINGFUL injected inputs — the active voice
    register, the output-config register knobs, the git branch, and the
    active-plan path — so a mid-window change to any of them forces a re-inject on
    the NEXT prompt instead of waiting out the turn throttle (the whole point: a
    knob you just toggled shows up now).

    Deliberately EXCLUDES the naming timestamp and the session clock: the stamp
    ticks every minute, so fingerprinting the rendered block would make the sig
    change every minute and defeat the throttle entirely. Only user-meaningful
    state belongs here. Best-effort: any read failure degrades to a constant
    part, never raises.

    Inject-domain knobs in the sig:
      voice_level, persona, terminal_voice_level, no_markdown, interview_rigor,
      action_prompting (terminal-voice.yaml) + code_style, audience, humanize
      (output.yaml) — every knob build_context renders is fingerprinted, so a
      toggle to any of them re-injects immediately."""
    parts = []
    try:
        import voice_prefs  # noqa: E402
        v = voice_prefs.load()
        parts.append("v=%s/%s/%s/%s/%s/%s/%s" % (
            v.get("voice_level"), v.get("persona"), v.get("terminal_voice_level"),
            v.get("no_markdown"), v.get("interview_rigor"),
            v.get("action_prompting"), v.get("persona_bundle")))
    except Exception:  # noqa: BLE001 - voice part is best-effort
        parts.append("v=?")
    # The output-config register knobs (output.yaml) are all injected now, so a
    # toggle to any must force a re-inject: code_style (inline code every turn),
    # audience (chat + report prose register), humanize (report directive).
    try:
        import output_config  # noqa: E402
        # resolve_all (NOT load): the injected text is built from resolve_all, which
        # applies the legacy output_style->code_style shim. Fingerprinting load()
        # would miss a shimmed code_style toggle (text changes, sig does not) and
        # silently defeat the re-inject throttle on the backward-compat path.
        oc = output_config.resolve_all()
        parts.append("o=cs%s/aud%s/hz%s" % (
            oc.get("code_style"), oc.get("audience"), oc.get("humanize")))
    except Exception:  # noqa: BLE001 - output_config part is best-effort
        parts.append("o=?")
    parts.append("b=%s" % (_git_branch(root) or ""))
    parts.append("p=%s" % (_active_plan(root) or ""))
    return "|".join(parts)


def _session_section() -> list:
    return [
        "## Session",
        "- DateTime: %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "- CWD: %s" % os.getcwd(),
        "- Timezone: %s" % (time.tzname[0] if time.tzname else "unknown"),
        "- OS: %s" % platform.system().lower(),
        "- User: %s" % (os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"),
        "- Locale: %s" % os.environ.get("LANG", ""),
        "- Delegate independent subtasks to subagents and keep working while they run; "
        "give each delegate a scoped prompt naming the files it may read and modify. "
        "Advisory subagents report findings and do not mutate plan/code unless tasked.",
        "- Include relevant environment information when prompting subagents.",
        "",
    ]


def _rules_section() -> list:
    return [
        "## Rules",
        '- Follow the harness rule layer in "%s" (load on demand; routing in CLAUDE.md).' % _RULES,
        '- Markdown files are organized in: Plans -> "{root}/plans" directory, '
        'Docs -> "{root}/docs" directory',
        '- **IMPORTANT:** DO NOT create markdown files outside of "{root}/plans" or '
        '"{root}/docs" UNLESS the user explicitly requests it.',
        "- When skills' scripts fail, report the failure unless the current task "
        "explicitly authorizes fixing skill code; only then fix and rerun.",
        "- Weigh simplicity against the codebase you are in: on a small or "
        "single-owner surface, prefer the least machinery that solves the case "
        "(YAGNI/KISS); on a long-lived or multi-team surface, the seam, the "
        "extension point and the explicit contract earn their cost. Deduplicate "
        "what shares a REASON to change, not what merely looks alike.",
        "- Lead with the outcome. Keep reports short by being selective about what goes "
        "in, not by compressing the writing into fragments or arrow chains.",
        "- In reports, list any unresolved questions at the end, if any.",
        "",
    ]


def _paths_section(plans: str, docs: str, reports: str) -> list:
    return [
        "## Paths",
        "Reports: %s | Plans: %s/ | Docs: %s/ | docs.maxLoc: %d"
        % (reports, plans, docs, _DOCS_MAXLOC),
        "",
    ]


def _plan_context_section(reports: str, branch, plan) -> list:
    lines = [
        "## Plan Context",
        "- Plan: %s" % (plan if plan else "none"),
        "- Reports: %s" % reports,
    ]
    if branch:
        lines.append("- Branch: %s" % branch)
    lines.append("")
    return lines


def _naming_section(plans: str, reports: str, stamp: str) -> list:
    return [
        "## Naming",
        "- Report: `%s{type}-%s-{slug}-report.md`" % (reports, stamp),
        "- Plan dir: `%s/%s-{slug}/`" % (plans, stamp),
        "- Replace `{type}` with: descriptive kebab-case purpose, agent handoff, "
        "or workflow context",
        "- Avoid generic report names like `review.md`, `report.md`, or `notes.md`",
        "- Replace `{slug}` with: descriptive-kebab-slug",
    ]


def _rule_pointer_section() -> list:
    """Diet B: a one-line pointer back to the rule layer instead of dumping the full
    Rules/Rule-routing sections every turn. CLAUDE.md (fresh at the top
    of the window) holds the when->rule routing; this just reminds the agent it exists
    and that markdown placement is fenced."""
    return [
        "## Rules",
        "- rules: %s (load on demand; full when->rule routing + ##Rule layer in "
        "CLAUDE.md). Re-read on drift; markdown only under plans/ or docs/." % _RULES,
        "",
    ]


def _slim_voice() -> str:
    """The live voice register on one line, carrying the literal `voice_level=<n>`
    the literal voice_level token so a substring assertion on a slim refresh survives. Reuses the
    unified resolver (resolve_all applies the output_style->code_style shim) —
    never reads a tracked file raw. Fail-open: any failure degrades to a marker."""
    try:
        import output_config  # noqa: E402
        oc = output_config.resolve_all()
        # Carry every knob the re-inject fingerprint (_context_sig) watches, so a
        # mid-window toggle that FORCES a refresh actually surfaces the changed
        # value in that (possibly slim) refresh instead of paying for a no-op.
        base = ("voice_level=%s persona=%s tvl=%s no_md=%s rigor=%s prompting=%s "
                "audience=%s code_style=%s humanize=%s") % (
            oc.get("voice_level"), oc.get("persona"), oc.get("terminal_voice_level"),
            oc.get("no_markdown"), oc.get("interview_rigor"), oc.get("action_prompting"),
            oc.get("audience"), oc.get("code_style"), oc.get("humanize"))
        # Pin the active persona-bundle CHARACTER (id + name + one-line gist) so it
        # does not drift out of attention between /compact re-fires. Nothing appended
        # when no bundle is active — byte-identical to the no-character case.
        return base + _persona_bundle_pin(oc.get("persona_bundle"))
    except Exception:  # noqa: BLE001 - voice line is best-effort context
        return "voice_level=?"


_PIN_GIST_MAX = 120


def _persona_bundle_pin(bundle_id) -> str:
    """The per-turn character pin: `persona_bundle=<id> (<name> — <one-line gist>)`.

    Keeps the CHARACTER present in attention every turn (the full SOUL + RELATIONSHIP
    stay SessionStart-only, not re-sent per turn). Returns "" when no bundle is active
    or the id no longer resolves — byte-identical to the no-character case. This runs
    only on the MAIN-only slim surface (UserPromptSubmit + Stop); it never reaches a
    subagent. Never raises (best-effort); the gist is capped so a long trait cannot
    bloat the slim budget."""
    if not bundle_id:
        return ""
    try:
        import persona_bundle  # noqa: E402 - lazy; leaf module
        b = persona_bundle.resolve(bundle_id)
        if b is None:
            return ""
        name = b.get("name") or bundle_id
        gist = (b.get("characteristic") or "").strip()
        if len(gist) > _PIN_GIST_MAX:
            gist = gist[:_PIN_GIST_MAX].rstrip() + "…"
        seg = " persona_bundle=%s (%s" % (bundle_id, name)
        if gist:
            seg += " — %s" % gist
        return seg + ")"
    except Exception:  # noqa: BLE001 - the pin is best-effort context
        return ""


def build_slim_context(root: Path) -> str:
    """The compact within-window refresh block (<= SLIM_BUDGET_CHARS). Carries the
    live voice register, the active plan + branch, the absolute report/plan paths +
    dated stamp (the hook's reason-for-existing), a mandatory directive with
    compact-hygiene, and a pointer back to the full rule layer. Drops the full-block
    headings (personal-first: no roster line at all)."""
    root = Path(root)
    plans = str(root / "plans")
    reports = str(root / "plans" / "reports") + os.sep
    branch = _git_branch(root) or "?"
    # Reports/Plans stay ABSOLUTE (a deep CWD writing a relative plans/ would spawn a
    # stray subtree — the hook's reason-for-existing). The plan path is READ-only, so it
    # rides relative to root: a wrong relative read just misses, it never mis-writes, and
    # the absolute root is right here on the Reports/Plans line for zero-indirection
    # resolution. This keeps the slim block within budget even when root is deep (a
    # harness worktree nests root ~50 chars deeper), instead of carrying the long root
    # prefix three times.
    plan_abs = _active_plan(root)
    plan = os.path.relpath(plan_abs, root) if plan_abs else "none"
    stamp = _naming_stamp()
    lines = [
        "[harness refresh - full rules loaded at session start] " + _slim_voice(),
        "posture: plan=%s branch=%s" % (plan, branch),
        "Reports:%s | Plans:%s/ | stamp:%s" % (reports, plans, stamp),
        _SLIM_DIRECTIVE,
        "tool cost: Read limit/offset + grep not cat + batch bash -> load "
        "harness/rules/agent-operational-discipline.md on heavy file/bash",
        # Name the load-bearing files, not just a bare rules dir: after a big /goal
        # Stop-gap the loop re-grounds with ZERO indirection. These are the ones NOT
        # otherwise named in slim — the active plan above (dynamic work-context), CLAUDE.md,
        # and the two auto-read prose standards. (harness/rules/ is already cited in the
        # tool-cost line above + CLAUDE.md's rule-routing section.)
        "reread on drift: active plan · CLAUDE.md · system-architecture · code-standards",
    ]
    return "\n".join(lines)


def _refresh_mode() -> str:
    """slim (default) | full, from the top-level `inject_refresh_mode` knob in
    harness-hooks.yaml. `full` restores the pre-slim behaviour verbatim (A/B
    baseline + instant rollback). Reads the RESOLVED document, so both the
    HARNESS_HOOK_CONFIG test seam and the per-project layer apply - opening the
    base file directly would answer with the shipped value and silently ignore
    what the project set. Fail-open: anything but a literal `full` -> `slim`."""
    try:
        raw = hook_runtime.hook_config_document()
        mode = (raw or {}).get("inject_refresh_mode")
        return "full" if mode == "full" else "slim"
    except Exception:  # noqa: BLE001 - malformed/missing config -> default slim
        return "slim"


def build_full_context(root: Path) -> str:
    """Legacy heavy block — restored only under inject_refresh_mode=full (instant
    rollback of the diet). Carries the static Session/Rules/Rule-routing
    sections a fresh session used to get every turn. Even here the voice register (a
    SessionStart dup, diet A) and the team roster (personal-first) stay dropped."""
    root = Path(root)
    plans = str(root / "plans")
    docs = str(root / "docs")
    reports = str(root / "plans" / "reports") + os.sep
    branch = _git_branch(root)
    stamp = _naming_stamp()
    plan = _active_plan(root)

    lines = []
    lines += _session_section()
    lines += [ln.replace("{root}", str(root)) for ln in _rules_section()]
    # `root` here is the PROJECT root (project-scoped plans/docs/reports); the rule
    # LAYER, by contrast, is bin-global — it ships in the engine, not the user repo —
    # so its routing index must glob the bin root even under a global/courier layout.
    lines += _rule_routing_section(harness_paths.bin_root())
    lines += _second_tier_section()
    lines += _paths_section(plans, docs, reports)
    lines += _plan_context_section(reports, branch, plan)
    lines += _naming_section(plans, reports, stamp)
    return "\n".join(lines)


def build_context(root: Path) -> str:
    """The default armed first-turn block (diet B): only the DYNAMIC context a static
    CLAUDE.md cannot carry — path layout, active plan + branch, dated naming pattern,
    and a one-line pointer back to the rule layer. The heavy static sections live in
    CLAUDE.md (fresh at the top of the window) and reload on demand; build_full_context
    restores them under the `full` knob. PURE given a root (only I/O is the best-effort
    git-branch + active-plan lookups). Absolute paths anchor every reference so a deep
    CWD cannot mislead file placement."""
    root = Path(root)
    plans = str(root / "plans")
    docs = str(root / "docs")
    reports = str(root / "plans" / "reports") + os.sep
    branch = _git_branch(root)
    stamp = _naming_stamp()
    plan = _active_plan(root)

    lines = []
    lines += _paths_section(plans, docs, reports)
    lines += _plan_context_section(reports, branch, plan)
    lines += _naming_section(plans, reports, stamp)
    lines += _rule_pointer_section()
    return "\n".join(lines)


def core(data: dict) -> str:
    # project_root() (NOT root()/bin_root()): the injected Plans/Reports/Docs are
    # project-scoped WRITES. Under a global/courier layout root() is the shared
    # read-only engine home, so a root()-based report path lands in the read-only bin
    # (write_guard blocks it) or a shared plans/ dir all projects collide in. The
    # sibling gates (gate_stage, write_guard, simplify_gate, secret_scan) already
    # split this way; a no-op under self-host where bin == project.
    return build_context(harness_paths.project_root())


def core_gated(data: dict):
    """Dispatcher entry: the decay-gated context block (or None). run() applies the
    same cadence then EMITS; the in-process dispatcher owns emission (it routes this
    return through context_surface_config), so this performs the identical decide() +
    per-scope state update and RETURNS the text-or-None instead of writing stdout.

    Wiring the raw core() as the dispatcher entry injected the full block on EVERY
    prompt — the decay cadence (decide + the per-cwd turn/arm/sig state) lives in run(),
    which the dispatcher bypasses by calling core() directly. Mirror it here."""
    d = data if isinstance(data, dict) else {}
    event = d.get("hook_event_name") or "UserPromptSubmit"
    scope = d.get("cwd") or os.getcwd()
    state = _load_state()
    current_sig = _context_sig(harness_paths.project_root())
    prior = state.get(scope)
    fill_ratio_val, threshold_val = _adaptive_params(d.get("transcript_path"))
    should, new_scope = decide(prior, event, d.get("source"), current_sig, _every_turns(),
                                fill_ratio_val, threshold_val)
    was_armed = bool((prior or {}).get("force", _ARMED_DEFAULT))
    # Mirror run():689-691 — scope_hint_advisory ships default-OFF; core_gated is
    # the LIVE dispatcher entry, so it must honor the same knob run() does instead
    # of appending the advisory on every qualifying prompt regardless of config.
    hint_on = _scope_hint_enabled()
    want_hint = hint_on and _scope_suggestion_wanted(d.get("prompt"))
    carry = hint_on and (want_hint or bool((prior or {}).get("pending_hint")))
    new_scope["ts"] = time.time()
    state[scope] = new_scope
    if should:
        root = harness_paths.project_root()
        # Block choice is INTENTIONALLY split by arm state (design decision, not drift):
        #   armed  -> build_context()      = the full Paths/Plan/Naming/Rules orientation
        #   refresh-> build_slim_context() = the compact voice-register + posture reminder
        # The first turn orients; periodic within-window refreshes only re-assert the
        # register that decays over a long context. When the working context FADES, the
        # armed branch re-serves the full build_context() block — decide() re-arms
        # `force` on any SessionStart AND on a sig change (voice/output/branch/plan), so a
        # /clear, a re-open, or a knob toggle brings the full orientation back on the next
        # prompt; you never have to hand-trigger it.
        if _refresh_mode() == "full":
            text = build_full_context(root)
        elif was_armed:
            text = build_context(root)
        else:
            text = build_slim_context(root)
        if carry and text:
            text += "\n" + _SCOPE_HINT_LINE
        _save_state(_prune_scopes(state))
        return text or None
    if carry:
        new_scope["pending_hint"] = True
        state[scope] = new_scope
    _save_state(_prune_scopes(state))
    return None


def _emit_context(text: str, event_key: str = "user_prompt_submit") -> None:
    # Route through the shared co-emit chokepoint. The MODEL always gets `text` via
    # additionalContext (UPS AC is SILENT to the human; SessionStart likewise); the
    # config surface optionally adds a human systemMessage mirror. One place, so UPS +
    # SessionStart + Stop + SubagentStart cannot drift on which channel renders.
    try:
        import context_surface_config as _cs
        _cs.emit(event_key, text)
        return
    except Exception as e:  # noqa: BLE001 — surface config never breaks injection
        hook_runtime.log_hook_error("inject_prompt_context", e)
    # fail-open: raw additionalContext under the correct event name, no human mirror
    hook_event = "SessionStart" if event_key == "session_start" else "UserPromptSubmit"
    sys.stdout.write(json.dumps({"hookSpecificOutput": {
        "hookEventName": hook_event, "additionalContext": text}}))
    sys.stdout.flush()


_SCOPE_HINT_LINE = (
    "scope-hint: this looks like a small/trivial task under a heavy skill - if it "
    "really is trivial, consider a lighter path than the full plan/cook ceremony "
    "(advisory only; nothing was changed or downgraded)."
)


def _scope_hint_enabled() -> bool:
    """Read the top-level `scope_hint_advisory` knob from harness-hooks.yaml. Ships
    default-OFF (a coarse text classifier over-fires the nudge on prose tasks); flip
    it on per-project via that project's own harness-hooks.yaml layer. Reads the
    RESOLVED document so the layer applies; opening the base file directly would
    answer with the shipped value. Fail-open: anything but a literal
    true/on -> False (off)."""
    try:
        raw = hook_runtime.hook_config_document()
        val = (raw or {}).get("scope_hint_advisory")
        return val is True or (isinstance(val, str) and val.strip().lower() in ("true", "on", "1"))
    except Exception:  # noqa: BLE001 - malformed/missing config -> default off
        return False


def _scope_suggestion_wanted(prompt_text) -> bool:
    """True only when the prompt is a TRIVIAL task invoked under a heavy SDLC skill
    - the single case Lever A appends its advisory. Risky or non-heavy prompts
    return False; it never downgrades, only nudges. Fail-open: any error -> False."""
    try:
        import scope_hint  # noqa: E402
        v = scope_hint.classify(prompt_text)
        return bool(v.get("heavy_skill") and v.get("level") == "trivial")
    except Exception:  # noqa: BLE001 - the advisory is best-effort, never load-bearing
        return False


def run(raw=None) -> None:
    """Telemetry-class + fail-open. Updates the per-cwd cadence state, then emits
    the context block only when the decay signal says to; otherwise a plain
    continue. Disabled or any exception -> plain continue. Never exits 2."""
    data = hook_runtime.read_stdin_json() if raw is None else hook_runtime._parse(raw)
    try:
        if hook_runtime.hook_enabled("inject_prompt_context", "telemetry"):
            event = data.get("hook_event_name") or "UserPromptSubmit"
            scope = data.get("cwd") or os.getcwd()
            state = _load_state()
            current_sig = _context_sig(harness_paths.project_root())
            prior = state.get(scope)
            fill_ratio_val, threshold_val = _adaptive_params(data.get("transcript_path"))
            should, new_scope = decide(prior, event, data.get("source"), current_sig,
                                        _every_turns(), fill_ratio_val, threshold_val)
            # Read the arm flag from the PRIOR state (before decide reset it): the
            # first injection after a session boundary is armed -> full; a later
            # within-window refresh is not armed -> slim (unless the toggle forces full).
            was_armed = bool((prior or {}).get("force", _ARMED_DEFAULT))
            # Lever A: classify EVERY prompt. A trivial task under a heavy skill
            # earns a one-line advisory on the turn we actually inject; a throttled
            # verdict is cached (pending_hint) so it surfaces on the next injection
            # instead of being lost, since the heavy-skill turn is often throttled.
            hint_on = _scope_hint_enabled()
            want_hint = hint_on and _scope_suggestion_wanted(data.get("prompt"))
            carry = hint_on and (want_hint or bool((prior or {}).get("pending_hint")))
            new_scope["ts"] = time.time()
            state[scope] = new_scope
            if should:
                root = harness_paths.project_root()
                if _refresh_mode() == "full":
                    text = build_full_context(root)
                elif was_armed:
                    text = build_context(root)
                else:
                    text = build_slim_context(root)
                if carry and text:
                    text += "\n" + _SCOPE_HINT_LINE
                # new_scope carries no pending_hint -> the cache clears on emit
                _save_state(_prune_scopes(state))
                if text:
                    _emit_context(text, "session_start" if event == "SessionStart"
                                  else "user_prompt_submit")
                    return
            else:
                if carry:
                    new_scope["pending_hint"] = True
                    state[scope] = new_scope
                _save_state(_prune_scopes(state))
    except Exception as e:  # noqa: BLE001 - injection must never break the session
        hook_runtime.log_hook_error("inject_prompt_context", e)
    hook_runtime.emit_continue()


def main(raw=None) -> None:
    run(raw=raw)


if __name__ == "__main__":
    main()
