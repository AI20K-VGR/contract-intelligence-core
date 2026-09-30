---
phase: 3
title: "Backend Ai2 E2e"
status: pending
plan: 260929-2323-ai2-c-integration
created: 2026-09-29
harness_version: 6.3.0
harness_kit_digest: 672de2e098c3cb8451018791788f1052b1b812ccec08a1f124191bd8bbc04ebd
harness_schema_version: 1.0
---

# Phase 3 — Backend Ai2 E2e

## Overview
Chứng minh luồng Backend ↔ AI2 chạy thật, lặp lại được, trên image/contract có version của B (D-1, D-2): submit → poll → Backend persist → query có citation → restart AI2 vẫn trả lời giống hệt → retry `attempt` mới → Backend cập nhật digest; job kẹt `QUEUED` được chạy lại. Ba nhóm commit:

- **3a — Backend retry theo attempt.** Hiện Backend không có đường này (PB-C5): `attempt` cứng 1 và persist raise Conflict khi digest đổi. Thêm tham số `attempt`, supersede theo VD-C1, hàm `retry_ai2_processing`.
- **3b — Bộ E2E** `backend/tests/e2e/` bằng pytest + testcontainers: Postgres + container AI2 (+ one-shot `ai2-migrate`), Backend chạy in-process.
- **3c — CI + tài liệu current-state.** Workflow mới `e2e-backend-ai2.yml`; cập nhật `docs/system-architecture.md`, `docs/code-standards.md`, `ai-service/README.md`.

Phụ thuộc P1 (quyết định ADR-14) và P2 (store, record, sweep, `ai2-migrate`).

## Dependency map
- **Upstream:** P1 (`verification-P1.json`: `Accepted` → E7 chạy trên Postgres; `Rejected` → plan đã sửa, E9 thay E7); P2 (`app.db.migrate`, `AI2_DATABASE_URL`, `AI2_JOB_SWEEP_INTERVAL_SECONDS`, record lazy); A P1 (golden `evals/data/golden/snapshots/G01.json`, `questions.json`); B P1 (`query_snapshot_digest` trong result, schema `ai2.query.v1`, danh sách field volatile), B P3 (image, `GET /version`, tag GHCR).
- **Downstream:** P4-F4.10 (release chỉ khi E2E xanh trên SHA release).
- **Code Backend tái dùng:** `infrastructure/ai_adapters.py:168-225` (`submit_ai2_processing`, `poll_ai2_processing`), `:286-327` (`query_ai2`); `worker.py:458-610` (`_run_ai2_if_ready`), `:327-354` (`_persist_ai2_snapshot_identity`), `:78-110` (`_ai2_query_snapshot_digest`); `shared/ai/persistence.py:870-1060` (`persist_ai2_processing_result`); `shared/ai/canonical_processing.py:234-360` (`build_processing_request`); `config/settings.py:390-391` (`get_settings` có cache).
- **Người:** HC-C2 (chủ Backend chốt VD-C1; mentor duyệt workflow `/.github/`).

## Requirements
### 3a — Backend retry theo attempt
- **F3.1** `build_processing_request(..., attempt: int = 1)` (`canonical_processing.py:234`, gán ở `:342`). `request_id`/`idempotency_key` giữ `f"{run_id}:ai2"` (`:338-341`) → AI2 tạo job mới nhờ `UNIQUE(tenant, key, attempt)`.
- **F3.2** `persist_ai2_processing_result` (`persistence.py:870-1060`), theo VD-C1(a):
  - đọc attempt đã lưu từ `run.ai2_result_json` (field `attempt` của wire result);
  - attempt mới **>** attempt đã lưu → supersede trong một transaction: xoá projection AI2 của run (`FindingORM`/`FindingSideORM` theo `run_id`; `ReviewItemORM` theo `run_id`; `FactORM` chỉ theo discriminator AI2/run đã xác minh ở bước 1), rồi ghi projection mới, cập nhật `ai2_result_json/ai2_result_digest/ai2_*`;
  - `CitationORM` không có run/extractor provenance theo quan sát hiện tại. Chỉ xoá citation sau khi đã xoá chính xác các fact AI2 cũ **và** chứng minh citation không còn được tham chiếu bởi fact/finding nào khác; nếu không thể chứng minh quyền sở hữu/tham chiếu an toàn, chặn supersede với `AI2_SUPERSEDE_CITATION_OWNERSHIP_UNKNOWN` (fail closed), không xoá theo document membership;
  - đã có `ReviewActionORM` cho review item của run → **không** supersede, raise `Ai2PersistenceConflict` với code `AI2_SUPERSEDE_BLOCKED_BY_REVIEW`;
  - attempt **bằng** + digest khác → Conflict như cũ (`:895-899`);
  - attempt **nhỏ hơn** → bỏ qua, log `ai2.stale_attempt_ignored` (chỉ id), trả kết quả có `accepted=false` cùng attempt/digest hiện hành từ DB (DOC-04 `:281`); caller không được dùng report cũ để cập nhật dossier metadata;
