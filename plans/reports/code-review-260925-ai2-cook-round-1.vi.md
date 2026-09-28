# Code review — active cook plan — round 1

Plan: `260925-0238-ai1-ai2-be-fe-review-fixes-260925-0238`
Reviewer: `agent:independent-code-reviewer`
Scope: product/test diff thuộc active plan; không review harness/cache ngoài scope.

## Verdict: BLOCKED

### Critical

- `backend/src/contract_intelligence/review/interfaces/api/routers/approval_router.py:47-53` — route `lock_dossier` chỉ có RBAC, không phụ thuộc `require_approval_access`; cùng lỗi ở `:89-105` (`create_external_approval`) và `:114-121` (`list_external_approvals`). Vì vậy principal cùng tenant có role phù hợp nhưng không owner/share dossier vẫn có thể lock, tạo hoặc đọc external approval. Điều này phá vỡ ACL dossier dùng chung và mutation fail-closed.
  - Fix: gắn dependency ACL approval vào toàn bộ route theo dossier; bổ sung test anonymous, cross-tenant và same-tenant-not-shared cho từng route.

### Important

- `backend/src/contract_intelligence/worker.py:464-465,513,601-628` — `_submitted_ai2_runs` được đánh dấu trước submit/poll và không bị xoá khi exception. Một lỗi transient sau `submit_ai2_processing` khiến lần xử lý/reconcile tiếp theo thoát sớm, không retry dù durable run đã bị ghi `failed`; recovery/idempotency không đạt mục tiêu bounded retry.
  - Fix: chỉ ghi receipt durable sau submit thành công, hoặc release in-memory guard trên failure; phân biệt retryable failure với terminal failure và test crash/retry trong cùng process lẫn sau restart.

## Gate evidence đã đọc

- Cook artifact `plans/260925-0238-ai1-ai2-be-fe-review-fixes-260925-0238/artifacts/verification-phase-6-integrated-verification.json`: các offline/backend/frontend checks ghi `PASS`, frontend format ghi `SKIP`, authenticated E2E ghi `SKIP`.
- `plans/.../artifacts/verification.json` ghi verdict `PASS_WITH_RISK`, không phải review approval; authenticated E2E vẫn `SKIP`.
- `git diff --check`: đã chạy và không báo lỗi whitespace mới trong output đã đọc.
- Architecture review: đã đọc `docs/system-architecture.md`; artifact review ghi `architecture_review.checked=true`.
- Security ceremony: scope preflight xác định `high_risk`; không chạy thêm security scan theo yêu cầu dừng, nên không coi security scan là PASS.

## E2E status

`authenticated E2E: NOT_RUN` — evidence hiện có chỉ là `SKIP`; không có Keycloak token/stack evidence, không suy diễn thành PASS.

## Unresolved

Hai finding trên cần sửa và re-review. `PASS_WITH_RISK` không đủ để clear hard gate; round này phải BLOCKED.
