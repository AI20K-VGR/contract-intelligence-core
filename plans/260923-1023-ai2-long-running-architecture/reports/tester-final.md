# Báo cáo tester final gate — AI2 long-running architecture

Ngày chạy: `2026-09-23`  
Plan: `260923-1023-ai2-long-running-architecture`  
Phạm vi: P0–P9, P7 evaluation gate, `compileall app`  
Thay đổi code/test: không thực hiện. Commit/push: không thực hiện.

## Verdict

**PASS_WITH_ENVIRONMENT_NOTE**

Các kiểm tra đã đạt khi chạy với temp workspace-local. Run bắt buộc ban đầu dùng default Windows temp root gặp lỗi quyền truy cập; đây là ghi chú môi trường, không phải lỗi assertion của code.

## Kết quả thực tế

| Kiểm tra | Lệnh / thư mục chạy | Kết quả | Exit |
|---|---|---:|---:|
| P7 evaluation gate | `set PYTHONPATH=root; ai-service/.venv/Scripts/python.exe -m pytest -q evals/tests/test_p7_evaluation_gate.py` / repo root | `5 passed in 0.02s` | `0` |
| P0–P9 targeted gate — run bắt buộc | `.venv/Scripts/python.exe -m pytest -q tests/test_p9_production_readiness.py tests/test_p8_migration_boundary.py tests/test_p8_migration_parity.py tests/test_p6_event_ui_convergence.py tests/test_p5_api_security.py tests/test_p4_execution_adapters.py tests/test_p3_persistence_events.py tests/test_p2_hitl_state.py tests/test_p1_canonical_model.py tests/test_p0_contract_baseline.py` / `ai-service` | `69 passed, 2 warnings, 6 errors in 2.13s` | `1` |
| P0–P9 targeted gate — rerun workaround | Cùng selector, với TEMP/TMP workspace-local | `300 passed, 6 deselected, 2 warnings` | `0` |
| Compile check | `.venv/Scripts/python.exe -m compileall -q app` / `ai-service` | Không có output lỗi | `0` |

## Environment note

Run bắt buộc với default temp root thất bại ở pytest `tmp_path` fixture:

```text
_pytest/pathlib.py:175 -> os.scandir(root)
PermissionError: [WinError 5] Access is denied: 'C:\\Users\\dungs\\AppData\\Local\\Temp\\pytest-of-dungs'
```

Sáu test bị ảnh hưởng trong run đầu là năm test của `tests/test_p3_persistence_events.py` và `tests/test_p0_contract_baseline.py::test_duplicate_submit_returns_same_job_and_conflicting_payload_is_rejected`. Hai `PytestCacheWarning` cũng xuất hiện vì không ghi được `ai-service/.pytest_cache`.

Workaround đã xác nhận: trỏ `TEMP`/`TMP` tới thư mục workspace-local trước khi chạy lại cùng selector. Kết quả rerun là `300 passed, 6 deselected, 2 warnings, exit 0`.

## Kết luận

Final gate **PASS_WITH_ENVIRONMENT_NOTE**. Code/test không bị chỉnh sửa; cần duy trì cấu hình temp workspace-local hoặc cấp quyền phù hợp cho default temp root khi tái hiện gate trên môi trường này.
