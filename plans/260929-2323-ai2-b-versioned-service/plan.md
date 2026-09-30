---
id: 260929-2323-ai2-b-versioned-service
title: "AI2-B versioned service: contracts, GHCR image, LLM enablement, observability"
description: "AI2 thành dịch vụ có version: contract ai2.query.v1 + chính sách tương thích, bật gpt-4o-mini an toàn (deadline wall-clock, fail-closed, egress do server quyết), image GHCR tự chứa có /version + provenance/SBOM, log/metrics/trace đã redact."
status: pending
priority: P1
effort: "9-11 ngày công agent + khoảng 1 ngày người (HC-B1..HC-B4, review mentor)"
mode: hard
tdd: true
branch: feature/code-full
tags: [ai2, contracts, versioning, llm, ghcr, observability, security]
created: 2026-09-29
author: 
decisions: []
phases:
  - phases/phase-1-versioned-contracts.md
  - phases/phase-2-llm-enablement.md
  - phases/phase-3-packaging-ghcr-image.md
  - phases/phase-4-observability.md
harness_version: 6.3.0
harness_kit_digest: 672de2e098c3cb8451018791788f1052b1b812ccec08a1f124191bd8bbc04ebd
harness_schema_version: 1.0
---

# Plan: AI2-B versioned service: contracts, GHCR image, LLM enablement, observability

> hs:cook đọc file này làm hợp đồng. Nhãn bằng chứng: **OBSERVED** (đã đọc/grep/chạy trong repo ngày 30/09/2026, xem "Bằng chứng nền"), **DERIVED** (suy từ dữ liệu đã quan sát), `[ASSUMED]` (chưa kiểm), `[PRIOR]` (kiến thức nền chưa kiểm lại). Số dòng lấy trên cây làm việc 30/09 (có WIP chưa commit ở `main.py`, `stack.py`, `l2_plan.py`, `query.py`, `ai1_snapshot_adapter.py`) — cook **grep lại anchor** ở bước 0 mỗi phase. Mọi lệnh chạy từ root repo. `$PY` = `.\ai-service\.venv\Scripts\python.exe` trên Windows (kèm `$env:PYTHONIOENCODING="utf-8"`) hoặc `ai-service/.venv/bin/python` trên Linux/CI.

## Tổng quan

B biến AI2 từ "FastAPI demo build tại chỗ" thành dịch vụ có version mà Backend pin được, rồi mới bật LLM. Bốn việc, theo thứ tự rủi ro:

1. **Contract có version, kiểm được** (P1). Hôm nay "additive" **không** tự an toàn: schema kết quả đóng (`additionalProperties:false` ×9), wire model AI2 `extra="forbid"`, `/query` chưa có schema, 3 nhánh trả về lệch nhau, lỗi thiếu `retryable`, và thông điệp lỗi có thể mang nguyên văn payload ra ngoài (PB-B7..B10). Backend lại tự tính lại digest của AI2 bằng một bản cài đặt thứ hai (PB-B11). P1 **đo** Backend có đọc khoan dung không (probe bằng test, không giả định), thêm `query_snapshot_digest`, công bố `ai2.query.v1` và chính sách tương thích.
2. **Bật LLM mà không vỡ ngân sách 20 s và không rò dữ liệu** (P2). Timeout của SDK là theo pha, không phải deadline tổng (probe của researcher: trickle sống 31,4 s dù `timeout=2`); client gọi lại lần hai trên mọi lỗi; L2 không bắt lỗi provider; `/query` không truyền LLM; và **route `/api/v1/dossiers/{id}/query` của Backend đang chuyển thẳng `policy_flags` do client gửi sang AI2** — hiện vô hại vì `/query` chưa có LLM, nhưng sẽ thành đường vòng egress ngay khi B nối LLM (PB-B5). P2 sửa egress phía server **trước**, rồi mới nối LLM qua một guard có deadline wall-clock, breaker, trần số lời gọi và fail-closed về câu trả lời tất định.
3. **Image GHCR tự chứa, có version** (P3). Image hiện **không tự chứa**: schema contract được đọc từ `/docs/contracts` do compose mount từ máy host (PB-B12) — pin tag mà schema lại lấy từ cây làm việc thì pin vô nghĩa. P3 nướng schema vào image, bỏ `COPY data/`, thêm `.dockerignore`, `GET /version` rẻ và không chạm mạng, workflow `ai2-release.yml` (tag `ai2-v*`, provenance + SBOM + attestation, `latest=false`, `linux/amd64`), cổng evidence theo D-6, và file override để Backend pin `tag@digest`.
4. **Quan sát được mà không log nội dung** (P4). Log JSON theo allow-list, `/metrics` Prometheus (~10 series, nhãn hữu hạn), trace OTel bật theo env (no-op khi không có endpoint), latency + token + chi phí LLM theo lượt.

B **không** nâng chất lượng và **không** claim cải thiện nào từ fixture HD (rò rỉ ở `l0_rules.py`, C gỡ). Nghiệm thu chất lượng của B chỉ là "không hồi quy" theo bộ chấm của A. Release GA `ai2-v1.0.0` cần `threshold_verdict = PASS` (D-6), nên B dừng ở pre-release `-rc.N` (VD-B1).

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

## Quyết định cần chốt ở validate (VD-B)

Cook dùng cột "Mặc định" nếu người dùng chưa chốt; mỗi điểm khi chốt ghi một dòng `## Validation Log`.

