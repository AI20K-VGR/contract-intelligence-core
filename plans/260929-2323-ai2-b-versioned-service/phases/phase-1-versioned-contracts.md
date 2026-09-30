---
phase: 1
title: "Versioned Contracts"
status: pending
plan: 260929-2323-ai2-b-versioned-service
created: 2026-09-29
harness_version: 6.3.0
harness_kit_digest: 672de2e098c3cb8451018791788f1052b1b812ccec08a1f124191bd8bbc04ebd
harness_schema_version: 1.0
---

# Phase 1 — Versioned Contracts

## Overview
Đưa contract Backend ↔ AI2 về trạng thái có version và kiểm được bằng máy, **trước** khi thêm bất kỳ field nào:

1. **Probe trước:** chứng minh bằng test rằng Backend đọc kết quả và response `/query` của AI2 một cách khoan dung (bỏ qua field lạ, state lạ). Đây là điều kiện để mọi thay đổi additive sau đó an toàn; hôm nay nó mới là giả thuyết đọc tĩnh (PB-B6).
2. Một nguồn sự thật cho tên contract (`app/contracts/versions.py`), schema `ai2.query.v1` (request/response) và `ai2.error.v1`, một builder duy nhất cho mọi nhánh `/query`, 10 site lỗi có `retryable`.
3. Thông điệp lỗi không mang giá trị payload ra ngoài (Backend log và lưu nguyên văn lỗi AI2, PB-B10).
4. `query_snapshot_digest` trong kết quả xử lý để Backend đọc thẳng thay vì tự tính lại (PB-B11), với fallback trong cửa sổ deprecation.
5. Chính sách tương thích + CHANGELOG.

Phụ thuộc: A đã merge (dùng gate offline của A làm regression). Không phụ thuộc phase nào của B.

## Dependency map
- **Upstream:** A merged — `evals/scripts/run_ai2_gate.py` (regression), CI `ai-service.yml`, `ai-service/tests/conftest.py` cô lập `.env`.
- **Code production (anchor 30/09, grep lại ở bước 0):**
  - `/query`: `ai-service/app/api/main.py:751-869` — 3 nhánh trả: lệch digest (`:~788-805`, thiếu `connected`/`used_llm`), thành công (`:~826-849`), chưa có record/unsigned (`:~850-869`); `"ai2.query.v1"` so chuỗi ở `:~786`.
  - Lỗi: `main.py:764,771,774,1644,1655,1673,1704,1706,1725,1727`; wire lỗi `main.py:237,256`.
  - Schema version cứng: `main.py:152` (`_queued_wire_result`), `ai-service/app/contracts/wire.py:364-368` (payload), validate `wire.py:371-395`.
  - Nguồn thông điệp chứa payload: `ai-service/app/contracts/schema_validation.py:64`, `ai-service/app/pipeline/ai1_snapshot_adapter.py:163`, `ai-service/app/security/service_envelope.py:89`.
  - Digest: `ai1_snapshot_adapter.py:111,215-218,2288-2291`; `create_idp_job` bỏ `adapted` (`main.py:~1649` `request, _ = ...`); `_run_wire_job` có `adapted` (`main.py:~169-174`).
  - Backend: `backend/src/contract_intelligence/worker.py:78-110,514,561-565`; `shared/ai/persistence.py:88-90,870-895`; `contract/interfaces/api/routers/contract_router.py:737-763`; `api/v1/dossiers.py:149-155`; `infrastructure/ai_adapters.py:196-224`.
  - State: `ai-service/app/contracts/models.py:10-16`; `l0_rules.py:593`; test ghim `tests/test_query_fallback_state.py:155-199`.
- **Downstream:** P2 điền giá trị `llm_called`/`llm_answer_used`/`llm_error_code` qua builder của P1 (không sửa schema); P3 `/version` đọc `versions.py` và băm bundle `docs/contracts/*.schema.json`; C E2E dùng `query_snapshot_digest`.
- **Người:** VD-B6 (enum state).

## Requirements

