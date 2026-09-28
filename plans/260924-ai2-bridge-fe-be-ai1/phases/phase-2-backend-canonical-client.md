# P2 — Backend canonical client và orchestration có feature flag

## Mục tiêu

Thêm đường gọi AI2 canonical vào BE mà không phá `AiServiceClient`/pipeline legacy.

## Module/file dự kiến

- `backend/src/contract_intelligence/shared/ai/`:
  - canonical client interface/implementation;
  - service-envelope signer/validator;
  - submit/status/cancel mapping;
  - retry/idempotency policy.
- `pipeline_orchestrator.py`: thêm branch có flag sau AI1 snapshot, giữ branch cũ nguyên vẹn.
- settings/env example/docker compose: thêm config additive.
- run step persistence: lưu AI2 task/correlation/reference.
- Test fake AI2 server và client contract.

## Contract

- Submit `POST /jobs/idp` trả `202` và `job_id`.
- Poll `GET /jobs/{job_id}` kèm signed poll envelope.
- `tenant_id`, `dossier_id`, `correlation_id`, `idempotency_key` không được đổi giữa retry.
- Timeout không đồng nghĩa task thất bại; trạng thái phải phân biệt `RUNNING`, `WAITING`, `SUCCEEDED`, `FAILED`, `CANCELLED`.

## Acceptance criteria

- Flag off không thay đổi request/response legacy.
- Flag on gọi canonical endpoint với request P1 và nhận result đúng schema.
- Retry cùng idempotency key không tạo duplicate.
- Signature sai, tenant sai, job không thuộc dossier và schema sai đều bị chặn.
- Server restart của BE không làm mất reference đã persist trước đó.

## Test cases

- submit/poll thành công.
- AI2 trả `NEEDS_REVIEW`, `INSUFFICIENT_EVIDENCE`, `BLOCKED`.
- 401/403, timeout, 5xx, malformed result.
- poll duplicate/out-of-order response.
- retry sau network disconnect.
- cancel trước submit, đang chạy và sau completion.
- hai request cùng idempotency key.

## Verification artifact

Canonical client integration report với fake AI2 server, request envelope capture đã redacted và state-transition trace.

## Risk / rollback

Risk là trộn task canonical với job legacy hoặc ký envelope sai. Rollback: tắt flag và giữ endpoint legacy; không xóa bảng/reference canonical đã ghi.

## Dependency

P1 adapter; service key/tenant signing contract phải được BE và AI2 xác nhận.

