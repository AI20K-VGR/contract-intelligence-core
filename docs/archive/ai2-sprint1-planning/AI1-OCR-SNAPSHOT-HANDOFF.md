# Yêu cầu bàn giao OCR Snapshot từ AI1 cho AI2

**Mục đích:** AI2 dùng OCR snapshot để trích fact, tạo citation, audit OCR/bbox và so sánh giữa hợp đồng với phụ lục.  
**Phạm vi AI1:** OCR/layout/provenance. AI1 không cần phát hiện conflict hoặc quyết định pháp lý.

## 1. Gói bàn giao cần có

1. Ít nhất một dossier gồm **1 hợp đồng + 1 phụ lục**.
2. Một mẫu PDF có `TEXT_LAYER` và một mẫu PDF `SCANNED_OCR`.
3. JSON OCR snapshot cho từng document.
4. Ảnh trang/PDF nguồn ở storage nội bộ để UI render overlay bbox; không commit nguồn thật hoặc PII lên GitHub.
5. Dossier manifest xác nhận document nào là `contract` và document nào là `annex`.

## 2. Document snapshot tối thiểu

```json
{
  "schema_version": "ai1.snapshot.v1",
  "snapshot_id": "ocr-run-20260916-001",
  "source_digest": "sha256:...",
  "dossier_id": "dossier-001",
  "document_id": "contract-001",
  "filename": "hop-dong.pdf",
  "document_role": "contract",
  "input_type": "TEXT_LAYER",
  "engine": { "name": "pymupdf", "version": "1.28.2" },
  "page_count": 7,
  "processing_ms": 220,
  "pages": []
}
```

- Re-OCR phải tạo `snapshot_id` mới; không ghi đè snapshot cũ.
- `source_digest` là SHA-256 của file nguồn.
- `document_role` do intake/BE/leader xác nhận, không suy từ tên file.
- `input_type`: `TEXT_LAYER`, `SCANNED_OCR`, hoặc `MIXED`; với `MIXED`, mỗi trang khai báo type riêng.

## 3. Page, line và word geometry bắt buộc

```json
{
  "page_number": 1,
  "status": "SUCCESS",
  "input_type": "TEXT_LAYER",
  "source_page_width": 595,
  "source_page_height": 842,
  "rotation_degrees": 0,
  "page_image_ref": {
    "uri": "storage://ocr/ocr-run-20260916-001/page-001.png",
    "width_px": 1785,
    "height_px": 2526
  },
  "text": "HỢP ĐỒNG\\n...",
  "lines": [
    {
      "line_id": "contract-001:s1:p001:l001",
      "text": "Điều 1. Giá trị hợp đồng",
      "page_char_start": 0,
      "page_char_end": 27,
      "bbox_normalized": [0.10, 0.20, 0.62, 0.23],
      "word_ids": ["contract-001:s1:p001:w001"]
    }
  ],
  "words": [
    {
      "word_id": "contract-001:s1:p001:w001",
      "line_id": "contract-001:s1:p001:l001",
      "text": "Điều",
      "line_char_start": 0,
      "line_char_end": 4,
      "bbox_normalized": [0.10, 0.20, 0.17, 0.23],
      "confidence": null
    }
  ],
  "warnings": [],
  "error": null
}
```

### Quy ước bắt buộc

```text
bbox_normalized = [x0, y0, x1, y1]
0 ≤ x0 < x1 ≤ 1; 0 ≤ y0 < y1 ≤ 1
origin = góc trên-trái
offset = Unicode code point, 0-based, end-exclusive
```

Offset luôn tính trên raw OCR text; không normalize/reformat text trước khi tính offset.

## 4. Block, clause region và bảng

AI1 nên trả thêm `blocks[]` (heading/paragraph, line IDs, reading order, bbox). AI2 có thể gộp line bbox thành clause-region bbox ở giai đoạn đầu, nhưng output tích hợp cuối phải có bbox vùng Điều/Khoản/Điểm.

Với bảng, không trả một text blob. Cần biểu diễn bảng thành `tables[] → rows[] → cells[]`, mỗi cell có text và bbox:

```json
{
  "table_id": "contract-001:s1:p004:t001",
  "bbox_normalized": [0.08, 0.42, 0.93, 0.75],
  "rows": [
    {
      "row_id": "contract-001:s1:p004:t001:r001",
      "cells": [
        {
          "cell_id": "contract-001:s1:p004:t001:r001:c002",
          "text": "300.000.000.000 VNĐ",
          "bbox_normalized": [0.42, 0.42, 0.82, 0.47]
        }
      ]
    }
  ]
}
```

## 5. Các trường hợp cần thể hiện

| Trường hợp | Mong đợi output |
|---|---|
| PDF text layer | `TEXT_LAYER`, text + word/line bbox native geometry |
| PDF scan | `SCANNED_OCR`, text + confidence + word/line bbox |
| Trang trắng | `SUCCESS`, text/geometry rỗng, warning `blank_page` |
| OCR một phần | `PARTIAL`, giữ phần đọc được và warning cụ thể |
| OCR lỗi | `FAILED`, có error code/message; job không biến mất |
| Trang xoay | Có `rotation_degrees`; bbox theo frame đã xoay thẳng |
| Trang có bảng | Table/row/cell và bbox tương ứng |
| Re-OCR | Snapshot mới, snapshot cũ vẫn truy vấn được |

## 6. Tiêu chí AI2 nghiệm thu handoff

AI2 có thể bắt đầu binding/audit khi xác nhận được:

1. Một value truy ngược được `document → page → line → character span → word/line bbox`.
2. Bbox render đúng trên ảnh trang gốc.
3. Một finding contract–annex có thể mang citation từ cả hai phía.
4. Có một trang text-layer và một trang scan theo cùng output shape.
5. Re-OCR không thay đổi snapshot cũ.
6. Trang thiếu text/geometry có warning/error rõ, để AI2 trả `insufficient_evidence` thay vì suy đoán.
7. Có engine/version, thời gian chạy, input type và source digest phục vụ audit.

## 7. Ngoài phạm vi AI1 ở đợt bàn giao này

- Trích fact nghiệp vụ (`price`, `quantity`, `date`, `party`...).
- Ghép contract với annex.
- Phát hiện xung đột hoặc quyết định precedence/hiệu lực pháp lý.
- Reviewer workflow/HITL.

Các phần trên thuộc AI2, Backend và Frontend.