Chức năng:
- **F1.1 Probe Backend khoan dung** — `backend/tests/unit/test_ai2_contract_tolerance.py`, viết và chạy **đầu tiên**:
  - T1 `persist_ai2_processing_result` nhận result có field lạ ở root và trong `result.facts[0]` → không lỗi, số đếm bằng result gốc.
  - T2 `_search_dto_from_ai2` nhận payload có field lạ + `state="FUTURE_STATE"` → `state == "INSUFFICIENT_EVIDENCE"`, không exception.
  - T3 route `POST /api/v1/dossiers/{id}/query` với AI2 giả trả field lạ → 200.
  - T4 `poll_ai2_processing` với status `"CANCELLED"` (sleep bị monkeypatch, `max_polls=2`) → `AiAdapterTimeoutError`. Ghim sự thật "thêm status job **không** additive-safe".
  - Kết quả T1–T3 quyết định thứ tự release: xanh → AI2 được thêm field response trong v1, không cần Backend release trước; đỏ → **dừng thêm field**, sửa Backend thành tolerant reader trong commit riêng, ghi "Backend release trước" vào CHANGELOG, báo main.
- **F1.2 `ai-service/app/contracts/versions.py`** (SSOT, không logic):
  - `PROCESSING_REQUEST = "be.ai2.processing.request.v1"`, `PROCESSING_RESULT = "ai2.be.processing.result.v1"`, `QUERY = "ai2.query.v1"`, `SERVICE_ENVELOPE = "ai2.service-envelope.v1"`, `ERROR = "ai2.error.v1"`.
  - `SUPPORTED_CONTRACTS` (tuple 5 tên trên), `DEPRECATED_CONTRACTS = ()`, `API_VERSIONS = ("v1",)`.
  - `QUERY_STATES = ("ANSWERED", "NEEDS_REVIEW", "INSUFFICIENT_EVIDENCE", "NOT_COMPARABLE", "BLOCKED")`, `DEPRECATED_QUERY_STATES = ("PASS",)` (theo VD-B6a; nếu VD-B6b thì tuple rỗng và `to_query_state` map `PASS→ANSWERED`).
  - Thay literal: `main.py:152`, `wire.py:367`, `main.py:~786`.
- **F1.3 Schema** (`$id` theo quy ước `https://contractintel.internal/schemas/<name>.json`, draft 2020-12):
  - `docs/contracts/ai2.query.v1.request.schema.json`: required `query` (1..4000), `dossier_id`; optional `snapshot_version`, `snapshot_digest`, `query_contract_version` (`const "ai2.query.v1"`), `acl_context`, `policy_flags` {`egress_allowed`, `use_llm`, `use_vector`: boolean}, `tenant_id`, `actor_id`, `service_envelope` (`$ref` `ai2.service-envelope.v1`). `additionalProperties: true` — ghi rõ lý do: `/query` nhận `dict` và payload đã được ký, AI2 là consumer khoan dung ở request query (khác `/jobs/idp` strict).
  - `docs/contracts/ai2.query.v1.response.schema.json`: root `additionalProperties: false`; required `schema_version` (`const "ai2.query.v1"`), `state` (enum 5 + `PASS` có `deprecated: true` trong mô tả), `connected`, `answer` (string|null), `citations` (array of object, `additionalProperties: true` — shape citation được làm giàu, ghi lý do), `retrieval_layer` (object), `reasoning_trace` (array), `used_llm`, `llm_called`, `llm_answer_used` (boolean), `llm_error_code` (null | enum: `DISABLED, TENANT_NOT_ALLOWED, NOT_CONFIGURED, BREAKER_OPEN, CALL_BUDGET_EXHAUSTED, DEADLINE_EXCEEDED, SATURATED, TIMEOUT, CONNECTION, RATE_LIMITED, PROVIDER_5XX, AUTH, BAD_REQUEST, INVALID_JSON, UNKNOWN`). Enum lỗi LLM định nghĩa ở đây để P2 không phải sửa schema.
  - `docs/contracts/ai2.error.v1.schema.json`: `{code: ^[A-Z0-9_]{3,64}$, message: string ≤ 300, retryable: boolean}`, `additionalProperties: false`.
  - `docs/contracts/ai2.be.processing.result.v1.schema.json`: thêm property root **không required** `query_snapshot_digest` (`^[0-9a-f]{64}$`), mô tả "đúng digest mà `/query` so với `snapshot_digest`".
