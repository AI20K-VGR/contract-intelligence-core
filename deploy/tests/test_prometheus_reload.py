"""deploy.sh restarts Prometheus when its mounted config changed (the real block, fake docker)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from test_keycloak_configure import BASH

ROOT = Path(__file__).resolve().parents[2]
START = "prometheus_changed=0\n"
END = 'echo "[deploy] waiting for backend health"'
TARGET = "/etc/prometheus/prometheus.yml"
CONFIG = "scrape_configs:\n  - job_name: ai2-service\n"


def _block() -> str:
    source = (ROOT / "deploy/deploy.sh").read_text(encoding="utf-8")
    assert source.index('"${COMPOSE[@]}" up -d --remove-orphans') < source.index(START)
    return START + source.split(START, 1)[1].split(END, 1)[0]


def _run(
    tmp_path: Path,
    *,
    live: str | None,
    check_ok: bool = True,
    running: bool = True,
) -> subprocess.CompletedProcess:
    """`live` is what ci-prometheus holds (None: no such file in the container)."""
    host = tmp_path / "host"
    host.mkdir()
    (host / "prometheus.yml").write_text(CONFIG, encoding="utf-8")
    container = tmp_path / "container"
    container.mkdir()
    if live is not None:
        (container / "prometheus.yml").write_text(live, encoding="utf-8")
    mounts = f"{host.as_posix()}/prometheus.yml|{TARGET}"
    check = "true" if check_ok else 'echo "FAILED: field bogus_key not found"; false'
    fakes = f"""
set -euo pipefail
calls="{tmp_path.as_posix()}/calls"
: > "$calls"
docker() {{
  if [[ "$1" == inspect ]]; then
    {"true" if running else "return 1"}
    [[ "$2" == -f ]] && printf '%s\n' "{mounts}"
    return 0
  fi
  if [[ "$1" == exec && "$2" == ci-prometheus && "$3" == sha256sum ]]; then
    local f="{container.as_posix()}/$(basename "$4")"
    [[ -f "$f" ]] || return 1
    sha256sum "$f"; return 0
  fi
  echo "unexpected docker $*" >&2; return 99
}}
compose() {{
  echo "compose $*" >> "$calls"
  if [[ "$1" == run ]]; then {check}; fi
}}
COMPOSE=(compose)
"""
    return subprocess.run(
        [BASH, "-c", fakes + _block()],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )


def _calls(tmp_path: Path) -> list[str]:
    return (tmp_path / "calls").read_text(encoding="utf-8").splitlines()


@pytest.mark.skipif(BASH is None, reason="Bash is required")
def test_unchanged_config_leaves_prometheus_alone(tmp_path: Path) -> None:
    proc = _run(tmp_path, live=CONFIG)

    assert proc.returncode == 0, proc.stderr
    assert _calls(tmp_path) == []
    assert "Prometheus" not in proc.stdout


@pytest.mark.skipif(BASH is None, reason="Bash is required")
def test_changed_config_is_checked_then_prometheus_restarts(tmp_path: Path) -> None:
    proc = _run(tmp_path, live="scrape_configs: []\n")

    assert proc.returncode == 0, proc.stderr
    calls = _calls(tmp_path)
    check = f"compose run --rm --no-deps -T --entrypoint promtool prometheus check config {TARGET}"
    assert calls == [check, "compose restart prometheus"]
    assert f"Prometheus config changed: {TARGET}" in proc.stdout
    assert "Prometheus restarted with the new config" in proc.stdout


@pytest.mark.skipif(BASH is None, reason="Bash is required")
def test_file_missing_in_the_container_counts_as_changed(tmp_path: Path) -> None:
    proc = _run(tmp_path, live=None)

    assert proc.returncode == 0, proc.stderr
    assert _calls(tmp_path)[-1] == "compose restart prometheus"


@pytest.mark.skipif(BASH is None, reason="Bash is required")
def test_a_config_that_does_not_load_stops_the_deploy_without_restarting(
    tmp_path: Path,
) -> None:
    proc = _run(tmp_path, live="old\n", check_ok=False)

    assert proc.returncode == 1
    assert not any(c.startswith("compose restart") for c in _calls(tmp_path))
    assert "Prometheus keeps the old one" in proc.stderr
    assert "bogus_key" in proc.stderr


@pytest.mark.skipif(BASH is None, reason="Bash is required")
def test_no_prometheus_container_skips_the_check(tmp_path: Path) -> None:
    proc = _run(tmp_path, live=None, running=False)

    assert proc.returncode == 0, proc.stderr
    assert _calls(tmp_path) == []


def test_block_runs_after_caddy_and_before_the_health_checks() -> None:
    source = (ROOT / "deploy/deploy.sh").read_text(encoding="utf-8")
    up = source.index('"${COMPOSE[@]}" up -d --remove-orphans')
    caddy = source.index("caddy_changed=0\n")
    block = source.index(START)
    health = source.index(END)
    assert up < caddy < block < health