| # | Câu hỏi | Phương án (khuyến nghị đứng đầu) | Mặc định cook | Ảnh hưởng |
|---|---|---|---|---|
| VD-B1 | "Release" trong D-6 gồm những tag nào? Chất lượng ≥ 95% là việc của C (C phụ thuộc B), nên nếu mọi tag đều cần PASS thì B không phát được image nào cho C pin (khoá chéo) | **(a)** Tag pre-release SemVer `ai2-vX.Y.Z-rc.N`: cần gate offline A exit 0 + 1 lượt live chạy tay (D-7) có **0 hồi quy tripwire**; tag GA `ai2-vX.Y.Z`: bắt buộc `threshold_verdict = PASS` cả offline lẫn live (D-6). B phát `1.0.0-rc.N`; GA `1.0.0` sau khi C đạt ngưỡng. (b) Mọi tag cần PASS → B không publish được, C E2E bằng build local | (a) | P3 cổng release, Acceptance, bàn giao C |
| VD-B2 | GA ép PASS ở đâu (research Open Q4) | **(a)** File evidence commit ở `evals/releases/<tag>.json` (sinh bằng script từ report gate + summary live của A, gắn **tree hash của `ai-service/`**) được job `release-gate` kiểm máy **và** environment `ai2-release` có required reviewer (Văn Dũng/mentor). (b) Chỉ file evidence. (c) Chỉ reviewer | (a) | P3 workflow, HC-B3 |
| VD-B3 | Deadline LLM mỗi lượt query và số lời gọi LLM tối đa — **chốt bằng số đo, không bằng lập luận** | **(a)** Mặc định `AI2_QUERY_LLM_DEADLINE_SECONDS=12`, `AI2_QUERY_MAX_LLM_CALLS=2` (1 draft + 1 replan), rồi chốt lại theo quy tắc sau lượt live HC-B1a: giữ nếu p95(`used_llm`) ≤ 17 s **và** tỉ lệ `DEADLINE_EXCEEDED` ≤ 5%; nếu tỉ lệ > 5% và p95 ≤ 14 s thì nâng deadline tối đa 15 s; nếu p95 > 17 s thì hạ deadline đúng phần vượt hoặc giảm còn 1 lời gọi; n < 60 → giữ mặc định, ghi `UNDERPOWERED`, đo lại trước GA. (b) Chốt cứng ngay 10 s / 1 lời gọi | (a) | P2 F2.6, F2.12; `/version` |
| VD-B4 | LLM đi đường nào trong Sprint 2 (research Open Q3) | **(a)** Gọi thẳng `https://api.openai.com/v1` với **đúng snapshot có ngày mà A đã pin** (compose default); `/version` báo `provider_host`. Lý do: benchmark của A đo trên OpenAI trực tiếp, nên số đo mới đại diện cho runtime; bớt một bên trung gian nhận dữ liệu. (b) Giữ proxy 9router `host.docker.internal:20128` (`client.py:23`, compose hiện tại) | (a) | P2 compose/`.env.example`, VD-B3 |
| VD-B5 | Ép "chỉ dữ liệu giả lập/ẩn danh" (D-5) bằng gì | **(a)** Hai lớp: Backend quyết cờ egress từ settings (mặc định `false`, bỏ cờ client gửi) **và** AI2 có kill switch `AI2_LLM_ENABLED` (mặc định `false`) + allowlist `AI2_LLM_EGRESS_TENANTS` (chỉ tenant dữ liệu giả lập; token `workspace` cho lane demo). "Bật LLM Sprint 2" = bật cấu hình ở môi trường dữ liệu giả lập. (b) Chỉ cấu hình Backend | (a) | P2 F2.1–F2.3, runbook |
| VD-B6 | Enum `state` của `ai2.query.v1` ("đủ 5 giá trị") khi L0 còn trả `PASS` và test hiện hành ghim `PASS` round-trip | **(a)** Schema liệt kê 5 giá trị chuẩn `ANSWERED/NEEDS_REVIEW/INSUFFICIENT_EVIDENCE/NOT_COMPARABLE/BLOCKED` + `PASS` là alias **deprecated** (vẫn phát, ghi CHANGELOG, bỏ ở `ai2.query.v2`); giá trị lạ → `INSUFFICIENT_EVIDENCE`. Giữ đúng luật "chỉ additive trong v1". (b) Đổi `PASS`→`ANSWERED` ngay ở biên `/query` (đúng 5 giá trị, nhưng đổi giá trị đang phát trong v1) | (a) | P1 F1.3/F1.4 |
| VD-B7 | Visibility và nền tảng image GHCR (research Open Q5) | **(a)** Package **private**, liên kết repo; host chạy Backend `docker login ghcr.io` bằng PAT `read:packages`; chỉ `linux/amd64`. (b) Public. (c) Thêm `linux/arm64` (QEMU chậm với pymupdf/opencv `[PRIOR]`) | (a) | P3 workflow, runbook, HC-B3 |
| VD-B8 | Có thêm hạ tầng quan sát vào compose không (D-4 cho phép, không bắt) | **(a)** Không: `/metrics` xem bằng `curl`, OTel no-op khi thiếu `OTEL_EXPORTER_OTLP_ENDPOINT`, log JSON ra stdout. Không Langfuse (gửi prompt sang dịch vụ khác, trái D-5). (b) Thêm Prometheus + Grafana + Jaeger/collector vào compose | (a) | P4 phạm vi |
| VD-B9 | Bàn giao từ A: "chuyển `load_dotenv` (`main.py:63`) từ import sang startup" | **(a)** Giữ lúc import nhưng **gate** bằng `AI2_LOAD_DOTENV` (image đặt `0`; `.dockerignore` loại `.env`). Chuyển sang startup sẽ làm 3 singleton đọc env **trước** khi `.env` được nạp (`main.py:74,77,78`, PB-B19) — hồi quy âm thầm ở dev. (b) Chuyển sang startup + đổi 3 singleton sang lazy | (a) | P3 F3.6 |
| VD-B10 | Container chạy non-root? | **(a)** Hoãn: volume `ai2_data` hiện do image root tạo; đổi user làm hỏng quyền ghi trên volume cũ `[PRIOR]`. Ghi follow-up. (b) Làm ngay kèm bước `chown` volume trong runbook | (a) | P3 Dockerfile |

## Bằng chứng nền (planner, 30/09/2026)

