# Tổng hợp độ chính xác OCR (AI1) — test-contract.pdf, 202 trang

## 1. Điều kiện thử nghiệm

| Hạng mục | Giá trị |
|---|---|
| Tài liệu | Hợp đồng liên danh ba bên (tổng hợp): hợp đồng chính 41 trang (92 Điều, 1.291 khoản) + 10 phụ lục (161 trang); 11 bảng logic (1.536 hàng); 42 mâu thuẫn cài sẵn (84 giá trị) |
| Ảnh scan | Xám, 150 DPI (1241×1754 px/trang A4), JPEG chất lượng ≈ 32 (ước lượng từ bảng lượng tử), nhiễu hạt, xoay ngẫu nhiên ±0,35° |
| Cỡ chữ | Nội dung 7,2 pt · ô bảng 6,3 pt (font hẹp) · header chạy 6 pt |
| Pipeline | AI1 production `mistral_verified` (đọc chính `mistral-ocr-2512`), `AI1_COST_MODE=budget`, render 150 DPI, chạy trực tiếp không qua backend |
| Ground truth | Lớp chữ của PDF gốc do bộ sinh dữ liệu tạo, căn 1:1 theo trang (202/202 ảnh trang trùng khớp) |
| Cách so | Chuẩn hoá khoảng trắng; hàng bảng dạng Markdown (`\| a \| b \|`) được tách thành từng ô trước khi so |

## 2. Kết quả tổng

| Chỉ số | Kết quả | Mẫu |
|---|---:|---:|
| Độ chính xác ký tự (1 − CER, chuẩn hoá khoảng trắng) | **99,43%** | 1.255.854 ký tự |
| Độ chính xác ký tự thô (1 − CER) | 99,25% | |
| Độ chính xác từ (1 − WER) | **98,99%** | 293.232 từ |
| Độ chính xác dấu tiếng Việt (chữ cái đúng dấu) | **99,80%** | |
| Critical field (số tiền, số lượng, %, ngày, MST, số HĐ) | 95,02% | 2.939 / 3.093 |
| Critical field, không tính số HĐ ở header | **99,86%** | 2.886 / 2.890 |
| Dòng đúng hoàn toàn (trang không có bảng) | 84,89% | 8.382 / 9.874 |
| Trang đạt ≥ 99% ký tự | 92,57% | 187 / 202 |
| Trang đạt ≥ 99,5% ký tự | 68,81% | 139 / 202 |
| Trung vị độ chính xác ký tự theo trang | 99,55% | |
| Trang thấp nhất | 90,56% (tr. 32) | |
| Chữ bị mất (đoạn liền ≥ 40 ký tự) | 924 ký tự = 0,074% | 2 đoạn (tr. 32, 62), 0 đoạn được cảnh báo |
| Trạng thái trang | SUCCESS 12 · PARTIAL 190 · FAILED 0 | 202 |
| Thời gian | 592 s OCR + 79 s dựng snapshot = 671 s | 3,3 s/trang · ~18 trang/phút |

## 3. Theo từng phần

| Phần | Trang | Số trang | Ký tự | Từ | Dấu | Critical field | Critical field (không tính số HĐ ở header) |
|---|---|---:|---:|---:|---:|---:|---:|
| Hợp đồng chính | 1–41 | 41 | 99,36% | 99,01% | 99,87% | 92,76% (423/456) | 99,28% (411/414) |
| PL I — Yêu cầu kỹ thuật | 42–45 | 4 | 99,52% | 98,97% | 99,78% | 89,66% (26/29) | 100% (25/25) |
| PL II — Bảng giá chi tiết | 46–56 | 11 | 99,28% | 97,35% | 99,03% | 99,50% (1.805/1.814) | 99,94% (1.802/1.803) |
| PL III — Lịch thanh toán | 57–58 | 2 | 98,65% | 96,88% | 99,63% | 99,33% (148/149) | 100% (147/147) |
| PL IV — Mức dịch vụ, bảo hành | 59–61 | 3 | 99,11% | 97,42% | 99,12% | 98,81% (166/168) | 100% (165/165) |
| PL V — Nhân sự, đào tạo | 62–63 | 2 | 96,70% | 96,24% | 99,79% | 97,92% (94/96) | 100% (94/94) |
| PL VI — Xử lý sự cố | 64–195 | 132 | 99,54% | 99,18% | 99,83% | 23,48% (31/132) | — (chỉ có số HĐ ở header) |
| PL VII — An toàn thông tin | 196 | 1 | 99,64% | 99,29% | 99,89% | 100% (19/19) | 100% (18/18) |
| PL VIII — Phạt, bồi thường | 197–198 | 2 | 99,27% | 98,47% | 99,66% | 99,47% (186/187) | 100% (185/185) |
| PL IX — Thanh lý | 199–200 | 2 | 99,60% | 99,33% | 99,88% | 91,67% (11/12) | 100% (10/10) |
| PL X — Sửa đổi, bổ sung | 201–202 | 2 | 98,53% | 97,94% | 99,82% | 96,77% (30/31) | 100% (29/29) |
| **Toàn tài liệu** | 1–202 | 202 | **99,43%** | **98,99%** | **99,80%** | 95,02% (2.939/3.093) | **99,86% (2.886/2.890)** |

