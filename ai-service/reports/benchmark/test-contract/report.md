# Benchmark OCR — test-contract.pdf so với ground truth

Snapshot `ocr-run-rerun-20260929-022825`, AI1_COST_MODE=`budget`. 202 trang snapshot / 202 trang ground truth.

1566 dòng của snapshot là hàng bảng dạng Markdown (`| a | b |`); chúng được tách thành từng ô trước khi so, vì lớp chữ ground truth liệt kê mỗi ô một dòng.

## Chất lượng chữ

| CER | WER | CER chuẩn hoá | WER chuẩn hoá | CER bỏ khác biệt dấu gạch/nháy | Lỗi dấu | Critical Field Accuracy | Cờ review |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.75% | 1.01% | 0.57% | 1.01% | 0.55% | 0.20% | 95.02% (2939/3093) | 425 |

| Phần | Trang bắt đầu | Số trang | CER chuẩn hoá | WER chuẩn hoá | Lỗi dấu | Critical Field |
|---|---:|---:|---:|---:|---:|---:|
| HỢP ĐỒNG CHÍNH | 1 | 41 | 0.64% | 0.99% | 0.13% | 92.76% (423/456) |
| PHỤ LỤC I — YÊU CẦU KỸ THUẬT VÀ TIÊU CHUẨN CHẤP NHẬN | 42 | 4 | 0.48% | 1.03% | 0.22% | 89.66% (26/29) |
| PHỤ LỤC II — BẢNG GIÁ CHI TIẾT | 46 | 11 | 0.72% | 2.65% | 0.97% | 99.50% (1805/1814) |
| PHỤ LỤC III — LỊCH VÀ QUY TRÌNH THANH TOÁN | 57 | 2 | 1.35% | 3.12% | 0.37% | 99.33% (148/149) |
| PHỤ LỤC IV — CAM KẾT MỨC DỊCH VỤ VÀ BẢO HÀNH DỊCH VỤ | 59 | 3 | 0.89% | 2.58% | 0.88% | 98.81% (166/168) |
| PHỤ LỤC V — DANH MỤC NHÂN SỰ VÀ ĐÀO TẠO | 62 | 2 | 3.30% | 3.76% | 0.21% | 97.92% (94/96) |
| PHỤ LỤC VI — QUY TRÌNH XỬ LÝ SỰ CỐ VÀ ỨNG CỨU | 64 | 132 | 0.46% | 0.82% | 0.17% | 23.48% (31/132) |
| PHỤ LỤC VII — AN TOÀN THÔNG TIN VÀ PHÁP LÝ DỮ LIỆU | 196 | 1 | 0.36% | 0.71% | 0.11% | 100.00% (19/19) |
| PHỤ LỤC VIII — PHẠT VÀ BỒI THƯỜNG | 197 | 2 | 0.73% | 1.53% | 0.34% | 99.47% (186/187) |
| PHỤ LỤC IX — DANH MỤC VÀ TRÌNH TỰ THANH LÝ | 199 | 2 | 0.40% | 0.67% | 0.12% | 91.67% (11/12) |
| PHỤ LỤC X — SỬA ĐỔI, BỔ SUNG VÀ CÁC SẮP XẾP ĐẶC THÙ | 201 | 2 | 1.47% | 2.06% | 0.18% | 96.77% (30/31) |

10 trang có CER chuẩn hoá cao nhất:

