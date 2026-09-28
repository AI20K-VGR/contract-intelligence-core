# P0 — Freeze decisions, compatibility và contract baseline

Mục tiêu: khóa các human decisions cần cho implementation và bảo vệ contract AI1→AI2 hiện tại.

TDD:

- Tests before: current `ocr.json`/`ai1.snapshot.v1`, missing citation, multiple logical documents, unsupported version, duplicate submit.
- Implement: chỉ thêm contract/compatibility fixtures và metadata cần thiết; không sửa AI1 producer.
- Tests after: existing AI1 contract suite và new contract cases.

Acceptance: baseline pass; unknown/missing/no-evidence behavior rõ; artifact `artifacts/p0-contract-baseline.json`.

Rollback: giữ adapter hiện tại, không đổi public schema.
