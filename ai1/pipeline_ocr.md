Kiến trúc hiện tại có hai phần độc lập: OCR tạo nội dung/bảng theo từng trang, sau đó bộ continuity quyết định bảng giữa hai trang có liên quan hay không.

```text
Frontend upload PDF
        ↓
Backend tạo OCR task
        ↓ Kafka: ai1.ocr.command
AI1 worker
        ↓
ProcessDocument
        ├─ PDF có text layer tốt → PyMuPDF
        └─ PDF scan/mixed       → render ảnh → Mistral OCR
                                      ↓
                             full-page Markdown
                             + ordered blocks/bbox
                                      ↓
                         Parse table theo từng trang
                                      ↓
                              BuildSnapshot
                                      ↓
                    Table Continuity giữa các trang
                       MERGE / SPLIT / NEEDS_REVIEW
                                      ↓
                           ai1.snapshot.v1
                                      ↓ Kafka
                  Backend persist → AI2 → Frontend
```

## 1. Điểm bắt đầu OCR

Backend gửi OCR task qua Kafka. AI1 worker nhận task và chạy tại:

- [`backend_ocr_job.py`](</D:/AI Thuc Chien/Contract Intelligence/contract-intelligence-core/ai-service/src/contract_ocr/infrastructure/backend_ocr_job.py:244>)
- [`process_document.py`](</D:/AI Thuc Chien/Contract Intelligence/contract-intelligence-core/ai-service/src/contract_ocr/application/use_cases/process_document.py:17>)

`ProcessDocument` phân loại từng trang:

- Trang có text layer tốt: lấy nội dung trực tiếp bằng PyMuPDF.
- Trang scan hoặc mixed: render thành ảnh, preprocessing rồi đưa cho OCR engine.
- Engine đang dùng cho scan là Mistral.

Với Mistral, logic nằm tại:

- [`mistral_ocr.py`](</D:/AI Thuc Chien/Contract Intelligence/contract-intelligence-core/ai-service/src/contract_ocr/infrastructure/ocr/mistral_ocr.py:42>)

## 2. Nội dung OCR và bbox được xử lý thế nào?

Luồng hiện tại đã tách nội dung và hình học:

```text
Mistral full-page markdown ───────→ source of truth cho text
Mistral ordered blocks + bbox ───→ source of truth cho vị trí
```

Cụ thể tại [`mistral_ocr.py`](</D:/AI Thuc Chien/Contract Intelligence/contract-intelligence-core/ai-service/src/contract_ocr/infrastructure/ocr/mistral_ocr.py:109>):

1. Gửi toàn bộ ảnh trang đến `client.ocr.process()`.
2. Yêu cầu:

   - `include_blocks=True`
   - `confidence_scores_granularity="block"`

3. Lưu toàn bộ markdown gốc thành `raw.md`.
4. Tạo nội dung line từ full-page markdown.
5. Tìm block có text tương ứng để gắn bbox.
6. Nếu không tìm được bbox, line vẫn được giữ lại nhưng không có bbox.

Vì vậy bbox không còn quyết định line nào được giữ. Điều này ngăn lỗi “OCR full text đúng nhưng dựng clause bị rơi chữ do crop/bbox”.

## 3. Bảng trong từng trang được tạo ở đâu?

Với Mistral, bảng không được OCR lại theo từng cell.

Mistral trả block có:

```text
type = table
content = Markdown pipe table
bbox = vị trí toàn bảng
```

Parser nằm tại:

- [`markdown_tables.py`](</D:/AI Thuc Chien/Contract Intelligence/contract-intelligence-core/ai-service/src/contract_ocr/infrastructure/ocr/markdown_tables.py:1>)

Quy trình:

```text
Mistral table block
        ↓
Parse Markdown:
| STT | Nội dung | Giá trị |
|-----|----------|---------|
| 1   | ...      | ...     |
        ↓
Tách header và rows
        ↓
Chuẩn hóa số cột
        ↓
Tạo Table / Row / Cell
```

Các xử lý đáng chú ý:

- Pipe đã escape `\|` không bị tách nhầm thành cột mới.
- Dòng thiếu cell được bổ sung cell rỗng ở cuối, không làm lệch các cột sau.
- Nội dung cell lấy từ Markdown của Mistral.
- Bbox toàn bảng là bbox thật của block Mistral: `MEASURED`.
- Bbox cell hiện được chia đều từ bbox toàn bảng: `CLAIMED`, không được coi là tọa độ cell chính xác.

Trong [`process_document.py`](</D:/AI Thuc Chien/Contract Intelligence/contract-intelligence-core/ai-service/src/contract_ocr/application/use_cases/process_document.py:137>), nếu Mistral đã trả `recognized.tables`, hệ thống sử dụng trực tiếp các bảng đó.

Chỉ khi OCR engine không trả bảng, hệ thống mới dùng fallback:

- [`extract_scanned_tables.py`](</D:/AI Thuc Chien/Contract Intelligence/contract-intelligence-core/ai-service/src/contract_ocr/application/use_cases/extract_scanned_tables.py:1>)
- [`table_grid.py`](</D:/AI Thuc Chien/Contract Intelligence/contract-intelligence-core/ai-service/src/contract_ocr/infrastructure/image/table_grid.py:1>)

