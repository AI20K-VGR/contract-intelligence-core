"""Application logs survive a deploy: journald driver plus capped journald storage.

Before, every service logged to the per-container json-file, which is deleted
with the container. Each deploy recreates containers, so the logs of two
production 500s on 20/10/2026 were gone by the time anyone looked.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from test_backup_schedule import _between, _run
from test_keycloak_configure import BASH

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / "docker-compose.yml"
PROD = ROOT / "deploy/compose.prod.yml"
DOCKER = shutil.which("docker")
SERVICES = (
    "frontend",
    "keycloak",
    "kafka",
    "backend",
    "backend-worker",
    "ai1-worker",
    "ai2-service",
    "minio",
    "caddy",
)
BLOCK_START = "# Service logs (deploy/compose.prod.yml sends them to journald)."
BLOCK_END = '"${COMPOSE[@]}" config --quiet'


class _ComposeLoader(yaml.SafeLoader):
    """Accepts Compose merge tags (``!reset``, ``!override``) as plain values."""


def _tagged(loader: yaml.SafeLoader, _suffix: str, node: yaml.Node):
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    return loader.construct_scalar(node)


_ComposeLoader.add_multi_constructor("!", _tagged)


@pytest.mark.parametrize("service", SERVICES)
def test_application_services_log_to_journald(service: str) -> None:
    doc = yaml.load(PROD.read_text(encoding="utf-8"), Loader=_ComposeLoader)
    logging = doc["services"][service]["logging"]
    assert logging["driver"] == "journald"
    assert logging["options"]["tag"] == "{{.Name}}"


@pytest.mark.skipif(
    DOCKER is None, reason="docker CLI is required for the render check"
)
def test_rendered_prod_config_uses_journald() -> None:
    text = LOCAL.read_text(encoding="utf-8") + PROD.read_text(encoding="utf-8")
    dummies = {name: "x" for name in re.findall(r"\$\{([A-Z0-9_]+):\?", text)}
    result = subprocess.run(
        [
            DOCKER,
            "compose",
            "-f",
            str(LOCAL),
            "-f",
            str(PROD),
            "config",
            "backend",
            "caddy",
        ],
        cwd=ROOT,
        env={**os.environ, **dummies},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )
    # Never echo stdout: the rendered config can carry local secrets.
    assert result.returncode == 0, result.stderr[-2000:]
    services = yaml.safe_load(result.stdout)["services"]
    for name in ("backend", "caddy"):
        assert services[name]["logging"]["driver"] == "journald"


def _limits(tmp_path: Path, env_lines: list[str]):
    conf = tmp_path / "journald.conf.d" / "ci-logs.conf"
    proc = _run(
        tmp_path,
        _between("deploy/deploy.sh", BLOCK_START, BLOCK_END),
        env_lines,
        {"JOURNALD_CONF_FILE": conf.as_posix()},
    )
    return proc, conf


@pytest.mark.skipif(BASH is None, reason="Bash is required")
def test_journald_is_capped_by_default(tmp_path: Path) -> None:
    proc, conf = _limits(tmp_path, [])

    assert proc.returncode == 0, proc.stderr
    text = conf.read_text(encoding="utf-8")
    assert "Storage=persistent" in text
    assert "SystemMaxUse=2G" in text
    assert "SystemKeepFree=4G" in text
    assert "MaxRetentionSec=30day" in text
    assert "service logs: journald keeps up to 2G, 30 days" in proc.stdout


@pytest.mark.skipif(BASH is None, reason="Bash is required")
def test_limits_come_from_env_and_an_unchanged_file_is_left_alone(
    tmp_path: Path,
) -> None:
    env = ["LOG_JOURNAL_MAX_USE=500M", "LOG_RETENTION_DAYS=14"]
    proc, conf = _limits(tmp_path, env)
    assert proc.returncode == 0, proc.stderr
    assert "SystemMaxUse=500M" in conf.read_text(encoding="utf-8")
    assert "MaxRetentionSec=14day" in conf.read_text(encoding="utf-8")

    again, _ = _limits(tmp_path, env)
    assert again.returncode == 0, again.stderr
    assert "service logs" not in again.stdout  # no rewrite, no journald restart


@pytest.mark.skipif(BASH is None, reason="Bash is required")
@pytest.mark.parametrize(
    "line",
    ["LOG_JOURNAL_MAX_USE=lots", "LOG_JOURNAL_MAX_USE=0G", "LOG_RETENTION_DAYS=two"],
)
def test_a_bad_limit_stops_the_deploy(tmp_path: Path, line: str) -> None:
    proc, conf = _limits(tmp_path, [line])

    assert proc.returncode == 1
    assert "LOG_JOURNAL_MAX_USE must look like" in proc.stderr
    assert not conf.exists()


def test_limits_are_checked_before_the_stack_changes() -> None:
    """A bad value must stop the deploy before build and `up -d` (review of #159)."""
    source = (ROOT / "deploy/deploy.sh").read_text(encoding="utf-8")
    check = source.index("LOG_JOURNAL_MAX_USE must look like")
    assert check < source.index('"${COMPOSE[@]}" build')
    assert check < source.index('"${COMPOSE[@]}" up -d')
