# Contract Backend ↔ AI2: Processing v1

**Trạng thái:** Canonical processing contract v1  
**Phạm vi:** Backend gửi toàn bộ dossier cho AI2 xử lý; AI2 trả kết quả async để Backend lưu và quyết định publish.

> **v1.2:** §6 là các quy tắc đã chốt theo [DEC-BE-AI2-01](DEC-BE-AI2-01-contract-decisions.vi.md). Backend chốt D1–D12; Lead duyệt D8, D11 (phương án A) và D12 ngày 30/09, **D6 chưa duyệt**; chờ AI2 (Văn Dũng) xác nhận. Chỗ nào §6 khác các mục trên thì theo §6.

## 1. Phạm vi và ownership

Contract này là wire contract giữa Backend và AI2, không thay thế `ai1.snapshot.v1`. AI1 vẫn sở hữu OCR/layout evidence; Backend sở hữu việc chọn snapshot, grouping dossier, policy và retry; AI2 sở hữu extraction/reasoning proposal.

Phase này chỉ chốt processing và processing result. Query/query-result, re-OCR, semantic validation ngược sang AI1 và production service authentication để phase sau.

Schema authority:

- [Backend → AI2 request schema](be.ai2.processing.request.v1.schema.json)
- [AI2 → Backend result schema](ai2.be.processing.result.v1.schema.json)
- [Contract registry](../../packages/contracts/schemas/registry.json)

## 2. Backend → AI2: processing request

Endpoint demo: `POST /jobs/idp`. Backend gửi `snapshots[]` đầy đủ của dossier, không chỉ body. Đây là điều kiện để AI2 so sánh body–annex và tạo finding liên tài liệu.

`service_envelope` là field bắt buộc của request canonical. Envelope có `payload_sha256`, nonce, thời hạn, scope và chữ ký HMAC; AI2 phải xác thực envelope trước khi nhận request hoặc chạy worker. `idempotency_key` được ghép với `attempt` để chống submit trùng và payload conflict.

```json
{
  "schema_version": "be.ai2.processing.request.v1",
  "request_id": "req-001",
  "idempotency_key": "dossier-001:attempt-1",
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
      "source_digest": "<64 hex>"
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
  }
}
```

Ví dụ trên là **hiện trạng** request Backend đang gửi (ví dụ `use_vector: true`). Luật đã chốt nằm ở §6: luồng xử lý `use_vector=false`, tối đa 6 file một hồ sơ, nhiều `body` chỉ theo D12.

`dossier_members[]` là danh sách membership có role rõ ràng. `role_relation_map[]` là quan hệ cấu trúc do Backend xác định; AI2 không tự suy ra hay sửa quan hệ này. `ANNEX_OF` bắt buộc có `related_member_id`; `MEMBER_OF` không có target.

Backend phải gửi đúng một member `body`, mọi member phải trỏ tới một snapshot trong `snapshots[]`, và các `source_digest` phải khớp với snapshot tương ứng. Adapter hiện tại kiểm tra các ràng buộc cross-field này ngoài JSON Schema.

`policy_flags` là authoritative từ Backend. AI2 không được mở rộng quyền egress, vector hoặc budget. `egress_allowed=false` phải chạy fail-closed đối với external LLM.

## 3. Async lifecycle và retry

`POST /jobs/idp` trả job envelope với `202 Accepted`; Backend poll `GET /jobs/{job_id}`. Public job status là:

`QUEUED → RUNNING → SUCCEEDED | FAILED`

`review_state` là trạng thái chất lượng/review độc lập: `PASS`, `NEEDS_REVIEW`, `INSUFFICIENT_EVIDENCE`, `BLOCKED` hoặc `null` khi job chưa hoàn tất.

Retry tạo `attempt` mới và nên giữ `request_id`/`idempotency_key` theo policy của Backend. Cùng `(idempotency_key, attempt)` trả lại cùng `job_id`; không tạo duplicate job trong cùng attempt.

Backend là nơi lưu request, job state và result. AI2 chỉ cần lưu state đủ cho worker/polling trong phase demo; production sẽ thay background task bằng durable queue.

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
3. POST/polling có idempotency theo attempt.
4. Result tách public wire shape khỏi internal `JobResult`/`IndexContribution`.
5. Có test cho membership, body/annex relation, citation resolution và async lifecycle.

## 6. Quy tắc đã chốt (v1.2)

Lý do và bằng chứng của từng mục nằm trong DEC-BE-AI2-01. Mã `Dn` trỏ tới mục tương ứng trong DEC. Lead đã duyệt D8, D11 (phương án A) và D12 ngày 30/09. **D6 chưa duyệt**: quy tắc bật egress và vector trên bản online bên dưới chỉ áp dụng khi Lead ghi provider và trần chi tiêu.

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
  - Tối đa 6 file một hồ sơ (`snapshots` từ 1 đến 6). Hồ sơ hơn 6 tài liệu thì Backend không gửi và trả `422 DOSSIER_TOO_MANY_DOCUMENTS` ("Hồ sơ tối đa 6 tài liệu").
  - Phụ lục không có `ANNEX_OF` vẫn được gửi với `role=annex`; finding liên tài liệu khi đó ghi là "quan hệ chưa xác nhận".
  - AI2 không suy luận, không sửa role hay quan hệ.
- **`policy_flags` (D6, Lead chưa duyệt).**
  - Egress của từng luồng do biến env quyết định (`AI2_PROCESSING_EGRESS_ALLOWED`, `AI2_QUERY_EGRESS_ALLOWED`), mặc định `false`.
  - Khi `egress_allowed=false`, AI2 vẫn trả `SUCCEEDED` với phần xử lý bằng luật cố định.
  - Vượt `max_llm_calls` thì AI2 trả `INSUFFICIENT_EVIDENCE` kèm lý do, không trả `FAILED`.
  - Luồng xử lý hồ sơ: `use_vector=false`.
  - Bản online **chưa bật egress và vector**: `AI2_QUERY_EGRESS_ALLOWED`, `AI2_QUERY_USE_VECTOR`, `AI2_VECTOR_RECALL_ENABLED` giữ `false` cho tới khi Lead duyệt D6. Khi bật: công tắc thật là `AI2_VECTOR_RECALL_ENABLED`; vector trên `/query` dựa vào egress của chính `/query`; trần embedding do AI2 đọc từ env của mình, Backend không gửi.

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
  - Timeout 20 giây.

### 6.5 Lưu trữ (D11)

- Lead chọn **phương án A** ngày 30/09; ADR-14 được chấp nhận.
- Dữ liệu nghiệp vụ nằm ở Postgres của Backend, và chỉ Backend ghi.
- Trạng thái riêng của AI2 nằm ở schema `ai2` trong cùng cụm Postgres, qua `AI2_DATABASE_URL` và user `ai2_app` (chỉ có quyền trên schema `ai2`). Migration của schema này do AI2 tự quản.
- Job store, query store và durable run store của AI2 nằm ở schema `ai2` ngay từ lần deploy online đầu tiên. Vector chưa bật trên bản online (D6); `vectors.sqlite` là cache, volume cho nó vẫn giữ. Chuyển vector sang pgvector quyết cùng D6.
- AI2 mất dữ liệu thì Backend dựng lại bằng cách gửi lại `/jobs/idp` với `attempt` mới.
- Không cần volume cho `AI2_JOB_DB` khi AI2 đã chạy trên Postgres.
