# Contract Backend ↔ AI2: Processing v1

**Trạng thái:** Canonical processing contract v1  
**Phạm vi:** Backend gửi toàn bộ dossier cho AI2 xử lý; AI2 trả kết quả async để Backend lưu và quyết định publish.  
**Transport:** đã chốt chuyển sang Kafka, event driven (2026-09-30) — xem [DOC-05e](../DOC-05e-kafka-ai2-idp-contract.md). **Hiện runtime vẫn là HTTP** `POST /jobs/idp` + poll; Kafka thành runtime khi DOC-05e §12 bước 3 đạt. Sau đó HTTP chỉ còn cho demo/manual và làm fallback khi `AI2_TRANSPORT=http`.

> **v1.2:** §6 là các quy tắc đã chốt theo [DEC-BE-AI2-01](DEC-BE-AI2-01-contract-decisions.vi.md). Backend chốt D1–D12; Lead duyệt D8, D11 (phương án A) và D12 ngày 30/09, D6 duyệt ngày 30/09; chờ AI2 (Văn Dũng) xác nhận. Chỗ nào §6 khác các mục trên thì theo §6.

## 1. Phạm vi và ownership

Contract này là wire contract giữa Backend và AI2, không thay thế `ai1.snapshot.v1`. AI1 vẫn sở hữu OCR/layout evidence; Backend sở hữu việc chọn snapshot, grouping dossier, policy và retry; AI2 sở hữu extraction/reasoning proposal.

Phase này chỉ chốt processing và processing result. Query/query-result, re-OCR, semantic validation ngược sang AI1 và production service authentication để phase sau.

Schema authority:

- [Backend → AI2 request schema](be.ai2.processing.request.v1.schema.json)
- [AI2 → Backend result schema](ai2.be.processing.result.v1.schema.json)
- [Contract registry](../../packages/contracts/schemas/registry.json)

## 2. Backend → AI2: processing request

Kênh runtime đích: event `ai2.idp.command` trên topic `ci.ai2.idp.commands`; request này là `payload` của envelope `ci.kafka.v1` (hoặc nằm trên MinIO qua `payload_ref` khi lớn hơn ngưỡng inline, DOC-05e §6). Endpoint demo `POST /jobs/idp` nhận đúng body này. Backend gửi `snapshots[]` đầy đủ của dossier, không chỉ body. Đây là điều kiện để AI2 so sánh body–annex và tạo finding liên tài liệu.

`service_envelope` là field bắt buộc của request canonical. Envelope có `payload_sha256`, nonce, thời hạn, scope và chữ ký HMAC; AI2 phải xác thực envelope trước khi nhận request hoặc chạy worker. Trên Kafka, AI2 kiểm tra chữ ký, `payload_sha256`, audience/tenant/dossier nhưng **không** kiểm tra `expires_at`/`nonce`, vì command có thể nằm trong topic hoặc được redeliver sau 300 giây; chống replay bằng dedupe `(idempotency_key, attempt)` (DOC-05e §4, §7). `idempotency_key` được ghép với `attempt` để chống submit trùng và payload conflict.

```json
{
  "schema_version": "be.ai2.processing.request.v1",
  "request_id": "run-001:ai2",
  "idempotency_key": "run-001:ai2",
  "attempt": 1,
  "task_id": "process-dossier",
  "dossier_id": "dossier-001",
  "snapshots": ["<ai1.snapshot.v1 body>", "<ai1.snapshot.v1 annex>"],
  "snapshot_identities": [
    {
      "snapshot_id": "snap-body-001",
      "snapshot_version": "ai1.snapshot.v1",
      "source_digest": "<64 hex>",
      "snapshot_digest": "<64 hex>"
    }
  ],
  "dossier_members": [
    {
      "member_id": "member-body-001",
      "document_id": "doc-body-001",
      "snapshot_id": "snap-body-001",
      "role": "body",
      "source_digest": "<64 hex>",
      "document_number": "HD-001/2026"
    }
  ],
  "role_relation_map": [
    {
      "relation_id": "rel-annex-001",
      "relation_type": "ANNEX_OF",
      "member_id": "member-annex-001",
      "related_member_id": "member-body-001",
      "dossier_id": "dossier-001"
    }
  ],
  "policy_flags": {
    "egress_allowed": false,
    "use_vector": true,
    "budget_limits": {
      "max_processing_seconds": 300,
      "max_llm_calls": 20,
      "max_embedding_tokens": 50000
    }
  },
  "service_envelope": {
    "schema_version": "ai2.service-envelope.v1",
    "issuer": "backend-service",
    "audience": "vsf-ai2",
    "tenant_id": "tenant-001",
    "actor_id": "backend",
    "dossier_id": "dossier-001",
    "scopes": ["ai2.jobs.submit"],
    "key_id": "default",
    "issued_at": 1790740800,
    "expires_at": 1790741100,
    "nonce": "3f9c2b7e8a1d4c56b0e2f7a9c1d3e5f7",
    "payload_sha256": "<64 hex: SHA-256 của request đã bỏ service_envelope>",
    "signature": "<64 hex: HMAC-SHA256 của envelope đã bỏ signature>"
  }
}
```

