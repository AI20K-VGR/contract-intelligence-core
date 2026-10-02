from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Column,
    DefaultClause,
    Integer,
    LargeBinary,
    MetaData,
    Table,
    Text,
    UniqueConstraint,
)

metadata = MetaData(schema="ai2")


def columns(spec: str):
    """Compact declarations; '?' marks nullable fields, '*' a primary key."""
    result = []
    for field in spec.split():
        name, kind = field.split(":")
        nullable, primary = "?" in kind, "*" in kind
        types = {"s": Text, "i": Integer, "n": BigInteger, "b": LargeBinary}
        result.append(Column(name, types[kind.replace("?", "").replace("*", "")],
                             nullable=nullable, primary_key=primary))
    return result


jobs = Table("jobs", metadata, *columns(
    "job_id:s* tenant_id:s dossier_id:s request_id:s idempotency_key:s attempt:i status:s "
    "request_json:s wire_json:s result_json:s? request_fingerprint:s? worker_token:s? lease_until_ms:n? created_ms:n updated_ms:n"),
    UniqueConstraint("tenant_id", "idempotency_key", "attempt", name="uq_ai2_job_idempotency"))
service_nonces = Table("service_nonces", metadata, *columns(
    "tenant_id:s* nonce:s* payload_fingerprint:s job_id:s created_ms:n"))
query_snapshots = Table("dossier_query_snapshots", metadata, *columns(
    "tenant_id:s* dossier_id:s* snapshot_digest:s payload:s updated_ms:n"))
sessions = Table("sessions", metadata, *columns("session_id:s* payload:s updated_ms:n"))
session_blobs = Table("session_blobs", metadata, *columns("session_id:s* file_id:s* content:b"))
vector_segments = Table("vector_segments", metadata, *columns(
    "segment_id:s* snapshot_digest:s node_id:s source_file_id:s? source_role:s? page_revision_id:s "
    "char_start:i char_end:i text_digest:s text:s embedding_version:s embedding_model:s dimensions:i vector_json:s"))
durable_runs = Table("durable_runs", metadata, *columns(
    "run_id:s* tenant_id:s generation_id:s snapshot_json:s snapshot_digest:s snapshot_sequence:i "
    "event_sequence:i state_version:i created_ms:n updated_ms:n lease_owner:s? lease_token:s? lease_until_ms:n?"))
durable_checkpoints = Table("durable_checkpoints", metadata, *columns(
    "run_id:s* checkpoint_id:s* tenant_id:s sequence:i state_json:s state_digest:s created_ms:n updated_ms:n"))
durable_events = Table("durable_events", metadata, *columns(
    "event_id:s* run_id:s tenant_id:s event_type:s schema_version:s sequence:i state_version:i generation_id:s "
    "created_ms:n actor_id:s? correlation_id:s causation_id:s? payload_json:s evidence_refs_json:s digest:s"),
    UniqueConstraint("run_id", "sequence", name="uq_ai2_event_sequence"))
durable_audit = Table("durable_audit", metadata, *columns(
    "audit_id:s* run_id:s tenant_id:s actor_id:s action:s details_json:s created_ms:n previous_digest:s? digest:s"))
durable_outbox = Table("durable_outbox", metadata, *columns(
    "event_id:s* run_id:s payload_json:s status:s attempts:i lease_token:s? lease_until_ms:n? available_after_ms:n published_ms:n?"))

# Match the existing store's omitted insertion fields.
durable_outbox.c.attempts.server_default = DefaultClause("0")
durable_runs.c.event_sequence.server_default = DefaultClause("0")
