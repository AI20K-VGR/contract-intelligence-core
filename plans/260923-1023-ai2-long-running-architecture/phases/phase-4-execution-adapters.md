# P4 — Execution boundary, current pipeline và ADK/A2A adapters

Mục tiêu: chạy pipeline hiện tại dưới canonical run; ADK là adapter optional; A2A deferred nếu chưa có agent boundary.

TDD:

- Tests before: pipeline success/failure/timeout, adapter mismatch, duplicate callback, no-citation tool, tenant propagation, cancel fence.
- Implement: typed adapter boundary và error/retry mapping.
- Tests after: parity với current pipeline và adapter contract.

Acceptance: adapter không sở hữu canonical state; không thêm A2A vào AI1→AI2 khi chưa được duyệt; artifact `artifacts/p4-adapter-contract.json`.

Rollback: disable adapter, dùng current worker.
