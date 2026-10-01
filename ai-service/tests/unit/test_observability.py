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
