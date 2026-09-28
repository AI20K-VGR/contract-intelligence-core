# Developer P2 report

## Phạm vi

- Đã đọc `plans/260924-2116-260924-ai2-epic11-completion/phases/phase-3-facts-findings.md` và test hiện có.
- Chỉ thêm regression tests vào `ai-service/tests/test_st045_facts_findings.py`.
- Không sửa app code, không commit.

## Regression coverage

- Fact giữ `raw_value`, `normalized_value`, `subject`, `citation` và provenance qua `FactExtractor`.
- Body/annex khác document không được pair nếu thiếu `BODY_ANNEX_RELATION`.
- Relation pair hợp lệ cho phép tạo finding nhưng không tạo legal winner.
- Tái sử dụng `fixtures.envelope` và `fixtures.PROFILE`.

## Verification

Command:

```text
cd ai-service
$env:PYTHONPATH=(Get-Location).Path
.\.venv\Scripts\python.exe -m pytest -q tests/test_st045_facts_findings.py --basetemp=.pytest-p2-target8
```

Result: `3 passed`.

Environment warning: pytest báo `PytestCacheWarning` vì không ghi được `.pytest_cache`; không ảnh hưởng kết quả test.
