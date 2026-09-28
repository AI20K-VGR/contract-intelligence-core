# Báo cáo kiểm thử (tester)

**Ngày:** 2026-09-28
**Phạm vi:** Chạy lại (read-only) hai bộ test được chỉ định cho backend và frontend của thay đổi HITL conflict-review-fixes. Không sửa code sản phẩm, không commit.

## Verdict: PASS

Cả 2 lệnh đều exit code `0` — mọi test đều pass.

---

## 1. Backend — `uv run pytest tests/unit/test_conflict_router.py -q`

- **Thư mục làm việc:** `C:\Users\dungs\OneDrive\Documents\VSF\backend`
- **Exit code:** `0`
- **Dòng tổng kết:** `8 passed, 3 warnings in 3.72s`

### Output đầy đủ

```
........                                                                 [100%]
============================== warnings summary ===============================
tests/unit/test_conflict_router.py::TestFindingReviewLatest::test_from_row_passes_latest_through
  tests\unit\test_conflict_router.py:152: PytestWarning: The test <Function test_from_row_passes_latest_through> is marked with '@pytest.mark.asyncio' but it is not an async function. Please remove the asyncio mark. If the test is not marked explicitly, check for global marks applied via 'pytestmark'.
    def test_from_row_passes_latest_through(self) -> None:

tests/unit/test_conflict_router.py::TestFindingReviewLatest::test_from_row_latest_none_when_review_has_no_actions
  tests\unit\test_conflict_router.py:166: PytestWarning: The test <Function test_from_row_latest_none_when_review_has_no_actions> is marked with '@pytest.mark.asyncio' but it is not an async function. Please remove the asyncio mark. If the test is not marked explicitly, check for global marks applied via 'pytestmark'.
    def test_from_row_latest_none_when_review_has_no_actions(self) -> None:

.venv\Lib\site-packages\_pytest\cacheprovider.py:469
  C:\Users\dungs\OneDrive\Documents\VSF\backend\.venv\Lib\site-packages\_pytest\cacheprovider.py:469: PytestCacheWarning: could not create cache path C:\Users\dungs\OneDrive\Documents\VSF\backend\.pytest_cache\v\cache\nodeids: [WinError 5] Access is denied: 'C:\\Users\\dungs\\OneDrive\\Documents\\VSF\\backend\\.pytest_cache\\v\\cache'
    config.cache.set("cache/nodeids", sorted(self.cached_nodeids))

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
8 passed, 3 warnings in 3.72s
```

**Ghi chú (không chặn PASS, chỉ để tham khảo):**
- 2 warning `PytestWarning`: hai test được đánh `@pytest.mark.asyncio` nhưng là hàm sync (`test_from_row_passes_latest_through`, `test_from_row_latest_none_when_review_has_no_actions` — dòng 152, 166). Không gây fail, nhưng nên gỡ marker thừa để dọn warning.
- 1 warning `PytestCacheWarning`: không tạo được cache dir do quyền OneDrive (`Access is denied`). Không ảnh hưởng kết quả test, chỉ là hạn chế môi trường OneDrive-sync trên máy này.

---

## 2. Frontend — `npx vitest run tests/conflict-anchors.test.ts tests/conflict-cite.test.ts tests/conflict-review-target.test.ts tests/review-timeline.test.ts tests/reviewer-label.test.ts`

- **Thư mục làm việc:** `C:\Users\dungs\OneDrive\Documents\VSF\frontend`
- **Exit code:** `0`
- **Dòng tổng kết:** `Test Files  5 passed (5)` / `Tests  19 passed (19)`

### Output đầy đủ

```
 RUN  v3.2.7 C:/Users/dungs/OneDrive/Documents/VSF/frontend

 ✓ tests/reviewer-label.test.ts (2 tests) 4ms
 ✓ tests/review-timeline.test.ts (1 test) 8ms
 ✓ tests/conflict-cite.test.ts (4 tests) 7ms
 ✓ tests/conflict-anchors.test.ts (9 tests) 12ms
 ✓ tests/conflict-review-target.test.ts (3 tests) 7ms

 Test Files  5 passed (5)
      Tests  19 passed (19)
   Start at  00:34:11
   Duration  1.04s (transform 385ms, setup 0ms, collect 901ms, tests 38ms, environment 1ms, prepare 1.32s)
```

---

## Tổng hợp

| # | Lệnh | Exit code | Kết quả |
|---|------|-----------|---------|
| 1 | `uv run pytest tests/unit/test_conflict_router.py -q` (backend) | 0 | 8 passed, 3 warnings |
| 2 | `npx vitest run tests/conflict-anchors.test.ts tests/conflict-cite.test.ts tests/conflict-review-target.test.ts tests/review-timeline.test.ts tests/reviewer-label.test.ts` (frontend) | 0 | 5 test files passed, 19 tests passed |

**Verdict cuối:** **PASS** — cả hai lệnh exit code 0, tổng 27 test pass (8 backend + 19 frontend), không có test fail.

## Câu hỏi/vấn đề chưa giải quyết

- Không có câu hỏi chặn. Hai warning ở mục backend (asyncio marker thừa, cache dir permission trên OneDrive) là ghi chú dọn dẹp không bắt buộc, không ảnh hưởng verdict.