| Trang | Phần | CER chuẩn hoá | Bảng | Trạng thái | Cờ review |
|---:|---|---:|---:|---|---:|
| 32 | 00-hop-dong-chinh.md | 9.44% | 0 | PARTIAL | 3 |
| 63 | 05-phu-luc-v-danh-muc-nhan-su-va-dao-tao.md | 7.30% | 1 | PARTIAL | 1 |
| 202 | 10-phu-luc-x-sua-doi-bo-sung-va-cac-sap-xep-dac-thu.md | 3.91% | 1 | SUCCESS | 0 |
| 61 | 04-phu-luc-iv-cam-ket-muc-dich-vu-va-bao-hanh-dich-.md | 2.70% | 1 | SUCCESS | 0 |
| 29 | 00-hop-dong-chinh.md | 2.36% | 0 | PARTIAL | 2 |
| 5 | 00-hop-dong-chinh.md | 2.12% | 0 | PARTIAL | 1 |
| 62 | 05-phu-luc-v-danh-muc-nhan-su-va-dao-tao.md | 1.73% | 1 | PARTIAL | 5 |
| 17 | 00-hop-dong-chinh.md | 1.51% | 0 | PARTIAL | 1 |
| 45 | 01-phu-luc-i-yeu-cau-ky-thuat-va-tieu-chuan-chap-nh.md | 1.40% | 1 | SUCCESS | 0 |
| 57 | 03-phu-luc-iii-lich-va-quy-trinh-thanh-toan.md | 1.39% | 1 | PARTIAL | 38 |

## Chữ bị mất

2 đoạn liền ≥ 40 ký tự có trong ground truth nhưng không có trong OCR, tổng 924 ký tự; 2 đoạn nằm trên trang không có cảnh báo mực chưa đọc (`ocr:unread_ink_lines`), tức là mất mà không ai được báo.

| Trang | Ký tự mất | Cảnh báo mực chưa đọc | Đầu đoạn (ground truth) |
|---:|---:|---|---|
| 32 | 835 | **không** |  toán; các phần còn lại giữ nguyên hiệu lực, trừ trường hợp Bên B có văn bản phản đối trong 24 quý kể từ ngày nhận được. |
| 62 | 89 | **không** | 2. Nhân sự chủ chốt đánh dấu sao; thay thế cần trình bày tương đương năng lực trở lên. V. |

## Critical field

| Loại field | Đúng / Tổng | Accuracy |
|---|---:|---:|
| CONTRACT_NUMBER | 53/203 | 26.11% |
| DATE | 3/3 | 100.00% |
| MONEY | 320/322 | 99.38% |
| PERCENTAGE | 595/596 | 99.83% |
| QUANTITY | 1962/1963 | 99.95% |
| TAX_CODE | 6/6 | 100.00% |

Field sai/thiếu (154 lần, 5 giá trị khác nhau):

- `CONTRACT_NUMBER: 1026/2026/TLT-BA/MDTP-ADQT-LVHÂU` ×150 (tr. 1, 1, 2, 4, 6, 7, 8, 9, …)
- `MONEY: 4.000.000 đồng` ×1 (tr. 32)
- `MONEY: 42.000.000 đồng` ×1 (tr. 32)
- `PERCENTAGE: 2,5%` ×1 (tr. 32)
- `QUANTITY: 10.863.000.000` ×1 (tr. 55)

## Giá trị mâu thuẫn cố ý

84/84 giá trị còn nguyên trên đúng trang OCR (0 giá trị không định vị được trong ground truth).


## Bảng

Ground truth: 11 bảng logic, 1536 hàng. Snapshot: 29 bảng theo trang, 1537 hàng.

| Hàng đúng hoàn toàn | Hàng có ô sai | Hàng thiếu | Hàng thừa | Độ chính xác ô |
|---:|---:|---:|---:|---:|
| 1221 (79.49%) | 315 | 0 | 1 | 96.24% |

