from __future__ import annotations

import json
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from contract_intelligence.infrastructure import ai_adapters


def test_graph_adapter_preserves_terminal_failed_status():
    page = ai_adapters._validate_ai2_graph_page(
        {
            "status": "FAILED",
            "graph_kind": "pair",
            "snapshot_digest": "digest-a",
            "edges": [],
            "total_count": 0,
            "has_more": False,
            "next_cursor": None,
        },
        tenant_id="tenant-a",
        dossier_id="dossier-a",
        job_id="job-a",
        snapshot_digest="digest-a",
        graph_kind="pair",
        limit=50,
    )
    assert page["status"] == "FAILED"


@pytest.mark.parametrize("job_status", [[], {}])
def test_trace_adapter_rejects_non_string_job_status_cleanly(job_status):
    with pytest.raises(ai_adapters.AiAdapterError, match="unknown job status"):
        ai_adapters._validate_ai2_trace(
            {
                "schema_version": "ai2.processing-trace.v1",
                "trace_status": "AVAILABLE",
                "status": "COMPLETE",
                "job_status": job_status,
                "snapshot_digest": "digest-a",
                "stages": [],
            },
            snapshot_digest="digest-a",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("headers", "body", "error"),
    [
        ({"content-length": "99"}, b"{}", "size limit"),
        ({}, b"12345", "size limit"),
        ({"content-length": "not-a-number"}, b"{}", "malformed Content-Length"),
    ],
)
async def test_bounded_get_rejects_oversized_or_malformed_response(
    monkeypatch, headers, body, error
):
    original_client = httpx.AsyncClient

    def client_factory(*, timeout):
        transport = httpx.MockTransport(
            lambda _request: httpx.Response(200, headers=headers, content=body)
        )
        return original_client(timeout=timeout, transport=transport)

    monkeypatch.setattr(ai_adapters.httpx, "AsyncClient", client_factory)

    with pytest.raises(ai_adapters.AiAdapterError, match=error):
        await ai_adapters._get_json_bounded(
            "http://ai2.test/read", headers=None, service="ai2.test", max_response_bytes=4
        )


@pytest.mark.asyncio
async def test_graph_adapter_signs_scope_and_accepts_only_bounded_projection(monkeypatch):
    calls = []
    payload = {
        "status": "READY",
        "graph_kind": "pair",
        "tenant_id": "tenant-a",
        "dossier_id": "dossier-a",
        "job_id": "job-a",
        "snapshot_digest": "digest-a",
        "edges": [
            {
                "tenant_id": "tenant-a",
                "dossier_id": "dossier-a",
                "job_id": "job-a",
                "snapshot_digest": "digest-a",
                "id": "pair-a",
                "kind": "PAIR",
                "label": "REFERENCE",
                "directed": False,
                "source_node_id": "node-a",
                "target_node_id": "node-b",
                "source_document_id": "file-a",
                "target_document_id": "file-b",
                "review_state": "NEEDS_REVIEW",
                "source_citation_ref": "cite:a",
                "target_citation_ref": "cite:b",
                "digest": "digest-a",
            }
        ],
        "total_count": 1,
        "has_more": False,
        "next_cursor": None,
    }

    async def fake_get(url, *, headers=None, service, max_response_bytes):
        calls.append((url, json.loads(headers["X-AI2-Service-Envelope"]), service))
        assert max_response_bytes == 512_000
        return payload

    monkeypatch.setattr(ai_adapters, "_get_json_bounded", fake_get)
    monkeypatch.setattr(ai_adapters, "_service_envelope", lambda data, **kw: {"signed": True, **kw})

    result = await ai_adapters.read_ai2_contract_graph(
        "job-a",
        dossier_id="dossier-a",
        snapshot_digest="digest-a",
        graph_kind="pair",
        tenant_id="tenant-a",
        actor_id="actor-a",
        cursor=None,
        limit=50,
    )

    url, envelope, service = calls[0]
    assert urlsplit(url).path.endswith("/internal/contract-graph/job-a")
    assert parse_qs(urlsplit(url).query)["snapshot_digest"] == ["digest-a"]
    assert envelope["scopes"] == ["ai2.graph.read"]
    assert envelope["tenant_id"] == "tenant-a"
    assert service == "ai2.contract_graph.read"
    assert result["edges"][0]["label"] == "REFERENCE"
    assert result["edges"][0]["source_document_id"] == "file-a"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change",
    [
        {"tenant_id": "tenant-other"},
        {"job_id": "job-other"},
        {"snapshot_digest": "digest-old"},
        {"edges": [{"id": "pair-a", "text_span": "must not cross"}]},
        {
            "edges": [
                {
                    "tenant_id": "tenant-a",
                    "dossier_id": "dossier-a",
                    "job_id": "job-a",
                    "snapshot_digest": "digest-a",
                    "id": "pair-a",
                    "kind": "PAIR",
                    "label": "REFERENCE",
                    "directed": False,
                    "source_node_id": "node-a",
                    "target_node_id": "node-b",
                    "source_document_id": 42,
                    "review_state": "NEEDS_REVIEW",
                    "source_citation_ref": "cite:a",
                    "target_citation_ref": "cite:b",
                    "digest": "edge-digest",
                }
            ]
        },
        {
            "edges": [
                {
                    "tenant_id": "tenant-other",
                    "dossier_id": "dossier-a",
                    "job_id": "job-a",
                    "snapshot_digest": "digest-a",
                    "id": "pair-a",
                    "kind": "PAIR",
                    "label": "REFERENCE",
                    "directed": False,
                    "source_node_id": "node-a",
                    "target_node_id": "node-b",
                    "review_state": "NEEDS_REVIEW",
                    "source_citation_ref": "cite:a",
                    "target_citation_ref": "cite:b",
                    "digest": "edge-digest",
                }
            ]
        },
        {
            "edges": [
                {
                    "tenant_id": "tenant-a",
                    "dossier_id": "dossier-a",
                    "job_id": "job-a",
                    "snapshot_digest": "digest-a",
                    "id": "pair-a",
                    "kind": "PAIR",
                    "label": "REFERENCE",
                    "directed": False,
                    "source_node_id": "node-a",
                    "target_node_id": "node-b",
                    "source_document_id": "file-a",
                    "review_state": "NEEDS_REVIEW",
                    "source_citation_ref": "cite:a",
                    "target_citation_ref": "cite:b",
                    "digest": "edge-digest",
                }
            ]
        },
        {"status": "MAGIC_SUCCESS"},
    ],
)
async def test_graph_adapter_fails_closed_on_wrong_scope_or_unexpected_fields(monkeypatch, change):
    payload = {
        "status": "READY",
        "graph_kind": "pair",
        "tenant_id": "tenant-a",
        "dossier_id": "dossier-a",
        "job_id": "job-a",
        "snapshot_digest": "digest-a",
        "edges": [
            {
                "tenant_id": "tenant-a",
                "dossier_id": "dossier-a",
                "job_id": "job-a",
                "snapshot_digest": "digest-a",
                "id": "pair-a",
                "kind": "PAIR",
                "label": "REFERENCE",
                "directed": False,
                "source_node_id": "node-a",
                "target_node_id": "node-b",
                "review_state": "NEEDS_REVIEW",
                "source_citation_ref": "cite:a",
                "target_citation_ref": "cite:b",
                "digest": "digest-a",
            }
        ],
        "total_count": 1,
        "has_more": False,
        "next_cursor": None,
    }
    payload.update(change)
    monkeypatch.setattr(ai_adapters, "_get_json_bounded", lambda *a, **k: _resolved(payload))
    monkeypatch.setattr(ai_adapters, "_service_envelope", lambda *_a, **_k: {})

    with pytest.raises(ai_adapters.AiAdapterError):
        await ai_adapters.read_ai2_contract_graph(
            "job-a",
            dossier_id="dossier-a",
            snapshot_digest="digest-a",
            graph_kind="pair",
            tenant_id="tenant-a",
            actor_id="actor-a",
            cursor=None,
            limit=50,
        )


