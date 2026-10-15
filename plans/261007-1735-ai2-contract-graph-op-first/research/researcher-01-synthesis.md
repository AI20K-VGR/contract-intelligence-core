# Research synthesis — AI2 contract graph, luồng 1 (operation-first)

Tổng hợp nghiên cứu đã làm trong phiên 2026-10-07. File này chỉ trỏ tới các báo cáo gốc, không làm lại nghiên cứu.
Nhãn: **OBSERVED** = đã chạy hoặc đọc; `[ASSUMED]` = chưa kiểm.

## Nguồn (đường dẫn tuyệt đối dưới repo develop)

| Báo cáo | Nội dung dùng cho plan |
|---|---|
| `plans/reports/understand-261007-1547-ai2-codebase-map-report.md` | Bản đồ AI2. `run_idp` có 20 bước (`ai-service/app/pipeline/idp.py:46`). Graph hiện có 6 `RelationType` (`ai-service/app/contracts/models.py:76`). Schema `ai2`, migrations `0001`–`0004` |
| `plans/reports/contract-graph-research-261007.md` | SOTA, ontology Akoma Ntoso `textualMod`. Ràng buộc BE: so chuỗi `"AMENDS"` (`backend/.../shared/ai/persistence.py:834`), `extra="forbid"` (`backend/.../shared/ai/schemas.py:253-288`) |
| `plans/reports/rootcause-261007-1610-ai2-16-key-graph-low-recall-report.md` | Recall thấp của AI2-16 do trích từng khoản thiếu ngữ cảnh + chỉ nguồn cặp SAME_KEY |
| `plans/reports/spike-261007-1719-operation-parser-vbhn-report.md` | **OBSERVED:** parser rule trên NĐ 50/2021 + VBHN 02/VBHN-BXD đạt op 26/26, marker 26/26, đích đủ cấp 16/26. 10 ca hụt do mục cha trỏ nhiều khoản |
| `plans/261007-1618-ai2-contract-graph/discovery-brief.md` | Quyết định V1–V6 và 3 vòng chốt; bake-off A–E |
| `plans/261007-1618-ai2-contract-graph/research-addendum-operation-first.md` | Kiến trúc 2 luồng; dữ liệu VBHN |

## Sự thật nền cho plan (OBSERVED)

1. `docs/contracts/ai2.be.processing.result.v1.schema.json`: `index_contribution.coverage` = `{"type": "object"}`; `context_finding.relation_type` = `string|null`. Thêm field vào coverage **không** phá BE.
2. `ai-service/app/pipeline/relation_markers.py` (commit `70998af`): `has_amend_marker()`, `defined_term()`, 21 test. Đã bắt 26/26 câu thao tác của NĐ 50/2021.
3. Chú thích VBHN có dạng "[n] Điểm/Khoản/Điều này được (sửa đổi, bổ sung|bổ sung|bãi bỏ) theo quy định tại <điểm x khoản y Điều z> <văn bản sửa đổi>". Thao tác nằm **trước** "theo quy định tại", vì tên văn bản sửa đổi đứng sau cũng chứa chữ "sửa đổi, bổ sung".
4. Trang VBHN đầu tiên có thể chứa mục lục. Thân "Điều 1." cần chọn theo đoạn dài nhất.
5. Phụ lục mua bán (n=1 mẫu, hoatieu.vn) ghi "Nội dung điều chỉnh: thay đổi số lượng hàng hóa" + bảng, **không** có địa chỉ đích.

## Quyết định ràng buộc (người dùng chốt)

- Phạm vi đợt này: **REDUCTION**, chỉ luồng 1 (P1–P4). Chưa làm phân loại cặp bằng LLM, chưa đổi query/L1, chưa làm UI.
- Graph chạy sau **feature flag mặc định tắt** (`AI2_CONTRACT_GRAPH_ENABLED`).
- Gửi BE: loại con map về `AMENDS`, không đổi contract (V6).
- Mâu thuẫn là finding `COMPARABLE_DIFFERENCE` (V3); không thuộc phạm vi đợt này ngoài việc liên kết nếu có sẵn.
- Thao tác ngầm (phụ lục không có địa chỉ): tìm đích theo nội dung qua `item_key`, luôn `NEEDS_REVIEW`.
- `PASS` tự động chỉ cho câu thao tác chuẩn + đích resolve duy nhất + citation hai phía, **và chỉ sau khi đạt ngưỡng**: cận dưới Wilson ≥ 0,85 với n ≥ 60 mỗi loại cạnh. Trước đó mọi cạnh `NEEDS_REVIEW`.
- Nhãn cạnh đợt 1: `INSERTION`, `SUBSTITUTION`, `REPEAL`, `REJECTION`, `SCOPE_LIMIT` (+ các loại khác cho luồng 2, ngoài phạm vi).

## Rủi ro đã biết

- Resolve địa chỉ khi mục cha trỏ nhiều khoản (10/26 trong spike). Địa chỉ tương đối ("vào sau khoản 4"). Phụ lục sửa phụ lục.
- Độ đúng của đích **chưa** đối chiếu với vị trí chú thích VBHN `[ASSUMED]`.
- n = 1 cặp văn bản; văn phong pháp quy lệch so với phụ lục hợp đồng.
- `USES_DEFINED_TERM` sau khi sửa regex có thể sinh nhiều cạnh, chưa có giới hạn.
