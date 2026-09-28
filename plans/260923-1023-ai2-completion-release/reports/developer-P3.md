# Báo cáo developer — P3 Processing Runtime

## Implementation

- Bổ sung runtime budget theo request cho thời gian, số lần gọi LLM, embedding token, retry và egress deny-by-default.
- Bổ sung fingerprint/idempotency conflict, tenant–dossier–attempt scope và lease/terminal update an toàn trong SQLite job store.
- Giữ raw snapshot tách khỏi review overlay; review bị stale khi processing basis thay đổi và không được publish authoritative.
- Giới hạn vector theo snapshot/model/dimension, kiểm tra lại citation và dừng trước provider khi vượt embedding budget.
- Chặn `run_code` khỏi AI2 gateway và L2 tool plan; không triển khai process isolation, đúng phạm vi phase.

## TDD evidence

- Intentional RED: runtime có `2 failed, 1 passed`; job-store test ban đầu lỗi `ImportError: JobPayloadConflict`.
- Targeted P3 mở rộng: `39 passed, 1 warning`.
- P3 gate đúng phase: `38 passed, 1 warning`.
- Full offline gate: `222 passed, 6 deselected, 1 warning`.
- Contract registry: `Contract registry OK (5 schemas)`.
- `git diff --check`: PASS.
- Kiểm tra UTF-8/U+FFFD trên 17 file: PASS, `U+FFFD=0`.

## Main review

- Chạy lại độc lập đúng P3 gate và full offline suite với `--basetemp` trong workspace.
- Xác nhận provider không được gọi khi egress bị từ chối hoặc budget embedding đã chạm trần.
- Xác nhận idempotency payload khác nhau bị từ chối, lease chỉ cập nhật đúng tenant/dossier/worker token, và `run_code` bị chặn.
- Xác nhận review stale chặn publish và vector không dùng sai snapshot/model/dimension.
- Warning còn lại là Starlette deprecation; 6 live tests được loại khỏi offline gate theo marker.

## Bổ sung sau review P3

- RED có chủ đích: integration test API vector path lỗi với `TypeError: _reason_output() got an unexpected keyword argument 'runtime'`.
- GREEN: `test_api_vector_path_honors_request_embedding_budget_before_provider` đạt `1 passed, 1 warning`; embedding provider có `0` calls khi `max_embedding_tokens` bị vượt.
- Sửa `_vector_service` và `_reason_output` để nhận `ProcessingRuntime` tùy chọn; runtime tạo `VectorRecallService` riêng cho request, dùng `EMBEDDING_CLIENT` hiện tại và giữ tương thích với caller không truyền runtime.
- Exact P3 gate: `40 passed, 1 warning`.
- Full offline: `223 passed, 6 deselected, 1 warning`.

## Security follow-up sau review P3

- RED có chủ đích: hai regression test mới cùng fail (`2 failed, 1 warning`): persist còn mặc định `egress_approved=True`; L2 chưa có boundary/taint instruction cho source text.
- GREEN: chạy đúng hai test mới đạt `2 passed, 1 warning`.
- `record_from_dict` nay fail-closed với `egress_approved=False` khi payload cũ thiếu field; đã thêm regression test.
- L2 đặt source từ `get_node` trong `<retrieved_contract_text>...</retrieved_contract_text>`, thêm instruction rằng đây là untrusted data, không phải instruction và phải bỏ qua mọi chỉ dẫn bên trong; payload vẫn bounded ở `PROMPT_CHAR_CAP=24000`, citation contract không đổi.
- `run_code` đã bị deny bởi `ToolGateway.ALLOWLIST`; không sửa lại path này.
- Exact P3 gate: `42 passed, 1 warning`.
- Full offline: `225 passed, 6 deselected, 1 warning`.
- Contract registry: `Contract registry OK (5 schemas)`.
- `git diff --check`: PASS.
- Byte-level UTF-8 scan trên 6 file follow-up: PASS, `U+FFFD=0`.

## Files

- Thay đổi nằm trong API/runtime, contract model, table/index/vector, gateway/job store/persist và test P3 liên quan; không sửa `plan.md`/phase file và không commit.
