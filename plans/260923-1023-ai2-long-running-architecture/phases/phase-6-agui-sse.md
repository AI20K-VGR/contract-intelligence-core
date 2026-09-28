# P6 — AG-UI boundary, fixed UI và HTTP command + SSE

Mục tiêu: map canonical events sang AG-UI; FE fixed allowlist; SSE chỉ notification/replay, HTTP là command.

TDD:

- Tests before: SSE auth/heartbeat/disconnect, replay/gap, duplicate/order, stale tab command, AG-UI mapping, A2UI catalog mismatch.
- Implement: SDK/reducer/API adapter; A2UI disabled by default.
- Tests after: state convergence và transport operations.

Acceptance: reconnect cùng state hash; disconnect không mất checkpoint; artifact `artifacts/p6-event-ui-convergence.json`.

Rollback: snapshot/polling; WebSocket chỉ sau benchmark.
