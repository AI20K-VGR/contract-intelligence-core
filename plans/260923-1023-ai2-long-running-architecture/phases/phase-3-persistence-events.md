# P3 — Durable persistence, events, outbox và replay

Mục tiêu: state tồn tại qua reconnect/restart/crash; event ordering, dedup, gap, snapshot fallback và audit.

TDD:

- Tests before: monotonic sequence, duplicate/out-of-order/gap, commit-publish failure, retry timeout, digest mismatch, worker crash/lease fence.
- Implement: snapshot/event/audit/outbox/replay store.
- Tests after: replay convergence và recovery integration.

Acceptance: không mất event/pending checkpoint, không lặp side effect; artifact `artifacts/p3-replay-convergence.json`.

Rollback: giữ legacy job path, new log read-only nếu migration chưa an toàn.
