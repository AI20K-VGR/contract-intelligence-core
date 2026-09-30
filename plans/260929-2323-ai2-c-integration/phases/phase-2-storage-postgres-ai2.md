---
phase: 2
title: "Storage Postgres Ai2"
status: pending
plan: 260929-2323-ai2-c-integration
created: 2026-09-29
harness_version: 6.3.0
harness_kit_digest: 672de2e098c3cb8451018791788f1052b1b812ccec08a1f124191bd8bbc04ebd
harness_schema_version: 1.0
---

# Phase 2 — Storage Postgres Ai2

## Overview
Làm cho câu trả lời của AI2 **giống hệt trước và sau restart**, rồi chuyển state sang schema `ai2` trong Postgres của Backend. Ba nhóm commit:

- **2a — ID tất định (không chờ ADR-14).** Bỏ `uuid4` khỏi ID đầu ra của pipeline (`clause.py:18,29`, `compare.py:416,468`). Gốc đã quan sát ở PB-C1.
- **2b — Store + record + phục hồi (không chờ ADR-14, kiểm trên SQLite).** Viết lại job store bằng SQLAlchemy Core chạy được cả SQLite lẫn Postgres; lưu record **sau** `run_idp` cùng transaction với `SUCCEEDED`; nạp record lazy; worker không verify lại envelope; sweep job kẹt; nonce có TTL; lease theo budget.
- **2c — Bind Postgres (CHỜ P1 = `Accepted`).** Bootstrap role/schema, Alembic đa schema, `ai2-migrate` trong compose, test quyền bằng testcontainers. Nếu P1 = `Rejected` → **2c′** (SQLite trên volume), sau khi plan được sửa và duyệt lại.

Không có cạnh DAG từ P1; cổng ADR-14 nằm ở bước 2c.0.

## Dependency map
- **Upstream:** P1 (chỉ cho 2c); A P3/P4 (marker, conftest cô lập `.env`, workflow `ai-service.yml` — file sửa tuần tự sau A); B (các sửa `main.py` của B đã merge, logger của B nếu có).
- **Downstream:** P3 (E2E dùng store, `ai2-migrate`, record persistence, sweep); P4 không phụ thuộc (không chung file; P4 import `compare._pair` mà không sửa).
- **Code tái dùng:** `app/tools/persist.py:46-118` (`record_to_dict/record_from_dict`), `app/pipeline/clause_compare.py:444` (mẫu ID băm), `app/security/service_envelope.py:105-109` (skew, hết hạn), fixture request `tests/test_clause_compare.py::_request` (`:122-168`).

## Requirements
### 2a — ID tất định
- **F2.1** `ClauseChunker.chunk` (`app/pipeline/clause.py:18,29`): `chunk_id = "chk_" + sha256(f"{handoff.dossier_id}|{handoff.pins.source_snapshot_digest}|{node.node_id}").hexdigest()[:12]`. Thứ tự chunk giữ nguyên (theo `handoff.nodes`).
- **F2.2** `app/pipeline/compare.py:416` (`_cand`): `cand_` + sha256 của `left.fact_id|right.fact_id|ftype|scope|item` (12 hex); `:468`: `iss_` + sha256 của `lab|f.fact_id` (12 hex). Theo mẫu `clause_compare.py:444`.
- **F2.3** Lint `uuid4` trong `app/pipeline/*.py`: chỉ cho phép đúng 4 chỗ tạo danh tính mới, không phải ID đầu ra: `ai1_ingest.py:26,41` (upload demo), `idp.py:50` (job_id mặc định), `execution.py:51` (run_id mặc định). Chỗ thứ 5 → test đỏ.

