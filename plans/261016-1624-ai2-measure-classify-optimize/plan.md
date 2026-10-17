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

## Kết quả vòng 2 (2026-10-16, key OpenAI mới)

Thêm hồ sơ dev HD-TEST-2026-003 (dịch vụ bảo trì) và HD-TEST-2026-004 (cung cấp nội thất, gồm bẫy báo nhầm "05" ↔ "5"); gold viết trước lần chạy đầu. Loại kỳ vọng mới: `semantic_same`, `clause_starts`.

| Thước đo | Trước vòng 2 | Sau vòng 2 |
|---|---|---|
| Offline dev (001+003+004) | 36/42 (0,857) | **42/42** |
| Offline held-out (002) | 20/21 | 20/21 (không tụt) |
| Live ×1, cả 4 hồ sơ | — | mọi kỳ vọng đạt; cạnh bị cấm 0 |
| Toàn bộ ai-service | 1921 | 1933 pass |
| evals/contract_graph | — | 304 pass (3 fail môi trường có từ trước) |

Lỗi loại 1 đã sửa, đều có test:

| Lỗi | Tầng | Sửa |
|---|---|---|
| "Sửa đổi điểm a khoản 1 Điều 3" → TARGET_NOT_FOUND: điểm "a)" sau khoản dạng "3.1." được gán `{dieu 3, diem a}`, thiếu khoản | luồng 1 (`resolver._place`) | Điểm lấy khoản đứng ngay trước trong cùng điều khi node cha chỉ là tiêu đề điều |
| Thời hạn tính bằng giờ/tuần/năm không trích được | semantic | Thêm đơn vị `hour/week/year` |
| "05" ↔ "5" bị báo `COMPARABLE_DIFFERENCE` (báo nhầm) | semantic compare | So `deadline` theo giá trị số |
| "Hai bên nghiệm thu…" không có chủ thể/hành động | semantic | `actor=BOTH`; "nghiệm thu" thành `ACCEPT` chỉ khi đứng ngay sau chủ thể |
| Trigger ngoài tập ký hiệu ("kể từ ngày kết thúc tháng") luôn UNKNOWN | semantic | Trigger dạng cụm từ chuẩn hóa `AFTER:<cụm từ>` |
| Đối tượng của "nghiệm thu" không được trích | semantic | `object_scope` cho `ACCEPT` |
| Chân trang toàn chữ hoa chỉ xuất hiện một lần trong mỗi file không bị loại | pairs | Dòng toàn chữ hoa lặp trên ≥ 2 trang của hồ sơ là chân/đầu trang |
| Khoản trùng nguyên văn ở hai điều khác nhau không thành ứng viên | pairs | Nguồn `VERBATIM` (hash text đã bỏ số thứ tự, thuộc nhóm core) |
| Log lỗi LLM không nói tầng nào | runtime | `operation=pairs|slot_context|alias|fact_normalize|table` |

Phát hiện loại 2 mới: cả 6 `LLM_TIMEOUT` của lượt live đều ở `operation=pairs`. Độ trễ một batch pairs là 15–31 giây, so với timeout 45 giây × 3 lần thử. Các hướng: timeout riêng cho pairs, giảm cỡ batch, hoặc hạ reasoning effort. Cần đo bằng live run (tốn phí) nên chưa đổi.

Vẫn chờ quyết định: held-out `semantic_difference` (câu tham số dạng danh từ, loại 3) và chính sách budget LLM (loại 3).
