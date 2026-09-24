# Developer report — P3 / ST-046

## Kết quả

Developer lane không hoàn tất sau nhiều lần chờ; main tiếp quản inline có kiểm soát để đóng scope tối thiểu của ST-046. Query boundary bind `snapshot_digest` với canonical record trước khi chạy FourLayerReasoner. Contract mới `ai2.query.v1` bắt buộc digest; digest thiếu hoặc stale trả `INSUFFICIENT_EVIDENCE`. Signed legacy caller không có field version vẫn giữ compatibility. Không đổi L0/L1/L2/L3 semantics.

## Files changed

- `ai-service/app/api/main.py`
- `ai-service/tests/test_st046_query_grounding.py`
- `backend/src/contract_intelligence/api/v1/dossiers.py`
- `backend/src/contract_intelligence/infrastructure/ai_adapters.py`

## Verification

- AI2 query/retrieval/grounding targeted suite: `51 passed`, exit code `0`.
- AI2 full suite: `686 passed, 1 skipped, 27 warnings`, exit code `0`.
- Backend pytest đã chạy ngoài sandbox nhưng dừng ở test không liên quan `TestDossierEndpoints.test_list_dossiers_returns_empty_list`: SQLite không hiểu PostgreSQL cast `::json`; kết quả `1 failed, 9 passed, 184 deselected`. Chưa claim Backend E2E PASS vì môi trường test hiện có blocker độc lập này.
- Metadata-only query vẫn fail-closed; stale digest fail-closed trước reasoning; valid path tiếp tục dùng reasoner hiện tại.

## Deviation

Main thực hiện inline vì `hs:developer` không trả kết quả sau nhiều lần chờ; không có thay đổi ngoài P3 boundary và test. Chưa claim Backend E2E PASS do blocker SQLite/PostgreSQL nêu trên.