- **F3.3** `worker.py`:
  - Tách khối submit → poll → persist → snapshot identity của `_run_ai2_if_ready` (`:514-590`) thành helper `_submit_poll_persist(session, *, request, tenant_id, dossier_id, run_id)` (DRY, hành vi `_run_ai2_if_ready` giữ nguyên, test hiện có `tests/unit/test_worker_pipeline_run.py:132-180` phải xanh không sửa).
  - Thêm `retry_ai2_processing(session, *, dossier_id, tenant_id, run_id) -> dict`: attempt = attempt đã lưu + 1, dựng request qua F3.1, gọi helper; chỉ khi persistence xác nhận `accepted=true` mới cập nhật `dossier.metadata_json["ai2_snapshot_digest"]` từ digest canonical đã lưu. Persist result và cập nhật snapshot identity trong cùng transaction/khóa run để completion stale không thể rewind digest hiện hành.
  - Nguồn digest: `report["query_snapshot_digest"]` (B) nếu có; thiếu → `_ai2_query_snapshot_digest(request)` + log `ai2.digest_fallback`; có cả hai mà khác nhau → lỗi `AI2_DIGEST_MISMATCH`, không persist digest (fail closed).
  - Không thêm route/endpoint mới (trigger retry chỉ qua hàm; nối vào UI/API là việc của Backend sau).

### 3b — E2E (`backend/tests/e2e/`)
- **F3.4 Harness** (`conftest.py`):
  - Marker `e2e` (đăng ký trong `backend/pyproject.toml`); cả thư mục skip trừ khi `AI2_E2E=1`; Docker không khả dụng → skip có lý do, trừ khi `AI2_E2E_REQUIRE_DOCKER=1` → fail. Dev dep `testcontainers[postgres]>=4.8,<5` `[ASSUMED cận]`.
  - Container (một `Network` riêng): `postgres:16-alpine` (user `ci`, db `contract_intelligence`, alias `pg`); image AI2 = env `AI2_E2E_IMAGE` (mặc định build `ai-service/Dockerfile.ai2` → `ai2:e2e-local`); one-shot `ai2-migrate` (cùng image, `python -m app.db.migrate --bootstrap`, admin URL tới `pg`); container AI2 (env như compose P2-F2.16, `AI2_SERVICE_HMAC_SECRET` sinh ngẫu nhiên mỗi session, `AI2_JOB_SWEEP_INTERVAL_SECONDS=2`, không cấu hình LLM, request `policy_flags.egress_allowed=false`).
  - Backend in-process: đặt `DATABASE_URL` (asyncpg tới port host), `AI2_BASE_URL`, `AI2_SERVICE_HMAC_SECRET`, `AI_SERVICE_MODE=http` **trước** lần gọi `get_settings()` đầu, rồi `get_settings.cache_clear()`. Chạy Backend `alembic upgrade head` (thư mục `backend/alembic`) **trước** và **sau** `ai2-migrate` (thứ tự và tính idempotent).
  - Mức L1 (ưu tiên): seed `DossierORM`, `DocumentORM`, `ManifestORM(status="confirmed")`, `ManifestItemORM`, `PipelineRunORM` (snapshot trong `config_snapshot`, đọc qua `_durable_snapshots_from_run` `worker.py:118`) rồi gọi `worker._run_ai2_if_ready`. Mức L2 (dự phòng nếu L1 không khả thi ở bước 1): `submit_ai2_processing` → `poll_ai2_processing` → `persist_ai2_processing_result` → `_persist_ai2_snapshot_identity` với một `pipeline_run` tối thiểu. Mức dùng ghi vào `verification-P3.json`.
  - Input: `evals/data/golden/snapshots/G01.json` (giả lập, A) + 3 câu có `required_spans` và 1 câu không trả lời được từ `evals/data/golden/questions.json`.
  - Helper: `restart_ai2()` → restart container, **luôn resolve lại port host**, chờ `/healthz` (deadline 60 s); `wait_job(job_id, deadline=120 s)` poll 0,5 s; `normalize(resp)` chỉ bỏ `VOLATILE_KEYS` lấy từ B (vd `request_id`, `trace_id`, `latency_ms`), test tự kiểm danh sách này ⊆ tập B khai báo.
