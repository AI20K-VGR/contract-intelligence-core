"""GPT cost attached to Langfuse cost_details and the Prometheus cost counter."""

import pytest

from contract_ocr.infrastructure.ocr.openai_vision_ocr import _cost_details

MODEL = "gpt-5.6-terra"  # $2.00 input, $0.20 cached, $2.50 cache write, $12.00 output / 1M


def test_uncached_call_is_billed_at_input_and_output_rates():
    cost = _cost_details(MODEL, {"input": 10_000, "output": 500})

    assert cost["input"] == pytest.approx(0.02)
    assert cost["output"] == pytest.approx(0.006)
    assert cost["total"] == pytest.approx(0.026)


def test_cached_prompt_tokens_are_billed_at_the_cached_rate():
    # 8,000 of the 10,000 prompt tokens were read from the prompt cache.
    cost = _cost_details(MODEL, {"input": 10_000, "input_cached": 8_000, "output": 500})

    assert cost["input"] == pytest.approx(2_000 * 2.00e-6)
    assert cost["input_cached"] == pytest.approx(8_000 * 0.20e-6)
    assert cost["total"] == pytest.approx(0.004 + 0.0016 + 0.006)


def test_cache_writes_are_billed_above_the_input_rate():
    cost = _cost_details(MODEL, {"input": 3_000, "input_cache_write": 2_000, "output": 0})

    assert cost["input"] == pytest.approx(1_000 * 2.00e-6)
    assert cost["input_cache_write"] == pytest.approx(2_000 * 2.50e-6)
    assert cost["total"] == pytest.approx(0.002 + 0.005)


def test_unknown_model_or_missing_usage_has_no_cost():
    assert _cost_details("gpt-unknown", {"input": 1, "output": 1}) is None
    assert _cost_details(MODEL, None) is None
