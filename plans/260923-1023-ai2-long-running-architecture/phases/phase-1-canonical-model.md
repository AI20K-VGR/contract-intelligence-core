# P1 — Canonical domain model, segmentation và evidence graph

Mục tiêu: model hóa run, snapshot, logical document, boundary, fact, relation, citation, generation và dependency/stale.

TDD:

- Tests before: body/annex trong một JSON, boundary ambiguous, low confidence, table continuation, bilingual, citation mismatch.
- Implement: canonical mapping và dependency graph; raw AI1 immutable.
- Tests after: schema/evidence/stale propagation suite.

Acceptance: thiếu evidence trả safe state; cross-document conclusion cần confirmation; artifact `artifacts/p1-domain-schema.json`.

Rollback: compatibility projection chỉ đọc, legacy output không đổi.
