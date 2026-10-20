from types import SimpleNamespace

from contract_ocr.infrastructure.observability import (
    observation,
    reset_langfuse_for_tests,
    response_usage,
)


def test_observation_is_noop_without_credentials(monkeypatch):
    for name in (
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
        "LANGFUSE_BASE_URL",
        "LANGFUSE_HOST",
    ):
        monkeypatch.delenv(name, raising=False)
    reset_langfuse_for_tests()

    with observation("test-span", input={"safe": True}) as span:
        assert span is None

    reset_langfuse_for_tests()


def test_response_usage_normalizes_openai_tokens():
    response = SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=11, completion_tokens=7, total_tokens=18)
    )

    assert response_usage(response) == {"input": 11, "output": 7, "total": 18}


def test_response_usage_normalizes_mistral_ocr_counters():
    response = SimpleNamespace(
        usage_info=SimpleNamespace(pages_processed=2, doc_size_bytes=1234)
    )

    assert response_usage(response) == {"pages_processed": 2, "document_size_bytes": 1234}


def test_response_usage_reads_openai_prompt_cache_counters():
    from openai.types.completion_usage import CompletionUsage, PromptTokensDetails

    response = SimpleNamespace(
        usage=CompletionUsage(
            prompt_tokens=10_000,
            completion_tokens=500,
            total_tokens=10_500,
            prompt_tokens_details=PromptTokensDetails(cached_tokens=8_000, cache_write_tokens=0),
        )
    )

    assert response_usage(response) == {
        "input": 10_000,
        "output": 500,
        "total": 10_500,
        "input_cached": 8_000,
    }


def test_response_usage_reads_responses_api_cache_counters_from_dicts():
    response = SimpleNamespace(
        usage={
            "input_tokens": 3_000,
            "output_tokens": 100,
            "total_tokens": 3_100,
            "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 2_000},
        }
    )

    assert response_usage(response)["input_cache_write"] == 2_000
    assert "input_cached" not in response_usage(response)
