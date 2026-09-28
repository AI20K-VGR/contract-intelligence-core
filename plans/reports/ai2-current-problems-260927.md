# AI2 — các vấn đề đang gặp (2026-09-27)

Câu hỏi: sau khi fact dòng OCR và chuẩn hóa LLM đã chạy, chỗ nào vẫn làm người duyệt thấy sai hoặc thấy thiếu?

Phạm vi: job replay trực tiếp `job_a4ef491109` trên hợp đồng 20 trang, và các `pipeline_run` backend đang lưu. Không gồm việc viết lại extractor.

## Xếp theo mức chặn người duyệt

### 1. Màn hình vẫn là lần chạy cũ: 1 fact

Replay trực tiếp AI2 ra 7 fact (`party_a`, `party_b`, hai MST, lịch thanh toán, hai tổng `1286400000` và `4149360000`) và một finding `COMPARABLE_DIFFERENCE`.

Backend không nhận lần chạy đó. `pipeline_run` mới nhất của `dos_01M3BPQFSXW68FGZJ1RPFMYXTY` vẫn là `facts: 1`, `findings: 0`, `evidence_issues: 5`, `ai2_evidence_ready = false`, `ai2_reason_code = REVIEW_REQUIRED`. Cùng hình với Test 4 và Test 5. Hồ sơ cover `dos_01M3A9R46PBKKKPXH49T308PR1` cũng còn `facts: 1`.

`evidence_ready` chỉ đúng khi trạng thái hoàn chỉnh là `COMPLETE` và không còn evidence issue (`backend/src/contract_intelligence/shared/ai/persistence.py:165`). Job `NEEDS_REVIEW` bị gắn `REVIEW_REQUIRED` (`persistence.py:158-160`), nên dossier không bao giờ “sẵn sàng bằng chứng” khi còn gap phụ lục.

### 2. Câu thanh toán do LLM viết lại vẫn được PASS

Dòng OCR gốc:

`4.2. Bên A thanh toán 30% trong vòng 07 ngay lam Vietc ké tú ngay ký; 40% sau khi hoàn thanh giai doan trién khai; 30% còn lái sau nghiém thu và nhân du hô so thanh toán hop lê.`

Giá trị chuẩn hóa L2:

`Bên A thanh toán 30% trong vòng 07 ngày làm việc kể từ ngày ký; 40% sau khi hoàn thành giai đoạn triển khai; 30% còn lại sau nghiệm thu và nhận đủ hồ sơ thanh toán hợp lệ.`

`GroundingGate.ground_fact` đặt `PASS` khi `raw_value` nằm trong nguồn (`ai-service/app/pipeline/grounding.py:13-16`). Nó không yêu cầu `normalized_value` là một đoạn của trang. Fact này có `review_state = PASS`, `provenance = L2`. Câu đã sửa lỗi OCR và thêm cách diễn đạt (“làm việc kể từ”, “nhận đủ hồ sơ”) không có trong dòng gốc.

MST và hai tổng vẫn `L0` vì đã là số. Tên hai bên `L2` trùng nguyên văn OCR.

### 3. Trích dẫn bảng phụ lục không xác minh được

Trong 111 citation của job mới: 101 `VALID`, 10 `UNVERIFIED`, 5 không có geometry. Các dòng không có geometry là tiêu đề cộng với bảng ở trang 1, 15, 18, 19, 20 (Phụ lục 01–04). Ô bảng được tạo với `validation_status` khởi đầu `UNVERIFIED` rồi mới verify (`ai-service/app/pipeline/ai1_snapshot_adapter.py:1142-1146`). `CitationResolver.verify` trả `UNVERIFIED` khi thiếu offset ký tự (`ai-service/app/pipeline/citations.py:107-108`) hoặc không có bảng nguồn (`citations.py:95-98`).

Hệ quả: phụ lục có số tổng đã thành fact, nhưng khối bảng đi kèm không phải citation đã kiểm.

### 4. 146 sự kiện từ khóa, trong khi chỉ có 7 fact

`extract_contract_events` gắn sự kiện khi dòng gấp dấu khớp một cụm (`ai-service/app/pipeline/contract_events.py:14-31`). Job 20 trang: `PARTY_DECLARATION` 28, `NOTICE` 14, `PRICE` 13, `ACCEPTANCE` 12, rồi `SCOPE`, `AMENDMENT`, `EFFECTIVE_TERM`, `WARRANTY` mỗi loại 10. “Bên A” trong một câu nghĩa vụ cũng thành sự kiện thông tin các bên. Đây là tín hiệu, không phải fact, và dày hơn phần fact người duyệt cần xem.

### 5. Vài hợp đồng vẫn thiếu tổng vì số không nằm trên dòng nhãn

Đã đọc OCR của sáu file đang lưu. Hợp đồng mua bán `744287578-Hợp-đồng.pdf` có dòng `Tổng cộng` đứng riêng ở trang 2, 5 và 10; số không ở cùng dòng nên không thành fact. File stress `Hop_dong_scan_stress_bang_lien_trang_khong_header.pdf` chỉ ra hai tên bên; bảng không có dòng tổng được ghi nhãn. Hai hồ sơ không có dòng OCR: `dos_01M39G25M4CHYFSR55BH2XFQNJ`, `dos_01M3A0SQMP6E7N1NYPXM3VZ28F`.

## Không phải lỗi mới

Phụ lục 02–04 là `CONTEXT_GAP` vì thân hợp đồng không gọi tên phụ lục, và không có fact giá trị thứ hai để ghép cặp. Phụ lục 01 có cặp giá và ghi `UNCONFIRMED`. Đó là hành vi đã chốt: không bịa câu “theo Phụ lục 01”, không chọn bên thắng.

## Câu hỏi còn mở

- Chạy lại pipeline qua backend cho hồ sơ 20 trang, hay chỉ cần người duyệt đọc job AI2?
- `normalized_value` không phải đoạn nguyên văn thì hạ `PASS` xuống `NEEDS_REVIEW`, hay cấm model sửa chữ OCR?

Bước tiếp theo hợp lý: hạ fact L2 khi câu chuẩn hóa không nằm trong nguồn, rồi reprocess một hồ sơ qua backend để màn hình hết kẹt ở 1 fact.
