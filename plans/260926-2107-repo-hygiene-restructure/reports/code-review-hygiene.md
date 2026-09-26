# Code review — repo-hygiene-restructure (cook commits)

- **Ngày:** 2026-09-26
- **Reviewer:** code-reviewer (Staff Engineer, độc lập; không sửa code, không commit)
- **Commit review:**
  - `b9ec2c7` chore(repo): stop tracking generated artifacts
  - `4205154` docs(repo): describe the backend as Python
- **Hợp đồng plan:** `plans/260926-2107-repo-hygiene-restructure/plan.md` + `phases/phase-1-hygiene.md` + `phases/phase-2-restructure.md`

## Scope

- File review (không xét 467 blob `node_modules` đã xoá khỏi index):
  - `scripts/check_repo_hygiene.py`
  - `scripts/check_readme_stack.py`
  - `.gitignore` — khối "Repo hygiene (P1)" (`.gitignore:102-113`)
  - `README.md` — mục cấu trúc/stack/quick-start
  - `ai-service/tests/test_import_lock.py`
  - `backend/tests/unit/test_package_import_lock.py`
- Trọng tâm: 5 kiểm tra user chỉ định + đọc kỹ correctness/an toàn.

## Kết quả 5 kiểm tra bắt buộc

| # | Kiểm tra | Kết quả | Bằng chứng |
|---|---|---|---|
| 1 | `git rm` là `--cached` (file còn trên đĩa) | ✅ PASS | `git show b9ec2c7 --diff-filter=D` liệt kê `ocr-result.json`, `result_khoiluong.json`, 15 file `output/**` là **D** (rời index); `Test-Path` cho cả 5 path (`ocr-result.json`, `result_khoiluong.json`, `output`, `apps/web/node_modules`, `apps/web/.vite`) đều trả `True`. Working tree không mất file. |
| 2 | `.gitignore` KHÔNG dùng rule trần `/apps/` | ✅ PASS | `.gitignore:104-105` dùng `/apps/web/node_modules/` và `/apps/web/.vite/` — hẹp. Không có dòng `/apps/`. `git check-ignore apps/web/src/main.tsx` → exit 1 (không ignore). `frontend/src/App.tsx` và `frontend/src/data` → exit 1 (source không bị chặn). |
| 3 | Test pytest KHÔNG gọi `git` | ✅ PASS | `ai-service/tests/test_import_lock.py` và `backend/tests/unit/test_package_import_lock.py` chỉ có `import ...`; chữ "git" chỉ xuất hiện trong docstring (`test_import_lock.py:6,10`), không có `subprocess`/`import git`/lệnh git runtime. |
| 4 | Import backend KHÔNG nằm trong suite ai-service | ✅ PASS | `contract_intelligence` chỉ được import ở `backend/tests/unit/test_package_import_lock.py:10`. Suite ai-service (`ai-service/tests/test_import_lock.py:24-27`) chỉ import `contract_ocr`, `app`, `benchmark`, `fixtures` — khớp `ai-service/pyproject.toml:49` `packages = ["src/contract_ocr", "src/benchmark", "app", "fixtures"]`. Không import chéo. |
| 5 | README KHÔNG claim Java **hoặc Celery** | ❌ FAIL (Celery) | Java: PASS — `git show 4205154 -- README.md` đổi hết `Java Spring Boot`→`Python FastAPI` (`README.md:11`), `Java 17, Spring Boot 3.x`→`Python 3.11+, FastAPI, Kafka worker` (`README.md:22`), `./mvnw spring-boot:run`→`uv run python -m contract_intelligence.worker` (`README.md:63`). Không còn token `Java`/`mvnw`/`Spring`. **Celery: FAIL** — `README.md:24` vẫn ghi ai-service là `Python (FastAPI / Celery worker)`, trong khi `Select-String celery` trên `backend/pyproject.toml` + `ai-service/pyproject.toml` = **0 match**; worker thật là `aiokafka` (`backend/pyproject.toml:32`, `ai-service/pyproject.toml:41-42`). |

