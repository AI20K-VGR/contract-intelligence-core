# Contract graph luồng 2 — P1 bộ nhãn cặp

- Ground truth: `GPT labeler pairs-labeler-v1 (approved=false; HG-1 human review pending, P2/P5)` — nhãn GPT chưa duyệt, không phải độ chính xác nghiệp vụ.
- Người gán nhãn: yêu cầu `gpt-4o-mini`, phục vụ `gpt-4o-mini-2024-07-18`, họ `openai`, prompt `pairs-labeler-v1`.
- Pool sha256: `7ff6505063fc07ce23088d5ce5c307da7f4da6d0764eb8e5642d0d65be6d005b`

## Nguồn và văn bản

- Nguồn liệt kê 21 {'SALES': 10, 'SUPPLY_SERVICE': 11}; dùng được 21; loại do tách < 5 Điều 0; lỗi tải/đọc 0.
- Theo profile: {'SALES': 10, 'SUPPLY_SERVICE': 11}; theo split: {'dev': 7, 'heldout': 14}; profile/split: {'SALES/dev': 2, 'SALES/heldout': 8, 'SUPPLY_SERVICE/dev': 5, 'SUPPLY_SERVICE/heldout': 6}; có Phụ lục: 1.
- Ngưỡng (≥15 dùng được, ≥6/profile, held-out ≥10, dev ≥5, không nhiễm bẩn trong held-out): **đạt**.

## Cụm và nhiễm bẩn (RT-13)

- Cụm: 21 (held-out/dev: {'dev': 7, 'heldout': 14}); cụm gần trùng 0 gồm 0 văn bản.
- Văn bản nhiễm bẩn: 0; ép dev (`forced_dev_contaminated`): 0; nhiễm bẩn trong held-out: 0.

## Pool (D17)

- Cặp: 1021 — theo tầng {'S1': 287, 'S2': 22, 'S3': 712}; split/tầng {'dev/S1': 94, 'dev/S3': 232, 'heldout/S1': 193, 'heldout/S2': 22, 'heldout/S3': 480}; vũ trụ trước trần/mẫu {'S1': 287, 'S2': 22, 'S3': 3083}.
- `excluded_luong1`: 0.

## Nhãn GPT

- Đã gán 1021, chưa gán (lỗi gọi) 0.
- Split/nhãn: {'dev/CONFLICT': 6, 'dev/DUPLICATE': 7, 'dev/GENERAL_SPECIFIC': 15, 'dev/REFERENCE': 1, 'dev/UNRELATED': 297, 'heldout/CONFLICT': 28, 'heldout/DUPLICATE': 41, 'heldout/GENERAL_SPECIFIC': 36, 'heldout/REFERENCE': 2, 'heldout/UNRELATED': 588}
- Tầng/nhãn: {'S1/CONFLICT': 29, 'S1/DUPLICATE': 47, 'S1/GENERAL_SPECIFIC': 20, 'S1/UNRELATED': 191, 'S2/DUPLICATE': 1, 'S2/GENERAL_SPECIFIC': 3, 'S2/UNRELATED': 18, 'S3/CONFLICT': 5, 'S3/GENERAL_SPECIFIC': 28, 'S3/REFERENCE': 3, 'S3/UNRELATED': 676}
- `label_invalid`: 0/1021 (0.000; Wilson95 0.000–0.004) {}
- `grounded=false` (nhãn hợp lệ ≠ UNRELATED (span bắt buộc)): 10/136 (0.073; Wilson95 0.040–0.130)

## Ước số dòng HG-1 (D18, chưa gồm S4 — P2 cập nhật)

| nhãn | GPT | chọn |
| --- | --- | --- |
| GENERAL_SPECIFIC | 51 | 51 |
| CONFLICT | 34 | 34 |
| DUPLICATE | 48 | 48 |
| REFERENCE | 3 | 3 |
| UNRELATED | 885 | 80 {'S1': 17, 'S2': 10, 'S3': 53} |

- Tổng: **216** / trần 380.

## Theo văn bản

