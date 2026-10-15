# P1 — CI xanh và baseline consent

## Overview

Khôi phục pipeline kiểm tra có thật cho AI service, sửa các lỗi đã quan sát trong Ruff/MyPy để branch PR có tín hiệu CI đáng tin. Do lỗi MyPy nằm ngay hàm đọc consent mới-hồ-sơ, phase này cũng đặt fallback true theo quyết định sản phẩm đã duyệt, nhưng vẫn giữ giá trị metadata bool tường minh (kể cả false) thắng fallback (`backend/src/contract_intelligence/worker.py:1112-1129`).

## Requirements

- **Functional:** thay TODO workflow bằng setup, Ruff check/format, MyPy và pytest AI service; sửa lỗi E501 tại `ai_adapters.py:720,729`; sửa trả kiểu `object` ở `worker.py:1123` mà không xóa khả năng opt-out. Consent resolver fail closed nếu thiếu/null/sai kiểu; tạo hồ sơ mới phải ghi consent true tường minh theo quyết định sản phẩm đã duyệt.
- **NFR:** CI không cần provider key; tests live/LLM được loại trừ rõ, không skip âm thầm. Không log env hoặc payload hợp đồng. Workflow chạy PR/push theo convention hiện tại, có timeout và PostgreSQL service nếu integration cần.
- **TDD:** thêm test đỏ cho consent missing/null/wrong-type false, stored true/false, và hồ sơ mới explicit true trước; sửa typing/lint; chạy workflow/lệnh tương đương xanh trước khi qua phase.

## Related Code Files

**Create:** —

**Modify (ownership chỉ P1):**

- `.github/workflows/ai-service.yml`
- `backend/src/contract_intelligence/infrastructure/ai_adapters.py`
- `backend/src/contract_intelligence/worker.py`
- `backend/src/contract_intelligence/contract/application/services/contract_service.py`
- `backend/src/contract_intelligence/contract/interfaces/api/routers/contract_router.py` (Ruff format gate surfaced this existing formatting violation while validating the CI fix; formatting-only)
- `backend/tests/unit/test_worker_pipeline_run.py`
- `backend/tests/unit/application/test_contract_service.py`

**Delete:** —

## Implementation Steps

1. Viết regression test: metadata consent false, missing, null hoặc sai kiểu phải trả false; explicit true trả true; tạo dossier mới ghi explicit `ai2_content_sharing_consent=true`. Chạy test để xác nhận đỏ trước code.
2. Sửa kiểu trả về worker bằng local typed bool/cast có kiểm chứng; giữ fallback resolver fail closed. Ghi consent true vào metadata tại đúng đường tạo dossier mới; không suy ra consent từ key thiếu.
3. Sửa line length bằng wrapping/clarifying code, không tắt Ruff E501 tại module.
4. Thay `.github/workflows/ai-service.yml` TODO (`:3-24`) bằng cài `uv sync --frozen --extra dev --extra web`, `ruff check`, `ruff format --check` và deterministic pytest không gọi provider. Không thêm checker chưa có trong project. Dùng PostgreSQL service/URL khi test cần DB; không đưa credentials thật vào workflow.
5. Chạy backend `ruff check src/ tests/`, `ruff format --check src/ tests/`, `mypy src/`, unit + architecture và integration PostgreSQL; chạy AI service lint/format/type/test với command tương ứng CI; chạy PR checks. Baseline branch run `38416741068` đã qua unit/integration nhưng các lỗi Ruff/MyPy và architecture cần được chứng minh hết trên SHA mới.

## Success Criteria

- [ ] Test consent red→green; only explicit stored true permits dossier egress; explicit false, missing, null and wrong-type consent all fail closed. New dossier creation persists explicit true under the already-approved default; missing metadata never means consent.
- [ ] AI-service workflow không còn echo TODO và thất bại đúng khi lint/test lỗi.
- [ ] Cả hai Ruff E501 và MyPy `worker.py:1123` đã biến mất; architecture tests không còn thất bại turndown do Ruff.
- [ ] Backend CI và AI-service workflow đều xanh trên branch commit mới; test không đọc provider keys.
- [ ] Ghi lại tên check ổn định cho backend, frontend, AI service và `pr-guard`; P5 xác nhận tất cả là required trong ruleset `develop` trước merge.
- [ ] Ghi lại tên check ổn định cho backend, frontend, AI service và `pr-guard`; P5 xác nhận tất cả là required trong ruleset `develop` trước merge PR.

## Risk Assessment

**Trung bình × Cao:** workflow mới có thể thiếu native dependency/service DB, tạo false-negative hoặc che test bằng skip. **Mitigation:** chạy lệnh trên runner Linux thật; chia unit và PostgreSQL integration rõ; không dựa vào setup của developer; test offline không dùng key.

**Thấp × Cao:** ghi consent true khi tạo dossier mới cho phép gửi nội dung ra provider. **Mitigation:** đây là quyết định đã được chủ sản phẩm phê duyệt trước; chỉ lưu true tường minh khi tạo mới, consent thiếu vẫn fail closed, và opt-out/audit UI được thêm ở P3.

**Rollback:** revert workflow/typing change nếu CI infrastructure regress; không đảo consent default mà không ghi explicit product config/decision.
