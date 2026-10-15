# Contract graph eval — P2 address resolver

- Ground truth: `vbhn-note auto-gold (approved=false)` (chưa duyệt; không phải độ chính xác nghiệp vụ)
- Dataset: 11 cặp, manifest sha256 `f74399ae07193ba8975e2cb58e8d83af8abaaa112c00a3b9c31c24b615b05220`
- Parser: baseline (P1 spike port): items + heads; hình dạng cây: full, article-only (`article-only` chỉ báo cáo, không gate — RT-05)
- precision = UNIQUE đúng / UNIQUE; coverage = UNIQUE / items; accuracy = UNIQUE đúng / items; items = gold (op ≠ OTHER) đã ghép được slot của parser.

## Tổng

| shape | scope | items | UNIQUE | AMBIGUOUS | NOT_FOUND | UNIQUE đúng | precision | coverage | accuracy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| full | all | 69 | 65 | 0 | 4 | 63 | 63/65 (0.969; CI95 0.895–0.992) | 65/69 (0.942; CI95 0.860–0.977) | 63/69 (0.913; CI95 0.823–0.960) |
| full | multi-clause | 14 | 14 | 0 | 0 | 14 | 14/14 (1.000; CI95 0.785–1.000) | 14/14 (1.000; CI95 0.785–1.000) | 14/14 (1.000; CI95 0.785–1.000) |
| full | nd50-2021 | 26 | 26 | 0 | 0 | 26 | 26/26 (1.000; CI95 0.871–1.000) | 26/26 (1.000; CI95 0.871–1.000) | 26/26 (1.000; CI95 0.871–1.000) |
| full | nd50-2021 multi-clause | 14 | 14 | 0 | 0 | 14 | 14/14 (1.000; CI95 0.785–1.000) | 14/14 (1.000; CI95 0.785–1.000) | 14/14 (1.000; CI95 0.785–1.000) |
| article-only | all | 69 | 65 | 0 | 4 | 63 | 63/65 (0.969; CI95 0.895–0.992) | 65/69 (0.942; CI95 0.860–0.977) | 63/69 (0.913; CI95 0.823–0.960) |
| article-only | multi-clause | 14 | 14 | 0 | 0 | 14 | 14/14 (1.000; CI95 0.785–1.000) | 14/14 (1.000; CI95 0.785–1.000) | 14/14 (1.000; CI95 0.785–1.000) |
| article-only | nd50-2021 | 26 | 26 | 0 | 0 | 26 | 26/26 (1.000; CI95 0.871–1.000) | 26/26 (1.000; CI95 0.871–1.000) | 26/26 (1.000; CI95 0.871–1.000) |
| article-only | nd50-2021 multi-clause | 14 | 14 | 0 | 0 | 14 | 14/14 (1.000; CI95 0.785–1.000) | 14/14 (1.000; CI95 0.785–1.000) | 14/14 (1.000; CI95 0.785–1.000) |

## Theo method

| shape | method | UNIQUE | đúng | precision |
| --- | --- | --- | --- | --- |
| full | EXACT | 65 | 63 | 63/65 (0.969; CI95 0.895–0.992) |
| full | ANCESTOR | 0 | 0 | 0/0 (n/a) |
| full | SELF | 0 | 0 | 0/0 (n/a) |
| full | ORDER_INFERENCE | 0 | 0 | 0/0 (n/a) |
| article-only | EXACT | 21 | 19 | 19/21 (0.905; CI95 0.711–0.974) |
| article-only | ANCESTOR | 44 | 44 | 44/44 (1.000; CI95 0.920–1.000) |
| article-only | SELF | 0 | 0 | 0/0 (n/a) |
| article-only | ORDER_INFERENCE | 0 | 0 | 0/0 (n/a) |

## So với P1 baseline (RT-10)

| pair | P1 target_correct | P2 full UNIQUE đúng | P2 article-only UNIQUE đúng |
| --- | --- | --- | --- |
| nd50-2021 | 13/26 | 26/26 | 26/26 |
| tt01-2022-bct | 2/6 | 5/6 | 5/6 |
| tt119-2014-btc | 6/8 | 7/8 | 7/8 |
| tt13-2023-btc | 3/3 | 4/4 | 4/4 |
| tt130-2016-btc | 5/5 | 5/5 | 5/5 |
| tt14-2019-nhnn | 0/1 | 0/1 | 0/1 |
| tt21-2018-bct | 2/2 | 2/2 | 2/2 |
| tt23-2016-nhnn | 0/1 | 0/1 | 0/1 |
| tt26-2015-btc | 10/13 | 11/13 | 11/13 |
| tt27-2014-nhnn | 3/3 | 3/3 | 3/3 |
| tt43-2018-nhnn | 0/0 | 0/0 | 0/0 |

## full: UNIQUE sai (2)

- tt119-2014-btc [27] INSERTION khoan 5 dieu 3 (EXACT): gold `diem a khoan 4 dieu 14` ≠ pred `khoan 4 dieu 14`
- tt23-2016-nhnn [7] SUBSTITUTION khoan 3 dieu 1 (EXACT): gold `None` ≠ pred `dieu 5`

- full: ORDER_INFERENCE chốt 0 (đúng 0, sai 0); mục cha chỉ làm ngữ cảnh: 10; gold bị bỏ sót: 44; slot không ghép gold: 35

## article-only: UNIQUE sai (2)

- tt119-2014-btc [27] INSERTION khoan 5 dieu 3 (EXACT): gold `diem a khoan 4 dieu 14` ≠ pred `khoan 4 dieu 14`
- tt23-2016-nhnn [7] SUBSTITUTION khoan 3 dieu 1 (EXACT): gold `None` ≠ pred `dieu 5`

- article-only: ORDER_INFERENCE chốt 0 (đúng 0, sai 0); mục cha chỉ làm ngữ cảnh: 10; gold bị bỏ sót: 44; slot không ghép gold: 35

## Giới hạn

- Cây đích là VBHN (đã chứa phần sửa đổi), không phải văn bản gốc: INSERTION được chấm bằng địa chỉ mới (canonical), không bằng node; anchor/container được kiểm trên cây VBHN.
- Câu thao tác + head lấy từ parser baseline P1; item không được baseline phát hiện là gold bị bỏ sót (missed_gold), không phải lỗi resolver.
- ORDER_INFERENCE dựa trên giả định [ASSUMED] mục con liệt kê theo thứ tự văn bản gốc; số đúng/sai của nhánh này báo riêng.
- Gold tự trích từ chú thích VBHN (approved=false): không phải độ chính xác nghiệp vụ.
- Phụ lục: resolver đọc cả `Phụ lục số N` và số La Mã (`Phụ lục II` → `phu luc 2`); `gold.canonical_address` không đọc `số` và giữ La Mã (`phu luc ii`). Gold chỉ sinh địa chỉ phụ lục từ nhãn `Phụ lục <n>` của VBHN, bộ dữ liệu hiện không có gold phụ lục La Mã.
