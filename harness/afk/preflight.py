#!/usr/bin/env python3
"""preflight.py — readiness probe for AFK (Ralph) mode. FAIL-OPEN by design.

Before an unattended Ralph loop runs, something has to answer: is this host
actually ready? Is docker up, is the sandbox image present, is the in-loop gate
genuinely live inside it? This module answers that — and returns the answer as
structured findings the orchestrator reads. It is an *advisory*, not a gate.

Two properties it must never violate:

  - It never raises and never exit-blocks. A readiness probe that crashed would
    itself become the obstacle between the user and a working fallback. Every
    check is wrapped so a thrown exception degrades to a finding, not a stack
    trace; the CLI always exits 0.
  - It never silently waves through a dead guardrail. The `gate_live` check runs
    the deterministic gate-live probe inside the image; if the stage gate does not fire
    there, that is a bold `fail` that steers the caller to the native fallback
    rather than letting a bare bypass run unsupervised.

Findings are `Finding(check, status, detail, fix, fallback_hint)` with status in
{ok, warn, fail}. `fail` means RED (the orchestrator offers fallback); `warn` is
surfaced but does not block; `ok` is green. `has_blocker()` is the RED test.
"""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from collections import namedtuple
from pathlib import Path

# Reuse the gate-live probe (same directory). One probe, two callers: the
# sandbox image test and this preflight check both ask "is the gate live here?".
sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate_live_probe  # noqa: E402

Finding = namedtuple("Finding", ("check", "status", "detail", "fix",
                                 "fallback_hint"))

# The harness sandbox image (built from harness/afk/Dockerfile), not the
# upstream base. The launcher exports the same name.
DEFAULT_IMAGE = os.environ.get("RALPH_IMAGE", "ralph-sandbox-harness")
DOCKERFILE = Path(__file__).resolve().parent / "Dockerfile"

# Known-good versions: a hint for "suspect #1 if it breaks", NOT a pin.
# Floating tags stay floating; this only drives a warn on drift.
TESTED_WITH = {"ralph_cli": ""}  # empty = drift check is a no-op until recorded

_FALLBACK = ("fall back to native `/loop` or `/goal` on the host "
             "(degraded: no docker isolation, simplified loop)")


# --------------------------------------------------------------------------- #
# individual checks — each returns one Finding, each independently testable
# --------------------------------------------------------------------------- #

def check_docker_installed(which=shutil.which, docker_bin="docker"):
    if which(docker_bin):
        return Finding("docker_installed", "ok", "%s on PATH" % docker_bin,
                       "", "")
    return Finding(
        "docker_installed", "fail", "%s not found on PATH" % docker_bin,
        "install Docker Engine (https://docs.docker.com/engine/install/)",
        _FALLBACK)


def check_docker_daemon(run=subprocess.run, docker_bin="docker", info=None):
    # `info` is the (rc, err) from a shared `docker info` probe. preflight()
    # computes it ONCE and passes it to both docker checks so the 20s call runs
    # a single time; a direct caller may omit it and the probe runs on demand.
    rc, err = info if info is not None else _docker_info(run, docker_bin)
    if rc == 0:
        return Finding("docker_daemon", "ok", "daemon responds", "", "")
    if "permission denied" in err.lower():
        # the daemon is up; this host just can't reach it — handled by perm.
        return Finding("docker_daemon", "ok",
                       "daemon up (see docker_perm)", "", "")
    return Finding(
        "docker_daemon", "fail", "`docker info` failed: %s" % (err or rc),
        "start the Docker daemon (e.g. `sudo systemctl start docker`)",
        _FALLBACK)


def check_docker_perm(run=subprocess.run, docker_bin="docker", info=None):
    # Reuses the same shared `docker info` probe as check_docker_daemon (see the
    # `info` note there) so `docker info` is not run a second time.
    rc, err = info if info is not None else _docker_info(run, docker_bin)
    if "permission denied" in err.lower():
        return Finding(
            "docker_perm", "fail",
            "current user cannot reach the docker socket",
            "add your user to the `docker` group "
            "(`sudo usermod -aG docker $USER`) then re-login",
            _FALLBACK)
    return Finding("docker_perm", "ok", "socket reachable", "", "")


def check_image_present(run=subprocess.run, docker_bin="docker",
                        image=DEFAULT_IMAGE, dockerfile=DOCKERFILE):
    if _run_ok(run, [docker_bin, "image", "inspect", image]):
        return Finding("image_present", "ok", "%s present" % image, "", "")
    build = ("docker build -f %s -t %s %s"
             % (dockerfile, image, Path(dockerfile).parent))
    if Path(dockerfile).exists():
        return Finding(
            "image_present", "warn",
            "%s absent but the Dockerfile is here — buildable" % image,
            build, "")
    return Finding(
        "image_present", "fail",
        "%s absent and no Dockerfile at %s" % (image, dockerfile),
        "restore harness/afk/Dockerfile, then: %s" % build, _FALLBACK)


