---
id: 260926-2107-repo-hygiene-restructure
title: "Dọn artifact rồi chuyển package, giữ logic"
status: completed
mode: hard
tdd: true
branch: feature/ai2-integration
created: 2026-09-26
author: user:dungskbg2004@gmail.com
decisions: []
phases:
  - phases/phase-1-hygiene.md
  - phases/phase-2-restructure.md
harness_version: 6.3.0
harness_kit_digest: 672de2e098c3cb8451018791788f1052b1b812ccec08a1f124191bd8bbc04ebd
harness_schema_version: 1.0
---

# Plan: Dọn artifact rồi chuyển package, giữ logic

> hs:cook ĐỌC file này làm hợp đồng. Mọi claim không hiển nhiên có anchor
> (`file:line` / lệnh git). Tag `[ASSUMED]` / `[PRIOR]` lên claim chưa chạy thật.
> Mode `--hard --deep --tdd`. KHÔNG `--parallel`.

## Tổng quan

Gỡ artifact đã lỡ commit ra khỏi git index (không xoá logic), gitignore các cache
local, rồi sửa README nói đúng stack và khoá import hiện tại bằng test trước khi
bàn tới chuyện chuyển package. Hai pha tuần tự: P1 hygiene → P2 restructure (P2
phụ thuộc P1).

Scope thật (đã cắt YAGNI): KHÔNG chuyển/đổi tên cây source `backend/src`,
`frontend/src`, `ai-service/src`, `ai-service/app` trong đợt này — vì research
chưa chứng minh move nào an toàn (`research/repo-layout-evidence.md:44-48`,
`:56-58`). P2 chỉ làm move nhỏ nhất: sửa README lie + guard cache `backend/backend`
+ ghi lại quyết định "để yên" có kiểm chứng. Plan MÔ TẢ việc; KHÔNG chạy `git rm`,
KHÔNG commit, KHÔNG push.

Vì sao cần: `git ls-files apps/web/node_modules` = 448 file, `output/` = 15 file,
`ocr-result.json` + `result_khoiluong.json` tracked ở root (đã đếm bằng git
2026-09-26). Chúng phình clone và diff mà không phải logic. README dòng 11/22/63
vẫn bảo backend là Java Spring + `./mvnw`, trong khi code là Python
`backend/src/contract_intelligence` (`backend/pyproject.toml:155-156`).

## Quyết định đã khoá

Từ user, KHÔNG re-litigate:

1. Một plan, hai pha tuần tự. P2 phụ thuộc P1.
2. P1 chỉ hygiene: gitignore + gỡ khỏi index (KHÔNG xoá logic) — `apps/web/node_modules`,
   `apps/web/.vite`, `output/`, root `ocr-result.json`, `result_khoiluong.json`.
   KHÔNG xoá file sản phẩm chưa commit.
3. P2 chỉ move package SAU khi test khoá import/hành vi. KHÔNG bịa layout mới tách
   `ai-service/src/contract_ocr` khỏi `ai-service/app` trừ khi research đã chứng
   minh an toàn (chưa — nên KHÔNG tách). Move nhỏ nhất: sửa README lie + cache
   `backend/backend`. Move nào chưa chứng minh thì: grep import trước, chỉ cho
   phép move có test sẽ fail nếu import gãy. Để yên `ai-service/frontend` và
   `ai-service/ocr-benchmark` là hợp lệ nếu ghi lại đó là quyết định đã kiểm.
4. KHÔNG đụng `harness/`, `.cursor/`, `.codex/`, `plans/`, `evals/`, `keycloak/`,
   `docs/` — trừ mục stack của `README.md`.
5. KHÔNG commit, KHÔNG push. Plan không tự `git rm`.

## Ràng buộc (constraint-scan)

- **Zone / ownership:** cây được đụng là `plans/**` (chính plan này), `.gitignore`,
  `README.md`, `scripts/**` (mới), `ai-service/tests/**` (mới). Vùng cấm ở QĐ #4.
- **Policy commit dữ liệu:** `.gitignore:3-14` + CONTRIBUTING chặn `*.pdf/*.docx/`
  ảnh/nén ngoài `docs/assets/`. Không thêm file dữ liệu nào.
