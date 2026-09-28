# P9 — Production hardening và release gate

Mục tiêu: verify SLO, capacity, retention, security, recovery runbook và operational ownership.

TDD:

- Tests before: chaos restart, queue duplicate/outage, stream saturation, retention gap, incident audit, security regression.
- Implement: runbook/dashboard/alert/config theo topology đã duyệt.
- Tests after: RTO/RPO/recovery and readiness gate.

Acceptance: không còn critical auth/data-loss/duplicate-side-effect finding; artifact `artifacts/p9-production-readiness.json`.

Rollback: canary/feature flag, giữ legacy path.
