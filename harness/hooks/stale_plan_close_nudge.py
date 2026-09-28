#!/usr/bin/env python3
"""stale_plan_close_nudge.py — advisory reminder to close a finished-but-open
plan before it gates unrelated work (nudge class).

The failure mode: cook finishes a plan green (writes verification.json verdict
PASS) but the finalize step that flips plan.md status to completed gets skipped
on an autonomous run. The gate's active-plan resolver only ever returns an
in_progress plan, so that stale plan stays "active" and blocks the next push/
ship — even one with nothing to do with it.

This hook fires on a publish-adjacent skill (hs:ship / hs:git) and points at the
fix when a cooked-but-not-closed plan is present. It looks across the WHOLE
corpus, not just the single resolver-active plan: the dominant real case is a
plan left at pending/approved carrying a PASS artifact (cook wrote the artifact but
neither open_plan nor close_plan ran), which resolve_active_plan never sees.
Keyed on the machine artifact (verdict PASS), not the human checkbox, so it
fires exactly when a close/reconcile would have helped.

Nudge posture: advisory, fail-open — stderr reminder only, ALWAYS continues
(never exit 2). The binding HOOK_CLASS lives here in code, never in config.
"""
import os
import sys
from pathlib import Path

try:
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001 — older streams / already-detached; never fatal
    pass

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HOOKS_DIR, "..", "scripts"))
if _HOOKS_DIR not in sys.path:
    sys.path.append(_HOOKS_DIR)
import hook_runtime  # noqa: E402

HOOK_CLASS = "nudge"
_NAME = Path(__file__).stem

# Publish-adjacent skills: the moments a lingering done-but-open plan actually
# bites (it gates the imminent push/ship). Cook itself is excluded — a mid-cook
# plan can legitimately hold a PASS for an earlier phase.
_PUBLISH_SKILLS = {"hs:ship", "ship", "hs:git", "git"}


def _root() -> Path:
    # The project being worked on — under a global install HARNESS_ROOT
    # points at the shared bin, so prefer the project-dir resolver; keep the
    # HARNESS_ROOT/cwd fallback so the nudge never resolves to None.
    return Path(hook_runtime.project_dir() or os.environ.get("HARNESS_ROOT") or ".")


def stale_done_plan(root=None):
    """The active plan dir IFF it is in_progress yet already verified PASS — the
    state a forgotten close leaves behind — else None. Fail-open: any error in
    resolution or artifact read returns None (a nudge never raises).

    Retained for the resolver-active case and its callers; the corpus-wide
    detector below (cooked_open_plans) is the broader one used by core."""
    root = Path(root) if root is not None else _root()
    try:
        import artifact_check as ac
        plan_dir = ac.resolve_active_plan(root)  # only ever an in_progress plan
        if plan_dir is None:
            return None
        # Read the verification artifact in EITHER format (.yaml preferred, .json
        # legacy) via the shared loader, so the nudge keeps firing after the
        # SSOT-YAML migration instead of silently going quiet.
        rec, problem = ac._load_artifact(plan_dir, "verification")
        if rec is None:
            return None
        verdict = str(rec.get("verdict") or "").strip().upper()
        return plan_dir if verdict == "PASS" else None
    except Exception:  # noqa: BLE001 — nudge is fail-open
        return None


# A plan in any of these states that already carries a PASS verification is
# "cooked but not closed". The legacy resolver only ever sees in_progress; the
# pending/approved cases are the dominant gap (cook wrote PASS but neither
# open_plan nor close_plan ran), invisible to resolve_active_plan. Status is read
# via normalize_status, so a legacy draft/awaiting plan folds to pending and is
# still caught here.
_OPEN_STATES = {"pending", "approved", "in_progress"}


def cooked_open_plans(root=None):
    """Every plan dir whose status is still open (pending/approved/in_progress) yet
    whose verification artifact reads PASS — the cooked-but-not-closed set across
    the WHOLE corpus, not just the single resolver-active plan. Fail-open: any
    error skips that plan; the list is best-effort and a nudge never raises."""
    root = Path(root) if root is not None else _root()
    out = []
    try:
        import artifact_check as ac
        import plan_status as ps
    except Exception:  # noqa: BLE001 — nudge is fail-open
        return out
    try:
        plan_mds = sorted((root / "plans").glob("*/plan.md"))
    except Exception:  # noqa: BLE001
        return out
    for pm in plan_mds:
        d = pm.parent
        if d.name in ("reports", "templates"):
            continue
        try:
            text = pm.read_text(encoding="utf-8")
            fm = ps._FRONTMATTER_RE.match(text)
            if not fm:
                continue
            sm = ps._STATUS_RE.search(fm.group(1))
            if not sm or ps.normalize_status(sm.group(1)) not in _OPEN_STATES:
                continue
            rec, _problem = ac._load_artifact(d, "verification")
            if rec is None:
                continue
            if str(rec.get("verdict") or "").strip().upper() == "PASS":
                out.append(d)
        except Exception:  # noqa: BLE001 — skip a bad plan, never raise
            continue
    return out


def _incoming_skill(data: dict) -> str:
    if data.get("tool_name") == "Skill":
        inp = data.get("tool_input") or {}
        return str(inp.get("skill") or inp.get("name") or "")
    return ""


def core(data: dict):
    """Return the advisory iff a publish-adjacent skill is starting AND at least
    one cooked-but-open plan exists anywhere in the corpus, else None. Routing is
    the caller's job via emit_nudge — never blocks. Points at close_plan for the
    single in_progress case and at reconcile for the bulk pending/approved audit."""
    if _incoming_skill(data) not in _PUBLISH_SKILLS:
        return None
    plans = cooked_open_plans()
    if not plans:
        return None
    names = ", ".join(p.name for p in plans)
    return (
        "[nudge] stale_plan_close: %d plan(s) verified PASS but still open "
        "(%s) — each will gate this and later push/ship until closed. Close an "
        "in_progress one: python3 harness/scripts/close_plan.py <plan-dir> . "
        "Audit/repair the whole set (incl. pending/approved): "
        "python3 harness/scripts/reconcile_plan_status.py . Advisory, "
        "non-blocking.\n" % (len(plans), names)
    )


def main() -> int:
    if not hook_runtime.hook_enabled(_NAME, HOOK_CLASS):
        hook_runtime.emit_continue()
        return 0
    data = hook_runtime.read_stdin_json()
    d = data if isinstance(data, dict) else {}
    try:
        msg = core(d)
        if msg:
            hook_runtime.emit_nudge_and_continue(_NAME, msg, d)
            return 0
    except Exception as e:  # noqa: BLE001 — fail-open: a nudge never blocks the tool
        hook_runtime.log_hook_error(_NAME, e)
    hook_runtime.emit_continue()
    return 0


if __name__ == "__main__":
    sys.exit(main())