### 2b — Store dialect-agnostic, record, phục hồi
- **F2.4 Dependency** (`ai-service/pyproject.toml` `dependencies`, VL-6): `sqlalchemy>=2.0.30,<2.1` (cùng dòng với Backend lock 2.0.54), `psycopg[binary]>=3.2,<4`, `alembic>=1.13,<2`; extra `dev`: `testcontainers[postgres]>=4.8,<5` `[ASSUMED: cận phiên bản chốt lúc uv lock]`. Chạy `uv lock`; `uv sync --frozen --extra dev --extra web` phải thành công trên Windows và Linux. Không sửa `Dockerfile.ai2` (migrations nằm dưới `app/`, đã được `COPY app/ app/`).
- **F2.5 `app/db/engine.py`.** `resolve_database_url()`: `AI2_DATABASE_URL` → `sqlite:///{AI2_JOB_DB}` (tương thích `jobs.py:49`) → `sqlite:///data/ai2/ai2_state.sqlite` (file mới, không đụng `jobs.sqlite` cũ, VD-C3). `get_engine()` lazy singleton, **không kết nối lúc import**. Postgres: `pool_size=5, max_overflow=5, pool_pre_ping=True`. SQLite: `execution_options(schema_translate_map={"ai2": None})`, `check_same_thread=False`, WAL + `busy_timeout`, `metadata.create_all` ở lần dùng đầu (dev/test). Không bao giờ log URL có mật khẩu (`url.render_as_string(hide_password=True)`).
- **F2.6 `app/db/tables.py`.** `metadata = MetaData(schema="ai2")`; ba bảng `jobs`, `service_nonces`, `dossier_record` + index như plan.md "Schema `ai2`".
- **F2.7 `app/tools/jobs.py` viết lại** bằng SQLAlchemy Core:
  - Class `SqlJobStore(engine)`, `SqlJobStore.from_env()`. `SQLiteJobStore(path)` giữ lại làm lớp con (dựng URL sqlite) cho tương thích: `tests/test_p0_contract_baseline.py:184`, `app/tools/__init__.py:13`. Giữ nguyên tên exception (`JobOwnershipConflict`, `JobNonceReplayConflict`, `JobPayloadConflict`) và re-export `durable` (`jobs.py:15-21`).
  - `create_or_get(..., actor_id, nonce_expires_ms)`: một transaction; nonce trùng khác fingerprint → `JobNonceReplayConflict`; `INSERT … ON CONFLICT DO NOTHING` rồi SELECT khi rỗng (dialect insert của `postgresql`/`sqlite`); ngữ nghĩa bằng `jobs.py:136-238`.
  - `claim(job_id, *, tenant_id, dossier_id, lease_ms)`: **một** `UPDATE … WHERE job_id AND tenant AND dossier AND (status='QUEUED' OR (status='RUNNING' AND lease_until_ms < :now)) RETURNING worker_token`.
  - `set_wire(...)` giữ fencing `worker_token` (`jobs.py:277-315`).
  - `complete(job_id, *, tenant_id, dossier_id, worker_token, status, wire, result, record_blob)`: một transaction: UPDATE fenced; nếu cập nhật 1 dòng và `status == "SUCCEEDED"` thì UPSERT `dossier_record` với điều kiện `excluded.attempt >= dossier_record.attempt`. Lỗi ở bước record → rollback cả job (job không thành `SUCCEEDED`).
  - `get`, `load_record(tenant_id, dossier_id) -> bytes | None`, `list_stranded(now_ms, grace_ms, limit)`, `purge_expired_nonces(now_ms) -> int`, `clear()`.
  - Bỏ `list_succeeded` (chỉ dùng bởi hydrate cũ và test).
