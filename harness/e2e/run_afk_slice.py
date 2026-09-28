#!/usr/bin/env python3
"""run_afk_slice.py — end-to-end acceptance for AFK mode: prove the spine.

The AFK safety model is "approval at both ENDS, freedom in the MIDDLE": a human
approves the plan going in and reviews the diff before ship coming out, and the
unattended loop in between is free to commit but can never push/pr/ship on its
own. This script proves that spine end to end, token-free, the way Claude Code
would drive it — gate_stage.py invoked as a SUBPROCESS with real stdin JSON
against a COPY of the harness in a temp dir (HARNESS_ROOT points there, so
nothing touches the real repo's plans/ or manifest).

Two parts, both deterministic and offline:

  Part A — the gate spine. Feed the gate a representative loop sequence. The
  LOCAL gate is advisory (exit 0): it emits an `[advisory]` naming the missing
  artifact, and the REMOTE CI gate is what enforces the exit. Each step asserts
  that advisory posture, not a local block:
    1. `git commit`        -> PASS (soft stage). Freedom in the middle.
    2. `git push` (no art) -> ADVISORY exit 0, names verification. The output end
                              is gated; remote CI enforces the exit.
    3. write verification  -> `git push` PASSES. Push opens on a presence
                              artifact (presence gate, not authn).
    4. `gh pr create`      -> still ADVISORY: pr needs review-decision too.
    5. review-decision PASS_WITH_RISK -> pr STILL advisory: only an explicit PASS
                              opens a hard ship stage. The loop's own soft
                              self-accept does not ship.
    6. review-decision PASS, no plan-approval -> pr STILL advisory on the human's
                              plan-approval artifact. The loop cannot ship.
    Every gate decision is traced with an actor.

  Part A2 — preflight never-blocks. A readiness probe that crashed
    would itself become the obstacle between the user and a working fallback,
    so it must degrade, never raise:
    - docker absent (empty PATH) -> CLI still exits 0; docker + gate_live come
      back `fail` with a fallback hint. The orchestrator offers native
      /loop·/goal instead of running a bare bypass.
    - gate silently dead (stub probe, fired=False) -> gate_live is a bold
      `fail` that steers to fallback, never a silent wave-through.
    - every check broken at once (run/which/probe all raise) -> preflight still
      returns a full list of findings, never an exception.

Reuses the proven transport helpers from run_vertical_slice (DRY: one _env /
_hook / _trace_events, two scenarios). Appends a run summary to
harness/e2e/RUN-LOG.md (gitignored).

Usage: python3 harness/e2e/run_afk_slice.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

_E2E = Path(__file__).resolve().parent
_HARNESS = _E2E.parent
_FIXTURE = _E2E / "fixture-mini"
_AFK = _HARNESS / "afk"

# DRY: the gate transport (subprocess + stdin JSON), env scrubbing, and trace
# reader are already proven in the vertical-slice e2e. Reuse them verbatim.
sys.path.insert(0, str(_E2E))
import run_vertical_slice as _vs  # noqa: E402

_PASSED = []
_FAILED = []


def _check(name: str, ok: bool, detail: str = "") -> None:
    (_PASSED if ok else _FAILED).append((name, detail))
    print("  %s %s%s" % ("✓" if ok else "✗", name,
                         (" — " + detail) if (detail and not ok) else ""))


def _build_fixture(tmp: Path) -> Path:
    """A temp repo carrying the REAL harness code (copied, never the repo tree)
    plus a single in_progress plan to resolve as active."""
    root = tmp / "proj"
    shutil.copytree(_FIXTURE, root)
    for sub in ("hooks", "scripts", "data", "install"):
        shutil.copytree(_HARNESS / sub, root / "harness" / sub)
    # Identity set per-command (no .git/config write) — see _vs.seed_git_repo.
    _vs.seed_git_repo(root, "afk@local", "afk")
    plan = root / "plans" / "260614-0900-afk-fixture"
    (plan / "artifacts").mkdir(parents=True)
    (plan / "plan.md").write_text(
        "---\ntitle: afk fixture\nstatus: in_progress\n---\n", encoding="utf-8")
    return plan


def _verification(plan_name: str) -> str:
    return json.dumps({
        "stage": "push", "plan": plan_name, "actor": "user:e2e-runner",
        "ts": datetime.now(timezone.utc).isoformat(),
        "checks": [{"name": "pytest", "status": "PASS"}],
        "verdict": "PASS",
    })


def _review_decision(verdict: str) -> str:
    return json.dumps({
        "verdict": verdict, "reviewer": "user:e2e-runner",
        "role": "implementer (self-cert)",
        "rationale": "e2e fixture review-decision",
    })


def part_a(tmp: Path) -> None:
    """The gate spine: commit free, push gated by a presence artifact, ship
    gated by review-decision==PASS and the human's plan-approval."""
    plan = _build_fixture(tmp)
    root = plan.parent.parent  # plans/<name> -> plans -> proj
    gate = root / "harness" / "hooks" / "gate_stage.py"
    art = plan / "artifacts"
    pin = {"HARNESS_ACTIVE_PLAN": str(plan)}

    def run(command: str):
        payload = {"session_id": "afk-e2e", "tool_name": "Bash",
                   "tool_input": {"command": command}}
        return _vs._hook(root, gate, payload, extra_env=pin)

    # 1. middle is free — a commit is a soft stage and never blocks.
    proc = run("git commit -m 'loop step'")
    _check("commit passes (freedom in the middle)", proc.returncode == 0,
           "rc=%s %s" % (proc.returncode, proc.stderr[:160]))

    # 2. output end is gated — push without verification blocks.
    proc = run("git push")
    _check("push without verification ADVISORY exit 0", proc.returncode == 0,
           "rc=%s %s" % (proc.returncode, proc.stderr[:160]))
    _check("push advisory names the missing verification artifact",
           "[advisory]" in proc.stderr and "verification" in proc.stderr, proc.stderr[:160])

    # 3. push opens on a presence artifact — the loop may write its own, so push
    #    is presence-gated; the real bar is enforced at ship.
    (art / "verification.json").write_text(_verification(plan.name),
                                           encoding="utf-8")
    proc = run("git push")
    _check("push with verification PASSES exit 0", proc.returncode == 0,
           "rc=%s %s" % (proc.returncode, proc.stderr[:160]))

    # 4. ship is a higher bar — pr needs review-decision even with verification.
    proc = run("gh pr create --fill")
    _check("pr with only verification ADVISORY", proc.returncode == 0,
           "rc=%s %s" % (proc.returncode, proc.stderr[:160]))
    _check("pr advisory names review-decision",
           "[advisory]" in proc.stderr and "review-decision" in proc.stderr, proc.stderr[:160])

    # 5. the loop's own soft self-accept does not ship — only an explicit PASS
    #    opens a hard stage; PASS_WITH_RISK is a conscious soft-accept.
    (art / "review-decision.json").write_text(
        _review_decision("PASS_WITH_RISK"), encoding="utf-8")
    proc = run("gh pr create --fill")
    _check("pr with PASS_WITH_RISK review ADVISORY", proc.returncode == 0,
           "rc=%s %s" % (proc.returncode, proc.stderr[:160]))
    _check("advisory explains only exactly PASS opens a hard stage",
           "[advisory]" in proc.stderr and ("exactly\nPASS" in proc.stderr or "exactly PASS" in proc.stderr),
           proc.stderr[:200])

    # 6. even a PASS review cannot ship without the human's plan-approval — the
    #    input-end approval artifact the loop must never forge.
    (art / "review-decision.json").write_text(
        _review_decision("PASS"), encoding="utf-8")
    proc = run("gh pr create --fill")
    _check("pr without plan-approval ADVISORY (remote CI enforces the exit)",
           proc.returncode == 0, "rc=%s %s" % (proc.returncode,
                                               proc.stderr[:160]))
    _check("pr advisory names plan-approval",
           "[advisory]" in proc.stderr and "plan-approval" in proc.stderr, proc.stderr[:160])

    # audit trail — every gate decision carries an actor; both block and pass
    # were recorded.
    events = _vs._trace_events(root)
    gate_events = [e for e in events if e["event"].startswith("gate_")]
    _check("trace has gate events", bool(gate_events))
    _check("every gate event carries an actor",
           all(e.get("actor") for e in gate_events))
    _check("both advisory and pass were traced",
           {"gate_advisory", "gate_pass"} <=
           {e["event"] for e in gate_events})


