# DOC-01 — Product Vision: Contract Intelligence (PROD-01)

**Phiên bản:** v0.2  
**Ngày soạn:** 15/09/2026  
**Trạng thái:** Draft ready — chưa có review hoặc sign-off thực tế.  
**Tác giả duy nhất:** Trần Văn Dũng — AI Engineer, AI2.  
**Reporter duy nhất đề xuất:** Trần Thị Kiều Trang — Team Leader/Frontend Engineer.  
**Reviewer dự kiến:** Mentor, tại buổi Sprint 1 demo.  
**Nguồn chuẩn:** Bản tiếng Việt này.

> Product Vision trả lời bốn câu hỏi bắt buộc: **Problem**, **Users**, **Value**, và **What is out of scope**. Tài liệu này định hướng mục tiêu toàn dự án; nó không thay thế BRD, PRD, Architecture, API Spec, data contract hoặc test plan.

## 1. Problem

### 1.1 Bối cảnh

Hợp đồng thương mại thường gồm hợp đồng chính, phụ lục và các bảng biểu. Người rà soát phải đọc nhiều trang PDF, xác định cấu trúc Điều–Khoản–Điểm, tìm các dữ kiện quan trọng và đối chiếu thông tin giữa các tài liệu liên quan. Nguồn đầu vào có thể là PDF scan hoặc PDF có text layer, nên việc tìm kiếm và kiểm tra còn gặp khó khăn về OCR, cấu trúc, bảng và vị trí nguồn.

Trong quy trình hiện tại, người dùng phải tự:

- Điều hướng qua tài liệu dài để tìm điều khoản và bảng liên quan.
- Đọc, chép hoặc đối chiếu các fact như giá trị, số lượng, ngày/thời hạn, các bên, mã số thuế và số hợp đồng tham chiếu.
- Xác định liệu hai giá trị có thật sự cùng đối tượng, cùng đơn vị, cùng phạm vi và có thể so sánh hay không.
- Truy ngược lại trang/đoạn gốc để kiểm tra trước khi đưa ra nhận định.

Việc này tốn thời gian, khó lặp lại nhất quán và có nguy cơ bỏ sót thông tin hoặc nhầm lẫn khi tài liệu có nhiều phụ lục, nhiều phiên bản, bảng phức tạp hoặc chất lượng scan không đồng đều.

### 1.2 Vấn đề sản phẩm cần giải quyết

Contract Intelligence là hệ thống OCR/IDP hỗ trợ biến dossier hợp đồng thành thông tin có cấu trúc, có nguồn dẫn và có thể rà soát. Hệ thống phải giúp người dùng:

1. Đọc được cấu trúc tài liệu thay vì chỉ nhìn một khối PDF thô.
2. Tìm và xem fact quan trọng trong ngữ cảnh của điều khoản/bảng chứa chúng.
3. Kiểm tra các khác biệt hoặc ứng viên xung đột giữa hợp đồng và phụ lục trên cơ sở evidence hai phía.
4. Xác nhận, chỉnh sửa, từ chối hoặc yêu cầu thêm evidence thông qua quy trình human-in-the-loop (HITL).

### 1.3 Nguyên tắc giải quyết vấn đề

- **Evidence-first:** mọi fact/finding phải có khả năng truy về nguồn tài liệu, trang và vị trí tương ứng trong snapshot đầu vào.
- **Context before comparison:** hệ thống chỉ so sánh khi biết đủ vai trò nghiệp vụ, đối tượng, đơn vị, phạm vi và điều kiện áp dụng; thiếu evidence phải được báo là thiếu evidence, không suy đoán.
- **Human remains accountable:** hệ thống tạo dữ liệu và finding kỹ thuật để hỗ trợ; người dùng có thẩm quyền mới ra quyết định nghiệp vụ/pháp lý.
- **Traceable history:** OCR mới, lần chạy mới và correction của reviewer phải có version/lịch sử riêng; không ghi đè evidence hay output máy.

## 2. Users

### 2.1 Người dùng chính — Chuyên viên rà soát hợp đồng

Đây là persona chính. Họ tiếp nhận dossier, kiểm tra nội dung hợp đồng/phụ lục và cần một cách làm nhanh, nhất quán, có thể kiểm chứng.

| Công việc cần làm | Khó khăn hiện tại | Giá trị cần nhận từ hệ thống |
|---|---|---|
| Đọc nhanh cấu trúc tài liệu | PDF dài, scan, bảng và Điều/Khoản/Điểm khó định vị | Cây cấu trúc và bảng được nhận diện để điều hướng trực tiếp. |
| Kiểm tra fact | Fact phân tán, dễ bỏ sót hoặc chép sai | Fact được trích xuất, giữ raw text và giá trị chuẩn hóa khi có thể. |
| Đối chiếu hợp đồng–phụ lục | Hai giá trị có thể khác role, scope hoặc thời hạn | Finding kỹ thuật nêu rõ có thể so sánh, khác biệt, amendment candidate, không so sánh được hoặc thiếu evidence. |
| Xác minh kết quả | Khó trở về chính xác nguồn gốc | Highlight/citation về hai phía nguồn để tự kiểm tra. |
| Sửa kết quả | Sửa tay làm mất dấu vết | HITL cho phép confirm/correct/reject/request evidence và lưu revision. |

### 2.2 Người dùng phụ

