# Research: versioning dịch vụ AI2, GHCR, bật LLM đồng bộ, observability (plan B)

Ngày: 2026-09-30. Phạm vi: 4 câu hỏi mở của plan B, tôn trọng D-1..D-8 (đã khoá, không re-litigate). Ngoài phạm vi: chọn provider LLM (D-5 đã chốt), Keycloak/AI1, ADR-14.

Nhãn bằng chứng: `OBSERVED` = đọc/grep/chạy trong repo; `FETCHED` = đã mở URL trong phiên này; `SEARCH` = chỉ thấy snippet kết quả tìm kiếm, chưa mở nguồn gốc; `[PRIOR]` = kiến thức huấn luyện chưa kiểm; `[ASSUMED]` = suy luận chưa chạy.

---

# PART 1 — OBSERVED trong repo

## 1.1 Version hiện tại: 3 nguồn sự thật, không nguồn nào nối với release

- `FastAPI(title="VSF AI2 IDP", version="0.1.0")` hard-code: `ai-service/app/api/main.py:67`.
- `pyproject.toml`: `name = "contract-ocr-lab"`, `version = "0.1.0"` (`ai-service/pyproject.toml:6-7`). Tên package là của OCR lab, không phải AI2.
- Git tag hiện có: `be-ban-1`, `fe-ban-1`, `v0.1.0` (chạy `git tag`). Không có prefix theo service. `v0.1.0` mơ hồ trong monorepo.
- Không có route `/version` (grep `"/version"` trong `main.py` rỗng). `/health` trả `status/llm/model/persist/embedding` (`main.py:677-695`), `/healthz` trả `{"status":"ok"}` (`main.py:698-702`). `/health` khởi tạo `NineRouterClient()` mỗi lần gọi (`main.py:679`) và có thể gọi `EMBEDDING_CLIENT.discover` (egress) nếu env bật (`main.py:680-687`) -> healthcheck compose (`docker-compose.yml`, block `ai2-service`, `healthcheck` gọi `/health`, timeout 3s) có thể chạm mạng ngoài. Nên tách liveness/readiness khỏi `/version`.
- API path đã có dạng kép: `@app.post("/query")` + `@app.post("/api/v1/query")` (`main.py:751-752`); `/process` + `/api/v1/process` (`main.py:~705`). Nghĩa là "API version" đã có chỗ đặt (`/api/v1`) nhưng chưa được coi là trục riêng.
- Compose build local, không kéo image: `docker-compose.yml:442-445` (`ai2-service: build: context ./ai-service, dockerfile Dockerfile.ai2`). Chưa có `image:` pin.

## 1.2 Contract: strict cả hai phía, nên "additive" KHÔNG tự động an toàn

- Schema kết quả có 9 chỗ `additionalProperties: false` (`grep -c` trên `docs/contracts/ai2.be.processing.result.v1.schema.json` = 9; ví dụ dòng 7, 13, 23, 35). Schema request = 6 chỗ (`be.ai2.processing.request.v1.schema.json`).
- `schema_version` là `const` cứng: `ai2.be.processing.result.v1` (schema dòng 81; code `main.py:152`).
- Pydantic phía AI2 dùng `ConfigDict(extra="forbid")` cho model wire (`ai-service/app/contracts/wire.py:26, 50, 59, 69, 87`). Tức AI2 từ chối request có field lạ: Backend thêm field vào request trước khi AI2 nâng cấp sẽ bị 4xx.
- Lỗi đã có `code/message/retryable` bắt buộc trong schema (`result.v1.schema.json:59-60`). Feature "response lỗi có `code`/`retryable`" phần lớn đã đúng ở result; cần kiểm `/query` và các nhánh lỗi HTTP khác (chưa có schema `ai2.query.v1` — thư mục `docs/contracts/` không có file này; `main.py:776-784` chỉ so chuỗi `"ai2.query.v1"`).
- Backend có parse AI2 payload bằng `model_validate` cho extraction/comparison (`shared/ai/persistence.py:461, 575`; `pipeline_orchestrator.py:394, 456`). CHƯA xác nhận Backend model có `extra=forbid` hay không cho result/query response -> mở (Open Q1).

## 1.3 Digest của `/query`: chuỗi so khớp tuyệt đối, có `attempt_id` bên trong

- AI2 tính `request_digest = _canonical_digest(payload)` (`ai-service/app/pipeline/ai1_snapshot_adapter.py:215`); hàm là sha256 của JSON canonical `sort_keys` (`:2288-2291`). Payload tương thích chứa `attempt_id` = `f"attempt:{request.attempt}"` (`:111`).
- `/query` so `requested_digest` với `record.pins.source_snapshot_digest` bằng so sánh chuỗi (`main.py:775-780`).
- Backend tự dựng lại cùng thuật toán: `backend/src/contract_intelligence/worker.py:78-110` (`_ai2_query_snapshot_digest`, docstring "Match AI2's canonical request digest"). Hai bản cài đặt độc lập của cùng một hash = coupling ngầm; bất kỳ đổi field/thứ tự/`attempt` nào ở một bên làm mọi query báo stale.
- Hệ quả: retry (attempt+1) cùng nội dung sinh digest khác. Đây là quyết định sản phẩm chưa được ghi lại (Open Q2).

