# DOC-01 · Product Vision — Contract Intelligence

| Thuộc tính | Giá trị |
|---|---|
| Mã | PROD-01 |
| Phiên bản | v0.3 |
| Ngày | 16/09/2026 |
| Trạng thái | Draft — Ready for Review |
| Owner | Trần Thị Kiều Trang — Leader (tổng hợp DOC-01) |
| Contributors | Trần Văn Dũng (AI2, v0.2) · Phạm Hoàng Chương (Problem/Value vận hành) · Nguyễn Đức Dũng (Users/OOS OCR) · Trần Thị Kiều Trang (HITL/Operator, ghép bản) |
| Reviewer | Mentor, demo Sprint 1 |
| Effective / review date | 16/09/2026 / TBD |
| Upstream / thay thế | Không có / Không có |

Product Vision trả lời bốn câu hỏi bắt buộc: **Problem, Users, Value, What is out of scope**. Nó định hướng mục tiêu toàn dự án; không thay thế BRD, PRD, Architecture, API Spec, data contract hoặc test plan.

## 1. Problem

### 1.1 Bối cảnh

Hợp đồng thương mại thường gồm hợp đồng chính, phụ lục và các bảng biểu. Người rà soát phải đọc nhiều trang PDF, xác định cấu trúc Điều–Khoản–Điểm, tìm dữ kiện quan trọng và đối chiếu giữa các tài liệu liên quan. Đầu vào có thể là PDF scan hoặc PDF có text layer, nên khó khăn không chỉ nằm ở OCR mà còn ở cấu trúc, bảng và vị trí nguồn.

Người dùng hiện phải tự điều hướng tài liệu dài, chép/đối chiếu giá trị–số lượng–ngày/thời hạn–các bên–mã số thuế–số hợp đồng tham chiếu, tự quyết định hai giá trị có cùng đối tượng/đơn vị/phạm vi để so sánh được hay không, và quay lại trang gốc trước khi nhận định. Quy trình này tốn thời gian, khó lặp lại nhất quán và dễ bỏ sót khi có nhiều phụ lục, phiên bản, bảng phức tạp hoặc scan không đồng đều.

### 1.2 Vấn đề sản phẩm cần giải quyết

Contract Intelligence là hệ thống OCR/IDP hỗ trợ biến dossier hợp đồng thành thông tin có cấu trúc, có nguồn dẫn và có thể rà soát. Hệ thống phải giúp người dùng:

1. Đọc cấu trúc tài liệu thay vì chỉ nhìn một khối PDF thô.
2. Tìm và xem fact quan trọng trong ngữ cảnh điều khoản/bảng chứa chúng.
3. Kiểm tra khác biệt hoặc ứng viên xung đột giữa hợp đồng và phụ lục trên evidence hai phía.
4. Confirm, correct, reject hoặc request evidence qua human-in-the-loop (HITL).

### 1.3 Nguyên tắc giải quyết

- **Evidence-first:** fact/finding phải truy được về source, trang và vị trí trong snapshot đầu vào.
- **Context before comparison:** chỉ so sánh khi đủ role, đối tượng, đơn vị, phạm vi và điều kiện áp dụng; thiếu evidence phải được nói rõ, không suy đoán.
- **Human remains accountable:** hệ thống tạo dữ liệu/finding kỹ thuật; người có thẩm quyền quyết định nghiệp vụ/pháp lý.
- **Traceable history:** OCR mới, run mới và reviewer correction có version/lịch sử riêng; không ghi đè evidence hay machine output.

## 2. Users

### 2.1 Người dùng chính — Chuyên viên rà soát hợp đồng

| Công việc | Khó khăn hiện tại | Giá trị cần nhận |
|---|---|---|
| Đọc cấu trúc | PDF dài, scan, bảng và Điều/Khoản/Điểm khó định vị | Cây cấu trúc/bảng để điều hướng trực tiếp. |
| Kiểm tra fact | Fact phân tán, dễ bỏ sót/chép sai | Raw text và normalized value khi có thể. |
| Đối chiếu hợp đồng–phụ lục | Có thể khác role, scope, thời hạn | Finding nói rõ comparable, difference, amendment candidate, not comparable hoặc missing evidence. |
| Xác minh | Khó về đúng nguồn | Highlight/citation về hai phía nguồn. |
| Đọc PDF scan/text-layer, tiếng Việt | OCR có thể sai số tiền/ngày | Không đọc được thì đánh dấu, không bịa và dẫn về vùng ảnh. |
| Sửa kết quả | Sửa tay làm mất dấu vết | HITL confirm/correct/reject/request evidence có revision. |

### 2.2 Người dùng phụ

- Quản lý/pháp chế nội bộ: theo dõi dossier cần chú ý và dùng kết quả đã được reviewer xác nhận.
- Nhân sự vận hành hợp đồng, mua hàng hoặc bán hàng: tra cứu theo quyền hạn, không được mặc định trao quyền phê duyệt pháp lý.
- Quản trị hệ thống: quản lý quyền truy cập, version đầu vào/kết quả và vận hành kỹ thuật; không đánh giá nội dung thay reviewer.
- **Operator:** đưa dossier (một hợp đồng và phụ lục PDF) vào hệ thống, theo dõi job, xem lý do lỗi và rerun nếu được phép; không phải người duyệt pháp lý và không cần màn HITL đầy đủ.

