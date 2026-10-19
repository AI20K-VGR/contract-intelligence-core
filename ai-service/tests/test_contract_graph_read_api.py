from __future__ import annotations

import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


def test_graph_page_is_not_ready_when_receipt_is_missing():
    from app.tools.contract_graph_read_model import graph_read_status

    assert graph_read_status(stage_status="COMPLETED", persistence_status=None, row_count=0) == "PERSISTENCE_UNKNOWN"


def test_graph_page_allows_verified_empty_graph_only_after_committed_stage():
    from app.tools.contract_graph_read_model import graph_read_status

    assert graph_read_status(stage_status="COMPLETED", persistence_status="COMMITTED", row_count=0) == "READY"
    assert graph_read_status(stage_status="SKIPPED", persistence_status="SKIPPED", row_count=0) == "SKIPPED"
    assert graph_read_status(stage_status="COMPLETED", persistence_status="FAILED", row_count=0) == "PERSIST_FAILED"
    assert graph_read_status(stage_status="SKIPPED", persistence_status="FAILED", row_count=0) == "PERSIST_FAILED"


def test_failed_builder_is_not_projected_as_skipped_or_ready():
    from app.tools.contract_graph_read_model import graph_read_status

    assert graph_read_status(stage_status="FAILED", persistence_status="SKIPPED", row_count=0) == "FAILED"
    assert graph_read_status(stage_status="FAILED", persistence_status="FAILED", row_count=0) == "PERSIST_FAILED"


@pytest.mark.parametrize("job_status", ["FAILED", "CANCELLED"])
def test_terminal_graph_job_is_not_reported_as_pending(job_status):
    from app.tools.contract_graph_read_model import graph_job_status

    assert graph_job_status(job_status) == "FAILED"


@pytest.mark.parametrize("job_status", ["QUEUED", "RUNNING"])
def test_nonterminal_graph_job_remains_pending(job_status):
    from app.tools.contract_graph_read_model import graph_job_status

    assert graph_job_status(job_status) == "PENDING"


def test_operation_projection_excludes_contract_text_and_citation_spans():
    from app.tools.contract_graph_read_model import project_operation_edge

    edge = {
        "tenant_id": "tenant-a", "dossier_id": "dossier-a", "job_id": "job-a",
        "source_snapshot_digest": "snapshot-a",
        "edge_id": "edge-1",
        "source_node_id": "annex-clause-1",
        "target_node_id": "body-clause-5",
        "op": "SUBSTITUTION",
        "target_address": "Điều 5",
        "review_state": "NEEDS_REVIEW",
        "source_citation_json": '{"citation_id":"c1","source_file_id":"annex-file","text_span":"private annex text","page":2}',
        "target_citation_json": '{"citation_id":"c2","source_file_id":"body-file","text_span":"private body text","page":4}',
        "new_text": "private replacement text",
        "scope_text": "private scope text",
        "digest": "d" * 64,
    }

    projected = project_operation_edge(edge)

    assert projected["source_citation_ref"] == "c1"
    assert projected["target_citation_ref"] == "c2"
    assert projected["source_document_id"] == "annex-file"
    assert projected["target_document_id"] == "body-file"
    assert projected["tenant_id"] == "tenant-a"
    assert projected["snapshot_digest"] == "snapshot-a"
    assert "text_span" not in repr(projected)
    assert "private" not in repr(projected)


def test_unknown_graph_kind_is_rejected():
    from app.tools.contract_graph_read_model import validate_graph_kind

    with pytest.raises(ValueError):
        validate_graph_kind("raw_contract_text")


def test_graph_cursor_is_kind_scoped():
    from app.tools.contract_graph_read_model import validate_graph_cursor

    assert validate_graph_cursor("cedge:" + "a" * 24, "operation")
    with pytest.raises(ValueError):
        validate_graph_cursor("cpair:" + "a" * 24, "operation")