## Đánh giá tổng thể

Phần hygiene (P1) và phần khoá import + gỡ Java (P2) làm đúng, sạch, khớp hợp đồng plan: gỡ index bằng `--cached` không mất file, `.gitignore` hẹp không chặn nhầm source, script guard cross-platform skip an toàn khi thiếu `.git`, import-lock đặt đúng suite và không gọi git. Có **một defect thực**: claim "Celery" trong README không được dependency nào chống lưng và vi phạm tiêu chí user đặt ra ("README does not claim ... Celery"). Kèm theo là docstring của chính file guard mới cũng khẳng định sai về Celery.

## Findings theo severity

### BLOCKING — vi phạm tiêu chí acceptance user chỉ định

**[B1] `README.md:24` vẫn claim "Celery worker" — không có dependency Celery ở đâu cả**
- Bằng chứng: `README.md:24` → `| ai-service/ | ... | Python (FastAPI / Celery worker) |`. `Select-String -Pattern celery` trên cả `backend/pyproject.toml` và `ai-service/pyproject.toml` trả 0 dòng. Async/worker stack thật là Kafka: `backend/pyproject.toml:32 aiokafka>=0.14.0`, `ai-service/pyproject.toml:41-42` extra `kafka = ["aiokafka>=0.14.0"]`.
- Tác động: sai lệch tech-stack trong tài liệu onboarding; vi phạm trực tiếp kiểm tra "README does not claim ... Celery". Commit `4205154` sửa hàng `backend/` (Java→Python + Kafka) nhưng bỏ sót hàng `ai-service/` — dòng Celery là claim cũ chưa được đụng tới.
- Đề xuất fix: đổi `README.md:24` `Celery worker` → mô tả đúng (vd `Python 3.11+, FastAPI, Kafka worker`) khớp `aiokafka`. Nếu Celery thực sự là kế hoạch tương lai, phải nói rõ "dự kiến, chưa có trong deps" — nhưng cột hiện gộp lẫn với công nghệ đang dùng nên dễ hiểu nhầm.

### High

**[H1] Docstring của guard mới khẳng định sai backend dùng Celery**
- Bằng chứng: `scripts/check_readme_stack.py:5-6` → "The backend is Python (FastAPI + Celery worker, per `backend/pyproject.toml` dependencies)". `backend/pyproject.toml` KHÔNG có celery; có `aiokafka` (`:32`). Đây là comment "nghe xuôi tai nhưng sai sự thật" ngay trong file vừa tạo — đúng loại rủi ro AI-assisted.
- Tác động: guard này là nơi định nghĩa "stack đúng"; docstring sai làm reviewer/maintainer sau tin nhầm và không bao giờ thấy claim Celery bị bắt (xem H2).
- Đề xuất fix: sửa docstring nói backend là FastAPI + Kafka (`aiokafka`) worker.

**[H2] `STALE_TOKENS` không phủ "Celery" nên guard không bao giờ bắt được B1**
- Bằng chứng: `scripts/check_readme_stack.py:22` → `STALE_TOKENS = ["./mvnw", "Java Spring Boot", "Java 17"]`. Guard chỉ chặn token Java/mvnw; claim Celery lọt qua. `python scripts/check_readme_stack.py` sẽ báo PASS dù README còn sai.
- Tác động: gate README cho cảm giác an toàn giả; regression Celery không bị chặn.
- Lưu ý phạm vi: plan P2 acceptance chỉ khoá Java/mvnw (`plan.md:108`, `phase-2-restructure.md:25-28`), nên đây là gap giữa "điều plan enforce" và "điều user check". Vì user đưa Celery vào tiêu chí, đề xuất thêm `"Celery"` (hoặc regex worker) vào token nếu ai-service không dùng Celery.

### Medium