Fallback này:

1. Dùng OpenCV tìm đường kẻ ngang/dọc.
2. Dựng grid.
3. Gán OCR line vào cell theo tâm bbox.
4. Không OCR lại từng crop cell.

Nó chỉ hỗ trợ tốt bảng có đường viền; bảng borderless phụ thuộc vào table block của Mistral.

## 4. Nối bảng xuyên trang nằm ở đâu?

Logic chính nằm tại:

- [`table_continuity.py`](</D:/AI Thuc Chien/Contract Intelligence/contract-intelligence-core/ai-service/src/contract_ocr/application/use_cases/table_continuity.py:57>)
- Được gọi từ [`build_snapshot.py`](</D:/AI Thuc Chien/Contract Intelligence/contract-intelligence-core/ai-service/src/contract_ocr/application/use_cases/build_snapshot.py:165>)

Hệ thống chỉ so sánh:

```text
Bảng cuối trang N
        với
Bảng đầu trang N+1
```

Nếu trang giữa không có bảng thì chuỗi continuity bị ngắt.

### Bước 1: Hard guards

Các trường hợp chắc chắn không nối:

- Bảng trước đã có dòng “Tổng”, “Tổng cộng”, “Total”.
- Bảng sau bắt đầu sau một heading/phụ lục mới.
- Cột STT của bảng sau quay lại `1` trong khi bảng trước đang ở số lớn hơn.
- Số cột khác nhau.
- Hai bảng không nằm gần cuối trang trước và đầu trang sau.

Kết quả là `SPLIT`.

### Bước 2: Tính điểm continuity

Nếu vượt qua hard guards:

- Cùng số cột và đúng vị trí mép trang: `+0.5`
- Header lặp lại: `+0.3`
- STT liên tục, ví dụ trang trước kết thúc `5`, trang sau bắt đầu `6`: `+0.3`
- Không lặp header: chỉ thêm `+0.1`

Ngưỡng:

```text
score >= 0.75  → MERGE
score <= 0.35  → SPLIT
còn lại        → NEEDS_REVIEW
```

Nếu bật `table_continuity_agent`, trường hợp mơ hồ có thể được gửi cho DeepSeek để phân loại. Mặc định tính năng này tắt.

## 5. Điểm quan trọng: hiện tại “MERGE” chưa ghép vật lý rows

Trong luồng production `BuildSnapshot`, kết quả hiện tại chỉ sinh metadata:

```json
{
  "from_table_id": "...p001-t001",
  "to_table_id": "...p002-t001",
  "decision": "MERGE",
  "confidence": 0.8,
  "reason_codes": [
    "TABLE_COLUMN_MATCH",
    "REPEATED_TABLE_HEADER"
  ]
}
```

Nó không biến hai bảng thành một mảng rows duy nhất. Hai bảng vẫn nằm riêng trong `pages[].tables[]`, còn quan hệ nối nằm trong `table_continuity[]`.

Có một implementation khác có khả năng ghép vật lý:

- [`reconstruction/table_merger.py`](</D:/AI Thuc Chien/Contract Intelligence/contract-intelligence-core/ai-service/src/contract_ocr/reconstruction/table_merger.py:137>)

Implementation này có thể:

- Bỏ header bị lặp ở trang sau.
- Ghép hai nửa của một row bị cắt qua trang.
- Nối text cùng cell mà không bỏ phần bên trái hoặc bên phải.
- Giữ provenance của cả hai trang.

Nhưng pipeline này thuộc hệ `reconstruction`, hiện chưa được nối vào đường chạy Mistral → `BuildSnapshot`. Vì vậy nếu yêu cầu là “frontend nhận đúng một bảng đã nối hoàn chỉnh”, hệ thống hiện chưa làm đến bước đó; nó mới chỉ đánh dấu `MERGE`.

## 6. Output cuối cùng

`BuildSnapshot` tạo `ai1.snapshot.v1` tại:

- [`build_snapshot.py`](</D:/AI Thuc Chien/Contract Intelligence/contract-intelligence-core/ai-service/src/contract_ocr/application/use_cases/build_snapshot.py:98>)

Cấu trúc chính:

```json
{
  "pages": [
    {
      "text": "...",
      "lines": [],
      "tables": []
    }
  ],
  "table_continuity": [
    {
      "from_table_id": "...",
      "to_table_id": "...",
      "decision": "MERGE"
    }
  ],
  "nodes": []
}
```

Kết luận ngắn:

- OCR text: lấy từ full-page Markdown của Mistral.
- Bbox: chỉ dùng map vị trí.
- Bảng từng trang: parse từ Mistral table block.
- Nối bảng xuyên trang: `table_continuity.py`.
- Production hiện chỉ link `MERGE/SPLIT`, chưa ghép vật lý rows thành một bảng duy nhất.
- Code ghép vật lý đã có trong `reconstruction/table_merger.py`, nhưng chưa được wire vào luồng Mistral hiện tại.