- **F1.4 `ai-service/app/api/query_contract.py`**:
  - `to_query_state(value) -> str`: giá trị trong `QUERY_STATES ∪ DEPRECATED_QUERY_STATES` giữ nguyên; còn lại → `INSUFFICIENT_EVIDENCE` (fail-closed).
  - `build_query_response(*, state, answer, citations, retrieval_layer, reasoning_trace, connected=True, llm_called=False, llm_answer_used=False, llm_error_code=None) -> dict`: luôn đủ key schema; `used_llm = llm_called`; `answer` không phải `str` → `json.dumps(..., ensure_ascii=False)` (giữ hành vi `main.py:~833-835`).
  - Cả 3 nhánh `/query` gọi builder; không đổi logic chọn nhánh.
- **F1.5 `ai-service/app/api/errors.py`**:
  - `ERROR_RETRYABLE: dict[str, bool]` cho mọi code ở 10 site (401/403/404/409/422 → `False`).
  - `ai2_http_error(status: int, code: str, message: str | None = None) -> HTTPException` với `detail = {code, message, retryable}`; `message` qua `safe_message()` (bỏ CR/LF, cắt 300 ký tự).
  - Thay 10 site; `main.py:1704` thành `ai2_http_error(404, "JOB_NOT_FOUND", "job not found")`.
- **F1.6 Thông điệp lỗi không mang giá trị payload**:
  - `schema_validation.py:64`: `f"{path}: {error.validator}"` (tên validator, không có `error.message`).
  - `ai1_snapshot_adapter.py:163` và `service_envelope.py:89`: tóm tắt `ValidationError` bằng `exc.errors(include_input=False, include_url=False)` → chuỗi `loc:type` nối bằng `; `.
  - `main.py:256` (lỗi worker chung): `message = "AI2 worker failed"` + `exc_type` trong log (không `str(exc)`); `main.py:237` giữ `str(exc)` vì nguồn đã được làm sạch ở trên.
  - Backend consumer sink cũng thuộc P1: `infrastructure/ai_adapters.py:84-91` không log/lưu raw `response.text`; chỉ giữ status + allow-list code/message đã sanitize, và `worker.py` không lưu `str(exc)` từ response AI2. Thêm canary regression cho lỗi định dạng cũ từ AI2 chạy qua adapter và worker.
- **F1.7 `query_snapshot_digest`**:
  - `create_idp_job`: giữ `adapted` thay vì `_`; `_queued_wire_result(request, job_id, query_snapshot_digest)`.
  - `_run_wire_job`: truyền `adapted.record.pins.source_snapshot_digest` vào `job_result_to_wire(result, request, query_snapshot_digest=...)`.
  - `job_result_to_wire(job, request, *, query_snapshot_digest: str | None = None)`: đặt ở root khi có.
  - Ngữ nghĩa **không đổi** (vẫn có `attempt_id`); chỉ lộ ra giá trị AI2 đã dùng.
- **F1.8 Backend ưu tiên digest của AI2** (`worker.py`, sau `SUCCEEDED`):
  - `reported = str(report.get("query_snapshot_digest") or "")`; dùng `reported` nếu có, ngược lại dùng `query_snapshot_digest` tự tính (`:514`).
  - Có cả hai mà khác nhau → log `worker.ai2.digest_mismatch` (chỉ cờ, không log giá trị) và dùng `reported`.
  - Không có → log `worker.ai2.digest_fallback` (đường deprecated).
- **F1.9 Tài liệu**:
  - `docs/contracts/README.md` thêm mục "Chính sách tương thích": 3 trục version (tag image `ai2-vX.Y.Z` ↔ path `/api/v1` ↔ `schema_version`), mỗi trục một nguồn sự thật; v1 chỉ additive (field response tuỳ chọn; field request chỉ sau khi AI2 hỗ trợ vì `/jobs/idp` strict; **không** thêm status job; thêm `state` chỉ khi Backend có nhánh mặc định — T2; không đổi tên; đổi ngữ nghĩa = major mới chạy song song); consumer MUST bỏ qua field lạ (ghim bằng T1–T3); hỗ trợ major N và N-1 ≥ 1 chu kỳ release B/C, gỡ N-1 chỉ ở image MAJOR; quy tắc bump image MAJOR/MINOR/PATCH; thứ tự release theo loại thay đổi. Liệt kê schema mới.
  - `docs/contracts/CHANGELOG.md`: mục "Unreleased (ai2 1.0.0-rc.1)" ghi before/after từng bề mặt ở bảng "Thay đổi hợp đồng" của plan.md, gồm các mục deprecated: `used_llm`, `PASS`, fallback tự tính digest ở Backend.

