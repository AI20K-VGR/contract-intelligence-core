---
id: 260929-2323-ai2-c-integration
title: "AI2-C integration: Postgres schema ai2, Backend-AI2 E2E, quality to 95"
description: "Chuyển trạng thái AI2 sang schema ai2 trong Postgres của Backend (cổng ADR-14), lưu record đã xử lý và làm chunk tất định để câu trả lời giống hệt sau restart, E2E Backend↔AI2 bằng testcontainers, gỡ luật rò rỉ fixture và đưa chỉ số lên ≥ 95% rồi bật enforce_thresholds_in_pr."
status: pending
priority: P1
effort: "12–16 ngày công agent + thời gian chờ ADR-14 (Architecture Lead) và các mốc duyệt HC-C1..HC-C4"
mode: hard
tdd: true
branch: feature/code-full
tags: [ai2, postgres, adr-14, e2e, testcontainers, determinism, quality, evals]
created: 2026-09-29
author: 
decisions: []
phases:
  - phases/phase-1-adr14-gate.md
  - phases/phase-2-storage-postgres-ai2.md
  - phases/phase-3-backend-ai2-e2e.md
  - phases/phase-4-quality-to-95.md
harness_version: 6.3.0
harness_kit_digest: 672de2e098c3cb8451018791788f1052b1b812ccec08a1f124191bd8bbc04ebd
harness_schema_version: 1.0
---

# Plan: AI2-C integration: Postgres schema ai2, Backend-AI2 E2E, quality to 95

> hs:cook đọc file này làm hợp đồng. Nhãn: **OBSERVED** (đã chạy lệnh/đọc code, có `file:line`), **DERIVED** (tính từ dữ liệu đã quan sát), `[ASSUMED]` (chưa kiểm), `[PRIOR]` (kiến thức nền chưa kiểm lại). Lệnh chạy từ root repo. `$PY` = `.\ai-service\.venv\Scripts\python.exe` (Windows, kèm `$env:PYTHONIOENCODING="utf-8"`) hoặc `ai-service/.venv/bin/python` (Linux/CI). Research đầu vào: `research/postgres-e2e-quality.md` (kể cả phụ lục probe của main). Các mục `VD-C*` là quyết định **chờ người dùng chốt ở bước validate**; cột "Khuyến nghị" là mặc định cook dùng nếu người dùng đồng ý.

## Tổng quan

C tích hợp AI2 vào hệ thống thật sau khi A (đo lường) và B (dịch vụ có version) xong. Ba việc:

1. **Trạng thái AI2 bền và đúng sau restart.** Hiện tại job/nonce nằm trong SQLite (`ai-service/app/tools/jobs.py:24-25`) và lúc khởi động AI2 chỉ **adapt lại request** (`ai-service/app/api/main.py:83-116`), bỏ mất toàn bộ phần `run_idp` ghi vào record → câu trả lời lệch sau restart (probe của main, research phụ lục). Thêm nữa `chunk_id` sinh bằng `uuid4()` (`ai-service/app/pipeline/clause.py:18,29`) nên **chạy lại `run_idp` không bao giờ cho cùng record** (PB-C1). C (a) lưu record **sau** `run_idp` cùng transaction với `SUCCEEDED` và nạp lại từ đó, (b) làm ID đầu ra của pipeline tất định, (c) chuyển state sang schema `ai2` trong Postgres của Backend (D-3) — phần này chờ ADR-14.
2. **E2E Backend ↔ AI2 chạy lại được** (D-2): submit → poll → Backend persist → query có citation → restart AI2 vẫn trả lời giống hệt → retry `attempt` mới → Backend cập nhật digest; job kẹt `QUEUED` được chạy lại; chạy trên image/contract có version của B.
3. **Chất lượng ≥ 95% không nhờ rò rỉ.** Gỡ các nhánh khớp câu hỏi thi trong `ai-service/app/reasoning/l0_rules.py:336-394` (PB-11 của A), thay bằng cơ chế tổng quát; allowlist của `evals/tests/test_no_eval_leakage.py` (A) về rỗng; `threshold_verdict = PASS` theo bộ chấm của A; bật `enforce_thresholds_in_pr`.

Cắt YAGNI: không SKIP LOCKED/poller (1 replica), không thư viện queue, không compose profile `e2e` (compose sẵn có đủ cho demo tay), không đụng lane Kafka của AI2 (`app/tools/query_store.py`, `app/transport/kafka_idp_worker.py:174`), không Backend least-privilege role (VD-C2).

## Quyết định đã khoá
Chốt qua AskUserQuestion ngày 29–30/09/2026 (không re-litigate). Nguồn đầy đủ: `plans/260929-2323-ai2-a-measure-baseline/plan.md` mục "Quyết định đã khoá" và "Quyết định validate".

