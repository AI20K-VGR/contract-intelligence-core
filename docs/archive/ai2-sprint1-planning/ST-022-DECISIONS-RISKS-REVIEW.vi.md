# Quyết định, rủi ro và sign-off v0.2

Owner soạn: Trần Văn Dũng — AI2. Quyết định dưới là cơ sở làm việc và đề xuất review; không có người duyệt/ngày duyệt được xác nhận. Không gắn Locked/Approved cho nhóm khi chưa có phản hồi.

| ID | Quyết định | Nguồn | Trạng thái |
|---|---|---|---|
| D-01 | Planning AI2 hiện tại; tách cổng A/B | Yêu cầu trực tiếp của người dùng | Working scope |
| D-02 | Fixture tự soạn, hai representation types | Thiết kế v0.2; giữ an toàn dữ liệu nguồn | Working design |
| D-03 | Candidate/evidence + HITL, không tự quyết pháp lý | BRD thiết kế | Working design |
| D-04 | Raw immutable, offset code points, upright geometry | DATA-CONTRACT.vi.md | Pending AI1/BE review |
| D-05 | Baseline local regex/normalizer; manual context phải khai báo | Experiment card | Pending technical review |
| D-06 | External services AI2=none; compute/time chưa đo | Phương án baseline hiện tại | Working design |
| D-07 | Bản Việt nguồn làm việc, bản Anh dịch v0.2 | Lựa chọn tổ chức tài liệu trong phiên; không phải team sign-off | Working convention |
| D-08 | Tách gold, binding, run và HITL; enums chuẩn | Review M01–M15 | Pending AI1/BE review |
| D-09 | 15 case/30 tổ hợp mỗi round thay 12/24 | Thêm thiếu evidence và semantic controls C13–C15 | Working design |
| D-10 | 5h/ngày, 24h work + 6h buffer; reviewers đề xuất | Estimate phục vụ lập lịch | Pending leader confirmation |

| Rủi ro | Dấu hiệu / owner xử lý | Phản ứng |
|---|---|---|
| AI1 chưa phản hồi shape/snapshot | Quá mốc đề xuất ở tracker; Trần Văn Dũng | Ghi Pending review cho shape; Blocked cho B binding, vẫn bàn giao protocol planning. |
| Reviewer chưa có thời gian | Chưa xác nhận lịch; Trần Văn Dũng trao đổi leader | Giữ Draft ready/Pending review đúng thực tế; đổi reviewer chỉ sau xác nhận. |
| Thiếu capacity | Dưới 5h/ngày hoặc feedback vượt buffer | Báo task ảnh hưởng và đề xuất dời acceptance, không cam kết run trong 24h planning. |
| False difference/amendment | Context hoặc evidence thiếu | Dùng decision table, C03/C13 và không đoán source. |
| Mất provenance | Re-OCR/review ghi đè | Snapshot/run/revision mới, kiểm tra refs và previous revision. |
| Overclaim | Dùng mẫu JSON/tập phát triển như run chất lượng | Ghi example_only, origin thủ công, counts/missing và giới hạn tập dữ liệu. |
| Lệch tài liệu | Case/field/lịch ở bản dịch khác nguồn | Đồng bộ v0.2, dùng link trong handout, archive review cũ. |

## Dòng sign-off cần điền sau review thực tế

| Nội dung | Reviewer đề xuất | Trạng thái hiện tại | Người duyệt / ngày / bằng chứng |
|---|---|---|---|
| Scope/capacity | Kiều Trang | Chưa xác nhận | Chưa có |
| Gold/context/OCR shape | Đức Dũng | Chưa xác nhận | Chưa có |
| Contract/metric | Hoàng Chương | Chưa xác nhận | Chưa có |
| Highlight frame | Kiều Trang + Đức Dũng | Chưa xác nhận | Chưa có |

Cổng A accepted khi reviewer tương ứng phản hồi, các blocker thiết kế đã xử lý và evidence sign-off được ghi. Cổng B accepted riêng khi có nguồn/run/audit thật. Việc trợ lý sửa tài liệu không thay thế các sign-off này.