- **F3.5 Kịch bản** (`test_backend_ai2_e2e.py`, mỗi kịch bản một test, không `sleep` cố định):
  - **E1 submit → poll → persist:** job `SUCCEEDED`; `pipeline_run.ai2_result_digest` có; `dossier.metadata_json["ai2_snapshot_digest"] == result["query_snapshot_digest"]`; result validate với `docs/contracts/ai2.be.processing.result.v1.schema.json`.
  - **E2 query có citation:** `query_ai2` với digest đã lưu → 3 câu có `required_spans` trả state thuộc tập cho phép và ≥ 1 citation có `page` + `line_ids`; câu không trả lời được → `INSUFFICIENT_EVIDENCE`, 0 giá trị bịa trong `answer`; response validate schema `ai2.query.v1` của B.
  - **E3 restart:** lưu 4 response chuẩn hoá → `restart_ai2()` (DB giữ nguyên) → hỏi lại → 4/4 bằng nhau (hồi quy cho lỗi hiện tại). Ghi lại port trước/sau restart (probe).
  - **E4 job kẹt:** chèn qua SQL (role migrator) một job `QUEUED` hợp lệ (request copy từ E1, idempotency key mới, envelope đã hết hạn) → `restart_ai2()` → sweep đưa tới `SUCCEEDED` trong deadline; Backend gửi lại cùng (key, attempt) → cùng `job_id`, `updated_ms`/`wire_json` không đổi.
  - **E5 retry attempt mới:** `retry_ai2_processing` → `job_id` khác, result `attempt == 2`, `query_snapshot_digest` khác digest cũ; Backend cập nhật `ai2_snapshot_digest` và `ai2_result_json.attempt == 2`; query bằng digest cũ → `INSUFFICIENT_EVIDENCE` + trace `AI2_QUERY_EVIDENCE_CONTEXT_REQUIRED` (`main.py:776-806`); bằng digest mới → có citation.
  - **E6 nonce replay:** cùng envelope/nonce, payload khác → HTTP 409 `SERVICE_NONCE_REPLAY`.
  - **E7 quyền (chỉ khi ADR-14 Accepted):** `ai2_app` bị `permission denied` khi `SELECT` bảng Backend ở `public`, `CREATE TABLE public.x`, `CREATE TABLE ai2.x`; role ít quyền mới tạo bị từ chối `SELECT * FROM ai2.jobs`; `public.alembic_version` giữ revision Backend, `ai2.alembic_version` = `0001_ai2_initial`.
  - **E8 không rò dữ liệu nhạy cảm:** log container AI2 (`get_logs()`) và `caplog` Backend không chứa chuỗi canary lấy từ snapshot G01, HMAC secret, mật khẩu DB.
  - **E9 (chỉ phương án dự phòng):** xoá file state SQLite trong volume AI2 + restart → `/query` trả `AI2_QUERY_EVIDENCE_REQUIRED` → `retry_ai2_processing` → trả lời lại có citation.
  - Mỗi test ghi một dòng vào `e2e-summary.json` (tên, pass/fail, thời gian, `job_id`, không văn bản hợp đồng).