- **F2.8 `app/tools/record_codec.py`.** `encode_record(rec) -> EncodedRecord(blob, sha256, size_bytes)` = gzip của JSON `{"record_schema_version": 1, "record": record_to_dict(rec)}` (`sort_keys=True, ensure_ascii=False`); `decode_record(blob) -> DossierRecord`, version khác → `RecordSchemaUnsupported`. Tái dùng `persist.record_to_dict/record_from_dict`, không viết serializer thứ hai.
- **F2.9 `app/tools/store.py`.** `RecordBackedSnapshotStore(InMemorySnapshotStore)` nhận `loader(tenant_id, dossier_id) -> DossierRecord | None`; `get()` trượt → loader → `put`. Lỗi giải mã → log `ai2.record_load_failed code=AI2_RECORD_REBUILD_REQUIRED` (chỉ id), trả `None` và đánh dấu để `/query` thêm trace code này (VD-C6). Không nạp eager.
- **F2.10 `app/tools/job_sweeper.py`.** `sweep_once(store, dispatch, now_ms)`: `list_stranded` (QUEUED có `updated_ms < now - grace`, grace mặc định 15 s; hoặc RUNNING hết lease), tối đa 20 job mỗi lượt → `dispatch(job_id)`; `purge_expired_nonces`. `start_periodic(interval_s) -> stop_event` dùng daemon thread; env `AI2_JOB_SWEEP_INTERVAL_SECONDS` (mặc định 30; `0` = chỉ chạy lúc startup). Dispatch qua `ThreadPoolExecutor(max_workers=AI2_JOB_WORKERS, mặc định 2)`.
- **F2.11 `app/api/main.py`.**
  - `JOB_STORE = SqlJobStore.from_env()` (lazy); `STORE = RecordBackedSnapshotStore(loader=…)` thay `InMemorySnapshotStore()` (`main.py:71`).
  - Xoá `_hydrate_store_from_jobs` (`:83-116`); startup (`:118-121`) chạy `sweep_once` rồi `start_periodic`; thêm shutdown dừng thread.
  - `create_idp_job` (`:1632-1695`): truyền `actor_id=service_envelope.actor_id`, `nonce_expires_ms=(service_envelope.expires_at + skew) * 1000`; background task `_run_wire_job(job_id)`.
  - `_run_wire_job(job_id)` (`:165-268`): đọc row; **không** gọi `verify_service_envelope`; adapt với `tenant_id`/`actor_id` của row; lease = `(budget.max_processing_seconds + 30) * 1000`; sau `run_idp`: `JOB_STORE.complete(..., record_blob=encode_record(adapted.record).blob)` rồi `STORE.put(adapted.record)`. Nhánh FAILED giữ nguyên ngữ nghĩa. Log chỉ gồm `job_id`, `dossier_id`, `attempt`, count, `size_bytes`, code.
  - `/query`: khi record không nạp được do F2.9 → trace code `AI2_RECORD_REBUILD_REQUIRED` thay `AI2_QUERY_EVIDENCE_REQUIRED` (`:849-869`).
- **F2.12 Test hiện có phải sửa:** `tests/test_api.py:13-38` (viết lại theo loader lazy); `tests/test_job_store.py` (6 test, `:23-172`) tham số hoá theo `[sqlite, postgres]`.

