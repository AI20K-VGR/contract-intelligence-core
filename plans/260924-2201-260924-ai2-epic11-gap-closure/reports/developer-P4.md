# Developer report — P4 / ST-047

## Kết quả

Developer lane không hoàn tất sau nhiều lần chờ; main tiếp quản inline có kiểm soát. AI2 giữ invariant propose-only: `IndexStore.propose()` chỉ tạo `IndexContribution` với `publish=propose`, append proposal và không thay đổi `active_pointer`. Backend đã bổ sung reviewer gate scoped theo tenant/dossier/digest với approve/reject, audit và idempotency.

## Files changed

- `ai-service/tests/test_st047_index_gate.py`
- `backend/src/contract_intelligence/shared/ai/index_gate.py`
- `backend/tests/contract_intelligence/test_st047_review_gate.py`

Không sửa `ai-service/app/pipeline/index.py` vì invariant ST-047 đã tồn tại và test mới xác nhận trực tiếp.

## Verification

- ST-047 targeted + related AI2 tests: `62 passed`, exit code `0`.
- AI2 full suite: `692 passed, 1 skipped, 27 warnings`.
- Backend reviewer gate: `2 passed`.
- Backend full suite: `264 passed, 28 warnings`.
- Backend ruff: `All checks passed`.
- Proposal/retry evidence: hai lần propose vẫn trả `publish=propose`, `active_pointer` vẫn `None`, không tự promote index.
- Review-required evidence: snapshot quality thấp trả `NEEDS_REVIEW` nhưng contribution vẫn `publish=propose`.

## Blockers / boundary

- Reviewer gate đã có interface rõ ràng tại `shared/ai/index_gate.py`; persistence implementation có thể thay thế in-memory seam mà không đổi AI2 wire contract.
