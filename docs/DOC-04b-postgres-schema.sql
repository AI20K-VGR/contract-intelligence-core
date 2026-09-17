-- =============================================================================
-- DOC-04b · PostgreSQL Schema for Contract Intelligence
-- =============================================================================
-- Phiên bản: v1.0 · 2026-09-17 · Đã chốt sau P0-05 optimistic concurrency + 2 concern
-- Tài liệu tham chiếu:
--   - docs/DOC-04-architecture.md (kiến trúc)
--   - backend/CONTEXT.md mục 5 (quyết định & ERD)
--   - docs/DOC-05-api-spec.yaml (API dùng schema này)
--
-- Migration Alembic V1 ban đầu sẽ sinh từ file này.
-- Trước khi chạy: tạo database `ci` và user `ci` riêng cho ứng dụng.
--
-- Nguyên tắc:
--   1. Bảng kết quả máy + audit chỉ INSERT (trigger forbid_mutation)
--   2. Optimistic concurrency: review_item.version, client echo base_version
--   3. Ngày hiệu lực: denormalize trên document, cập nhật ở S7
--   4. ID: TEXT có tiền tố (dos_, doc_, pg_, run_, ln_, cit_, fct_, fnd_, ri_, ra_)
-- =============================================================================

BEGIN;

-- ===========================================================================
-- §1. EXTENSIONS
-- ===========================================================================
-- uuid-ossp có thể cần cho gen_random_uuid() trong một số flow khởi tạo
-- ứng dụng; ULID sẽ do app sinh (lib `python-ulid` hoặc `ulid-py`)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";