| # | Quyết định |
|---|---|
| D-1 | Đóng gói AI2 = image Docker có tag semver trên **GHCR của repo** + HTTP API; Backend gọi qua HTTP và pin đúng tag |
| D-2 | E2E = **chỉ Backend ↔ AI2** (không AI1/OCR, không Keycloak) |
| D-3 | Lưu trữ AI2 = **schema `ai2` trong Postgres của Backend** (P2); trái ADR-02 nên cần **ADR-14** do Architecture Lead duyệt |
| D-4 | Phạm vi EXPANSION: observability (metrics/log/trace), CI đầy đủ, chi phí LLM |
| D-5 | **Bật LLM trong Sprint 2** cho cả xử lý hồ sơ và hỏi đáp; LLM = OpenAI `gpt-4o-mini`; chỉ gửi dữ liệu giả lập/ẩn danh cho tới khi provider được duyệt cho dữ liệu thật |
| D-6 | Ngưỡng chặt (D-A8): 0 giá trị bịa, 100% citation đúng, chỉ số khác ≥ 95%, p95 < 20 giây (chỉ tính lượt dùng LLM, VD-7); PR chặn hồi quy, **release của B/C bắt buộc `threshold_verdict = PASS`** (VD-2) |
| D-7 | Benchmark LLM thật **chỉ chạy tay**, bắt buộc chạy trước mỗi release B/C (VD-5, VD-8) |
| D-8 | Thứ tự: A đo lường → B dịch vụ có version → C tích hợp; B và C đo bằng bộ chấm của A |

## Bằng chứng nền (probe của planner và main, 30/09/2026)

| # | Quan sát | Nhãn |
|---|---|---|
| PB-M1 | Probe của main (research phụ lục): `adapt_be_ai2_processing_request` giống hệt giữa `PYTHONHASHSEED` 1/2; request thô vs `sort_keys` giống hệt → hai giả thuyết hash-seed/`sort_keys` **bị loại** | OBSERVED (main) |
| PB-M2 | Record sau `adapt` ≠ record sau `run_idp` (facts và phần do bước xử lý ghi) → hydrate hiện tại (`main.py:83-116`, chỉ adapt lại request) **thiếu hậu xử lý** → nguyên nhân chính | OBSERVED (main) |
| PB-M3 | `run_idp` seed 1/2/3 cho 3 hash khác nhau, **chỉ phần `chunks` khác** | OBSERVED (main) |
| PB-C1 | Planner chạy lại trong **cùng một process, cùng `PYTHONHASHSEED=1`**, 2 lượt `run_idp` trên fixture `tests/test_clause_compare.py::_request`: `chunks` vẫn khác (`chk_ae9f9d50…` vs `chk_2c6fc8b4…`), mọi phần khác của `record_to_dict` giống hệt. Gốc là `chunk_id=f"chk_{uuid4().hex[:8]}"` (`app/pipeline/clause.py:18,29`), **không phải hash seed**. `cand_clause_*` đã tất định (băm, `app/pipeline/clause_compare.py:444`); còn 2 chỗ sinh ID ngẫu nhiên trong đầu ra kết quả: `app/pipeline/compare.py:416` (`cand_`), `:468` (`iss_`) | OBSERVED (planner) |
| PB-C2 | `run_idp` sửa record tại chỗ (`app/pipeline/idp.py:111,290-293`) và `mem.put(record)` (`:114,304`) → record đã xử lý = `adapted.record` sau khi `run_idp` trả về; serializer có sẵn `record_to_dict/record_from_dict` (`app/tools/persist.py:46-118`) phủ đủ mọi field của `DossierRecord` (`app/tools/store.py:23-54`) | OBSERVED |
| PB-C3 | Envelope: TTL mặc định 300 s (`app/security/service_envelope.py:54`), trần `AI2_SERVICE_MAX_TTL_SECONDS` 3600 s (`:106`), lệch đồng hồ 30 s (`:105`), hết hạn khi `expires_at <= now - skew` (`:109`). Worker verify lại envelope (`main.py:169`) → job cũ hơn TTL không bao giờ chạy lại được | OBSERVED |
| PB-C4 | Backend chạy bằng `ci` = `POSTGRES_USER` (superuser) ở `docker-compose.yml:194,276,386`. `backend/alembic/versions/v2__create_app_user.py` tạo **bảng** `app_user`, không phải DB role | OBSERVED |
| PB-C5 | Backend: `attempt` gán cứng 1 (`backend/src/contract_intelligence/shared/ai/canonical_processing.py:342`); `persist_ai2_processing_result` **raise `Ai2PersistenceConflict`** khi run đã có digest khác (`shared/ai/persistence.py:895-899`); `_run_ai2_if_ready` bỏ qua run đã có `ai2_result_digest` (`worker.py:~481-485`). → "retry với attempt mới" hiện **không có đường** ở Backend. DOC-04 §5: "Result chỉ được nhận cho attempt/lease đang active; result trả về cho attempt cũ bị bỏ" (`docs/DOC-04-architecture.md:281`) | OBSERVED |
| PB-C6 | `/query` khi thiếu record trả `INSUFFICIENT_EVIDENCE` + `AI2_QUERY_EVIDENCE_REQUIRED` (`main.py:849-869`); khi digest lệch trả `AI2_QUERY_EVIDENCE_CONTEXT_REQUIRED` (`main.py:776-806`) | OBSERVED |
| PB-C7 | Máy dev Windows **không có Docker** (`docker` không có trong PATH, không có Docker Desktop). `ai-service/.venv`: Python 3.12.14, SQLite 3.53.1 (hỗ trợ `RETURNING`), chưa có `sqlalchemy`. `backend/.venv` chưa tồn tại | OBSERVED |
| PB-C8 | Backend `get_settings()` có `@lru_cache(maxsize=1)` (`backend/src/contract_intelligence/config/settings.py:390-391`); CI Backend: Python 3.11, `uv sync --frozen --extra dev`, ruff check + format, mypy, import-linter, `pytest tests/unit`, `tests/architecture`, `tests/integration` (`.github/workflows/backend-ci.yml:19-150`); pytest `--strict-markers`, `testpaths=["tests"]` (`backend/pyproject.toml:147-162`) | OBSERVED |
| PB-C9 | Luật rò rỉ fixture: `l0_rules.py:336-344` ("điều 3"), `:346-355` ("thanh toán"), `:357-370` ("phụ lục 7" → `cl_9`), `:372-379` (USD → `field_usd`), `:381-393` (xây lắp → `field_penalty_*`). Thêm literal id fixture ở `app/reasoning/gold.py:8-17` (`LABEL_CITE`, gồm `cl_9`). Logic so sánh currency/unit/scope/condition có sẵn ở `app/pipeline/compare.py:220-300` (`_pair`); `bm25_lite_score` có sẵn (`l1_retrieval.py:494-520`) nhưng `_lexical_hits` (`:301-320`) không dùng | OBSERVED |
| PB-C10 | Đã có read model bền thứ hai cho record: `app/tools/query_store.py` (SQLite `runs.sqlite`, lane Kafka) | OBSERVED |

