# P4 — phép đo classifier v9 trên mẫu dev mới

Ngày: 2026-10-11

## Đăng ký trước

- Run ID: `P4-classifier-v9-dev20-fresh-r1`
- Tập: 20 cặp đã được user duyệt trong v3 dev gold, loại toàn bộ 20 cặp của `P4-baseline-r1`.
- Chọn mẫu cố định theo seed `P4-classifier-v9-dev20-fresh-r1-sha256-pair-id`: 3 `REFERENCE`, 3 `GENERAL_SPECIFIC`, 14 `UNRELATED`.
- SHA-256 thứ tự pair ID: `c4cdac1658e5d0b5408fedbe97b603c4831b4b97e3e2860c1289f376288a37b3`.
- Xử lý: classifier production `pairs-v9`; model yêu cầu `cx/gpt-5.5`, cấu hình endpoint/key chỉ đọc từ `ai-service/.env` và không ghi ra artifact.
- Giới hạn: tối đa 3 HTTP requests, 100.000 tokens, 550 giây; 1 lần thử mỗi request; dừng ngay khi lỗi.
- Chấm: nhãn chính xác; hướng A/B cho `REFERENCE` và `GENERAL_SPECIFIC`; số false `DUPLICATE`; nhóm theo nhãn.
- Output chỉ lưu pair IDs, nhãn/hướng dự đoán, outcome/rejection code, model phục vụ và số liệu tổng hợp; không lưu văn bản hợp đồng hoặc response thô.
- Dùng cho chẩn đoán classifier-only; không đo candidate recall, không mở gate và không truy cập held-out.

Nếu request lỗi hoặc vượt hạn mức, đánh dấu `invalid_unscored`, không chạy lại registration này.

## Kết quả

Hoàn tất 3 request; provider phục vụ `gpt-5.5`; dùng 12.026 tokens trong 37,26 giây. Chấm lại từ event log: `13/20` chính xác, gồm `REFERENCE` 1/3, `GENERAL_SPECIFIC` 0/3, `UNRELATED` 12/14; có 1 dự đoán `DUPLICATE` sai. Event `model_unrelated` được chấm là dự đoán `UNRELATED`; validator reject vẫn là abstain. SHA-256 artifact đã chấm: `21df42a16fe8b0d184d4e8f286518bfcbb5693fd0e611da2c35e9ac43d49f7e7`.

Đây là mẫu chẩn đoán nhỏ, chọn theo nhãn và chỉ đo classifier khi đã đưa sẵn cặp. Không ước lượng recall toàn sản phẩm, không mở gate, không truy cập held-out.
