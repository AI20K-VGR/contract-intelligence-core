#!/usr/bin/env python3
"""plannotator_wrapper_guard.py — PreToolUse compliance gate: force the annotate review
through the wrapper.

Two entries, one module, one break-glass switch:
  * bash_core  — PreToolUse(Bash): blocks a bare `plannotator annotate ...` shell command
    (typed by hand, or a bare-skill !command if it surfaces as a Bash tool call).
  * skill_core — PreToolUse(Skill): blocks a Skill(plannotator-annotate) call before the
    bare !command can even run (the primary model channel).

Both redirect to the wrapper `harness/scripts/plannotator_surface.py annotate`, which
injects `--gate` + globs the whole phase directory: the reviewer then sees every phase
file and gets a real Approve button on the plan. A bare invocation lacks `--gate` → the
UI opens annotation-only (Send/Close, no Approve) → the review session closes with no
decision. Fixing a repeated failure that had only prose advice behind it before.

Scope is annotate ONLY: `review` has no `--gate` flag in the binary, so a bare `review`
== the wrapper `review` at the command level — gating it would buy tracing, not an Approve
button, so it is deliberately left alone (with the other 4 plannotator skills). The wrapper
itself passes both gates: its command token is `plannotator_surface.py` (not
`plannotator annotate`), and it shells out to the binary via subprocess INSIDE Python —
not a Bash tool call, so no hook sees it.

Posture: compliance class — but the RUNTIME crash/timeout path fails OPEN. This gate is in
the "redirect" family (like disabled_skill_router / model_guard): a hard block whose
own runtime error must never wedge a whole session's Bash or Skill lane. Each core swallows
its own runtime errors → None, and both dispatch rows carry `fail_open: true` as the second
belt. (A module-LOAD failure — a broken import or a renamed entry — still fails closed at the
dispatcher like every other gate; that is the dispatcher's contract, not this gate's to
override.) Only a real "bare annotate" decision returns a reason and blocks.

Residual (documented, not chased): a determined operator can spell around the Bash regex
(`bash -c "..."`, `$(...)`, `pla""nnotator`, an alias) — the same not-airtight class the
bash_safety_guard template already accepts. The model rarely fights its own guard, and the
Skill lane catches the model-tool path regardless.

HOOK_CLASS is a code constant; config (harness-hooks.yaml) can only toggle enabled/mode,
never reclassify the gate. Break-glass: `plannotator_wrapper_guard: {enabled: false}`
silences BOTH lanes (both dispatch rows share the name) — the diff is tracked and the
skip is visible.
"""

import os
import re
import sys
from pathlib import Path

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HOOKS_DIR, "..", "scripts"))
if _HOOKS_DIR not in sys.path:
    sys.path.append(_HOOKS_DIR)
import hook_runtime  # noqa: E402

HOOK_CLASS = "compliance"
_NAME = Path(__file__).stem

# annotate ONLY (DEC-D/E: review has no --gate, so gating it buys only tracing).
_GATED_SKILLS = {"plannotator-annotate"}

# A trailing `#...` comment (at a word boundary) is not part of any command.
_COMMENT_RE = re.compile(r"(?:^|\s)#[^\n]*")
# Quoted spans — a mention inside a quote (`echo "..."`, `git commit -m "..."`) is a
# string literal, not an invocation.
_QUOTED_SPAN_RE = re.compile(r"'[^']*'|\"[^\"]*\"")

# Bare `plannotator annotate`: the binary token `plannotator` at a word boundary (so an
# absolute path /usr/local/bin/plannotator still matches) immediately followed by the
# `annotate` verb. The wrapper's `plannotator_surface.py` does NOT match — an `_` follows
# `plannotator`, not the required whitespace. `review` is intentionally not matched (DEC-E).
_BARE_ANNOTATE_RE = re.compile(r"\bplannotator\s+annotate\b")


def _verb_view(cmd: str) -> str:
    """Comment → spaces, quoted SPANS → underscores (content destroyed); length-
    preserving. A `plannotator annotate` living inside a quote or a comment is then not
    read as a command — killing false positives like `echo "plannotator annotate"` and
    `git commit -m "use plannotator annotate"`. Mirrors bash_safety_guard._verb_view."""
    s = _COMMENT_RE.sub(lambda m: " " * len(m.group(0)), cmd)
    return _QUOTED_SPAN_RE.sub(lambda m: "_" * len(m.group(0)), s)


def _reason() -> str:
    """The single block reason (annotate only). Cites the wrapper path, NOT the bare-skill
    install path — the CI invariant bans citing that dot-claude tree literal inside harness."""
    return (
        "bare `plannotator annotate` opens the annotation-only UI (Send/Close, no Approve) "
        "→ the review closes with no decision. Run it through the wrapper: "
        "`python3 harness/scripts/plannotator_surface.py annotate <target>` — it injects "
        "`--gate` and globs the whole phase directory, so the reviewer sees every phase "
        "file and gets a real Approve button on the plan."
    )


def bash_core(data: dict):
    """PreToolUse(Bash) core: None ⇒ allow; str ⇒ block reason. Blocks a bare
    `plannotator annotate` shell command unconditionally (DEC-C: no `--gate` escape).
    Fails OPEN on any internal error (defense-in-depth with the row's fail_open)."""
    try:
        if data.get("tool_name") != "Bash":
            return None
        cmd = hook_runtime.bash_command(data)
        if not cmd.strip():
            return None  # no command to gate → fail-open
        if not _BARE_ANNOTATE_RE.search(_verb_view(cmd)):
            return None
        return _reason()
    except Exception:  # noqa: BLE001 — F1 fail-open: never wedge the Bash lane
        return None


def _skill_slug(data: dict) -> str:
    """The invoked skill name from a PreToolUse(Skill) payload, normalized to a bare slug
    that KEEPS the hyphen: strip a leading '/', an 'hs:' prefix, lowercase, first token.
    'plannotator-annotate' stays 'plannotator-annotate'. '' when no skill name is present.
    Mirrors disabled_skill_router._target_slug."""
    ti = data.get("tool_input")
    raw = ""
    if isinstance(ti, dict):
        raw = ti.get("skill") or ti.get("name") or ""
    raw = str(raw).strip().lstrip("/")
    if raw.lower().startswith("hs:"):
        raw = raw[3:]
    raw = raw.strip().split()[0] if raw.strip() else ""
    return raw.lower()


def skill_core(data: dict):
    """PreToolUse(Skill) core: None ⇒ allow; str ⇒ block reason. Blocks a
    Skill(plannotator-annotate) call (DEC-D: annotate only — review + the other 4
    plannotator skills pass through). Gates ONLY a Skill payload (symmetric with
    bash_core's tool-name guard); a non-Skill payload passes. Fails OPEN on any
    runtime error."""
    try:
        if data.get("tool_name") != "Skill":
            return None
        if _skill_slug(data) not in _GATED_SKILLS:
            return None
        return _reason()
    except Exception:  # noqa: BLE001 — F1 fail-open: never wedge the Skill lane
        return None


def main() -> int:
    # Standalone entry wires the Bash core (the in-process dispatcher calls both cores
    # directly). Compliance wrapper: fail-closed on its own errors, fail-open on absent
    # input, honors the enabled gate; blocks with exit 2 + reason when core returns a str.
    hook_runtime.run_compliance_hook(_NAME, bash_core)
    return 0


if __name__ == "__main__":
    sys.exit(main())
