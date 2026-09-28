# P0 — Freeze baseline và contract fixture

## Mục tiêu

Chụp lại behavior thật của hai branch và nhánh AI2 hiện tại trước khi thêm integration seam; phân biệt contract legacy, canonical và legacy `ocr.json` demo.

## Module/file dự kiến

- Chỉ đọc: `backend/src/contract_intelligence/shared/ai/client.py`
- Chỉ đọc: `backend/src/contract_intelligence/shared/ai/schemas.py`
- Chỉ đọc: `backend/src/contract_intelligence/shared/ai/pipeline_orchestrator.py`
- Chỉ đọc: backend run/extraction routers và persistence
- Chỉ đọc: `frontend/src/api/*`, `frontend/src/pages/*`, `frontend/src/App.tsx`
- AI2: `ai-service/app/contracts/wire.py`, `ai-service/app/api/main.py`, `ai-service/app/pipeline/*`
- Thêm fixture/test plan trong vùng test phù hợp sau khi được duyệt; không sửa production behavior ở P0.

## Contract

- Legacy BE client tiếp tục gọi `/api/v1/jobs/*`.
- Canonical AI2 tiếp tục dùng `be.ai2.processing.request.v1` và `ai2.be.processing.result.v1`.
- Branch refs và commit SHA trong plan là baseline kiểm toán.

## Acceptance criteria

- Có bảng mapping field-level legacy→canonical và canonical result→BE read model.
- Có fixture tối thiểu: body-only, body+annex, nhiều annex, thiếu citation, digest mismatch, role ambiguity.
- Xác định rõ fixture nào là contract-valid và fixture nào phải ra `NEEDS_REVIEW`/`INSUFFICIENT_EVIDENCE`.

## Test cases

- Snapshot AI1 v3 hợp lệ.
- Snapshot legacy `data/meta` thiếu page citation.
- Hai snapshot cùng dossier nhưng khác digest.
- Body không có annex.
- Body có hai annex và relation map explicit.

## Verification artifact

`baseline-contract-matrix.md` và fixture manifest trong plan/eval artifact.

## Risk / rollback

Risk là hiểu nhầm branch snapshot hoặc coi mock là production contract. Rollback: xóa fixture/plan artifact mới; không có production code bị thay đổi.

## Dependency

Không có. P0 phải hoàn thành trước mọi phase code.