- **File đang dở, CẤM xoá** (`research/repo-layout-evidence.md:48`): sửa chưa commit
  trong `ai-service/app`, `backend/src/contract_intelligence`, `frontend/src`,
  `docker-compose.yml`, và file mới `ai2_analysis_dtos.py`,
  `test_worker_render_urls.py`, `DossierAnalysisPanel.tsx`, `AnalysisCenterPage.tsx`,
  `citation-pane-source.test.tsx`. Gỡ index chỉ nhắm 5 path artifact ở QĐ #2.
- **Lệnh test thật của repo:** ai-service `uv run pytest -q` (`ai-service/pyproject.toml:60,66`
  testpaths=tests, pythonpath="."); backend `pytest` (`backend/pyproject.toml:155-156`
  testpaths=tests, pythonpath=src); frontend `npm test` → `vitest run`
  (`frontend/package.json:12`).

## Features

- clone-without-vendored-node-modules — clone không còn `apps/web/node_modules` và `apps/web/.vite` (gỡ khỏi index, giữ trên đĩa)
- clone-without-generated-ocr-dumps — clone không còn `output/` cùng `ocr-result.json` và `result_khoiluong.json` ở root, sau khi xác nhận không có test đọc chúng
- worktree-ignores-local-caches — `.gitignore` chặn `node_modules` ở root, `apps/`, `output/`, root JSON, basetemp pytest đặt tên tay (`.pytest-*`), cache uv (`.uv-cache-*`) và `backend/backend/`
- package-layout-moves-keep-runtime-behavior — chuyển package source chỉ sau test khóa import và hành vi hiện tại; đợt này KHÔNG move cây source, ghi lại quyết định để yên có kiểm chứng
- readme-describes-the-python-monorepo — README mô tả backend Python đang có, không còn hướng dẫn `./mvnw`

## Phases

| # | Theme | Phụ thuộc | Cỡ |
|---|---|---|---|
| 1 | Hygiene | — (gốc) | S — 1 file modify (`.gitignore`), 1 file create (script check), 5 path gỡ index |
| 2 | Restructure | P1 | S — sửa `README.md`; tạo import-lock ở đúng suite (`ai-service/tests`, `backend/tests`) và `scripts/check_readme_stack.py`. Không relocate source trong đợt này trừ khi grep cook-time chứng minh một move có test sẽ đỏ nếu import gãy. |

## Out of scope

- KHÔNG chuyển/đổi tên `backend/src`, `frontend/src`, `ai-service/src`, `ai-service/app`.
- KHÔNG sửa hành vi OCR / extraction / citation / dossier.
- KHÔNG xoá `plans/`, `docs/` (ngoài mục stack README), `keycloak/`, `evals/`, harness.
- KHÔNG xoá file sản phẩm chưa commit (danh sách ở Ràng buộc).
- KHÔNG gộp nhánh `feature/code-full`.
- KHÔNG commit, KHÔNG push, KHÔNG chạy `git rm` từ plan.

## Acceptance (toàn plan)

- [ ] Mỗi phase red→green TDD; suite liên quan xanh sau mỗi phase (lệnh thật ở Ràng buộc).
- [ ] P1: `git ls-files apps/web/node_modules` và `git ls-files output/` trả rỗng; `git ls-files ocr-result.json result_khoiluong.json` rỗng; `git ls-files apps/web/.vite` rỗng. Script check hygiene xanh.
- [ ] P1: `git check-ignore` báo ignored cho mẫu `node_modules/x`, `output/x`, `.pytest-sample/x`, `.uv-cache-x/y`, `backend/backend/x`.
- [ ] P1: 5 path gỡ index vẫn CÒN trên đĩa (gỡ `--cached`, không xoá file).
- [ ] P2: `python scripts/check_readme_stack.py` xanh — README không còn `./mvnw` / `Java Spring Boot` ở mục stack.
- [ ] P2: `uv run pytest -q tests/test_import_lock.py` trong `ai-service` khoá `contract_ocr`, `app`, `benchmark`, `fixtures`. `pytest -q tests/unit/test_package_import_lock.py` trong `backend` khoá `contract_intelligence`. Không test nào trong suite sản phẩm gọi `git`.
- [ ] P2: có bản ghi quyết định "để yên `ai-service/frontend` + `ai-service/ocr-benchmark`" kèm bằng chứng grep import.

