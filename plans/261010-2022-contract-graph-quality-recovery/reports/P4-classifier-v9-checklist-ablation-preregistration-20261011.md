# P4 — ablation checklist cho classifier v9

Ngày: 2026-10-11

## Đăng ký trước

- Run ID: `P4-classifier-v9-checklist-dev20-fresh-r1`
- Treatment: thêm checklist cuối prompt v9 (`pairs-v9-checklist`), giữ nguyên validator.
- Control: `P4-classifier-v9-dev20-fresh-r1`, dùng đúng 20 pair ID và thứ tự đã khóa.
- Tập dev SHA-256: `c4cdac1658e5d0b5408fedbe97b603c4831b4b97e3e2860c1289f376288a37b3`.
- Model yêu cầu `cx/gpt-5.5`; tối đa 3 HTTP requests, 100.000 tokens, 550 giây; 1 lần thử/request; dừng khi lỗi.
- So sánh: exact label + direction, false `DUPLICATE`, nhóm theo gold label. Model chỉ nhận văn bản cặp cần phân loại.
- Chỉ chẩn đoán dev; không mở gate, không đo candidate recall, không truy cập held-out.

Nếu có request lỗi hoặc vượt hạn mức, đánh dấu `invalid_unscored`, không chạy lại.