### 3c — CI và tài liệu
- **F3.6 `.github/workflows/e2e-backend-ai2.yml`:**
  - Trigger: `pull_request` paths `backend/**`, `ai-service/**`, `docker-compose.yml`, `docs/contracts/**`, `evals/data/golden/**`, `.github/workflows/e2e-backend-ai2.yml`; `push` lên `develop`/`main`; `workflow_dispatch` input `ai2_image` (tag@digest GHCR của B cho release).
  - `permissions: contents: read`; job dispatch thêm `packages: read`. Không `pull_request_target`, không secret (HMAC sinh trong test). `concurrency` theo ref, `timeout-minutes: 30`. Mọi `uses:` pin SHA 40 ký tự (quy ước A F4.7).
  - Bước: checkout; setup-python theo `backend-ci.yml:27-30` (3.11); `pip install uv`; `cd backend && uv sync --frozen --extra dev`; PR: `docker build -f ai-service/Dockerfile.ai2 -t ai2:e2e-local ai-service`; dispatch: `docker pull "$AI2_IMAGE"` (input qua `env:`); chạy `AI2_E2E=1 AI2_E2E_REQUIRE_DOCKER=1 uv run pytest tests/e2e -m e2e -v --junitxml=e2e-junit.xml`; upload `e2e-junit.xml` + `e2e-summary.json` (`if: always()`).
- **F3.7 Tài liệu current-state:**
  - `docs/system-architecture.md`: state AI2 ở schema `ai2` (hoặc SQLite theo 2c′), sweep + claim nguyên tử, record lazy, 1 replica; E2E là bằng chứng mức CI, không phải HA (giữ các cảnh báo `:30`, `:87`).
  - `docs/code-standards.md`: AI2 chỉ truy cập DB qua `app/db` + `app/tools/jobs.py`; role app không DDL; không `uuid4` cho ID đầu ra pipeline; lệnh E2E; biến `AI2_REQUIRE_DOCKER`/`AI2_E2E_REQUIRE_DOCKER`.
  - `ai-service/README.md` mục "State và E2E": biến môi trường, bootstrap/migrate, dự phòng SQLite, lệnh E2E Windows/Linux, SQL purge tay (VD-C4), SQL gỡ schema/role (chỉ khi được duyệt).

Phi chức năng:
- Một lượt E2E ≤ 15 phút trên `ubuntu-latest` `[ASSUMED]`.
- Tất định: không phụ thuộc mạng ngoài/LLM; deadline tường minh.

## Related Code Files
**Create**
- `backend/tests/e2e/__init__.py`, `backend/tests/e2e/conftest.py`, `backend/tests/e2e/test_backend_ai2_e2e.py`
- `backend/tests/unit/test_ai2_attempt_supersede.py`
- `.github/workflows/e2e-backend-ai2.yml`

**Modify**
- `backend/src/contract_intelligence/shared/ai/canonical_processing.py`
- `backend/src/contract_intelligence/shared/ai/persistence.py`
- `backend/src/contract_intelligence/worker.py`
- `backend/pyproject.toml`, `backend/uv.lock` (`backend/requirements.txt` là export `--no-dev`, không đổi vì chỉ thêm dev dep)
- `docs/system-architecture.md`, `docs/code-standards.md`, `ai-service/README.md`

**Delete** — không có.

## File inventory

| File | Hành động | Nhóm | Cỡ | Tác động test |
|---|---|---|---|---|
| `canonical_processing.py` | M | 3a | ~5 dòng | unit mới + test hiện có |
| `persistence.py` | M | 3a | ~80 dòng | `test_ai2_attempt_supersede.py`, `tests/unit/test_ai2_result_persistence.py`, `tests/integration/test_ai2_review_fixes_flow.py` |
| `worker.py` | M | 3a | ~70 dòng (tách helper + hàm retry) | `tests/unit/test_worker_pipeline_run.py` |
| `test_ai2_attempt_supersede.py` | C | 3a | ~220 dòng | SQLite in-memory như `tests/integration/conftest.py` |
| `tests/e2e/*` | C | 3b | ~250 + ~350 dòng | Docker |
| `backend/pyproject.toml`, `uv.lock` | M | 3b | marker + dev dep | toàn suite Backend (`--strict-markers`) |
| `e2e-backend-ai2.yml` | C | 3c | ~80 dòng | chạy thật trên CI |
| 3 file tài liệu | M | 3c | ~1 trang tổng | — |