| # | Quan sát | Nhãn |
|---|---|---|
| PB-B1 | `openai 3.14.0` + `httpx 0.28.1`, server giả: `timeout=2`, trickle 1 byte/s → call sống 10,0 s (`max_retries=0`) và 31,4 s (`max_retries=2`); im lặng → 3,0 s. Timeout là theo pha, không phải deadline tổng (research §1.6) | OBSERVED (researcher) |
| PB-B2 | `client.py:27-28` timeout mặc định 45 s, `max_retries=0`; `:57` bắt **mọi** `Exception` rồi gọi lần 2 không `response_format` (401/timeout cũng gọi lại → tới 2×45 s); `:14,71,84` `all_traces` là list cấp class, lớn vô hạn suốt process, không có chỗ đọc (grep `all_traces` trong `app/ tests/ evals/`) | OBSERVED |
| PB-B3 | `l2_plan.py:158` (draft) và `:255` (`_plan`) gọi `complete_json` không bắt lỗi provider (chỉ bắt `ToolBlocked`/`TypeError` quanh tool); `MAX_REPLAN = 2` (`:11`) → tối đa 3 lời gọi logic/lượt | OBSERVED |
| PB-B4 | `/query` dựng `QueryRouter(STORE, ToolGateway(STORE))` không có llm (`main.py:823`); `stack.py:120-124` `allow_llm` đòi cả `use_vector`; `FourLayerReasoner.run` không bao giờ đặt `used_llm` (grep `used_llm` trong `stack.py` = 0) nên `used_llm` của `/query` luôn `false` (`query.py:79`) | OBSERVED |
| PB-B5 | Kiểm kê egress Backend — 6 site: (1) `shared/ai/canonical_processing.py:349-356` xử lý hồ sơ (lane chính, `worker.py:497`) `egress_allowed: False`; (2) `contract_router.py:806` `/dossiers/{id}/search` `{"egress_allowed": False}`, bỏ qua `settings.ai2_query_egress_allowed` (`settings.py:148-154`) và `ai2_query_use_vector` (`:155-158`); (3) **`api/v1/dossiers.py:135` chuyển `body.policy_flags` của client sang AI2** (`schemas/queries.py:16-19`, route đăng ký ở `main.py:326`); (4) `ai_adapters.py:445-452` lane Kafka (`ai2_handoff.py:243`, `max_llm_calls: 0`); (5) `api/v1/webhooks.py:186` lane `/process` legacy — AI2 trả `INSUFFICIENT_EVIDENCE` mà không xử lý (`main.py:705-748`); (6) `schemas/queries.py:17` default của trường client | OBSERVED |
| PB-B6 | Giả thuyết Backend đọc khoan dung (đọc tĩnh, **chưa chạy**): `persist_ai2_processing_result` đọc bằng `.get` (`persistence.py:870-895`), `_result_digest` băm cả result (`:88-90`); `_search_dto_from_ai2` map state lạ → `INSUFFICIENT_EVIDENCE` (`contract_router.py:737-749`); `DossierQueryResponse` `extra="ignore"` (`queries.py:25`) và dựng từ key tường minh (`dossiers.py:149-155`). **Không khoan dung** ở status job: poll chỉ coi `SUCCEEDED/FAILED` là kết thúc (`ai_adapters.py:222`) → thêm status mới sẽ poll tới hết ngân sách. P1 bước 1 biến giả thuyết thành OBSERVED bằng test | hypothesis |
| PB-B7 | AI2 chặt: schema result `additionalProperties:false` ×9 (`grep -c`); `wire.py:26,50,59,69,87,95,105` `extra="forbid"`; AI2 tự validate result với schema trước khi trả (`wire.py:371-395`) | OBSERVED |
| PB-B8 | `ReviewState` có 6 giá trị (`models.py:10-16`); L0 trả `PASS` trên đường query (`l0_rules.py:593` → `stack.py:61-70`); test hiện hành ghim `PASS` round-trip qua `/api/v1/query` (`tests/test_query_fallback_state.py:155-199`); FE và Backend đều nhận 6 giá trị (`frontend/src/api/ai2.ts:1-7,113-121`, `contract_router.py:741-748`). Result: `status` 4 giá trị, `review_state` 4 giá trị + null (schema) | OBSERVED |
| PB-B9 | `/query` không có `schema_version` ở nhánh nào; nhánh lệch digest (`main.py:~788-805`) thiếu `connected` và `used_llm` | OBSERVED |
| PB-B10 | 10 chỗ raise lỗi ở endpoint contract trả `{code,message}` không có `retryable`: `main.py:764,771,774` (`/query`), `:1644,1655,1673` (`/jobs/idp`), `:1704,1706,1725,1727` (`/jobs/{id}`); `:1704` trả chuỗi `job_id` trần. Nguồn thông điệp có thể mang giá trị payload: `schema_validation.py:64` dùng `error.message` của jsonschema; `ai1_snapshot_adapter.py:163` và `service_envelope.py:89` nhúng `{exc}` của pydantic; wire lỗi `main.py:237,256` dùng `str(exc)`. Backend log `response.text[:500]` của lỗi AI2 (`ai_adapters.py:84-91`) và lưu `str(exc)[:1000]` (`worker.py:621,629`). Việc jsonschema/pydantic nhúng giá trị input là `[PRIOR]` → P1 kiểm bằng test canary | OBSERVED + `[PRIOR]` |
| PB-B11 | Digest: `_canonical_digest` = sha256 hex trần (`ai1_snapshot_adapter.py:2288-2291`) của payload tương thích có `attempt_id` (`:111`), ghim ở `:215-218`; Backend cài lại cùng thuật toán (`worker.py:78-110`), tính ở `:514`, lưu ở `:561-565`; result wire không mang digest | OBSERVED |
| PB-B12 | **Image không tự chứa**: `schema_validation.py:13-14` lấy `parents[3]/docs/contracts`; trong image file nằm ở `/app/app/contracts/` (`Dockerfile.ai2:5,20`) → `/docs/contracts`, chỉ tồn tại nhờ compose mount `./docs:/docs:ro` (`docker-compose.yml:462`). Là đường duy nhất thoát khỏi `ai-service/` lúc chạy (grep `parents[`) | OBSERVED |
| PB-B13 | `Dockerfile.ai2:22` `COPY data/ data/`; không có `.dockerignore`; runtime chỉ cần thư mục ghi được `data/ai2` và tự `mkdir` (`persist.py:27-34`, `jobs.py:24-25,55`, `vector_recall.py:65-69`); `data/` tracked = 8 file placeholder OCR-lab (`git ls-files`); `ai-service/data/ai2/{jobs,vectors}.sqlite` **untracked và không bị ignore** (`git status` `?? ai-service/data/ai2/`; `ai-service/.gitignore` không có rule) | OBSERVED |
| PB-B14 | `/health` tạo `NineRouterClient()` mỗi lần và có thể gọi `EMBEDDING_CLIENT.discover` (egress) khi bật env, trả `persist: str(DATA)` (`main.py:677-695`); healthcheck compose gọi `/health` (`docker-compose.yml:472`); Backend dùng `/healthz` của AI2 (`backend/.../shared/ai/client.py:396`); demo đọc `/health` (`static/demo.js:88`, `lab.js:33`) | OBSERVED |
| PB-B15 | Version: `FastAPI(..., version="0.1.0")` (`main.py:67`); `pyproject.toml:6-7` là `contract-ocr-lab 0.1.0`; tag git hiện có `be-ban-1`, `fe-ban-1`, `v0.1.0`; remote `AI20K-VGR/contract-intelligence-core` → đường GHCR chữ thường `ghcr.io/ai20k-vgr/contract-intelligence-core/ai2` | OBSERVED |
| PB-B16 | Ngân sách caller: `ai2_query_timeout_seconds = 20.0` (`settings.py:142-147`), ép bằng `asyncio.wait_for` ở `/search` (`contract_router.py:~790-812`); route `/dossiers/{id}/query` chỉ có timeout httpx 30 s theo pha (`ai_adapters.py:24`) | OBSERVED |
| PB-B17 | Log AI2 là `%`-format stdlib; `kafka_idp_worker.py:266` log **nguyên message Kafka** bằng `%r` (có thể chứa snapshot); không có JSON/redaction; `prometheus`/`opentelemetry` = 0 hit trong `ai-service/app`; `langfuse` chỉ AI1 dùng (`src/contract_ocr/infrastructure/observability.py`, `tests/unit/test_observability.py`) | OBSERVED |
| PB-B18 | Máy dev này: `docker` không có trên PATH (Git Bash `command not found`); `uv 0.12.19` có. → Nghiệm thu build image chạy trên GitHub Actions (ubuntu) | OBSERVED |
| PB-B19 | Env đọc lúc import: `load_dotenv` ở `main.py:62-63`; singleton đọc env khi khởi tạo: `JOB_STORE` (`main.py:74`, `jobs.py:49`), `EMBEDDING_CLIENT` (`main.py:77`, `embeddings.py:59-69`), `VECTOR_RECALL` (`main.py:78`, `vector_recall.py:181`) | OBSERVED |
| PB-B20 | Lane xử lý: `runtime.complete_json` (`runtime.py:69-111`) retry 1 lần, chỉ `checkpoint` trước mỗi lần thử; `_is_retryable_provider_error` (`:16-22`) chỉ nhận `TimeoutError`/`ConnectionError` builtin + status — `openai.APITimeoutError`/`APIConnectionError` không kế thừa builtin `[PRIOR]` nên bị xếp không-retry. Gọi LLM xử lý: `fact.py:92`, `table.py:145` (qua runtime); `:94`, `:152` không runtime (lane workspace) | OBSERVED + `[PRIOR]` |

