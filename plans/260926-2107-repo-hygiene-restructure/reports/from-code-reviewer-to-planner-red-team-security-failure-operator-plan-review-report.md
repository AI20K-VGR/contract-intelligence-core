# Red-team plan review — repo-hygiene-restructure

**Plan:** `plans/260926-2107-repo-hygiene-restructure`
**Reviewer:** red-teamer (adversarial, advisory — KHÔNG sửa plan)
**Ngày:** 2026-09-26
**Personas:** Failure Mode Analyst · Bad-day Operator · Maintainer-6-months-later · Security/Boundary
**Verdict 1 dòng:** Plan hygiene (P1) vững, nhưng P2 có **3 lỗi HIGH proven-by-config** khiến chính gate "uv run pytest -q PASS 100%" không thể xanh như mô tả — sửa trước khi cook.

## Bảng findings (xếp theo severity)

| id | sev | proven/suspected | anchor | fix rẻ nhất |
|---|---|---|---|---|
| RT-01 | **H** | proven (config) | `phase-2-restructure.md:30-32` vs `ai-service/pyproject.toml:66` (`pythonpath=["."]`) + `backend/pyproject.toml:156` (`pythonpath=["src"]`) | Đặt import-lock của `contract_intelligence` trong `backend/tests` (chạy bằng backend pytest), không nhét vào suite ai-service. |
| RT-02 | **H** | proven (design) | `phase-2-restructure.md:45-49,91,104`; `phase-1-hygiene.md:41-43` | Tách assertion phụ thuộc `git` khỏi suite sản phẩm; `skip` khi không có `.git`/git binary. |
| RT-03 | **H** | proven (design/SRP) | `phase-2-restructure.md:45-49,80` (claim "Zero overlap") | Chuyển assertion repo-root (README + `.gitignore`) sang `scripts/check_repo_hygiene.py`, không để trong `ai-service/tests`. |
| RT-04 | M | proven | `plan.md:34`, `phase-2-restructure.md:20` vs `research/repo-layout-evidence.md:43-48,55-58` | Sửa citation trỏ đúng `research/...:10-12` và `:31-37`. |
| RT-05 | M | proven | `plan.md:31-36,53-58`; `phase-2-restructure.md:96,116` | Bỏ kết luận "KHÔNG move" khỏi acceptance; để grep cook-time quyết định theo đúng QĐ #3. |
| RT-06 | M | proven | `ai-service/pyproject.toml:49` vs `phase-2-restructure.md:29-31,55-57` | Thêm import-lock cho `benchmark` + `fixtures` hoặc ghi rõ vì sao loại. |
| RT-07 | M | proven | `plan.md:127` (gọi là "pattern hẹp"); `phase-1-hygiene.md:28` | Dùng `/apps/web/node_modules/` + `/apps/web/.vite/` thay cho `/apps/`. |
| RT-08 | L–M | proven (detective, không preventive) | `phase-1-hygiene.md:44-46,114` | Guard tồn-tại phải chạy TRƯỚC commit; backup 2 JSON + `output/` trước khi thao tác index. |
| RT-09 | L | proven | `phase-2-restructure.md:37-39,91,130` vs `plan.md:117` (rollback độc lập) | Ghi rõ revert phải theo thứ tự P2→P1 (P2 test phụ thuộc runtime vào `.gitignore` của P1). |

---

## Chi tiết finding

### RT-01 (H) — import-lock `contract_intelligence` sẽ LỖI trong suite ai-service
`phase-2-restructure.md:30-32` khoá `import contract_intelligence` như thể import được từ chỗ test sống. Nhưng test sống ở `ai-service/tests`, chạy bằng `uv run pytest -q` với `pythonpath=["."]` (`ai-service/pyproject.toml:66`). `contract_intelligence` là package của **backend** (`backend/pyproject.toml:156` `pythonpath=["src"]`) và **không** được khai báo là dependency của ai-service (`git grep contract_intelligence -- ai-service/pyproject.toml` = 0 hit; chỉ có `build-backend = hatchling.build` ở dòng 3, không liên quan). → collection-time `ImportError`, gate P2 không bao giờ xanh trừ khi hack `sys.path` (không được mô tả). **Fix:** khoá import backend trong `backend/tests`; ai-service test chỉ khoá `contract_ocr`/`app`.