## Implementation Steps
0. **Cổng:** đọc `artifacts/verification-P1.json` và `verification-P2.json`. ADR-14 chưa quyết định hoặc P2 chưa PASS → dừng. `Rejected` mà plan chưa sửa + duyệt lại → dừng.
1. **Probe → RED** (máy có Docker hoặc CI): (a) Backend in-process mức L1 có chạy được với Postgres testcontainer không (import `worker.py` kéo `aiokafka` `:20` nhưng `_run_ai2_if_ready` không gọi Kafka); ghi mức L1/L2. (b) Port host của container sau restart có đổi không (ghi quan sát; harness vẫn resolve lại). (c) Xác định discriminator xoá `FactORM` của AI2 cho một run và kiểm tra tham chiếu `CitationORM` dùng chung; nếu không chứng minh được ownership + không còn tham chiếu → dừng 3a supersede, báo main (Câu hỏi mở 5), không xoá citations theo dossier/document.
2. **3a RED:** `test_ai2_attempt_supersede.py`: `test_higher_attempt_supersedes_projection`, `test_same_attempt_different_digest_conflicts`, `test_lower_attempt_is_ignored`, `test_stale_attempt_completion_does_not_rewind_current_digest` (attempt N+1 persist trước N), `test_supersede_preserves_shared_non_ai2_citation`, `test_supersede_blocked_when_review_action_exists`, `test_supersede_fails_closed_without_citation_ownership_proof`, `test_build_request_carries_attempt`, `test_retry_uses_result_query_snapshot_digest`, `test_digest_mismatch_fails_closed`. Chạy → đỏ.
3. **3a GREEN:** F3.1–F3.3. `uv run pytest tests/unit tests/architecture tests/integration -q` xanh; ruff, format, mypy, import-linter sạch. Commit `feat(backend): supersede AI2 result by attempt and retry entrypoint`.
4. **3b RED:** viết harness + E1–E8; chạy trên CI/Docker → các kịch bản cần 3a/P2 đỏ đúng chỗ (ghi output).
5. **3b GREEN:** sửa đến khi 8/8 xanh. Không nới deadline quá 2× giá trị ban đầu mà không ghi lý do. Commit `test(e2e): backend-ai2 end-to-end suite with testcontainers`.
6. **3c:** workflow F3.6 (lấy SHA action bằng `git ls-remote`); HC-C2 (mentor duyệt `/.github/`).
7. Chạy workflow 3 lượt liên tiếp trên cùng SHA → ghi 3 URL.
8. Tài liệu F3.7. Commit `docs: AI2 state, E2E and runbook`.
9. Regression gate.

## TDD
### Tests Before (RED)
- [ ] 10 test đơn vị ở bước 2 (Backend, SQLite in-memory) — đỏ vì chưa có tham số `attempt`, supersede, stale-completion guard, citation ownership guard, `retry_ai2_processing`.
- [ ] E1–E8 (Docker): E1/E2/E3/E6/E8 kỳ vọng xanh ngay khi P2 đã xong (xác nhận harness); **E4, E5, E7 là RED thật** (E5 cần 3a; E4 cần sweep P2 chạy trong container; E7 cần bootstrap 2c). Nếu E3 đỏ sau P2 → đó là lỗi của P2, quay lại P2.

### Implement
Bước 3, 5, 6.

### Tests After
- [ ] `tests/unit/test_worker_pipeline_run.py`, `tests/unit/test_ai2_result_persistence.py`, `tests/unit/test_ai2_read_model_completeness.py`, `tests/integration/test_ai2_review_fixes_flow.py` xanh không sửa.

