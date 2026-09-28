# Báo cáo debug/fix: AI2 query mất snapshot sau restart

## Nguyên nhân đã xác nhận

`ai-service/app/api/main.py:784-793` chỉ đọc `STORE`, là registry trong RAM. Trong khi đó `ai-service/app/transport/kafka_idp_worker.py:171-174` đã ghi snapshot citation-bearing vào `query_store`, endpoint `/query` không đọc lại kho này. Vì vậy khi HTTP query API khác process với worker, hoặc API vừa restart, `STORE.get(...)` trả `None` và endpoint rơi vào `AI2_QUERY_EVIDENCE_REQUIRED` dù snapshot đã được persist.

## Tái hiện

Test hồi quy `ai-service/tests/test_legacy_compat.py:129-162` lưu một record có snapshot/citation vào durable query store, xoá `main.STORE`, rồi query bằng service envelope hợp lệ.

- Trước fix: `1 failed`, response có `state=INSUFFICIENT_EVIDENCE`.
- Sau fix: test pass, query trả citation.

## Thay đổi

- `ai-service/app/api/main.py:176-180`: HTTP worker ghi record canonical vào RAM và durable query store ngay sau khi validate handoff.
- `ai-service/app/api/main.py:784-792`: query hydrate record từ durable store theo `tenant_id + dossier_id` khi RAM miss, sau đó vẫn kiểm tra `snapshot_digest` hiện hành trước reasoning.
- Không nới lỏng HMAC, tenant binding, dossier binding hoặc digest guard.

## Kiểm thử

- Targeted regression + query/contract tests: `38 passed`.
- AI2 suite, bỏ qua test collection lỗi sẵn `tests/unit/test_production_query.py`: `721 passed, 1 skipped`.
- Full suite còn 1 lỗi có sẵn tại `tests/unit/test_kafka_contract_compat.py::test_kafka_boundary_accepts_current_ocr_lab_snapshot_shape`: test tự tính schema root thành `C:\Users\dungs\OneDrive\docs\contracts`, không phải lỗi của thay đổi này.
- `hs-run fix next` không chạy được trên Windows hiện tại vì `harness/bin/hs-run.cmd` bị lỗi parsing/path (`hs-run: cannot find ""`).

## Blast radius

Chỉ ảnh hưởng đường query canonical của AI2 và HTTP processing worker. Legacy `/process`, query không có service envelope, và digest mismatch vẫn fail closed như trước.