### 2c — Bind Postgres (chờ ADR-14)
- **F2.13 `app/db/bootstrap.py`** (admin, idempotent, `psycopg.sql` cho identifier/literal, không log mật khẩu): tạo/đồng bộ mật khẩu role `ai2_migrator`, `ai2_app` (LOGIN); `CREATE SCHEMA IF NOT EXISTS ai2 AUTHORIZATION ai2_migrator`; `REVOKE ALL ON SCHEMA ai2 FROM PUBLIC`; `GRANT USAGE ON SCHEMA ai2 TO ai2_app`; `ALTER DEFAULT PRIVILEGES FOR ROLE ai2_migrator IN SCHEMA ai2 GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ai2_app` (và `USAGE, SELECT ON SEQUENCES`); `ALTER ROLE ai2_app CONNECTION LIMIT 20`; `ALTER ROLE ai2_app SET statement_timeout = '30s'`; `ALTER ROLE ai2_app|ai2_migrator SET search_path = ai2`.
- **F2.14 `app/db/migrations/`** (`env.py`, `script.py.mako`, `versions/0001_ai2_initial.py`): `target_metadata = tables.metadata`. Postgres: `version_table_schema="ai2"`, `include_schemas=True`, `include_name` chỉ nhận schema `ai2` (schema `None`/`public` → `False`). SQLite: `schema_translate_map`, `render_as_batch=True`, version table không schema.
- **F2.15 `app/db/migrate.py`** (`python -m app.db.migrate [--bootstrap]`): có `AI2_DB_ADMIN_URL` và `--bootstrap` → F2.13; sau đó `alembic upgrade head` bằng `AI2_DB_MIGRATOR_URL` (Postgres) hoặc `AI2_DATABASE_URL` (SQLite). Cấu hình Alembic dựng bằng code (không cần `alembic.ini`). Exit: 0 ok, 1 lỗi migration, 2 thiếu cấu hình. Chỉ in revision.
- **F2.16 `docker-compose.yml`:**
  - Thêm service `ai2-migrate`: build giống `ai2-service` (`:442-445`), `command: ["uv","run","--no-sync","python","-m","app.db.migrate","--bootstrap"]`, env `AI2_DB_ADMIN_URL=postgresql+psycopg://ci:${BACKEND_DB_PASSWORD:-ci_secret_dev}@backend-db:5432/contract_intelligence`, `AI2_DB_MIGRATOR_URL`, `AI2_DB_MIGRATOR_PASSWORD` (mặc định dev `ai2_migrator_dev`), `AI2_DB_APP_PASSWORD` (mặc định dev `ai2_app_dev`); `depends_on: backend-db: service_healthy`; `restart: "no"`.
  - `ai2-service`: thêm `AI2_DATABASE_URL=postgresql+psycopg://ai2_app:${AI2_DB_APP_PASSWORD:-ai2_app_dev}@backend-db:5432/contract_intelligence`; `depends_on`: `backend-db` (`service_healthy`) và `ai2-migrate` (`service_completed_successfully`, `[PRIOR]` Compose spec). Giữ volume `ai2_data` (`:461`).
- **F2.17 `.github/workflows/ai-service.yml`:** job test offline thêm `env: AI2_REQUIRE_DOCKER: "1"` để test `requires_docker` không được skip âm thầm trên CI.
- **F2.18 `ai-service/tests/conftest.py`:** fixture session `pg_admin_url` (testcontainers `postgres:16-alpine`, user `ci`, db `contract_intelligence`, như compose `:189-196`); Docker không khả dụng → `pytest.skip("Docker không khả dụng")`, trừ khi `AI2_REQUIRE_DOCKER=1` → `pytest.fail`. Đăng ký marker `requires_docker` trong `pyproject.toml`. Env test mặc định `AI2_DATABASE_URL=sqlite:///<tmp>/ai2_state.sqlite` để test không ghi vào `data/ai2/`.
- **2c′ (chỉ khi ADR-14 `Rejected`, sau khi plan được sửa + duyệt lại):** bỏ F2.13; compose không đặt `AI2_DATABASE_URL` (SQLite `/app/data/ai2/ai2_state.sqlite` trên volume), `ai2-migrate` chạy `app.db.migrate` không `--bootstrap`; F2.17, F2.18 vẫn áp dụng cho suite store.

Phi chức năng:
- Không kết nối DB lúc import `app.api.main`.
- Không log văn bản hợp đồng, HMAC secret, mật khẩu DB, URL có mật khẩu (`docs/code-standards.md:50`).
- 1 replica; claim nguyên tử đủ an toàn khi sweep và background task cùng dispatch.

## Related Code Files
**Create**
- `ai-service/app/db/__init__.py`, `ai-service/app/db/engine.py`, `ai-service/app/db/tables.py`
- `ai-service/app/db/bootstrap.py`, `ai-service/app/db/migrate.py`
- `ai-service/app/db/migrations/env.py`, `ai-service/app/db/migrations/script.py.mako`, `ai-service/app/db/migrations/versions/0001_ai2_initial.py`
- `ai-service/app/tools/record_codec.py`, `ai-service/app/tools/job_sweeper.py`
- `ai-service/tests/test_pipeline_determinism.py`, `ai-service/tests/test_record_persistence.py`, `ai-service/tests/test_job_recovery.py`, `ai-service/tests/test_ai2_postgres_schema.py`

