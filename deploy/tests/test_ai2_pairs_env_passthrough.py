"""AI2_PAIRS_CONCURRENCY must reach the ai2-service container through Compose (P2, D9/F1).

Production resets ``env_file`` for ai2-service, so only keys listed under ``environment:`` in
deploy/compose.prod.yml reach the container; ``docker exec -e`` is not evidence of that.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / "docker-compose.yml"
PROD = ROOT / "deploy/compose.prod.yml"
PROD_ENV = ROOT / "deploy/.env.prod.example"
KEY = "AI2_PAIRS_CONCURRENCY"
DOCKER = shutil.which("docker")


class _ComposeLoader(yaml.SafeLoader):
    """Accepts Compose merge tags (``!reset``, ``!override``) as plain values."""


def _tagged(loader: yaml.SafeLoader, _suffix: str, node: yaml.Node):
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    return loader.construct_scalar(node)


_ComposeLoader.add_multi_constructor("!", _tagged)


def _environment(path: Path) -> dict:
    doc = yaml.load(path.read_text(encoding="utf-8"), Loader=_ComposeLoader)  # noqa: S506
    env = doc["services"]["ai2-service"]["environment"]
    return env if isinstance(env, dict) else dict(item.split("=", 1) for item in env)


# D1
@pytest.mark.parametrize("path", [LOCAL, PROD], ids=["local", "prod"])
def test_compose_static_has_pairs_concurrency(path):
    assert _environment(path)[KEY] == "${AI2_PAIRS_CONCURRENCY:-5}"


def _required_vars() -> set[str]:
    text = LOCAL.read_text(encoding="utf-8") + PROD.read_text(encoding="utf-8")
    return set(re.findall(r"\$\{([A-Z0-9_]+):\?", text))


def _render(args: list[str], extra_env: dict[str, str], tmp_path: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if k != KEY}
    env.update(extra_env)
    result = subprocess.run(
        [DOCKER, "compose", *args, "config", "ai2-service"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )
    # Never echo stdout: the rendered config can carry local secrets.
    assert result.returncode == 0, result.stderr[-2000:]
    return yaml.safe_load(result.stdout)["services"]["ai2-service"]["environment"]


# D2
@pytest.mark.skipif(DOCKER is None, reason="docker CLI is required for the render check")
@pytest.mark.parametrize(("value", "expected"), [(None, "5"), ("1", "1")])
def test_compose_render_prod_passes_pairs_concurrency(tmp_path, value, expected):
    dummies = {name: "x" for name in _required_vars()}
    extra = dummies if value is None else {**dummies, KEY: value}
    env = _render(
        ["-f", "docker-compose.yml", "-f", "deploy/compose.prod.yml", "--env-file", str(PROD_ENV)],
        extra,
        tmp_path,
    )
    assert env[KEY] == expected
    # env_file is reset for ai2-service in production: nothing leaks from ai-service/.env.
    assert "OPENAI_API_KEY" not in env


# D3
@pytest.mark.skipif(DOCKER is None, reason="docker CLI is required for the render check")
@pytest.mark.parametrize(("value", "expected"), [(None, "5"), ("1", "1")])
def test_compose_render_local_passes_pairs_concurrency(tmp_path, value, expected):
    empty = tmp_path / "empty.env"
    empty.write_text("", encoding="utf-8")
    extra = {} if value is None else {KEY: value}
    env = _render(["-f", "docker-compose.yml", "--env-file", str(empty)], extra, tmp_path)
    assert env[KEY] == expected


# --- P3: AI2_PAIRS_REASONING_EFFORT (D9/F3.3). Production stays empty (no effort sent) until
# an OpenAI confirmation run passes (F3.9); local may diverge only after its gate.
EFFORT = "AI2_PAIRS_REASONING_EFFORT"
EFFORT_DEFAULTS = {
    "local": "${AI2_PAIRS_REASONING_EFFORT:-}",
    "prod": "${AI2_PAIRS_REASONING_EFFORT:-}",
}
EFFORT_RENDERED = {"local": "", "prod": ""}


def _render_without(keys: set[str], args: list[str], extra_env: dict[str, str]) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in keys}
    env.update(extra_env)
    result = subprocess.run(
        [DOCKER, "compose", *args, "config", "ai2-service"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    return yaml.safe_load(result.stdout)["services"]["ai2-service"]["environment"]


def _prod_args() -> list[str]:
    return [
        "-f",
        "docker-compose.yml",
        "-f",
        "deploy/compose.prod.yml",
        "--env-file",
        str(PROD_ENV),
    ]


# D4
@pytest.mark.parametrize("path", [LOCAL, PROD], ids=["local", "prod"])
def test_compose_static_has_pairs_reasoning_effort(path):
    assert _environment(path)[EFFORT] == EFFORT_DEFAULTS["local" if path == LOCAL else "prod"]


def test_prod_env_example_lists_pairs_reasoning_effort():
    lines = PROD_ENV.read_text(encoding="utf-8").splitlines()
    assert f"{EFFORT}={EFFORT_RENDERED['prod']}" in lines


# D5
@pytest.mark.skipif(DOCKER is None, reason="docker CLI is required for the render check")
@pytest.mark.parametrize(
    ("value", "expected"), [(None, EFFORT_RENDERED["prod"]), ("medium", "medium")]
)
def test_compose_render_prod_passes_pairs_reasoning_effort(value, expected):
    extra = {name: "x" for name in _required_vars()}
    if value is not None:
        extra[EFFORT] = value
    env = _render_without({EFFORT}, _prod_args(), extra)
    assert env[EFFORT] == expected


# D6
@pytest.mark.skipif(DOCKER is None, reason="docker CLI is required for the render check")
@pytest.mark.parametrize(
    ("value", "expected"), [(None, EFFORT_RENDERED["local"]), ("medium", "medium")]
)
def test_compose_render_local_passes_pairs_reasoning_effort(tmp_path, value, expected):
    empty = tmp_path / "empty.env"
    empty.write_text("", encoding="utf-8")
    extra = {} if value is None else {EFFORT: value}
    env = _render_without({EFFORT}, ["-f", "docker-compose.yml", "--env-file", str(empty)], extra)
    assert env[EFFORT] == expected


@pytest.mark.skipif(DOCKER is None, reason="docker CLI is required for the render check")
def test_compose_render_prod_effort_empty_when_unset_even_if_local_differs():
    extra = {name: "x" for name in _required_vars()}
    assert _render_without({EFFORT}, _prod_args(), extra)[EFFORT] == ""
