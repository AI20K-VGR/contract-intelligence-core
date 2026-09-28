---
phase: 2
title: "AI2 Persistence Coverage"
status: pending
plan: 260925-0238-ai1-ai2-be-fe-review-fixes-260925-0238
created: 2026-09-25
---

# Phase 2 — AI2 Persistence Coverage

## Overview

Đưa toàn bộ `ai2.be.processing.result.v1` qua Backend persistence/read model mà không làm rơi context/evidence. Phase bảo toàn facts, findings, context findings, events, chunks, citations, evidence issues, annex links và coverage; đồng thời tách job `SUCCEEDED` khỏi predicate evidence-ready.

Dependencies: Phase 1 ACL/route invariant; AI2 producer và canonical schema hiện có. Downstream: phases 3–6.

## Files

- Modify: `backend/src/contract_intelligence/shared/ai/persistence.py`, result DTO/mapper và pipeline status mapper đang chỉ đọc `facts`/`findings`.
- Inspect/modify only when required by a failing contract test: `ai-service/app/contracts/wire.py`, `docs/contracts/ai2.be.processing.result.v1.schema.json` (không đổi version âm thầm).
- Extend the existing Backend read-model repository/model; không tạo bảng song song khi projection hiện tại đủ chứa JSON/provenance.
- Create: `backend/tests/unit/test_ai2_result_persistence.py`, `backend/tests/unit/test_ai2_read_model_completeness.py`.
- Modify: `backend/tests/unit/test_worker_pipeline_run.py`, `ai-service/tests/test_processing_wire_contract.py`.

## Tests Before (RED)

- [ ] Round-trip fixture có 58 chunks, 23 events, citations, context findings, evidence issues, annex links và coverage nhưng `facts=[]`, `findings=[]`; tất cả IDs/counts/provenance phải còn.
- [ ] Fact/finding thiếu citation tạo review/error metric hoặc drop reason ổn định, không silently skip và không evidence-ready.
- [ ] `SUCCEEDED` không tự thành evidence-ready khi read model incomplete/zero-output bất thường.
- [ ] Run `python -m pytest backend/tests/unit/test_ai2_result_persistence.py backend/tests/unit/test_ai2_read_model_completeness.py backend/tests/unit/test_worker_pipeline_run.py -q --basetemp tmp/plan-ai2-p2-red`; tests mới fail trên persistence hiện tại.

## Implement

1. Map each wire field to an existing read model or versioned canonical JSON projection with schema validation; retain source file, citation, document and annex scope.
2. Persist nested arrays atomically with job result and idempotency key; same payload replay is safe, digest conflict is rejected.
3. Add completeness evaluation for no eligible data vs dropped invalid data vs persistence failure; emit reason code and input/output counts.
4. Keep job lifecycle `SUCCEEDED` separate from evidence-ready; expose the completeness/state fields through a DTO.
5. Add reload-process tests to prove the result is not only in memory.

## Tests After (GREEN)

- [ ] Full wire payload round-trips nested fields, citation provenance, coverage and annex links.
- [ ] Idempotent replay creates no duplicate records; invalid citation produces a stable reason/review state.
- [ ] Input pages/lines/tables, output chunks/citations/facts/findings, dropped records and evidence issue count match the fixture.

## Regression Gate

`python -m pytest backend/tests/unit/test_ai2_result_persistence.py backend/tests/unit/test_ai2_read_model_completeness.py backend/tests/unit/test_worker_pipeline_run.py ai-service/tests/test_processing_wire_contract.py ai-service/tests/test_contract_context.py -q --basetemp tmp/plan-ai2-p2-regression`; then `ruff check backend/src backend/tests ai-service/app ai-service/tests`.

## Success / Acceptance

- [ ] Context/chunks/events/evidence issues with zero facts/findings remain visible in the read model/DTO.
- [ ] Missing citation is never silently dropped; reason code and review state are persisted.
- [ ] `SUCCEEDED` is not presented as `PASS` or evidence-ready.

## Risks

- Old read models may lack nested fields; use additive versioned projection/migration and retain backward reads.
- Large atomic payloads may stress transactions; bound payload/retry rather than adding an out-of-scope queue.
- Producer/consumer drift; validate fixtures against the canonical schema before persistence assertions.

## Rollback

Feature-flag the new projection write while retaining the old reader; revert only mapper/read-model writes on failure, never delete persisted evidence or downgrade review state.
