# P5 — API, authorization, security và observability

Mục tiêu: snapshot, replay/stream source và command API có tenant/role authorization, audit, redaction và tracing.

TDD:

- Tests before: cross-tenant, role matrix, replay scope, idempotent command, redaction, prompt injection, tool allow/deny, correlation.
- Implement: API/error catalog, authz/audit/telemetry boundary.
- Tests after: security and observability suite.

Acceptance: deny-by-default; không log raw contract/hidden reasoning; artifact `artifacts/p5-api-security-contract.json`.

Rollback: internal-only/feature flag, không mở public endpoint.
