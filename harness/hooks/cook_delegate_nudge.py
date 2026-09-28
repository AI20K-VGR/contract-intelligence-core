#!/usr/bin/env python3
"""cook_delegate_nudge.py — advisory backstop for cook's per-phase delegate-by-default.

On a `mode: hard` plan the per-phase implement loop (3.I) is supposed to go to a
`@developer` subagent (main keeps verify + the paired commit). That posture is PROSE,
not a gate — nothing blocks an inline run — so a fresh clean-context cook can dive
straight into implementing inline and silently skip the delegation. This hook is the
soft reminder: when the MAIN agent writes non-test SOURCE while a `mode: hard` plan is
in_progress, it fires ONCE (per plan/session) to say "delegate 3.I, or opt into inline
explicitly (--in-place / a phase `in_place: true`)".

The discriminator is agent IDENTITY, not stateful phase-window counting: a write that
carries an `agent_type`/`subagent_type` attribution IS the delegation (a subagent is
doing it) → stay silent. A write with attribution ABSENT is the main thread → the
inline case worth flagging. This sidesteps tracking "0 Task calls this phase".

Nudge posture: default-ON, advisory, fail-open — writes a reminder to its configured
sink and ALWAYS continues (never exit 2). Deduped once per (session, plan) so a phase
full of writes nudges once, not per-file. The binding HOOK_CLASS lives here in code.

Scope note: this is deliberately cook-only (plan-bound). The reliable predicate —
in_progress `mode: hard` plan + main-agent source write — only exists where a plan is
being cooked phase-by-phase; a generic "you have subagents but ran inline" nudge across
every skill would be a false-positive machine (small fixes, --in-place, advisory skills
all run inline legitimately). Sibling skills that grow their own delegate-by-default
posture should get their own predicate, not widen this one.
"""

import fnmatch
import os
import sys
from pathlib import Path

# Diagnostic text carries Vietnamese; guard stderr encoding so a non-UTF-8 locale
# degrades to replacement chars instead of raising mid-write (fail-open).
try:
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001 — older streams / already-detached; never fatal
    pass

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HOOKS_DIR, "..", "scripts"))
if _HOOKS_DIR not in sys.path:
    sys.path.append(_HOOKS_DIR)
import hook_runtime  # noqa: E402
import nudge_dedupe  # noqa: E402

HOOK_CLASS = "nudge"
_NAME = Path(__file__).stem
_DEDUPE_KIND = "cook_delegate"

_WRITE_TOOLS = {"Write", "Edit", "MultiEdit"}

# Only a code-source write is a 3.I implement. A doc/config/data write, a test file,
# an artifact — none are the implement step, so none should nudge. An explicit code
# allowlist keeps false positives near zero (config/docs never trip it).
_CODE_EXTS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".go", ".rs", ".java",
    ".rb", ".php", ".c", ".cc", ".cpp", ".h", ".hpp", ".cs", ".kt", ".swift",
    ".scala", ".sh", ".sql",
}

# Phase frontmatter values that mean "this phase runs inline on purpose".
_INLINE_MODES = {"fast", "inline"}
_INLINE_DELEGATE = {"inline", "false", "no", "off"}


def _root() -> Path:
    """The project root whose plans/ we resolve the active plan under. CLAUDE_PROJECT_DIR
    (host-set) wins; then HARNESS_ROOT (test/self-host seam); then cwd."""
    raw = hook_runtime.project_dir() or os.environ.get("HARNESS_ROOT") or os.getcwd()
    return Path(raw)