**Modify**
- `ai-service/app/pipeline/clause.py`, `ai-service/app/pipeline/compare.py`
- `ai-service/app/tools/jobs.py`, `ai-service/app/tools/store.py`, `ai-service/app/tools/__init__.py`
- `ai-service/app/api/main.py`
- `ai-service/pyproject.toml`, `ai-service/uv.lock`
- `ai-service/tests/conftest.py`, `ai-service/tests/test_api.py`, `ai-service/tests/test_job_store.py`
- `docker-compose.yml`, `.github/workflows/ai-service.yml`

**Delete** — không có (`data/ai2/jobs.sqlite` là dữ liệu dev không track, để nguyên theo VD-C3).

## File inventory

| File | Hành động | Nhóm | Cỡ | Tác động test |
|---|---|---|---|---|
| `clause.py`, `compare.py` | M | 2a | vài dòng | `test_pipeline_determinism.py`, suite reasoning |
| `test_pipeline_determinism.py` | C | 2a | ~120 dòng | RED sẵn (PB-C1) |
| `app/db/engine.py`, `tables.py`, `__init__.py` | C | 2b | ~150 dòng | toàn bộ store test |
| `jobs.py` | M (viết lại) | 2b | ~300 dòng | `test_job_store.py`, `test_p0_contract_baseline.py:184`, wire tests |
| `record_codec.py`, `job_sweeper.py` | C | 2b | ~80 + ~120 dòng | `test_record_persistence.py`, `test_job_recovery.py` |
| `store.py`, `tools/__init__.py` | M | 2b | ~40 dòng | `test_api.py`, query tests |
| `main.py` | M | 2b | ~80 dòng đổi | `test_api.py`, `test_processing_wire_contract.py:385`, `test_service_envelope.py:67` |
| `pyproject.toml`, `uv.lock` | M | 2b/2c | deps + marker | toàn suite |
| `test_record_persistence.py`, `test_job_recovery.py` | C | 2b | ~200 + ~220 dòng | mới |
| `test_api.py`, `test_job_store.py` | M | 2b | viết lại 1 test, tham số hoá 6 test | — |
| `bootstrap.py`, `migrate.py`, `migrations/*` | C | 2c | ~120 + ~80 + ~150 dòng | `test_ai2_postgres_schema.py` |
| `conftest.py` | M | 2c | ~50 dòng | fixture Postgres |
| `test_ai2_postgres_schema.py` | C | 2c | ~220 dòng | Docker |
| `docker-compose.yml` | M | 2c | ~35 dòng | E2E (P3), `docker compose config` |
| `.github/workflows/ai-service.yml` | M | 2c | +2 dòng | A `evals/tests/test_ci_workflows.py` phải vẫn xanh |

## Implementation Steps
**2a (không chờ ADR-14)**
1. RED: viết `tests/test_pipeline_determinism.py` (mục TDD). Chạy → `test_run_idp_record_identical_across_processes` và `test_run_idp_output_ids_stable` đỏ (khớp PB-C1).
2. GREEN: F2.1, F2.2; lint F2.3. Chạy lại 3/3 xanh + suite reasoning (`tests/test_reasoning.py`, `tests/test_clause_compare.py`, `tests/test_l0.py`). Commit `fix(ai2): deterministic pipeline output ids`.

**2b (không chờ ADR-14)**
3. F2.4: sửa `pyproject.toml`, `uv lock`, `uv sync --frozen --extra dev --extra web` trên Windows. Lỗi resolve → dừng và hỏi, không tự sửa pin của A/B.
4. RED: `test_record_persistence.py`, `test_job_recovery.py`; tham số hoá `test_job_store.py` (mới chỉ `sqlite`); viết lại `test_api.py:13-38`. Chạy → đỏ vì chưa có API mới.
5. GREEN: F2.5–F2.11. Chạy nhóm test 2b + suite offline. Đo `size_bytes` record cho fixture `test_clause_compare._request` và (nếu A đã có) snapshot golden ≥ 55 trang; ghi vào `verification-P2.json`. Commit `feat(ai2): durable processed record, sweep and dialect-agnostic job store`.

