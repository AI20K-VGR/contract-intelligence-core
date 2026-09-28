# Scout report — bổ sung tài liệu AI2

Ngày: 2026-09-23  
Phạm vi: chỉ tài liệu AI2 và các tài liệu sản phẩm liên quan.

## Đã xác minh

- Mục tiêu wave hiện tại bao gồm sáu profile: `SALES`, `SUPPLY_SERVICE`, `LEASE`, `CONSTRUCTION_WORK`, `EMPLOYMENT`, `NDA`.
- Phụ lục được mô hình hóa như thành viên liên quan của cùng dossier, với các mở rộng về giá, số lượng, phạm vi kỹ thuật, tiến độ, SLA, thanh toán, nghiệm thu và sửa đổi.
- Các điểm neo triển khai hiện có nằm ở `ai-service/app/pipeline/contract_context.py`, `ai-service/app/pipeline/outline.py`, `ai-service/app/pipeline/compare.py`, `ai-service/app/reasoning/query.py`, `ai-service/app/reasoning/relations.py` và `ai-service/app/reasoning/stack.py`.
- Luồng hiện có đã có citation, safe states và các lớp suy luận L0–L3; tài liệu mới mô tả phần cần mở rộng thành bounded free-form Q&A trong một dossier.
- `ai-service/fixtures/cases/manifest.json` hiện có 65 case records. Con số 95 là corpus tham khảo do người dùng cung cấp và phải giữ trạng thái `UNVERIFIED` cho đến khi được review.

## Khoảng trống cần giữ rõ trong tài liệu

- Không tuyên bố độ chính xác nghiệp vụ trước khi có golden set được con người duyệt.
- Không suy diễn khi thiếu hoặc mâu thuẫn bằng chứng; phải trả citation, lý do và `NEEDS_REVIEW` khi phù hợp.
- Không trộn các dossier chỉ vì trùng `dossier_id`.
- Không tự động kết luận bên nào thắng hoặc điều khoản nào có ưu tiên pháp lý.

## Tài liệu đã cập nhật

- `docs/ai2/AI2-15-contract-profiles-structure-relations-and-free-form-qa.vi.md`
- `docs/ai2/README.md`
- `docs/ai2/AI2-02-extraction-engine-design.vi.md`
- `docs/ai2/AI2-06-implementation-gap.vi.md`
- `docs/ai2/AI2-07-full-pipeline.vi.md`
- `docs/DOC-02-brd.md`
- `docs/DOC-03-prd.md`