def _has_agent_attribution(data: dict) -> bool:
    """True when the write carries a non-empty subagent attribution — i.e. a subagent
    (not the main thread) is doing it, which IS the delegation. Read straight off the
    top-level payload, not via resolve_actor (session_id is shared)."""
    for key in ("agent_type", "subagent_type"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return True
    return False


def _target_rel(data: dict, root: Path):
    """The write target as a path relative to root (best-effort). Returns a POSIX-ish
    relative string, or None when there is no path."""
    ti = data.get("tool_input") or {}
    raw = ti.get("file_path") or ti.get("path") or ti.get("notebook_path")
    if not raw:
        return None
    p = Path(str(raw))
    try:
        return p.resolve().relative_to(root.resolve()).as_posix()
    except (ValueError, OSError):
        # Outside root or unresolvable — fall back to the raw string; classification
        # below still works off basename/suffix.
        return p.as_posix()


def _is_implement_source(rel: str) -> bool:
    """True when rel is a code-source implement target: a known code ext, NOT a test
    file, NOT under a docs/plans tree."""
    low = rel.lower()
    parts = low.split("/")
    base = parts[-1]
    if Path(low).suffix not in _CODE_EXTS:
        return False
    if base.startswith("test_") or base.endswith("_test.py") or ".test." in base or ".spec." in base:
        return False
    if any(seg in ("tests", "test", "__tests__") for seg in parts[:-1]):
        return False
    if parts[0] in ("docs", "plans"):
        return False
    return True


def _read_frontmatter(text: str) -> dict:
    """Parse a leading `--- ... ---` YAML frontmatter block to a dict. Any error → {}
    (fail-open — a nudge never breaks on a malformed phase file)."""
    if not text.startswith("---"):
        return {}
    body = text[3:]
    end = body.find("\n---")
    if end == -1:
        return {}
    block = body[:end]
    try:
        data = hook_runtime.yaml_load(block)
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001 — fail-open
        return {}


def _glob_match(rel: str, pattern: str) -> bool:
    """fnmatch with a `**` that also matches across path separators (fnmatch already
    lets `*` span `/`, so `**` collapses to `*`)."""
    pat = str(pattern).strip()
    if not pat:
        return False
    return fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(rel, pat.replace("**", "*"))


def _phase_opts_inline(plan_dir: Path, rel: str) -> bool:
    """True when a phase covering `rel` opts into inline via its frontmatter:
    `in_place: true`, `mode: fast|inline`, or `delegate: inline|false`. Its `owns`
    globs must match `rel` (an unscoped phase override does not silence unrelated
    writes). Fail-open: any read/parse error → False (do not suppress)."""
    phdir = plan_dir / "phases"
    if not phdir.is_dir():
        return False
    for ph in phdir.glob("*.md"):
        try:
            fm = _read_frontmatter(ph.read_text(encoding="utf-8"))
        except OSError:
            continue
        inline = (
            bool(fm.get("in_place"))
            or str(fm.get("mode", "")).strip().lstrip("-").lower() in _INLINE_MODES
            or str(fm.get("delegate", "")).strip().lower() in _INLINE_DELEGATE
        )
        if not inline:
            continue
        owns = fm.get("owns") or []
        if isinstance(owns, str):
            owns = [owns]
        if any(_glob_match(rel, pat) for pat in owns):
            return True
    return False


def _plan_mode(plan_dir: Path) -> str:
    """The plan's frontmatter `mode:` (normalized, leading `--` stripped), or ''."""
    try:
        fm = _read_frontmatter((plan_dir / "plan.md").read_text(encoding="utf-8"))
    except OSError:
        return ""
    return str(fm.get("mode", "")).strip().lstrip("-").lower()


def core(data: dict, root: Path):
    """Return (advisory, plan_name) iff a MAIN-agent write is implementing inline
    source under a `mode: hard` in_progress plan whose covering phase did NOT opt into
    inline; else None. Routing + dedupe are the caller's job — this never blocks."""
    if data.get("tool_name") not in _WRITE_TOOLS:
        return None
    if _has_agent_attribution(data):
        return None  # a subagent is writing — this IS the delegation
    rel = _target_rel(data, root)
    if not rel or not _is_implement_source(rel):
        return None

    from artifact_check import resolve_active_plan
    plan_dir = resolve_active_plan(root)
    if plan_dir is None:
        return None
    if _plan_mode(plan_dir) != "hard":
        return None  # only a hard plan carries the delegate-by-default expectation
    if _phase_opts_inline(plan_dir, rel):
        return None

    msg = (
        "[nudge] cook_delegate: plan `mode: hard` — the per-phase implement (3.I) is "
        "delegate-by-default. Hand this write to a `@developer` subagent (main keeps "
        "verify + the paired commit), OR opt into inline explicitly with `--in-place` "
        "or a phase `in_place: true`. Advisory, non-blocking.\n"
    )
    return msg, plan_dir.name


def core_dispatch(data: dict):
    """In-process dispatcher entry: a single-arg core(data) that resolves the project
    root, applies the once-per-(session, plan) dedupe, and RETURNS the advisory string
    (or None). The dispatcher runs this instead of main() and emits the return value
    unconditionally, so the dedupe MUST live here — otherwise the nudge would fire on
    every source write in the phase instead of once. Fail-open: any error → None."""
    if not isinstance(data, dict):
        return None
    try:
        hit = core(data, _root())
    except Exception as e:  # noqa: BLE001 — a nudge never blocks the tool
        hook_runtime.log_hook_error(_NAME, e)
        return None
    if not hit:
        return None
    msg, subject = hit
    session = data.get("session_id") or os.environ.get("HARNESS_SESSION_ID") or ""
    if nudge_dedupe.already_nudged(session, _DEDUPE_KIND, subject):
        return None
    nudge_dedupe.mark_nudged(session, _DEDUPE_KIND, subject)
    return msg


def main() -> int:
    # Nudge structure mirrors cook_isolation_nudge: honor the config gate, run the
    # detector fail-open, dedupe once per (session, plan), then route via
    # emit_nudge_and_continue (config sink) + ALWAYS continue.
    if not hook_runtime.hook_enabled(_NAME, HOOK_CLASS):
        hook_runtime.emit_continue()
        return 0
    data = hook_runtime.read_stdin_json()
    d = data if isinstance(data, dict) else {}
    try:
        hit = core(d, _root())
        if hit:
            msg, subject = hit
            session = d.get("session_id") or os.environ.get("HARNESS_SESSION_ID") or ""
            if not nudge_dedupe.already_nudged(session, _DEDUPE_KIND, subject):
                nudge_dedupe.mark_nudged(session, _DEDUPE_KIND, subject)
                hook_runtime.emit_nudge_and_continue(_NAME, msg, d)
                return 0
    except Exception as e:  # noqa: BLE001 — fail-open: a nudge never blocks the tool
        hook_runtime.log_hook_error(_NAME, e)
    hook_runtime.emit_continue()
    return 0


if __name__ == "__main__":
    sys.exit(main())
