# Code review vòng 2 — AI1/AI2/Backend/Frontend (focused)

Ngày review: 2026-09-25  
Phạm vi: chỉ `dependencies_approval.py`, `approval_router.py`, `worker.py` và regression tests ACL/route/approval/worker. Không chạy full suite, không sửa product code.

## Verdict

**PASS_WITH_RISK** — không còn Critical blocker của vòng 1 trong phạm vi đã kiểm tra; còn một regression Important về phân biệt quyền đọc external approval của administrator.

## Đã xác minh blocker vòng 1

- `backend/src/contract_intelligence/review/interfaces/api/routers/approval_router.py:49-54,92-98,118-125` đã gắn lần lượt `require_lock_access` và `require_external_approval_access` vào lock/create/list. `backend/tests/unit/test_route_registration_authz.py:101-113` kiểm tra ba route đều có dossier-level ACL dependency.
- `backend/src/contract_intelligence/review/interfaces/api/dependencies_approval.py:39-112` đọc dossier theo `dossier_id`, kiểm tra tenant/role/owner-share qua `dossier_access_decision`, và fail closed bằng `403` khi ACL không cho phép.
- `backend/src/contract_intelligence/worker.py:601-603` giải phóng `_submitted_ai2_runs` trong nhánh exception trước khi ghi trạng thái failed. `backend/tests/unit/test_worker_pipeline_run.py:131-183` xác minh transient failure không giữ guard và lần gọi sau vẫn thử submit lại (`submit.await_count == 2`).

## Finding Important còn lại

### I1 — GET external approvals của administrator bị kiểm tra nhầm bằng quyền APPROVE

Evidence: `backend/src/contract_intelligence/review/interfaces/api/dependencies_approval.py:89-108` dùng chung cho cả hai route tại `backend/src/contract_intelligence/review/interfaces/api/routers/approval_router.py:92-98,118-125`, nhưng chọn `AclAction.APPROVE` chỉ dựa trên `user.role == "ADMINISTRATOR"`. Vì vậy administrator được share dossier với grant chỉ có `actions: ["query"]` sẽ bị từ chối khi gọi `GET /dossiers/{id}/external-approvals`, dù route contract cho phép administrator tra cứu danh sách (`docs/DOC-05b-frontend-backend-api-contract.md:350-356`) và `dossier_access_decision` cố ý hỗ trợ action restriction (`backend/src/contract_intelligence/shared/acl.py:72-78`).

Fix đề xuất: tách dependency cho read và create, hoặc truyền action theo route; `GET` luôn dùng `AclAction.QUERY`, còn `POST` dùng `AclAction.APPROVE`. Bổ sung regression test cho administrator shared với query-only grant.

Đây là denial-of-valid-access, không phải privilege escalation; do đó phân loại Important, không phải Critical.

## Verification

Đã chạy đúng targeted regression, không chạy full suite:

```text
uv run pytest tests/unit/test_approval_router.py tests/unit/test_route_registration_authz.py tests/unit/test_dossier_acl_consistency.py tests/unit/test_worker_pipeline_run.py -q --basetemp ..\\tmp\\review-r2-focused-uv
25 passed, 1 warning in 2.29s
```

Authenticated E2E: **NOT_RUN** theo phạm vi/điều kiện hiện tại; không dùng trạng thái này làm failure và không suy diễn thành PASS.

Không thực hiện thay đổi product code.
