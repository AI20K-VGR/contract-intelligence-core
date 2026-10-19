"""Langfuse settings must reach ai2-service in production (question cost tracking).

Production resets ``env_file`` for ai2-service, so only keys listed under
``environment:`` in deploy/compose.prod.yml reach the container.
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
PROD = ROOT / "deploy/compose.prod.yml"
LOCAL = ROOT / "docker-compose.yml"
PROD_ENV = ROOT / "deploy/.env.prod.example"
KEYS = (
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_BASE_URL",
    "LANGFUSE_TRACING_ENVIRONMENT",
    "LANGFUSE_SAMPLE_RATE",
    "AI2_LLM_PRICES_JSON",
)


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
    return doc["services"]["ai2-service"]["environment"]


def test_prod_passes_langfuse_settings_with_empty_key_defaults():
    env = _environment(PROD)
    for key in KEYS:
        assert env[key].startswith("${" + key + ":-"), key
    # Off unless the server sets the keys: never a required (`:?`) variable.
    assert env["LANGFUSE_PUBLIC_KEY"] == "${LANGFUSE_PUBLIC_KEY:-}"
    assert env["LANGFUSE_SECRET_KEY"] == "${LANGFUSE_SECRET_KEY:-}"


def test_ai2_traces_are_not_labelled_as_ai1():
    for path in (PROD, LOCAL):
        assert _environment(path)["OTEL_SERVICE_NAME"] == "contract-intelligence-ai2"


def test_prod_env_example_documents_every_key_without_values():
    lines = PROD_ENV.read_text(encoding="utf-8").splitlines()
    for key in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "AI2_LLM_PRICES_JSON"):
        assert f"{key}=" in lines, key
