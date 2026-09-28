# P7 — Evaluation, regression, recovery và load gates

Mục tiêu: mở rộng eval hiện có cho domain output và workflow/recovery, không thay deterministic gate bằng LLM judge.

TDD:

- Tests before: golden/contract/replay/security/load cases và ground-truth provenance checks.
- Implement: scorer/runner/corpus/CI additions sau adjudication.
- Tests after: full regression, crash/restart, race, reconnect và soak.

Acceptance: metrics có denominator; không claim business accuracy thiếu ground truth; artifact `artifacts/p7-evaluation-gate.json`.

Rollback: evaluation advisory-only, không bật publish gate mới.
