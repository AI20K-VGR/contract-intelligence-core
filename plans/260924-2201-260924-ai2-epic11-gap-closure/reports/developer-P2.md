# Developer report — P2 / ST-045

## Kết quả

ST-045 logic hiện có trong `fact.py`, `compare.py` và `idp.py` đã đáp ứng các invariant đã duyệt. Không cần sửa application logic; bổ sung test evidence độc lập.

## TDD evidence

- RED baseline: các invariant chưa có test riêng trong phase evidence.
- GREEN: `cd ai-service; $env:PYTHONPATH=(Get-Location).Path; .\.venv\Scripts\python.exe -m pytest -q tests/test_st045_facts_findings.py --basetemp=.pytest-st045` — `3 passed`, exit code `0`.
- Coverage: fact giữ raw/normalized/subject/citation/provenance; body–annex thiếu relation bị fail-closed; relation hợp lệ tạo finding nhưng không có legal winner/model winner.

## Files changed

- `ai-service/tests/test_st045_facts_findings.py`
- Không sửa `ai-service/app/`.

## Blockers

Không còn blocker trong phạm vi ST-045. Pytest có một `PytestCacheWarning` do quyền ghi `.pytest_cache`, không ảnh hưởng assertion hoặc exit code.