Phi chức năng:
- Không đổi hành vi với caller hiện tại ngoài các mục ghi CHANGELOG.
- Không thêm dependency.
- Không log/echo giá trị payload trong bất kỳ thông điệp lỗi nào của 3 endpoint contract.

## Related Code Files
**Create**
- `docs/contracts/ai2.query.v1.request.schema.json`, `docs/contracts/ai2.query.v1.response.schema.json`, `docs/contracts/ai2.error.v1.schema.json`, `docs/contracts/CHANGELOG.md`
- `ai-service/app/contracts/versions.py`, `ai-service/app/api/query_contract.py`, `ai-service/app/api/errors.py`
- `ai-service/tests/test_versioned_contracts.py`
- `backend/tests/unit/test_ai2_contract_tolerance.py`

**Modify**
- `docs/contracts/ai2.be.processing.result.v1.schema.json`, `docs/contracts/README.md`
- `ai-service/app/api/main.py`, `ai-service/app/contracts/wire.py`, `ai-service/app/contracts/schema_validation.py`, `ai-service/app/pipeline/ai1_snapshot_adapter.py`, `ai-service/app/security/service_envelope.py`
- `backend/src/contract_intelligence/worker.py`, `backend/src/contract_intelligence/infrastructure/ai_adapters.py`

**Delete**: không có.

## File inventory

| File | Hành động | Cỡ | Tác động test |
|---|---|---|---|
| `backend/tests/unit/test_ai2_contract_tolerance.py` | C | ~220 dòng (T1–T4 + 3 test digest) | probe quyết thứ tự release |
| `ai-service/tests/test_versioned_contracts.py` | C | ~350 dòng | toàn bộ F1.2–F1.7 |
| 3 schema mới | C | ~60 / ~110 / ~25 dòng | validate nhánh `/query`, lỗi |
| `ai2.be.processing.result.v1.schema.json` | M | +6 dòng | `test_processing_wire_contract.py`, `test_result_regressions.py` phải xanh |
| `versions.py` | C | ~30 dòng | hằng khớp schema |
| `query_contract.py` | C | ~60 dòng | builder + map state |
| `errors.py` | C | ~50 dòng | 10 site |
| `main.py` | M | ~-40/+40 dòng | `test_query_fallback_state.py`, `test_service_envelope.py`, `test_api.py`, `test_p5_api_security.py` |
| `wire.py` | M | +8 dòng | wire contract tests |
| `schema_validation.py` | M | 1 dòng | mọi test contract (không test nào khớp message gốc — grep) |
| `ai1_snapshot_adapter.py`, `service_envelope.py` | M | ~+10 dòng mỗi file (helper tóm tắt) | `test_ai1_snapshot_adapter.py`, `test_service_envelope.py` |
| `worker.py`, `ai_adapters.py` | M | ~+25 dòng | `test_worker_pipeline_run.py`, adapter/worker error-canary tests |
| `README.md`, `CHANGELOG.md` | M/C | ~1 trang | — |

## Implementation Steps
0. **Preflight.** Kiểm A đã có: `Test-Path evals/scripts/run_ai2_gate.py` (Linux: `test -f`); cây sạch (`git status --porcelain` rỗng ngoài `plans/`). Grep lại mọi anchor ở "Dependency map" (WIP làm lệch dòng); ghi số dòng thật vào `verification-P1.json`.
1. **Probe Backend (commit 1a).** Viết `backend/tests/unit/test_ai2_contract_tolerance.py` T1–T4 (tái dùng fixture DB/async của `tests/unit/test_ai2_result_persistence.py` và client của `test_query_state_passthrough.py`). Chạy `cd backend; uv run pytest tests/unit/test_ai2_contract_tolerance.py -q -p no:cacheprovider`. Ghi kết quả từng T vào `verification-P1.json` với nhãn OBSERVED. Rẽ nhánh theo F1.1.
2. **Probe echo lỗi.** Viết trước 4 test canary trong `test_versioned_contracts.py` (snapshot sai kiểu chứa `CANARY-HD-7f3a`; field pydantic sai chứa canary; envelope sai chứa canary; `run_idp` monkeypatch raise `ValueError("CANARY-HD-7f3a")`). Chạy, kỳ vọng **đỏ** ít nhất ở jsonschema/pydantic (xác nhận `[PRIOR]` của PB-B10); nếu xanh sẵn ở nguồn nào thì ghi OBSERVED và vẫn giữ test làm regression.
   - Bổ sung Backend canary: fake AI2 cũ trả error body chứa `CANARY-HD-7f3a`; kiểm không xuất hiện trong log của `ai_adapters.py`/`worker.py` hoặc exception/result được lưu; giữ code/status ổn định để chẩn đoán.
