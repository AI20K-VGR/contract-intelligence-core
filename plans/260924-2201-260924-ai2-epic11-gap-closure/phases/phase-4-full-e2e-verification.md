---
phase: 4
task: ST-047
title: "Propose IndexContribution + reviewer gate"
status: pending
plan: 260924-2201-260924-ai2-epic11-gap-closure
created: 2026-09-24
harness_version: 6.3.0
harness_kit_digest: 672de2e098c3cb8451018791788f1052b1b812ccec08a1f124191bd8bbc04ebd
harness_schema_version: 1.0
---

# Phase 4 — ST-047: IndexContribution + reviewer gate + final E2E

## Mục tiêu

Đóng riêng ST-047: AI2 tạo `IndexContribution` ở trạng thái `propose`; Backend/reviewer quyết định publish active với audit/idempotency. Trong cùng commit C4, chạy final Backend → AI2 → Backend E2E/regression để chứng minh C1–C3 phối hợp đúng. Final verification là artifact của ST-047, không tạo commit thứ 5.

## Files / ownership

- **AI2:** `ai-service/app/pipeline/index.py`, `ai-service/app/contracts/models.py`, `ai-service/app/contracts/wire.py`.
- **Backend:** reviewer/persistence/worker quanh `backend/src/contract_intelligence/worker.py:382-410`, `backend/src/contract_intelligence/shared/ai/persistence.py:659-790`; chỉ nối interface đã được owner chốt.
- **Tests/artifacts:** proposal/reviewer tests, tạo `ai-service/tests/test_st047_index_gate.py`, `backend/tests/contract_intelligence/test_st047_review_gate.py`, và final E2E test nếu thiếu.
- Không sửa ST-044/ST-045/ST-046 semantics trong commit này; nếu phát hiện regression thì mở blocker, không lẫn sửa task cũ.

## TDD

- **RED:** AI2 publish khác `propose`, unauthorized active-pointer mutation, reviewer reject/approve, duplicate/retry, stale digest/cross-tenant contribution.
- **Implement:** nối gate hiện có hoặc interface tối thiểu có owner/API/storage rõ; lưu audit actor/digest/timestamp/idempotency; AI2 không có publish capability.
- **GREEN:** ST-047 targeted suite, final E2E và toàn bộ regression C1–C3; full suite/type-check/build/lint theo command thật.

## Success / evidence

- [ ] AI2 chỉ phát `IndexContribution.publish=propose`.
- [ ] Reviewer approve mới đổi active pointer; reject/retry giữ invariant và audit.
- [ ] Final E2E chứng minh Backend chọn snapshot → AI2 process → Backend persist → query grounded → index proposal/review.
- [ ] `verification-ST-047.json` gồm C1–C4 commit SHAs, commands, test counts, exit codes và blocker owner nếu có.
- [ ] Commit duy nhất của task: `feat(ai2): complete ST-047`; kiểm tra `git show --stat --check <C4>`.
- [ ] Sau C4, `git log --oneline -4` map một-một ST-044/ST-045/ST-046/ST-047; không có commit thứ 5 cho verification.

## Lệnh kiểm tra

```powershell
cd ai-service
$env:PYTHONPATH=(Get-Location).Path
.\.venv\Scripts\python.exe -m pytest -q tests -k "index or st047 or processing_wire"
cd ..\backend
uv run pytest -q tests -k "review or persistence or ai2 or st047" --maxfail=1
```

## Blocker policy

Nếu reviewer API/storage, fixture, temp-dir, dependency hoặc Backend interpreter chưa sẵn sàng, ghi `BLOCKED`/`NEEDS_REVIEW` cùng command, exit code, owner; không fake approve, không skip silent, không hạ assertion.

## Rollback

`git revert <C4>` rồi chạy lại C1–C3 regression; nếu cần rollback toàn bộ thì revert theo thứ tự C4 → C1.
