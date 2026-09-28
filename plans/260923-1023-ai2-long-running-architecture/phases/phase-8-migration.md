# P8 — Migration, canary và cutover

Mục tiêu: chuyển từ `/extract` và `/jobs/idp` sang canonical run facade, giữ AI1 contract và legacy rollback.

TDD:

- Tests before: old/new parity, one/multi-document, legacy session/durable run, flags, deploy/rollback mid-run, duplicate submit.
- Implement: feature flags, dual-read/compare, persistence migration.
- Tests after: canary parity và rollback drill.

Acceptance: non-stale verified generation mới được publish; artifact `artifacts/p8-migration-parity.json`.

Rollback: traffic/feature flags về legacy, giữ append-only records.
