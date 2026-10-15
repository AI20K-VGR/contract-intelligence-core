"""GPT-5 takes max_completion_tokens and no temperature, in inference and in the health probe."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any

import pytest

from app.llm.client import NineRouterClient, llm_status

GPT5 = ["gpt-5.5", "openai/gpt-5.5"]
OTHER = "gpt-4o-mini"


class _FakeOpenAI:
    """Stands in for the OpenAI SDK client and records every request's kwargs."""

    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.error = error
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def with_options(self, **_: Any) -> _FakeOpenAI:
        return self

    def _create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))],
            model=kwargs["model"],
            usage=None,
        )


def _client(model: str, *, strong_model: str | None = None, error: Exception | None = None):
    client = NineRouterClient(api_key="sk-test", model=model, strong_model=strong_model)
    fake = _FakeOpenAI(error)
    client._client = fake  # type: ignore[assignment]
    return client, fake


@pytest.mark.parametrize("model", GPT5)
def test_gpt5_inference_sends_max_completion_tokens_and_no_temperature(model: str) -> None:
    client, fake = _client(model)

    client.complete_json("system", "user", max_output_tokens=256)

    sent = fake.calls[0]
    assert sent["model"] == model
    assert sent["max_completion_tokens"] == 256
    assert "max_tokens" not in sent
    assert "temperature" not in sent


def test_other_models_keep_max_tokens_and_temperature_zero() -> None:
    client, fake = _client(OTHER)

    client.complete_json("system", "user", max_output_tokens=256)

    sent = fake.calls[0]
    assert sent["max_tokens"] == 256
    assert sent["temperature"] == 0
    assert "max_completion_tokens" not in sent


@pytest.mark.parametrize("model", [*GPT5, OTHER])
def test_no_output_cap_is_sent_when_none_is_asked(model: str) -> None:
    client, fake = _client(model)

    client.complete_json("system", "user")

    assert not {"max_tokens", "max_completion_tokens"} & fake.calls[0].keys()


def test_the_rule_follows_the_model_actually_called() -> None:
    client, fake = _client(OTHER, strong_model="openai/gpt-5.5")

    client.complete_json("system", "user", strong=True, max_output_tokens=64)

    sent = fake.calls[0]
    assert sent["model"] == "openai/gpt-5.5"
    assert sent["max_completion_tokens"] == 64
    assert "temperature" not in sent


@pytest.mark.parametrize("model", GPT5)
def test_gpt5_health_probe_is_ready_with_gpt5_parameters(model: str) -> None:
    client, fake = _client(model)

    assert llm_status(client) == "ready"

    sent = fake.calls[0]
    assert sent["max_completion_tokens"] == 1
    assert "max_tokens" not in sent
    assert "temperature" not in sent


def test_other_model_health_probe_keeps_max_tokens_and_temperature() -> None:
    client, fake = _client(OTHER)

    assert llm_status(client) == "ready"

    sent = fake.calls[0]
    assert sent["max_tokens"] == 1
    assert sent["temperature"] == 0
    assert "max_completion_tokens" not in sent


class _ProviderError(Exception):
    """Like openai.APIStatusError: a status code, and a message that may echo secrets."""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


def test_a_failed_probe_logs_model_status_and_type_but_no_message_or_key(
    caplog: pytest.LogCaptureFixture,
) -> None:
    error = _ProviderError("Unsupported parameter 'max_tokens' for key sk-test-SECRET", 400)
    client, _ = _client("openai/gpt-5.5", error=error)
    client.api_key = "sk-test-SECRET"

    with caplog.at_level(logging.WARNING, logger="app.llm.client"):
        assert llm_status(client) == "unreachable"

    logged = caplog.text
    assert "openai/gpt-5.5" in logged
    assert "400" in logged
    assert "_ProviderError" in logged
    assert "SECRET" not in logged
    assert "Unsupported parameter" not in logged
