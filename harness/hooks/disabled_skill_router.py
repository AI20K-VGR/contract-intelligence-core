#!/usr/bin/env python3
"""disabled_skill_router.py — PreToolUse(Skill) block-with-map for an off skill.

When the model invokes the Skill tool on a skill this install DISABLED (omitted at the
dir level), this gate blocks the raw call and replies with the three sanctioned ways
forward — the "block-with-map" (router chặn-kèm-bản-đồ):

    1. /hs:use <name>                       — the proxy that loads + runs the off skill
    2. read the stash SKILL.md at <abs path> — do it inline
    3. hs_cli.py skills --enable <name>     — turn it back on

A live or unknown target passes silently — the router only ever speaks to redirect an
off skill, never to slow a normal call.

HOOK_CLASS = compliance: it exits 2 to BLOCK. Deliberate, documented deviation from the
compliance contract (shared with model_guard): an INTERNAL ERROR fails OPEN
(exit 0) so a broken disabled-state source — a corrupt omit record, an unlistable stash —
does NOT brick every skill call in the session. Only a real "target is disabled" decision
exits 2, and that exit sits OUTSIDE the fail-open try so a broad except can never swallow
it and turn the gate dark. The single switch is the registration toggle
`disabled_skill_router.enabled` (compliance default True).

Whether PreToolUse(Skill) even fires for an omitted skill (the host may validate the
enum-catalog before hooks run) is the live probe deferred to P3; the same 3-path map also
reaches the model via disabled_ref_nudge + hs:use, so the deliverable never rests on this
hook alone.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.join(os.path.dirname(_HERE), "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import hook_runtime  # noqa: E402

HOOK_CLASS = "compliance"
_HOOK = "disabled_skill_router"


def _target_slug(data: dict) -> str:
    """The invoked skill name from a PreToolUse(Skill) payload, normalized to a bare
    slug: 'hs:ask' / '/hs:ask' / 'ask' → 'ask'. '' when no skill name is present."""
    ti = data.get("tool_input")
    raw = ""
    if isinstance(ti, dict):
        raw = ti.get("skill") or ti.get("name") or ""
    raw = str(raw).strip().lstrip("/")
    if raw.lower().startswith("hs:"):
        raw = raw[3:]
    raw = raw.strip().split()[0] if raw.strip() else ""
    return raw.lower()


def _block_reason(slug: str, sp) -> str:
    path = str(sp) if sp else "harness/plugins/hs/disabled-skills/%s" % slug
    return (
        "skill '%s' is install-disabled (omitted). Do NOT call it raw — take one of "
        "three paths: (1) run the proxy `/hs:use %s` (loads its off deps + runs it); "
        "(2) read the stash SKILL.md at %s and perform it inline; "
        "(3) re-enable it: `python3 harness/scripts/hs_cli.py skills --enable %s`."
        % (slug, slug, path, slug)
    )


def core(data: dict):
    """Return a BLOCK reason string when a Skill call targets an install-disabled skill,
    else None. Stdout-free (no emit/exit) so the in-process dispatcher can call it; the
    caller owns the terminal write. Records re-enable demand as a caged side effect.
    Fail-open BY DESIGN — the caller wraps it so a crash never wedges a call."""
    slug = _target_slug(data)
    if not slug:
        return None  # no skill name to gate
    import disabled_skills
    root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    sources = disabled_skills.default_sources(root)
    if slug not in disabled_skills.effective_disabled(sources):
        return None  # live / unknown — free
    sp = disabled_skills.stash_path(slug, sources)
    reason = _block_reason(slug, sp)
    # Secondary re-enable signal: record demand for this off skill. Individually caged —
    # a broken emit must NOT turn the block dark (the block does not depend on it).
    try:
        import emit_disabled_demand
        emit_disabled_demand.emit(slug, "router_block", data.get("session_id"))
    except Exception as ee:  # noqa: BLE001 — demand is telemetry; never gates the block
        hook_runtime.log_hook_error(_HOOK, ee)
    return reason  # deliberate block


def main() -> None:
    # 1. Registration toggle is the ONLY switch. A broken enabled read fails OPEN.
    try:
        if not hook_runtime.hook_enabled(_HOOK, HOOK_CLASS):
            hook_runtime.emit_continue()
            sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001 — a broken enabled read must not wedge a call
        hook_runtime.log_hook_error(_HOOK, e)
        hook_runtime.emit_continue()
        sys.exit(0)

    # Every internal error from here fails OPEN (documented deviation).
    try:
        reason = core(hook_runtime.read_stdin_json())  # {} on empty/malformed
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001 — FAIL-OPEN: a router crash never wedges a call
        hook_runtime.log_hook_error(_HOOK, e)
        reason = None
    if reason:
        # The only exit-2 path — deliberate block, kept outside the fail-open try.
        sys.stderr.write("[%s] BLOCKED: %s\n" % (_HOOK, reason))
        sys.exit(2)
    hook_runtime.emit_continue()
    sys.exit(0)


if __name__ == "__main__":
    main()
