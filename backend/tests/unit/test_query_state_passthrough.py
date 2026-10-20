from __future__ import annotations

import pytest

from contract_intelligence.contract.interfaces.api.routers.contract_router import (
    DossierSearchDTO,
    _search_dto_from_ai2,
)


@pytest.mark.parametrize("state", ["PASS", "NEEDS_REVIEW", "INSUFFICIENT_EVIDENCE", "BLOCKED"])
def test_backend_query_dto_preserves_server_state_and_trace(state: str) -> None:
    dto = _search_dto_from_ai2(
        {
            "query": "payment",
            "state": state,
            "answer": "HTTP success is not semantic success",
            "connected": True,
            "used_llm": False,
            "citations": [{"node_id": "n1", "text_span": "payment"}],
            "retrieval_layer": {"selected": "LEXICAL"},
            "reasoning_trace": [{"code": "LEXICAL_RETRIEVAL"}],
        },
        fallback_query="payment",
    )

    assert isinstance(dto, DossierSearchDTO)
    assert dto.state == state
    assert dto.used_llm is False
    assert dto.retrieval_layer["selected"] == "LEXICAL"
    assert dto.reasoning_trace[0]["code"] == "LEXICAL_RETRIEVAL"


def test_backend_query_dto_defaults_to_safe_state_without_server_state() -> None:
    dto = _search_dto_from_ai2(
        {
            "query": "payment",
            "connected": True,
            "answer": "looks answered",
            "hits": [{"text": "payment"}],
        },
        fallback_query="payment",
    )

    assert dto.state == "INSUFFICIENT_EVIDENCE"
    assert dto.connected is True
