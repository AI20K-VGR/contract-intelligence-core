# Discovery Brief — Dọn cây repo rồi mới cấu trúc lại, không đổi logic

**Date:** 2026-09-26
**Status:** draft

---

## 1. Problem framing

Working tree `feature/ai2-integration` trộn code sản phẩm với cache test, `node_modules` đã commit, artifact OCR và cài harness. README gốc vẫn mô tả backend Java trong khi code là Python. Người dùng muốn rà mọi thư mục, tìm thứ nên giữ và nên bỏ, rồi cấu trúc lại toàn bộ mà không mất logic.

**Root cause (if known):** `.gitignore` chỉ chặn `frontend/node_modules/` và `.pytest_cache/`, không chặn `apps/web/node_modules`, `output/`, basetemp pytest đặt tên tay, hay `node_modules` ở root.
**Current impact:** `git ls-files` đếm 448 file tracked dưới `apps/web/node_modules` và 15 file tracked dưới `output/`. Cây đĩa còn hàng chục thư mục `.pytest-*` và `.uv-cache-*` chưa commit.
**Deadline / urgency:** Không có hạn. Chuyển thư mục source trước khi có test giữ hành vi là rủi ro mất logic.

---

## 2. Hard constraints

| Constraint | Type | Notes |
|---|---|---|
| Không mất logic nghiệp vụ | policy | Người dùng nói rõ. Đổi chỗ file source chỉ sau plan và test giữ hành vi. |
| Working tree hiện tại | scope | Không bỏ file chưa commit một cách mù. Phân loại rồi mới xoá. |
| Cấu trúc lại toàn bộ | scope | Người dùng chọn full-restructure, kèm plan trước khi sửa. |
| Không commit hợp đồng / scan | policy | `README.md` và `.gitignore`: cấm pdf/docx/ảnh ngoài `docs/assets/`. |

---

## 3. Evidence summary

**Research report:** [SKIPPED] — quan sát local `git ls-files` và listing đĩa, không có báo cáo web.

Key findings:

- Tracked theo top-level: `ai-service` 496, `apps` 450 (448 là `node_modules`), `backend` 302, `frontend` 122, `evals` 80, `docs` 77, `ai1` 10, `output` 15.
- `apps/web` không có source: 448 `node_modules` + 2 file `.vite`.
- `ai1/README.md` nói mã chạy nằm ở `ai-service/`; `ai1/` là gói bàn giao schema và example.
- `ai-service` có hai cây code tracked: `src/` (112, AI1 `contract_ocr`) và `app/` (82, AI2).
- `README.md` dòng 11–25 mô tả backend Java/Spring và `./mvnw`. Cây thật là `backend/src/contract_intelligence` (Python).
- File sản phẩm chưa commit cần giữ: sửa trong `backend/src`, `ai-service/app`, `frontend/src`, `docker-compose.yml`, cộng file mới `ai2_analysis_dtos.py`, `test_worker_render_urls.py`, `DossierAnalysisPanel.tsx`, `AnalysisCenterPage.tsx`, `citation-pane-source.test.tsx`.
- Chưa chạy test suite trong phiên này. Chưa có danh sách lỗi logic.

---

## 4. Option space

| # | Approach | Pros | Cons | Complexity |
|---|---|---|---|---|
| A | Xoá và chuyển mọi thư mục trong một lượt | Khớp câu "cấu trúc lại toàn bộ ngay" | Dễ mất logic; trộn cache với source | high |
| B | Hai pha: gỡ artifact đã commit và gitignore cache, rồi plan riêng cho việc chuyển package | Logic source không bị đụng ở pha 1 | Cây thư mục source chưa "đẹp" ngay | medium |
| C | Chỉ sửa README và gitignore, để `apps/web/node_modules` trong git | Diff nhỏ | 448 file phụ thuộc vẫn nằm trong lịch sử và clone | low |

---

## 5. Chosen direction + rationale

**Chosen direction:** Option B — dọn artifact và cache trước, chuyển package source ở plan sau.

**Why:**
1. `apps/web/node_modules` và `output/` không phải logic. Gỡ khỏi index không đổi hành vi runtime.
2. `backend/src`, `frontend/src`, `ai-service/src`, `ai-service/app` là logic. Chuyển chúng khi chưa có test giữ hành vi vi phạm ràng buộc "không mất logic".
3. File chưa commit phía trên là việc AI2 đang dở. Không xoá.

**Accepted trade-off:**
- Cây source tạm thời vẫn là monorepo bốn bề (`backend`, `frontend`, `ai-service`, `ai1`, `evals`) cho đến plan pha 2.

