import os

import pytest

from app.llm.client import NineRouterClient
from app.pipeline.idp import run_idp
from fixtures import envelope, mock_record


@pytest.mark.llm
@pytest.mark.live
def test_live_9router_json():
    client = NineRouterClient()
    if not client.configured():
        pytest.skip("AI2_LLM_API_KEY not set")
    data = client.complete_json(
        "Return JSON only.",
        'Return {"ok": true, "echo": "ping"} with those exact keys.',
    )
    assert "ok" in data or "echo" in data or "raw" in data


@pytest.mark.llm
@pytest.mark.live
def test_live_idp_with_llm():
    client = NineRouterClient()
    if not client.configured():
        pytest.skip("AI2_LLM_API_KEY not set")
    result = run_idp(mock_record(), envelope(), llm=client)
    assert result.contribution is not None
