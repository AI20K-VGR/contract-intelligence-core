---
phase: 1
task: ST-044
title: "Validate handoff snapshot + dựng relation graph"
status: pending
plan: 260924-2201-260924-ai2-epic11-gap-closure
created: 2026-09-24
harness_version: 6.3.0
harness_kit_digest: 672de2e098c3cb8451018791788f1052b1b812ccec08a1f124191bd8bbc04ebd
harness_schema_version: 1.0
---

# Phase 1 — ST-044: Handoff + relation graph

## Mục tiêu

Đóng riêng ST-044: validate schema/digest/provenance/lifecycle của canonical handoff và dựng relation graph từ parent, source role, explicit references. AI2 không nhận raw PDF. Đây là commit bằng chứng C1.

## Files / ownership

- **AI2:** `ai-service/app/contracts/wire.py`, `ai-service/app/pipeline/handoff.py`, `ai-service/app/reasoning/relations.py`, processing adapter nếu cần.
- **Tests:** `ai-service/tests/test_processing_wire_contract.py`, handoff/relation tests; tạo `ai-service/tests/test_st044_handoff_relation.py` nếu thiếu coverage.
- Không sửa fact/finding/query/index trong commit này.

## TDD

- **RED:** raw PDF, sai schema/digest/provenance/lifecycle, page/node failed, missing parent/reference và non-deterministic graph.
- **Implement:** chỉ bổ sung validation/edge construction/contract coverage trên pipeline hiện tại.
- **GREEN:** targeted ST-044 suite và regression canonical wire contract.

## Success / evidence

- [ ] Handoff hợp lệ qua gate; raw PDF/snapshot sai bị reject.
- [ ] Graph có `PARENT_OF`, source-role và explicit reference/amendment edges, bounded và deterministic.
- [ ] Tạo `verification-ST-044.json` gồm commands, test count, exit code, file:line anchors.
- [ ] Commit duy nhất của task: `feat(ai2): complete ST-044`; kiểm tra `git show --stat --check <C1>`.

## Lệnh kiểm tra

```powershell
cd ai-service
$env:PYTHONPATH=(Get-Location).Path
.\.venv\Scripts\python.exe -m pytest -q tests/test_processing_wire_contract.py tests/test_ingest.py tests/test_st044_handoff_relation.py
```

## Rollback

`git revert <C1>` rồi chạy lại canonical contract suite; không reset/checkout destructive.