**DEC recorded:** none — chưa phải quyết định kiến trúc đã đóng.

---

## 6. Open questions

- [ ] `ai-service/frontend` (6 file) và `ai-service/ocr-benchmark` (36 file) là lab hay runtime? Chưa đọc. Không chuyển trong pha 1.
- [ ] `evals/` (80 file) có phải cổng CI đang chạy không? Giữ nguyên đến khi plan đọc workflow.
- [ ] Harness (`.cursor`, `.codex`, `.claude`, `.harness`, `harness/`, `AGENTS.md`, `CLAUDE.md`) là công cụ local. Có commit vào repo sản phẩm hay giữ untracked?
- [ ] Lỗi logic: chưa chạy pytest/frontend test. Pha sửa bug chỉ bắt đầu khi có test đỏ cụ thể.
- [ ] `output/ocr/...` và `ocr-result.json`, `result_khoiluong.json` có đang được test đọc như fixture không?

---

## 7. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Xoá nhầm file AI2 chưa commit | medium | mất việc đang dở | Pha 1 không đụng các path liệt kê ở mục "giữ" |
| `output/` hoặc JSON root là fixture của test | medium | test đỏ sau khi gỡ | Grep reference trước `git rm` |
| `git rm` `apps/web/node_modules` làm diff khổng lồ | high | review khó | Một commit riêng, không trộn với sửa logic |
| Chuyển package AI1/AI2 trước test | high | mất logic | Cấm trong pha 1 |

---

## 8. Explicitly OUT of scope

- Không chuyển/đổi tên package `backend/src`, `frontend/src`, `ai-service/src`, `ai-service/app` trong pha này.
- Không sửa hành vi OCR, extraction, citation, dossier.
- Không xoá `plans/`, `docs/`, `keycloak/`, `evals/` cho đến khi plan xác nhận.
- Không gộp nhánh `feature/code-full` vào working tree.
- Không commit hay push.

---

## Pha 1 — giữ / bỏ (chưa thực hiện)

**Giữ (logic hoặc việc đang dở):**

- Đã sửa, chưa commit: `ai-service/app/api/main.py`, `ai-service/app/tools/persist.py`, `backend/.env.example`, `backend/src/contract_intelligence/**` đang modified, `backend/tests/unit/application/test_extraction_service.py`, `docker-compose.yml`, `frontend/src/App.tsx`, `frontend/src/api/analysis.ts`, `frontend/src/api/structure.ts`, `frontend/src/components/CitationPane.tsx`, `frontend/src/components/DynamicCitationViewer.tsx`
- Mới, chưa commit: `backend/src/contract_intelligence/extraction/application/dtos/ai2_analysis_dtos.py`, `backend/tests/unit/test_worker_render_urls.py`, `frontend/src/components/DossierAnalysisPanel.tsx`, `frontend/src/pages/AnalysisCenterPage.tsx`, `frontend/tests/citation-pane-source.test.tsx`
- Source tracked: `backend/src`, `frontend/src`, `ai-service/src`, `ai-service/app`, `ai-service/tests`, `ai1/contracts`, `docs`, `keycloak`, `evals`

**Bỏ khỏi đĩa (cache, chưa commit, không phải source):**

- `node_modules/` ở root
- `tmp/`
- `.pytest_cache/`, `.ruff_cache/`
- `ai-service/.pytest-*`, `backend/.pytest-*`, `backend/.pytest_cache/`, `backend/.mypy_cache/`, `backend/.ruff_cache/`
- `.uv-cache-*`, `.tmp-corepack`, `.tmp-uv-cache`, `backend/backend/` (chỉ thấy `.uv-cache-integration`)
- `frontend/dist/` nếu chỉ là build

**Bỏ khỏi git, không xoá logic (cần grep fixture trước):**

- `apps/web/node_modules/**`, `apps/web/.vite/**`
- `output/**`
- `ocr-result.json`, `result_khoiluong.json` ở root

**Để yên cho đến khi trả lời câu hỏi mở:**

- `harness/`, `.cursor/`, `.codex/`, `.claude/`, `.harness/`, `.sdlc-tools/`, `AGENTS.md`, `CLAUDE.md`
- `plans/`, `reports/`
- `ai-service/data/`, `ai-service/artifacts/`, `ai-service/frontend/`, `ai-service/ocr-benchmark/`

---

## Handoff -> hs:plan

Tier: complex / multi-step.

`/hs:plan --hard --deep --tdd C:\Users\dungs\OneDrive\Documents\VSF\plans\20260926-repo-hygiene-restructure-discovery\discovery-brief.md`

`/clear` trước khi dán lệnh đó.
