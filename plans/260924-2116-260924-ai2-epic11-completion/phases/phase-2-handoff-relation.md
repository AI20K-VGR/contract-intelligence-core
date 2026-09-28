---
phase: 2
title: "Handoff Relation"
status: pending
plan: 260924-2116-260924-ai2-epic11-completion
created: 2026-09-24
harness_version: 6.3.0
harness_kit_digest: 672de2e098c3cb8451018791788f1052b1b812ccec08a1f124191bd8bbc04ebd
harness_schema_version: 1.0
---

# Phase 2 — Handoff & Relation Graph

## Overview

Đóng ST-044: validate snapshot từ Backend bằng schema, content digest, provenance pins, lifecycle/page inventory và dossier membership; sau đó dựng relation graph từ parent node, source role và explicit reference. Không mở đường raw PDF/OCR.

## Requirements

- Validation phải reject raw PDF và mismatch schema/digest/provenance/membership với code/state ổn định.
- Graph phải deterministic, bounded, giữ source digest/citation và phân biệt ambiguity với confirmed relation.
- Không được để graph edge tự sinh ra legal finding.

## Implementation Steps

1. Viết RED fixtures cho valid/invalid handoff và relation edge/issue.
2. Củng cố thứ tự validation và error mapping tại handoff boundary.
3. Củng cố graph construction, ordering, scope/budget và explicit reference handling.
4. Chạy regression phase 1 và ghi `verification-P2.json`.

## Files

**Modify:** `ai-service/app/pipeline/handoff.py`, `ai-service/app/reasoning/relations.py`, `ai-service/app/pipeline/idp.py`, `ai-service/app/contracts/wire.py` nếu thiếu invariant.

**Create/Modify tests:** `ai-service/tests/test_handoff_*.py`, `test_relation_graph*.py`, canonical API tests cho `/jobs/idp`.

## TDD (Tests Before → Implement → Tests After → Regression Gate)

- **Tests-before (RED):** valid body+annex; schema invalid; source digest mismatch; missing version pin; page FAILED/ENCRYPTED; raw PDF bytes; wrong tenant/dossier; parent-child; role edge; explicit `REFERENCES`/`AMENDS`; missing/ambiguous target; deterministic graph ordering.
- **Implement:** củng cố validation ordering và stable error/state; graph edges phải giữ `source_snapshot_digest`, citation linkage, role và issue; giới hạn node/edge expansion.
- **Tests-after:** `cd ai-service; $env:PYTHONPATH=(Get-Location).Path; .\.venv\Scripts\python.exe -m pytest -q tests/test_handoff* tests/test_relation* tests/test_processing_wire_contract.py`.
- **Regression gate:** chạy lại phase 1 targeted suite; kiểm tra request không chứa PDF bytes và graph không vượt budget.

## Success

- [ ] Handoff hợp lệ tạo được `ValidatedHandoff` và relation graph deterministic.
- [ ] Invalid schema/digest/provenance/membership/lifecycle trả code/state có thể audit.
- [ ] Relation graph liên kết đúng body–annex, explicit reference và citation; ambiguity không bị tự đoán.
- [ ] Negative tests chứng minh AI2 không nhận raw PDF hoặc tự OCR.

## Risk Assessment

Graph có thể nối nhầm tài liệu do reference không đủ target. Mitigation: relation issue + `NEEDS_REVIEW`, bounded expansion và không cho graph edge tự trở thành finding.