## Ràng buộc (constraint-scan)

- **Zone ghi file.** `harness/data/ownership.yaml:8-16` chỉ ràng buộc script harness (`docs/`, `plans/`, …); path của B không bị chặn. `harness/data/stage-policy.yaml` bước `pr`/`merge` cần `verification`, `review-decision`, `plan-approval` → P4 phát thêm `review-decision.json`.
- **CODEOWNERS.** `.github/CODEOWNERS`: `/.github/` cần `@hieubui2409` → `ai2-release.yml` qua HC-B2.
- **Tiền đề.** A đã merge vào nhánh gốc (D-8): cần `evals/scripts/run_ai2_gate.py`, `evals/scripts/run_live_benchmark.py`, `evals/live/benchmark.py`, `evals/live/pricing.json`, `ai-service/tests/conftest.py` (cô lập `.env`), CI `ai-service.yml`. WIP trên `feature/code-full` phải commit trước. Bước 0 mỗi phase kiểm bằng `Test-Path`/`test -f`; thiếu → dừng, báo main.
- **File dùng chung với A (tuần tự, A xong trước):** `ai-service/app/llm/client.py` (A P3 +`response_model`), `ai-service/pyproject.toml` (A P3 marker), `docs/code-standards.md` (A P4), `evals/live/benchmark.py` + `evals/tests/test_live_benchmark.py` (A P3). B chỉ sửa additive, không đổi ngữ nghĩa của A.
- **File dùng chung với C (C sau B):** `ai-service/app/api/main.py`, `docker-compose.yml`, `backend/.../worker.py`. B không đụng lưu trữ (`jobs.py`, schema Postgres) — thuộc C.
- **Chuẩn code.** `docs/code-standards.md`: Python ≥ 3.12; public schema/API change phải ghi before/after, caller, migration, rollback (mục "Compatibility"); không log secret/raw contract/provider response chưa sanitize; retry chỉ cho lỗi retryable và có giới hạn; `NEEDS_REVIEW/INSUFFICIENT_EVIDENCE/BLOCKED` không hạ thành success.
- **Kiến trúc.** `docs/system-architecture.md`: Backend sở hữu public API/ACL/durable read model; AI2 là candidate producer. B giữ ranh giới: egress quyết ở Backend, AI2 phòng thủ lớp hai.
- **Máy dev.** Không có docker (PB-B18) → phần image chỉ nghiệm thu trên CI; test tĩnh (Dockerfile/compose/workflow) chạy được trên Windows.

## Kiến trúc và luồng dữ liệu

```
QUERY (đồng bộ; caller Backend cắt ở 20 s — settings.py:142-147)
FE → Backend /dossiers/{id}/search | /dossiers/{id}/query
      └─ egress_policy.query_policy_flags(settings)      [P2: server quyết, bỏ policy_flags của client]
   → AI2 POST /query (service envelope ký) → verify → digest guard (main.py:~788, so với record.pins)
      └─ resolve_llm(tenant, requested, lane="query")    [P2: kill switch + allowlist tenant + client configured]
   → QueryRouter(llm) → FourLayerReasoner.run
        L0 → L1 → (COMPARE_TYPES & allow_llm = use_llm ∧ egress) L2
                     └─ LlmCallGuard(deadline, max_calls, breaker, executor có giới hạn) ──► OpenAI
                        LlmUnavailable(code) → _fallback_review (tất định, có citation)
        → L3 ground → {state, answer, citations, llm_called, llm_answer_used, llm_error_code}
   → build_query_response() = ai2.query.v1 (schema_version, 5 state + PASS deprecated)  [P1]
   → Backend (tolerant reader, P1 probe) → FE
   [P4: middleware X-Request-ID/traceparent → log ai2.request/ai2.query theo allow-list + metrics + span L0..L3, LLM]

PROCESSING (bất đồng bộ)
Backend worker → build_processing_request(processing_policy_flags(settings)) → AI2 POST /jobs/idp
   → queued wire (+query_snapshot_digest) → BackgroundTask _run_wire_job
   → resolve_llm(lane="processing") → ProcessingRuntime (call_timeout_scope ≤ thời gian còn lại) → run_idp
   → job_result_to_wire(+query_snapshot_digest) → Backend poll → persist
   → snapshot_digest = result.query_snapshot_digest  (fallback: worker.py:78-110, deprecated)   [P1]

RELEASE
git tag ai2-vX.Y.Z[-rc.N] → ai2-release.yml:
   release-gate (regex SemVer + evals/releases/<tag>.json khớp tree ai-service/) ─┐
   image-check (build, 0 *.sqlite*, không .env, /version, schema load không mount) ─┴→ publish (env ai2-release)
   → GHCR ai2:X.Y.Z[-rc.N] + sha-<7> (không latest) + provenance/SBOM + attestation → digest
   → Backend pin: docker-compose.ai2-image.yml  image: ghcr.io/ai20k-vgr/contract-intelligence-core/ai2:<tag>@<digest>
```

