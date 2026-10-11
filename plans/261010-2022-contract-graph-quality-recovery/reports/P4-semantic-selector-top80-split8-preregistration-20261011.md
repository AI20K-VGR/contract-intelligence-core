# P4 — semantic selector top-80 với batch nhỏ hơn

Ngày: 2026-10-11

## Đăng ký trước

- Run ID: `P4-semantic-selector-dev32-top80-split8-v3`.
- Phạm vi: 32 document ID trong dev recall frame khóa sẵn; không đọc held-out.
- Model: `cx/gpt-5.5`; tối đa 80 cặp/doc, chỉ trả node ID pair, không nhãn hoặc span.
- Batch: 8 request cân bằng theo kích thước đầu vào, 4 document/request. Mỗi request chỉ thử một lần để số request được đếm chính xác.
- Giới hạn: 8 HTTP requests, 500.000 tokens, 550 giây. Dừng ở request lỗi hoặc vượt budget; không chạy lại registration này.
- Kiểm tra: node hợp lệ, bỏ self-pair/Luong-1/ancestor, deduplicate, coverage theo 37 positive đã user duyệt.
- So sánh: selector top-80 riêng và offline fixed-cap blend với current C/40; không tích hợp runtime từ phép đo này.
- Artifact local ignored; không lưu contract text hay raw response. Metric dev-only; held-out không truy cập.

Run top-80 trước (`P4-semantic-selector-dev32-top80-v2`) invalid sau request error khi batch lớn hơn. Registration này đổi duy nhất cách chia batch để kiểm tra khả năng hoàn tất; vẫn tính là run riêng, không xóa hoặc thay metric run cũ.

## Kết quả

Invalid/unscored tại request thứ 3: 3 HTTP requests đã khởi chạy, 2 response thành công, 107.334 tokens được ghi nhận, 153,84 giây; request thứ ba dừng bằng `LabelerCallError`. Không có metric candidate hợp lệ; run bị loại và không chạy lại. Held-out không truy cập.
