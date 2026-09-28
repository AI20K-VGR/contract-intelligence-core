# Verification artifact refresh — AI2 long-running architecture

Ngày: `2026-09-24`

Sau các vòng hardening R1–R6, các verification artifact P5/P6/P9 đã được cập nhật để khớp với source/test hiện tại.

## Kết quả độc lập

| Phạm vi | Kết quả |
|---|---:|
| P5 focused | `29 passed, 1 warning` |
| P6 focused | `17 passed, 1 warning` |
| P9 focused | `48 passed, 1 warning` |
| P0–P9 targeted | `148 passed, 1 warning` |
| P7 evaluation gate | `5 passed` |
| Full `ai-service` | `373 passed, 6 deselected, 2 warnings` |

Warning còn lại là Windows ACL trên `.pytest_cache` và deprecation warning từ Starlette; không có assertion failure.

## Artifact đã refresh

- `artifacts/p5-api-security-contract.json`: P5 `29 passed`, ApprovalGrant scoped/finite/one-time; idempotency có actor.
- `artifacts/p6-event-ui-convergence.json`: P6 `17 passed`, regression `148 passed`, SSE binding ghi rõ principal/tenant/run/resource.
- `artifacts/p9-production-readiness.json`: P9 `48 passed`, regression `148 passed`.

Các artifact là evidence của test/configuration boundary; không được hiểu là HTTP/SSE production route, shared durable approval ledger, HA, live recovery hoặc business accuracy đã được triển khai.

Không commit/push.
