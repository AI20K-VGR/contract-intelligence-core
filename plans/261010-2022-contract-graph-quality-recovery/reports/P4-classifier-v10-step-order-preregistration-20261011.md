# P4 — classifier v10 sửa thứ tự xử lý nhãn

Ngày: 2026-10-11

## Đăng ký trước

- Run ID: `P4-classifier-v10-step-order-dev20-r1`.
- Thay đổi: chuyển quy trình xét `REFERENCE` lên BƯỚC 3 và `GENERAL_SPECIFIC` xuống BƯỚC 4 để thống nhất với thứ tự ưu tiên đã ghi; không đổi validator.
- Control: hai prompt v9 đã chạy trên cùng 20 cặp và thứ tự khóa.
- SHA-256 tập pair ID: `c4cdac1658e5d0b5408fedbe97b603c4831b4b97e3e2860c1289f376288a37b3`.
- Model yêu cầu `cx/gpt-5.5`; tối đa 3 HTTP requests, 100.000 tokens, 550 giây; 1 lần thử/request; dừng nếu request lỗi.
- Chấm exact label + direction, false `DUPLICATE`, và số theo gold label. Output không chứa văn bản hợp đồng.
- Mẫu đã lộ trong các lượt v9, nên đây là controlled diagnostic cùng mẫu, không phải validation độc lập.
- Dev-only; không đo candidate recall, không mở gate, không truy cập held-out.

Nếu request lỗi hoặc vượt giới hạn, đánh dấu `invalid_unscored` và không chạy lại.

## Kết quả

Hoàn tất 3 request; provider phục vụ `gpt-5.5`; dùng 12.240 tokens trong 43,01 giây. Exact `16/20`: `REFERENCE` 2/3, `GENERAL_SPECIFIC` 1/3, `UNRELATED` 13/14; 1 false `DUPLICATE`. Control `pairs-v9` đạt 13/20; `pairs-v9-checklist` đạt 16/20. Trên mẫu nhỏ đã lộ, v10 tăng REFERENCE từ 1/3 lên 2/3 so với v9 baseline, nhưng vẫn bỏ sót một REFERENCE, chỉ đúng 1/3 GENERAL_SPECIFIC và còn false `DUPLICATE`. Kết quả không phải gate hoặc validation độc lập. Artifact SHA-256: `66751ba8d9a29db2ecfd59e3e6879d694630378a934f9de4c327a571bc62379e`.
