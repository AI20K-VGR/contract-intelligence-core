# Đo → phân loại → tối ưu chất lượng AI2

Ngày: 2026-10-16 · Nhánh: `feature/ai2-contract-graph`

## Luồng

```
Đo (scorer) → phân loại từng lỗi
   ├─ Loại 1, 2 → sửa theo TDD (agent tự làm, dưới rào chắn)
   ├─ Loại 3    → dừng → so phương án → người dùng chọn → thực thi theo phase
   └─ Loại 4    → báo cáo → người dùng sửa gold/test → đo lại
→ code review → ship
```

## Phase 1: thước đo

- `fixtures/seeded/score.py`: chạy offline (tất định, không LLM) mọi hồ sơ cài lỗi. Mỗi kỳ vọng thành một dòng PASS/FAIL kèm tầng bị rơi; in `SCORE <đạt>/<tổng>` của tập **dev** và tập **held-out** riêng.
- Hồ sơ dev: HD-TEST-2026-001 (đã có). Hồ sơ held-out: HD-TEST-2026-002, mới, hư cấu, với các lỗi cài sẵn **khác loại** (xung đột body↔annex khác số hiệu điều, dẫn chiếu không phải sửa đổi, câu giới hạn phạm vi, câu bị ngắt qua trang, sửa đổi thời hạn có đổi giá trị, khoản lặp, bảng, chân trang).
- Gold được viết trước khi chạy và **không chỉnh theo kết quả**. Gold sai thì là lỗi loại 4, cần người duyệt.

## Rào chắn

1. Gold/fixture seeded và test là chỉ đọc khi tối ưu: diff chạm `fixtures/seeded/` hay `tests/test_seeded_*` trong một vòng tối ưu thì vòng đó bị loại.
2. Guard tách khỏi metric: toàn bộ test ai-service (golden, citation) phải xanh.
3. Chỉ tối ưu theo dev; held-out chỉ dùng để chấm.
4. Lỗi cần đổi từ hai module trở lên hoặc đổi hợp đồng dữ liệu thì xếp loại 3: dừng, không vá.

## Kết quả vòng 1 (2026-10-16)

Thước đo: `python -m fixtures.seeded.score` (offline) và `python -m fixtures.seeded.run_live --repeats N` (classifier). Gold của HD-TEST-2026-002 (held-out) và gold live của nó được viết trước lần chạy đầu tiên.

| Thước đo | Kết quả |
|---|---|
| Offline dev (001) | 18/18 |
| Offline held-out (002) | 20/21 |
| Live dev ×2 | 4/4 kỳ vọng, mỗi kỳ vọng 2/2; cạnh bị cấm 0 |
| Live held-out ×2 | 3/3 kỳ vọng, mỗi kỳ vọng 2/2; cạnh bị cấm 0 |
| Toàn bộ ai-service | 1921 pass |

Phân loại:

| # | Phát hiện | Loại | Xử lý |
|---|---|---|---|
| 1 | Câu tham số dạng danh từ "Thời gian giao hàng là trong vòng 30/45 ngày" bị mô hình hóa thành nghĩa vụ thiếu chủ thể nên không bao giờ được so (held-out `semantic_difference` 3.1 ↔ PL01 2.1). Tầng pairs vẫn bắt được bằng CONFLICT | 3 | Dừng, trình phương án |
| 2 | `object_scope` = "là" (regex lấy hệ từ) | 1 | Đã sửa, có test |
| 3 | 429 `credit_balance_exhausted` bị coi là rate limit, retry 3 lần mỗi lời gọi và đốt hết budget 20 lời gọi; người dùng thấy "quá tải" | 1 | Đã sửa: `LLM_QUOTA_EXHAUSTED`, dừng sau 1 request, các lời gọi sau trong job không gửi gì |
| 4 | Mỗi lượt chạy dùng hết 20/20 lời gọi (pairs và semantic dùng chung); semantic báo `LLM_BUDGET_EXCEEDED` | 3 (chính sách chi phí) | Cần quyết định budget theo hồ sơ |
| 5 | `LLM_TIMEOUT` ngắt quãng (6 lần / 4 lượt), chưa tái hiện được để biết tầng nào | 2 | Cần ghi nhãn tầng vào log trước khi tối ưu |
| 6 | Tập dev đã bão hòa (18/18): vòng lặp tối ưu không còn gì để leo | Thước đo | Cần thêm hồ sơ dev |

Sự cố vận hành: tài khoản OpenAI dùng cho AI2 local hết credit (`429 credit_balance_exhausted`) lúc chạy `budget_probe`. Mọi lời gọi live sau đó đều thất bại cho tới khi nạp credit.