-- ===========================================================================
-- §2. TÀI KHOẢN & PHÂN QUYỀN
-- ===========================================================================
CREATE TABLE app_user (
    id            TEXT PRIMARY KEY,                            -- prefix "usr_"
    display_name  TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('operator', 'reviewer', 'admin')),
    password_hash TEXT NOT NULL,                               -- argon2
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ===========================================================================
-- §3. ĐIỀU PHỐI BATCH & DOSSIER
-- ===========================================================================
CREATE TABLE batch (
    id          TEXT PRIMARY KEY,                              -- prefix "btc_"
    name        TEXT NOT NULL,
    auto_paused BOOLEAN NOT NULL DEFAULT false,
    created_by  TEXT NOT NULL REFERENCES app_user(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE dossier (
    id            TEXT PRIMARY KEY,                            -- prefix "dos_"
    name          TEXT NOT NULL,
    batch_id      TEXT REFERENCES batch(id) ON DELETE SET NULL,
    has_conflicts BOOLEAN NOT NULL DEFAULT false,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE document (
    id             TEXT PRIMARY KEY,                           -- prefix "doc_"
    dossier_id     TEXT NOT NULL REFERENCES dossier(id) ON DELETE CASCADE,
    role           TEXT NOT NULL CHECK (role IN ('contract', 'annex')),
    order_index    INT NOT NULL DEFAULT 0,
    filename       TEXT NOT NULL,
    sha256         TEXT NOT NULL,
    blob_uri       TEXT NOT NULL,
    page_count     INT NOT NULL DEFAULT 0,
    lang_detected  TEXT DEFAULT 'vi',
    signing_date   DATE,                                       -- FIX concern 1: denormalized
    effective_date DATE,                                       -- FIX concern 1: denormalized
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ===========================================================================
-- §4. HẠ TẦNG PIPELINE & TASK QUEUE
-- ===========================================================================
CREATE TABLE job (
    id             TEXT PRIMARY KEY,                           -- prefix "job_"
    dossier_id     TEXT NOT NULL REFERENCES dossier(id) ON DELETE CASCADE,
    batch_id       TEXT REFERENCES batch(id) ON DELETE SET NULL,
    status         TEXT NOT NULL CHECK (status IN (
                       'uploaded', 'processing', 'extracted',
                       'pending_review', 'reviewed', 'approved', 'failed'
                   )),
    has_conflicts  BOOLEAN NOT NULL DEFAULT false,
    current_run_id TEXT,                                       -- FK added after pipeline_run
    error_code     TEXT,
    error_detail   JSONB,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE pipeline_run (
    id                     TEXT PRIMARY KEY,                   -- prefix "run_"
    job_id                 TEXT NOT NULL REFERENCES job(id) ON DELETE CASCADE,
    dossier_id             TEXT NOT NULL REFERENCES dossier(id) ON DELETE CASCADE,
    status                 TEXT NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
    config_snapshot        JSONB NOT NULL,
    pipeline_version       TEXT NOT NULL,
    git_sha                TEXT NOT NULL,
    trace_id               TEXT,
    requested_by_pseudo_id TEXT,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at            TIMESTAMPTZ
);

-- FK trễ từ job.current_run_id → pipeline_run.id
ALTER TABLE job ADD CONSTRAINT fk_job_current_run
    FOREIGN KEY (current_run_id) REFERENCES pipeline_run(id) ON DELETE SET NULL;

CREATE TABLE job_step (
    id          BIGSERIAL PRIMARY KEY,
    run_id      TEXT NOT NULL REFERENCES pipeline_run(id) ON DELETE CASCADE,
    document_id TEXT REFERENCES document(id) ON DELETE CASCADE,
    step        TEXT NOT NULL,
    status      TEXT NOT NULL CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'retrying')),
    attempt     INT NOT NULL DEFAULT 1,
    pages       INT DEFAULT 0,
    duration_ms INT,
    error_code  TEXT,
    metrics     JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_job_step_checkpoint UNIQUE (run_id, document_id, step)
);

CREATE TABLE task (
    id           BIGSERIAL PRIMARY KEY,
    kind         TEXT NOT NULL,
    job_id       TEXT NOT NULL REFERENCES job(id) ON DELETE CASCADE,
    batch_id     TEXT REFERENCES batch(id) ON DELETE SET NULL,
    payload      JSONB NOT NULL DEFAULT '{}',
    traceparent  TEXT,
    status       TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'dead')),
    priority     INT NOT NULL DEFAULT 100,
    attempts     INT NOT NULL DEFAULT 0,
    max_attempts INT NOT NULL DEFAULT 3,
    run_after    TIMESTAMPTZ NOT NULL DEFAULT now(),
    locked_by    TEXT,
    locked_at    TIMESTAMPTZ,
    heartbeat_at TIMESTAMPTZ,
    last_error   JSONB,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ===========================================================================
-- §5. DỮ LIỆU CẤP TRANG VÀ KẾT QUẢ MÁY (PHẦN LỚN IMMUTABLE)
-- ===========================================================================
CREATE TABLE page (
    id          TEXT PRIMARY KEY,                              -- prefix "pg_"
    document_id TEXT NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    page_no     INT NOT NULL,
    kind        TEXT NOT NULL CHECK (kind IN ('native', 'scanned', 'hybrid')),
    features    JSONB DEFAULT '{}',
    width_pt    REAL NOT NULL,
    height_pt   REAL NOT NULL,
    rotation    INT NOT NULL DEFAULT 0,
    transform   JSONB,
    render_uri  TEXT NOT NULL,
    preview_uri TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_document_page UNIQUE (document_id, page_no)
);

CREATE TABLE document_text (
    id            TEXT PRIMARY KEY,
    document_id   TEXT NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    run_id        TEXT NOT NULL REFERENCES pipeline_run(id) ON DELETE CASCADE,
    text          TEXT NOT NULL,
    normalization TEXT NOT NULL DEFAULT 'NFC',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_document_run_text UNIQUE (document_id, run_id)
);

CREATE TABLE ocr_line (
    id             TEXT PRIMARY KEY,                           -- prefix "ln_"
    page_id        TEXT NOT NULL REFERENCES page(id) ON DELETE CASCADE,
    run_id         TEXT NOT NULL REFERENCES pipeline_run(id) ON DELETE CASCADE,
    line_no        INT NOT NULL,
    text           TEXT NOT NULL,
    bbox           JSONB NOT NULL,                            -- CPS [x0,y0,x1,y1]
    confidence     REAL NOT NULL,
    doc_char_start INT NOT NULL,
    doc_char_end   INT NOT NULL,
    words          JSONB NOT NULL DEFAULT '[]',
    source         JSONB,
    flags          JSONB DEFAULT '{}',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE citation (
    id             TEXT PRIMARY KEY,                           -- prefix "cit_"
    document_id    TEXT NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    run_id         TEXT NOT NULL REFERENCES pipeline_run(id) ON DELETE CASCADE,
    quote          TEXT NOT NULL,
    quote_sha256   TEXT NOT NULL,
    segments       JSONB NOT NULL,
    doc_char_start INT NOT NULL,
    doc_char_end   INT NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (doc_char_end > doc_char_start)
);

CREATE TABLE clause_node (
    id             TEXT PRIMARY KEY,                           -- prefix "cln_"
    document_id    TEXT NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    run_id         TEXT NOT NULL REFERENCES pipeline_run(id) ON DELETE CASCADE,
    parent_id      TEXT REFERENCES clause_node(id),
    node_type      TEXT NOT NULL,
    label          TEXT,
    number         TEXT,
    title          TEXT,
    text           TEXT NOT NULL,
    doc_char_start INT NOT NULL,
    doc_char_end   INT NOT NULL,
    line_ids       JSONB NOT NULL DEFAULT '[]',
    page_start     INT NOT NULL,
    page_end       INT NOT NULL,
    confidence     REAL NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE fact (
    id                TEXT PRIMARY KEY,                        -- prefix "fct_"
    document_id       TEXT NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    run_id            TEXT NOT NULL REFERENCES pipeline_run(id) ON DELETE CASCADE,
    key               TEXT NOT NULL,
    fact_type         TEXT NOT NULL,
    raw_text          TEXT NOT NULL,
    normalized_value  JSONB,
    context_clause_id TEXT REFERENCES clause_node(id),
    context_text      TEXT,
    confidence        REAL NOT NULL,
    extractor         TEXT NOT NULL,
    validation_status TEXT NOT NULL DEFAULT 'passed' CHECK (validation_status IN ('passed', 'failed', 'skipped')),
    validation_notes  JSONB,
    citation_id       TEXT NOT NULL REFERENCES citation(id),
    trace_id          TEXT,
    observation_id    TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE annex_link (
    id                   TEXT PRIMARY KEY,                     -- prefix "alnk_"
    annex_document_id    TEXT NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    contract_document_id TEXT NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    run_id               TEXT NOT NULL REFERENCES pipeline_run(id) ON DELETE CASCADE,
    score                REAL NOT NULL,
    status               TEXT NOT NULL CHECK (status IN ('linked', 'linked_needs_review', 'unlinked')),
    annex_sequence       INT NOT NULL DEFAULT 1,
    effective_date       DATE,
    citation_id          TEXT REFERENCES citation(id),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_annex_contract_run UNIQUE (annex_document_id, contract_document_id, run_id)
);

CREATE TABLE finding (
    id           TEXT PRIMARY KEY,                             -- prefix "fnd_"
    dossier_id   TEXT NOT NULL REFERENCES dossier(id) ON DELETE CASCADE,
    run_id       TEXT NOT NULL REFERENCES pipeline_run(id) ON DELETE CASCADE,
    finding_type TEXT NOT NULL CHECK (finding_type IN ('structured', 'semantic')),
    scope        TEXT NOT NULL CHECK (scope IN ('within_document', 'contract_annex', 'annex_annex')),
    key_or_topic TEXT NOT NULL,
    disposition  TEXT NOT NULL CHECK (disposition IN (
                        'comparable_match', 'comparable_difference', 'candidate_amendment',
                        'not_comparable', 'insufficient_evidence'
                    )),
    severity     TEXT NOT NULL CHECK (severity IN ('high', 'medium', 'low')),
    confidence   REAL NOT NULL,
    rationale    TEXT,
    method       TEXT NOT NULL,
    trace_id     TEXT,
    observation_id TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE finding_side (
    finding_id     TEXT NOT NULL REFERENCES finding(id) ON DELETE CASCADE,
    side           TEXT NOT NULL CHECK (side IN ('a', 'b')),
    document_id    TEXT NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    fact_id        TEXT REFERENCES fact(id),
    clause_node_id TEXT REFERENCES clause_node(id),
    citation_id    TEXT NOT NULL REFERENCES citation(id),      -- BR-14: cả hai phía đều có citation
    value_snapshot JSONB,
    PRIMARY KEY (finding_id, side)
);


-- ===========================================================================
-- §6. HITL & OPTIMISTIC CONCURRENCY
-- ===========================================================================
-- review_item: cờ version tăng đơn (P0-05)
CREATE TABLE review_item (
    id                    TEXT PRIMARY KEY,                   -- prefix "ri_"
    dossier_id            TEXT NOT NULL REFERENCES dossier(id) ON DELETE CASCADE,
    run_id                TEXT NOT NULL REFERENCES pipeline_run(id) ON DELETE CASCADE,
    target_type           TEXT NOT NULL CHECK (target_type IN ('fact', 'finding', 'annex_link', 'clause', 'table_cell', 'citation')),
    target_id             TEXT NOT NULL,
    reason                TEXT NOT NULL,
    priority              TEXT NOT NULL CHECK (priority IN ('P1', 'P2', 'P3')),
    status                TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved', 'awaiting_evidence')),
    version               INT NOT NULL DEFAULT 1,              -- P0-05 optimistic concurrency
    source_trace_id       TEXT,
    source_observation_id TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- review_action: append-only + echo base_version
CREATE TABLE review_action (
    id              TEXT PRIMARY KEY,                          -- prefix "ra_"
    review_item_id  TEXT NOT NULL REFERENCES review_item(id) ON DELETE CASCADE,
    target_type     TEXT NOT NULL,
    target_id       TEXT NOT NULL,
    action          TEXT NOT NULL CHECK (action IN ('confirm', 'correct', 'reject', 'needs_more_evidence')),
    base_version    INT NOT NULL,                              -- P0-05: client echo version đang xem
    corrected_value JSONB,
    corrected_bbox  JSONB,
    comment         TEXT,
    reviewer_id     TEXT NOT NULL REFERENCES app_user(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (action <> 'correct' OR corrected_value IS NOT NULL OR corrected_bbox IS NOT NULL)
);

CREATE TABLE dossier_approval (
    id              TEXT PRIMARY KEY,                          -- prefix "apr_"
    dossier_id      TEXT NOT NULL REFERENCES dossier(id) ON DELETE CASCADE,
    run_id          TEXT NOT NULL REFERENCES pipeline_run(id) ON DELETE CASCADE,
    approved_by     TEXT NOT NULL REFERENCES app_user(id),
    snapshot_sha256 TEXT NOT NULL,
    comment         TEXT,
    approved_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ===========================================================================
-- §7. AUDIT TRAILS & LEDGER (APPEND-ONLY)
-- ===========================================================================
CREATE TABLE job_event (
    id         BIGSERIAL PRIMARY KEY,
    job_id     TEXT NOT NULL REFERENCES job(id) ON DELETE CASCADE,
    from_status TEXT,
    to_status  TEXT NOT NULL,
    actor      TEXT NOT NULL,
    reason     TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE page_step_stat (
    id          BIGSERIAL PRIMARY KEY,
    page_id     TEXT NOT NULL REFERENCES page(id) ON DELETE CASCADE,
    run_id      TEXT NOT NULL REFERENCES pipeline_run(id) ON DELETE CASCADE,
    step        TEXT NOT NULL,
    engine      TEXT NOT NULL,
    duration_ms INT NOT NULL,
    cache_hit   BOOLEAN NOT NULL DEFAULT false,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE usage_ledger (
    id               BIGSERIAL PRIMARY KEY,
    run_id           TEXT NOT NULL REFERENCES pipeline_run(id) ON DELETE CASCADE,
    dossier_id       TEXT NOT NULL,
    step             TEXT NOT NULL,
    provider         TEXT NOT NULL,
    model_requested  TEXT NOT NULL,
    model_returned   TEXT,
    input_tokens     INT NOT NULL DEFAULT 0,
    cached_tokens    INT NOT NULL DEFAULT 0,
    output_tokens    INT NOT NULL DEFAULT 0,
    reasoning_tokens INT,
    pages            INT NOT NULL DEFAULT 0,
    cache_hit        BOOLEAN NOT NULL DEFAULT false,
    latency_ms       INT,
    cost_usd         NUMERIC(12, 6) NOT NULL,
    price_version    TEXT NOT NULL,
    trace_id         TEXT,
    observation_id   TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ===========================================================================
-- §8. BỘ CHỈ MỤC HIỆU NĂNG (INDEXES)
-- ===========================================================================
-- FK + status filter + composite phục vụ resolve citation / effective view
CREATE INDEX idx_document_dossier_id        ON document(dossier_id);
CREATE INDEX idx_document_order             ON document(dossier_id, role, order_index);
CREATE INDEX idx_page_document_id           ON page(document_id);
CREATE INDEX idx_job_dossier_id             ON job(dossier_id);
CREATE INDEX idx_job_status                 ON job(status);
CREATE INDEX idx_job_step_run_id            ON job_step(run_id);
CREATE INDEX idx_task_ready                 ON task (priority, run_after) WHERE status = 'queued';
CREATE INDEX idx_task_job_id                ON task(job_id);

CREATE INDEX idx_ocr_line_page_run          ON ocr_line(page_id, run_id);
CREATE INDEX idx_citation_document_run      ON citation(document_id, run_id);
CREATE INDEX idx_clause_node_doc_run        ON clause_node(document_id, run_id);
CREATE INDEX idx_fact_document_run          ON fact(document_id, run_id);
CREATE INDEX idx_fact_key                   ON fact(key);
CREATE INDEX idx_fact_citation_id           ON fact(citation_id);
CREATE INDEX idx_finding_dossier_run        ON finding(dossier_id, run_id);
CREATE INDEX idx_finding_side_finding_id    ON finding_side(finding_id);
CREATE INDEX idx_finding_side_fact_id       ON finding_side(fact_id);
CREATE INDEX idx_finding_side_citation_id   ON finding_side(citation_id);

CREATE INDEX idx_review_item_dossier        ON review_item(dossier_id, status);
CREATE INDEX idx_review_item_target         ON review_item(target_type, target_id);
CREATE INDEX idx_review_action_item         ON review_action(review_item_id, created_at DESC);
CREATE INDEX idx_usage_ledger_run           ON usage_ledger(run_id);
CREATE INDEX idx_usage_ledger_dossier       ON usage_ledger(dossier_id);


-- ===========================================================================
-- §9. CƯỠNG CHẾ BẤT BIẾN (TRIGGERS)
-- ===========================================================================
-- Hàm chung: bất kỳ bảng immutable nào UPDATE/DELETE đều raise exception
CREATE OR REPLACE FUNCTION forbid_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'Bảng % là bất biến (append-only), không được phép UPDATE hoặc DELETE', TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;

-- Áp dụng cho tất cả bảng kết quả máy + audit
CREATE TRIGGER trg_immutable_document_text BEFORE UPDATE OR DELETE ON document_text FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER trg_immutable_ocr_line       BEFORE UPDATE OR DELETE ON ocr_line       FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER trg_immutable_citation       BEFORE UPDATE OR DELETE ON citation       FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER trg_immutable_clause_node    BEFORE UPDATE OR DELETE ON clause_node    FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER trg_immutable_fact           BEFORE UPDATE OR DELETE ON fact           FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER trg_immutable_annex_link     BEFORE UPDATE OR DELETE ON annex_link     FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER trg_immutable_finding        BEFORE UPDATE OR DELETE ON finding        FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER trg_immutable_finding_side   BEFORE UPDATE OR DELETE ON finding_side   FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER trg_immutable_review_action  BEFORE UPDATE OR DELETE ON review_action  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER trg_immutable_job_event      BEFORE UPDATE OR DELETE ON job_event      FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER trg_immutable_usage_ledger   BEFORE UPDATE OR DELETE ON usage_ledger   FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER trg_immutable_dossier_approval BEFORE UPDATE OR DELETE ON dossier_approval FOR EACH ROW EXECUTE FUNCTION forbid_mutation();


-- ===========================================================================
-- §10. VIEWS NGHIỆP VỤ
-- ===========================================================================
-- Conflict: view trên finding cần reviewer xử lý
CREATE OR REPLACE VIEW v_conflict AS
SELECT f.*
FROM finding f
WHERE f.disposition IN ('comparable_difference', 'candidate_amendment', 'insufficient_evidence')
   OR f.confidence < 0.6;

-- Effective fact: fact + action mới nhất qua review_item.version (không dùng created_at)
CREATE OR REPLACE VIEW v_fact_effective AS
SELECT
    f.id                        AS fact_id,
    f.document_id,
    f.run_id,
    f.key,
    f.normalized_value          AS machine_value,
    CASE ra.action
        WHEN 'correct' THEN COALESCE(ra.corrected_value, f.normalized_value)
        WHEN 'reject'  THEN NULL
        ELSE f.normalized_value
    END                         AS effective_value,
    COALESCE(ra.action, 'unreviewed') AS review_state,
    ra.corrected_bbox,
    ra.reviewer_id,
    ra.created_at               AS reviewed_at,
    f.citation_id               AS original_citation_id,
    ri.id                       AS review_item_id,
    ri.version                  AS current_item_version         -- Client echo vào base_version
FROM fact f
LEFT JOIN review_item ri
       ON ri.target_type = 'fact' AND ri.target_id = f.id
LEFT JOIN LATERAL (
    SELECT a.*
    FROM review_action a
    WHERE a.review_item_id = ri.id
    ORDER BY a.created_at DESC
    LIMIT 1
) ra ON TRUE;

-- Tóm tắt batch
CREATE OR REPLACE VIEW v_batch_summary AS
SELECT j.batch_id,
       count(*)                                                                AS total,
       count(*) FILTER (WHERE j.status IN ('reviewed', 'approved'))            AS done,
       count(*) FILTER (WHERE j.status = 'pending_review')                     AS needs_review,
       count(*) FILTER (WHERE j.status = 'failed')                             AS failed,
       count(*) FILTER (WHERE j.status IN ('uploaded', 'processing', 'extracted')) AS in_progress
FROM job j
WHERE j.batch_id IS NOT NULL
GROUP BY j.batch_id;


-- ===========================================================================
-- §11. SEED TÀI KHOẢN MẶC ĐỊNH (DEV ONLY)
-- ===========================================================================
-- 3 tài khoản bootstrap cho môi trường dev; production seed bằng script riêng
-- với password_hash từ argon2 thật. Không commit hash production.
-- INSERT INTO app_user (id, display_name, role, password_hash)
-- VALUES
--     ('usr_01J0001OPERATOR', 'Default Operator', 'operator', '$argon2id$dev_only'),
--     ('usr_01J0001REVIEWER', 'Default Reviewer', 'reviewer', '$argon2id$dev_only'),
--     ('usr_01J0001ADMIN',    'Default Admin',    'admin',    '$argon2id$dev_only');


COMMIT;


-- =============================================================================
-- Hết DOC-04b · PostgreSQL Schema v1.0
-- =============================================================================