## 1.4 Bốn chỗ tắt LLM (xác nhận anchor)

- Backend: `shared/ai/canonical_processing.py:350` `"egress_allowed": False`.
- Backend: `contract/interfaces/api/routers/contract_router.py:806` `"policy_flags": {"egress_allowed": False}`, bỏ qua `settings.ai2_query_egress_allowed` (định nghĩa `config/settings.py:148`, default False).
- Còn 3 chỗ Backend nữa cùng hard-code False mà brief không liệt kê: `api/v1/webhooks.py:186` (`egress_allowed False, use_vector True`), `infrastructure/ai_adapters.py:446`, `schemas/queries.py:17` (default_factory). Phase 2 phải grep toàn bộ, không chỉ 2 chỗ.
- AI2 `/query` dựng `QueryRouter(STORE, ToolGateway(STORE))` không có llm (`main.py:823`).
- `reasoning/stack.py:120-123`: `allow_llm = use_llm is True AND use_vector is True AND egress_allowed is True`.

## 1.5 Client LLM: tổng thời gian xấu nhất >> 20 giây (phát hiện chính)

- `NineRouterClient`: `timeout = float(env AI2_LLM_TIMEOUT_SECONDS, default 45)`, `OpenAI(..., timeout=timeout, max_retries=0)` (`ai-service/app/llm/client.py:27-28`). Default 45s > ngân sách 20s của caller.
- `complete_json` bắt MỌI `Exception` ở lần gọi đầu rồi gọi lần hai không có `response_format` (`client.py:49-72`). Kể cả 401/timeout cũng gọi lần hai. => một `complete_json` có thể tốn 2 x 45s = 90s.
- L2 gọi LLM ở `l2_plan.py:158` (`self.llm.complete_json(...)`) không try/except cho lỗi provider (chỉ bắt `ToolBlocked`, `TypeError` ở `:146-152`); ngoài ra có `self._plan(...)` (LLM) và replan tối đa `MAX_REPLAN` lần (`l2_plan.py:~148-153`). Nhiều lần gọi LLM tuần tự mỗi query, không có deadline chung.
- `ProcessingRuntime` đã có sẵn khái niệm budget + retry: phân loại retry 408/409/429/>=500 (`ai-service/app/pipeline/runtime.py:16-22`), `retry_limit: int = 1` (`:39`), `ProcessingTimeout("processing time budget exceeded")` (`:52`). Có thể tái dùng pattern cho query path.
- Trace token đã ghi `prompt_tokens/completion_tokens/total_tokens` (`client.py:77-82`) và chỉ lưu `request_digest[:16]` + số ký tự, không lưu nội dung (`client.py:37-44`) => pattern redact tốt, giữ lại.

## 1.6 Probe thực (chạy trong phiên này) — hành vi timeout/retry của SDK

Môi trường: `openai 3.14.0` (khớp `uv.lock:998-999`), `httpx 0.28.1`, server giả trên 127.0.0.1. `timeout=2.0`:

| Server giả | max_retries | Kết quả | Thời gian | Số kết nối |
|---|---|---|---|---|
| im lặng (nhận request, không trả) | 0 | `APITimeoutError` | 3.0s | 1 |
| im lặng | 2 | `APITimeoutError` | 7.4s | 3 |
| trickle (gửi header, rồi 1 byte/giây x 8) | 0 | `APITimeoutError` | 10.0s | 1 |
| trickle | 2 | `APITimeoutError` | 31.4s | 3 |

Đọc kết quả: (a) `timeout` là timeout THEO PHA (read reset mỗi khi có byte), KHÔNG phải deadline tổng: trickle 8 byte làm call sống 10s dù `timeout=2`. (b) `max_retries=2` nhân thời gian gần x3 và cộng backoff. (c) Trường hợp im lặng 3.0s > 2.0s: chưa giải thích được phần dư ~1s (Open Q6). Kết luận: 20s wall-clock phải được ép ở tầng ứng dụng bằng deadline tính từ `time.monotonic()`, không tin tham số `timeout` của SDK. Đây là probe cục bộ (không gọi OpenAI thật), chỉ chứng minh cơ chế client.

## 1.7 Packaging / CI

