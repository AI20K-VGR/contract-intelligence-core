#!/usr/bin/env python3
"""gate_live_probe.py — does the harness stage gate fire inside a sandbox image?

A deterministic, token-free probe. It runs gate_stage.py INSIDE the given
Docker image against a mounted repo (as HARNESS_ROOT) plus a throwaway active
plan that carries NO verification.json, feeding a PreToolUse(Bash "git push")
payload on stdin. The stage gate is fail-closed, so a correctly provisioned
image blocks that push with exit 2 and a reason naming the missing
verification artifact. A bare image (no python3 / no PyYAML / no gate) cannot
produce that block — the probe reads that absence as "guardrail not live".

Reused in two places (DRY — one probe, two callers):
  - the sandbox image test: proves the image carries python3 + PyYAML and the
    gate machinery actually runs inside the container.
  - the preflight `gate_live` check before any unattended run: a live in-loop
    guardrail must be confirmed, never assumed — a silently broken hook means
    fall back, not run a bare bypass.

Shells out to ``docker`` and never raises on a docker failure: a fail-open
caller gets a ProbeResult with fired=False plus a detail string, not an
exception.
"""

import json
import shutil
import subprocess
import tempfile
from collections import namedtuple
from pathlib import Path

ProbeResult = namedtuple("ProbeResult", ("fired", "exit_code", "detail"))

# A "git push" with no verification.json is the cheapest command that exercises
# the full hard-stage path: stage detection -> active plan -> artifact check.
_PUSH_PAYLOAD = json.dumps(
    {"tool_name": "Bash", "tool_input": {"command": "git push"}})

# in_progress frontmatter so the plan also resolves on the fallback path, even
# though HARNESS_ACTIVE_PLAN pins it explicitly below.
_PLAN_MD = "---\ntitle: gate-live probe\nstatus: in_progress\n---\n"


def docker_available(docker_bin: str = "docker") -> bool:
    """True only when the docker CLI exists AND its daemon answers — callers
    use this to skip (tests) or warn-and-fall-back (preflight) cleanly."""
    if not shutil.which(docker_bin):
        return False
    try:
        return subprocess.run(
            [docker_bin, "info"], capture_output=True, timeout=20
        ).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def probe(image: str, repo_root, *, docker_bin: str = "docker",
          timeout: int = 120) -> ProbeResult:
    """Run the deterministic gate probe inside ``image``.

    fired=True iff the gate blocked the push (exit 2) with a reason naming the
    verification artifact — meaning python3 + PyYAML are present and the gate
    is live inside the container. Any docker failure returns fired=False with a
    detail string (never raises)."""
    repo_root = Path(repo_root).resolve()
    # Ensure plans/ exists on the host so the :ro /work bind-mount can be overlaid
    # at /work/plans.  Without this, Docker cannot create the mount point inside the
    # read-only layer on checkouts where plans/ is gitignored and absent.
    (repo_root / "plans").mkdir(exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="gate-live-plan-")
    try:
        # The active plan must live UNDER <root>/plans/ (the gate rejects a plan dir
        # outside it — a redirected plan outside the forgery-guarded plans/*/artifacts/
        # zone would be a forgery vector). Overlay the repo's existing /work/plans with
        # our controlled dir (mounting the already-present /work/plans needs no mkdir,
        # so it survives the :ro repo mount) and pin the plan inside it.
        plan_dir = Path(tmp) / "gate-live-probe"
        plan_dir.mkdir()
        (plan_dir / "plan.md").write_text(_PLAN_MD, encoding="utf-8")
        (plan_dir / "state").mkdir(exist_ok=True)
        cmd = [
            docker_bin, "run", "--rm", "-i",
            "-v", "%s:/work:ro" % repo_root,
            "-v", "%s:/work/plans" % tmp,
            "-e", "HARNESS_ROOT=/work",
            "-e", "HARNESS_ACTIVE_PLAN=/work/plans/gate-live-probe",
            "-e", "HARNESS_STATE_DIR=/work/plans/gate-live-probe/state",
            image, "python3", "/work/harness/hooks/gate_stage.py",
        ]
        try:
            proc = subprocess.run(cmd, input=_PUSH_PAYLOAD, capture_output=True,
                                  text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return ProbeResult(False, None, "docker run timed out after %ss"
                               % timeout)
        except (OSError, subprocess.SubprocessError) as e:
            return ProbeResult(False, None, "docker invocation failed: %s" % e)
        fired = proc.returncode == 2 and "verification" in proc.stderr
        detail = (proc.stderr.strip() or proc.stdout.strip() or "no output")
        return ProbeResult(fired, proc.returncode, detail)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
