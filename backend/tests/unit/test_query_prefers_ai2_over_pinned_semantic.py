from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from contract_intelligence.schemas.queries import DossierQueryRequest
from contract_intelligence.shared.auth import AuthenticatedUser

dossier_api = importlib.import_module("contract_intelligence.api.v1.dossiers")


class _Session:
    async def refresh(self, _record: Any) -> None:
        return None

    async def commit(self) -> None:
        return None

    def add(self, _record: Any) -> None:
        return None


def _semantic(state: str, extension: dict | None) -> dict[str, Any]:
    return {
        "semantic_extension": extension,
        "state": state,
        "reason": None,
        "run_id": "run-a",
        "result_digest": "d",
        "typed_table_projections": {"payment_schedules": [], "boq_checks": []},
    }


async def _ask(monkeypatch, semantic: dict[str, Any]) -> tuple[Any, list]:
    calls: list = []
    dossier = SimpleNamespace(
        id="dossier-a",
        tenant_id="tenant-a",
        checksum=None,
        deleted_at=None,
        metadata_json={"created_by": "owner", "ai2_snapshot_digest": "digest-a"},
    )

    async def ai2(payload: dict[str, Any]) -> dict[str, Any]:
        calls.append(payload)
        return {"state": "ANSWERED", "answer": "Đợt 1 30%, đợt 2 40%", "citations": []}

    monkeypatch.setattr(dossier_api, "_semantic_result", AsyncMock(return_value=semantic))
    monkeypatch.setattr(dossier_api, "_ensure_current_semantic_run", AsyncMock())
    monkeypatch.setattr(dossier_api, "_acl_check_dossier_access", AsyncMock(return_value=dossier))
    monkeypatch.setattr(dossier_api, "enforce_query_limits", AsyncMock())
    monkeypatch.setattr(dossier_api, "query_ai2", ai2)
    monkeypatch.setattr(
        dossier_api, "save_query_trace", AsyncMock(return_value=SimpleNamespace(id="t"))
    )
    monkeypatch.setattr(dossier_api, "_dossier_document_ids", AsyncMock(return_value=set()))
    monkeypatch.setattr(dossier_api, "record_query_answer", lambda *_a: None)
    response = await dossier_api._run_dossier_query(
        endpoint="ask",
        dossier_id="dossier-a",
        body=DossierQueryRequest(query="Mỗi đợt bao nhiêu %?"),
        session=_Session(),
        user=AuthenticatedUser("owner", "tenant-a", "o@example.test", "O", "OPERATOR"),
    )
    return response, calls


@pytest.mark.asyncio
async def test_ask_with_a_persisted_semantic_result_is_answered_by_ai2(monkeypatch):
    # #121: the pinned-semantic path returned the first clauses verbatim and never used the LLM.
    response, calls = await _ask(monkeypatch, _semantic("NEEDS_REVIEW", {"frames": []}))
    assert len(calls) == 1 and response.answer == "Đợt 1 30%, đợt 2 40%"


@pytest.mark.asyncio
async def test_ask_while_the_current_result_is_not_ready_stays_blocked(monkeypatch):
    response, calls = await _ask(monkeypatch, _semantic("NOT_READY", None))
    assert calls == [] and response.state == "BLOCKED"


# PR #125 review (Chuongpham2004 #1): a semantic dossier used to keep only VALID frame
# citations; AI2 answers must pass the OCR citation guard before they are returned.
_GOOD = {
    "source_file_id": "doc-a",
    "text_span": "trong 30 ngày",
    "char_start": 10,
    "char_end": 23,
    "page": 1,
    "line_ids": ["doc-a:s1:p001:l001"],
}
_FORGED = {**_GOOD, "text_span": "trong 03 ngày"}


async def _ask_with_citations(monkeypatch, semantic, citations):
    from contract_intelligence.shared.ai.citation_guard import CitationGuardResult

    checked: list[str] = []

    async def verify(_session, *, document_id, citation):
        checked.append(citation.quote)
        ok = citation.quote == _GOOD["text_span"] and document_id == "doc-a"
        return CitationGuardResult(accepted=ok, quote=citation.quote, quote_sha256="")

    monkeypatch.setattr(dossier_api, "verify_citation", verify, raising=False)

    async def ai2(_payload):
        return {"state": "ANSWERED", "answer": "Thanh toán trong 30 ngày.", "citations": citations}

    monkeypatch.setattr(dossier_api, "_semantic_result", AsyncMock(return_value=semantic))
    monkeypatch.setattr(dossier_api, "_ensure_current_semantic_run", AsyncMock())
    dossier = SimpleNamespace(
        id="dossier-a",
        tenant_id="tenant-a",
        checksum=None,
        deleted_at=None,
        metadata_json={"created_by": "owner", "ai2_snapshot_digest": "digest-a"},
    )
    monkeypatch.setattr(dossier_api, "_acl_check_dossier_access", AsyncMock(return_value=dossier))
    monkeypatch.setattr(dossier_api, "enforce_query_limits", AsyncMock())
    monkeypatch.setattr(dossier_api, "query_ai2", ai2)
    monkeypatch.setattr(
        dossier_api, "save_query_trace", AsyncMock(return_value=SimpleNamespace(id="t"))
    )
    monkeypatch.setattr(dossier_api, "_dossier_document_ids", AsyncMock(return_value={"doc-a"}))
    monkeypatch.setattr(dossier_api, "record_query_answer", lambda *_a: None)
    response = await dossier_api._run_dossier_query(
        endpoint="query",
        dossier_id="dossier-a",
        body=DossierQueryRequest(query="Thời hạn thanh toán?"),
        session=_Session(),
        user=AuthenticatedUser("owner", "tenant-a", "o@example.test", "O", "OPERATOR"),
    )
    return response, checked


@pytest.mark.asyncio
async def test_semantic_dossier_answer_keeps_only_guard_verified_citations(monkeypatch):
    response, checked = await _ask_with_citations(
        monkeypatch, _semantic("NEEDS_REVIEW", {"frames": []}), [_GOOD]
    )
    assert checked == ["trong 30 ngày"]
    assert [c["text_span"] for c in response.citations] == ["trong 30 ngày"]
    assert response.answer == "Thanh toán trong 30 ngày."


@pytest.mark.asyncio
async def test_semantic_dossier_answer_with_a_forged_citation_is_withheld(monkeypatch):
    response, checked = await _ask_with_citations(
        monkeypatch, _semantic("NEEDS_REVIEW", {"frames": []}), [_GOOD, _FORGED]
    )
    assert checked == ["trong 30 ngày", "trong 03 ngày"]
    assert [c["text_span"] for c in response.citations] == ["trong 30 ngày"]
    assert response.state == "BLOCKED" and not response.answer
    assert response.reasoning_trace[0]["code"] == "BACKEND_CITATION_UNVERIFIED"
