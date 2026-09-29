# Báo cáo đánh giá OCR (AI1) — test-contract.pdf, 202 trang scan

*29/09/2026 · Pipeline AI1 `mistral_verified`, chế độ `budget`, so với ground truth độc lập căn theo từng trang.*

## Kết quả chính

| Chỉ số | Kết quả |
|---|---:|
| Ký tự đúng | **99,43%** (1,26 triệu ký tự) |
| Từ đúng | **98,99%** (293 nghìn từ) |
| Đúng dấu tiếng Việt | **99,80%** |
| Critical field (không tính số HĐ ở header) | **99,86%** (2.886/2.890); tính cả: 95,02% |
| Ô bảng đúng | **96,24%**; 0/1.536 hàng bị thiếu |
| Giá trị mâu thuẫn còn nguyên (đầu vào AI2) | **84/84** |

## Tóm tắt

- Chữ được đọc đúng 99,43% ký tự và 98,99% từ, dù ảnh scan rất khó (chữ 6–7,2 pt, 150 DPI, JPEG chất lượng thấp). 187/202 trang đạt từ 99% trở lên.
- Dữ kiện AI2 cần đều còn đủ: 84/84 giá trị mâu thuẫn cố ý, số tiền và số lượng đúng 99,4–99,95%, bảng không thiếu hàng nào, 92/92 Điều đúng trang.
- **Nghiêm trọng:** hai đoạn chữ bị mất mà không có cảnh báo (trang 32 mất 835 ký tự gồm khoản 74.8–74.10, trang 62 mất 89 ký tự).
- Lỗi phổ biến nhất là thay bằng một chữ hợp lệ khác dấu (sổ→số, két→kết, BÊN→BÈN). Cờ review chỉ bắt được 12,9% số dòng sai.
- Hồ sơ này từng thất bại khi chạy qua backend, không phải do OCR mà do kết quả 14,3 MB vượt giới hạn tin nhắn Kafka 10 MiB.

## Điều kiện và phương pháp

| | |
|---|---|
| Tài liệu | Hợp đồng liên danh ba bên (tổng hợp): hợp đồng chính 41 trang (92 Điều, 1.291 khoản) và 10 phụ lục 161 trang; 11 bảng (1.536 hàng); 42 mâu thuẫn cài sẵn |
| Ảnh scan | Xám 150 DPI, JPEG chất lượng ≈ 32, nhiễu hạt, xoay ±0,35°; chữ 7,2 pt, ô bảng 6,3 pt, header 6 pt |
| Pipeline | `mistral_verified` (đọc chính `mistral-ocr-2512`), `AI1_COST_MODE=budget`, render 150 DPI, chạy trực tiếp không qua backend; 671 s (3,3 s/trang) |
| Ground truth | Lớp chữ PDF gốc của bộ sinh dữ liệu, khớp 1:1 với 202 ảnh trang, độc lập với OCR |
| Chỉ số | Ký tự = 1 − CER, từ = 1 − WER (chuẩn hoá khoảng trắng); critical field = giá trị trong ground truth xuất hiện trên đúng trang OCR; bảng so theo hàng và ô |

## Kết quả theo phần

| Phần | Trang | Ký tự | Từ | Dấu | Critical field* |
|---|---:|---:|---:|---:|---:|
| Hợp đồng chính | 1–41 | 99,36% | 99,01% | 99,87% | 99,28% (411/414) |
| PL I · Yêu cầu kỹ thuật | 42–45 | 99,52% | 98,97% | 99,78% | 100% (25/25) |
| PL II · Bảng giá chi tiết | 46–56 | 99,28% | 97,35% | 99,03% | 99,94% (1.802/1.803) |
| PL III · Lịch thanh toán | 57–58 | 98,65% | 96,88% | 99,63% | 100% (147/147) |
| PL IV · Mức dịch vụ, bảo hành | 59–61 | 99,11% | 97,42% | 99,12% | 100% (165/165) |
| PL V · Nhân sự, đào tạo | 62–63 | 96,70% | 96,24% | 99,79% | 100% (94/94) |
| PL VI · Xử lý sự cố | 64–195 | 99,54% | 99,18% | 99,83% | — |
| PL VII · An toàn thông tin | 196 | 99,64% | 99,29% | 99,89% | 100% (18/18) |
| PL VIII · Phạt, bồi thường | 197–198 | 99,27% | 98,47% | 99,66% | 100% (185/185) |
| PL IX · Thanh lý | 199–200 | 99,60% | 99,33% | 99,88% | 100% (10/10) |
| PL X · Sửa đổi, bổ sung | 201–202 | 98,53% | 97,94% | 99,82% | 100% (29/29) |
| **Toàn tài liệu** | 1–202 | **99,43%** | **98,99%** | **99,80%** | **99,86% (2.886/2.890)** |