## Ràng buộc (constraint-scan)

- **Zone ghi file.** `harness/data/ownership.yaml:8-16` chỉ ràng buộc script harness (`docs/`, `plans/`, …). Path của C không bị chặn.
- **Stage policy.** `harness/data/stage-policy.yaml:62-64`: bước `pr` cần `verification`, `review-decision`, `plan-approval` → P4 phát `review-decision.json` cho toàn bộ diff của C.
- **CODEOWNERS / PR guard.** `/.github/` cần mentor (`.github/CODEOWNERS:3`) → workflow E2E mới cần mentor duyệt (HC-C2). Path đã khoá của A (`evals/baselines/**`, `evals/cards/**`, `evals/data/golden/manifest.json`) cần label `ai2-baseline-update` + CODEOWNER (A RT-01) → P4.
- **Code standards.** `docs/code-standards.md:47-51`: lỗi có code ổn định; không log secret/HMAC/văn bản hợp đồng; scope tenant/dossier/actor/attempt/idempotency bắt buộc trên biên Backend↔AI2. `:59`: đổi schema/API/CLI công khai phải ghi before/after, caller, migration, rollback. `:61`: không giả định working tree sạch.
- **Kiến trúc.** `docs/DOC-04-architecture.md:93` (ADR-02: `ai-service` không kết nối PostgreSQL, không sở hữu queue/lease) và `:94` (ADR-03: không thêm second state store) → ADR-14 bắt buộc (D-3). Governance: thay đổi ADR phải có dòng change record (`docs/DOC-04-architecture.md:981-985`).
- **Tiền đề cook.** WIP trên `feature/code-full` (git status: `l0_rules.py`, `l1_retrieval.py`, `stack.py`, … đang `M`) phải được commit trước; A và B đã merge các phần C phụ thuộc (mục "Tiền đề ngoài plan").

## Kiến trúc và luồng dữ liệu

```
POST /jobs/idp ─verify envelope (1 lần)─► adapt ─► JobStore.create_or_get  [tx: nonce(expires_ms) + job(QUEUED, tenant, actor_id)]
      └─► BackgroundTasks: _run_wire_job(job_id)
Sweeper (startup + mỗi AI2_JOB_SWEEP_INTERVAL_SECONDS) ─► list_stranded (QUEUED quá grace | RUNNING hết lease) ─► executor: _run_wire_job(job_id)
                                                       └─► purge_expired_nonces
_run_wire_job(job_id): đọc row (request_json, tenant_id, actor_id) ─► adapt (KHÔNG verify lại envelope)
   ─► claim: UPDATE … WHERE status='QUEUED' OR (RUNNING AND lease hết) RETURNING worker_token  (lease = max_processing_seconds + 30 s)
   ─► run_idp(adapted.record) ─► complete [tx: UPDATE jobs (fenced by worker_token) + UPSERT dossier_record(gzip(record_to_dict)) khi attempt ≥ attempt đã lưu]
   ─► STORE.put(record)
POST /query ─► STORE.get(tenant, dossier) ─miss─► load dossier_record ─► decode ─► put ─► kiểm digest ─► QueryRouter
Backend: _run_ai2_if_ready (attempt 1) | retry_ai2_processing (attempt n+1) ─► submit/poll/persist(supersede theo attempt) ─► dossier.metadata.ai2_snapshot_digest = result.query_snapshot_digest (B)
```

**Schema `ai2`** (`MetaData(schema="ai2")`; SQLite dùng `schema_translate_map={"ai2": None}`):

| Bảng | Khoá / cột chính | Ghi chú |
|---|---|---|
| `ai2.jobs` | PK `job_id`; `tenant_id, dossier_id, actor_id` (mới), `request_id, idempotency_key, attempt, status, request_json, wire_json, result_json, request_fingerprint, worker_token, lease_until_ms, created_ms, updated_ms`; `UNIQUE(tenant_id, idempotency_key, attempt)`; index `(tenant_id, dossier_id, updated_ms)`, `(status, updated_ms)` | tương đương `jobs.py:68-90` + `actor_id` |
| `ai2.service_nonces` | PK `(tenant_id, nonce)`; `payload_fingerprint, job_id, created_ms, expires_ms` (mới); index `expires_ms` | `expires_ms = (envelope.expires_at + skew) * 1000` (PB-C3) |
| `ai2.dossier_record` | PK `(tenant_id, dossier_id)`; `job_id, attempt, record_schema_version, codec='gzip+json', payload (bytea/BLOB), size_bytes, sha256, updated_ms` | chỉ bản hiện hành của mỗi dossier |
| `ai2.alembic_version` | | tách khỏi `public.alembic_version` của Backend |