- `Dockerfile.ai2`: `COPY data/ data/` (`:22`), `EXPOSE 8002`, CMD 1 tiến trình uvicorn (`:26`). Không có `.dockerignore` ở `ai-service/` hay root (`ls -a` không thấy). `ai-service/data/ai2/` chứa `jobs.sqlite`, `vectors.sqlite` (untracked trong git status, `.gitignore` không có rule sqlite: grep rỗng). Build local sẽ nhét dữ liệu hợp đồng vào layer; compose che bằng volume `ai2_data:/app/data/ai2` nên dev không thấy, nhưng image push lên GHCR sẽ mang theo nếu build từ cây làm việc bẩn. CI checkout sạch thì không có (file untracked), nhưng `.dockerignore` vẫn là lớp phòng thủ bắt buộc.
- `.github/workflows/ai-service.yml` là placeholder: `permissions: contents: read`, step `echo "no CI defined for ai-service yet"`. Có sẵn `backend-ci.yml`, `frontend.yml`, `pr-guard.yml`, `labeler.yml`.
- Dependency: `pyproject` khai `langfuse>=4.15,<5` (`pyproject.toml`, deps list) và `uv.lock:844-845` lock `langfuse 4.15.6`; Backend khai `opentelemetry-api/sdk/instrumentation-fastapi` (`backend/pyproject.toml:24-26`). Grep `opentelemetry|langfuse|prometheus` trong `backend/src` và `ai-service/app` (py) = 0 file => đã khai báo nhưng CHƯA dùng.

## 1.8 Observability stack hiện có

- `docker-compose.yml` chỉ có: keycloak-db, keycloak, backend-db, kafka, backend, backend-worker, ai1-worker, ai2-service, minio, mailpit, minio-init (grep `^\s{2}name:` + `image:`). KHÔNG có Prometheus/Grafana/Loki/Jaeger/OTel collector. Grep từ khoá tương ứng trong compose/pyproject chỉ trúng 3 dòng OTel của Backend.
- => Mọi thứ "cần backend hạ tầng" (collector, Prometheus server) là thêm mới; phải cân với D-4 (EXPANSION đã khoá) nhưng không được giả định có sẵn.

---

# PART 2 — Nguồn ngoài

## Q1. Versioning: 3 trục độc lập, chính sách tương thích, pin, `/version`