\* Không tính số hợp đồng ở header. PL VI không có số tiền hay ngày. Ba field sai của hợp đồng chính đều nằm trong đoạn bị mất ở trang 32.

| Critical field theo loại | Đúng / Tổng | Tỉ lệ |
|---|---:|---:|
| Số lượng | 1.962 / 1.963 | 99,95% |
| Tỉ lệ % | 595 / 596 | 99,83% |
| Số tiền | 320 / 322 | 99,38% |
| Mã số thuế | 6 / 6 | 100% |
| Ngày | 3 / 3 | 100% |
| Số hợp đồng (202/203 lần ở header 6 pt) | 53 / 203 | 26,11% |

| Bảng và cấu trúc | Kết quả |
|---|---:|
| Hàng bảng đúng hoàn toàn | 79,49% (1.221/1.536) |
| Hàng bảng thiếu / thừa | 0 / 1 |
| Ô bảng đúng | 96,24% |
| Điều nhận đúng, đúng trang | 92 / 92 |
| Khoản: recall · precision | 99,77% · 100% |
| Cấu trúc 10 phụ lục | chưa dựng |

## Vấn đề phát hiện

1. **[Nghiêm trọng] Mất chữ mà không có cảnh báo.** Trang 32 mất 835 ký tự (khoản 74.8–74.10, gồm 4.000.000 đồng, 42.000.000 đồng và 2,5%); trang 62 mất 89 ký tự. Bản đọc 2512 đã bỏ sót các dòng này, bộ đo mực chưa đọc không phát hiện, và chế độ `budget` không đọc lần hai.
2. **[Nghiêm trọng] Hồ sơ lớn thất bại khi chạy qua backend.** OCR xong 202/202 trang, nhưng kết quả 14,3 MB vượt giới hạn Kafka 10 MiB (`kafka_worker.py:137`). Với mật độ chữ như hồ sơ này, mọi tài liệu khoảng từ 150 trang trở lên sẽ gặp lỗi tương tự.
3. **[Cao] Thay bằng chữ hợp lệ khác dấu.** Khoảng 1.543 từ bị sai theo kiểu này; pipeline chỉ sửa được 3,4% số lỗi của bản đọc thô. Cờ review có precision 54% và chỉ bắt được 13% số dòng sai. Hay gặp nhất: sổ→số (258), két→kết (154), BÊN→BÈN (142), đề→để (122), phân→phần (65), bảo→báo (49).
4. **[Cao] Số hợp đồng ở header chỉ đúng 26%.** Ở cỡ chữ 6 pt, `MDTP-ADQT-LVHÂU` bị đọc lệch thành LVHÁU, LVHÀU, MOTP, HDTP… trên 150/203 lần xuất hiện.
5. **[Trung bình] Sai lệch trong dữ liệu snapshot.** Phụ lục chưa có node cấu trúc (một khoản trải từ trang 41 đến 202); 1.566 dòng bảng còn cú pháp Markdown trong `lines[].text`; `processing_ms` ghi 71.255 s trong khi thời gian thực là 671 s.

## Đề xuất, theo thứ tự ưu tiên

1. Lưu kết quả OCR vào MinIO và chỉ gửi đường dẫn qua Kafka, để hồ sơ lớn không còn bị thất bại.
2. Trên mọi trang, so số dòng có mực với số dòng đọc được; nếu lệch thì đọc lại, hoặc gắn cờ và ghi rõ lý do.
3. Đo lại cùng tài liệu ở chế độ `accuracy` để biết mức giảm lỗi khác dấu và chi phí tăng thêm; bổ sung danh sách cặp chữ dễ nhầm (sổ/số, bảo/báo, đề/để) cho bước kiểm tra.
4. Dùng độ tin cậy dòng để tô vùng cần kiểm (FR-OCR-08): dòng 0,70 sai 53%, còn dòng 0,90 chỉ sai 13,7%.
5. Dựng node phụ lục, tách chữ trong dòng bảng khỏi cú pháp Markdown, và sửa cách tính `processing_ms`.

## Giới hạn của đánh giá

- Chỉ một tài liệu tổng hợp, với điều kiện khó hơn scan thực tế; đây là số đo chịu tải, không phải độ chính xác điển hình.
- Chỉ chạy chế độ `budget`; chưa đo chi phí API và chưa đo độ chính xác bbox.

## Tệp kèm theo

- `ai-service/data/generated/rerun/dos_01M3KS8KG9AHQHTY3CMC1VSB8S/test-contract.snapshot.json`
- `ai-service/data/generated/rerun/dos_01M3KS8KG9AHQHTY3CMC1VSB8S/test-contract.md`
- `ai-service/reports/benchmark/test-contract/report.md`, `results.json`
- `ai-service/scripts/benchmark_snapshot.py`, `tests/unit/test_benchmark_snapshot.py`