| doc_id | profile | split | cluster | Điều | node | phụ lục | cặp theo tầng | nhãn |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pd-0cd20d2016 | SUPPLY_SERVICE | heldout | cl-827a747788 | 13 | 13 | — | {'S3': 40} | {'GENERAL_SPECIFIC': 3, 'UNRELATED': 37} |
| pd-0dd5942e4e | SUPPLY_SERVICE | heldout | cl-ed52f83937 | 5 | 8 | — | {'S1': 1, 'S3': 24} | {'CONFLICT': 1, 'GENERAL_SPECIFIC': 5, 'UNRELATED': 19} |
| pd-0ef7060ac8 | SALES | heldout | cl-920467d2f1 | 15 | 15 | — | {'S3': 40} | {'CONFLICT': 1, 'GENERAL_SPECIFIC': 2, 'UNRELATED': 37} |
| pd-176a825fca | SALES | heldout | cl-c2c7bcdf6c | 9 | 36 | — | {'S1': 36, 'S3': 40} | {'CONFLICT': 12, 'DUPLICATE': 2, 'GENERAL_SPECIFIC': 9, 'UNRELATED': 53} |
| pd-1c0f85fee4 | SALES | heldout | cl-a00a96d219 | 8 | 23 | có | {'S1': 32, 'S2': 22, 'S3': 40} | {'CONFLICT': 1, 'DUPLICATE': 14, 'GENERAL_SPECIFIC': 7, 'UNRELATED': 72} |
| pd-1e78e105fc | SUPPLY_SERVICE | heldout | cl-66c3003368 | 12 | 12 | — | {'S3': 40} | {'UNRELATED': 40} |
| pd-21d3913039 | SUPPLY_SERVICE | heldout | cl-a1b67a0d3c | 13 | 24 | — | {'S1': 36, 'S3': 40} | {'DUPLICATE': 5, 'UNRELATED': 71} |
| pd-242e0b7a96 | SALES | heldout | cl-f73dec390c | 6 | 7 | — | {'S3': 20} | {'UNRELATED': 20} |
| pd-2e28a08bfa | SALES | heldout | cl-79aeaf564f | 12 | 14 | — | {'S1': 1, 'S3': 40} | {'GENERAL_SPECIFIC': 1, 'UNRELATED': 40} |
| pd-3d8842533f | SALES | heldout | cl-94f7b2cf53 | 6 | 6 | — | {'S3': 15} | {'CONFLICT': 1, 'GENERAL_SPECIFIC': 1, 'REFERENCE': 1, 'UNRELATED': 12} |
| pd-43cd896d78 | SUPPLY_SERVICE | heldout | cl-7e7b2d2767 | 7 | 27 | — | {'S1': 32, 'S3': 40} | {'CONFLICT': 1, 'DUPLICATE': 8, 'GENERAL_SPECIFIC': 1, 'UNRELATED': 62} |
| pd-4b7adfd987 | SUPPLY_SERVICE | heldout | cl-f9b79e7bb2 | 7 | 7 | — | {'S3': 21} | {'UNRELATED': 21} |
| pd-96be63cf8b | SALES | heldout | cl-c62f273a33 | 7 | 12 | — | {'S1': 10, 'S3': 40} | {'DUPLICATE': 7, 'GENERAL_SPECIFIC': 1, 'REFERENCE': 1, 'UNRELATED': 41} |
| pd-a3a3c94483 | SALES | heldout | cl-8b59038c24 | 12 | 42 | — | {'S1': 45, 'S3': 40} | {'CONFLICT': 11, 'DUPLICATE': 5, 'GENERAL_SPECIFIC': 6, 'UNRELATED': 63} |
| pd-ae9bb69ee7 | SALES | dev | cl-4637ce270e | 9 | 18 | — | {'S1': 7, 'S3': 40} | {'CONFLICT': 2, 'DUPLICATE': 1, 'GENERAL_SPECIFIC': 2, 'UNRELATED': 42} |
| pd-b300e5ad70 | SUPPLY_SERVICE | dev | cl-0fa3021b56 | 5 | 5 | — | {'S3': 10} | {'GENERAL_SPECIFIC': 1, 'REFERENCE': 1, 'UNRELATED': 8} |
| pd-b6d8628d32 | SUPPLY_SERVICE | dev | cl-6ef7261d72 | 13 | 24 | — | {'S1': 46, 'S3': 40} | {'DUPLICATE': 4, 'GENERAL_SPECIFIC': 4, 'UNRELATED': 78} |
| pd-bf1d9346b4 | SALES | dev | cl-1027a3caf6 | 7 | 16 | — | {'S1': 13, 'S3': 40} | {'DUPLICATE': 1, 'GENERAL_SPECIFIC': 4, 'UNRELATED': 48} |
| pd-e0d65645f2 | SUPPLY_SERVICE | dev | cl-61cf8fa90c | 8 | 8 | — | {'S3': 28} | {'UNRELATED': 28} |
| pd-eec95ad3b2 | SUPPLY_SERVICE | dev | cl-d10ad02902 | 5 | 13 | — | {'S1': 28, 'S3': 40} | {'CONFLICT': 2, 'DUPLICATE': 1, 'GENERAL_SPECIFIC': 3, 'UNRELATED': 62} |
| pd-fa299625d8 | SUPPLY_SERVICE | dev | cl-b8007cde81 | 7 | 9 | — | {'S3': 34} | {'CONFLICT': 2, 'GENERAL_SPECIFIC': 1, 'UNRELATED': 31} |