Bằng chứng ngoài:
1. Google AIP-180 (FETCHED, https://google.aip.dev/180): thêm component mới (field, message, enum value) được phép trong cùng major; không được thêm field required vào request; không được đổi ngữ nghĩa hiển thị ("must not change visible behavior or semantics"); đổi tên = xoá + thêm; thêm enum value ở response "cần thận trọng" vì client có thể không xử lý giá trị lạ.
2. Stripe (FETCHED, https://stripe.com/blog/api-versioning): phiên bản theo ngày, thêm field mới là an toàn, đổi kiểu/xoá field là cấm; client được "pin" phiên bản (header `Stripe-Version` hoặc pin mặc định của account); thay đổi phá vỡ gói trong "version change modules".
3. SemVer 2.0.0 [PRIOR] (https://semver.org, chưa mở): MAJOR = phá vỡ API công khai, MINOR = thêm tương thích ngược, PATCH = sửa lỗi. Áp cho image tag.
4. Cross-check nội bộ: repo đã dùng tên-có-major cho contract (`...result.v1`) — giống kiểu AIP (major nằm trong tên), phù hợp giữ.

Đánh giá cho AI2 (1 consumer):
- Không dùng date-based kiểu Stripe: Stripe cần vì hàng nghìn client; ở đây 1 Backend, lockstep release là khả thi và rẻ hơn. Nhưng học được 2 ý: client pin rõ ràng, và đổi ngữ nghĩa = đổi version.
- Ba trục, mỗi trục có một nguồn sự thật:
  - Image: SemVer `X.Y.Z`, tag git `ai2-vX.Y.Z`. Nguồn sự thật: git tag; build inject vào image (`--build-arg`), `/version` đọc từ env/file, hết hard-code `main.py:67`. `pyproject` nên bỏ là nguồn (name/version thuộc OCR lab).
  - API: `/api/v1/...` (đã có, `main.py:751-752`). Chỉ tăng khi đổi route/method/status semantics. Không liên quan số image.
  - Contract: `schema_version` chuỗi (`ai2.be.processing.result.v1`, `ai2.query.v1`). Major nằm trong tên; tăng major = schema mới song song, không sửa tại chỗ.
- Quy tắc bump image: MAJOR khi bỏ hỗ trợ một contract/API major hoặc đổi ngữ nghĩa; MINOR khi thêm field/route/state tương thích; PATCH khi sửa lỗi/nội bộ. Rule ghi vào CHANGELOG, đặt cạnh `docs/contracts/README.md`.
- Deprecation (đơn giản do 1 consumer): AI2 hỗ trợ contract major N và N-1 ít nhất 1 chu kỳ release B/C; `/version` liệt kê `contracts.supported`; xoá N-1 chỉ ở image MAJOR mới.
- Cách Backend pin: (i) compose/Helm dùng `image: ghcr.io/<owner>/<repo>/ai2:1.2.3@sha256:<digest>` (tag để đọc, digest để bất biến); (ii) Backend đọc `GET /version` lúc khởi động và fail-fast nếu `contracts.supported` không chứa contract nó nói [ASSUMED: chưa chạy, cần test]; (iii) bump pin qua PR (Renovate/Dependabot cho docker image [PRIOR]).
- `GET /version` tối thiểu: `service` (`ai2`), `service_version`, `api_versions` (`["v1"]`), `contracts.supported` (list), `model`/`strong_model` (từ `NineRouterClient`, không trả API key), `git_sha`, `build_time`, `llm_enabled` (cờ cấu hình, không phải kết quả gọi thật). Không trả path dữ liệu (hiện `/health` trả `persist: str(DATA)` `main.py:692`, nên bỏ khỏi endpoint công khai). Không chạm mạng, không tạo client.

Câu hỏi "đổi ngữ nghĩa digest / thêm field vào result v1 có an toàn additive không?":
- Thêm field vào result v1: CHỈ an toàn với consumer "tolerant reader". Ở đây cả schema (`additionalProperties:false` x9) lẫn pydantic AI2 (`extra=forbid`) đều strict. AIP-180 và Stripe đều mặc định "additive = an toàn" dựa trên giả định client bỏ qua field lạ; giả định đó KHÔNG được chứng minh ở repo này. Hành động: (a) xác nhận Backend đọc result/query bằng model `extra=ignore`; nếu chưa, đổi sang ignore TRƯỚC (Backend release trước), rồi mới cho AI2 phát field mới; (b) giữ `additionalProperties:false` trong schema như guard phía producer, kèm quy tắc văn bản "consumer MUST ignore unknown fields"; (c) contract test: output AI2 validate với schema trong repo để schema không lệch code.
- Thêm giá trị `state` (đủ 5 giá trị): theo AIP-180 là "thận trọng" — Backend phải có nhánh default cho state lạ.
- Đổi ngữ nghĩa digest: KHÔNG additive (AIP-180: đổi ngữ nghĩa = breaking). Lối an toàn: thêm `query_snapshot_digest` vào result (đúng feature đã khoá) để Backend đọc thẳng thay vì tự tính lại (`worker.py:78-110` bị loại bỏ dần); `/query` tiếp tục nhận `snapshot_digest` theo thuật toán cũ trong cửa sổ deprecation; nếu sau này đổi thuật toán thì thêm `digest_algorithm` (ví dụ `sha256:v2`) và hỗ trợ song song. Đây cũng chấm dứt hai bản cài đặt hash độc lập.

## Q2. Publish GHCR bằng GitHub Actions

Bằng chứng:
1. GitHub Docs (FETCHED, docs.github.com ... working-with-the-container-registry): xác thực bằng `GITHUB_TOKEN` với quyền `packages: write`; package mới mặc định private; kéo theo digest `ghcr.io/NS/IMG@sha256:...`. Tài liệu trang này KHÔNG nói về tính bất biến của tag.
2. Docker Docs (FETCHED, https://docs.docker.com/build/ci/github-actions/attestations/): `provenance: mode=max`, `sbom: true` trên `docker/build-push-action`; repo public mặc định `mode=max`, repo private `mode=min`; attestation yêu cầu push thẳng lên registry (không `load` vào local store).
3. docker/metadata-action (FETCHED, https://github.com/docker/metadata-action): rút version từ git tag có prefix bằng `type=match,pattern=ai2-v(.*),group=1` (hoặc `type=semver` + `match=`); `latest` sinh tự động ở chế độ `auto` — phải tắt bằng `flavor: latest=false` nếu không muốn `latest` (vì latest phá ý đồ pin).
4. GitHub Docs artifact attestations (FETCHED, docs.github.com ... using-artifact-attestations...): cần `id-token: write, contents: read, attestations: write, packages: write`; action `actions/attest` với `subject-name` (không tag), `subject-digest`, `push-to-registry: true`; consumer kiểm bằng `gh attestation verify oci://ghcr.io/ORG/IMAGE:tag -R ORG/REPO`.
- Tag GHCR có mutable không: tài liệu trang GitHub không nói. [PRIOR] tag là con trỏ đổi được (push lại cùng tag ghi đè) — GHCR không có "immutable tags" kiểu ECR bật cứng. [ASSUMED] cho đến khi kiểm docs GHCR chi tiết hơn. Vì vậy digest pin là cơ chế bất biến duy nhất chắc chắn; thêm quy ước "không bao giờ push lại tag `ai2-vX.Y.Z` đã phát hành" + rule bảo vệ tag `ai2-v*` (GitHub tag protection/ruleset [PRIOR]).

Thiết kế đề xuất:
- Workflow riêng `ai2-release.yml` (đừng nhồi vào `ai-service.yml` PR CI, giữ PR CI `contents: read`). Trigger `push: tags: ["ai2-v*"]`. Quyền: `contents: read, packages: write, id-token: write, attestations: write`.
- Tag ảnh: `ai2:1.2.3` (từ `type=match`), `ai2:sha-<short>`; `latest=false`; không tag `1.2`/`1` để tránh trôi không kiểm soát (Backend pin đúng `X.Y.Z@digest`).
- Gate trước publish: tag phải khớp semver regex; test AI2 xanh; và theo D-6/D-7, release yêu cầu `threshold_verdict = PASS` (chạy tay, nên workflow chỉ kiểm sự tồn tại artifact verdict hoặc dùng `environment:` có reviewer — mở Open Q4).
- Provenance + SBOM: `provenance: mode=max`, `sbom: true` trên build-push-action; thêm `actions/attest` cho digest. Chi phí thấp, đáng làm vì D-4 EXPANSION. SBOM/attestation làm manifest có thêm entry `unknown/unknown` — chỉ ảnh hưởng công cụ liệt kê, không ảnh hưởng `docker pull` [PRIOR].
- Multi-arch: [ASSUMED] chỉ `linux/amd64` ban đầu (compose chạy trên Docker Desktop Windows/Linux x86, `docker-compose.yml` không có `platform:`). Thêm `linux/arm64` chỉ khi có dev dùng Apple Silicon; QEMU build với pymupdf/opencv/numpy chậm đáng kể [PRIOR]. Cần xác nhận với team (Open Q5).
- Visibility: package mới mặc định private (nguồn 1) -> host chạy Backend phải `docker login ghcr.io` với PAT `read:packages`, hoặc chuyển package sang public/liên kết repo. Phải ghi vào runbook.
- `.dockerignore` (feature đã khoá) tối thiểu loại `data/ai2/*.sqlite*`, `.env`, `.venv`, `__pycache__`, `reports/`, `experiments/`, `ocr-benchmark/`. Đề xuất thêm bước CI: `docker run --rm image find /app/data -name '*.sqlite*'` phải rỗng (chưa chạy, [ASSUMED]).
- Lưu ý ngữ nghĩa Dockerfile: `COPY data/ data/` (`:22`) copy cả `data/` cần thiết cho runtime? Chưa xác định file nào trong `data/` (ngoài `ai2/`) thật sự cần -> Open Q7.

## Q3. Bật LLM trong query đồng bộ, caller timeout 20s

Bằng chứng:
1. OpenAI Python README (FETCHED, https://github.com/openai/openai-python): default timeout 10 phút; nhận float hoặc `httpx.Timeout`; ghi đè từng request bằng `.with_options(timeout=...)`; ném `APITimeoutError`; tự retry mặc định 2 lần với exponential backoff cho lỗi kết nối, 408, 409, 429, >=500; `max_retries=0` tắt; request ID qua `exc.request_id`. README main dùng `httpx2` trong text — có thể khác vài chi tiết với 3.14.0, nhưng hành vi timeout/retry đã được probe ở 1.6.
2. httpx docs (FETCHED, https://www.python-httpx.org/advanced/timeouts/): 4 loại timeout connect/read/write/pool, mỗi loại chỉ chặn từng pha; trang không nói có deadline tổng. Trùng khớp probe 1.6 (trickle sống 10s với timeout 2s).
3. Azure Circuit Breaker pattern (FETCHED, https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker): trạng thái Closed/Open/Half-Open; ở Open có thể "return a default value that's meaningful to the application"; kết hợp Retry nhưng retry phải dừng khi breaker báo lỗi không tạm thời; cảnh báo timeout quá dài làm breaker không bảo vệ được; phải có observability cho chuyển trạng thái; đừng dùng để thay xử lý lỗi nghiệp vụ.
4. OpenAI docs khác về rate-limit/backoff: [PRIOR], không mở thêm.

Đánh giá / thiết kế:
- Vấn đề gốc là cấu trúc, không phải tham số: xấu nhất hiện tại = (số lần gọi LLM/query) x (2 lần thử trong `complete_json`) x 45s (1.5). Không chỉnh timeout được cho đủ 20s nếu không có deadline chung.
- Deadline chung theo request: tạo `QueryDeadline` (đơn điệu `time.monotonic()`), mặc định tổng LLM <= ~12s (chừa ~8s cho retrieval, ghép câu, mạng Backend->AI2 và dự phòng; số này là [ASSUMED], cần đo từ benchmark A). Truyền vào `NineRouterClient`; mỗi lần gọi dùng `client.with_options(timeout=httpx.Timeout(connect=2, read=min(remaining, cap), write=5, pool=2), max_retries=0)`; trước mỗi lần gọi kiểm `remaining > min_needed` nếu không bỏ qua LLM. Vì `def` sync chạy trong threadpool của FastAPI [PRIOR] không huỷ thread được, nên read-timeout = remaining là cơ chế chặn thật; đừng dựa `asyncio.wait_for`.
- Retry: 0 retry cho luồng đồng bộ theo mặc định. Cho phép tối đa 1 retry chỉ khi (lỗi thuộc {408,409,429,>=500,connection}) VÀ `remaining` còn đủ >= 2x p50 latency; không retry 400/401/403/404/422. Tái dùng phân loại `_is_retryable_provider_error` (`runtime.py:16-22`).
- Bỏ "fallback without json_format" theo kiểu bắt mọi Exception (`client.py:57`): chỉ áp dụng khi lỗi là 400 nói về `response_format` (ví dụ model/proxy không hỗ trợ); các lỗi 401/timeout/5xx không được gọi lần hai.
- Fail-closed: bọc `l2_plan.py:158` (và `_plan`) bằng try/except loại lỗi provider (`APITimeoutError`, `APIConnectionError`, `APIStatusError`, `RateLimitError`, JSON parse) -> trả `draft=None, skipped/blocked` như nhánh hiện có, rồi tầng lắp ráp trả câu trả lời tất định (retrieval + citation). Ghi `llm_called=True, llm_answer_used=False, llm_error_code=<enum>` (đúng feature "tách `llm_called`/`llm_answer_used`"). Lỗi 401 đã làm crash stack (context brief) — cần test đỏ trước (TDD đã khoá).
- Circuit breaker: đáng làm nhưng tối thiểu. Đơn tiến trình (`Dockerfile.ai2:26` một uvicorn worker), nên state trong RAM là đủ; nếu sau này nhiều worker, mỗi worker tự có breaker (chấp nhận được). Ngưỡng gợi ý [ASSUMED]: 5 lỗi loại timeout/5xx/429 trong 60s -> Open 30s -> Half-Open 1 probe. Lỗi 401/400 không tính vào breaker nhưng phải bật cảnh báo cấu hình (fail-closed vĩnh viễn tới khi sửa). Tự viết ~40 dòng hơn thêm dependency (pybreaker/tenacity [PRIOR]); khoảng lợi lớn nhất là short-circuit trả lời tất định ngay lập tức thay vì chờ timeout.
- Budget/request: `max_llm_calls` (2: plan + answer), `max_tokens` cho completion, trần `prompt_chars` (client đã đo `last_prompt_chars`), trần chi phí = tokens x bảng giá (`gpt-4o-mini` ~ $0.15/1M input, $0.60/1M output là [PRIOR], BẮT BUỘC xác minh trên trang giá OpenAI trước khi hard-code; đưa vào config, không vào code). Thêm kill-switch toàn cục (env `AI2_LLM_ENABLED=false` hoặc trần chi phí/ngày) vì D-5 nói dữ liệu thật chưa được duyệt.
- `base_url` mặc định là `http://localhost:20128/v1` (`client.py:23`, compose `docker-compose.yml` `AI2_LLM_BASE_URL host.docker.internal:20128`): là proxy "9router", không phải api.openai.com trực tiếp. Nghĩa là latency/lỗi/giá do proxy quyết định; cần xác nhận D-5 dùng route nào (Open Q3).
- Xác thực: mọi số liệu latency của LLM thật chỉ có ở benchmark chạy tay (D-7); probe 1.6 chỉ chứng minh cơ chế client.

## Q4. Observability cho FastAPI + LLM, bộ tối thiểu hữu ích

Bằng chứng:
1. OTel FastAPI instrumentation (FETCHED, https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/fastapi/fastapi.html): `FastAPIInstrumentor.instrument_app(app)`; loại URL bằng `OTEL_PYTHON_FASTAPI_EXCLUDED_URLS`/`excluded_urls=` (dùng để loại `/health`, `/healthz`, `/metrics`); `server_request_hook` để gắn attribute tuỳ biến. Trang không nêu tên metric/span cụ thể.
2. OTel GenAI semantic conventions: trang `opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-metrics/` (FETCHED) chỉ còn thông báo "GenAI semantic conventions have moved to the OpenTelemetry GenAI semantic conventions repository" (https://github.com/open-telemetry/semantic-conventions-genai). Trang repo mở được nhưng không hiển thị nội dung metric. SEARCH (snippet, chưa mở): `gen_ai.client.token.usage` (histogram, tách `gen_ai.token.type` input/output) và `gen_ai.client.operation.duration` (giây, cả thành công và lỗi); namespace `gen_ai.*` vẫn ở trạng thái experimental/development; thu nội dung message qua `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT`. Nguồn thấy trong kết quả tìm kiếm: https://opentelemetry.io/blog/2026/genai-observability/, https://www.dash0.com/knowledge/opentelemetry-genai-semantic-conventions-explained, https://greptime.com/blogs/2026-05-09-opentelemetry-genai-semantic-conventions, https://genkit.dev/docs/observability/otel-genai-semantic-conventions/. Chi phí (cost) KHÔNG thấy trong danh sách metric của các snippet -> [ASSUMED] không có metric chuẩn cho cost; phải tự đặt tên (ví dụ `ai2.llm.cost_usd`), tính từ token x bảng giá.
3. prometheus_client multiprocess docs (FETCHED, https://prometheus.github.io/client_python/multiprocess/): nhiều worker cần `PROMETHEUS_MULTIPROC_DIR`, không hỗ trợ custom collector/`set_function`/Info/Enum/exemplar, gauge cần `multiprocess_mode`; với Gunicorn phải gọi `mark_process_dead`. Repo đang chạy 1 tiến trình uvicorn (`Dockerfile.ai2:26`) nên chưa dính các giới hạn này; ghi lại như ràng buộc nếu tăng worker.
4. OWASP Logging Cheat Sheet (FETCHED, https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html): không log secret, PII nhạy cảm, session id (hash nếu cần theo dõi); kỹ thuật "removed, masked, sanitized, hashed, encrypted"; sanitize CR/LF để chống log injection.
5. Redaction cụ thể (structlog processor, Presidio) và Langfuse: [PRIOR], không mở.

Đánh giá:
- Bộ tối thiểu hữu ích cho team này (không có stack quan sát nào, 1.8), theo thứ tự giá trị/chi phí:
  1. Log JSON có cấu trúc, allow-list field, KHÔNG log nội dung hợp đồng. Field bắt buộc mỗi request: `request_id`, `trace_id`/`traceparent` (nhận từ Backend), `endpoint`, `status`, `latency_ms`, `contract_versions`, `image_version`, `llm_called`, `llm_answer_used`, `llm_error_code`, `model`, `prompt_tokens`, `completion_tokens`, `cost_usd`, `breaker_state`. Redaction theo allow-list (chỉ log key đã đăng ký), không theo deny-list regex; chuỗi tự do (câu hỏi người dùng, text đoạn hợp đồng, tên bên) chỉ ghi dạng độ dài + sha256 rút gọn — đúng pattern đã có ở `client.py:37-44`. Chi phí gần 0, không cần hạ tầng.
  2. Endpoint `GET /metrics` (prometheus_client) với ~6 series: `ai2_http_requests_total{route,status}`, `ai2_http_request_duration_seconds{route}`, `ai2_llm_calls_total{outcome}` (ok/timeout/rate_limited/auth/breaker_open), `ai2_llm_tokens_total{type}`, `ai2_llm_cost_usd_total`, `ai2_llm_breaker_state`. Label chỉ dùng tập hữu hạn (route đã chuẩn hoá, outcome enum); không bao giờ label theo `document_id`/query. Chưa có Prometheus server -> endpoint tồn tại nhưng có thể xem bằng `curl` cho tới khi có stack; đây là điểm tiết kiệm.
  3. Trace OTel: chỉ bật khi có `OTEL_EXPORTER_OTLP_ENDPOINT` (no-op nếu không); `FastAPIInstrumentor.instrument_app` + span thủ công quanh L0-L3 và mỗi lần gọi LLM (đặt attribute theo tên `gen_ai.*` của spec mới nhất kèm cảnh báo experimental; pin phiên bản package). Giá trị lớn nhất là truyền `traceparent` Backend -> AI2 (Backend đã khai dependency OTel, 1.7, nhưng chưa dùng) để nối một lượt hỏi đáp qua hai service. Loại `/health`,`/healthz`,`/metrics` bằng excluded_urls.
- Prometheus vs OTel metrics: chọn Prometheus client cho metrics (nhẹ, một endpoint, không cần collector), OTel chỉ cho trace. Đánh đổi: hai hệ thống thay vì một; chấp nhận vì OTel metrics cần collector/OTLP endpoint mà team chưa có (1.8) và semconv GenAI vẫn experimental. Nếu sau này có collector, có thể đổi sang OTel metrics mà không đổi tên nghiệp vụ.
- Langfuse: đã ở dependency (1.7) nhưng chưa dùng; nó gửi prompt/completion tới một dịch vụ khác -> mâu thuẫn ràng buộc D-5 (chỉ dữ liệu giả lập tới khi provider được duyệt) và cần hạ tầng riêng. Không đưa vào B; ghi nhận là quyết định để sau.
- Chi phí LLM theo lượt (yêu cầu D-4): tính từ `usage` mà client đã thu (`client.py:77-82`); cần cộng dồn qua nhiều lần gọi trong một query, không chỉ lần cuối, và ghi cả khi lỗi sau khi đã tốn token.

---

# Kết luận XẾP HẠNG

Xếp theo rủi ro nếu bỏ qua x chi phí làm:

1. **Deadline chung + fail-closed cho LLM (Phase 2)** — rủi ro cao nhất, đã có bằng chứng chạy được: `timeout` SDK không phải deadline tổng (probe 1.6), `complete_json` gọi hai lần trên mọi lỗi (`client.py:57`), L2 không bắt lỗi provider (`l2_plan.py:158`). Làm trước khi bật bất kỳ cờ egress nào; test đỏ: server giả trả 401/timeout/trickle -> query trả câu tất định < 20s với `llm_answer_used=false`. Breaker tối thiểu đi kèm.
2. **Chính sách tương thích contract + `query_snapshot_digest` (Phase 1)** — phải xác nhận Backend có phải tolerant reader trước khi thêm bất kỳ field nào (schema và pydantic đều strict). Không đổi ngữ nghĩa digest; thêm `query_snapshot_digest` vào result, giữ `snapshot_digest` cũ trong cửa sổ deprecation, sau đó bỏ bản hash trùng ở `worker.py:78-110`.
3. **Ba trục version + `GET /version` (Phase 1/3)** — một nguồn sự thật (git tag `ai2-vX.Y.Z` -> build-arg -> `/version`), bỏ hard-code `main.py:67`, Backend fail-fast theo `contracts.supported`.
4. **Đóng gói GHCR (Phase 3)** — workflow riêng `ai2-release.yml` theo tag `ai2-v*`, `packages: write` + attestations, `provenance: mode=max`, `sbom: true`, `latest=false`, chỉ `linux/amd64`, `.dockerignore` loại sqlite, Backend pin `tag@digest`. Độ chắc cao (3 nguồn chính thức nhất quán), rủi ro thấp.
5. **Observability tối thiểu (Phase 4)** — (a) log JSON allow-list + request/trace id, (b) `/metrics` Prometheus ~6 series gồm token/cost/breaker, (c) OTel trace bật theo env, chủ yếu để nối `traceparent` với Backend. Không thêm collector/Prometheus/Grafana vào B trừ khi team quyết định (D-4 cho phép nhưng không bắt).

Khuyến nghị bakeoff (đo được, load-bearing): ngưỡng deadline LLM (12s?) và số lần gọi LLM/query nên chốt bằng số đo từ benchmark A + chạy tay D-7, không bằng lập luận; escalate sang `hs:bakeoff` cho tham số này.

# Rủi ro chấp nhận / giới hạn của nghiên cứu

- Chưa gọi OpenAI/9router thật: mọi số về latency/giá LLM là [ASSUMED]/[PRIOR].
- GenAI semconv chỉ tới mức SEARCH-snippet (spec đã chuyển repo, trang metric không hiển thị nội dung khi fetch); tên metric có thể đổi vì còn experimental.
- Tính mutable của tag GHCR chưa được tài liệu GitHub xác nhận trong phiên này.
- Chưa đọc code Backend phần parse response `/query` và result AI2 để biết strict/tolerant.
- SemVer.org không được mở (giữ [PRIOR]).
- Probe 1.6 chạy trên máy dev Windows, không đại diện mạng container; phần dư ~1s ở case "im lặng" chưa giải thích.

# Open questions

1. Backend parse result/`/query` response bằng model `extra=forbid` hay `ignore`? (quyết định thứ tự release Backend/AI2 khi thêm field). Cần đọc code Backend và chạy contract test có field lạ.
2. Digest có nên chứa `attempt_id` (`ai1_snapshot_adapter.py:111`)? Retry cùng nội dung hiện làm mọi query bị stale; product/Architecture Lead phải chốt.
3. D-5 dùng `api.openai.com` trực tiếp hay proxy 9router (`client.py:23`)? Ảnh hưởng timeout, giá, và chính sách egress.
4. Gate `threshold_verdict = PASS` (D-6) thực thi ở đâu cho release image: GitHub `environment` có reviewer, hay artifact verdict kiểm trong workflow?
5. Có dev dùng Apple Silicon (cần `arm64`) không? Host chạy Backend là gì (cần cách `docker login ghcr.io` hay để package public)?
6. Vì sao probe "im lặng" mất 3.0s khi `timeout=2.0` (SDK 3.14.0 + httpx 0.28.1)? Cần đo thêm trước khi đặt số ngân sách theo giây.
7. Trong `ai-service/data/` (ngoài `ai2/`), thư mục/tệp nào thật sự cần cho runtime để `COPY data/ data/` (`Dockerfile.ai2:22`) chỉ copy phần cần?
8. Còn bao nhiêu chỗ Backend hard-code `egress_allowed False` ngoài 2 chỗ trong brief (đã thấy thêm `webhooks.py:186`, `ai_adapters.py:446`, `schemas/queries.py:17`)? Phase 2 cần grep đầy đủ và test cho từng đường.
9. Bảng giá `gpt-4o-mini` và tên chính xác model-id qua proxy: cần xác minh trước khi đưa vào config cost.