### RT-02 (H) — gate sản phẩm phụ thuộc git binary + `.git`
`phase-2-restructure.md:104` đặt `uv run pytest -q` (100% PASS) làm regression gate, mà `test_repo_layout.py` gọi `git rev-parse --show-toplevel`, `git check-ignore`, `git grep` (`:45-49,91`). `phase-1-hygiene.md:41-43` cũng shell ra `git`. Trong Docker/CI copy source **không có `.git`** hoặc image không có git binary → cả suite đỏ vì lý do không liên quan logic. Reachability thật: build image ai-service thường `COPY` source không kèm `.git`. **Fix:** tách các assertion git ra gate riêng hoặc `pytest.skip` khi `git rev-parse` fail.

### RT-03 (H) — test đặt sai nhà (SRP/naming) + phá claim "Zero overlap"
`ai-service/tests/test_repo_layout.py` sống trong ai-service nhưng assert README **root** và `.gitignore` **root** (kết quả P1). Coupling chéo 3 lớp: (1) git hiện diện, (2) nội dung README root, (3) pattern `backend/backend/` do P1 thêm. Maintainer chỉ chạy ai-service tests sẽ đỏ vì thứ không thuộc ai-service — mâu thuẫn trực tiếp claim "Zero overlap … P1 owns .gitignore fully" (`phase-2-restructure.md:80`). Tên `test_repo_layout` trong service con che giấu trách nhiệm repo-level. **Fix:** đưa assertion repo-level vào `scripts/check_repo_hygiene.py`.

### RT-04 (M) — anchor trung tâm KHÔNG chứng minh điều plan nói
Lý do gốc để từ chối move — "research chưa chứng minh move an toàn" — viện dẫn `research/repo-layout-evidence.md:44-48` và `:56-58`. Đã đọc: `:43-48` là mục **"Lệnh test thật"** + đầu **"File đang dở"**; `:55-58` là **"Open questions"**/locked decisions. **Không dòng nào** nói về an toàn move. Anchor đúng nằm ở `research:10-12` (kết luận "chuyển package không được đi trước test") và `research:31-37` ("Chưa đọc hết để quyết định chuyển hay để yên"). Gate đứng trên citation sai. **Fix:** sửa citation.

### RT-05 (M) — known tension: refusal HỢP LỆ nhưng plan front-run evidence gate
**Phán quyết:** việc plan giao 0 move source (dù title "chuyển package" + feature `package-layout-moves-keep-runtime-behavior` hứa move) **KHÔNG phải vi phạm decision đã khoá**. QĐ #3 (`plan.md:53-58`) tự nói rõ: "Để yên … là **hợp lệ** nếu ghi lại đó là quyết định đã kiểm." Đây là refusal có căn cứ, không phải scope-cut lén.
**NHƯNG** đây vẫn là finding: plan **tiền-quyết** "chưa — nên KHÔNG tách" / "không move" và nhét vào acceptance (`plan.md:36`, `phase-2-restructure.md:116`) **TRƯỚC** khi chạy grep mà chính QĐ #3 coi là cổng thật ("grep import trước, chỉ cho phép move có test sẽ fail nếu import gãy"). Plan front-run kết quả grep của chính nó — nếu cook-time grep cho thấy một move nhỏ an toàn, acceptance "không move" sẽ đá nhau với QĐ #3. **Fix:** acceptance chỉ khoá "mọi move phải có import-lock test", để grep cook-time quyết định move/không.

### RT-06 (M) — import-lock chỉ phủ 2/4 package wheel ship
Wheel ai-service ship 4 package: `packages = ["src/contract_ocr", "src/benchmark", "app", "fixtures"]` (`ai-service/pyproject.toml:49`; khớp `research:11`). Import-lock chỉ khoá `contract_ocr` + `app` (`phase-2-restructure.md:29-31,55-57`), bỏ `benchmark` + `fixtures`. Move tương lai đụng 2 cái bị bỏ → test không bắt, "khoá layout" thủng. **Fix:** thêm import-lock cho `benchmark`/`fixtures`.