**Role (Postgres):** `ai2_migrator` (chủ schema, DDL, chỉ dùng bởi one-shot `ai2-migrate`); `ai2_app` (DML trên `ai2.*`, `CONNECTION LIMIT 20`, `statement_timeout=30s`, `search_path=ai2`). Bootstrap role/schema bằng bước admin (`python -m app.db.migrate --bootstrap` với `AI2_DB_ADMIN_URL`), **không** qua `initdb.d` (volume `backend_pgdata` đã tồn tại, `docker-compose.yml:199-202`).

### Thay đổi hợp đồng (before / after / ai bị ảnh hưởng / đường chuyển)

| Bề mặt | Before | After | Ai bị ảnh hưởng | Đường chuyển / rollback |
|---|---|---|---|---|
| Env lưu trữ AI2 | `AI2_JOB_DB` (SQLite, `jobs.py:49`) | `AI2_DATABASE_URL`; không đặt → `sqlite:///{AI2_JOB_DB}` nếu có, else `data/ai2/ai2_state.sqlite` | compose, dev, test | Bỏ `AI2_DATABASE_URL` = quay về SQLite trên volume |
| Khởi động AI2 | adapt lại mọi job SUCCEEDED (`main.py:83-121`) | không hydrate eager; record nạp lazy khi `STORE.get` trượt | `/query` | revert commit 2b |
| Worker | verify lại envelope (`main.py:169`) | dùng danh tính đã verify lưu trong row | job requeue | — |
| `chunk_id`, `candidate_id` (`compare.py`), `issue_id` | `uuid4` | băm nội dung, giữ tiền tố `chk_/cand_/iss_` | không consumer nào parse (Backend không lưu `chunk_id`, grep rỗng) | revert commit 2a |
| Backend `persist_ai2_processing_result` | digest khác → Conflict | theo VD-C1: attempt lớn hơn thì supersede, bằng thì Conflict, nhỏ hơn thì bỏ qua | Backend read model | revert commit 3a |
| Backend `build_processing_request` | `attempt: 1` cứng | tham số `attempt: int = 1` | worker | tương thích ngược |
| `/query` | — | thêm trace code `AI2_RECORD_REBUILD_REQUIRED` khi record không giải mã được (VD-C6) | Backend | chuỗi mới trong `reasoning_trace`, không đổi schema |
| Compose | `ai2-service` không phụ thuộc DB | thêm `ai2-migrate`; `ai2-service` depends_on `backend-db` + `ai2-migrate` | dev | rollback compose |

## Features
- `ai2-state-in-postgres` — trạng thái riêng của AI2 (job store, idempotency, nonce, hồ sơ đã xử lý) chuyển sang schema `ai2` trong Postgres Backend, user `ai2_app` chỉ có quyền trên schema đó, migration alembic riêng; hồ sơ dựng lại từ request **và kết quả đã lưu** (sửa lỗi câu trả lời lệch sau khi khởi động lại). Có cổng ADR-14.
- `backend-ai2-e2e` — bộ E2E Backend ↔ AI2 chạy lại được: submit → poll → Backend persist → query có citation → restart AI2 vẫn trả lời → retry với `attempt` mới → Backend cập nhật digest; job kẹt `QUEUED` được gửi lại.
- `quality-uplift-95` — gỡ luật riêng cho fixture trong `l0_rules.py` (allowlist rò rỉ của A về rỗng), vá truy xuất (bảng tóm tắt giá trị, câu VAT thành node riêng), đưa các chỉ số lên ≥ 95% theo bộ chấm của A và bật `enforce_thresholds_in_pr`.

Kế hoạch này là C trong bộ 3 (A `plans/260929-2323-ai2-a-measure-baseline` → B `plans/260929-2323-ai2-b-versioned-service` → **C**).

## Phases
| # | Theme | Phụ thuộc (bắt đầu) | Cổng cấp bước | Cỡ |
|---|---|---|---|---|
| 1 | Adr14 Gate: soạn ADR-14 trong DOC-04, Architecture Lead quyết định (HC-C1) | — | — | S agent (0,5 ngày) + chờ người |
| 2 | Storage Postgres Ai2: 2a ID tất định; 2b store SQLAlchemy Core + lưu record + sweep (kiểm trên SQLite); 2c bind Postgres (role/schema/alembic/compose) | — | **2c chờ P1 = Accepted** (Rejected → 2c′ SQLite trên volume) | L, 3–4 ngày, 3 commit |
| 3 | Backend Ai2 E2e: Backend retry/supersede theo attempt; E2E testcontainers E1–E8; workflow CI; tài liệu current-state | P1, P2 | — | L, 3 ngày |
| 4 | Quality To 95: gap theo lớp lỗi, 3 cơ chế tổng quát, allowlist rỗng, gate PASS, bật enforce | — (tiền đề ngoài: A P2) | **Bước đóng release (F4.10) chờ `verification-P3.json` PASS** | XL, 4–6 ngày |

## Ma trận phụ thuộc và sở hữu file (`--parallel`)

| | P1 | P2 | P3 | P4 |
|---|---|---|---|---|
| P1 | — | cổng bước 2c | **cạnh** P1→P3 | độc lập |
| P2 | | — | **cạnh** P2→P3 | độc lập (không chung file) |
| P3 | | | — | cổng bước F4.10 |
| P4 | | | | — |

