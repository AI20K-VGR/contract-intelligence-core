"""Exercise the real deploy loop with a virtual Bash clock and provider responses."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from test_keycloak_configure import BASH

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(BASH is None, reason="Bash is required")
@pytest.mark.parametrize(
    "mode", ["ready", "recover", "slow_failure", "fast_failure", "logs_timeout"]
)
def test_ai2_readiness_has_total_deadline(mode):
    source = (ROOT / "deploy/deploy.sh").read_text(encoding="utf-8")
    loop = source.split("ai2_ready=0\n", 1)[1].split(
        'echo "[deploy] AI2 full capability: ready"', 1
    )[0]
    setup = r"""
set -euo pipefail
SECONDS=0
calls=0
last_timeout=0
probe() {
  if [[ "$1" == logs ]]; then
    echo diagnostic_logs >&2
    if [[ "$mode" == logs_timeout ]]; then return 124; fi
    return 0
  fi
  calls=$((calls + 1))
  [[ "${*: -1}" =~ timeout=([0-9]+) ]]
  last_timeout=${BASH_REMATCH[1]}
  (( last_timeout > 0 && last_timeout <= 90 ))
  if [[ "$mode" == ready ]] || [[ "$mode" == recover && "$calls" -eq 2 ]]; then
    return 0
  fi
  if [[ "$mode" == slow_failure ]]; then SECONDS=$((SECONDS + last_timeout)); fi
  return 1
}
sleep() { SECONDS=$((SECONDS + $1)); }
timeout() {
  [[ "$1" == --kill-after=5s ]]
  [[ "$2" =~ ^[0-9]+s$ ]]
  if [[ "$3" == probe && "$4" == logs ]]; then [[ "$2" == 10s ]]; fi
  shift 2
  "$@"
}
COMPOSE=(probe)
trap 'echo "$ai2_ready $calls $SECONDS $last_timeout"' EXIT
ai2_ready=0
"""
    proc = subprocess.run(
        [BASH, "-c", f"mode={mode}\n{setup}\n{loop}".replace("SECONDS", "test_clock")],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    ready, calls, elapsed, last_timeout = map(int, proc.stdout.strip().split())
    if mode in {"ready", "recover"}:
        assert proc.returncode == 0, proc.stderr
        assert ready == 1
        assert calls == (1 if mode == "ready" else 2)
        assert elapsed <= 5
    else:
        assert proc.returncode == 1
        assert ready == 0
        assert elapsed == 600
        assert "diagnostic_logs" in proc.stderr
        assert calls == (7 if mode == "slow_failure" else 120)
        if mode == "slow_failure":
            assert last_timeout == 30
