# Phản hồi AI Service cho `backend-ai-contract-v2.md`

**Từ:** AE1 (AI Engineer) | **Gửi:** Backend team | **Phiên bản:** v0.1
**Tài liệu gốc:** `backend-ai-contract-v2.md` v0.2

---

## 1. Đính chính model OCR

Contract v0.2 ghi engine chính là **GPT-5.6 Luna**. AI Service thực tế đang dùng **GPT-5.6 Terra Light**, không phải Luna.

Đề nghị Backend cập nhật lại:
- Giá trị enum `engine_used` trong callback: đổi `"gpt-5.6-luna"` → `"gpt-5.6-terra-light"`.
- Mọi chỗ khác trong contract nhắc tới "Luna" (mục Timeout, mục §Vấn đề còn mở) hiểu là Terra Light.

## 2. Port

Xác nhận chạy đúng theo contract: AI Service lắng nghe ở **`8001`**, gọi qua service name `ai-service` trong `docker-compose.yml`.

## 3. Trả lời các điểm "còn mở" ở mục 2 (Interface OCR / IDP Extraction)

| Câu hỏi từ Backend | Trả lời |
|---|---|
| Trả `confidence` per-field hay chỉ tổng thể hợp đồng? | Per-field. Pipeline OCR hiện đã tính confidence ở cấp line và cấp word; khi lên cấp `clause`, AI Service sẽ tổng hợp confidence theo từng clause/citation, không trả một số duy nhất cho cả hợp đồng. |
| Bbox tính theo pixel hay tỷ lệ %? | **Tỷ lệ chuẩn hoá 0–1** theo chiều rộng/cao trang (không phải pixel tuyệt đối, không phải %). Nếu Backend/FE cần pixel hoặc %, AI Service có thể quy đổi thêm ở tầng response — cần Backend xác nhận định dạng FE muốn nhận trước khi chốt. |
| Format bảng phụ lục khi có merged cells? | **Chưa chốt** — cần thêm 1 vòng trao đổi riêng giữa 2 bên trước khi code song song phần `appendix_tables`. |

## 4. Timeout Terra Light

Số liệu benchmark Terra Light trên bộ 30 mẫu **chưa có** — con số 90s trong contract v0.2 vẫn là ước tính từ Terra (bản đầy đủ), chưa phải Terra Light. AI Service sẽ đo lại và gửi số liệu thật khi hoàn thành benchmark (theo kế hoạch ở DOC-04 §13), Backend chưa nên chốt cứng timeout ở mức code lúc này.

## 5. Interface 2 — Conflict Detection

- Xác nhận: Conflict Detection là worker riêng phía AI Service (dùng LLM), Backend chỉ nhận kết quả qua callback, không tự làm rule-based.
- Danh sách đầy đủ `conflict_type`: **chưa chốt**, sẽ gửi kèm khi có bản nháp đầu tiên của tầng Structuring.
- Thời điểm chạy (tự động ngay sau `extracted`, hay chờ Reviewer duyệt clause): **chưa chốt**, cần quyết định chung với Backend + Team Leader.

## 6. Trạng thái triển khai thực tế phía AI Service (để Backend nắm tiến độ)

Codebase hiện tại là OCR Lab (công cụ benchmark engine), **chưa** phải bản triển khai contract này. Cụ thể còn thiếu, sẽ làm theo thứ tự:

1. Endpoint `POST /extract`, `POST /detect-conflicts` (202 Accepted + xử lý nền) — hiện chỉ có `POST /api/ocr` đồng bộ, dùng để test nội bộ.
2. Hàng đợi async (Redis + worker) — hiện xử lý đồng bộ trong process, chưa có queue.
3. Callback client gọi ngược `callback_url` của Backend — hiện chưa có.
4. Enforce `is_sensitive` (bắt buộc route PaddleOCR, chặn gọi Terra Light) — hiện chưa có flag này ở đâu trong hệ thống, sẽ bổ sung là hạng mục bảo mật ưu tiên cao.
5. Cascade engine tự động (native → Terra Light → PaddleOCR fallback) — hiện người dùng phải tự chọn 1 engine, chưa có logic fallback tự động.
6. Tầng Structuring (dựng `clauses` phân cấp DIEU/KHOAN/DIEM) và Citation extraction (`MONEY/DATE/TAX_CODE/PARTY_NAME/CLAUSE_REF`) — chưa có, đây là phần việc mới cần xây từ đầu.

## 7. Việc cần 2 bên chốt trước khi code song song

- [ ] Định dạng bbox cuối cùng cho FE (0–1 / pixel / %).
- [ ] Format `appendix_tables` khi có merged cells.
- [ ] Danh sách `conflict_type` và thời điểm trigger Conflict Detection.
- [ ] Timeout chính thức cho Terra Light (chờ số đo thật).
- [ ] Đổi tên `gpt-5.6-luna` → `gpt-5.6-terra-light` trong toàn bộ tài liệu/contract.