## Rollback

- Mỗi phase commit riêng (do cook, không phải plan). Hoàn tác theo thứ tự P2 rồi P1: `git revert <sha-P2>` trước, sau đó `git revert <sha-P1>`. Revert P1 trong khi giữ test P2 không được, vì gate README không phụ thuộc `.gitignore` nhưng backup và ignore là của P1.
- Vì P1 dùng `git rm --cached` (không xoá đĩa), kể cả không revert vẫn không mất file; chỉ cần `git add` lại nếu muốn track trở lại.
- Sau mỗi revert: chạy lại regression gate của phase đó để xác nhận sạch.

## Risks

| Risk | Khả năng | Tác động | Mitigation |
|---|---|---|---|
| `output/` hoặc root JSON là fixture test | thấp | test đỏ sau khi gỡ index | Research đã grep: chỉ 1 hit `ai-service/scripts/benchmark_data_langfuse.py:142` là nơi GHI, không đọc (`research/...:17-19`). P1 grep lại trước khi gỡ; file vẫn trên đĩa nên test đọc-đĩa vẫn chạy. |
| Gỡ index `apps/web/node_modules` tạo diff khổng lồ | cao | review khó | Một commit P1 riêng, không trộn sửa logic; diff là xoá-tracking thuần. |
| Lỡ đụng file AI2 chưa commit | trung bình | mất việc đang dở | P1/P2 chỉ nhắm path liệt kê; KHÔNG `git add -A`; gỡ index theo path tường minh. |
| Move package trước khi có test | cao | mất logic | CẤM ở đợt này; P2 chỉ move sau import-lock test, và research chưa chứng minh move nào → không move. |
| `.gitignore` chặn nhầm source (vd `frontend/src/data`) | thấp | mất file app | Pattern: `/node_modules/`, `/apps/web/node_modules/`, `/apps/web/.vite/`, `/output/`, hai JSON tên đầy đủ, `.pytest-*`, `.uv-cache-*`, `backend/backend/`. Không dùng `/apps/` cả cây. Giữ ngoại lệ `.gitignore:15-16`. |

## Câu hỏi mở

- `ai-service/frontend` (6 file) và `ai-service/ocr-benchmark` (36 file) là lab hay có import runtime? P2 grep import và ghi quyết định; nếu có import chéo bất ngờ thì DỪNG, không move (đã cấm move đợt này).
- Harness (`.cursor`, `harness/`, `AGENTS.md`) có nên vào commit sản phẩm không — ngoài scope hai pha này.

## Red-team disposition

Nguồn: `reports/from-code-reviewer-to-planner-red-team-security-failure-operator-plan-review-report.md`.

| id | Quyết định | Chỗ đã sửa |
|---|---|---|
| RT-01 | Accept | Import backend chuyển sang `backend/tests/unit/test_package_import_lock.py` |
| RT-02 | Accept | Suite pytest không gọi git. Script hygiene skip exit 0 khi không có `.git` |
| RT-03 | Accept | README check nằm ở `scripts/check_readme_stack.py`, không ở suite ai-service |
| RT-04 | Accept | Citation move-safety là `research/repo-layout-evidence.md` mục kết luận và ranh giới package, không phải mục lệnh test |
| RT-05 | Accept | Acceptance không khóa "không bao giờ move". Move chỉ khi grep cook-time có test sẽ đỏ nếu import gãy |
| RT-06 | Accept | Import-lock AI gồm `benchmark` và `fixtures` |
| RT-07 | Accept | Ignore `/apps/web/node_modules/` và `/apps/web/.vite/`, không `/apps/` |
| RT-08 | Accept | Backup `tmp/hygiene-backup/` và assert tồn tại trước `git rm` |
| RT-09 | Accept | Rollback P2 rồi mới P1 |
