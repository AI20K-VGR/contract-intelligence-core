# Developer report — P1 / ST-044

## Kết quả

Đã áp dụng thay đổi tối thiểu cho relation graph: node được sắp xếp ổn định theo `(order, node_id)` và parent thiếu được ghi thành `EvidenceIssue` thay vì âm thầm bỏ qua (`ai-service/app/reasoning/relations.py:132`, `ai-service/app/reasoning/relations.py:218-237`). Canonical wire/handoff validation hiện có được giữ nguyên.

## TDD evidence

- **RED:** `cd ai-service; $env:PYTHONPATH=(Get-Location).Path; .\.venv\Scripts\python.exe -m pytest -q tests/test_st044_handoff_relation.py --basetemp=.pytest-st044-red` — `1 failed` (expected: missing parent was not reported).
- **GREEN:** `cd ai-service; $env:PYTHONPATH=(Get-Location).Path; .\.venv\Scripts\python.exe -m pytest -q tests/test_st044_handoff_relation.py --basetemp=.pytest-st044-green` — `1 passed`.
- **Targeted regression:** `cd ai-service; $env:PYTHONPATH=(Get-Location).Path; .\.venv\Scripts\python.exe -m pytest -q tests/test_processing_wire_contract.py tests/test_ingest.py tests/test_st044_handoff_relation.py --basetemp=.pytest-st044-regression` — `27 passed`, exit code `0`.

## Files changed

- `ai-service/app/reasoning/relations.py`
- `ai-service/tests/test_st044_handoff_relation.py`
- `plans/260924-2201-260924-ai2-epic11-gap-closure/reports/developer-P1.md`

## Remaining blockers

Không có blocker trong phạm vi ST-044. Pytest vẫn phát `2 warnings` do quyền ghi `.pytest_cache`; không ảnh hưởng assertion hoặc exit code. Không tạo commit theo yêu cầu.
