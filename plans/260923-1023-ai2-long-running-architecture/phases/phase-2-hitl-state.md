# P2 — Reasoning state machine và HITL commands

Mục tiêu: durable-domain transition và command model cho context, approve, reject, edit, impact confirm, resume, cancel.

TDD:

- Tests before: transition matrix, incomplete context, stale/expired command, duplicate retry, concurrent actors, unauthorized actor, timeout/cancel race.
- Implement: reducer và command validation với state version/CAS/idempotency.
- Tests after: deterministic reducer, authz và audit fields.

Acceptance: không auto-approve; một race chỉ một winner; artifact `artifacts/p2-state-transition-matrix.json`.

Rollback: feature flag facade về synchronous path, không bypass gate.
