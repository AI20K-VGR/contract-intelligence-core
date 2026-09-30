# Contract Backend ↔ AI2: Processing v1

**Trạng thái:** Canonical processing contract v1  
**Phạm vi:** Backend gửi toàn bộ dossier cho AI2 xử lý; AI2 trả kết quả async để Backend lưu và quyết định publish.  
**Transport:** đã chốt chuyển sang Kafka, event driven (2026-09-30) — xem [DOC-05e](../DOC-05e-kafka-ai2-idp-contract.md). **Hiện runtime vẫn là HTTP** `POST /jobs/idp` + poll; Kafka thành runtime khi DOC-05e §12 bước 3 đạt. Sau đó HTTP chỉ còn cho demo/manual và làm fallback khi `AI2_TRANSPORT=http`.

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

`request_id` và `idempotency_key` cố định theo run (`<run_id>:ai2`); `attempt` là trường riêng, tăng khi Backend retry. Cách chuẩn hoá JSON trước khi hash và ký: `sort_keys`, `separators=(",", ":")`, `ensure_ascii=False`, UTF-8.

`dossier_members[]` là danh sách membership có role rõ ràng. `role_relation_map[]` là quan hệ cấu trúc do Backend xác định; AI2 không tự suy ra hay sửa quan hệ này. `ANNEX_OF` bắt buộc có `related_member_id`; `MEMBER_OF` không có target.

Backend phải gửi đúng một member `body`, mọi member phải trỏ tới một snapshot trong `snapshots[]`, và các `source_digest` phải khớp với snapshot tương ứng. Adapter hiện tại kiểm tra các ràng buộc cross-field này ngoài JSON Schema.

`policy_flags` là authoritative từ Backend. AI2 không được mở rộng quyền egress, vector hoặc budget. `egress_allowed=false` phải chạy fail-closed đối với external LLM.

## 3. Async lifecycle và retry

Trên Kafka (runtime):

1. Backend publish `ai2.idp.command` cho mỗi cặp `(run, attempt)`.
2. AI2 publish `ai2.idp.started` khi bắt đầu chạy pipeline.
3. AI2 publish đúng một kết quả cuối: `ai2.idp.completed` (`status=SUCCEEDED`) hoặc `ai2.idp.failed` (`status=FAILED`), payload là `ai2.be.processing.result.v1`.

Backend không poll. Timeout do watchdog của Backend quyết định: thời gian chờ trong hàng đợi và thời gian chạy (`max_processing_seconds` + grace) được tính riêng (DOC-05e §8). Hết hạn thì run `FAILED` với `AI2_TIMEOUT`.

Trên HTTP (demo/fallback): `POST /jobs/idp` trả job envelope với `202 Accepted`; Backend poll `GET /jobs/{job_id}`.

Public job status ở cả hai kênh là:

`QUEUED → RUNNING → SUCCEEDED | FAILED`

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