def check_arch_amd64(machine=None):
    arch = (machine or platform.machine()).lower()
    if arch in ("x86_64", "amd64"):
        return Finding("arch_amd64", "ok", "host is %s" % arch, "", "")
    return Finding(
        "arch_amd64", "warn",
        "host is %s; the Ralph base image is linux/amd64-only" % arch,
        "it will run under emulation (slower); or use an amd64 host", "")


def check_ralph_cli(which=shutil.which):
    if which("ralph-afk"):
        return Finding("ralph_cli", "ok", "ralph-afk on PATH", "", "")
    return Finding(
        "ralph_cli", "fail", "ralph-afk not on PATH",
        "install the Ralph CLI (npm i -g @daonhan/ralph) so `ralph-afk` resolves",
        _FALLBACK)


def check_image_deps(run=subprocess.run, docker_bin="docker",
                     image=DEFAULT_IMAGE):
    # The ruamel check asserts the declared FLOOR, not mere importability, and that is
    # the whole point of the assertion. Debian ships python3-ruamel.yaml 0.17.21, which
    # imports perfectly and parses `2026-01-01T10:00:00Z` to a NAIVE datetime — silently
    # dropping the timezone where >=0.18 keeps it. An import-only probe passes on exactly
    # the version the Dockerfile switched to pip to avoid, so it would report "ok" for the
    # image this check exists to reject.
    probe = ("import sys, yaml, ruamel.yaml; "
             "sys.exit(0 if ruamel.yaml.version_info >= (0, 18) else 1)")
    ok = _run_ok(run, [docker_bin, "run", "--rm", image, "python3", "-c", probe])
    if ok:
        return Finding("image_deps", "ok",
                       "python3 + PyYAML + ruamel.yaml>=0.18 present in image", "", "")
    return Finding(
        "image_deps", "fail",
        "image lacks python3/PyYAML, or carries ruamel.yaml below the declared >=0.18 "
        "floor (the apt package is 0.17.21 and drops timezones) — the in-loop gate would "
        "wedge fail-closed or read timestamps differently than the host",
        "rebuild the image from harness/afk/Dockerfile", _FALLBACK)


def check_claude_auth(home=None):
    base = Path(home) if home else Path.home()
    # learn: this intentionally reads the HOST operator's session directory
    # (~/.claude) — the unattended loop cannot run if the host is not logged in,
    # so the preflight inspects the host session dir to confirm auth before launch.
    if (base / ".claude").exists():
        return Finding("claude_auth", "ok", "~/.claude present", "", "")
    return Finding(
        "claude_auth", "fail", "~/.claude not found — claude is not logged in",
        "run `claude` once and authenticate before an unattended run",
        _FALLBACK)


def check_workspace_git(workspace=None):
    ws = Path(workspace) if workspace else Path.cwd()
    if (ws / ".git").exists():
        return Finding("workspace_git", "ok", "%s is a git repo" % ws, "", "")
    return Finding(
        "workspace_git", "fail", "%s is not a git repo" % ws,
        "run AFK from inside the repo clone (the loop commits as it goes)",
        _FALLBACK)


def check_inputs_exist(paths=()):
    missing = [p for p in paths if p and not Path(p).exists()]
    if not missing:
        return Finding("inputs_exist", "ok", "plan + PRD found", "", "")
    return Finding(
        "inputs_exist", "fail", "input(s) not found: %s" % ", ".join(missing),
        "pass existing plan/PRD paths: /hs:afk \"<plan> <prd>\" [N]",
        _FALLBACK)


def check_gate_live(image=DEFAULT_IMAGE, repo_root=None, probe=None):
    probe = probe or gate_live_probe.probe
    root = repo_root or os.environ.get("HARNESS_ROOT") or os.getcwd()
    result = probe(image, root)
    if result.fired:
        return Finding("gate_live", "ok",
                       "stage gate fired inside the image (exit 2)", "", "")
    # The safety argument rests entirely on this gate. If it does not fire, do
    # not run a bare bypass — this is a bold fail that steers to fallback.
    return Finding(
        "gate_live", "fail",
        "in-loop gate did NOT fire inside the image (exit=%r): %s"
        % (result.exit_code, result.detail),
        "rebuild the image; confirm harness/ + .claude/settings.json mount in",
        "do NOT run unattended without a live gate — %s" % _FALLBACK)


