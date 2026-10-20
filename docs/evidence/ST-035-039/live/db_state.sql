-- Server-side state of the live evidence dossier. Run with: psql -v dossier=<id> -f db_state.sql
\pset pager off
\echo '== ST-035: dossier + documents + job (one transaction at upload) =='
SELECT id, tenant_id, status, is_locked, is_approved, has_conflicts, deleted_at, created_at
FROM dossier WHERE id = :'dossier';
SELECT id, role, filename, file_size_bytes, left(sha256, 16) AS sha256_16, blob_uri
FROM document WHERE dossier_id = :'dossier' ORDER BY order_index;
SELECT id, status, current_run_id, error_code, created_at, updated_at
FROM job WHERE dossier_id = :'dossier';

\echo '== ST-036: pipeline run + steps (one run, AI1 via Kafka) =='
SELECT id, status, pipeline_version, error_code, created_at, finished_at
FROM pipeline_run WHERE dossier_id = :'dossier' ORDER BY created_at;
SELECT s.run_id, s.step, s.status, s.attempt, s.document_id, s.duration_ms
FROM pipeline_step s JOIN pipeline_run r ON r.id = s.run_id
WHERE r.dossier_id = :'dossier' ORDER BY s.step, s.document_id;

\echo '== ST-036/037/038: audit_event timeline for the dossier =='
SELECT occurred_at, actor_id, action, entity_type, from_state, to_state, left(detail, 160) AS detail
FROM audit_event WHERE dossier_id = :'dossier' ORDER BY occurred_at;

\echo '== ST-037: facts persisted from AI2 (HTTP) =='
SELECT d.role, f.raw_text, left(f.fact_type, 70) AS context, f.extractor
FROM fact f JOIN document d ON d.id = f.document_id
WHERE d.dossier_id = :'dossier' ORDER BY d.order_index, f.created_at;
SELECT count(*) AS findings FROM finding WHERE dossier_id = :'dossier';

\echo '== ST-038: review items + append-only review_action =='
SELECT id, target_type, status, version, created_at, updated_at
FROM review_item WHERE dossier_id = :'dossier' ORDER BY created_at;
SELECT a.review_item_id, a.action, a.base_version, a.reviewer_id, a.created_at
FROM review_action a JOIN review_item i ON i.id = a.review_item_id
WHERE i.dossier_id = :'dossier' ORDER BY a.created_at;

\echo '== ST-039: query_trace (actor / snapshot / citations / ACL decision) =='
SELECT endpoint, actor_id, state, acl_decision, dropped_citations, snapshot_version,
       left(snapshot_digest, 16) AS digest_16, query_contract_version, error_code, latency_ms,
       left(citations, 120) AS citations
FROM query_trace WHERE dossier_id = :'dossier' ORDER BY created_at;

\echo '== Append-only enforcement on the live DB (each statement must fail) =='
\set ON_ERROR_STOP off
BEGIN; UPDATE audit_event SET actor_id = 'tamper' WHERE dossier_id = :'dossier'; ROLLBACK;
BEGIN; DELETE FROM query_trace WHERE dossier_id = :'dossier'; ROLLBACK;
BEGIN; UPDATE review_action SET action = 'confirm' WHERE review_item_id IN
    (SELECT id FROM review_item WHERE dossier_id = :'dossier'); ROLLBACK;

\echo '== Schema: migration head + review_action unique index =='
SELECT version_num FROM alembic_version;
SELECT indexname, indexdef FROM pg_indexes WHERE indexname = 'uq_review_action_item_base_version';