3. **RED còn lại** (danh sách ở TDD). Chạy, xác nhận đỏ đúng lý do.
4. **Implement AI2 (commit 1b)**: `versions.py` → 3 schema + sửa result schema → `query_contract.py` → `errors.py` → sửa 10 site + 3 nguồn thông điệp + 2 wire lỗi → digest ở `create_idp_job`/`_run_wire_job`/`job_result_to_wire`.
5. **Implement Backend + docs (commit 1c)**: `ai_adapters.py` sanitize raw upstream error body; `worker.py` F1.8 (+3 test digest và canary test Backend); README + CHANGELOG.
6. **Regression gate** (mục TDD). Commit từng bước khi gate xanh.

## TDD

### Tests Before (RED)
`backend/tests/unit/test_ai2_contract_tolerance.py`:
- [ ] `test_persist_result_ignores_unknown_root_and_nested_fields` (T1)
- [ ] `test_search_dto_ignores_unknown_fields_and_maps_unknown_state` (T2)
- [ ] `test_dossier_query_route_ignores_unknown_ai2_fields` (T3)
- [ ] `test_poll_does_not_treat_unknown_status_as_terminal` (T4 — ghim hành vi, xanh ngay là đúng)
- [ ] `test_worker_prefers_ai2_query_snapshot_digest`
- [ ] `test_worker_falls_back_to_local_digest_when_absent`
- [ ] `test_worker_uses_ai2_digest_and_logs_mismatch_without_values`

`ai-service/tests/test_versioned_contracts.py`:
- [ ] `test_versions_constants_match_schema_files` — mỗi hằng có file schema; `const`/`$id` khớp; `SUPPORTED_CONTRACTS` không trùng.
- [ ] `test_no_contract_name_literals_outside_versions` — grep `main.py`, `wire.py` không còn literal `"ai2.query.v1"`/`"ai2.be.processing.result.v1"` ngoài import.
- [ ] `test_query_digest_mismatch_branch_validates_and_has_connected_used_llm`
- [ ] `test_query_success_branch_validates_schema`
- [ ] `test_query_unsigned_fallback_branch_validates_schema`
- [ ] `test_query_state_passthrough_and_unknown_fails_closed` — parametrize 6 giá trị hợp lệ + `"FUTURE"` → `INSUFFICIENT_EVIDENCE`.
- [ ] `test_query_error_bodies_follow_error_schema` — 401 envelope sai, 422 thiếu query, 422 thiếu dossier (3 site).
- [ ] `test_jobs_error_bodies_follow_error_schema` — `/jobs/idp` 401, 422, 409; `/jobs/{id}` 404, 401 thiếu header, 401 envelope sai, 403 (7 site). Tổng 10/10.
- [ ] `test_error_messages_never_echo_payload_canary` — 4 kịch bản của bước 2; kiểm body HTTP và wire `errors[].message`.
- [ ] `test_legacy_ai2_error_body_canary_not_logged_or_persisted` — old-format error body qua Backend adapter/worker; không canary trong log/result/exception.
- [ ] `test_queued_and_result_wire_carry_query_snapshot_digest` — submit job (BackgroundTasks chạy đồng bộ trong `TestClient`) → wire QUEUED và SUCCEEDED có field; bằng `STORE.get(...).pins.source_snapshot_digest`.
- [ ] `test_query_with_reported_digest_passes_guard` — `/query` với `snapshot_digest = result.query_snapshot_digest` không rơi vào nhánh lệch digest.
- [ ] `test_result_without_query_snapshot_digest_still_valid` — wire cũ (không field) validate.

