#!/usr/bin/env python3
"""plannotator_surface.py — optional Plannotator review-surface adapter.

Feature-detect the external `plannotator` binary, launch it on a harness
artifact (markdown via `annotate`, a diff via `review`), and normalize the
outcome to a small dict the hs:* review gates branch on. The harness stays
self-contained and Python-pure: plannotator is an OPTIONAL external tool (a
bun-compiled binary), never vendored, never a hard dependency.

Fail-open and env-gated. The gate is CI/disable-marker based, NOT a TTY check:
the agent runs this through a captured pipe (no controlling TTY), so isatty()
would wrongly skip a real interactive session. Automated contexts set CI (or
PLANNOTATOR_DISABLE) and degrade to a plain question instead of opening a
browser. Tracing is best-effort and never breaks the call.

run() statuses:
  approved    — user approved (annotate --json)
  dismissed   — user closed without action (annotate --json)
  annotated   — user left feedback; `feedback` carries it (annotate --json)
  review_text — review-mode plaintext in `feedback` (caller interprets)
  unavailable — binary not found
  skipped     — env-gated out (CI / disabled)
  error       — launch or parse failed; `feedback` may carry detail (fail-open)
"""

import json
import os
import shutil
import subprocess
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
# Shared telemetry lives under harness/hooks/. Best-effort import so the
# surface still runs in a stripped checkout — tracing is optional, never fatal.
_HOOKS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
if _HOOKS not in sys.path:
    sys.path.append(_HOOKS)
try:
    import trace_log
    import hook_runtime
except Exception:  # noqa: BLE001 — telemetry is optional
    trace_log = None
    hook_runtime = None

_HOOK = "plannotator_surface"
_MODES = ("annotate", "review")

_INSTALL_GUIDE = (
    "Plannotator not installed (optional review surface). Quick install:\n"
    "  1) Binary (required for this gate):\n"
    "     curl -fsSL https://plannotator.ai/install.sh | bash\n"
    "  2) Claude Code plugin (optional, for native plan-mode):\n"
    "     /plugin marketplace add backnotprop/plannotator\n"
    "     /plugin install plannotator@plannotator   (then restart)\n"
    "Details: docs/harness/deployment-guide.md (Optional: Plannotator section).\n"
    "Disable the review gate entirely: set environment variable PLANNOTATOR_DISABLE=1."
)


def _trace(event, **kw):
    if trace_log is None:
        return
    try:
        actor = hook_runtime.resolve_actor() if hook_runtime else None
        trace_log.append_event(hook=_HOOK, event=event, actor=actor, **kw)
    except Exception:  # noqa: BLE001 — tracing never breaks the traced op
        pass


def detect():
    """Resolve the plannotator binary, or None. PLANNOTATOR_BINARY overrides
    the PATH lookup (tests, custom installs)."""
    override = os.environ.get("PLANNOTATOR_BINARY")
    if override:
        ok = os.path.isfile(override) and os.access(override, os.X_OK)
        return override if ok else None
    return shutil.which("plannotator")


def env_allows():
    """True only outside automation. CI / explicit disable → False so the gate
    falls back to a plain AskUserQuestion instead of a blocking browser."""
    if os.environ.get("PLANNOTATOR_DISABLE"):
        return False
    if (os.environ.get("CI") or os.environ.get("GITLAB_CI")
            or os.environ.get("GITHUB_ACTIONS")):
        return False
    return True


def _plan_phase_files(plan_md):
    """Sibling phase files of a plan.md, sorted by name. Empty when `plan_md`
    is not a readable plan.md or has no `phase*.md` siblings (the harness
    phase-file naming convention). Never raises."""
    try:
        if (os.path.basename(plan_md) != "plan.md"
                or not os.path.isfile(plan_md)):
            return []
        parent = os.path.dirname(os.path.abspath(plan_md)) or "."
        names = sorted(
            n for n in os.listdir(parent)
            if n != "plan.md" and n.startswith("phase") and n.endswith(".md")
            and os.path.isfile(os.path.join(parent, n)))
        return [os.path.join(parent, n) for n in names]
    except Exception:  # noqa: BLE001 — fail-open, never break the gate
        return []


def run(mode, target):
    """Launch plannotator <mode> <target> and normalize the outcome. Never
    raises — returns a dict with a `status` key (see module docstring)."""
    if mode not in _MODES:
        return {"status": "error", "feedback": "unknown mode %r" % mode}
    binary = detect()
    if not binary:
        _trace("unavailable", target=target, status="unavailable")
        return {"status": "unavailable"}
    if not env_allows():
        _trace("skipped", target=target, status="skipped")
        return {"status": "skipped"}

    # annotate is an approval surface: --gate adds the Approve button (without
    # it plannotator offers no approved path, only Send-Annotations / Close). A
    # multi-phase plan is annotated as its directory so the folder browser
    # surfaces plan.md and every phase file in the annotation UI.
    if mode == "annotate":
        phases = _plan_phase_files(target)
        annotate_target = (os.path.dirname(os.path.abspath(target))
                           if phases else target)
        cmd = [binary, "annotate", annotate_target, "--gate", "--json"]
    else:
        cmd = [binary, "review", target]

    _trace("launch", target=target, tool=mode)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except Exception as e:  # noqa: BLE001 — launch failure is fail-open
        _trace("error", target=target, status="error", note=str(e))
        return {"status": "error", "feedback": str(e)}

    out = (proc.stdout or "").strip()

    if mode == "review":
        # No --json for review: hand the plaintext back for the caller to read
        # (approved-prompt vs feedback), as the stock plannotator-review does.
        _trace("result", target=target, status="review_text")
        return {"status": "review_text", "feedback": out}

    # annotate --json
    if proc.returncode != 0 and not out:
        _trace("error", target=target, status="error", exit_code=proc.returncode)
        return {"status": "error", "feedback": (proc.stderr or "").strip()}
    try:
        rec = json.loads(out) if out else {"decision": "dismissed"}
    except ValueError:
        _trace("error", target=target, status="error", note="bad json")
        return {"status": "error", "feedback": out}
    decision = rec.get("decision")
    if decision in ("approved", "dismissed", "annotated"):
        result = {"status": decision}
        if rec.get("feedback"):
            result["feedback"] = rec["feedback"]
        _trace("result", target=target, status=decision)
        return result
    _trace("error", target=target, status="error", note="unknown decision")
    return {"status": "error", "feedback": out}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) < 2:
        sys.stderr.write(
            "usage: plannotator_surface.py <annotate|review> <target>\n")
        return 2
    result = run(argv[0], argv[1])
    if result.get("status") == "unavailable":
        sys.stderr.write(_INSTALL_GUIDE + "\n")
    sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
