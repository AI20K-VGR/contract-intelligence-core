---
phase: 1
title: "Contract Boundaries"
status: pending
plan: 260923-1023-ai2-completion-release
created: 2026-09-23
harness_version: 6.3.0
harness_kit_digest: 672de2e098c3cb8451018791788f1052b1b812ccec08a1f124191bd8bbc04ebd
harness_schema_version: 1.0
---

# Phase 1 — Contract Boundaries

## Overview

Khóa ranh giới AI1–AI2 trước khi sửa logic: canonical snapshot/request, identity,
membership, digest, role, tenant/dossier scope, legacy adapter và result wire. Hai
OCR-lab inputs được đọc theo producer profile `ai1.snapshot.v1/ocr-lab` qua adapter,
không được nhầm với canonical backend snapshot và không suy quan hệ giữa
`doc-001` và `doc-002` từ `dossier_id` chung.

Phase này cũng khóa registry profile cho sáu loại hợp đồng wave đầu. Type profile
chỉ định field/fact đặc thù, alias và version; nhận diện type phải dựa trên evidence
trong snapshot hoặc caller metadata đã được xác nhận, không suy từ tên file.

## Context links

- `docs/contracts/AI1-AI2-CONTRACT.vi.md`
- `docs/contracts/BE-AI2-PROCESSING-CONTRACT.vi.md`
- `docs/contracts/ai1.snapshot.v1.schema.json`
- `docs/contracts/be.ai2.processing.request.v1.schema.json`
- `docs/contracts/ai2.be.processing.result.v1.schema.json`
- `ai-service/app/pipeline/ai1_snapshot_adapter.py:58-372`
- `ai-service/app/contracts/models.py:97-198`
- `ai-service/app/contracts/wire.py:18-146`

## Files

**Modify:** `ai-service/app/pipeline/ai1_snapshot_adapter.py`,
`ai-service/app/contracts/models.py`, `ai-service/app/contracts/wire.py`,
`docs/contracts/ai1.snapshot.v1.schema.json`,
`docs/contracts/be.ai2.processing.request.v1.schema.json`,
`docs/contracts/ai2.be.processing.result.v1.schema.json`.

**Create:** `ai-service/app/contracts/contract_profiles.py` và
`docs/contracts/ai2.contract-type-profile.v1.schema.json`.

**Create or extend tests:** `ai-service/tests/test_processing_wire_contract.py`,
`ai-service/tests/test_canonical_contract.py`,
`ai-service/tests/test_ai1_result_v01.py`.

**Profile tests:** `ai-service/tests/test_contract_profiles.py`.

## Tests Before (regression coverage written BEFORE refactoring)

- [ ] Khóa request schema, membership mismatch, unknown root field, reject result
  v0.1 và result wire citation ở `test_processing_wire_contract.py:110-200`.
- [ ] Khóa compatibility adapter trong `test_ai1_result_v01.py` và
  `test_canonical_contract.py`; PASS là regression lock, không giả vờ RED.

## Implement

1. So sánh schema JSON, Pydantic wire models và adapter field-by-field; khóa
   ownership cho identity, role relation, snapshot/source digest và attempt.
2. Bổ sung semantic rejection cho duplicate snapshot/document identity, membership
   lệch, digest sai dạng, relation target ngoài dossier và unknown field.
3. Giữ `adapt_ai1_result_v01`/legacy riêng; package v1 không nhận legacy shape nếu
   caller không explicit gọi compatibility path.
4. Bảo đảm result wire đăng ký citation một lần, không tạo bbox/line/span mới khi
   upstream không có và map error code ổn định.
5. Cập nhật contract docs/registry nếu shape công khai thay đổi; không mở rộng root
   field để tiện truyền metadata nội bộ.

6. Khóa riêng topology producer hiện tại: table ở `pages[*].tables`, cell ở
   `rows[*].cells`, continuity ở root `table_continuity`; giữ `source_digest` raw
   dạng `sha256:<hex>` khi đi qua adapter.

7. Định nghĩa field core và profile riêng cho `SALES`, `SUPPLY_SERVICE`, `LEASE`,
   `CONSTRUCTION_WORK`, `EMPLOYMENT`, `NDA`; phụ lục giá/số lượng/phạm vi/tiến độ/
   SLA/thanh toán/nghiệm thu/điều chỉnh là profile extension. Unknown type/field
   không bị ép vào field sai loại; giữ raw evidence và `UNMAPPED`/`NEEDS_REVIEW`.

## Tests After (new behavior)

- [ ] Test duplicate identity, cross-dossier relation, source/snapshot digest
  mismatch, invalid attempt/idempotency và canonical-vs-legacy rejection.
- [ ] Test unknown nested field và empty/partial snapshot; phải là lỗi contract hoặc
  `NEEDS_REVIEW`, không exception không mã.
- [ ] Validate fixture result bằng `validate_contract(...)` và registry command.

## Regression Gate

`Set-Location ai-service; .venv\Scripts\python.exe -m pytest tests/test_processing_wire_contract.py tests/test_canonical_contract.py tests/test_ai1_result_v01.py -q --basetemp ..\tmp\ai2-phase1-basetemp`

Sau đó chạy full gate trong plan trước khi chuyển phase.

## Post artifact

Ghi `plans/260923-1023-ai2-completion-release/artifacts/verification-P1.json`
với `phase`, commit/tree fingerprint, exact commands, schema/semantic checks,
producer-profile topology checks và verdict. Artifact phải phân biệt test trước,
test sau và mọi `NOT_RUN`; không ghi baseline dirty-tree như bằng chứng sau cook.

## Success

- [ ] Input canonical hợp lệ đi qua adapter và result wire hợp lệ.
- [ ] Payload sai bị reject bằng error code có thể assert.
- [ ] Registry/schema xanh; không có compatibility field lọt vào canonical root.
- [ ] Type profile schema/version hợp lệ; profile mới không đổi semantics profile
  cũ; unknown type không tạo fact đặc thù không có evidence.

## Risks

Schema strict hơn có thể làm hỏng caller cũ; giữ adapter legacy và test migration
riêng, không nới canonical schema để che lỗi caller.