### Implement
Theo bước 4–5.

### Tests After
- Test hiện hành phải xanh không sửa: `tests/test_query_fallback_state.py` (gồm `PASS` round-trip), `test_processing_wire_contract.py`, `test_p0_contract_baseline.py`, `test_result_regressions.py`, `test_service_envelope.py`, `test_api.py`, `test_ai1_result_v01.py`, `test_legacy_compat.py`; Backend `test_worker_pipeline_run.py`, `test_ai2_result_persistence.py`, `test_query_state_passthrough.py`, `test_contract_router.py`.

### Regression Gate
- AI2 offline suite (lệnh chuẩn plan.md) → 0 failed, 0 error.
- `cd backend; uv run pytest tests/unit -q -p no:cacheprovider` → 0 failed; `uv run ruff check src/ tests/` 0; `uv run mypy src/` không thêm lỗi so với base.
- `cd ai-service; .venv/Scripts/ruff.exe check . ../evals` → `All checks passed`.
- `$PY evals/scripts/run_ai2_gate.py --mode pr --base-ref origin/<base>` → exit 0.

## Test scenario matrix

| Mức | Kịch bản | Test |
|---|---|---|
| Critical | Backend vỡ khi AI2 thêm field | T1–T3 |
| Critical | Thông điệp lỗi mang nội dung hợp đồng ra Backend log/DB | `test_error_messages_never_echo_payload_canary` |
| Critical | Digest Backend lưu khác digest AI2 so → mọi query báo thiếu evidence | 3 test digest Backend + `test_query_with_reported_digest_passes_guard` |
| High | Nhánh `/query` thiếu key → Backend đọc mặc định sai | 3 test nhánh + schema |
| High | State lạ lọt ra như trạng thái trả lời | `test_query_state_passthrough_and_unknown_fails_closed` |
| High | Thêm status job làm Backend poll treo | T4 (ghim) + chính sách "không thêm status" |
| Medium | Tên contract lệch giữa code và schema | `test_versions_constants_match_schema_files`, `test_no_contract_name_literals_outside_versions` |
| Medium | Wire cũ trong job store không còn hợp lệ | `test_result_without_query_snapshot_digest_still_valid` |

## Success Criteria
- [ ] (OBSERVED) T1–T4 đã chạy; kết quả + quyết định thứ tự release ghi trong `verification-P1.json` và CHANGELOG.
- [ ] (test) 12/12 test AI2 và 7/7 test Backend mới xanh; regression gate xanh trên Windows và CI Linux.
- [ ] (invariant) 3/3 nhánh `/query` validate schema; 10/10 site lỗi đúng `ai2.error.v1`; 0/4 kịch bản canary lộ chuỗi canary.
- [ ] (invariant) `git grep -n '"ai2.query.v1"' -- ai-service/app` chỉ còn trong `app/contracts/versions.py`.
- [ ] (test) `test_query_fallback_state.py::test_query_endpoint_round_trips_state_and_operational_fields` xanh không sửa (VD-B6a).
- [ ] Gate offline A exit 0.

## Risk Assessment

| Rủi ro | Khả năng × Tác động | Giảm thiểu |
|---|---|---|
| T1–T3 đỏ (Backend strict ở chỗ chưa thấy) | Thấp × Cao | Nhánh rẽ F1.1: sửa Backend trước, ghi thứ tự release; không phát field mới cho tới khi xanh |
| Sanitize làm mất thông tin debug | Trung × Thấp | Giữ `loc:type` + code ổn định; chi tiết đầy đủ chỉ ở test/local |
| Builder đổi hành vi nhánh (vd. `answer` JSON) | Thấp × Trung | Test nhánh so với output cũ; giữ `json.dumps` như `main.py:~833-835` |
| Test canary xanh sẵn nên không chứng minh gì | Trung × Thấp | Ghi OBSERVED "nguồn X không echo"; test vẫn giữ làm regression |
| Anchor lệch do WIP | Cao × Thấp | Bước 0 grep lại, ghi dòng thật |
| Backend `mypy` có lỗi sẵn làm nhiễu | Trung × Thấp | So số lỗi base vs head, không đòi 0 tuyệt đối |