Ví dụ trên là **hiện trạng** request Backend đang gửi (ví dụ `use_vector: true`). Luật đã chốt nằm ở §6: luồng xử lý `use_vector=false`, tối đa 6 file một hồ sơ, nhiều `body` chỉ theo D12.

`request_id` và `idempotency_key` cố định theo run (`<run_id>:ai2`); `attempt` là trường riêng, tăng khi Backend retry. Cách chuẩn hoá JSON trước khi hash và ký: `sort_keys`, `separators=(",", ":")`, `ensure_ascii=False`, UTF-8.

`dossier_members[]` là danh sách membership có role rõ ràng. `role_relation_map[]` là quan hệ cấu trúc do Backend xác định; AI2 không tự suy ra hay sửa quan hệ này. `ANNEX_OF` bắt buộc có `related_member_id`; `MEMBER_OF` không có target.

Backend phải gửi đúng một member `body`, mọi member phải trỏ tới một snapshot trong `snapshots[]`, và các `source_digest` phải khớp với snapshot tương ứng. Adapter hiện tại kiểm tra các ràng buộc cross-field này ngoài JSON Schema.

`dossier_members[].document_number` (tuỳ chọn, chuỗi 1–160 ký tự, `null` được) là số hiệu văn bản đã xác nhận ở manifest. Backend chỉ thêm trường khi có giá trị; trường không nằm trong `required`, không đổi `source_digest` hay snapshot. AI2 dùng nó để biết một điều khoản tham chiếu văn bản nào khác, nên consumer phải chấp nhận trường này trước khi Backend gửi (schema `be.ai2.processing.request.v1`).

`policy_flags.egress_allowed` mang **consent theo hồ sơ** (`metadata.ai2_content_sharing_consent`, xem D6 ngày 15/10), không phải quyết định egress cuối cùng. Egress thực tế của một lần xử lý là `AI2_PROCESSING_EGRESS_ALLOWED` (env của AI2) **và** `policy_flags.egress_allowed`; thiếu một trong hai thì AI2 chạy fail-closed đối với external LLM, vẫn `SUCCEEDED` với phần xử lý bằng luật cố định. AI2 không được mở rộng egress, vector hoặc budget vượt giá trị Backend gửi. Consent chỉ coi là bật khi giá trị lưu đúng là boolean `true`; thiếu hoặc sai kiểu là `false`.

## 3. Async lifecycle và retry

Trên Kafka (runtime):

1. Backend publish `ai2.idp.command` cho mỗi cặp `(run, attempt)`.
2. AI2 publish `ai2.idp.started` khi bắt đầu chạy pipeline.
3. AI2 publish đúng một kết quả cuối: `ai2.idp.completed` (`status=SUCCEEDED`) hoặc `ai2.idp.failed` (`status=FAILED`), payload là `ai2.be.processing.result.v1`.

Backend không poll. Timeout do watchdog của Backend quyết định: thời gian chờ trong hàng đợi và thời gian chạy (`max_processing_seconds` + grace) được tính riêng (DOC-05e §8). Hết hạn thì run `FAILED` với `AI2_TIMEOUT`.

Trên HTTP (demo/fallback): `POST /jobs/idp` trả job envelope với `202 Accepted`; Backend poll `GET /jobs/{job_id}`.

Hàng đợi (cả hai kênh): AI2 chạy tối đa `AI2_MAX_CONCURRENT_JOBS` job cùng lúc (mặc định 1). Job đã nhận mà chưa tới lượt ở `QUEUED`; `max_processing_seconds` chỉ bắt đầu tính khi job rời hàng đợi. Backend không tính thời gian `QUEUED` vào hạn xử lý: trên HTTP, hạn poll được đặt lại mỗi lần thấy `QUEUED`, và thời gian chờ có trần riêng `AI2_MAX_QUEUE_WAIT_SECONDS` (mặc định 1800 s, quá thì `AI2_TIMEOUT`). Backend gửi cùng lúc không quá số job AI2 chạy (`WORKER_AI2_MAX_CONCURRENCY` lấy cùng giá trị), nên phần dư chờ ở Backend, nơi không có hạn.

