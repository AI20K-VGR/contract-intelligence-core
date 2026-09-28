# Code review final — AI2 long-running architecture

## Phạm vi

Review chỉ đọc các reports/artifacts hiện hành và:

- `ai-service/app/security/policy.py`
- `ai-service/app/transport/events.py`
- `ai-service/app/ops/readiness.py`
- `ai-service/tests/test_p5_api_security.py`
- `ai-service/tests/test_p6_event_ui_convergence.py`
- `ai-service/tests/test_p9_production_readiness.py`

Không chạy lại test và không sửa code.

## Findings

**Important — điều kiện retention bị đảo chiều.** Tại `ai-service/app/ops/readiness.py:189-193`, gate dùng `recovery_window_days >= retention_days`, trong khi contract/report P9 yêu cầu retention phải bao phủ recovery window, tức `retention_days >= recovery_window_days`. Vì vậy cấu hình `retention_days=30`, `recovery_window_days=60` có thể được đánh PASS sai. Test `ai-service/tests/test_p9_production_readiness.py:68-76` chỉ kiểm tra hai giá trị bằng nhau nên chưa bắt được lỗi bất đẳng thức này.

Không thấy thêm lỗi Critical/Important trực tiếp trong các boundary P5/P6 đã đọc. Các giới hạn còn lại đã được ghi nhận trong reports/artifacts: policy/idempotency còn in-process và chưa gắn route thực; P6 chưa phải HTTP/SSE production server; P9 chỉ đánh giá evidence/configuration khai báo, chưa chứng minh HA, live traffic, load/soak hay recovery thật. Full test run cũng có giới hạn môi trường `PermissionError [WinError 5]` ở pytest temp-root; rerun workspace-local đã xanh theo `tester-final.md`.

## Verdict

**BLOCKED** — cần sửa điều kiện retention và thêm test cho trường hợp retention nhỏ hơn recovery window trước khi coi readiness gate là đúng.
