# Hướng dẫn xây dựng và duyệt nhãn Golden

## Phạm vi và nguyên tắc

Golden set này gồm hợp đồng tổng hợp G01–G08, không dùng dữ liệu khách hàng thật. AI1 snapshot là nguồn bằng chứng; nhãn phản ánh khả năng định vị và trạng thái bằng chứng, không phải kết luận pháp lý. Câu hỏi và nhãn kỳ vọng phải độc lập với output của reasoner.

Trạng thái kỳ vọng được tính bằng `expected_state_for(question_kind, mutations)` trong `evals/golden/spec.py`. Không gán trạng thái riêng cho từng câu. Nếu một tình huống chưa được quy tắc bao phủ, hãy bổ sung quy tắc và cập nhật hướng dẫn trước khi sinh lại dữ liệu.

## Quy tắc trạng thái

| Tình huống được khai báo | Trạng thái kỳ vọng |
|---|---|
| Xung đột thân/phụ lục, tên trùng nhưng mã số thuế khác, sửa đổi chồng lấn hoặc giá trị/ngày/tỷ lệ mâu thuẫn | `NEEDS_REVIEW` |
| Phụ lục thiếu, thông tin không có, bằng chứng không đọc được hoặc câu hỏi quá rộng | `INSUFFICIENT_EVIDENCE` |
| So sánh hai đại lượng không cùng loại | `NOT_COMPARABLE` |
| Tra cứu một giá trị hoặc điều khoản không có xung đột | `ANSWERED` |

Khi một câu có nhiều mutation, xung đột ưu tiên trước; kế tiếp là không thể so sánh; cuối cùng là thiếu bằng chứng. Mutation hoặc question kind không biết phải báo lỗi, không được rơi về nhãn mặc định.

## Span và citation

- Mỗi `required_span` trỏ tới đúng trang, các `line_ids` cụ thể và bounding box hợp của các dòng đó.
- `acceptable_spans` là danh sách span tường minh cho từng câu. Chỉ gồm dòng bắt buộc, dòng nối tiếp của cùng câu bị ngắt trang/ngắt dòng, và bằng chứng phía đối chiếu cần thiết khi có xung đột.
- Mỗi acceptable span tối đa ba dòng. Không đưa heading điều khoản hay toàn bộ đoạn vào chỉ để làm rộng vùng khớp.
- ID dòng phải tồn tại trong snapshot. Bbox span bằng hợp bbox của các dòng nguồn; không ước lượng hình học.

## Giá trị chuẩn hóa

Mỗi gold value ghi `kind`, `raw`, `normalized` và `span_id`. `raw` giữ nguyên cách viết trong dòng nguồn; `normalized` chỉ áp dụng phép chuẩn hóa xác định theo loại giá trị. Ngày giữ ngữ nghĩa ngày, phần trăm không chuyển thành số tiền, và đơn vị tiền tệ không bị bỏ. Chuỗi NFC và digest dùng nội dung UTF-8 với xuống dòng LF.

## Duyệt mù candidate

Worksheet candidate chỉ chứa định danh, nguồn và SHA, tiêu đề/kịch bản/ghi chú, số trang hoặc node và tags. Không đưa nhãn cũ từ `eval_suite.py` hoặc output hệ thống vào worksheet. Tệp quyết định khởi tạo mọi `decision` là `PENDING` và `final_label` là `null`; người duyệt tự xem nguồn rồi ghi quyết định cùng căn cứ. Chỉ Văn Dũng thực hiện promote có reviewer và basis hợp lệ. `CI` không được approve hay promote.

## Thay đổi sau khi chốt spec

Commit spec, catalog và hướng dẫn trước lần chạy reasoner đầu tiên. Sau `spec_commit`, mọi thay đổi quy tắc trạng thái hoặc span phải ghi lý do tại đây và được HC-1 duyệt. Ghi SHA commit spec vào manifest; không suy ra nhãn từ kết quả reasoner.

| Ngày | Thay đổi | Lý do | HC-1 |
|---|---|---|---|
| Chưa có | Chưa có thay đổi sau spec commit | — | — |

## Giới hạn D-A10

95 candidate `UNVERIFIED` cần HC-2 adjudicate độc lập trước khi được dùng làm ground truth. Agreement/Kappa mô tả mức đồng thuận giữa quyết định reviewer và nhãn fixture sau mapping; chỉ có hai nguồn và không thay đổi kết luận D-A10. Việc hoàn thành P1 không đồng nghĩa candidate đã được duyệt.
