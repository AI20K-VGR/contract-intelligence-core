---
phase: 5
title: "Backend Integration Verification"
status: pending
plan: 260924-2116-260924-ai2-epic11-completion
created: 2026-09-24
harness_version: 6.3.0
harness_kit_digest: 672de2e098c3cb8451018791788f1052b1b812ccec08a1f124191bd8bbc04ebd
harness_schema_version: 1.0
---

# Phase 5 — Backend E2E & Verification Gate

## Overview

Đóng phần tích hợp thực tế: Backend submit/poll canonical `/jobs/idp`, persist `ai2.be.processing.result.v1`, tạo review/audit, query chỉ gửi context/reference hợp lệ và ghi QueryTrace. Loại bỏ việc coi metadata-only `/process`, legacy extract/compare là đường hoàn thành. Kết thúc bằng integration, security và regression gate.

## Requirements

- Backend phải chọn canonical route bằng contract version, poll signed result và persist idempotently.
- Query phải qua ACL/policy, đúng snapshot digest và ghi audit trace.
- Retry, timeout, stale result, tenant isolation và active-index prohibition phải có negative tests.
- Không được báo full PASS khi fixture blocker hoặc test command chưa có output thành công; phải có mentor disposition nếu chấp nhận blocker.

## Implementation Steps

1. Viết RED integration tests cho submit/poll/persist/query/retry, stale digest, route selection và cross-tenant scope.
2. Route orchestrator/adapter sang canonical `/jobs/idp`; giữ legacy fail-closed.
3. Wire persistence, review/audit và query context; thêm contract smoke fixture giữa hai service.
4. Chạy full suite/lint/type-check/build; nếu fixture blocker còn tồn tại thì ghi FAIL/BLOCKED, không hạ tiêu chuẩn; ghi `verification-P5.json` + `review-decision.json`.

## Files

**Modify:** `backend/src/contract_intelligence/infrastructure/ai_adapters.py:163`, `backend/src/contract_intelligence/shared/ai/canonical_processing.py`, `backend/src/contract_intelligence/shared/ai/persistence.py:659`, `backend/src/contract_intelligence/shared/ai/pipeline_orchestrator.py`, `backend/src/contract_intelligence/api/v1/dossiers.py:174`, worker/webhook path và config nếu cần.

**Create/Modify tests:** Backend adapter/orchestrator/persistence/query tests; AI2 API E2E fixtures; contract samples; negative tenant/ACL/idempotency/stale-digest tests.

## TDD (Tests Before → Implement → Tests After → Regression Gate)

- **Tests-before (RED):** submit canonical request → 202 → poll signed result; persist facts/findings/citations; duplicate idempotency; worker retry; query ACL/policy; missing projection; stale digest; AI2 timeout/provider error; no active index mutation.
- **Implement:** route canonical processing end-to-end, wire persistence/review state/audit, add query context handoff and response state, retain legacy fail-closed compatibility.
- **Tests-after:**
  - `cd ai-service; $env:PYTHONPATH=(Get-Location).Path; .\.venv\Scripts\python.exe -m pytest -q tests`
  - `cd backend; uv run pytest` (documented at `backend/README.md:114`)
  - `cd backend; uv run ruff check .` và `uv run lint-imports` (`backend/README.md:117-118`)
  - Chạy contract smoke giữa hai service bằng fixture sanitized.
- **Regression gate:** full AI2 + Backend suite, lint/type-check/build nếu repo có; security negative tests và artifact scan không có secret/raw PDF.

## Success

- [ ] Một request canonical đi xuyên Backend → AI2 → Backend persistence/review không dùng legacy metadata-only lane.
- [ ] Query trả đúng state/citation và được Backend audit theo ACL/policy/snapshot digest.
- [ ] Retry/idempotency/stale result không tạo duplicate fact/finding hoặc vượt active index gate.
- [ ] Toàn bộ ST-044–ST-047 có evidence command/output và không còn blocker chưa được ghi nhận.

## Risk Assessment

Backend hiện có nhiều adapter cũ chạy song song, dễ tạo hai behavior. Mitigation: test route selection, log contract version, explicit deprecation marker và không xóa legacy cho đến khi migration smoke pass.