Lô chạy song song (antichain, tập file rời nhau): **{P1, P2 (2a+2b), P4}** ngay khi tiền đề ngoài thoả; P2-2c chạy khi P1 xong; P3 sau P1 và P2; P4-F4.10 sau P3. Sở hữu file theo phase: xem `plan-graph.yaml` (mỗi file đúng một phase). Điểm dễ đụng đã tách: `compare.py` thuộc P2 (P4 chỉ import `_pair`, không sửa); `docker-compose.yml` và `.github/workflows/ai-service.yml` thuộc P2; `docs/DOC-04-architecture.md` thuộc P1; `docs/system-architecture.md`, `docs/code-standards.md`, `ai-service/README.md` thuộc P3; `docs/ai2/**` thuộc P4.

## Tiền đề ngoài plan (A, B)

| Từ | Cần gì | Phase C dùng | Nếu chưa có |
|---|---|---|---|
| A P1 | `evals/data/golden/snapshots/G0x.json`, `questions.json` (đã duyệt HC-1), `build_golden --variant-seed` | P3 (input E2E), P4 | P3/P4 dừng ở bước 1 |
| A P2 | `evals/scripts/run_ai2_gate.py`, `evals/tests/test_no_eval_leakage.py` (ALLOWLIST đóng băng), card v2 có `enforce_thresholds_in_pr` (đã duyệt HC-3), baseline offline | P4 | P4 dừng |
| A P3/P4 | marker đã đăng ký (`live`, `llm`, `integration`, `requires_pdf_fixture`), conftest cô lập `.env`, `.github/workflows/ai-service.yml` thật | P2 (thêm marker, env CI) | P2-2c chỉnh lại file tương ứng |
| B P1 | `query_snapshot_digest` trong result; JSON Schema `ai2.query.v1` (`[ASSUMED]` path `docs/contracts/ai2.query.v1.schema.json`); danh sách field volatile của response | P3 (E1, E2, E5) | P3 dùng hàm digest cũ `worker.py:78-110` và chỉ validate result schema v1 |
| B P3 | image AI2 build từ `ai-service/Dockerfile.ai2`, tag `ai2-vX.Y.Z` trên GHCR, `GET /version` | P3 (release dispatch) | PR CI build image cục bộ, release dispatch chờ B |
| B P4 | logger có cấu trúc, allow-list field | P2, P3 (log mới) | dùng `logging` chuẩn, chỉ log id/count/size/code |

## Cổng ADR-14 và phương án dự phòng

- **Accepted** → P2-2c bind Postgres như thiết kế; P3 chạy E1–E8 trên Postgres.
- **Rejected** → phương án B (research): **SQLite trên volume `ai2_data` + Backend resubmit**. Vì store ở P2-2b đã dùng SQLAlchemy Core chạy được trên SQLite, phần thay đổi chỉ là: (1) P2-2c′: bỏ bootstrap role/schema, compose không đặt `AI2_DATABASE_URL` (file `/app/data/ai2/ai2_state.sqlite` trên volume), `ai2-migrate` chạy alembic trên SQLite; (2) P3 bỏ E7 (quyền Postgres), thêm E9 (mất volume AI2 → `/query` trả `AI2_QUERY_EVIDENCE_REQUIRED` → Backend `retry_ai2_processing` → trả lời lại). **Rejected làm đổi nội dung plan → sửa plan và duyệt lại** (approval gắn với nội dung), không cook thẳng.
- Trong lúc chờ: P2-2a/2b và P4 (trừ F4.10) chạy bình thường.

## Mốc duyệt của người (agent không tự làm)

| # | Việc | Người | Bằng chứng | Chặn gì |
|---|---|---|---|---|
| HC-C1 | Duyệt/từ chối ADR-14 (PR sửa `docs/DOC-04-architecture.md`) | Architecture Lead (`docs/DOC-04-architecture.md:9`) | URL review approve hoặc SHA commit đổi trạng thái ADR-14 | P2-2c, P3 |
| HC-C2 | (i) Chủ Backend đồng ý semantics supersede (VD-C1); (ii) mentor duyệt `.github/workflows/e2e-backend-ai2.yml` (`/.github/` CODEOWNER) | chủ Backend + `@hieubui2409` | URL review | merge P3 |
| HC-C3 | Duyệt card bật `enforce_thresholds_in_pr` bằng `evals/scripts/approve_card.py --approved-by "Văn Dũng"`; label `ai2-baseline-update` + CODEOWNER review cho baseline mới | Văn Dũng | SHA commit do Văn Dũng tạo | F4.9 |
| HC-C4 | Release C: chạy benchmark live tay (D-7) + chấp nhận verdict trên tập biến thể mới | Văn Dũng | URL run / file report | F4.10, release |

## Out of scope
- Poller `FOR UPDATE SKIP LOCKED`, nhiều replica, thư viện queue (Celery/RQ/procrastinate) — cần ADR mới khi > 1 replica.
- Role Backend không phải superuser (VD-C2 khuyến nghị để follow-up của Backend).
- Lane Kafka của AI2 (`app/tools/query_store.py`, `app/transport/kafka_idp_worker.py`), session demo `app/tools/persist.py` (`runs.sqlite`), `vectors.sqlite`, P3 `DurableRunStore` (`app/tools/durable.py`) — vẫn SQLite; gộp read model là follow-up (PB-C10).
- Import dữ liệu `data/ai2/jobs.sqlite` cũ (VD-C3 khuyến nghị không import).
- Tự động xoá attempt cũ (VD-C4 khuyến nghị để sau).
- Compose profile `e2e`: demo tay dùng `docker compose up backend-db ai2-migrate ai2-service`.
- Keycloak, AI1/OCR, Kafka trong E2E (D-2). Đo chất lượng qua HTTP; cập nhật DOC-06.
- Hạ ngưỡng D-6 dưới bất kỳ hình thức nào.

