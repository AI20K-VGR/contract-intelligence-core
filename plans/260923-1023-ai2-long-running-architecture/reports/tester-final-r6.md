# Tester final R6 — AI2 long-running architecture

Ngày chạy: `2026-09-24`  
Phạm vi: full `ai-service`, targeted P0–P9, P7 evaluation gate, `compileall app`  
Thay đổi code/docs/plan/artifacts: không thực hiện. Không commit/push.

## Verdict

**PASS_WITH_ENVIRONMENT_NOTE**

Các kiểm tra được yêu cầu đã chạy xong và không có test failure. Kết quả dưới đây là từ lượt chạy mới, không dùng lại counts cũ/cache cũ.

## Kết quả đã xác nhận

| Kiểm tra | Lệnh thực thi từ `ai-service` | Kết quả | Exit |
|---|---|---:|---:|
| Preflight trực tiếp | `\.\.venv\Scripts\python.exe ..\harness\scripts\hs_run.py test next` | JSON `state=verified`, `exit_code=0`; harness định tuyến tới completion-release đã đóng | `0` |
| Full suite | `\.\.venv\Scripts\python.exe -m pytest -q` | `373 passed, 6 deselected, 2 warnings in 17.03s` | `0` |
| Targeted P0–P9 | `\.\.venv\Scripts\python.exe -m pytest -q tests/test_p9_production_readiness.py tests/test_p8_migration_boundary.py tests/test_p8_migration_parity.py tests/test_p6_event_ui_convergence.py tests/test_p5_api_security.py tests/test_p4_execution_adapters.py tests/test_p3_persistence_events.py tests/test_p2_hitl_state.py tests/test_p1_canonical_model.py tests/test_p0_contract_baseline.py` | `148 passed, 1 warning in 1.74s` | `0` |
| P7 evaluation gate | `\.\.venv\Scripts\python.exe -m pytest -q ..\evals\tests\test_p7_evaluation_gate.py` | `5 passed in 0.03s` | `0` |
| Compile app | `\.\.venv\Scripts\python.exe -m compileall -q app` | Không có output lỗi | `0` |

Trước mỗi lệnh test/compile, phiên chạy đặt:

```powershell
$env:TEMP = (Join-Path (Get-Location) 'tmp\tester-final-r6')
$env:TMP = (Join-Path (Get-Location) 'tmp\tester-final-r6')
$env:PYTHONPATH = (Resolve-Path '..').Path
```

## Warnings

- Full suite: `DeprecationWarning` từ `starlette\testclient.py:53` về `anyio.abc.BlockingPortal`.
- Full và targeted suite: `PytestCacheWarning` vì process không tạo được `ai-service\.pytest_cache\v\cache\nodeids` do `WinError 5: Access is denied`.
- Đây là warning môi trường; không có assertion failure.

## Limitations / chưa hoàn tất

- `..\harness\bin\hs-run.cmd test next` không chạy được trên Windows do launcher bị lỗi parse encoding (`'un' is not recognized...`); preflight được xác nhận bằng Python script trực tiếp như bảng trên.
- P7 được gọi từ `ai-service` bằng path tương đối `..\evals\tests\test_p7_evaluation_gate.py` vì thư mục `evals` nằm ở workspace root.
- `compileall -q app` chỉ báo exit code, không xuất số file biên dịch.
- Không tạo/cập nhật `verification.yaml`, JUnit artifact hoặc artifact verification khác theo yêu cầu không sửa artifacts.
- Lệnh dọn thư mục temp/log `ai-service\tmp\tester-final-r6` đã bị ngắt khi người dùng hủy lượt trước; không chạy lại và không chờ thêm. Các thư mục tạm cũ có sẵn trong workspace không bị dọn.
- Đây là kiểm tra pytest/compile theo phạm vi yêu cầu; không phải bằng chứng cho production HTTP/SSE, HA/recovery hoặc live external integrations.

