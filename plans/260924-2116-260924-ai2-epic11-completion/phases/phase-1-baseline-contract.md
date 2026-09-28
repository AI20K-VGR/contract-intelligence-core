---
phase: 1
title: "Baseline Contract"
status: pending
plan: 260924-2116-260924-ai2-epic11-completion
created: 2026-09-24
harness_version: 6.3.0
harness_kit_digest: 672de2e098c3cb8451018791788f1052b1b812ccec08a1f124191bd8bbc04ebd
harness_schema_version: 1.0
---

# Phase 1 — Baseline & Contract Gate

## Overview

Chốt canonical contract và baseline test trước khi sửa behavior. Đồng bộ `be.ai2.processing.request.v1`/`ai1.snapshot.v1` giữa AI2–Backend, lập compatibility boundary cho `ai1.snapshot.v3` và legacy extraction/comparison, đồng thời xử lý blocker fixture/standards để các gate sau có thể chạy thật.

## Requirements

- Request/result schema version phải được assert ở cả hai service.
- Digest, idempotency, HMAC envelope và migration boundary phải có test tự động.
- Mọi unresolved contract choice phải gắn `[ASSUMED]` và dừng trước phase 2.

## Implementation Steps

1. Chạy targeted baseline và lưu failure/fixture inventory.
2. Đối chiếu wire schema, Backend builder và legacy adapter; chốt canonical version bằng artifact được mentor duyệt.
3. Thêm contract fixtures và negative tests; cập nhật migration note, không đổi legacy route ngầm.
4. Chạy phase gate và ghi `verification-P1.json`.

## Evidence và touchpoints

- `ai-service/app/contracts/wire.py:53,107` — snapshot/request version hiện tại.
- `ai-service/app/pipeline/ai1_snapshot_adapter.py:275` — canonical snapshot adapter.
- `backend/src/contract_intelligence/shared/ai/canonical_processing.py:204,338` — Backend builder.
- `backend/src/contract_intelligence/shared/ai/ai1_adapter.py:28` — v3 → v1 compatibility boundary.
- `docs/contracts/BE-AI2-PROCESSING-CONTRACT.vi.md:8` — processing contract hiện hành.
- `docs/DOC-05c-backend-ai-service-contract.md:351` — legacy v3/v2 contract cần đánh dấu rõ.

## Files

**Create/Modify:** `ai-service/tests/test_contract_*.py`, `backend/tests/...` canonical contract tests, `docs/contracts/*`/mentor decision note, fixture support files nếu owner xác nhận chúng thuộc workspace; không sửa unrelated dirty files.

## TDD (Tests Before → Implement → Tests After → Regression Gate)

- **Tests-before (RED):** test request snapshot version/digest mismatch, duplicate member, legacy endpoint usage, signed envelope/idempotency và canonical result schema; chạy baseline targeted và ghi failure thật.
- **Implement:** chốt validator/adapter/contract registry; thêm explicit migration note và fixture prerequisite.
- **Tests-after:**
  - `cd ai-service; $env:PYTHONPATH=(Get-Location).Path; .\.venv\Scripts\python.exe -m pytest -q tests/test_processing_wire_contract.py tests/test_canonical_contract.py tests/test_happy_ai2_contract.py`
  - `cd backend; uv run pytest tests -q` (pytest config: `backend/pyproject.toml:147`)
  - full suite chỉ chạy sau khi fixture import blocker được giải quyết.
- **Regression gate:** schema validation, HMAC envelope, idempotency, no-raw-PDF negative test đều pass; không được claim full green nếu chưa có output command.

## Success

- [ ] Mentor quyết định canonical version và được ghi vào contract artifact.
- [ ] AI2/Backend cùng tạo và validate một canonical request/result mẫu.
- [ ] Legacy `v3`/`v2` được đánh dấu adapter/compatibility, không còn là đường mặc định.
- [ ] Fixture blocker và missing standards có owner/action rõ ràng.

## Risk Assessment

Rủi ro lớn nhất là sửa code trước khi version contract được chốt, dẫn đến hai shape cùng được coi là canonical. Chặn bằng contract gate và không cook phase 2 khi artifact chưa được duyệt.