| Phần | Bảng | Cột đầu | Hàng | Đúng | Có ô sai | Thiếu | Độ chính xác ô |
|---|---:|---|---:|---:|---:|---:|---:|
| 00-hop-dong-chinh.md | 1 | BÊN A / BÊN B / BÊN C | 2 | 1 | 1 | 0 | 83.33% |
| 01-phu-luc-i-yeu-cau-ky-thuat-va-tieu-ch | 1 | Mã / Hạng mục yêu cầu / Ước lượng nghiệm thu | 140 | 126 | 14 | 0 | 97.50% |
| 02-phu-luc-ii-bang-gia-chi-tiet.md | 1 | Mã / Diễn giải / ĐVT | 301 | 260 | 41 | 0 | 97.67% |
| 02-phu-luc-ii-bang-gia-chi-tiet.md | 2 | Mã / Diễn giải / ĐVT | 301 | 229 | 72 | 0 | 95.85% |
| 02-phu-luc-ii-bang-gia-chi-tiet.md | 3 | Mã / Diễn giải / ĐVT | 301 | 238 | 63 | 0 | 96.18% |
| 03-phu-luc-iii-lich-va-quy-trinh-thanh-t | 1 | Mã đợt / Nội dung gắn mốc / Tỷ lệ | 70 | 28 | 42 | 0 | 87.14% |
| 04-phu-luc-iv-cam-ket-muc-dich-vu-va-bao | 1 | Mã / Hạng mục dịch vụ / Ưu tiên | 160 | 105 | 55 | 0 | 94.27% |
| 05-phu-luc-v-danh-muc-nhan-su-va-dao-tao | 1 | STT / Họ và tên / Vai trò | 90 | 85 | 5 | 0 | 99.21% |
| 08-phu-luc-viii-phat-va-boi-thuong.md | 1 | Mã / Nhóm vi phạm / Mức phạt (đ) | 90 | 76 | 14 | 0 | 96.89% |
| 09-phu-luc-ix-danh-muc-va-trinh-tu-thanh | 1 | Mã / Nội dung kiểm tra / Bên chịu trách nhiệm | 80 | 73 | 7 | 0 | 98.25% |
| 10-phu-luc-x-sua-doi-bo-sung-va-cac-sap- | 1 | BÊN A / BÊN B / BÊN C | 1 | 0 | 1 | 0 | 0.00% |

Ví dụ hàng có ô sai (ground truth → OCR):

- `CÔNG TY TNHH SẢN XUẤT - THƯƠNG MẠI MINH ĐỨC THỊNH PHÁT ‖ CÔNG TY CỔ PHẦN TƯ VẤN - CÔNG NGHỆ ANH DŨNG QUANG THẮNG ‖ CÔNG TY TNHH TÀI CHÍNH - `<br>→ `CÔNG TY TNHH SẢN XUẤT - THƯƠNG MẠI MINH ĐỨC THỊNH PHÁT ‖ CÔNG TY CỔ PHẦN TƯ VẤN - CÔNG NGHỆ ANH DÙNG QUANG THẮNG ‖ CÔNG TY TNHH TÀI CHÍNH - `
- `YC-001 ‖ Hạng mục hồ sơ bảo hành thiết bị số 1 ‖ 19 giờ ‖ Nên có`<br>→ `YC-001 ‖ Hạng mục hồ sơ báo hành thiết bị số 1 ‖ 19 giờ ‖ Nên có`
- `YC-013 ‖ Hạng mục hồ sơ bảo hành thiết bị số 13 ‖ 21 giờ ‖ Nên có`<br>→ `YC-013 ‖ Hạng mục hồ sơ báo hành thiết bị số 13 ‖ 21 giờ ‖ Nên có`
- `YC-014 ‖ Hạng mục sổ theo dõi tài sản số 14 ‖ 46 giờ ‖ Bắt buộc`<br>→ `YC-014 ‖ Hạng mục số theo dõi tài sản số 14 ‖ 46 giờ ‖ Bắt buộc`
- `YC-028 ‖ Hạng mục hồ sơ bảo hành thiết bị số 28 ‖ 20 giờ ‖ Bắt buộc`<br>→ `YC-028 ‖ Hạng mục hồ sơ báo hành thiết bị số 28 ‖ 20 giờ ‖ Bắt buộc`
- `YC-039 ‖ Hạng mục sổ theo dõi tài sản số 39 ‖ 28 giờ ‖ Bắt buộc`<br>→ `YC-039 ‖ Hạng mục số theo dõi tài sản số 39 ‖ 28 giờ ‖ Bắt buộc`
- `YC-053 ‖ Hạng mục sổ theo dõi tài sản số 53 ‖ 41 giờ ‖ Bắt buộc`<br>→ `YC-053 ‖ Hạng mục số theo dõi tài sản số 53 ‖ 41 giờ ‖ Bắt buộc`
- `YC-055 ‖ Hạng mục hồ sơ bảo hành thiết bị số 55 ‖ 24 giờ ‖ Bắt buộc`<br>→ `YC-055 ‖ Hạng mục hồ sơ báo hành thiết bị số 55 ‖ 24 giờ ‖ Bắt buộc`

