---
phase: 2
title: "Restructure"
status: pending
plan: 260926-2107-repo-hygiene-restructure
created: 2026-09-26
harness_version: 6.3.0
harness_kit_digest: 672de2e098c3cb8451018791788f1052b1b812ccec08a1f124191bd8bbc04ebd
harness_schema_version: 1.0
---

# Phase 2 — Restructure

## Overview

Move nhỏ nhất, giữ hành vi: sửa mục stack `README.md` cho đúng backend Python
(bỏ `./mvnw`/Java), khoá import hiện tại của 3 cây source bằng test đặc tả
(characterization), và ghi lại quyết định ĐÃ KIỂM là để yên `ai-service/frontend`
+ `ai-service/ocr-benchmark`. KHÔNG relocate cây source nào — research chưa chứng
minh move an toàn (`research/repo-layout-evidence.md:44-48,56-58`). Phụ thuộc Phase 1.

## Requirements

Functional:
- `README.md` mục cấu trúc/stack: `backend/` mô tả Python (FastAPI + Celery worker,
  Clean Architecture/DDD), KHÔNG còn "Java Spring Boot" (`README.md:11`), "Java 17,
  Spring Boot 3.x" (`README.md:22`), và lệnh `cd backend && ./mvnw spring-boot:run`
  (`README.md:63`) đổi sang lệnh Python thật (vd `uv run ...` / `pytest`).
- Import hiện tại còn resolve, được khoá bằng test:
  `ai-service/src/contract_ocr` (98 file, `research/...:35`), `ai-service/app`
  (`research/...:36`), `backend/src/contract_intelligence`
  (`backend/pyproject.toml:156` pythonpath=src).
- Ghi bản quyết định: `ai-service/frontend` + `ai-service/ocr-benchmark` để yên,
  kèm bằng chứng grep import (không có import runtime chéo → không cần move).

Non-functional:
- KHÔNG đụng logic runtime; chỉ README (doc) + test mới.
- KHÔNG sửa `.gitignore` (P1 sở hữu file đó) — `backend/backend/` đã được P1 ignore;
  P2 chỉ GUARD bằng `git check-ignore` trong test.

## Related Code Files

- **Modify:** `README.md` — chỉ mục cấu trúc monorepo + bảng vai trò + block "Bắt
  đầu nhanh" (dòng ~11, 22, 63). KHÔNG đụng phần khác của docs.
- **Create:** `ai-service/tests/test_import_lock.py` — chỉ `import contract_ocr`, `app`, `benchmark`, `fixtures` (wheel `ai-service/pyproject.toml:49`). Không gọi `git`. Không import `contract_intelligence`.
- **Create:** `backend/tests/unit/test_package_import_lock.py` — chỉ `import contract_intelligence` dưới `pythonpath=src`.
- **Create:** `scripts/check_readme_stack.py` — đọc `README.md` ở repo root, fail nếu mục stack còn `./mvnw` hoặc `Java Spring Boot`. Không nằm trong suite pytest của ai-service.

## File inventory (--deep)

| Path | Action | Cỡ | Test impact |
|---|---|---|---|
| `README.md` | Modify | ~6 dòng đổi (mục stack) | Doc-only; không runtime |
| `scripts/check_readme_stack.py` | Create | ~40 dòng | Gate README, ngoài pytest |
| `ai-service/tests/test_import_lock.py` | Create | ~40 dòng | Khoá 4 package wheel AI |
| `backend/tests/unit/test_package_import_lock.py` | Create | ~20 dòng | Khoá `contract_intelligence` |
| `ai-service/src/contract_ocr`, `src/benchmark`, `app`, `fixtures` | Không đổi | wheel line 49 | Import-lock |
| `backend/src/contract_intelligence` | Không đổi | pythonpath src | Import-lock ở backend |
| `ai-service/frontend`, `ai-service/ocr-benchmark` | Không đổi (ghi quyết định) | 6 + 36 file | 0 — grep xác nhận không import runtime |

## Test scenario matrix (--deep)

| Ưu tiên | Scenario | Kỳ vọng |
|---|---|---|
| Critical | `import contract_ocr` (pythonpath="." của ai-service) | resolve (lock) |
| Critical | import module chính trong `ai-service/app` | resolve (lock) |
| Critical | `import contract_intelligence` trong backend pytest | resolve |
| Critical | `scripts/check_readme_stack.py` trước khi sửa README | exit khác 0 (RED) |
| High | README backend mô tả Python/FastAPI | script exit 0 sau sửa |
| Medium | grep `import`/`from` từ `ai-service/frontend`, `ai-service/ocr-benchmark` vào `contract_ocr`/`app` | không có → an toàn để yên |