**[M1] Guard README kiểm token trên toàn file, không giới hạn mục stack**
- Bằng chứng: `scripts/check_readme_stack.py:44-45` đọc cả `README.md` rồi `token in text`. Docstring (`:6-8`) nói chỉ nhắm "mục cấu trúc / role table / quick-start". Nếu sau này có đoạn hợp lệ nhắc "Java 17" (vd so sánh lịch sử, ADR link) sẽ false-positive.
- Tác động: thấp hiện tại (README chưa có), nhưng guard rộng hơn mô tả của chính nó.
- Đề xuất: chấp nhận được cho hiện trạng; nếu muốn chính xác, giới hạn vùng quét theo heading.

### Low

**[L1] `check_repo_hygiene.py` — negative check phụ thuộc path tồn tại**
- Bằng chứng: `scripts/check_repo_hygiene.py:98-106` fail nếu KHÔNG có `frontend/src/App.tsx` hoặc `frontend/src/data` trên đĩa. Hợp lý (cần ít nhất 1 source path để test âm tính), nhưng gắn cứng path frontend; nếu layout đổi, guard đỏ vì lý do không liên quan hygiene.
- Tác động: rất thấp; cả 2 path hiện tồn tại.

## Complexity lens (báo riêng, KHÔNG block)

- `scripts/check_readme_stack.py` và `scripts/check_repo_hygiene.py` là stdlib thuần + gọi `git` qua `subprocess`, không kéo dependency mới — đúng bậc thấp của thang tối giản (Standard library). Không có over-engineering. Import-lock test tối giản đúng mức (chỉ `import` + assert not None). Không có đề xuất giảm phức tạp nào đáng làm.

## Positive observations (chỉ phần calibrate rủi ro)

- `git rm --cached` xác nhận không mất file: đúng như QĐ #2 và Rollback trong plan; commit hygiene tách riêng khỏi logic (469 file, toàn bộ là xoá-tracking + 2 script + `.gitignore`).
- `.gitignore:104-105` hẹp đúng như Risk "`.gitignore` chặn nhầm source" đã mitigate; `git check-ignore` âm tính cho `frontend/src/*` xác nhận.
- Guard skip exit 0 khi thiếu `git`/`.git` (`check_repo_hygiene.py:44-55`) — không làm vỡ CosI image không có `.git` (RT-02).
- Import-lock đặt đúng suite theo RT-01/RT-03; suite pytest không gọi git.

## Trạng thái plan TODO (không sửa plan)

- P1 acceptance (`phase-1-hygiene.md:104-111`): ✅ đạt — ls-files rỗng cho 5 nhóm, check-ignore dương/âm đúng, 5 path còn trên đĩa.
- P2 acceptance (`phase-2-restructure.md:109-114`): ⚠️ đạt một phần — Java/mvnw đã gỡ, import-lock xanh về cấu trúc, nhưng claim Celery còn sót (B1) khiến tiêu chí user "no Celery" chưa đạt. Đề nghị lead xử B1 trước khi đánh dấu P2 done.

## Metrics

- File review: 6 (không tính 467 blob node_modules).
- Lint/type: không chạy (review-only, không sửa); script là stdlib + subprocess git, không có import lạ.
- Git checks chạy thật: `ls-files` (rỗng ×5 nhóm), `check-ignore` (dương ×9 / âm ×3), `diff-filter=D`, `Test-Path` (×5), `Select-String celery` (0 match).

## Unresolved questions

- Celery có phải kế hoạch tương lai cho ai-service không, hay hoàn toàn là claim cũ sai? Nếu tương lai, README nên tách rõ "đang dùng" vs "dự kiến"; nếu không, xoá hẳn.

---

**VERDICT: BLOCKED**

- BLOCKING: B1 — `README.md:24` còn claim "Celery worker" không có dependency chống lưng, vi phạm kiểm tra "README does not claim ... Celery".
- High: H1 (docstring guard sai Celery), H2 (`STALE_TOKENS` không phủ Celery nên guard bỏ lọt).
- Medium: M1 (guard quét toàn file). Low: L1 (negative-check gắn cứng path frontend).
- 4/5 kiểm tra user PASS sạch; chỉ nhánh Celery của kiểm tra #5 fail.
