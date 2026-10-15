# P4 — ablation checklist cho classifier v10

Ngày: 2026-10-11

## Đăng ký trước

- Run ID: `P4-classifier-v10-checklist-dev20-r1`.
- Treatment: prompt v10 đã sửa đúng thứ tự REFERENCE trước GENERAL_SPECIFIC, cộng checklist cuối prompt.
- Control: `P4-classifier-v10-step-order-dev20-r1`, cùng 20 pair ID và thứ tự.
- SHA-256 sample: `c4cdac1658e5d0b5408fedbe97b603c4831b4b97e3e2860c1289f376288a37b3`.
- Model yêu cầu `cx/gpt-5.5`; tối đa 3 HTTP requests, 100.000 tokens, 550 giây; 1 lần thử/request; dừng nếu lỗi.
- So sánh exact label + direction, false `DUPLICATE`, nhóm theo gold label.
- Mẫu dev đã lộ trong các lượt v9/v10; đây là controlled ablation, không phải validation độc lập hay gate.
- Không truy cập held-out; artifact chỉ lưu IDs và số liệu, không lưu văn bản hợp đồng.

Đây là lượt prompt ablation cuối trên sample này. Nếu request lỗi hoặc vượt giới hạn, đánh dấu `invalid_unscored`, không chạy lại.

## Kết quả

Hoàn tất 3 requests; provider phục vụ `gpt-5.5`; 12.676 tokens trong 46,26 giây. Exact `15/20`: `REFERENCE` 2/3, `GENERAL_SPECIFIC` 0/3, `UNRELATED` 13/14; 1 false `DUPLICATE`. Control v10 không checklist đạt 16/20, do đó giữ v10 baseline; không ghép checklist. Artifact SHA-256: `7f52aa91ca5805e3aae1fdb3a1f46ba345c2a5693989154d71a58daed1f2d1bd`.