## Dependency map (--deep)

- Phụ thuộc: **Phase 1** (edge P1→P2 trong `plan-graph.yaml`). Cần P1 đã: gỡ index
  sạch + `.gitignore` có `backend/backend/` (scenario High của P2 giả định pattern
  đã tồn tại). Chạy P2 trước P1 → `git check-ignore backend/backend` fail.
- File dùng chung: không. P1 sở hữu `.gitignore` và `scripts/check_repo_hygiene.py`. P2 sở hữu `README.md`, `scripts/check_readme_stack.py`, và hai file test import-lock. Suite pytest không gọi git (RT-02, RT-03).

## TDD

### Tests Before (RED — viết trước khi sửa)
- [ ] `python scripts/check_readme_stack.py` → **FAIL** hôm nay (README:11,22,63 còn Java/`./mvnw`).
- [ ] `ai-service/tests/test_import_lock.py` import `contract_ocr`, `app`, `benchmark`, `fixtures` → **PASS** (khoá regression). Không import backend.
- [ ] `backend/tests/unit/test_package_import_lock.py` import `contract_intelligence` → **PASS**.
- Chạy README script trước khi sửa file. Import-lock viết trước mọi move.

### Implement
1. Grep import cross-tree: `git grep -n "contract_ocr\|from app" -- ai-service/frontend ai-service/ocr-benchmark`. Ghi kết quả vào docstring test + phần "Quyết định đã kiểm" dưới. Nếu CÓ import runtime chéo bất ngờ → DỪNG (move bị cấm đợt này), báo lại.
2. Sửa mục stack `README.md`: dòng 11 (`backend/` → Python FastAPI), bảng dòng 22 (bỏ Java 17/Spring, ghi Python 3.x / FastAPI / Celery / PostgreSQL), block "Bắt đầu nhanh" dòng 63 (bỏ `./mvnw`, thay lệnh Python thật vd `uv run` / `pytest`). KHÔNG đụng phần docs khác.
3. Viết ba file ở Related Code. Nếu grep bước 1 không thấy import chéo, không relocate. Nếu thấy một move nhỏ mà test import-lock sẽ đỏ khi gãy, ghi move đó vào phase rồi mới chuyển. Không nhét assert git vào pytest.

### Tests After (hành vi mới)
- [ ] `python scripts/check_readme_stack.py` → exit 0.
- [ ] Hai import-lock test giữ PASS.

### Regression Gate (lệnh thật)
- `python scripts/check_readme_stack.py` — MUST PASS.
- `cd ai-service; uv run pytest -q tests/test_import_lock.py` — MUST PASS.
- `cd backend; python -m pytest -q tests/unit/test_package_import_lock.py` — MUST PASS.
- `cd frontend; npm test` — N/A nếu P2 không sửa `frontend/src`.

## Quyết định đã kiểm (điền khi Implement bước 1)

- `ai-service/frontend` (6 file) + `ai-service/ocr-benchmark` (36 file): để yên.
  Bằng chứng: kết quả `git grep` bước 1 (dán vào docstring test). Lý do: không có
  import runtime từ AI1/AI2 vào 2 cây này → không có move nào an toàn được chứng
  minh, và move chưa chứng minh bị cấm đợt này (`plan.md` QĐ #3).

## Success Criteria

- [ ] README mục stack không còn `mvnw`/Java Spring Boot; mô tả Python/FastAPI (đo bằng test token).
- [ ] Import-lock xanh: AI (`contract_ocr`, `app`, `benchmark`, `fixtures`) và backend (`contract_intelligence`) ở đúng suite.
- [ ] Bản ghi grep: để yên `ai-service/frontend` và `ai-service/ocr-benchmark` nếu không có import chéo.
- [ ] Ba lệnh regression gate ở trên exit 0. Suite pytest không gọi git.

## Risk Assessment

| Risk | Khả năng × Tác động | Mitigation |
|---|---|---|
| Grep phát hiện import chéo bất ngờ | thấp × cao | Bước Implement #1 DỪNG và báo; không tự move (move bị cấm). |
| Test tìm sai repo-root trên Windows | trung bình × trung bình | Dùng `git rev-parse --show-toplevel`; fallback đi lên từ `__file__` [ASSUMED] — kiểm khi chạy thật. |
| Sửa README lan sang phần docs khác | thấp × trung bình | Chỉ đụng 3 vùng dòng 11/22/63; diff review nhỏ. |
| P2 chạy khi P1 chưa xong | thấp × trung bình | Edge P1→P2 trong `plan-graph.yaml`; `test_backend_backend_ignored` đỏ sẽ chặn. |