**Lifetime của state mới** (kiểm theo chỉ dẫn "check lifetime before adding state"):
- `LlmCallGuard`, `NineRouterClient`: **mỗi request/run** (client tạo mỗi request như hiện tại `main.py:535`; trace per-instance nên đếm `llm_called` đúng dưới đồng thời).
- `LlmBreaker`, executor + semaphore in-flight, registry metrics, tracer provider: **mỗi process** (1 uvicorn worker, `Dockerfile.ai2:26`). Nhiều worker → mỗi worker một breaker (chấp nhận, ghi trong runbook).
- ContextVar deadline/timeout: **mỗi context request**, luôn reset trong `finally`.

### Thay đổi hợp đồng (before / after / ai bị ảnh hưởng / đường chuyển)

| Bề mặt | Before | After | Ai bị ảnh hưởng | Đường chuyển / rollback |
|---|---|---|---|---|
| `ai2.be.processing.result.v1` | không có digest query | + `query_snapshot_digest` (tuỳ chọn, `^[0-9a-f]{64}$`), ngữ nghĩa **y hệt** digest mà `/query` so | Backend worker | Backend ưu tiên field mới, fallback tự tính (deprecated) trong cửa sổ tới khi C xác nhận E2E; wire cũ trong job store vẫn hợp lệ |
| `/query` response | 3 nhánh lệch key, không schema | `ai2.query.v1` response schema; mọi nhánh có `schema_version`, `connected`, `used_llm`, `llm_called`, `llm_answer_used`, `llm_error_code` | Backend `_search_dto_from_ai2`, `dossiers.py` | Additive; Backend bỏ qua field lạ (P1 probe). `used_llm` = alias `llm_called` (deprecated) |
| `state` query | 6 giá trị không công bố | 5 chuẩn + `PASS` deprecated (VD-B6a) | FE/Backend (đã nhận đủ 6) | Không đổi giá trị đang phát |
| Lỗi HTTP contract | `{code,message}`; 404 `/jobs/{id}` là chuỗi | `ai2.error.v1` `{code,message,retryable}` ở 10 site; message không mang giá trị payload | Backend chỉ log text | Additive (+`retryable`); 404 đổi dạng (Backend không parse detail — `ai_adapters.py:84-91`) |
| Backend → AI2 `policy_flags` (query) | cứng `false` / **client quyết** | `egress_allowed`, `use_llm` = setting; `use_vector` = setting | FE (không gửi flags — grep `frontend/src`), Backend routes | Trường `policy_flags` của `DossierQueryRequest` vẫn nhận nhưng bị bỏ qua (deprecated) |
| AI2 dùng LLM | cần `use_llm ∧ use_vector ∧ egress` | cần `use_llm ∧ egress` + `AI2_LLM_ENABLED` + tenant trong allowlist | Backend flags; A benchmark (đường `legacy_unflagged` giữ nguyên) | Kill switch `AI2_LLM_ENABLED=false` hoàn tác tức thì |
| Endpoint mới | — | `GET /version`, `GET /api/v1/version`, `GET /metrics` | Backend/C (tuỳ chọn), vận hành | Additive |
| `/health` | có `persist: <path>` | bỏ `persist` | demo UI (không đọc `persist`) | Additive-safe |
| Image | build local, schema từ mount host | GHCR `ai2:<semver>` tự chứa schema, `AI2_CONTRACT_ROOT` | compose, C | Re-pin digest cũ; `AI2_CONTRACT_ROOT` fallback đường repo |

## Features
- `versioned-contracts` — contract request/result/query có `schema_version`; JSON Schema mới cho `ai2.query.v1`; `query_snapshot_digest` trong kết quả; đủ 5 giá trị `state`; response lỗi có `code`/`retryable`; changelog + chính sách tương thích (chỉ additive trong v1).
- `versioned-ai2-image` — image AI2 gắn tag semver trên GHCR (`ai2-vX.Y.Z`), có `GET /version` (service, API, contract, model, git sha), `.dockerignore` loại `data/ai2/*.sqlite*`.
- `llm-enabled-ai2` — gỡ 4 chỗ đang tắt LLM (2 chỗ gán cứng ở Backend, `/query` không truyền LLM, L2 đòi cờ vector); bắt lỗi provider ở L2; timeout hỏi đáp < 20 giây; tách `llm_called`/`llm_answer_used`.
- `ai2-observability` — metrics, log có cấu trúc đã redact, trace; latency và chi phí LLM theo lượt.

Kế hoạch này là B trong bộ 3 (A `plans/260929-2323-ai2-a-measure-baseline` → **B** → C `plans/260929-2323-ai2-c-integration`).

## Phases
| # | Theme | Phụ thuộc | Cỡ |
|---|---|---|---|
| 1 | Versioned Contracts: probe Backend khoan dung (test trước), `versions.py` làm SSOT, schema `ai2.query.v1` + `ai2.error.v1`, builder 1 chỗ cho `/query`, 10 site lỗi có `retryable`, sanitize thông điệp lỗi, `query_snapshot_digest` + Backend ưu tiên field mới, CHANGELOG + chính sách tương thích | A đã merge; WIP đã commit | M, ~2 ngày, 3 commit (1a probe, 1b AI2, 1c Backend+docs) |
| 2 | Llm Enablement: egress do server quyết (sửa bypass `dossiers.py:135` **trước**), `resolve_llm` (kill switch + allowlist), `LlmCallGuard` (deadline wall-clock, breaker, trần lời gọi, in-flight có giới hạn), sửa client/runtime/L2/stack, nối `/query`; lượt live HC-B1a chốt VD-B3 | P1 | L, ~3 ngày + HC-B1a, 4 commit (2a Backend, 2b lõi LLM, 2c nối reasoning/API, 2d số đo + mặc định) |
| 3 | Packaging GHCR Image: nướng schema vào image, `AI2_CONTRACT_ROOT`, bỏ `COPY data/`, `.dockerignore`, `/version`, gate `load_dotenv`, `ai2-release.yml` + cổng evidence, override pin `tag@digest`, runbook; publish `ai2-v1.0.0-rc.1` | P1, P2 | M, ~2 ngày + HC-B1b/B2/B3/B4 |
| 4 | Observability: log JSON allow-list (bỏ message exception), `/metrics` ~10 series nhãn hữu hạn, OTel no-op theo env + span L0–L3/LLM `gen_ai.*` không nội dung, chi phí từ `pricing.json` của A; sửa log thô Kafka; tài liệu; publish `ai2-v1.0.0-rc.2` | P2, P3 | M, ~2 ngày + HC-B1c/B4 |