## Cấu trúc

Hợp đồng chính: trang 1–41.

| Hạng mục | Ground truth | Snapshot | Khớp |
|---|---:|---:|---:|
| Điều | 92 | 92 | 92 (đúng trang: 92) |
| Khoản (hợp đồng chính) | 1291 | 1288 | recall 99.77% · precision 100.00% |

Khoản thiếu (tối đa 40): 74.10, 74.8, 74.9

**CLAUSE 92.14** kéo dài trang 41–202: vượt qua ranh giới hợp đồng chính, nuốt nội dung phụ lục vào một node.

## Lỗi đọc hay gặp

Chỉ khác dấu:

| Đúng | OCR | Số lần |
|---|---|---:|
| sổ | số | 258 |
| két | kết | 154 |
| BÊN | BÈN | 142 |
| đề | để | 122 |
| phân | phần | 65 |
| bảo | báo | 49 |
| bản | bán | 49 |
| bản | bàn | 48 |
| giám | giảm | 43 |
| Sổ | Số | 40 |
| quyền | quyển | 31 |
| Bản | Bán | 30 |
| 1026/2026/TLT-BA/MDTP-ADQT-LVHÂU | 1026/2026/TLT-BA/MDTP-ADQT-LVHÁU | 29 |
| 1026/2026/TLT-BA/MDTP-ADQT-LVHÂU | 1026/2026/TLT-BA/MDTP-ADQT-LVHÀU | 29 |
| án | ăn | 27 |

Khác chữ:

| Đúng | OCR | Số lần |
|---|---|---:|
| nhật | nhập | 24 |
| đếm | điểm | 15 |
| phát | nhật | 11 |
| 1026/2026/TLT-BA/MDTP-ADQT-LVHÂU | 1026/2026/TLT-BA/MOTP-ADQT-LVHÂU | 6 |
| nhật | nhận | 4 |
| 1026/2026/TLT-BA/MDTP-ADQT-LVHÂU | 1026/2026/TLT-BA/MOTP-ADQT-LVHÀU | 3 |
| bản | báo | 3 |
| sao | cáo | 3 |
| B | A | 3 |
| 1026/2026/TLT-BA/MDTP-ADQT-LVHÂU | 1026/2026/TLT-BA/HDTP-ADQT-LVHÂU | 2 |
| dụng | năng | 1 |
| trì | trì. | 1 |
| thực | kế | 1 |
| hiện | trên | 1 |
| 1026/2026/TLT-BA/MDTP-ADQT-LVHÂU | 1026/2026/TLT-BA/HOTP-ADQT-LVHÂU | 1 |

## Cờ review và độ tin cậy dòng

Trên các trang không có bảng: 9874 dòng, 1492 dòng có ít nhất một lỗi (15.11%). Cờ review phủ 357 dòng: precision 54.06%, recall 12.94%.

| Cờ | Dòng | Dòng thật sự sai | Precision |
|---|---:|---:|---:|
| `needs_review:arbiter_unavailable` | 1 | 1 | 100.00% |
| `needs_review:critical_field_conflict` | 6 | 6 | 100.00% |
| `needs_review:critical_field_unverified` | 356 | 192 | 53.93% |
| `needs_review:spelling_unverified` | 1 | 1 | 100.00% |

| Độ tin cậy dòng | Dòng | Dòng sai | Tỉ lệ sai |
|---:|---:|---:|---:|
| 0.90 | 9517 | 1299 | 13.65% |
| 0.75 | 1 | 1 | 100.00% |
| 0.70 | 349 | 185 | 53.01% |
| 0.50 | 1 | 1 | 100.00% |
| 0.30 | 6 | 6 | 100.00% |