## 4. Critical field theo loại

| Loại | Đúng / Tổng | Độ chính xác | Ghi chú |
|---|---:|---:|---|
| Số lượng (số có phân cách hàng nghìn) | 1.962 / 1.963 | 99,95% | 1 đọc sai (tr. 55) |
| Tỉ lệ % | 595 / 596 | 99,83% | 1 thuộc đoạn bị mất tr. 32 |
| Số tiền (kèm "đồng") | 320 / 322 | 99,38% | 2 thuộc đoạn bị mất tr. 32 |
| Mã số thuế | 6 / 6 | 100% | |
| Ngày | 3 / 3 | 100% | |
| Số hợp đồng | 53 / 203 | 26,11% | 202/203 lần nằm ở header cỡ 6 pt; bị đọc lệch thành LVHÁU, LVHÀU, MOTP, HDTP… |

## 5. Bảng

| Chỉ số | Kết quả |
|---|---:|
| Hàng ground truth | 1.536 (11 bảng logic) |
| Hàng snapshot | 1.537 (29 bảng theo trang) |
| Hàng đúng hoàn toàn | **79,49%** (1.221) |
| Hàng có ít nhất một ô sai | 315 |
| Hàng thiếu / thừa | **0** / 1 |
| Độ chính xác ô | **96,24%** |

| Bảng | Hàng | Hàng đúng hoàn toàn | Độ chính xác ô |
|---|---:|---:|---:|
| Hợp đồng chính — khối chữ ký 3 bên | 2 | 1 (50,0%) | 83,33% |
| PL I — Yêu cầu kỹ thuật | 140 | 126 (90,0%) | 97,50% |
| PL II — Bảng giá, bảng 1 | 301 | 260 (86,4%) | 97,67% |
| PL II — Bảng giá, bảng 2 | 301 | 229 (76,1%) | 95,85% |
| PL II — Bảng giá, bảng 3 | 301 | 238 (79,1%) | 96,18% |
| PL III — Lịch thanh toán | 70 | 28 (40,0%) | 87,14% |
| PL IV — Mức dịch vụ | 160 | 105 (65,6%) | 94,27% |
| PL V — Nhân sự | 90 | 85 (94,4%) | 99,21% |
| PL VIII — Phạt, bồi thường | 90 | 76 (84,4%) | 96,89% |
| PL IX — Thanh lý | 80 | 73 (91,2%) | 98,25% |
| PL X — Khối chữ ký 3 bên | 1 | 0 (0%) | 0,00% |

## 6. Cấu trúc

| Hạng mục | Kết quả |
|---|---|
| Điều (hợp đồng chính) | **92/92 (100%)**, 92/92 đúng trang |
| Khoản (hợp đồng chính) | recall **99,77%** (1.288/1.291) · precision **100%**; 3 khoản thiếu (74.8–74.10) là đoạn bị mất ở tr. 32 |
| Cấu trúc phụ lục | Chưa dựng: node `CLAUSE 92.14` trải tr. 41–202, gộp cả 10 phụ lục |

## 7. Giá trị mâu thuẫn cố ý (đầu vào của AI2)

| Chỉ số | Kết quả |
|---|---:|
| Giá trị còn nguyên trên đúng trang | **84/84 (100%)** — cả 42 mâu thuẫn |

## 8. Cờ review và độ tin cậy dòng (trang không có bảng, 9.874 dòng)

| Chỉ số | Kết quả |
|---|---:|
| Dòng có ít nhất một lỗi | 1.492 (15,11%) |
| Dòng được gắn cờ review | 357 |
| Precision của cờ (dòng gắn cờ thật sự sai) | 54,06% (193/357) |
| Recall của cờ (dòng sai có cờ) | 12,94% (193/1.492) |

| Độ tin cậy dòng | Số dòng | Dòng đúng hoàn toàn |
|---:|---:|---:|
| 0,90 | 9.517 | 86,35% |
| 0,75 | 1 | 0% |
| 0,70 | 349 | 46,99% |
| 0,50 | 1 | 0% |
| 0,30 | 6 | 0% |

## 9. Ghi chú khi trích dẫn

- Một tài liệu tổng hợp, điều kiện khó hơn scan thực tế nhiều (chữ 6–7,2 pt ở 150 DPI, JPEG ≈ 32): đây là số đo chịu tải, không phải độ chính xác điển hình.
- Ground truth độc lập với OCR (lấy từ lớp chữ của PDF gốc), không phải bản OCR đã sửa tay.
- Chế độ `budget`: bản đọc thứ hai chỉ chạy trên một phần trang; pipeline sửa được 54/1.597 lỗi chỉ-khác-dấu của bản đọc thô 2512 (3,4%).
- Lỗi chủ yếu là thay bằng chữ hợp lệ khác dấu: sổ→số (258), két→kết (154), BÊN→BÈN (142), đề→để (122).
- Chi phí API chưa được đo trong lần chạy này.