## Acceptance (toàn plan)
- [ ] Mỗi phase red→green TDD (P1 là phase tài liệu + cổng người, TDD N/A có lý do); commit riêng từng nhóm; regression gate xanh sau mỗi phase.
- [ ] Lint/type/build (lệnh thật của repo):
  - ai-service: `cd ai-service; .venv/Scripts/ruff.exe check . ../evals` → `All checks passed`; `uv sync --frozen --extra dev --extra web` exit 0 (Windows + Linux). Type-check: N/A (repo không cấu hình cho ai-service).
  - backend: `cd backend; uv sync --frozen --extra dev; uv run ruff check src/ tests/; uv run ruff format --check src/ tests/; uv run mypy src/; uv run python -m import_linter --config .importlinter` → exit 0.
- [ ] (test, Windows + Linux) Tất định: `$PY -m pytest -q -p no:cacheprovider ai-service/tests/test_pipeline_determinism.py` → 3/3 passed (trước: RED, PB-C1).
- [ ] (test, Windows + Linux) Restart không Docker: `test_record_persistence.py::test_query_identical_after_simulated_restart_subprocess` passed — 2 subprocess (`PYTHONHASHSEED` 1 và 2): process 1 xử lý + hỏi 3 câu, process 2 chỉ hỏi → 3/3 response giống hệt sau chuẩn hoá.
- [ ] (test) Suite offline ai-service `-m "not live and not llm" --strict-markers` → 0 failed, 0 error. Trên Windows không Docker: test `requires_docker` **skipped kèm lý do**, số lượng ghi vào `verification-P2.json`. Trên CI Linux (`AI2_REQUIRE_DOCKER=1`): **0 skipped** trong nhóm `requires_docker`.
- [ ] (test, CI Linux) E2E: `cd backend; AI2_E2E=1 AI2_E2E_REQUIRE_DOCKER=1 uv run pytest tests/e2e -m e2e -v` → **8/8 passed, 0 skipped** (E1–E8; fallback: E1–E6, E8, E9), 3 lượt workflow liên tiếp xanh trên cùng SHA (URL trong `verification-P3.json`).
- [ ] (invariant) `evals/tests/test_no_eval_leakage.py` xanh với `ALLOWLIST == []`.
- [ ] (test) `$PY evals/scripts/run_ai2_gate.py --mode pr --base-ref origin/develop` với ngưỡng enforce → exit 0; `threshold_verdict = PASS` cả 2 domain; mọi chỉ số có gate n ≥ 60 và in `x/n` + Wilson + cluster CI; tripwire (`citation_correct` 100%, `value_fabricated` 0, `fact_value_fabricated` 0) sạch.
- [ ] (manual — `manual_test_anchor.py`) HC-C1: trạng thái ADR-14 + bằng chứng ghi trong `verification-P1.json`.
- [ ] (manual — `manual_test_anchor.py`) HC-C3/HC-C4: card `enforce_thresholds_in_pr: true` duyệt bởi Văn Dũng (SHA); verdict tập biến thể seed mới = PASS; benchmark live không có tripwire hồi quy.
- [ ] (invariant) Không log văn bản hợp đồng/khoá: E8 + `test_no_sensitive_values_logged` (P2) xanh.
- [ ] `review-decision.json` verdict `PASS` (P4).

## Test matrix (tóm tắt)

| Tầng | Cái gì | Ở đâu |
|---|---|---|
| Unit | ID tất định; codec record round-trip + đủ field; claim nguyên tử; lease theo budget; nonce TTL; sweep; worker không verify lại; lazy load; Backend supersede/conflict/stale; structural refs, comparability, retrieval views | `ai-service/tests/*`, `backend/tests/unit/test_ai2_attempt_supersede.py` |
| Integration | Store trên SQLite + Postgres (testcontainers); alembic multi-schema, `version_table_schema`, autogenerate rỗng khi có bảng `public`; quyền role; bootstrap idempotent; restart mô phỏng bằng subprocess | `test_job_store.py`, `test_ai2_postgres_schema.py`, `test_record_persistence.py` |
| E2E | E1–E8 (E9 fallback) trên container AI2 + Postgres, Backend in-process | `backend/tests/e2e/`, workflow `e2e-backend-ai2.yml` |
| Eval | Gate A (PR, enforce) + tập biến thể seed mới + live (tay) | P4 |

## Rollback
- Mỗi nhóm là commit riêng; `git revert <range>` rồi chạy lại regression gate của phase trước.
- P1: revert commit DOC-04.
- P2: 2a revert → ID ngẫu nhiên trở lại (vô hại, mất tính tất định). 2b revert → store SQLite cũ + hydrate eager; file `ai2_state.sqlite` bị bỏ qua. 2c revert → compose về SQLite; schema/role `ai2` để lại trong DB là vô hại; xoá chỉ khi được duyệt: `DROP SCHEMA ai2 CASCADE; DROP ROLE ai2_app; DROP ROLE ai2_migrator;` (admin, ghi trong README P3).
- P3: revert 3a → Backend trở lại Conflict khi digest đổi; disable workflow E2E.
- P4: revert phải gồm cả thay đổi ALLOWLIST (không thì lint đỏ); tắt enforce cần card mới qua HC-C3.