### 2.3 Ranh giới trách nhiệm

Người dùng phải thấy rõ output máy, output đã được reviewer chỉnh sửa/xác nhận và evidence còn thiếu. Finding không được trình bày như kết luận pháp lý hoặc che giấu giới hạn của OCR.

## 3. Value

### 3.1 Lời hứa giá trị

Contract Intelligence chuyển việc đọc/đối chiếu PDF thủ công thành quy trình có cấu trúc, truy vết được và có con người kiểm soát. Nó rút ngắn thời gian định vị thông tin, giảm rủi ro bỏ sót, nhưng không thay thế chuyên môn hay thẩm quyền phê duyệt.

Người dùng theo dõi được lifecycle: nạp file → đang xử lý → đã trích → chờ review → đã review/duyệt, hoặc lỗi kèm lý do. Dossier không có lệch vẫn đi hết luồng; không bị kẹt vì không có conflict.

### 3.2 Giá trị theo năng lực

| Năng lực | Giá trị người dùng | Điều kiện đáng tin |
|---|---|---|
| OCR và tái tạo cấu trúc | Điều hướng Điều–Khoản–Điểm/bảng nhanh hơn | Có nguồn gốc, phân biệt lỗi/thiếu dữ liệu. |
| Fact extraction | Giảm chép tay | Raw, normalization, context và citation tách riêng. |
| So sánh có ngữ cảnh | Hướng sự chú ý tới khác biệt đáng rà soát | Không coi khác biệt bề mặt là xung đột. |
| Evidence/provenance | Reviewer tự xác minh | Hai phía nguồn và version đầu vào rõ ràng. |
| HITL | Sửa/xác nhận không mất lịch sử | Revision append-only, correction tách machine output. |

### 3.3 Lộ trình giá trị

MVP Sprint 1–3 chứng minh nền tảng: PDF tiếng Việt, cấu trúc Điều–Khoản–Điểm/bảng và fact chính có thể truy nguồn. Demo tối thiểu là dossier có hợp đồng và có thể kèm phụ lục, nơi người dùng xem structure/table, fact và evidence.

Sau khi có evidence thực nghiệm, thứ tự mở rộng là: comparison contract–annex/annex–annex theo context, finding có evidence hai phía, HITL correction/history đầy đủ, rồi mới đến ngôn ngữ/định dạng khác đã được duyệt.

### 3.4 Tín hiệu thành công

Sprint 1 thành công khi Mentor và nhóm thống nhất problem, users, value và ranh giới MVP. Đây là nghiệm thu tài liệu, không phải bằng chứng OCR quality, model run, accuracy hay production readiness.

Gate B dùng protocol riêng để đo binding fact/finding vào snapshot thật, citation/bbox audit, extraction/comparison và metrics. Không đặt mục tiêu số học trong Product Vision trước khi có data, baseline và reviewer chốt phương pháp đo. Deliverable Sprint 1 là DOC-01/02/03 draft, sample, OCR spike, hướng kiến trúc và wireframe HITL.

## 4. What is out of scope

### 4.1 Ngoài phạm vi thẩm quyền

- Tự kết luận hiệu lực pháp lý, diễn giải pháp luật, xác định văn bản hiệu lực/ưu tiên hoặc khuyến nghị pháp lý.
- Tự phê duyệt/từ chối hợp đồng, ký kết thay người dùng hoặc thay thế quyết định nghiệp vụ.
- Trình bày finding kỹ thuật như phán quyết hoặc che giấu evidence/context chưa đủ.

### 4.2 Ngôn ngữ và định dạng

- **Must:** PDF tiếng Việt, text-layer và scan.
- **Should:** tiếng Anh/song ngữ Việt–Anh trong bộ mẫu và thử OCR; MVP không cam kết mọi biến thể hoặc production-quality đa ngữ.
- **Không hỗ trợ MVP:** DOCX, email, ảnh rời; JPG/PNG là mở rộng sau.

### 4.3 Ngoài phạm vi MVP

- Tự động phát hiện/giải quyết toàn bộ xung đột hợp đồng–phụ lục ngay demo đầu tiên.
- Train OCR model riêng hoặc coi spike/POC là worker production.
- Tự tạo/sửa/redline nội dung hợp đồng.
- Cam kết quality, throughput, cost, SLA hoặc production readiness khi chưa có run/audit/evidence thật.
- Thay thế contract-management system, approval workflow hoặc kho lưu trữ hồ sơ hiện hữu.

### 4.4 Điều không được suy diễn

- Fixture, JSON mẫu và planning không phải bằng chứng OCR/model/evaluation.
- Có finding không đồng nghĩa finding đã được reviewer xác nhận.
- Upload cùng dossier không tự chứng minh amendment relationship, effective date hay precedence.

## Liên kết canonical

Business rules: [DOC-02](DOC-02-brd.md) · Product requirements: [DOC-03](DOC-03-prd.md) · Architecture: [DOC-04](DOC-04-architecture.md) · Evaluation: [DOC-06](DOC-06-eval-report.md).
