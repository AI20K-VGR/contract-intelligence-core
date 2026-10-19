"""deploy.sh schedules the nightly backup; backup.sh keeps BACKUP_KEEP_DAYS of them.

Runs the real blocks of both scripts against a temporary env file and cron file,
so the test needs no root and touches nothing outside tmp_path.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from test_keycloak_configure import BASH

ROOT = Path(__file__).resolve().parents[2]
DEPLOY_START = "# Nightly backup (deploy/backup.sh)."
DEPLOY_END = 'api="https://$(envval API_HOST)"'
BACKUP_START = "DEST=${BACKUP_DIR:-/var/backups/contract-intelligence}"
BACKUP_END = 'mkdir -p "$DEST/$stamp"'


def _between(path: str, start: str, end: str) -> str:
    source = (ROOT / path).read_text(encoding="utf-8")
    return start + source.split(start, 1)[1].split(end, 1)[0]


def _run(tmp_path: Path, script: str, env_lines: list[str], env: dict[str, str] | None = None):
    env_file = tmp_path / ".env.prod"
    env_file.write_text("\n".join(env_lines) + "\n", encoding="utf-8")
    prelude = f"""
set -euo pipefail
ENV_FILE="{env_file.as_posix()}"
envval() {{ grep -E "^$1=" "$ENV_FILE" | tail -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//'; }}
systemctl() {{ return 0; }}
"""
    return subprocess.run(
        [BASH, "-c", prelude + script],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
        cwd=tmp_path,
        env={"PATH": "/usr/bin:/bin", **(env or {})},
    )


def _schedule(tmp_path: Path, env_lines: list[str]):
    cron = tmp_path / "ci-backup"
    proc = _run(
        tmp_path,
        _between("deploy/deploy.sh", DEPLOY_START, DEPLOY_END),
        env_lines,
        {"BACKUP_CRON_FILE": cron.as_posix()},
    )
    return proc, cron


@pytest.mark.skipif(BASH is None, reason="Bash is required")
def test_default_schedule_is_two_in_the_morning_vietnam_time(tmp_path: Path) -> None:
    proc, cron = _schedule(tmp_path, ["BACKUP_SCHEDULE="])

    assert proc.returncode == 0, proc.stderr
    lines = cron.read_text(encoding="utf-8").splitlines()
    assert lines[-1].startswith("0 19 * * * root ")
    assert lines[-1].endswith("/deploy/backup.sh >> /var/log/ci-backup.log 2>&1")
    assert "SHELL=/bin/bash" in lines
    assert "nightly backup scheduled: 0 19 * * *" in proc.stdout


@pytest.mark.skipif(BASH is None, reason="Bash is required")
def test_a_second_deploy_leaves_the_same_schedule_alone(tmp_path: Path) -> None:
    _schedule(tmp_path, ["BACKUP_SCHEDULE=30 18 * * *"])
    proc, cron = _schedule(tmp_path, ["BACKUP_SCHEDULE=30 18 * * *"])

    assert proc.returncode == 0, proc.stderr
    assert "scheduled" not in proc.stdout  # unchanged: not rewritten
    assert cron.read_text(encoding="utf-8").count("backup.sh") == 1


@pytest.mark.skipif(BASH is None, reason="Bash is required")
def test_a_changed_schedule_replaces_the_old_one(tmp_path: Path) -> None:
    _schedule(tmp_path, ["BACKUP_SCHEDULE="])
    proc, cron = _schedule(tmp_path, ["BACKUP_SCHEDULE=0 20 * * 1-5"])

    assert proc.returncode == 0, proc.stderr
    text = cron.read_text(encoding="utf-8")
    assert "0 20 * * 1-5 root " in text
    assert "0 19 * * *" not in text


@pytest.mark.skipif(BASH is None, reason="Bash is required")
def test_off_removes_the_schedule(tmp_path: Path) -> None:
    _schedule(tmp_path, ["BACKUP_SCHEDULE="])
    proc, cron = _schedule(tmp_path, ["BACKUP_SCHEDULE=off"])

    assert proc.returncode == 0, proc.stderr
    assert not cron.exists()
    assert "schedule removed" in proc.stdout


@pytest.mark.skipif(BASH is None, reason="Bash is required")
@pytest.mark.parametrize("value", ["0 19 * *", "0 19 * * * *", "@daily", "0 19 * * *; rm -rf /"])
def test_a_value_that_is_not_a_five_field_expression_stops_the_deploy(
    tmp_path: Path, value: str
) -> None:
    proc, cron = _schedule(tmp_path, [f"BACKUP_SCHEDULE={value}"])

    assert proc.returncode == 1
    assert "not a 5-field cron expression" in proc.stderr
    assert not cron.exists()


@pytest.mark.skipif(BASH is None, reason="Bash is required")
@pytest.mark.parametrize(
    ("env_lines", "env", "expected"),
    [
        (["BACKUP_KEEP_DAYS="], {}, "3"),
        (["BACKUP_KEEP_DAYS=5"], {}, "5"),
        (["BACKUP_KEEP_DAYS=5"], {"BACKUP_KEEP_DAYS": "2"}, "2"),  # environment wins
        ([], {}, "3"),
    ],
)
def test_keep_days_come_from_the_environment_then_the_env_file_then_three(
    tmp_path: Path, env_lines: list[str], env: dict[str, str], expected: str
) -> None:
    block = _between("deploy/backup.sh", BACKUP_START, BACKUP_END)
    proc = _run(tmp_path, block + 'echo "keep=$KEEP_DAYS"', env_lines, env)

    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip().endswith(f"keep={expected}")


@pytest.mark.skipif(BASH is None, reason="Bash is required")
def test_keep_days_must_be_a_number(tmp_path: Path) -> None:
    block = _between("deploy/backup.sh", BACKUP_START, BACKUP_END)
    proc = _run(tmp_path, block, ["BACKUP_KEEP_DAYS=a week"])

    assert proc.returncode == 1
    assert "must be a number of days" in proc.stderr


def test_the_schedule_is_installed_before_the_smoke_test() -> None:
    source = (ROOT / "deploy/deploy.sh").read_text(encoding="utf-8")
    assert source.index("configuring Keycloak") < source.index(DEPLOY_START)
    assert source.index(DEPLOY_START) < source.index('echo "[deploy] smoke test"')
