#!/usr/bin/env python3
"""run_vertical_slice.py — end-to-end acceptance: generate-then-advise in a temp dir.

Proves the personal-first vertical slice end to end the way Claude Code would drive
it: hooks are invoked as SUBPROCESSES with real stdin JSON (simulated transport — no
import cheating), against a COPY of fixture-mini in a temp dir with HARNESS_ROOT
pointing there, so nothing touches the real repo's plans/ or manifest.

Scenario (personal-first: local ADVISES, remote CI enforces):
  1. session_init runs → session file + trace with actor.
  2. `git push` with a plan but NO artifacts → gate_stage ADVISORY (exit 0 + trace).
  3. Write verification.json → gate PASSES silently (exit 0).
  3b. Verdict policy: a FAILed check / BLOCKED or off-enum verdict / empty checks each ADVISORY.
  3c. Multi-artifact stage (pr) ADVISORY until every required artifact is present.
  4. Disable the gate via config → gate SKIPS with a traced reason.
  5. git-pre-push-hook.sh smoke: WARNS without artifacts, passes with; the forgery
     arm STILL BLOCKS a shell-write to a receipt path (the agent cage holds).
  6. Every gate decision in the trace carries an actor.

Appends a run summary to harness/e2e/RUN-LOG.md (gitignored).

Usage: python3 harness/e2e/run_vertical_slice.py
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

_PASSED = []
_FAILED = []


def _check(name: str, ok: bool, detail: str = "") -> None:
    (_PASSED if ok else _FAILED).append((name, detail))
    print("  %s %s%s" % ("✓" if ok else "✗", name,
                         (" — " + detail) if (detail and not ok) else ""))


def _env(root: Path) -> dict:
    env = dict(os.environ)
    env.pop("PYTEST_CURRENT_TEST", None)
    for ci in ("CI", "GITLAB_CI", "GITHUB_ACTIONS"):
        env.pop(ci, None)
    # Hermetic: drop EVERY inherited HARNESS_* so a configured dev shell
    # (.harness-dev/*.yaml pointers, a redirected guard/stage policy, nudge channels,
    # standards config, …) reads identical to a clean CI run — this slice asserts the
    # SHIPPED gate behavior, never the dev's local posture. Allowlist-scrub (like
    # conftest's _scrub_dev_posture_env) is staleness-proof: a new HARNESS_* knob is
    # scrubbed automatically. The plumbing the slice needs is set explicitly after the
    # wipe. gate_stage flagging any _POSTURE_ENV as a redirected-policy advisory, a
    # relaxed dogfood write-guard config, a scratch hook config — all leak in otherwise.
    for k in [k for k in env if k.startswith("HARNESS_")]:
        env.pop(k, None)
    env["HARNESS_ROOT"] = str(root)
    env["HARNESS_STATE_DIR"] = str(root / "harness" / "state")
    env["HARNESS_HOOK_LOG_DIR"] = str(root / "harness" / "state" / "logs")
    env["HARNESS_USER"] = "e2e-runner"
    return env


def _hook(root: Path, script: Path, payload: dict, extra_env=None):
    env = _env(root)
    for k, v in (extra_env or {}).items():
        env[k] = v
    return subprocess.run([sys.executable, str(script)],
                          input=json.dumps(payload), capture_output=True,
                          text=True, env=env)


def _trace_events(root: Path):
    out = []
    trace = root / "harness" / "state" / "trace"
    if trace.is_dir():
        for f in sorted(trace.glob("trace-*.jsonl")):
            for line in f.read_text(encoding="utf-8").splitlines():
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return out


def seed_git_repo(root: Path, email: str, name: str) -> None:
    """Init a fixture repo and make the seed commit WITHOUT writing identity
    into .git/config. Identity is passed per-command via `git -c user.x=...`,
    so the commit is attributed but the local config is never touched. The
    AFK sandbox bind-mounts the host repo's .git read-write — a `git config
    user.*` here would silently rewrite the human's committer identity on their
    own machine. Per-command config is the hermetic alternative."""
    subprocess.run(["git", "init", "-q"], cwd=str(root), check=True,
                   capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=str(root), check=True,
                   capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=%s" % email, "-c", "user.name=%s" % name,
         "commit", "-qm", "seed fixture"],
        cwd=str(root), check=True, capture_output=True)


def _global_layout_arm() -> None:
    """The two-zone guard under a SIMULATED global layout (bin≠project) — the one
    place the two-zone branch actually fires (self-host collapses it). The shared
    binary is the real repo; the project is a fresh temp dir. A foreign tool-Write
    into ${bin}/** BLOCKS (bin-lane + whole-bin catch-all); a legit project
    .harness/ write PASSES. Driven as a subprocess with stdin JSON (real transport)."""
    wg = _HARNESS / "hooks" / "write_guard.py"
    tmp = Path(tempfile.mkdtemp(prefix="harness-e2e-global-"))
    try:
        proj = tmp / "proj"
        (proj / ".harness" / "state" / "telemetry").mkdir(parents=True)

        def _wg(target: str):
            env = dict(os.environ)
            # Scrub inherited roots AND any dev guard-config overrides
            # (.harness-dev/*.yaml) so this arm is hermetic — otherwise a
            # relaxed dogfood write-guard config leaks in and the block never fires.
            for k in ("HARNESS_ROOT", "HARNESS_DATA_ROOT", "HARNESS_HOOK_LOG_DIR",
                      "PYTEST_CURRENT_TEST", "HARNESS_GUARD_POLICY",
                      "HARNESS_WRITE_GUARD_CONFIG"):
                env.pop(k, None)
            env["HARNESS_BIN_ROOT"] = str(_HARNESS.parent)  # the real repo == bin
            env["CLAUDE_PROJECT_DIR"] = str(proj)
            env["HARNESS_STATE_DIR"] = str(proj / ".harness" / "state")
            payload = {"session_id": "e2e-global", "tool_name": "Write",
                       "tool_input": {"file_path": target, "content": "x"}}
            return subprocess.run([sys.executable, str(wg)], input=json.dumps(payload),
                                  capture_output=True, text=True, env=env)

        bin_hook = str(_HARNESS / "hooks" / "write_guard.py")
        _check("[global] tool-Write into ${bin} hook BLOCKS (exit 2)",
               _wg(bin_hook).returncode == 2)
        bin_nonguard = str(_HARNESS.parent / ".claude" / "settings.json")
        _check("[global] whole-bin catch-all BLOCKS a non-guarded bin path (exit 2)",
               _wg(bin_nonguard).returncode == 2)
        proj_write = str(proj / ".harness" / "state" / "telemetry" / "e.jsonl")
        _check("[global] legit project .harness/ write PASSES (exit 0)",
               _wg(proj_write).returncode == 0)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="harness-e2e-"))
    print("e2e vertical slice in %s (simulated transport: stdin JSON "
          "subprocess, not native Claude Code)" % tmp)
    try:
        root = tmp / "proj"
        shutil.copytree(_FIXTURE, root)
        # The slice under test is the REAL harness code, copied so the run
        # cannot write into the repo tree.
        shutil.copytree(_HARNESS / "hooks", root / "harness" / "hooks")
        shutil.copytree(_HARNESS / "scripts", root / "harness" / "scripts")
        shutil.copytree(_HARNESS / "data", root / "harness" / "data")
        shutil.copytree(_HARNESS / "install", root / "harness" / "install")
        # The fixture must be a real git repo: the pre-push hook resolves its
        # root via `git rev-parse --show-toplevel` after scrubbing HARNESS_*
        # (transport posture), so a bare copytree dir cannot host it. Identity
        # is set per-command (no .git/config write) — see seed_git_repo.
        seed_git_repo(root, "e2e@local", "e2e")

        gate = root / "harness" / "hooks" / "gate_stage.py"
        session_init = root / "harness" / "hooks" / "session_init.py"
        push_payload = {"session_id": "e2e-s1", "tool_name": "Bash",
                        "tool_input": {"command": "git push"}}

        # 1. session attribution
        proc = _hook(root, session_init, {"session_id": "e2e-s1"})
        _check("session_init continues", proc.returncode == 0, proc.stderr)
        sess = root / "harness" / "state" / "sessions" / "e2e-s1.json"
        _check("session file written with actor",
               sess.is_file() and "e2e-runner" in sess.read_text(encoding="utf-8"))

        # 2. plan exists but artifacts missing → ADVISORY (exit 0; enforced at remote CI)
        plan = root / "plans" / "260612-0900-fixture-feature"
        plan.mkdir(parents=True)
        (plan / "plan.md").write_text(
            "---\ntitle: fixture feature\nstatus: in_progress\n---\n",
            encoding="utf-8")
        proc = _hook(root, gate, push_payload)
        _check("push without artifact ADVISORY exit 0", proc.returncode == 0,
               "rc=%s stderr=%s" % (proc.returncode, proc.stderr[:200]))
        _check("advisory names the missing artifact",
               "[advisory]" in proc.stderr and "verification" in proc.stderr, proc.stderr[:200])

        # 3. add artifacts → PASS
        art = plan / "artifacts"
        art.mkdir()
        (art / "verification.json").write_text(json.dumps({
            "stage": "push", "plan": plan.name, "actor": "user:e2e-runner",
            "ts": datetime.now(timezone.utc).isoformat(),
            "checks": [{"name": "pytest", "status": "PASS"}],
            "verdict": "PASS",
        }), encoding="utf-8")
        proc = _hook(root, gate, push_payload)
        _check("push with artifact PASSES exit 0", proc.returncode == 0,
               proc.stderr[:200])

        # 3b. verdict policy: a present artifact that did not actually pass must still
        # ADVISORY (exit 0) — a FAILed check, a BLOCKED or off-enum (crashed-verifier) verdict, or
        # an empty checks array. Proves the gate reads the artifact's content, not just
        # its presence (the verdict allowlist + per-check gate), end to end.
        good_artifact = (art / "verification.json").read_text(encoding="utf-8")

        def _write_verif(checks, verdict):
            (art / "verification.json").write_text(json.dumps({
                "stage": "push", "plan": plan.name, "actor": "user:e2e-runner",
                "ts": datetime.now(timezone.utc).isoformat(),
                "checks": checks, "verdict": verdict,
            }), encoding="utf-8")

        for label, checks, verdict in (
            ("a FAILed check", [{"name": "pytest", "status": "FAIL"}], "PASS"),
            ("a BLOCKED verdict", [{"name": "pytest", "status": "PASS"}], "BLOCKED"),
            ("an off-enum verdict", [{"name": "pytest", "status": "SKIP"}], "ERROR"),
            ("an empty checks array", [], "PASS"),
        ):
            _write_verif(checks, verdict)
            proc = _hook(root, gate, push_payload)
            _check("push ADVISORY on %s (exit 0)" % label,
                   proc.returncode == 0 and "[advisory]" in proc.stderr,
                   "rc=%s stderr=%s" % (proc.returncode, proc.stderr[:160]))
        (art / "verification.json").write_text(good_artifact, encoding="utf-8")
        proc = _hook(root, gate, push_payload)
        _check("push PASSES again after restoring a valid artifact",
               proc.returncode == 0, proc.stderr[:160])

        # 3b-dod. DoD-by-change-class: a bugfix REQUIRES a regression result. With
        # only a unit result → the gate ADVISES (exit 0); add the regression result and it PASSES
        # — the gate re-reads the raw result files, end to end.
        results = art / "results"
        results.mkdir(exist_ok=True)
        _pass_junit = ('<testsuite name="u" tests="2" failures="0" errors="0" '
                       'skipped="0"/>')
        (results / "unit.xml").write_text(_pass_junit, encoding="utf-8")

        def _write_dod(checks):
            (art / "verification.json").write_text(json.dumps({
                "stage": "push", "plan": plan.name, "actor": "user:e2e-runner",
                "ts": datetime.now(timezone.utc).isoformat(),
                "checks": checks, "verdict": "PASS",
            }), encoding="utf-8")

        _write_dod([{"name": "unit", "status": "PASS", "format": "junit",
                     "file": "results/unit.xml"}])
        proc = _hook(root, gate, push_payload,
                     {"HARNESS_CHANGE_CLASS": "bugfix"})
        _check("bugfix missing regression ADVISORY (DoD)",
               proc.returncode == 0 and "[advisory]" in proc.stderr and "regression" in proc.stderr,
               "rc=%s stderr=%s" % (proc.returncode, proc.stderr[:160]))
        (results / "reg.xml").write_text(_pass_junit, encoding="utf-8")
        _write_dod([
            {"name": "unit", "status": "PASS", "format": "junit",
             "file": "results/unit.xml"},
            {"name": "regression", "status": "PASS", "format": "junit",
             "file": "results/reg.xml"}])
        proc = _hook(root, gate, push_payload,
                     {"HARNESS_CHANGE_CLASS": "bugfix"})
        _check("bugfix with regression PASSES (DoD)", proc.returncode == 0,
               proc.stderr[:160])
        (art / "verification.json").write_text(good_artifact, encoding="utf-8")
        shutil.rmtree(results, ignore_errors=True)

        # 3c. a MULTI-artifact stage (pr) ADVISES (exit 0) until EVERY required artifact is
        # present, not just the first — proves the gate enforces the full required[] set.
        pr_payload = {"session_id": "e2e-s1", "tool_name": "Bash",
                      "tool_input": {"command": "gh pr create"}}
        proc = _hook(root, gate, pr_payload)
        _check("pr ADVISORY with only verification (names missing review-decision)",
               proc.returncode == 0 and "[advisory]" in proc.stderr and "review-decision" in proc.stderr,
               "rc=%s stderr=%s" % (proc.returncode, proc.stderr[:160]))
        (art / "review-decision.json").write_text(json.dumps({
            "verdict": "PASS", "reviewer": "user:e2e", "role": "reviewer",
            "rationale": "looks good",
        }), encoding="utf-8")
        proc = _hook(root, gate, pr_payload)
        _check("pr ADVISORY with verification+review but no plan-approval",
               proc.returncode == 0 and "[advisory]" in proc.stderr and "plan-approval" in proc.stderr,
               "rc=%s stderr=%s" % (proc.returncode, proc.stderr[:160]))
        (art / "review-decision.json").unlink()  # leave the fixture as step 3 had it

        # 3d. full multi-artifact PASS, then a plan-body edit re-opens approval (drift).
        sys.path.insert(0, str(_HARNESS / "scripts"))
        import plan_approval as _pa
        plan_md = (plan / "plan.md").read_text(encoding="utf-8")
        (art / "review-decision.json").write_text(json.dumps({
            "verdict": "PASS", "reviewer": "user:e2e", "role": "reviewer",
            "rationale": "ok"}), encoding="utf-8")
        (art / "plan-approval.json").write_text(json.dumps({
            "schema": "plan-approval/v1", "plan": plan.name,
            "plan_hash": _pa.plan_hash(plan), "file_hashes": _pa.file_hashes(plan),
            "author": "user:hieu.bt2409@gmail.com",
            "reviewer": "user:hieu.bt2409@gmail.com",
            "verdict": "APPROVED", "rationale": "reviewed",
            "ts": datetime.now(timezone.utc).isoformat()}), encoding="utf-8")
        proc = _hook(root, gate, pr_payload)
        _check("pr PASSES with verification + review + a valid plan-approval",
               proc.returncode == 0, proc.stderr[:200])
        (plan / "plan.md").write_text(
            plan_md + "\nA new body line that changes the plan hash.\n", encoding="utf-8")
        proc = _hook(root, gate, pr_payload)
        _check("pr ADVISORY after the plan body changed (approval drift re-opens)",
               proc.returncode == 0 and "[advisory]" in proc.stderr and "changed" in proc.stderr,
               proc.stderr[:200])
        (plan / "plan.md").write_text(plan_md, encoding="utf-8")           # restore
        (art / "review-decision.json").unlink()
        (art / "plan-approval.json").unlink()

        # 4. disabled gate → skip with traced reason
        cfg = root / "disabled-hooks.yaml"
        cfg.write_text("hooks:\n  gate_stage:\n    enabled: false\n",
                       encoding="utf-8")
        proc = _hook(root, gate, push_payload,
                     extra_env={"HARNESS_HOOK_CONFIG": str(cfg)})
        _check("disabled gate skips exit 0", proc.returncode == 0)

        # 5. pre-push transport hook smoke (artifact present → pass)
        #
        # `input=""` is load-bearing, not tidiness. The hook opens with
        # `PUSH_REFS="$(cat)"` — correct against real git, which always writes the
        # ref lines and closes. Without an explicit stdin the child INHERITS this
        # runner's, so under any caller whose stdin is an open pipe that never
        # closes (a CI shell, a background job) the `cat` blocks forever and the
        # whole run hangs with no output and no timeout. Measured: 30 minutes in
        # `ci.sh e2e` before it was killed by hand; with stdin closed the same
        # slice finishes in seconds.
        prepush = root / "harness" / "install" / "git-pre-push-hook.sh"
        proc = subprocess.run(["sh", str(prepush)], capture_output=True,
                              text=True, env=_env(root), cwd=str(root), input="")
        _check("pre-push hook passes with artifact", proc.returncode == 0,
               proc.stderr[:200])
        (art / "verification.json").unlink()
        proc = subprocess.run(["sh", str(prepush)], capture_output=True,
                              text=True, env=_env(root), cwd=str(root), input="")
        # The block must be the ARTIFACT gate firing, not an incidental exit-2 (a
        # gate crash, missing python, import failure all exit 2). Mirror step 2's
        # content guard so a path-conditional crash can't pass this vacuously.
        _check("pre-push hook WARNS without artifact (exit 0)",
               proc.returncode == 0 and "[pre-push warn]" in proc.stderr
               and "verification" in proc.stderr,
               "rc=%s stderr=%s" % (proc.returncode, proc.stderr[:200]))

        # 5c. forgery arm SURVIVES personal-first: a shell write to a receipt path
        # is still a HARD block (exit 2) — local unblock loosens the human gate, not
        # the agent cage.
        forge_payload = {"session_id": "e2e-s1", "tool_name": "Bash",
                         "tool_input": {"command":
                             "echo x > plans/%s/artifacts/verification.json" % plan.name}}
        proc = _hook(root, gate, forge_payload)
        _check("forgery write to a receipt path STILL BLOCKS (exit 2)",
               proc.returncode == 2,
               "rc=%s stderr=%s" % (proc.returncode, proc.stderr[:160]))

        # 6. audit trail: decisions carry actor
        events = _trace_events(root)
        gate_events = [e for e in events if e["event"].startswith("gate_")]
        _check("trace has gate events", bool(gate_events))
        _check("every gate event carries an actor",
               all(e.get("actor") for e in gate_events))
        _check("both advisory and pass were traced",
               {"gate_advisory", "gate_pass"} <=
               {e["event"] for e in gate_events})
        _check("skip was traced with reason",
               any(e["event"] == "gate_skip" and e.get("note")
                   for e in events))

        # Global-layout arm: the two-zone guard under a real bin≠project layout
        # (the dogfood arm above is bin==project and collapses the branch).
        _global_layout_arm()

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    ok = not _FAILED
    summary = "%s | %d passed, %d failed | transport=simulated-stdin" % (
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
