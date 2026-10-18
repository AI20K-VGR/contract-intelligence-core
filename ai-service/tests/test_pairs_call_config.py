"""P3 pairs call knobs: AI2_PAIRS_REASONING_EFFORT and the effective prompt version (F3.1/F3.2)."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from app.llm.client import NineRouterClient
from app.pipeline import runtime as runtime_mod
from app.pipeline.contract_graph import pair_builder as builder
from app.pipeline.contract_graph import pair_classifier as pc
from app.pipeline.runtime import ProcessingRuntime
from tests.test_contract_graph_pair_builder import build

ENV = "AI2_PAIRS_REASONING_EFFORT"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv(ENV, raising=False)
    monkeypatch.delenv("AI2_LLM_LIGHT_REASONING_EFFORT", raising=False)
    # Same isolation as test_contract_graph_pair_builder: no real pairs endpoint.
    for key in (
        builder.PAIRS_BASE_URL_ENV,
        builder.PAIRS_API_KEY_ENV,
        builder.PAIRS_MODEL_ENV,
        builder.PAIRS_ENV,
    ):
        monkeypatch.delenv(key, raising=False)
    runtime_mod._warned_pairs_efforts.clear()
    runtime_mod._warned_light_efforts.clear()


def _capturing_client(model: str, sent: list[dict]) -> NineRouterClient:
    client = NineRouterClient(api_key="sk-test", model=model)

    def create(**kwargs: object) -> SimpleNamespace:
        sent.append(kwargs)
        choice = SimpleNamespace(
            message=SimpleNamespace(content='{"ok": true}'), finish_reason="stop"
        )
        return SimpleNamespace(choices=[choice], usage=None, model=model)

    client._client.chat.completions.create = create  # type: ignore[method-assign]
    return client


def _sent(model: str, operation: str) -> dict:
    sent: list[dict] = []
    runtime = ProcessingRuntime(egress_allowed=True, max_llm_calls=2)
    runtime.complete_json(_capturing_client(model, sent), "Return JSON.", "u", operation=operation)
    return sent[0]


# R3.1
@pytest.mark.parametrize("value", ["low", "LOW ", "minimal", "medium", "high"])
def test_pairs_effort_from_env(monkeypatch, value):
    monkeypatch.setenv(ENV, value)
    assert runtime_mod.pairs_reasoning_effort() == value.strip().casefold()
    assert _sent("gpt-5.5", "pairs")["reasoning_effort"] == value.strip().casefold()


# R3.2
@pytest.mark.parametrize("value", [None, "", "  ", "provider_default", "PROVIDER_DEFAULT"])
def test_pairs_effort_unset_empty_or_provider_default_sends_nothing(monkeypatch, value):
    if value is not None:
        monkeypatch.setenv(ENV, value)
    assert runtime_mod.pairs_reasoning_effort() is None
    assert "reasoning_effort" not in _sent("gpt-5.5", "pairs")


# R3.3
def test_pairs_effort_invalid_value_ignored_with_one_warning(monkeypatch, caplog):
    monkeypatch.setenv(ENV, "turbo")
    with caplog.at_level(logging.WARNING, logger="app.pipeline.runtime"):
        assert runtime_mod.pairs_reasoning_effort() is None
        assert "reasoning_effort" not in _sent("gpt-5.5", "pairs")
        assert runtime_mod.pairs_reasoning_effort() is None
    warnings = [r for r in caplog.records if ENV in r.getMessage()]
    assert len(warnings) == 1


# R3.4
@pytest.mark.parametrize("operation", ["slot_context", "alias", "semantic", None])
def test_pairs_effort_not_applied_to_other_operations(monkeypatch, operation):
    monkeypatch.setenv(ENV, "low")
    assert "reasoning_effort" not in _sent("gpt-5.5", operation)


def test_pairs_effort_does_not_change_light_path(monkeypatch):
    monkeypatch.setenv(ENV, "high")
    monkeypatch.setenv("AI2_LLM_LIGHT_REASONING_EFFORT", "low")
    assert _sent("gpt-5.5", "slot_context")["reasoning_effort"] == "low"
    assert _sent("gpt-5.5", "pairs")["reasoning_effort"] == "high"


# R3.5
@pytest.mark.parametrize(
    ("model", "expected"),
    [("gpt-5.5", "low"), ("cx/gpt-5.6-luna", "low"), ("gpt-4o-mini", None), ("claude-x", None)],
)
def test_pairs_effort_only_sent_to_gpt5_models(monkeypatch, model, expected):
    monkeypatch.setenv(ENV, "low")
    assert _sent(model, "pairs").get("reasoning_effort") == expected


# R3.6
@pytest.mark.parametrize(
    ("effort", "batch", "expected"),
    [
        (None, 8, "pairs-v13"),
        ("low", 8, "pairs-v13+effort-low"),
        (None, 10, "pairs-v13+batch-10"),
        ("low", 10, "pairs-v13+effort-low+batch-10"),
    ],
    ids=["default", "effort", "batch", "both"],
)
def test_effective_prompt_version_suffixes(monkeypatch, effort, batch, expected):
    if effort:
        monkeypatch.setenv(ENV, effort)
    monkeypatch.setattr(pc, "PAIRS_PER_CALL", batch)
    assert pc.effective_prompt_version() == expected


@pytest.mark.parametrize(
    ("effort", "batch", "expected"),
    [(None, 8, "pairs-v13"), ("low", 10, "pairs-v13+effort-low+batch-10")],
    ids=["default", "both"],
)
def test_relations_carry_effective_prompt_version(monkeypatch, effort, batch, expected):
    if effort:
        monkeypatch.setenv(ENV, effort)
    monkeypatch.setattr(pc, "PAIRS_PER_CALL", batch)
    result = build()
    assert result.mode == "llm"
    assert result.prompt_version == expected
    assert result.stats["prompt_version"] == expected
    assert result.relations and {r.prompt_version for r in result.relations} == {expected}


def test_rule_only_keeps_base_prompt_version(monkeypatch):
    monkeypatch.setenv(ENV, "low")
    result = build(llm=None)
    assert result.mode == "rule_only"
    assert result.prompt_version == pc.PROMPT_VERSION


# PR #125 review round 2 (Chuongpham2004): the light knob is validated like the pairs one.
# An invalid value used to reach NineRouterClient, which raised ValueError on every
# slot_context/alias call (LLM_NON_RETRYABLE) without any configuration warning.
@pytest.mark.parametrize("value", ["none", "xhigh"])
def test_light_effort_invalid_value_sends_nothing_with_one_warning(monkeypatch, caplog, value):
    light = "AI2_LLM_LIGHT_REASONING_EFFORT"
    monkeypatch.setenv(light, value)
    with caplog.at_level(logging.WARNING, logger="app.pipeline.runtime"):
        first = _sent("gpt-5.5", "slot_context")
        second = _sent("gpt-5.5", "alias")
    assert "reasoning_effort" not in first and "reasoning_effort" not in second
    assert len([r for r in caplog.records if light in r.getMessage()]) == 1


def test_light_effort_valid_value_still_sent(monkeypatch):
    monkeypatch.setenv("AI2_LLM_LIGHT_REASONING_EFFORT", "MINIMAL")
    assert _sent("gpt-5.5", "alias")["reasoning_effort"] == "minimal"
