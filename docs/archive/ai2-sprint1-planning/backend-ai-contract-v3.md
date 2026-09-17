# Contract kỹ thuật: Backend ↔ AI Service
**Dự án:** Contract Intelligence (PROD-01) | **Phiên bản:** v0.3
**Thay đổi so với v0.2:** đính chính theo phản hồi chính thức của AI Engineer (`BACKEND_CONTRACT_RESPONSE_v0.1.md`) — đổi tên engine, xác nhận confidence per-field, xác nhận bbox 0-1, cập nhật trạng thái triển khai thực tế phía AI Service, và đánh dấu rõ các mục vẫn đang chờ quyết định (không tự chốt khi chưa có xác nhận).

---

## 0. Trạng thái triển khai thực tế (quan trọng — đọc trước khi code)

> Theo xác nhận của AI Engineer: codebase hiện tại (`contract_ocr` / OCR Lab) **chỉ là công cụ benchmark engine**, chưa phải bản triển khai contract này. Cụ thể AI Service **hiện chưa có**:
> - Endpoint bất đồng bộ `POST /extract`, `POST /detect-conflicts` (hiện chỉ có `POST /api/ocr` đồng bộ, dùng nội bộ)
> - Hàng đợi async (Redis + worker) — hiện xử lý đồng bộ trong process
> - Callback client gọi ngược `callback_url` của Backend
> - Enforce `is_sensitive` (chưa có flag này ở đâu trong hệ thống)
> - Cascade engine tự động (native → Terra Light → PaddleOCR) — hiện phải chọn thủ công 1 engine
> - Tầng Structuring (clause phân cấp) và Citation extraction — chưa xây

**Khuyến nghị cho Backend:** không chờ AI Service hoàn thiện mới bắt đầu code. Dựng 1 **mock server** trả đúng response theo contract này (mục 2, 3) để phát triển và test Backend song song. Khi AI Service thật sẵn sàng, chỉ cần đổi `AI_SERVICE_URL` trỏ sang service thật.

---

## 1. Nguyên tắc chung

- Backend và AI Service nằm **cùng 1 repo** (`contract-intelligence-core`) nhưng chạy như **2 process/service độc lập**, giao tiếp qua **HTTP REST nội bộ**.
- Port đã xác nhận: AI Service `8001`, gọi qua service name `ai-service` trong `docker-compose.yml`.
- Xử lý bất đồng bộ qua callback: AI Service nhận job, xử lý nền, gọi ngược `callback_url` khi xong.
- Toàn bộ response lỗi theo format thống nhất ở mục 5.

### ⚠️ Timeout — CHƯA CHỐT, không hard-code

AI Engineer xác nhận: **chưa có số đo benchmark thật cho Terra Light**. Con số 90s ở bản v0.2 là ước tính từ Terra bản đầy đủ, không áp dụng được cho Terra Light.

**Yêu cầu bắt buộc:** Backend đọc timeout qua biến môi trường (`OCR_TIMEOUT_SECONDS`, mặc định tạm 90s), **không hard-code trong logic** — để khi AI Service gửi số liệu thật, chỉ cần đổi config, không sửa code.

---

## 2. Interface 1: OCR / IDP Extraction

### Request

`POST http://ai-service:8001/extract`

```json
{
  "contract_id": "c1a2b3c4-uuid",
  "file_url": "https://storage.internal/contracts/c1a2b3c4.pdf",
  "is_sensitive": false,
  "callback_url": "http://backend:8000/internal/extraction-callback"
}
```

*(Không đổi so với v0.2 — AI Engineer chưa phản hồi riêng về field này, giữ nguyên.)*

### Response ngay lập tức (202 Accepted)

```json
{ "contract_id": "c1a2b3c4-uuid", "status": "accepted" }
```

### Callback khi xử lý xong — `POST {callback_url}`

```json
{
  "contract_id": "c1a2b3c4-uuid",
  "status": "success",
  "engine_used": "gpt-5.6-terra-light",
  "pages": [
    { "page_number": 1, "width": 1240, "height": 1754 }
  ],
  "clauses": [
    {
      "clause_id": "temp-001",
      "level": "DIEU",
      "parent_temp_id": null,
      "order": 1,
      "text": "Điều 1. Đối tượng hợp đồng",
      "bbox": { "page": 1, "x": 0.097, "y": 0.114, "width": 0.645, "height": 0.023 },
      "confidence": 0.95
    }
  ],
  "appendix_tables": [
    {
      "table_id": "temp-t01",
      "page": 3,
      "bbox": { "page": 3, "x": 0.081, "y": 0.228, "width": 0.726, "height": 0.171 },
      "rows": [["Hạng mục", "Số lượng", "Đơn giá"], ["...", "...", "..."]]
    }
  ],
  "citations": [
    {
      "clause_temp_id": "temp-002",
      "value_type": "MONEY",
      "value": "500,000,000 VNĐ",
      "bbox": { "page": 1, "x": 0.242, "y": 0.148, "width": 0.121, "height": 0.011 },
      "confidence": 0.91
    }
  ]
}
```

### ✅ Đã chốt (theo phản hồi AI Engineer)