## Risks

| # | Rủi ro | Khả năng × Tác động | Giảm thiểu |
|---|---|---|---|
| R1 | ADR-14 chậm/bị từ chối làm tắc toàn plan | Trung × Cao | Cổng cấp bước: 2a/2b/P4 không chờ; fallback 2c′/E9 đã thiết kế; store dialect-agnostic |
| R2 | Chạy lại `run_idp` vẫn lệch vì nguồn ngẫu nhiên khác | Thấp × Cao | Không rehydrate bằng `run_idp` nữa (lưu record); lint cấm `uuid4` trong `app/pipeline` ngoài 4 chỗ allowlist; test 2 subprocess khác seed + cùng seed |
| R3 | AI2 làm cạn tài nguyên DB dùng chung với Backend | Trung × Cao | `CONNECTION LIMIT 20`, `statement_timeout 30s`, pool 5+5, retention (VD-C4), size record đo và báo |
| R4 | Alembic của AI2 đụng bảng Backend / hai `alembic_version` đè nhau | Trung × Cao | `version_table_schema="ai2"`, `include_schemas` + `include_name` chỉ `ai2`; test autogenerate rỗng khi `public` có bảng; E2E chạy Backend upgrade trước và sau `ai2-migrate` |
| R5 | "Backend không có quyền trên ai2" không cưỡng chế được (superuser `ci`) | Cao × Trung | VD-C2; test bằng role ít quyền để chứng minh schema không cấp gì cho PUBLIC; ghi hạn chế trong ADR-14 |
| R6 | Supersede ở Backend xoá review đang dở | Trung × Cao | VD-C1: chặn supersede khi đã có review action của người (`AI2_SUPERSEDE_BLOCKED_BY_REVIEW`); test đơn vị |
| R7 | E2E flaky (port đổi sau restart, timing) | Trung × Trung | Luôn resolve lại port sau restart; poll có deadline, không sleep cố định; 3 lượt CI liên tiếp xanh |
| R8 | Không chạy được E2E trên Windows dev (PB-C7) | Cao × Thấp | VD-C5: nghiệm thu E2E trên CI Linux; test Docker skip có lý do ở local, fail khi skip trên CI |
| R9 | Khoảng cách tới 95% lớn hơn dự kiến (nhất là domain xử lý) | Trung × Cao | Đo gap theo lớp ở bước 1 P4; quy tắc dừng + hỏi người (VD-C7); không hạ ngưỡng |
| R10 | Overfit golden khi gỡ luật rò | Trung × Cao | Mỗi fix gắn một lớp lỗi + test trên tài liệu tổng hợp khác fixture; lặp trên dev split; holdout + tập biến thể seed mới chỉ ở release; lint rò rỉ |
| R11 | Record lớn (hợp đồng ≥ 55 trang) làm chậm/phình DB | Trung × Trung | gzip JSON trong `bytea`; đo `size_bytes` trên golden 55+ trang; nạp lazy |
| R12 | Sửa chồng file giữa các plan A/B/C (`main.py`, `pyproject.toml`, workflow) | Trung × Trung | D-8 tuần tự; C bắt đầu sau khi A/B merge; mỗi phase đọc lại file trước khi sửa |

## Quyết định cần người dùng chốt (validate)

## Red-Team Disposition

| Finding | Disposition | Plan update / evidence |
|---|---|---|
| RT-C-01 (high): stale attempt completion can rewind the current dossier query digest | Accept | P3 F3.2/F3.3 now returns the accepted/current attempt and digest; only accepted persistence may update snapshot identity, atomically with result persistence. Added reverse-completion concurrency test to P3 RED/E5 (`reports/from-code-reviewer-to-planner-red-team-backend-data-integrity-db-safety-plan-review-report.md`). |
| RT-C-02 (high): deleting citations by document can remove citations shared with non-AI2 facts | Accept | P3 F3.2 and step 1(c) require verified AI2 fact ownership and reference checks before citation deletion; unknown ownership fails closed. Added shared-citation preservation and ownership-unknown tests (`reports/from-code-reviewer-to-planner-red-team-backend-data-integrity-db-safety-plan-review-report.md`). |

Both accepted findings are propagated into phase 3 requirements, implementation steps, and RED tests. No phase may proceed with destructive supersede cleanup unless citation ownership and references are proven safe.

## Quyết định cần người dùng chốt (validate)