def check_version_aware(run=subprocess.run, which=shutil.which,
                        tested_with=None):
    """Warn-only, NEVER fail. A drift from the tested-with record is a
    hint ('suspect #1 if it breaks'), not a blocker. Undeterminable → ok."""
    tested_with = tested_with or TESTED_WITH
    want = (tested_with.get("ralph_cli") or "").strip()
    if not want or not which("ralph-afk"):
        return Finding("version_aware", "ok",
                       "no tested-with baseline to compare (skipped)", "", "")
    proc = run(["ralph-afk", "--version"], capture_output=True, text=True,
               timeout=20)
    got = (getattr(proc, "stdout", "") or "").strip()
    if want in got:
        return Finding("version_aware", "ok",
                       "ralph-afk matches tested-with %s" % want, "", "")
    return Finding(
        "version_aware", "warn",
        "ralph-afk version drifted from tested-with %s (got: %r)"
        % (want, got),
        "if the loop misbehaves, suspect this first; break-glass: pin "
        "RALPH_IMAGE=...@sha256:... or the npm version, or report upstream",
        "")


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _docker_info(run, docker_bin):
    try:
        proc = run([docker_bin, "info"], capture_output=True, text=True,
                   timeout=20)
        return getattr(proc, "returncode", 1), (getattr(proc, "stderr", "")
                                                 or "")
    except (OSError, subprocess.SubprocessError) as e:
        return 1, str(e)


def _run_ok(run, cmd, timeout=120):
    try:
        return getattr(run(cmd, capture_output=True, text=True,
                           timeout=timeout), "returncode", 1) == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _safe(name, fn, *args, **kwargs):
    """Run a check; an exception degrades to a warn finding, never escapes.
    This is the fail-open backstop — preflight must not raise."""
    try:
        return fn(*args, **kwargs)
    except Exception as e:  # noqa: BLE001 — fail-open is the whole point
        return Finding(name, "warn", "check errored (treated as advisory): %s"
                       % e, "re-run preflight; report if it persists", "")


def has_blocker(findings):
    """RED iff any finding is a hard fail. Warns are surfaced, not blocking."""
    return any(f.status == "fail" for f in findings)


# --------------------------------------------------------------------------- #
# orchestration
# --------------------------------------------------------------------------- #

def preflight(plan_path=None, prd_path=None, *, image=DEFAULT_IMAGE,
              workspace=None, repo_root=None, docker_bin="docker",
              machine=None, home=None, run=subprocess.run,
              which=shutil.which, probe=None, tested_with=None):
    """Probe host readiness for an AFK run. Returns a list of Findings; never
    raises, never exit-blocks. The orchestrator branches on has_blocker()."""
    # One `docker info` probe feeds BOTH docker checks (daemon + perm) — avoids a
    # duplicate 20s call. Guarded so a raising `run` degrades to a probe failure
    # rather than escaping preflight (fail-open is the whole contract).
    try:
        docker_info = _docker_info(run, docker_bin)
    except Exception:  # noqa: BLE001 — fail-open: never let the probe crash preflight
        docker_info = (1, "docker info probe raised")
    return [
        _safe("docker_installed", check_docker_installed, which, docker_bin),
        _safe("docker_daemon", check_docker_daemon, run, docker_bin, docker_info),
        _safe("docker_perm", check_docker_perm, run, docker_bin, docker_info),
        _safe("image_present", check_image_present, run, docker_bin, image),
        _safe("arch_amd64", check_arch_amd64, machine),
        _safe("ralph_cli", check_ralph_cli, which),
        _safe("image_deps", check_image_deps, run, docker_bin, image),
        _safe("claude_auth", check_claude_auth, home),
        _safe("workspace_git", check_workspace_git, workspace),
        _safe("inputs_exist", check_inputs_exist, (plan_path, prd_path)),
        _safe("gate_live", check_gate_live, image, repo_root, probe),
        _safe("version_aware", check_version_aware, run, which, tested_with),
    ]


def render(findings):
    """Human-readable summary table."""
    sym = {"ok": "OK  ", "warn": "WARN", "fail": "FAIL"}
    lines = []
    for f in findings:
        lines.append("[%s] %-16s %s" % (sym.get(f.status, "?"), f.check,
                                        f.detail))
        if f.fix:
            lines.append("       fix: %s" % f.fix)
        if f.fallback_hint:
            lines.append("       fallback: %s" % f.fallback_hint)
    verdict = "RED (offer fallback)" if has_blocker(findings) else "GREEN"
    lines.append("-> %s" % verdict)
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="AFK readiness probe (fail-open; always exits 0)")
    ap.add_argument("--plan")
    ap.add_argument("--prd")
    ap.add_argument("--image", default=DEFAULT_IMAGE)
    ap.add_argument("--workspace")
    ap.add_argument("--repo-root")
    ap.add_argument("--json", action="store_true", help="emit findings as JSON")
    args = ap.parse_args(argv)

    findings = preflight(plan_path=args.plan, prd_path=args.prd,
                         image=args.image, workspace=args.workspace,
                         repo_root=args.repo_root)
    if args.json:
        print(json.dumps([f._asdict() for f in findings], indent=2))
    else:
        print(render(findings))
    # Fail-open: a readiness probe NEVER exit-blocks the workflow.
    return 0


if __name__ == "__main__":
    sys.exit(main())