### RT-07 (M) — `/apps/` là ignore-cả-cây, plan gọi nhầm là "hẹp"
`.gitignore` dự định thêm `/apps/` (`phase-1-hygiene.md:28`) ignore TOÀN BỘ cây `apps/`, không chỉ `node_modules`/`.vite`. `plan.md:127` gọi đây là "pattern hẹp" — sai sự thật. Đã kiểm: `apps/web` trên đĩa **không có** `src`/`package.json` (chỉ `.vite` + `node_modules`) nên hôm nay vô hại; nhưng bất kỳ app thật thêm vào `apps/` sau này sẽ bị chôn thầm lặng (react/vite deps trong node_modules gợi ý đây từng định là app thật). **Fix:** `/apps/web/node_modules/` + `/apps/web/.vite/`.

### RT-08 (L–M) — guard chống `-f` là detective, không preventive → path bất khả hồi
`phase-1-hygiene.md:114` chống `git rm --cached -f` lỡ xoá đĩa bằng cách script **assert tồn tại SAU** thao tác. Nếu `-f` lỡ lọt, file đã mất trước khi script báo đỏ. `node_modules` tái tạo được (`npm i`), nhưng `output/ocr/744287578/...` (dossier_result.json, demo_report.html) + root `ocr-result.json`/`result_khoiluong.json` là artifact sinh một lần, không rebuild → **bất khả hồi**. **Fix:** assert tồn-tại TRƯỚC commit; backup 2 JSON + `output/` trước khi đụng index.

### RT-09 (L) — P2 test assert kết quả P1, chỏi với rollback độc lập
`test_backend_backend_ignored` (`phase-2-restructure.md:91`) assert pattern do P1 thêm. Rollback (`plan.md:117`) cho revert từng phase độc lập; revert P1 mà giữ P2 → suite ai-service đỏ. Chỏi claim "P2 không đụng .gitignore". **Fix:** ghi rõ revert theo thứ tự P2→P1.

---

## Irreversible / data-loss paths (xếp trên path hồi được)

1. **RT-08 — mất artifact sinh-một-lần nếu `-f` lỡ lọt.** `output/ocr/744287578/ai2-run/...` + root `ocr-result.json`/`result_khoiluong.json` không rebuild được. Guard hiện tại chỉ phát hiện sau khi mất. Ưu tiên cao hơn mọi finding cosmetic.
2. **`git rm --cached` (không `-f`) — KHÔNG mất dữ liệu** (đúng như plan mô tả `plan.md:114`): file ở lại đĩa + lịch sử. Xác nhận thiết kế rollback P1 an toàn (`git add` lại là track lại). Không phải blocker.

## Residual risks (chấp nhận + điều kiện)

- **`output/` demo data (15 file) rời index** — an toàn: đã kiểm `git grep output/ocr` trong `ai-service/backend/frontend` = 0 hit đọc; chỉ 1 writer `benchmark_data_langfuse.py:142` ghi `output/reports`. Test đọc `ocr-run-*.json` là từ `DOWNLOADS` (path tuyệt đối ngoài repo), KHÔNG từ `output/`. Điều kiện chấp nhận: giữ file trên đĩa + lịch sử.
- **Root JSON không bị code tham chiếu** — `git grep ocr-result.json|result_khoiluong.json` (trừ harness/plans/docs) = 0 hit. Claim plan `plan.md:122` đứng vững.
- **`backend/backend/` chỉ có `.uv-cache-integration`** (0 file tracked) — ignore an toàn, không chôn source.
- **Test đọc `C:/Users/dungs/Downloads/...` (path tuyệt đối máy tác giả)** — fragility có sẵn, NGOÀI scope plan này; không tính là blocker nhưng nên backlog.
- **Câu hỏi harness vào commit sản phẩm** — plan tự đánh dấu ngoài scope (`plan.md:131`); chấp nhận.

---

**Đường dẫn report:** `plans/260926-2107-repo-hygiene-restructure/reports/from-code-reviewer-to-planner-red-team-security-failure-operator-plan-review-report.md`
**Severity cao nhất:** **HIGH** (RT-01, RT-02, RT-03)