### Regression Gate
- `cd backend; uv sync --frozen --extra dev; uv run pytest tests/unit tests/architecture tests/integration -q` → 0 failed (Windows + Linux).
- `uv run ruff check src/ tests/; uv run ruff format --check src/ tests/; uv run mypy src/; uv run python -m import_linter --config .importlinter` → exit 0.
- CI Linux: `cd backend && AI2_E2E=1 AI2_E2E_REQUIRE_DOCKER=1 uv run pytest tests/e2e -m e2e -v` → 8/8 passed, 0 skipped.
- Windows không Docker: `cd backend; $env:AI2_E2E="1"; uv run pytest tests/e2e -m e2e` → 8 skipped với lý do "Docker không khả dụng" (VD-C5a); không có `AI2_E2E` → cả thư mục skip.
- ai-service suite offline của P2 vẫn 0 failed.

## Test scenario matrix

| Mức | Kịch bản | Test |
|---|---|---|
| Critical | Câu trả lời đổi sau restart AI2 | E3 |
| Critical | Retry attempt mới không cập nhật được Backend (Conflict) / query dùng digest cũ vẫn trả lời | E5, `test_higher_attempt_supersedes_projection` |
| Critical | Supersede xoá công sức review của người | `test_supersede_blocked_when_review_action_exists` |
| Critical | Rò quyền giữa `ai2` và `public` | E7 |
| High | Job kẹt / envelope hết hạn làm job chết | E4 |
| High | Replay nonce | E6 |
| High | Digest hai phía lệch âm thầm | `test_digest_mismatch_fails_closed`, E1 |
| High | Log lộ dữ liệu | E8 |
| Medium | E2E flaky do port/timing | resolve lại port, deadline, 3 lượt CI xanh |
| Medium | E2E skip âm thầm trên CI | `AI2_E2E_REQUIRE_DOCKER=1` |

## Success Criteria
- [ ] (test) 7/7 test `test_ai2_attempt_supersede.py` xanh; suite Backend `tests/unit tests/architecture tests/integration` 0 failed; ruff/format/mypy/import-linter sạch.
- [ ] (test, CI Linux) E2E **8/8 passed, 0 skipped** (fallback: E1–E6, E8, E9 = 8/8); 3 lượt workflow liên tiếp xanh trên cùng SHA (3 URL trong `verification-P3.json`).
- [ ] (invariant) `verification-P3.json` ghi: mức in-process (L1/L2), port trước/sau restart, image AI2 đã dùng (tag hoặc digest), thời gian từng kịch bản.
- [ ] (invariant) Workflow: không `secrets.`, không `pull_request_target`, `contents: read`, mọi `uses:` pin SHA (A `evals/tests/test_ci_workflows.py` xanh nếu nó quét mọi workflow).
- [ ] (manual — `manual_test_anchor.py`) HC-C2: chủ Backend xác nhận VD-C1; mentor duyệt workflow (URL).
- [ ] (invariant) 3 tài liệu F3.7 cập nhật; không claim HA/production recovery.

## Risk Assessment

| Rủi ro | Khả năng × Tác động | Giảm thiểu |
|---|---|---|
| R3-1: Backend in-process L1 không khả thi (seed phức tạp, import side effect) | Trung × Trung | Mức L2 dùng đúng các hàm Backend thật; ghi mức đã dùng |
| R3-2: Không xoá được fact AI2 theo run (thiếu discriminator) | Trung × Cao | Bước 1(c) phát hiện sớm; dừng và hỏi (có thể cần migration Backend) thay vì xoá theo document một cách mù |
| R3-3: Supersede đổi hành vi Backend đang dùng | Trung × Cao | VD-C1 + HC-C2; attempt bằng vẫn Conflict; test hiện có không sửa phải xanh |
| R3-4: Build image AI2 chậm trên CI | Trung × Trung | Cache layer (`uv` cache mount có sẵn trong Dockerfile); timeout 30 phút |
| R3-5: Chưa có schema `ai2.query.v1`/`query_snapshot_digest` của B | Trung × Trung | Dùng fallback digest cũ + chỉ validate result v1; ghi thiếu hụt; không tự viết schema thay B |
| R3-6: Windows dev không chạy được E2E | Cao × Thấp | VD-C5; skip có lý do; CI là nơi nghiệm thu |