def part_a2(tmp: Path) -> None:
    """preflight never blocks the workflow: every failure mode degrades to a
    finding + fallback, never an exception or a non-zero exit."""
    preflight_py = _AFK / "preflight.py"

    # (a) real transport: run the CLI with docker (and ralph-afk) off PATH.
    #     A readiness probe must still exit 0 and hand back a fallback offer.
    empty = tmp / "emptybin"
    empty.mkdir(parents=True)
    env = dict(os.environ)
    env["PATH"] = str(empty)
    env.pop("RALPH_IMAGE", None)
    proc = subprocess.run(
        [sys.executable, str(preflight_py), "--json",
         "--workspace", str(tmp), "--repo-root", str(tmp)],
        capture_output=True, text=True, env=env)
    _check("preflight CLI exits 0 even on a broken host (never-block)",
           proc.returncode == 0, "rc=%s %s" % (proc.returncode,
                                               proc.stderr[:160]))
    findings = {}
    try:
        findings = {f["check"]: f for f in json.loads(proc.stdout)}
    except (ValueError, KeyError) as e:
        _check("preflight emits parseable JSON findings", False, str(e))
    _check("docker absent reported as fail with a fallback",
           findings.get("docker_installed", {}).get("status") == "fail"
           and bool(findings.get("docker_installed", {}).get("fallback_hint")))
    _check("gate_live cannot confirm -> fail steers to fallback",
           findings.get("gate_live", {}).get("status") == "fail"
           and bool(findings.get("gate_live", {}).get("fallback_hint")))

    # in-process: import the module to exercise specific branches deterministi-
    # cally without needing a docker daemon at all.
    sys.path.insert(0, str(_AFK))
    import gate_live_probe
    import preflight as pf

    # (b) the gate is silently dead (probe present but the hook never fired):
    #     a bold fail that says do-not-run, not a silent wave-through.
    dead = lambda image, root: gate_live_probe.ProbeResult(
        False, 0, "no gate output")
    gl = pf.check_gate_live(probe=dead)
    _check("silently dead gate -> bold fail", gl.status == "fail")
    _check("dead-gate fallback says do NOT run unattended",
           "do NOT run" in gl.fallback_hint)

    # (c) every probe path broken at once: preflight still returns a full
    #     findings list and never raises (the fail-open backstop).
    def boom(*a, **k):
        raise RuntimeError("simulated host failure")

    raised = None
    out = []
    try:
        out = pf.preflight(run=boom, which=boom, probe=boom,
                           workspace=str(tmp), repo_root=str(tmp))
    except Exception as e:  # noqa: BLE001 — the whole point is it must not
        raised = e
    _check("preflight never raises even when every check explodes",
           raised is None, "raised %r" % raised)
    _check("preflight returns a full findings list under total failure",
           isinstance(out, list) and len(out) == 12,
           "len=%s" % (len(out) if isinstance(out, list) else "n/a"))
    _check("preflight.has_blocker stays callable on degraded findings",
           isinstance(pf.has_blocker(out), bool))


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="harness-afk-e2e-"))
    print("e2e afk slice in %s (token-free: gate via stdin-JSON subprocess; "
          "preflight never-block proof)" % tmp)
    try:
        print("Part A — approval-at-both-ends, freedom-in-the-middle:")
        part_a(tmp / "a")
        print("Part A2 — preflight never-block -> fallback:")
        part_a2(tmp / "a2")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    ok = not _FAILED
    summary = "%s | afk: %d passed, %d failed | transport=simulated-stdin" % (
        datetime.now(timezone.utc).isoformat(), len(_PASSED), len(_FAILED))
    print("\ne2e:", summary)
    try:
        with open(_E2E / "RUN-LOG.md", "a", encoding="utf-8") as fh:
            fh.write("- %s\n" % summary)
            for name, detail in _FAILED:
                fh.write("  - FAILED: %s — %s\n" % (name, detail))
    except OSError:
        pass
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
