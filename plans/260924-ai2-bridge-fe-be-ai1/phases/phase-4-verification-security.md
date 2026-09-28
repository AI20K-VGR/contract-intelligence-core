# P4 — Security, failure, observability và Backend E2E

## Mục tiêu

Chứng minh đường Backend↔AI2 không làm mất tenant boundary, evidence integrity, idempotency hoặc khả năng recovery.

## Module/file dự kiến

- Backend authz/service envelope/configuration.
- AI2 endpoint contract tests.
- Backend integration/E2E test suites.
- Structured logging/metrics/tracing fields.
- Security and failure runbook.

## Contract

- Log có correlation/task/run ID nhưng không log raw contract text/secrets ngoài policy.
- Mọi service call có tenant, service identity, timestamp và outcome.
- Retry chỉ áp dụng cho operation an toàn; submit cần idempotency.
- Citation/result không được coi là verified nếu digest/provenance invalid.

## Acceptance criteria

- Cross-tenant read/write tests đều fail closed.
- Secret không xuất hiện trong log/artifact.
- AI2/BE restart, disconnect, duplicate, out-of-order và partial result có test evidence.
- Metrics tối thiểu: submit latency, poll latency, terminal status, retry count, evidence rejection, mapping failure.
- Backend E2E chạy được với flag off và flag on.
- Không có file FE bị sửa.

## Test cases

- user/tenant/service unauthorized.
- bad signature, replay và stale envelope.
- prompt-injection-like text trong evidence không được biến thành command.
- downstream unavailable.
- retry sau side effect.
- server restart giữa submit và poll.
- duplicate/out-of-order result.
- large dossier/multiple annex trong configured limits.

## Verification artifact

Security test report, failure-mode matrix, trace sample đã redact, Backend E2E report và timeout baseline.

## Risk / rollback

Risk là test chỉ chứng minh happy path hoặc log làm lộ dữ liệu. Rollback: giữ canonical flag off; revoke/rotate integration credentials nếu phát hiện leak.

## Dependency

P2 lifecycle và P3 persistence mapping.