**2c (chờ ADR-14)**
6. **2c.0 Cổng:** đọc `artifacts/verification-P1.json`. `adr14.status != "Accepted"` → dừng nhóm 2c, báo main (P1 chờ) hoặc chuyển sang 2c′ (chỉ khi plan đã sửa + duyệt lại).
7. RED: `test_ai2_postgres_schema.py` + thêm tham số `postgres` cho `test_job_store.py`; conftest F2.18. Trên Windows không Docker: xác nhận skip có lý do; chạy RED thật trên CI Linux (hoặc máy có Docker).
8. GREEN: F2.13–F2.16. `docker compose config` hợp lệ. Nếu có Docker: `docker compose up -d backend-db ai2-migrate ai2-service` rồi `curl http://localhost:8002/healthz`.
9. F2.17. Chạy regression gate. Commit `feat(ai2): bind AI2 state to Postgres schema ai2 (ADR-14)`.

## TDD
### Tests Before (RED)
2a — `tests/test_pipeline_determinism.py`:
- [ ] `test_run_idp_record_identical_across_processes`: 3 subprocess `sys.executable` chạy `adapt_be_ai2_processing_request(_request())` + `run_idp(..., job_id="job_fixed")` với `PYTHONHASHSEED` = 1, 2 và 1 (lặp lại) → sha256 của `json.dumps(record_to_dict(record), sort_keys=True)` bằng nhau cả 3. **Đỏ hôm nay** (PB-M3, PB-C1).
- [ ] `test_run_idp_output_ids_stable`: 2 lượt trong cùng process → tập `chunk_id`, `candidate_id`, `issue_id` trong `JobResult.contribution` bằng nhau. Đỏ hôm nay.
- [ ] `test_pipeline_has_no_random_output_ids`: quét AST `app/pipeline/*.py`, lời gọi `uuid4` chỉ ở 4 vị trí allowlist F2.3. Đỏ hôm nay (`clause.py:18,29`, `compare.py:416,468`).

2b — `tests/test_record_persistence.py`:
- [ ] `test_record_codec_roundtrip`: encode → decode → `record_to_dict` bằng nhau.
- [ ] `test_record_to_dict_covers_all_fields`: `{f.name for f in dataclasses.fields(DossierRecord)} ⊆ record_to_dict(rec).keys()` (chặn field mới bị quên).
- [ ] `test_record_schema_version_mismatch_is_fail_closed`: blob version 99 → `/query` trả `INSUFFICIENT_EVIDENCE` + `AI2_RECORD_REBUILD_REQUIRED`.
- [ ] `test_record_written_atomically_with_succeeded`: làm lỗi bước ghi record (monkeypatch) → job không `SUCCEEDED`, không có record.
- [ ] `test_older_attempt_does_not_overwrite_newer_record`.
- [ ] `test_query_identical_after_simulated_restart_subprocess`: SQLite file tạm; subprocess A (`PYTHONHASHSEED=1`) gửi job qua `TestClient` (egress tắt), chờ `SUCCEEDED`, hỏi 3 câu, in JSON; subprocess B (`PYTHONHASHSEED=2`, process mới, STORE rỗng) chỉ hỏi 3 câu → 3/3 response bằng nhau sau chuẩn hoá. **Đỏ hôm nay** (hydrate hiện tại thiếu hậu xử lý, PB-M2).
- [ ] `test_no_sensitive_values_logged`: `caplog` của một job đầy đủ không chứa chuỗi canary trong snapshot, HMAC secret, mật khẩu trong URL.