Chuỗi P1 → P2 → P3 → P4 (cạnh tường minh thêm P1→P3, P2→P4). Không `--parallel`: cả 4 phase sửa `ai-service/app/api/main.py`, 3 phase sửa `docker-compose.yml`, và mỗi phase dùng output của phase trước (xem Validation Log VL-2).

## Mốc duyệt của người (agent không tự làm)

| # | Việc | Người | Bằng chứng | Chặn gì |
|---|---|---|---|---|
| HC-B1a/b/c | Cho phép lượt live (khoá qua env, dữ liệu giả lập, `--max-usd 5`): (a) sau P2 để chốt VD-B3; (b) cuối P3 làm evidence rc.1; (c) cuối P4 làm evidence rc.2. Trần tháng của project OpenAI (A VD-5: 20 USD) dùng chung với A | Văn Dũng | xác nhận trong phiên + `summary.json` | Acceptance P2; tag rc |
| HC-B2 | Review `.github/workflows/ai2-release.yml` (CODEOWNERS `/.github/`) | `@hieubui2409` | URL review PR | Merge P3 |
| HC-B3 | Admin repo: environment `ai2-release` (deployment chỉ tag `ai2-v*`; required reviewer theo VD-B2); ruleset tag `ai2-v*` (cấm update/delete, chỉ maintainer tạo); package GHCR: visibility theo VD-B7, liên kết repo, cho workflow quyền ghi | admin repo | ảnh chụp cấu hình/URL | Publish |
| HC-B4 | Commit evidence (`$PY evals/scripts/ai2_release_evidence.py make ...`), tạo và push tag `ai2-v1.0.0-rc.1` (P3) và `ai2-v1.0.0-rc.2` (P4); duyệt deployment `ai2-release` | Văn Dũng | run URL + digest | Acceptance P3/P4 |

Ngoài B: duyệt provider cho dữ liệu thật (D-5) — B giữ "chỉ giả lập".

## Out of scope và bàn giao

- **C** (`plans/260929-2323-ai2-c-integration`): schema `ai2` Postgres (ADR-14); E2E Backend↔AI2 **dùng image GHCR đã pin** qua `docker-compose.ai2-image.yml` (có thể preflight `GET /version` so `contracts.supported` và `contracts.bundle_sha256`); E2E "retry `attempt` mới → Backend cập nhật digest" dựa trên `query_snapshot_digest`; gỡ fallback tự tính digest ở `worker.py:78-110` sau khi E2E xanh; nâng chất lượng + gỡ luật rò rỉ `l0_rules.py`; tag GA `ai2-v1.0.0` với evidence PASS (VD-B1).
- **Không làm trong B:** vector/embedding trên đường query (deadline của B **không** phủ embedding — giữ `ai2_query_use_vector=false`, `AI2_VECTOR_RECALL_ENABLED=false`); Langfuse cho AI2; collector/Prometheus/Grafana (VD-B8); Backend inject `traceparent`/OTel phía Backend; Backend fail-fast theo `/version` lúc khởi động; đổi tên package `contract-ocr-lab`; `linux/arm64`; non-root (VD-B10); LLM cho lane Kafka (D-2 chỉ HTTP; giữ `egress_allowed: False` và có test ghim); lane workspace/demo ngoài kill switch; streaming LLM; thêm status job mới (Backend poll không additive, PB-B6); thuật toán digest v2 (có/không `attempt_id` — research Open Q2); retry cho lỗi LLM trên đường query (mặc định 0 retry).
- **Nhận bàn giao từ A:** `load_dotenv` (P3, VD-B9).

## Acceptance (toàn plan)

Lệnh chuẩn (dùng lại của A):
- AI2 offline — Windows: `cd ai-service; .venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --strict-markers -m "not live and not llm" --basetemp $env:TEMP\ai2pt`; Linux: `cd ai-service && uv run pytest -q -p no:cacheprovider --strict-markers -m "not live and not llm"`.
- Backend: `cd backend; uv run pytest tests/unit -q -p no:cacheprovider`; `uv run ruff check src/ tests/`; `uv run mypy src/`.
- Evals: `$PY -m pytest -q -p no:cacheprovider --strict-markers -m "not live and not llm" evals/tests`.
- Lint AI2: `cd ai-service; .venv/Scripts/ruff.exe check . ../evals` (Linux: `uv run ruff check . ../evals`).

