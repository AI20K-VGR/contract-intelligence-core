# Research: repo hygiene rồi chuyển package

**Plan:** `plans/260926-2107-repo-hygiene-restructure`
**Date:** 2026-09-26
**Method:** câu hỏi trả lời được bằng git/grep trong repo. Không spawn researcher ngoài repo (`research-phase.md`: câu trong repo không đưa cho agent web).

## Kết luận xếp hạng

1. **Pha hygiene được làm trước và độc lập.** `apps/web` là `node_modules` đã commit. `output/` và hai JSON ở root không bị test Python/TS đọc. Gỡ khỏi index không đổi runtime.
2. **Pha chuyển package không được đi trước test khóa import.** `ai-service` đang ship bốn cây trong một wheel: `src/contract_ocr`, `src/benchmark`, `app`, `fixtures` (`ai-service/pyproject.toml` `[tool.hatch.build.targets.wheel]`). Đổi chỗ chúng là đổi build, không phải dọn file rác.
3. **README gốc sai stack.** Nó bảo backend Java/`./mvnw`. Code là `backend/src/contract_intelligence` (Python, `contract-intelligence-backend`).

## Evidence

### Vendored deps

- `git ls-files apps` (2026-09-26): 448 file `apps/web/node_modules`, 2 file `apps/web/.vite`. Không có source.
- `README.md` mục cấu trúc monorepo không có `apps/`.
- Lần grep `apps/web` trong product code không trỏ vào cây này. Các hit nằm trong tài liệu harness (`harness/plugins/hs/skills/web-frameworks/...`) như ví dụ Turborepo chung.

### Generated dumps

- `git grep` ngoài `harness/`, `plans/`, `docs/`, `node_modules`, `apps`: một hit `ai-service/scripts/benchmark_data_langfuse.py:142` — `--output-dir` mặc định `../output/reports` (nơi **ghi** báo cáo, không phải fixture đọc).
- `backend/` và `frontend/`: không có `ocr-result.json` hay `result_khoiluong.json`.
- `docs/reviews/AI2-REVIEW-2026-09-22.vi.md` trỏ mẫu ngoài repo `C:/Users/dungs/Downloads/ocr-result.json`, không phải file root của repo.

### Cache chưa ignore

- `.gitignore` có `frontend/node_modules/` và `.pytest_cache/`. Không có `node_modules/` ở root, không có `apps/`, không có `output/`, không có pattern cho `.pytest-*` đặt tên tay hay `.uv-cache-*`.
- Đĩa đang có các thư mục đó (listing phiên 2026-09-26). Chúng untracked.

### Ranh giới package hiện tại (không được bịa đường chuyển)

- AI1: `ai-service/src/contract_ocr` (98 file tracked trong prefix đó).
- AI2: `ai-service/app/` (pipeline, reasoning, api, …).
- Lab: `ai-service/ocr-benchmark/` (artifacts, data, reports) và `ai-service/frontend/` (index, ocr_raw.html, vendor). Chưa đọc hết để quyết định chuyển hay để yên — pha 2 phải kiểm tra import trước khi đụng.
- Handoff: `ai1/README.md` nói mã chạy ở `../ai-service/`, `ai1/` là schema và example.
- Backend: `backend/src/contract_intelligence`. `backend/backend/` trên đĩa chỉ thấy cache uv.
- UI sản phẩm: `frontend/` (`package.json` script `test`: `vitest run`).

### Lệnh test thật

- AI1: `ai-service/pyproject.toml` `testpaths = ["tests"]`, `pythonpath = ["."]`. README AI1 ghi `uv run pytest -q`.
- Backend: `backend/pyproject.toml` `testpaths = ["tests"]`, `pythonpath = ["src"]`.
- Frontend: `npm test` → `vitest run` trong `frontend/`.

### File đang dở, cấm xoá

Working tree `feature/ai2-integration` còn sửa chưa commit trong `ai-service/app`, `backend/src/contract_intelligence`, `frontend/src`, `docker-compose.yml`, và file mới `ai2_analysis_dtos.py`, `test_worker_render_urls.py`, `DossierAnalysisPanel.tsx`, `AnalysisCenterPage.tsx`, `citation-pane-source.test.tsx`.

## Quyết định đã khóa (từ user, không re-litigate)

- Một plan, hai pha: hygiene rồi restructure.
- Sizer `scope_split.py` ra `multi` / 1600 cells / 4 sub-plan vì trục mặc định. Đã ghi `decision: proceed` trong `artifacts/scope-sizing.json`: một git index, hai pha tuần tự, không tách bốn plan.

## Open questions

- `ai-service/frontend` và `ai-service/ocr-benchmark` có import từ runtime AI1/AI2 không. Pha 2 phải grep trước khi di chuyển. Chưa có kết luận chuyển đi đâu.
- Harness (`.cursor`, `harness/`, `AGENTS.md`) có vào commit sản phẩm không. Ngoài phạm vi hai pha này trừ khi plan nói rõ để yên.
