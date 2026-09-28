# Code review — active cook plan — round 2

Plan: `260925-0238-ai1-ai2-be-fe-review-fixes-260925-0238`
Reviewer: `agent:independent-code-reviewer`
Phạm vi: chỉ re-review các sửa đổi ACL approval và worker retry/idempotency, cùng hồi quy Critical/Important trực tiếp.

## Verdict: PASS_WITH_RISK

Không còn finding Critical/Important trong phạm vi round 2:

- `backend/src/contract_intelligence/review/interfaces/api/routers/approval_router.py:50-53,94-97,121-124` đã wire `require_lock_access`/`require_external_approval_access` vào lock/create/list; approve tiếp tục có `require_approval_access` tại `:70-71`.
- `backend/src/contract_intelligence/review/interfaces/api/dependencies_approval.py:64-116` bind dossier ACL với tenant, role và owner/share metadata; create dùng `APPROVE`, list dùng `QUERY` theo role.
- `backend/src/contract_intelligence/worker.py:513-527,591-603` chỉ đánh dấu `_submitted_ai2_runs` sau commit thành công và release guard khi exception, nên retry transient không còn bị chặn bởi in-memory guard.

## Verification đã chạy

`uv run --project backend python -m pytest backend/tests/unit/test_route_registration_authz.py backend/tests/unit/test_approval_router.py backend/tests/unit/test_worker_pipeline_run.py -q --basetemp tmp/round2-review`

Kết quả: `15 passed, 1 warning in 2.44s`. Warning duy nhất là `PytestCacheWarning` do không ghi được `backend/.pytest_cache`; không có test failure.

## Risk còn lại

- Diff vẫn thuộc high-risk auth/API. Security scan PASS chưa được chạy trong round này; vì vậy không tuyên bố hard-gate `PASS`. `PASS_WITH_RISK` chỉ ghi nhận targeted review xanh, không cấp phép ship.
- Authenticated E2E vẫn `NOT_RUN`: verification trước đó chỉ ghi `SKIP`, không có Keycloak token/stack evidence và không được suy diễn thành PASS.
- Không chạy full suite theo yêu cầu.