def test_pair_projection_excludes_classifier_spans():
    from app.tools.contract_graph_read_model import project_pair_relation

    relation = {
        "tenant_id": "tenant-a", "dossier_id": "dossier-a", "job_id": "job-a",
        "source_snapshot_digest": "snapshot-a",
        "relation_id": "cpair:" + "a" * 24,
        "label": "CONFLICT",
        "directed": 0,
        "node_a_id": "clause-a",
        "node_b_id": "clause-b",
        "review_state": "NEEDS_REVIEW",
        "citation_a_json": '{"citation_id":"a","source_file_id":"file-a","text_span":"private left text"}',
        "citation_b_json": '{"citation_id":"b","source_file_id":"file-b","text_span":"private right text"}',
        "span_a": "private left span",
        "span_b": "private right span",
        "digest": "e" * 64,
    }

    projected = project_pair_relation(relation)

    assert projected["directed"] is False
    assert projected["source_citation_ref"] == "a"
    assert projected["target_citation_ref"] == "b"
    assert projected["source_document_id"] == "file-a"
    assert projected["target_document_id"] == "file-b"
    assert projected["job_id"] == "job-a"
    assert "private" not in repr(projected)


def test_signed_graph_read_returns_unavailable_when_postgres_is_not_configured(monkeypatch):
    from app.api.main import app
    from app.security.service_envelope import build_service_envelope

    monkeypatch.delenv("AI2_DATABASE_URL", raising=False)
    monkeypatch.setenv("AI2_SERVICE_HMAC_SECRET", "graph-read-test-secret")
    params = {"job_id": "job-1", "dossier_id": "dossier-1", "snapshot_digest": "a" * 64,
              "graph_kind": "operation", "cursor": None, "limit": 50}
    signed = build_service_envelope(
        params, secret="graph-read-test-secret", tenant_id="tenant-1", dossier_id="dossier-1",
        scopes=["ai2.graph.read"],
    )
    with TestClient(app) as client:
        response = client.get(
            "/internal/contract-graph/job-1",
            params={key: value for key, value in params.items() if value is not None and key != "job_id"},
            headers={"x-ai2-service-envelope": json.dumps(signed)},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "UNAVAILABLE"


def test_signed_graph_read_rejects_unscoped_service_envelope(monkeypatch):
    from app.api.main import app
    from app.security.service_envelope import build_service_envelope

    monkeypatch.setenv("AI2_SERVICE_HMAC_SECRET", "graph-read-test-secret")
    params = {"job_id": "job-1", "dossier_id": "dossier-1", "snapshot_digest": "a" * 64,
              "graph_kind": "operation", "cursor": None, "limit": 50}
    signed = build_service_envelope(
        params, secret="graph-read-test-secret", tenant_id="tenant-1", dossier_id="dossier-1",
    )
    with TestClient(app) as client:
        response = client.get(
            "/internal/contract-graph/job-1",
            params={key: value for key, value in params.items() if value is not None and key != "job_id"},
            headers={"x-ai2-service-envelope": json.dumps(signed)},
        )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "SERVICE_SCOPE_MISSING"


@pytest.mark.parametrize(
    ("job_status", "expected"),
    [("QUEUED", "PENDING"), ("RUNNING", "PENDING"), ("FAILED", "FAILED"), ("CANCELLED", "FAILED")],
)
def test_signed_graph_read_distinguishes_nonterminal_and_terminal_jobs(
    pg_url, monkeypatch, job_status, expected,
):
    from sqlalchemy import update

    from app.api import contract_graph_router
    from app.api.main import app
    from app.db.tables import jobs
    from app.security.service_envelope import build_service_envelope
    from app.tools.jobs import PostgresJobStore

    monkeypatch.setenv("AI2_SERVICE_HMAC_SECRET", "fixture-hmac-material-graph-read-01")
    store = PostgresJobStore(pg_url)
    job, _ = store.create_or_get(
        tenant_id="terminal-status-tenant", dossier_id=f"dossier-{job_status}",
        request_id=f"request-{job_status}", idempotency_key=f"idem-{job_status}",
        attempt=1, request={}, wire={},
    )
    with store.engine.begin() as cx:
        cx.execute(update(jobs).where(jobs.c.job_id == job["job_id"]).values(status=job_status))
    monkeypatch.setattr(contract_graph_router, "database_url", lambda: pg_url)
    monkeypatch.setattr(contract_graph_router, "get_engine", lambda: store.engine)
    monkeypatch.setattr(contract_graph_router, "ensure_database", lambda _engine: None)
    params = {
        "job_id": job["job_id"], "dossier_id": f"dossier-{job_status}",
        "snapshot_digest": "digest-a", "graph_kind": "operation", "cursor": None, "limit": 50,
    }
    signed = build_service_envelope(
        params, secret="fixture-hmac-material-graph-read-01", tenant_id="terminal-status-tenant",
        dossier_id=params["dossier_id"], scopes=["ai2.graph.read"],
    )
    with TestClient(app) as client:
        response = client.get(
            f"/internal/contract-graph/{job['job_id']}",
            params={key: value for key, value in params.items() if value is not None and key != "job_id"},
            headers={"x-ai2-service-envelope": json.dumps(signed)},
        )
    assert response.status_code == 200
    assert response.json()["status"] == expected
    assert response.json()["edges"] == []


def test_postgres_completion_records_verified_empty_and_failed_graph_writes(pg_url, monkeypatch):
    from sqlalchemy import select

    from app.db.tables import graph_write_receipts
    from app.tools import contract_edge_store
    from app.tools.jobs import PostgresJobStore
    from fixtures import envelope as make_envelope
    from fixtures.contract_graph_records import graph_record

    store = PostgresJobStore(pg_url)
    record = graph_record()
    record.dossier_id = "read-api-" + uuid4().hex
    env = make_envelope()
    env.auth.dossier_id = record.dossier_id
    record.contract_graph_ran = True
    record.pair_relations_ran = False
    record.contract_edges = []

    def finish(suffix: str) -> str:
        job, _ = store.create_or_get(
            tenant_id=record.tenant_id,
            dossier_id=record.dossier_id,
            request_id=suffix,
            idempotency_key=record.dossier_id + suffix,
            attempt=1,
            request={},
            wire={},
        )
        token = store.claim(job["job_id"], tenant_id=record.tenant_id, dossier_id=record.dossier_id)
        assert store.complete_with_snapshot(
            job["job_id"], tenant_id=record.tenant_id, dossier_id=record.dossier_id,
            worker_token=token, status="SUCCEEDED", wire={"status": "SUCCEEDED"},
            record=record, envelope=env,
        )
        return job["job_id"]

    empty_job_id = finish("empty")
    with store.engine.connect() as cx:
        empty_receipts = cx.execute(select(graph_write_receipts).where(
            graph_write_receipts.c.job_id == empty_job_id,
        )).mappings().all()
    by_kind = {row["graph_kind"]: row for row in empty_receipts}
    assert by_kind["operation"]["stage_status"] == "COMPLETED"
    assert by_kind["operation"]["write_status"] == "COMMITTED"
    assert by_kind["operation"]["row_count"] == 0
    assert by_kind["pair"]["write_status"] == "SKIPPED"

    record.contract_graph_stage_status = "FAILED"
    record.pair_relations_stage_status = "FAILED"
    record.contract_graph_ran = False
    record.pair_relations_ran = False
    failed_build_job_id = finish("builder-failed")
    with store.engine.connect() as cx:
        failed_build_receipts = cx.execute(select(graph_write_receipts).where(
            graph_write_receipts.c.job_id == failed_build_job_id,
        )).mappings().all()
    assert {row["graph_kind"]: row["stage_status"] for row in failed_build_receipts} == {
        "operation": "FAILED", "pair": "FAILED",
    }

    monkeypatch.setattr(contract_edge_store, "replace_contract_edges", lambda *_a, **_kw: (_ for _ in ()).throw(RuntimeError()))
    failed_job_id = finish("failed")
    with store.engine.connect() as cx:
        failed = cx.execute(select(graph_write_receipts).where(
            graph_write_receipts.c.job_id == failed_job_id,
            graph_write_receipts.c.graph_kind == "operation",
        )).mappings().one()
    assert failed["write_status"] == "FAILED"
    assert failed["error_code"] == "GRAPH_STORE_WRITE_FAILED"
    assert store.get(failed_job_id)["status"] == "SUCCEEDED"
