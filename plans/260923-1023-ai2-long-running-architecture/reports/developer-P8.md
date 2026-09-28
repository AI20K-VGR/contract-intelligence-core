# Báo cáo developer P8 — migration parity và rollback

## Phạm vi

Đã bổ sung các module stdlib-only `ai-service/app/migration/canary.py` và `ai-service/app/migration/boundary.py`, cùng hai nhóm test `test_p8_migration_parity.py` và `test_p8_migration_boundary.py`. Thay đổi chỉ bao phủ các primitive bounded theo yêu cầu P8; không sửa route, persistence, contract AI1 hay traffic production.

## Contract đã triển khai

- `MigrationMode` hỗ trợ `LEGACY`, `CANARY`, `CANONICAL`.
- `MigrationConfig` giữ policy chỉ publish verified và bật/tắt compare.
- `SubmitRecord.digest` dùng SHA-256 trên payload field được canonicalize ổn định.
- `submit_once` trả lại record hiện có cho retry cùng idempotency key/digest và reject conflict.
- `can_publish` fail-closed với generation stale/mismatch hoặc status khác `VERIFIED`.
- `compare_outputs` trả `equal` và tuple path khác biệt theo thứ tự deterministic.
- `rollback_mode` chuyển mode về `LEGACY` và giữ nguyên các flag.
- `MigrationBoundary` giữ mapping legacy session → run, parity dual-read, rollback mid-run và chặn publish stale/unverified.

## Kiểm thử

Focused command (đã resolve glob `test_p8*.py` trong PowerShell):

```text
.venv\\Scripts\\python.exe -m pytest -q tests/test_p8*.py --basetemp=.pytest-basetemp-p8
```

Kết quả thực tế: `13 passed, 1 warning`.

Warning duy nhất là `PytestCacheWarning` do `.pytest_cache` không writable trên Windows; test không bị fail. Bộ focused gồm cả `test_p8_migration_boundary.py` và `test_p8_migration_parity.py`.

## Giới hạn

Đây là parity/rollback boundary thuần deterministic, chưa kết nối với route hoặc persistence production. Không có commit được tạo.