Public job status ở cả hai kênh là:

`QUEUED → RUNNING → SUCCEEDED | FAILED`

**Tiến độ trong bước (đã chốt 18/10/2026 trong [PR #125](https://github.com/AI20K-VGR/contract-intelligence-core/pull/125), thực hiện #116; Backend nhận từ PR #117).** Khi job `RUNNING`, response `GET /jobs/{job_id}` có thể thêm trường tuỳ chọn:

```json
"progress": { "step": "S6", "done": 12, "total": 40, "unit": "clause" }
```

- `step`: bước AI2 đang chạy, một trong `S4`, `S5`, `S6`, `S7`, `S9`, `S10` (nhãn trên giao diện: S4 nhận diện, S5 kiểm tra chất lượng, S6 dựng cấu trúc, S7 trích xuất dữ kiện, S9 so sánh tìm mâu thuẫn, S10 xếp hàng rà soát).
- `done`, `total`: số nguyên, `total >= 1`; `unit`: `chunk`, `clause`, `pair`, `page` hoặc `document`.
- Backend đánh dấu các bước AI2 trước `step` là `succeeded`, `step` là `running`, rồi hiện `done/total` trên giao diện (DOC-05b v3.2.0). Job lỗi thì bước đang `running` thành `failed`.
- Chỉ mang tính tham khảo: thiếu trường hoặc giá trị sai thì Backend bỏ qua, không làm hỏng run. Backend tự giới hạn số lần ghi, AI2 không cần.
- Backend chỉ nhận tiến độ cho run mà job đang trỏ tới (`current_run_id`), khi run còn `running` và đúng tenant; tiến độ sau khi huỷ hoặc của run cũ bị bỏ qua.
- Không có trường này thì giao diện chỉ hiện vòng quay cho các bước AI2, như trước.

`review_state` là trạng thái chất lượng/review độc lập: `PASS`, `NEEDS_REVIEW`, `INSUFFICIENT_EVIDENCE`, `BLOCKED` hoặc `null` khi job chưa hoàn tất.

`idempotency_key` = `<run_id>:ai2`, cố định trong một run. Retry của Backend tạo `attempt + 1` và command mới; cùng `(idempotency_key, attempt)` thì AI2 không chạy lại mà trả lại kết quả đã lưu (cùng `job_id`). Cùng cặp nhưng `payload_sha256` khác → `AI2_IDEMPOTENCY_CONFLICT`. Kết quả của attempt cũ đến muộn bị Backend bỏ qua và ghi audit.

Lỗi luôn có `errors[].retryable`. Lỗi tạm (429/529, timeout provider) AI2 tự thử lại có giới hạn, sau đó trả `FAILED` với `retryable=true`; Backend chỉ mở retry cho run khi `retryable=true` hoặc khi chính Backend timeout. Bảng mã lỗi ở DOC-05e §5.3.

Backend là nơi lưu request, job state và result. Kho dedupe của AI2 phải bền qua restart (PostgreSQL theo DOC-11 §3); in-memory chỉ dùng khi chạy local.

## 4. AI2 → Backend: processing result

Result luôn giữ `input_snapshots[]` để Backend kiểm tra result đang nói về đúng snapshot identities. Khi thành công:

- `facts[]` có `citation_ids[]`;
- `findings[]` có disposition/review state rõ ràng và citation IDs ở hai phía;
- mọi citation ID trong facts/findings/evidence issues phải resolve được trong `result.citations[]`;
- AI2 không tạo bbox mới; geometry chỉ được chuyển tiếp từ evidence hiện có;
- citation có thể có `table_id`/`cell_id` (optional, additive). Khi có, resolver đối chiếu chính xác ô nguồn cùng page revision, text, bbox và hash. Không tạo line/span giả cho ô không có line mapping; đánh giá citation theo assignment vẫn phải báo thiếu mapping này;
- `index_contribution.state` luôn là `propose`, không phải publish.

Khi thất bại, `result` là `null` và `errors[]` phải có `code`, `message`, `retryable`. Backend không được coi proposal là authoritative chỉ vì job `SUCCEEDED`; review/publish là trách nhiệm Backend.

## 5. Compatibility và Definition of Done

`ai2.idp.request.v1` vẫn được giữ trong code để chạy fixture/adapter tương thích, nhưng contract canonical của API processing là `be.ai2.processing.request.v1` và `ai2.be.processing.result.v1`.

### 5.1 Compatibility boundary

| Shape/version | Vai trò | Quy tắc |
|---|---|---|
| `be.ai2.processing.request.v1` + `ai1.snapshot.v1` | Canonical Backend → AI2 | Được validate ở wire boundary; đây là đường duy nhất cho `POST /jobs/idp`. |
| `ai2.be.processing.result.v1` | Canonical AI2 → Backend | Result phải giữ snapshot identities, citation references và `index_contribution.state=propose`. |
| `ai1.snapshot.v3` | Legacy/backend adapter | Chỉ được nhận tại `backend/src/contract_intelligence/shared/ai/ai1_adapter.py` để phục vụ persistence tương thích; không được nâng ngầm thành input canonical của AI2. |
| `ai2.extraction.v2` / `ai2.comparison.v2` | Legacy endpoint/DTO | Không phải result của processing canonical; không dùng làm đường thay thế cho `/jobs/idp`. |
| `ai2.idp.request.v1` | Compatibility adapter/fixture lane | Được chuyển vào canonical adapter hiện có, nhưng không thay thế transport contract `be.ai2.processing.request.v1`. |

Không tự động đổi version giữa các lane. Mọi migration từ `ai1.snapshot.v3` hoặc legacy result v2 sang canonical phải có contract decision riêng và test parity trước khi mở rộng phạm vi.

### 5.2 Fixture inventory và blocker

- Fixture canonical đã có: `examples/ai1.snapshot.v1.body.example.json`, `examples/ai1.snapshot.v1.annex.example.json` và các JSON Schema v1 trong thư mục này.
- Contract tests của AI2 dùng fixture sanitized trong `docs/contracts/examples`; không dùng PDF bytes hoặc output runtime làm fixture canonical.
- Full-suite inventory hiện vẫn có test/import ngoài P1 tham chiếu module hỗ trợ không có trong checkout (ví dụ `scripts.validate_input_coverage`) và dependency môi trường thiếu (`langfuse`). Đây là blocker kiểm thử hiện hữu, không được xử lý bằng cách nới contract hoặc sửa fixture ngoài ownership P1.

Đạt phase khi:

1. Hai schema mới có trong registry và được kiểm tra tự động.
2. Request full dossier được adapter vào pipeline mà không sửa snapshot gốc.
3. Command Kafka (và POST/polling ở kênh demo) có idempotency theo attempt.
4. Result tách public wire shape khỏi internal `JobResult`/`IndexContribution`.
5. Có test cho membership, body/annex relation, citation resolution và async lifecycle.

## 6. Quy tắc đã chốt (v1.2)

Lý do và bằng chứng của từng mục nằm trong DEC-BE-AI2-01. Mã `Dn` trỏ tới mục tương ứng trong DEC. Lead đã duyệt D8, D11 (phương án A) và D12 ngày 30/09; D6 duyệt ngày 30/09.

### 6.1 Kết nối và bảo mật

- **Kênh gọi (D1).** Sprint 2: chỉ HTTP, `POST /jobs/idp` trả `202`, sau đó Backend poll `GET /jobs/{job_id}`. Sprint 3: chuyển sang Kafka theo DOC-05e v2 (PR #36) khi DOC-05e §12 đạt; HTTP còn làm fallback. `POST /query` là lời gọi đồng bộ ở cả hai sprint.
- **Envelope (D2).**
  - `issuer=backend-service`, `audience=vsf-ai2`, `key_id=default`; Backend đặt thời hạn 300 giây. AI2 cho lệch đồng hồ 30 giây và từ chối envelope có thời hạn quá 3600 giây.
  - Scope: `ai2.jobs.submit` cho submit và poll, `ai2.query` cho hỏi đáp.
  - Payload đem đi hash: bỏ trường `service_envelope`, chuẩn hoá JSON với `sort_keys`, `separators=(",", ":")`, `ensure_ascii=False`, mã hoá UTF-8. Chữ ký là HMAC-SHA256 trên envelope đã bỏ `signature`.
  - Mỗi môi trường dùng một secret riêng, đặt giống nhau cho `backend`, `backend-worker` và `ai2-service`. Thiếu secret thì cả hai phía đều từ chối (fail-closed).
  - `/query` bắt buộc có chữ ký: `AI2_QUERY_REQUIRE_SIGNATURE`, mặc định `true`, thiếu envelope thì `401 SERVICE_ENVELOPE_MISSING`. Chỉ compose local hoặc test cần nhánh cũ mới đặt `false`.
- **Mạng (D3).** Bản online không publish cổng 8002. Healthcheck gọi `/healthz`, endpoint không gọi LLM.

### 6.2 Request

- **Snapshot và digest (D4).**
  - Chỉ gửi `ai1.snapshot.v1`.
  - `source_digest` và `snapshot_digest` là 64 ký tự hex chữ thường, không có tiền tố. AI2 nhận `sha256:<hex>` để tương thích nhưng chuẩn hoá ngay khi nhận.
- **Hồ sơ nhiều file (D5).**
  - Gửi đủ mọi snapshot của hồ sơ. Sprint 2: đúng một member `body`; có 0 hoặc nhiều hơn một body thì Backend không gửi. Sprint 3: được nhiều `body` theo D12 (so hợp đồng–hợp đồng), bật qua `policy_flags.max_body_members`. AI2 nhận trường này trước; Backend chỉ gửi sau đó, vì `policy_flags` phía AI2 cấm trường lạ.
  - Tối đa 6 file một hồ sơ (`snapshots` từ 1 đến 6). Hồ sơ hơn 6 tài liệu thì Backend không gửi và trả `422 DOSSIER_TOO_MANY_DOCUMENTS`. Giới hạn đếm tài liệu (file tải lên, phần sau khi tách), không đếm trang.
  - Phụ lục không có `ANNEX_OF` vẫn được gửi với `role=annex`; finding liên tài liệu khi đó ghi là "quan hệ chưa xác nhận".
  - AI2 không suy luận, không sửa role hay quan hệ.
- **`policy_flags` (D6, Lead duyệt 30/09).**
  - Cờ egress, vector và LLM là cấu hình của `ai2-service`, đọc từ env `AI2_PROCESSING_EGRESS_ALLOWED`, `AI2_QUERY_EGRESS_ALLOWED`, `AI2_QUERY_USE_LLM`, `AI2_QUERY_USE_VECTOR`, `AI2_VECTOR_RECALL_ENABLED`. Mặc định ban đầu `false`; **từ 15/10 bản online đặt `true`** (Lead, review PR #85). Env của AI2 là điều kiện cần; consent theo hồ sơ là điều kiện đủ (dòng dưới). Backend không gửi `use_llm`.
  - **Consent theo hồ sơ (15/10).** Backend lưu `ai2_content_sharing_consent` trên hồ sơ và gửi: ở xử lý qua `policy_flags.egress_allowed`; ở `/query` qua trường `content_sharing_consent` của request. Egress, LLM và vector của `/query` chỉ bật khi env AI2 bật **và** request mang `content_sharing_consent=true` **và** snapshot đã lưu consent `true`, trong một request có `service_envelope` hợp lệ. Hồ sơ mới nhận mặc định của server `AI2_CONTENT_SHARING_CONSENT_DEFAULT` (`true` trên bản online). Chỉ chủ hồ sơ hoặc `ADMINISTRATOR` đổi được qua `PATCH /dossiers/{id}/ai2-content-sharing-consent` (DOC-05b). Consent đổi thì có hiệu lực từ request kế tiếp (`effective_from: next_request`), không sửa lại kết quả đã xử lý. Riêng **bật** consent khi lượt chạy cuối đã qua AI2, backend tự gửi `dossier.ai2.reindex` (cùng đường `POST /dossiers/{id}/ai2/reindex`, `ai2_attempt` tăng 1) sau khi đã commit consent, nên AI2 nhận một request mới với `policy_flags.egress_allowed=true` (DOC-05b v3.1.0).
  - Thứ tự: AI2 đổi `egress_allowed` và `use_vector` trong `policy_flags` thành tuỳ chọn (A8). `use_vector` trong request không quyết định vector (công tắc là `AI2_VECTOR_RECALL_ENABLED`). `egress_allowed` không còn bị bỏ qua: nó là consent theo hồ sơ như trên, nên Backend **tiếp tục gửi** trường này (B3 chỉ áp dụng cho `use_vector`). `max_processing_seconds` và `budget_limits` vẫn do Backend gửi.
  - Khi `egress_allowed=false`, AI2 vẫn trả `SUCCEEDED` với phần xử lý bằng luật cố định.
  - Vượt `max_llm_calls` thì AI2 trả `SUCCEEDED` với `review_state=NEEDS_REVIEW` kèm issue `LLM_BUDGET_EXCEEDED`, không trả `FAILED` (D6, Lead duyệt 02/10).
  - Luồng xử lý hồ sơ: `use_vector=false`.
  - Bản online (Lead, 30/09; đổi 15/10): OpenAI gọi thẳng `https://api.openai.com/v1`, **`gpt-5.5`** cho xử lý hồ sơ, `/query`, bước suy luận khó và ghép cặp đồ thị, embedding `text-embedding-3-small`; tối đa 20 lần gọi LLM và 100.000 token embedding một hồ sơ, hard limit **30 USD/tháng** (Lead xác nhận 15/10), không cảnh báo chủ động, hết trần thì tắt env. Cả nhóm được tải hồ sơ lên bản online, chỉ hợp đồng mẫu đã ẩn thông tin, không gửi hồ sơ thật.
  - Công tắc thật của vector là `AI2_VECTOR_RECALL_ENABLED`; vector trên `/query` dựa vào egress của chính `/query`; trần embedding do AI2 đọc từ env của mình, Backend không gửi.

### 6.3 Vòng đời job

- **Idempotency và retry (D7).**
  - `idempotency_key` bằng `<run_id>:ai2`.
  - Gửi lại vì mất phản hồi mạng: giữ nguyên key và `attempt`, nhận lại cùng `job_id`.
  - Retry sau `FAILED` có `retryable=true`: giữ key, `attempt` tăng 1, tối đa 3 attempt cho một run.
  - Bộ snapshot thay đổi: mở run mới, key mới.
  - Cùng `(key, attempt)` mà payload khác: AI2 trả `409`, Backend không retry.
  - Payload tất định: cùng `(key, attempt)` thì payload (bỏ `service_envelope`) giống hệt từng byte, kể cả khi dựng lại. `created_at` của snapshot lấy từ lúc lưu, không lấy giờ hiện tại.
  - Job được retry khi và chỉ khi `status=FAILED` và có ít nhất một lỗi `retryable=true`. `retryable` theo mã lỗi (lỗi tạm: `true`; lỗi contract, dữ liệu sai: `false`), không theo `review_state`. Hồ sơ `SUCCEEDED` + `BLOCKED` không retry.
- **Ánh xạ trạng thái (D8, Lead duyệt 30/09).**
  - `SUCCEEDED` với `PASS`, `NEEDS_REVIEW` hoặc `INSUFFICIENT_EVIDENCE`: hồ sơ chuyển sang `pending_review`, nhãn UI "Chờ rà soát".
  - `SUCCEEDED` + `BLOCKED`, hoặc `FAILED` đã hết lượt retry: hồ sơ chuyển sang `failed`.
  - Khi `status=SUCCEEDED` và `review_state=BLOCKED`, `errors[0]` là issue gây chặn. Backend lấy mã lỗi của run `failed` từ `errors[0].code`, không có thì dùng `AI2_BLOCKED`.
  - Khi `status` khác `SUCCEEDED`, Backend bỏ qua `review_state` (giá trị này không có nghĩa khi job không `SUCCEEDED`) và chỉ đọc `status` và `errors[]`.
  - `evidence_ready` chỉ cho biết đủ bằng chứng để publish; nó không quyết định hồ sơ có vào hàng chờ review hay không.

### 6.4 Kết quả

- **Kiểm tra và lưu (D9).**
  - `input_snapshots[]` phải khớp các snapshot đã gửi, và mọi `citation_id` phải có trong `citations[]`. Sai một điều thì Backend không lưu phần nào của result.
  - Kết quả là bản đề xuất (`propose`); chỉ publish sau khi reviewer duyệt.
  - AI2 không tạo bbox mới.
  - Citation `UNVERIFIED` vẫn được lưu nhưng gắn cờ.
  - `table_id` và `cell_id` được lưu nếu có.
  - Finding liên tài liệu thiếu citation một phía thì bị hạ xuống `NEEDS_REVIEW`.
- **Hỏi đáp `ai2.query.v1` (D10).**
  - AI2 trả `query_snapshot_digest` (64 hex) trong result xử lý hồ sơ, dùng chung cho HTTP và Kafka. Backend lưu nguyên giá trị đó và gửi lại trong `/query`. Backend không tự tính digest, và không dùng `dossier.checksum` thay thế. Chuyển tiếp: result chưa có trường này thì Backend tạm tính như cũ, và xoá phần tự tính sau khi AI2 deploy.
  - Hồ sơ chưa có digest thì Backend không gọi AI2.
  - `acl_context` là `user_id` của người hỏi, chỉ dùng cho audit.
  - `state` nhận một trong bốn giá trị `ANSWERED`, `NEEDS_REVIEW`, `INSUFFICIENT_EVIDENCE`, `BLOCKED`. `BLOCKED` là bị khoá hoặc bị chính sách chặn, không phải lỗi hệ thống.
  - Backend chờ 30 giây. AI2 giới hạn LLM trong `/query` ở 15 giây; quá thì trả kết quả truy xuất kèm citation, `NEEDS_REVIEW` (D6).

### 6.5 Lưu trữ (D11)

- Lead chọn **phương án A** ngày 30/09; ADR-14 được chấp nhận.
- Dữ liệu nghiệp vụ nằm ở Postgres của Backend, và chỉ Backend ghi.
- Trạng thái riêng của AI2 nằm ở schema `ai2` trong cùng cụm Postgres, qua `AI2_DATABASE_URL` và user `ai2_app` (chỉ có quyền trên schema `ai2`). Migration của schema này do AI2 tự quản.
- Job store, query store và durable run store của AI2 nằm ở schema `ai2` ngay từ lần deploy online đầu tiên. Vector cũng nằm trong schema `ai2` bằng pgvector (Lead, 30/09), bật trên bản online theo D6. Postgres dùng image `pgvector/pgvector:pg16`, script khởi tạo chạy `CREATE EXTENSION vector`.
- AI2 mất dữ liệu thì Backend dựng lại bằng cách gửi lại `/jobs/idp` với `attempt` mới.
- Không cần volume cho `AI2_JOB_DB` và `vectors.sqlite` khi AI2 đã chạy trên Postgres.

## 7. Xoá nội dung hồ sơ — issue #131

**Trạng thái: đã chốt với Backend (Chương) ngày 19/10/2026 tại
[review PR #132](https://github.com/AI20K-VGR/contract-intelligence-core/pull/132#pullrequestreview-5566790702),
ghi nhận tại bổ sung #131 trong DEC-BE-AI2-01.**

Phần AI2 triển khai trên PostgreSQL + pgvector (ADR-14), không có chế độ purge SQLite.
`DossierDeletionService` của Backend purge nội dung DB trước, rồi gọi API này;
chỉ đánh dấu `purge_status=completed` khi cả hai thành công. HTTP client dùng canonical `ai2_base_url` và bộ
ký envelope hiện có. Response chưa completed hoặc thiếu evidence hợp lệ làm purge
thất bại; background task commit trạng thái failed khi transaction còn hợp lệ để
`sweep_pending_purges()` thử lại. Evidence tích luỹ được lưu ở `deletion_ledger.evidence.ai2`.
Sweeper xử lý cả ledger completed thiếu khoá `ai2`: chỉ gọi AI2 và bổ sung evidence,
giữ số đếm Backend cũ; nếu lỗi thì failed và retry mà không dọn lại Backend.
Giữ nguyên `purge_completed_at`/`purged_at` đã có của Backend, cả khi dọn bù AI2
thất bại rồi thử lại; không thay mốc purge gốc bằng thời điểm backfill.

**Endpoint:** `DELETE /api/v1/dossiers/{dossier_id}`; JSON body bắt buộc:

```json
{
  "tenant_id": "tenant-001",
  "dossier_id": "dossier-001",
  "service_envelope": {"...": "ai2.service-envelope.v1"}
}
```

Envelope dùng issuer/audience/key/HMAC và TTL như endpoint canonical hiện có,
với scope **`ai2.dossier.delete`**. Hash payload bỏ `service_envelope`, theo D2.
`dossier_id` trên URL, body và envelope phải trùng; `tenant_id` trong body phải trùng
envelope. Tenant từ chữ ký quyết định phạm vi xoá; header tenant đơn lẻ không đủ quyền.
Không thêm cơ chế service-token mới ngoài xác thực canonical hiện tại.

Ví dụ tạo body bằng helper AI2 (Backend dùng bộ ký tương đương của mình):

```python
payload = {"tenant_id": tenant_id, "dossier_id": dossier_id}
payload["service_envelope"] = build_service_envelope(
    payload, secret=secret, tenant_id=tenant_id, dossier_id=dossier_id,
    scopes=["ai2.dossier.delete"],
)
```

**Response `200`:** chỉ trả khi xoá DB và cleanup file đều hoàn tất.

```json
{
  "status": "completed",
  "deleted": {"jobs": 3, "dossier_query_snapshots": 1, "vector_segments": 812},
  "evidence": {
    "deleted": {"jobs": 3, "dossier_query_snapshots": 1, "vector_segments": 812},
    "blob_directories": 0
  }
}
```

Ví dụ rút gọn; thực tế `deleted` có số dòng cho mọi bảng được purge. `deleted` là số
xoá ở lần gọi này; `evidence.deleted` là tổng tích luỹ qua các lần retry. Backend lưu
`evidence` vào deletion ledger. Gọi lặp hoặc scope chưa tồn tại vẫn thành công, thường
trả số xoá mới bằng 0. Envelope còn hạn có thể được gửi lại cho cùng thao tác xoá;
retry sau hết hạn phải ký envelope mới. Thao tác này không phục hồi hồ sơ.

| HTTP | Code | Xử lý |
|---|---|---|
| 401 | `SERVICE_*` từ verifier | Sửa chữ ký, scope hoặc thời hạn |
| 403 | `SERVICE_TENANT_MISMATCH` | Sửa tenant binding |
| 422 | `SERVICE_DOSSIER_MISMATCH` | Sửa URL/body binding |
| 503 | `AI2_PURGE_INCOMPLETE`, `retryable=true` | Chưa được đánh dấu completed; retry |

Xoá nhầm tenant không xoá dữ liệu của tenant khác và không tiết lộ sự tồn tại của nó:
scope không có dữ liệu vẫn trả thành công. Không trả nội dung hợp đồng/path/SQL trong lỗi.

**Dữ liệu và đồng thời:**

- Xoá jobs, query snapshots, session/blobs, graph edges/pair relations, graph receipts,
  processing trace và durable runs/checkpoints/events/outbox/audit thuộc scope.
- `dossier_resource_refs` lưu lịch sử ownership/digest không chứa nội dung. Migration
  backfill từ trường JSON có cấu trúc; không nối bằng substring hoặc đoán ID. Durable
  child có thể bổ sung owner của run; dữ liệu mâu thuẫn owner làm migration/write thất bại.
- Vector dùng `record.pins.source_snapshot_digest`; digest của durable state không
  đồng nghĩa với vector digest. Chỉ xoá segment khi mọi owner của digest đã tombstone,
  xét trên tất cả tenant và cả digest lịch sử. Writer vector từ query luôn bind owner.
- Tombstone `(tenant_id,dossier_id)` tồn tại lâu dài, kể cả scope chưa từng có dữ liệu.
  Job mới, message tới muộn và write muộn bị chặn ở DB. Job hiện tại mất lease/row;
  worker dừng hợp tác ở checkpoint và không thể commit kết quả trở lại.
- Các transaction ghi ngắn dùng `pg_advisory_xact_lock_shared(131,2)`, purge dùng
  `pg_advisory_xact_lock(131,2)` độc quyền; các writer khác resource chạy song song.
  Đăng ký owner dùng khoá riêng theo loại và ID resource để giữ owner bất biến;
  không giữ khoá trong lời gọi LLM/embedding. Khoá statement chạy trước khoá row;
  store nào SELECT FOR UPDATE phải lấy khoá purge trước. Đây là thứ tự khoá bắt buộc.
- Durable outbox kiểm tra lại claim trước publish và giữ erasure gate đến khi
  callback publish đồng bộ kết thúc. Purge đợi publication đang chạy; payload đã
  claim nhưng bị purge trước publication không được phát. Callback phải có timeout
  và không gọi lại AI2 persistence trong cùng lời gọi để tránh chờ khoá của chính nó.
- Audit vẫn append-only với run còn sống; chỉ cho DELETE toàn bộ audit của run có
  owner đã tombstone để không giữ lại `details_json` có thể chứa nội dung.
- File blobs legacy được xoá sau commit bằng session ID đã đăng ký, giới hạn trong
  `AI2_DATA_DIR/blobs`. Nếu lỗi/crash, tombstone vẫn chặn truy cập và trạng thái pending
  được sweeper AI2 tiếp tục; Backend cũng phải retry để lấy evidence completed.
- Giữ `service_nonces` chống replay và hai bảng metadata tombstone/resource refs;
  không giữ request/result/snapshot/text/blob trong các bảng này.
- `/query` cho scope đã xoá trả `410 AI2_DOSSIER_DELETED`; `/jobs/{job_id}` của job
  đã purge không còn tồn tại. Session cache cũ không được đọc lại nội dung đã xoá.

**Triển khai:** chạy migration `0009_dossier_purge` trước khi sử dụng endpoint. Không
downgrade bỏ fencing sau khi đã có tombstone; migration từ chối thao tác đó. Kiểm thử
chấp nhận dùng PostgreSQL thật, gồm pgvector. Luồng Backend → AI2 đã kiểm chứng local
với HTTP thật, hai file/OCR, retry và restart AI2; E2E này chỉ chạy local, không chạy CI.
Backend gọi purge ngay sau deploy, không có cờ enable; AI2 chưa có endpoint thì
purge failed và sweeper thử lại. Deploy AI2 cùng migration/readers/writers trước Backend,
không chạy worker cũ sau khi xoá. Sweeper tự dọn scope completed thiếu evidence AI2
(7 hồ sơ theo audit #131 ngày 18/10); kiểm đếm DB/files sau rollout trước khi đóng issue.