async def _resolved(value):
    return value


@pytest.mark.asyncio
async def test_trace_adapter_rejects_unexpected_raw_text(monkeypatch):
    payload = {
        "schema_version": "ai2.processing-trace.v1",
        "trace_status": "AVAILABLE",
        "status": "COMPLETE",
        "execution_id": "exec-a",
        "snapshot_digest": "digest-a",
        "stages": [
            {
                "stage_id": "contract_graph_operation",
                "status": "COMPLETED",
                "started_ms": 1,
                "duration_ms": 2,
                "item_count": 1,
                "reason_code": None,
            }
        ],
        "contract_text": "secret",
    }
    monkeypatch.setattr(ai_adapters, "_get_json_bounded", lambda *a, **k: _resolved(payload))
    monkeypatch.setattr(ai_adapters, "_service_envelope", lambda *_a, **_k: {})

    with pytest.raises(ai_adapters.AiAdapterError):
        await ai_adapters.read_ai2_processing_trace(
            "job-a",
            dossier_id="dossier-a",
            snapshot_digest="digest-a",
            tenant_id="tenant-a",
            actor_id="actor-a",
        )


def test_trace_projection_keeps_failure_outcome_and_job_status():
    trace = ai_adapters._validate_ai2_trace(
        {
            "schema_version": "ai2.processing-trace.v1",
            "trace_status": "AVAILABLE",
            "status": "COMPLETE",
            "job_status": "CANCELLED",
            "snapshot_digest": "digest-a",
            "stages": [],
        },
        snapshot_digest="digest-a",
    )
    assert trace["status"] == "COMPLETE"
    assert trace["job_status"] == "CANCELLED"


class _StopAfterUrl(Exception):
    pass


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["graph", "evidence", "trace"])
async def test_job_id_is_percent_encoded_in_ai2_path(monkeypatch, kind):
    urls: list[str] = []

    async def fake_get(url, *, headers=None, service, max_response_bytes):
        urls.append(url)
        raise _StopAfterUrl

    monkeypatch.setattr(ai_adapters, "_get_json_bounded", fake_get)
    monkeypatch.setattr(ai_adapters, "_service_envelope", lambda data, **kw: {"signed": True})
    common = {
        "dossier_id": "dossier-a",
        "snapshot_digest": "digest-a",
        "tenant_id": "tenant-a",
        "actor_id": "actor-a",
    }
    hostile = "../admin?x=1#frag"

    with pytest.raises(_StopAfterUrl):
        if kind == "graph":
            await ai_adapters.read_ai2_contract_graph(
                hostile, graph_kind="pair", cursor=None, limit=50, **common
            )
        elif kind == "evidence":
            await ai_adapters.read_ai2_contract_graph_evidence(
                hostile, graph_kind="pair", node_id="n", citation_ref="c", **common
            )
        else:
            await ai_adapters.read_ai2_processing_trace(hostile, **common)

    parts = urlsplit(urls[0])
    assert "%2E%2E" in parts.path or "..%2Fadmin" in parts.path or "%2F" in parts.path
    assert "/admin" not in parts.path
    assert "?" not in parts.path and "#" not in parts.path
