# Contract Backend ↔ AI2: Processing v1

**Trạng thái:** Canonical processing contract v1  
**Phạm vi:** Backend gửi toàn bộ dossier cho AI2 xử lý; AI2 trả kết quả async để Backend lưu và quyết định publish.

## 1. Phạm vi và ownership

Contract này là wire contract giữa Backend và AI2, không thay thế `ai1.snapshot.v1`. AI1 vẫn sở hữu OCR/layout evidence; Backend sở hữu việc chọn snapshot, grouping dossier, policy và retry; AI2 sở hữu extraction/reasoning proposal.

Phase này chỉ chốt processing và processing result. Query/query-result, re-OCR, semantic validation ngược sang AI1 và production service authentication để phase sau.

Schema authority:

- [Backend → AI2 request schema](be.ai2.processing.request.v1.schema.json)
- [AI2 → Backend result schema](ai2.be.processing.result.v1.schema.json)
- [Contract registry](../../packages/contracts/schemas/registry.json)

## 2. Backend → AI2: processing request

Endpoint demo: `POST /jobs/idp`. Backend gửi `snapshots[]` đầy đủ của dossier, không chỉ body. Đây là điều kiện để AI2 so sánh body–annex và tạo finding liên tài liệu.

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

`dossier_members[]` là danh sách membership có role rõ ràng. `role_relation_map[]` là quan hệ cấu trúc do Backend xác định; AI2 không tự suy ra hay sửa quan hệ này. `ANNEX_OF` bắt buộc có `related_member_id`; `MEMBER_OF` không có target.

Backend phải gửi đúng một member `body`, mọi member phải trỏ tới một snapshot trong `snapshots[]`, và các `source_digest` phải khớp với snapshot tương ứng. Adapter hiện tại kiểm tra các ràng buộc cross-field này ngoài JSON Schema.

`policy_flags` là authoritative từ Backend. AI2 không được mở rộng quyền egress, vector hoặc budget. `egress_allowed=false` phải chạy fail-closed đối với external LLM.

## 3. Async lifecycle và retry

**Runtime production (DOC-05e):** Backend publish `ai2.idp.command` lên Kafka `ci.ai2.idp.commands` với payload = request này; AI2 worker xử lý và publish `ai2.idp.completed` / `ai2.idp.failed` lên `ci.ai2.idp.results`. HTTP không phải path runtime.

**Demo HTTP:** `POST /jobs/idp` trả job envelope với `202 Accepted`; client/lab poll `GET /jobs/{job_id}`. Public job status là:

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

Đạt phase khi:

1. Hai schema mới có trong registry và được kiểm tra tự động.
2. Request full dossier được adapter vào pipeline mà không sửa snapshot gốc.
3. POST/polling có idempotency theo attempt.
4. Result tách public wire shape khỏi internal `JobResult`/`IndexContribution`.
5. Có test cho membership, body/annex relation, citation resolution và async lifecycle.
