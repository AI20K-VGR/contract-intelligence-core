"""deploy.sh restarts Caddy when a mounted config file changed (the real block, fake docker)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from test_keycloak_configure import BASH

ROOT = Path(__file__).resolve().parents[2]
START = "caddy_changed=0\n"
END = 'echo "[deploy] waiting for backend health"'


def _block() -> str:
    source = (ROOT / "deploy/deploy.sh").read_text(encoding="utf-8")
    assert source.index('"${COMPOSE[@]}" up -d --remove-orphans') < source.index(START)
    return START + source.split(START, 1)[1].split(END, 1)[0]


def _run(
    tmp_path: Path, *, live: dict[str, str], adapt_ok: bool = True
) -> subprocess.CompletedProcess:
    """Host files differ from `live` (what ci-caddy holds) where the test says so."""
    host = tmp_path / "host"
    host.mkdir()
    (host / "Caddyfile").write_text("api { respond 404 }\n", encoding="utf-8")
    (host / "frontend.caddy").write_text("app {}\n", encoding="utf-8")
    (host / "certs").mkdir()  # directory mounts are skipped
    container = tmp_path / "container"
    container.mkdir()
    for name, text in live.items():
        (container / name).write_text(text, encoding="utf-8")
    mounts = "\n".join(
        [
            f"{host.as_posix()}/Caddyfile|/etc/caddy/Caddyfile",
            f"{host.as_posix()}/frontend.caddy|/etc/caddy/sites/frontend.caddy",
            f"{host.as_posix()}/certs|/etc/caddy/certs",
        ]
    )
    adapt = "true" if adapt_ok else 'echo "Error: unrecognized directive"; false'
    fakes = f"""
set -euo pipefail
calls="{tmp_path.as_posix()}/calls"
: > "$calls"
docker() {{
  if [[ "$1" == inspect ]]; then printf '%s\\n' "{mounts}"; return 0; fi
  if [[ "$1" == exec && "$2" == ci-caddy && "$3" == sha256sum ]]; then
    local f="{container.as_posix()}/$(basename "$4")"
    [[ -f "$f" ]] || return 1
    sha256sum "$f"; return 0
  fi
  echo "unexpected docker $*" >&2; return 99
}}
compose() {{
  echo "compose $*" >> "$calls"
  if [[ "$1" == run ]]; then {adapt}; fi
}}
COMPOSE=(compose)
"""
    return subprocess.run(
        [BASH, "-c", fakes + _block()], capture_output=True, text=True, check=False, timeout=20
    )


def _calls(tmp_path: Path) -> list[str]:
    return (tmp_path / "calls").read_text(encoding="utf-8").splitlines()


SAME = {"Caddyfile": "api { respond 404 }\n", "frontend.caddy": "app {}\n"}


@pytest.mark.skipif(BASH is None, reason="Bash is required")
def test_unchanged_config_leaves_caddy_alone(tmp_path: Path) -> None:
    proc = _run(tmp_path, live=SAME)

    assert proc.returncode == 0, proc.stderr
    assert _calls(tmp_path) == []
    assert "Caddy" not in proc.stdout


@pytest.mark.skipif(BASH is None, reason="Bash is required")
def test_changed_caddyfile_is_checked_then_caddy_restarts(tmp_path: Path) -> None:
    proc = _run(tmp_path, live={**SAME, "Caddyfile": "api { respond 200 }\n"})

    assert proc.returncode == 0, proc.stderr
    calls = _calls(tmp_path)
    assert calls[0].startswith("compose run --rm --no-deps -T caddy caddy adapt")
    assert calls[1:] == ["compose restart caddy"]
    assert "Caddy config changed: /etc/caddy/Caddyfile" in proc.stdout
    assert "frontend.caddy" not in proc.stdout
    assert "Caddy restarted with the new config" in proc.stdout


@pytest.mark.skipif(BASH is None, reason="Bash is required")
def test_file_missing_in_the_container_counts_as_changed(tmp_path: Path) -> None:
    proc = _run(tmp_path, live={"Caddyfile": SAME["Caddyfile"]})

    assert proc.returncode == 0, proc.stderr
    assert _calls(tmp_path)[-1] == "compose restart caddy"
    assert "Caddy config changed: /etc/caddy/sites/frontend.caddy" in proc.stdout


@pytest.mark.skipif(BASH is None, reason="Bash is required")
def test_a_config_that_does_not_parse_stops_the_deploy_without_restarting(tmp_path: Path) -> None:
    proc = _run(tmp_path, live={**SAME, "Caddyfile": "old\n"}, adapt_ok=False)

    assert proc.returncode == 1
    assert not any(c.startswith("compose restart") for c in _calls(tmp_path))
    assert "keeps serving the old one" in proc.stderr
    assert "unrecognized directive" in proc.stderr


def test_block_runs_right_after_up_and_before_the_health_checks() -> None:
    source = (ROOT / "deploy/deploy.sh").read_text(encoding="utf-8")
    up = source.index('"${COMPOSE[@]}" up -d --remove-orphans')
    block = source.index(START)
    health = source.index(END)
    smoke = source.index("[deploy] smoke test")
    assert up < block < health < smoke