2b — `tests/test_job_recovery.py`:
- [ ] `test_worker_runs_job_after_envelope_expired`: envelope `ttl_seconds=1`, đẩy đồng hồ qua `expires_at + skew` → `sweep_once` chạy job tới `SUCCEEDED`. **Đỏ hôm nay** (`main.py:169`).
- [ ] `test_sweep_requeues_stranded_queued_job`: chèn job `QUEUED` (không background task), `updated_ms` cũ hơn grace → `SUCCEEDED`; job mới hơn grace không bị dispatch.
- [ ] `test_sweep_reclaims_expired_running_lease`.
- [ ] `test_claim_is_atomic_under_threads`: 8 thread claim cùng job → đúng 1 token.
- [ ] `test_lease_covers_processing_budget`: `lease_until_ms >= now + max_processing_seconds*1000`.
- [ ] `test_resubmit_same_key_attempt_does_not_rerun_succeeded_job`: POST lại cùng (key, attempt) → cùng `job_id`, `updated_ms`/`wire_json` không đổi.
- [ ] `test_nonce_ttl_cleanup`: nonce có `expires_ms < now` bị xoá; nonce còn hạn + payload khác → 409 `SERVICE_NONCE_REPLAY` (`main.py:1672-1687`).

2c — `tests/test_ai2_postgres_schema.py` (`requires_docker`):
- [ ] `test_bootstrap_is_idempotent` (chạy 2 lần, không lỗi, mật khẩu đồng bộ).
- [ ] `test_migrations_create_objects_only_in_ai2`: sau `upgrade head`, `information_schema.tables` của `public` không có bảng mới; `ai2.alembic_version` có `0001_ai2_initial`.
- [ ] `test_alembic_autogenerate_ignores_public`: tạo bảng giả `public.backend_like` rồi so metadata → không có op nào (bộ lọc `include_name`).
- [ ] `test_backend_alembic_version_untouched`: tạo `public.alembic_version` giả với giá trị `v9__x` trước khi migrate AI2 → giá trị giữ nguyên.
- [ ] `test_ai2_app_cannot_read_or_create_in_public`, `test_ai2_app_has_no_ddl_in_ai2`, `test_ai2_app_role_limits` (`rolconnlimit = 20`, `statement_timeout = 30s`).
- [ ] `test_least_privileged_role_cannot_read_ai2`: role mới LOGIN không grant → `SELECT * FROM ai2.jobs` bị `permission denied` (VD-C2a).
- [ ] `test_job_store.py[postgres]`: 6 test hiện có + claim nguyên tử chạy trên Postgres.

### Implement
Theo bước 2, 5, 8.

### Tests After
- [ ] `tests/test_processing_wire_contract.py::test_api_accepts_idempotent_async_processing_job` (`:385`), `tests/test_service_envelope.py::test_jobs_endpoint_requires_signed_service_envelope` (`:67`), `tests/test_p0_contract_baseline.py` xanh không sửa.

### Regression Gate
- Windows: `cd ai-service; .venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --strict-markers -m "not live and not llm" --basetemp $env:TEMP\ai2pt` → 0 failed, 0 error; số test `requires_docker` bị skip ghi lại.
- Linux CI: `cd ai-service && AI2_REQUIRE_DOCKER=1 uv run pytest -q -p no:cacheprovider --strict-markers -m "not live and not llm"` → 0 failed, 0 error, 0 skipped trong `requires_docker`.
- `cd ai-service; .venv/Scripts/ruff.exe check . ../evals` → `All checks passed`.
- `docker compose config -q` exit 0 (nơi có Docker; trên Windows không Docker kiểm bằng CI).
- `$PY evals/scripts/run_ai2_gate.py --mode pr --base-ref origin/develop` exit 0 (không hồi quy do đổi ID).

## Test scenario matrix