| Field | Chốt |
|---|---|
| `engine_used` | Enum: `native`, `gpt-5.6-terra-light`, `paddle-ocr` — **đã đổi từ `gpt-5.6-luna`** |
| `confidence` | Trả **per-field** (theo từng clause/citation), không phải 1 số cho cả hợp đồng |
| `bbox` | **Tỷ lệ chuẩn hoá 0–1** theo width/height trang (không phải pixel, không phải %) — Backend lưu đúng định dạng này vào DB (khớp yêu cầu bbox chuẩn hoá trong DOC-04 v0.3) |

### ⚠️ Điểm cần Backend quyết định và phản hồi lại AI Engineer

- [ ] **FE có cần bbox ở định dạng khác (pixel/%) không?** AI Service có thể quy đổi thêm ở tầng response nếu cần — Backend cần hỏi Trang rồi trả lời AI Engineer, tránh để treo 2 chiều.

### ⚠️ Điểm còn treo — chưa chốt (không tự giả định)

- [ ] Format `appendix_tables` khi bảng có merged cells — cần thêm 1 buổi trao đổi riêng (AI Engineer xác nhận rõ "chưa chốt").

### Response lỗi
Mã lỗi: `OCR_FAILED`, `UNSUPPORTED_FILE_FORMAT`, `FILE_TOO_LARGE`, `TIMEOUT`, `LOW_CONFIDENCE_EXTRACTION`.

---

## 3. Interface 2: Conflict Detection

Xác nhận: đây là worker riêng phía AI Service (dùng LLM), Backend **chỉ nhận kết quả qua callback**, không tự làm rule-based.

### Request

`POST http://ai-service:8001/detect-conflicts`

```json
{
  "contract_id": "c1a2b3c4-uuid",
  "clauses": [
    { "clause_id": "real-101", "text": "...", "value_type": "MONEY", "value": "500,000,000" },
    { "clause_id": "real-205", "text": "...", "value_type": "MONEY", "value": "450,000,000" }
  ],
  "callback_url": "http://backend:8000/internal/conflict-callback"
}
```

### Callback kết quả

```json
{
  "contract_id": "c1a2b3c4-uuid",
  "status": "success",
  "conflicts": [
    {
      "clause_id_a": "real-101",
      "clause_id_b": "real-205",
      "conflict_type": "AMOUNT_MISMATCH",
      "description": "Số tiền tại Điều 3 không khớp với Phụ lục 1",
      "confidence": 0.92
    }
  ]
}
```

### ⚠️ Điểm còn treo — chưa chốt

- [ ] **Danh sách đầy đủ `conflict_type`** — AI Engineer sẽ gửi kèm bản nháp Structuring đầu tiên. **Chương cần chủ động hỏi mốc thời gian cụ thể** cho bản nháp này, tránh chờ vô thời hạn.
- [ ] **Thời điểm trigger Conflict Detection** (tự động ngay sau `extracted`, hay chờ Reviewer xác nhận clause trước) — cần quyết định **3 bên**: Backend + AI Engineer + Team Leader (Trang). Chương nên chủ động đề xuất lịch họp 3 bên.

---

## 4. Bảo mật (theo DOC-04 §9, nhắc lại vì AI Service xác nhận CHƯA có enforcement)

- Backend **luôn phải gửi đúng `is_sensitive`** trong mọi request `/extract`.
- **Lưu ý rủi ro hiện tại:** AI Engineer xác nhận flag này "chưa có ở đâu trong hệ thống" phía AI Service — nghĩa là dù Backend gửi đúng, AI Service **chưa enforce được** cho tới khi họ implement xong (được liệt là hạng mục bảo mật ưu tiên cao). Backend nên theo dõi tiến độ mục này sát sao vì đây là rủi ro compliance, không chỉ rủi ro kỹ thuật.
- Backend không log nội dung file/text trả về — chỉ log `contract_id`, `status`, `engine_used`, timestamp.
- API key OpenAI chỉ nằm ở phía AI Service.

---

## 5. Format lỗi chung

```json
{
  "contract_id": "c1a2b3c4-uuid",
  "status": "error",
  "error": {
    "code": "OCR_FAILED",
    "message": "Không thể đọc file, file có thể bị hỏng hoặc scan mờ",
    "retryable": true
  }
}
```

---

## 6. Việc cần 2 bên tiếp tục chốt (tổng hợp từ phản hồi AI Engineer)

- [ ] Định dạng bbox cuối cùng cho FE hiển thị (0–1 giữ nguyên khi lưu, nhưng FE cần gì khi render?)
- [ ] Format `appendix_tables` khi có merged cells
- [ ] Danh sách `conflict_type` đầy đủ + mốc thời gian nhận bản nháp Structuring
- [ ] Thời điểm trigger Conflict Detection (họp 3 bên: Backend + AI Engineer + Trang)
- [ ] Timeout chính thức cho Terra Light (chờ AI Engineer benchmark xong — Backend dùng giá trị config tạm, không hard-code)

## 7. Checklist trước khi implement

- [ ] Dựng mock server FastAPI giả lập đúng response ở mục 2, 3 để code Backend song song trong lúc AI Service chưa xong
- [ ] `OCR_TIMEOUT_SECONDS` đọc từ env var, không hard-code
- [ ] Backend implement sẵn 2 callback endpoint: `/internal/extraction-callback`, `/internal/conflict-callback`
- [ ] Theo dõi tiến độ AI Service theo đúng thứ tự đã công bố ở mục 0 (endpoint async → queue → callback → is_sensitive → cascade engine → Structuring/Citation) để biết khi nào tích hợp thật khả thi