- **Quản lý/pháp chế nội bộ:** theo dõi dossier cần chú ý và sử dụng kết quả đã được người rà soát xác nhận trong quy trình của tổ chức.
- **Nhân sự vận hành hợp đồng, mua hàng hoặc bán hàng:** tra cứu thông tin đã được rà soát theo quyền hạn được cấp; không là người mà hệ thống mặc định trao quyền phê duyệt pháp lý.
- **Quản trị hệ thống:** quản lý quyền truy cập, version đầu vào/kết quả và vận hành kỹ thuật; không đánh giá nội dung nghiệp vụ thay reviewer.

### 2.3 Nhu cầu và ranh giới trách nhiệm

Người dùng cần minh bạch về việc kết quả nào là output máy, kết quả nào đã được reviewer chỉnh sửa/xác nhận và evidence nào còn thiếu. Hệ thống không được trình bày finding như kết luận pháp lý, cũng không che giấu mức độ không chắc chắn hoặc giới hạn của OCR.

## 3. Value

### 3.1 Lời hứa giá trị

Contract Intelligence giúp chuyên viên rà soát chuyển việc đọc/đối chiếu PDF thủ công thành một quy trình có cấu trúc, truy vết được và có con người kiểm soát. Sản phẩm rút ngắn thời gian định vị thông tin và giảm rủi ro bỏ sót, nhưng không thay thế năng lực chuyên môn hoặc thẩm quyền phê duyệt của con người.

### 3.2 Giá trị theo năng lực sản phẩm

| Năng lực | Giá trị người dùng | Điều kiện để đáng tin |
|---|---|---|
| OCR và tái tạo cấu trúc | Đọc/điều hướng Điều–Khoản–Điểm và bảng nhanh hơn | Hiển thị được nguồn gốc và phân biệt lỗi/thiếu dữ liệu. |
| Fact extraction | Tập trung các dữ kiện cần kiểm tra, giảm chép tay | Raw text, normalization, context và citation được giữ riêng. |
| So sánh có ngữ cảnh | Hướng sự chú ý tới khác biệt đáng rà soát | Không coi khác biệt bề mặt là xung đột; nêu rõ disposition và evidence. |
| Evidence/provenance | Reviewer tự xác minh thay vì tin hộp đen | Có hai phía nguồn cho finding và version đầu vào rõ ràng. |
| HITL | Reviewer sửa/xác nhận kết quả mà không mất lịch sử | Revision append-only, tách correction khỏi output máy. |

### 3.3 Lộ trình giá trị

**MVP Sprint 1–3** tập trung chứng minh nền tảng: PDF tiếng Việt, cấu trúc Điều–Khoản–Điểm/bảng, và fact chính có thể truy nguồn. Demo tối thiểu là một dossier gồm hợp đồng và có thể kèm phụ lục, nơi người dùng mở tài liệu, xem structure/table, xem fact và kiểm tra lại nguồn.

Sau khi có evidence thực nghiệm, sản phẩm mở rộng theo thứ tự: (1) so sánh contract–annex và annex–annex theo context; (2) finding có evidence hai phía; (3) HITL correction/history đầy đủ; (4) mở rộng ngôn ngữ/định dạng theo yêu cầu được duyệt.

### 3.4 Tín hiệu thành công

Ở Sprint 1 demo, thành công của Product Vision là Mentor và nhóm có thể xác nhận rằng mục tiêu, người dùng, giá trị và ranh giới MVP được hiểu thống nhất. Đây là nghiệm thu tài liệu, **không** là bằng chứng OCR quality, model run, accuracy hay production readiness.

Khi bắt đầu Gate B, các tín hiệu kỹ thuật/sản phẩm phải được đo bằng protocol riêng: khả năng bind fact/finding vào snapshot thật, audit citation/bounding box, kết quả extraction/comparison và metric đã định nghĩa. Không đặt mục tiêu số học trong Product Vision khi chưa có data, baseline và reviewer chốt phương pháp đo.

## 4. What is out of scope

### 4.1 Ngoài phạm vi thẩm quyền

- Tự động kết luận hiệu lực pháp lý, diễn giải pháp luật, xác định văn bản nào có hiệu lực/ưu tiên hoặc đưa khuyến nghị pháp lý.
- Tự động phê duyệt/từ chối hợp đồng, ký kết thay người dùng hoặc thay thế quyết định nghiệp vụ của tổ chức.
- Trình bày finding kỹ thuật như một phán quyết, hoặc che giấu trường hợp evidence/context chưa đủ.

### 4.2 Ngoài phạm vi MVP

- Tự động phát hiện và giải quyết toàn bộ xung đột hợp đồng–phụ lục ngay trong demo đầu tiên.
- Hỗ trợ DOCX, email, ảnh rời hoặc các định dạng khác PDF.
- Cam kết hỗ trợ tiếng Anh, song ngữ hoặc mọi biến thể ngôn ngữ trong MVP.
- Tự động tạo/sửa/redline nội dung hợp đồng.
- Cam kết quality, throughput, chi phí, SLA hoặc khả năng production khi chưa có run/audit/evidence thực tế.
- Thay thế hệ thống quản lý hợp đồng, workflow phê duyệt hoặc kho lưu trữ hồ sơ hiện hữu.

### 4.3 Điều không được suy diễn từ Product Vision

- Fixture minh họa, JSON mẫu hoặc tài liệu planning không phải bằng chứng OCR chất lượng, model run hoặc nghiệm thu kỹ thuật.
- Việc có một finding không đồng nghĩa finding đã được reviewer xác nhận.
- Dossier được upload cùng nhau không tự chứng minh quan hệ amendment, thời điểm hiệu lực hoặc thứ tự ưu tiên giữa các tài liệu.