| Mức | Kịch bản | Test |
|---|---|---|
| Critical | Câu trả lời khác sau restart | `test_query_identical_after_simulated_restart_subprocess`, P3 E3 |
| Critical | Record không khớp job (job SUCCEEDED mà thiếu record) | `test_record_written_atomically_with_succeeded` |
| Critical | AI2 đụng bảng Backend / đè `alembic_version` | `test_alembic_autogenerate_ignores_public`, `test_backend_alembic_version_untouched`, `test_migrations_create_objects_only_in_ai2` |
| Critical | Rò quyền giữa schema | `test_ai2_app_cannot_read_or_create_in_public`, `test_least_privileged_role_cannot_read_ai2` |
| High | Job kẹt vĩnh viễn | `test_sweep_requeues_stranded_queued_job`, `test_sweep_reclaims_expired_running_lease`, `test_worker_runs_job_after_envelope_expired` |
| High | Chạy đôi / worker cũ ghi đè | `test_claim_is_atomic_under_threads`, fencing trong `test_job_store.py` |
| High | Replay nonce / bảng nonce phình | `test_nonce_ttl_cleanup` |
| High | Log lộ dữ liệu | `test_no_sensitive_values_logged` |
| Medium | Lease ngắn hơn budget gây tính đôi | `test_lease_covers_processing_budget` |
| Medium | Test Postgres skip âm thầm trên CI | F2.17 + fixture fail khi `AI2_REQUIRE_DOCKER=1` |

## Success Criteria
- [ ] (test) `test_pipeline_determinism.py` 3/3 xanh trên Windows và Linux (trước: 2 đỏ + lint đỏ).
- [ ] (test) `test_record_persistence.py` 7/7, `test_job_recovery.py` 7/7 xanh trên Windows (SQLite).
- [ ] (test, CI Linux) `test_ai2_postgres_schema.py` 8/8 và `test_job_store.py[postgres]` 7/7 xanh, **0 skipped** với `AI2_REQUIRE_DOCKER=1`.
- [ ] (test) Suite offline ai-service 0 failed, 0 error (Windows + Linux).
- [ ] (invariant) `rg -n "_hydrate_store_from_jobs|list_succeeded" ai-service/app` → 0 hit; `rg -n "verify_service_envelope" ai-service/app/api/main.py` không còn trong `_run_wire_job`.
- [ ] (invariant) `size_bytes` của record (fixture + golden ≥ 55 trang nếu có) ghi trong `verification-P2.json`.
- [ ] (invariant) `docker compose config -q` exit 0; compose có `ai2-migrate` và `ai2-service.depends_on.ai2-migrate.condition == service_completed_successfully`.

## Risk Assessment

| Rủi ro | Khả năng × Tác động | Giảm thiểu |
|---|---|---|
| R2-1: SQLAlchemy Core khác hành vi giữa SQLite và Postgres (`RETURNING`, `ON CONFLICT`, isolation) | Trung × Cao | Một bộ test chạy trên cả hai dialect; SQLite 3.53.1 có `RETURNING` (PB-C7); dialect insert tường minh |
| R2-2: `psycopg[binary]` không có wheel cho Windows py3.12 | Thấp × Trung `[PRIOR]` | Bước 3 phát hiện ngay; dừng và hỏi (không đổi driver âm thầm) |
| R2-3: Thread sweep rò trong test | Trung × Trung | `AI2_JOB_SWEEP_INTERVAL_SECONDS=0` trong test; shutdown dừng thread; `TestClient` dùng context manager |
| R2-4: Sửa `main.py` chồng với B | Trung × Trung | C chạy sau khi B merge; đọc lại `main.py` trước bước 5; giữ phạm vi sửa ở các hàm nêu trong F2.11 |
| R2-5: Alembic trên SQLite (`schema_translate_map` + batch) không chạy `[ASSUMED]` | Trung × Trung | SQLite dùng `create_all` cho dev/test; alembic SQLite chỉ cần cho 2c′; test `test_migrations_*` có biến thể SQLite khi đi 2c′ |
| R2-6: Bootstrap chạy bằng superuser trong compose | Trung × Trung | Chỉ `ai2-migrate` nhận admin URL; prod là DBA (ADR-14); không log mật khẩu |
| R2-7: Record lớn làm chậm commit SUCCEEDED | Trung × Trung | gzip; đo `size_bytes`; nếu > 20 MB `[ASSUMED ngưỡng]` → báo ở verification và mở follow-up |
