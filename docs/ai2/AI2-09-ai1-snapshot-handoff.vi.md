# AI2-09 — Handoff AI1 snapshot

Contract canonical được hợp nhất tại:

[docs/contracts/AI1-AI2-CONTRACT.vi.md](../contracts/AI1-AI2-CONTRACT.vi.md)

File này là compatibility pointer để các tài liệu AI2 cũ không trỏ tới một định nghĩa handoff riêng.

## Quy ước hiện tại

- AI1 phát `ai1.snapshot.v1`.
- Tầng vận chuyển chuyển nguyên payload cho AI2, không sửa semantic.
- AI2 giữ nguyên identity và evidence reference khi dựng dữ liệu nội bộ.
- Runtime canonical đã có schema/semantic validation; quarantine vận hành là phần riêng chưa triển khai.
- `PARTIAL`, `UNKNOWN`, `UNAVAILABLE` và `FAILED` giữ nguyên semantics.
- Không đưa re-OCR vào contract hiện tại.

Output thực `machine/effective` v0.1 được nhận qua compatibility endpoint `/api/workspace/ai1-result`, không phải payload thay thế cho `ai1.snapshot.v1` ở `/jobs/idp`. Xem [review thực nghiệm](../reviews/AI2-REVIEW-2026-09-22.vi.md).