Checklist:
- [ ] Mỗi phase red→green TDD; ba suite trên **0 failed, 0 error** sau mỗi phase, trên Windows và trên CI Linux.
- [ ] Lint + type-check + build: ruff AI2/evals `All checks passed`; ruff Backend 0 lỗi; mypy Backend **không thêm lỗi** so với base (chạy trên base và head, so số lỗi); `uv sync --frozen --extra dev --extra web --extra mistral --extra kafka` exit 0 sau P4 (lock đã cập nhật có chủ đích).
- [ ] (test) Gate offline của A trên head B: `$PY evals/scripts/run_ai2_gate.py --mode pr --base-ref origin/<base>` exit 0 — 0 hồi quy, 0 đơn vị tripwire FAIL mới (chạy sau P2 và sau P4).
- [ ] (invariant) Contract: 5/5 nhánh response `/query` (lệch digest, thành công không LLM, thành công có LLM, LLM lỗi → tất định, fallback chưa có record) validate với `ai2.query.v1.response.schema.json`; 10/10 site lỗi trả đúng `ai2.error.v1`; wire result có `query_snapshot_digest` validate và **bằng** digest mà `/query` so; probe Backend 4/4 kịch bản đúng kỳ vọng (3 khoan dung + 1 status lạ không kết thúc).
- [ ] (test) Ma trận lỗi LLM 10/10 (bảng ở P2): `/query` trả trong ≤ deadline + 1,0 s (deadline test 2 s), `llm_answer_used=false` trừ ca `ok`, `llm_error_code` và số lần server giả bị gọi đúng bảng, 0 exception thoát ra.
- [ ] (test) Egress: 6/6 site Backend có test với cờ kỳ vọng; client gửi `{"egress_allowed": true, "use_llm": true}` → payload sang AI2 mang cờ của settings (mặc định `false`); kill switch tắt hoặc tenant ngoài allowlist → **0** lần gọi server giả trên 5 lane (`/query`, `/jobs/idp`, Kafka worker, workspace reason, case run).
- [ ] (manual — `manual_test_anchor.py`) HC-B1a: `$PY evals/scripts/run_live_benchmark.py --k 3 --max-usd 5 --load-dotenv --fail-on-threshold --tripwire-only` trên head P2 exit 0 (0 hồi quy tripwire); báo n(`used_llm=true`), p95 kèm CI, tỉ lệ `DEADLINE_EXCEEDED`, chi phí; VD-B3 chốt theo quy tắc, ghi Validation Log.
- [ ] (CI) Job `image-check` của `ai2-release.yml` xanh trên 1 PR (URL trong `verification-P3.json`): 0 file `*.sqlite*` trong image, không có `/app/.env`, `/version.service_version` = version build, `/version.git_sha` = commit, load schema thành công **không** mount `docs`, `/healthz` 200 trong ≤ 60 s.
- [ ] (test) Cổng evidence 7/7: GA PASS→0; GA FAIL→1; rc 0 hồi quy→0; rc có hồi quy tripwire→1; tree `ai-service/` lệch→1; thiếu file evidence→2; tag sai SemVer→2.
- [ ] (manual — HC-B4) `ai2-v1.0.0-rc.1` (cuối P3) và `ai2-v1.0.0-rc.2` (cuối P4): workflow xanh; GHCR có đúng tag `1.0.0-rc.N` + `sha-<7>`, **không** có `latest`; `gh attestation verify oci://ghcr.io/ai20k-vgr/contract-intelligence-core/ai2:1.0.0-rc.N -R AI20K-VGR/contract-intelligence-core` exit 0; `docker buildx imagetools inspect <ref> --format "{{json .SBOM}}"` khác rỗng; `docker compose -f docker-compose.yml -f docker-compose.ai2-image.yml config` render `image: ...:1.0.0-rc.N@sha256:<digest>`; digest ghi trong runbook AI2-17.
- [ ] (test) Quan sát: canary 0/8 (4 kịch bản × {chuỗi hợp đồng `CANARY-HD-7f3a`, khoá `sk-test-CANARY`}) không xuất hiện trong log bắt được (stdout/stderr/caplog) và trong `/metrics`; `/metrics` có đúng 10 series đặt tên ở P4, nhãn thuộc tập hữu hạn; OTel không endpoint → 0 lần export; với in-memory exporter có span L0–L3 + `ai2.llm.call`, 0 attribute chứa nội dung.
- [ ] (invariant) Không lộ secret: `git grep -nE "sk-[A-Za-z0-9_-]{20,}" -- ai-service backend evals docs .github docker-compose*.yml` → 0 hit.
- [ ] **Không** thuộc acceptance B: tag GA `ai2-v1.0.0` (cần PASS, VD-B1a → C).

## Test matrix (tóm tắt)

| Tầng | Cái gì | Ở đâu |
|---|---|---|
| Unit | builder `/query`, map state, catalog lỗi, sanitize thông điệp, `versions.py`; phân loại lỗi provider (class `openai` thật), breaker, deadline, trần lời gọi, in-flight, fallback `response_format`; `resolve_llm`; `/version`; hygiene Dockerfile/compose/`.dockerignore`; invariant workflow; cổng evidence; logger allow-list, pricing, metrics | `ai-service/tests/test_versioned_contracts.py`, `test_llm_guard.py`, `test_version_endpoint.py`, `test_packaging_hygiene.py`, `test_observability_*.py`, `evals/tests/test_ai2_release_*.py`, `backend/tests/unit/test_ai2_*.py` |
| Integration | `TestClient` + server OpenAI giả trên `127.0.0.1:0` (silent/trickle/401/403/400/429/500/JSON hỏng/ok); job `/jobs/idp` → poll → `/query` với digest; Backend worker với report giả; canary xuyên log | P1, P2, P4 |
| E2E / live | Lượt live A (HC-B1a/b/c); build + publish image thật trên Actions; `gh attestation verify` | P2, P3, P4 (manual anchor) |

## Rollback
- Mỗi commit con là một commit riêng; hoàn tác bằng `git revert <range>` theo thứ tự ngược, rồi chạy lại regression gate của phase trước.
- **P1:** field mới đều tuỳ chọn; Backend còn fallback tự tính digest nên revert AI2 không làm Backend sai; sanitize thông điệp revert độc lập.
- **P2 rollback:** cấu hình được đọc lúc process khởi động (xác minh ở P2 preflight); đổi env không tác động process đang chạy. Không cần image/code deploy, nhưng phải restart/recreate AI2 và Backend workloads theo runbook, rồi chạy probe canary với upstream mock để xác nhận 0 lần gọi provider trước khi đóng incident. Thứ tự: set `AI2_LLM_ENABLED=false`, `AI2_QUERY_EGRESS_ALLOWED=false`, `AI2_PROCESSING_EGRESS_ALLOWED=false`; restart AI2 và Backend; kiểm tra `/version`/health và zero-call probe. **Không** revert riêng commit 2a khi 2c còn — revert 2c trước.
- **P3:** re-pin digest trước trong env compose; tắt workflow; tag đã phát không bao giờ push lại (ruleset HC-B3). `AI2_CONTRACT_ROOT` fallback đường repo nên compose cũ (có mount) vẫn chạy.
- **P4:** `AI2_METRICS_ENABLED=false`, bỏ `OTEL_EXPORTER_OTLP_ENDPOINT`, `AI2_LOG_FORMAT=text`; gỡ dependency cần revert cả `uv.lock`.

## Risks