| # | Câu hỏi | Phương án | Khuyến nghị | Ảnh hưởng |
|---|---|---|---|---|
| VD-C1 | Backend xử lý kết quả của `attempt` mới thế nào (hiện raise Conflict, PB-C5) | (a) Supersede trong cùng `pipeline_run` khi attempt mới > attempt đã lưu; attempt nhỏ hơn bị bỏ + log (DOC-04:281); chặn khi đã có review action của người. (b) Mỗi attempt một `pipeline_run` mới, dossier trỏ run mới nhất. (c) Chỉ cập nhật digest + `ai2_result_json`, projection cũ giữ nguyên (lệch) | **(a)** | P3 F3.2, E5, HC-C2 |
| VD-C2 | Backend chạy bằng superuser `ci` (PB-C4) | (a) Cưỡng chế chiều AI2→Backend; chứng minh schema `ai2` không cấp gì cho PUBLIC bằng role ít quyền; ghi hạn chế + follow-up Backend trong ADR-14. (b) C thêm role `backend_app` không superuser cho Backend (+2–3 ngày, bề mặt Backend). (c) Bỏ qua | **(a)** | P1, P2 test quyền, E7 |
| VD-C3 | Dữ liệu `data/ai2/jobs.sqlite` cũ | (a) Không import; dữ liệu dev bỏ; hồ sơ cần AI2 thì Backend chạy lại (attempt mới). (b) Script import job; record vẫn phải chạy lại vì chưa từng được lưu | **(a)** | P2, README |
| VD-C4 | Giữ attempt cũ (`request_json` ~MB/attempt) | (a) C không tự xoá; báo số/size trong verification; README có SQL purge tay; follow-up khi vượt ngưỡng. (b) Sweep giữ N=3 attempt gần nhất mỗi idempotency key (NULL payload cũ). (c) TTL 30 ngày | **(a)** | P2, P3 README |
| VD-C5 | Nghiệm thu E2E ở đâu (Windows dev không có Docker, PB-C7) | (a) CI Linux là nơi nghiệm thu (3 lượt xanh); Windows chạy phần không Docker; test Docker skip có lý do ở local, fail nếu skip trên CI. (b) Cài Docker Desktop và bắt buộc thêm 1 lượt E2E trên Windows | **(a)** | P2, P3 acceptance |
| VD-C6 | Nạp record khi restart + khi record không giải mã được | (a) Lazy khi `STORE.get` trượt; không giải mã được → `INSUFFICIENT_EVIDENCE` + `AI2_RECORD_REBUILD_REQUIRED`, Backend retry attempt mới; không tự chạy lại `run_idp`. (b) Nạp eager toàn bộ lúc startup. (c) Tự chạy lại `run_idp` offline khi lệch version | **(a)** | P2 F2.9/F2.11 |
| VD-C7 | Nếu gap tới 95% lớn (đặc biệt domain xử lý) | (a) Sau bước 1 P4, nếu > 6 lớp lỗi cần sửa hoặc có chỉ số < 85%: dừng, báo cáo gap, hỏi người để re-plan. (b) Làm tiếp tới khi đạt | **(a)** | P4 bước 1 |
| VD-C8 | Release của C | (a) Một release sau khi P3 + P4 xong (F4.10 chờ P3). (b) Cho release trung gian chỉ có chất lượng (P4) trước khi E2E/Postgres xong | **(a)** | P4 F4.10 |

## Validation Log
- VL-1 | complexity: complex · 4 phases · risk: DB dùng chung + khoảng cách chất lượng | mode `--hard --tdd` | khớp, giữ nguyên.
- VL-2 | Áp **`--deep`**: rủi ro chính (di chuyển state sang DB dùng chung, quyền role, E2E xuyên service, overfit) cần file inventory, ma trận kịch bản test, dependency map mỗi phase. Áp **`--parallel`**: DAG không phải chuỗi — P1 là cổng người có thể chờ nhiều ngày trong khi P2 (2a/2b) và P4 độc lập về file; có ma trận phụ thuộc + bảng sở hữu file ở trên và trong `plan-graph.yaml`.
- VL-3 | Phase > 8 file: P2 (28 file), P3 (13), P4 (22 gồm card/baseline). Giữ đúng 4 phase theo yêu cầu; P2 chia 3 commit 2a/2b/2c, P3 chia 3a/3b/3c, P4 commit theo lớp lỗi.
- VL-4 | Sửa research: nguyên nhân `chunks` lệch là `uuid4` (PB-C1), không phải `PYTHONHASHSEED`; test RED vẫn chạy 2 subprocess khác seed như main yêu cầu, **và** thêm cặp cùng seed để bắt đúng gốc.
- VL-5 | Cổng người được biểu diễn ở cấp bước (P2-2c chờ P1, P4-F4.10 chờ P3), không thành cạnh DAG, để việc không cần Postgres không bị chặn; `plan-graph.yaml` chỉ chứa cạnh chặn khởi động (P1→P3, P2→P3).
- VL-6 | Dependency mới của ai-service (`sqlalchemy`, `psycopg[binary]`, `alembic`) đặt vào `dependencies` chính, không extra: store được import khi import `app.api.main`, nên extra sẽ làm vỡ suite offline và image nếu thiếu cờ; không cần sửa `Dockerfile.ai2` (migrations nằm trong `app/`).

## Câu hỏi còn mở
1. Ai là Architecture Lead duyệt ADR-14 và kênh bằng chứng (review PR hay biên bản)?
2. B đặt tên/path chính xác cho schema `ai2.query.v1` và danh sách field volatile của response `/query` là gì (P3 chuẩn hoá so sánh)?
3. Đường dẫn image GHCR chính xác của B (`ghcr.io/<owner>/<repo>/ai2`?) cho dispatch release.
4. Số tài liệu `docs/ai2/AI2-18-*`: B có dùng số 17/18 không (P4 đổi sang số trống kế tiếp nếu trùng, sửa `plan-graph.yaml` trước cook).
5. `FactORM` không có `run_id` (`backend/.../extraction/infrastructure/persistence/orm.py:159-180`): discriminator an toàn để xoá fact AI2 của một run khi supersede là gì (`extractor`?) — P3 bước 1 xác minh; nếu không có, VD-C1(a) cần thêm cột ở Backend (migration Backend) → báo lại.