| # | Rủi ro | Khả năng × Tác động | Giảm thiểu |
|---|---|---|---|
| R1 | Egress vòng qua cờ client (`dossiers.py:135`) khi `/query` có LLM | Cao × Cao | Commit 2a trước 2c; test ghim; lớp 2 ở AI2 (kill switch + allowlist, VD-B5) |
| R2 | Deadline không được tôn trọng (trickle, PB-B1) | Trung × Cao | Deadline wall-clock bằng `future.result(timeout)` + timeout httpx theo phần còn lại; test trickle |
| R3 | Thread bị bỏ rơi chiếm tài nguyên/chi phí | Trung × Cao | Permit chỉ nhả khi future/provider call thực sự kết thúc; semaphore + executor giới hạn 4, không backlog; stuck call giữ permit và fail-closed `SATURATED`; runbook recycle process nếu provider không hồi đáp |
| R4 | Backend không khoan dung như giả thuyết | Thấp × Cao | P1 bước 1 probe trước khi thêm field; nếu đỏ: sửa Backend trước, release Backend→AI2 |
| R5 | Khoá chéo D-6 (B cần PASS, PASS cần C) | Cao × Cao | VD-B1 (rc vs GA) |
| R6 | Image không tự chứa (PB-B12) | Cao (OBSERVED) × Cao | Nướng schema + `AI2_CONTRACT_ROOT`; smoke load schema không mount |
| R7 | Dữ liệu hợp đồng lọt vào image/layer/git | Trung × Cao | `.dockerignore`, bỏ `COPY data/`, CI `find` 0 sqlite, ignore `data/ai2/` |
| R8 | Tag GHCR ghi đè được `[ASSUMED]` | Trung × Trung | Pin digest; ruleset tag (HC-B3); workflow không bao giờ push lại tag đã có |
| R9 | Thông điệp lỗi/traceback mang nội dung hợp đồng | Trung × Cao | Sanitize 3 nguồn (P1); formatter bỏ message exception (P4); test canary |
| R10 | Lệch interface với A (key JSON, chữ ký `BudgetedClient`) `[ASSUMED]` | Trung × Trung | Bước 0 mỗi phase đọc file thật của A; guard bọc lời gọi bằng duck-typing, không đổi chữ ký `complete_json` |
| R11 | Claim chất lượng dựa trên fixture HD rò rỉ | Trung × Cao | B chỉ claim "0 hồi quy"; C gỡ luật |
| R12 | Trần tháng OpenAI 20 USD dùng chung A/B | Thấp × Trung | Mỗi lượt `--max-usd 5`; chi phí thật ước ≪ trần `[ASSUMED]`; exit 4 → không phát tag |
| R13 | Compose `additional_contexts` cần Compose v2.17+ `[PRIOR]` | Thấp × Trung | Ghi runbook; CI dùng buildx `build-contexts` |
| R14 | Nhãn metric bùng nổ cardinality | Thấp × Trung | Route template, enum outcome; test đếm tập nhãn |
| R15 | Máy dev không build được image (PB-B18) | Cao × Thấp | Test tĩnh chạy Windows; build/publish trên Actions |

## Red-Team Disposition

| Finding | Disposition | Plan update / evidence |
|---|---|---|
| SEC-1 (high, proven): old-format AI2 error body reaches Backend logs/storage verbatim | Accept | P1 F1.6, file inventory, and graph now include `backend/.../infrastructure/ai_adapters.py`; sanitize upstream response to allow-listed status/code and add canary tests through adapter + worker. Report: `reports/from-code-reviewer-to-planner-red-team-security-adversary-plan-review-report.md`. |
| FM-1 (high, suspected): timed-out provider future outlives caller and makes permit release ambiguous | Accept | P2 now binds the in-flight permit to actual future completion; bounded executor/no backlog; tests assert the cap during a blocked call and recovery after completion. A never-finishing call remains fail-closed and requires process recycle. Report: `reports/from-code-reviewer-to-planner-red-team-failure-mode-analyst-plan-review-report.md`. |
| OPS-1 (medium, suspected): env-only rollback may leave startup-loaded settings active | Accept | P2 rollback now states startup-bound behavior, restart/recreate sequence without image deploy, and zero-upstream-call verification. Report: `reports/from-code-reviewer-to-planner-red-team-bad-day-operator-plan-review-report.md`. |

All accepted findings are propagated to phase requirements, file ownership, verification, or runbook scope. P2 preflight must verify the actual settings reload semantics; if runtime behavior differs from the stated startup-bound assumption, revise rollback steps before implementation.

## Validation Log
- VL-1 | complexity: complex · 4 phases · risk: egress/bảo mật, deadline, đóng gói | mode `--hard --tdd` | giữ nguyên.
- VL-2 | Áp **`--deep`**: rủi ro nằm ở biên hai service (contract, egress, deadline) và đóng gói, mỗi phase cần file inventory, ma trận kịch bản test, dependency map. **Không `--parallel`**: DAG là chuỗi, cả 4 phase sửa `ai-service/app/api/main.py`, P2/P3/P4 sửa `docker-compose.yml`, và mỗi phase tiêu thụ output phase trước (`versions.py` → `/version`; `LlmSettings`/observer của guard → P4).
- VL-3 | Phase > 8 file: P1 17, P2 27, P3 17, P4 18. Giữ 4 phase do người dùng khoá; chia commit con có gate riêng.
- VL-4 | Sửa research: (a) research coi `read timeout = remaining` là "cơ chế chặn thật", nhưng chính probe trickle của research phủ định (PB-B1) → B thêm deadline wall-clock; (b) research không thấy image phụ thuộc mount `docs` (PB-B12); (c) Open Q7 đã có câu trả lời: runtime chỉ cần `data/ai2` (PB-B13); (d) `langfuse` có người dùng (AI1), chỉ AI2 là chưa dùng; (e) "4 chỗ tắt LLM" thực tế là 3 chỗ phía AI2 + 6 site Backend, trong đó `dossiers.py:135` là bypass tiềm ẩn.

## Câu hỏi còn mở
1. Key chính xác của `threshold_verdict` trong report gate (`run_ai2_gate.py --report-json`) và `summary.json` live của A; schema `evals/live/pricing.json` — `[ASSUMED]`, P3/P4 bước 0 đọc file thật.
2. Máy của team có Docker Compose ≥ v2.17 không (cho `additional_contexts`).
3. Snapshot `gpt-4o-mini` có ngày mà A chốt ở A-P3 bước 1 (dùng làm default compose theo VD-B4).
