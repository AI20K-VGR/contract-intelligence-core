# Tóm tắt trao đổi: AI1, AI2 và output OCR

**Ngày:** 15/09/2026  
**Phạm vi:** Làm rõ yêu cầu bài tập Contract Intelligence, trách nhiệm AI1/AI2 và data contract OCR phục vụ AI2.

## 1. Mục tiêu dự án

Hệ thống xử lý một dossier gồm một hợp đồng và `0..n` phụ lục. Hệ thống phải:

1. Nhận PDF scan và PDF có text layer.
2. OCR/trích text, cấu trúc Điều → Khoản → Điểm và bảng.
3. Trích fact có nguồn dẫn chính xác.
4. So sánh trong một tài liệu, contract–annex, annex–annex.
5. Phát hiện conflict structured và semantic.
6. Cho reviewer xác nhận, sửa, từ chối và chỉnh bbox.

Hệ thống hỗ trợ reviewer; không đưa tư vấn pháp lý, xác minh chữ ký, chỉnh PDF hay tự kết luận điều khoản nào có hiệu lực.

## 2. Yêu cầu cố định từ assignment

- Hỗ trợ cả PDF scan và text layer, phát hiện loại input theo từng trang.
- Thiết kế đa ngôn ngữ; Việt, Anh và trang song ngữ là phạm vi bắt buộc.
- Bbox bắt buộc ở ba mức: `word`, `line`, `clause region`.
- Bbox chuẩn hóa trong `[0,1]`, gốc trên-trái, kèm kích thước trang và rotation thực tế.
- Citation phải resolve được: document → page → OCR line → character span → bbox.
- Bảng phải thành rows/cells, không chỉ là blob text.
- Conflict gồm hai family: structured và semantic; ba scope: within-document, contract–annex, annex–annex.
- Sprint 1 cần: Product Vision, BRD, PRD drafts; sample set v0 + ground truth; spike OCR hai loại input; bbox trên một trang thật; kế hoạch Sprint 2–3 và câu trả lời planning.
- Sprint 2: single dossier end-to-end, clauses/citations/bboxes, HITL UI cơ bản, Architecture/API Spec.
- Sprint 3: cả hai family conflict, batch run, bbox editing, Evaluation Report có số liệu.

## 3. Phân định AI1 và AI2

| Thành phần | AI1 | AI2 |
|---|---|---|
| Nhiệm vụ chính | Đọc/số hóa PDF | Hiểu, trích fact và so sánh có ngữ cảnh |
| Input | PDF scan hoặc text layer | Snapshot OCR/layout của AI1 |
| Output | Text, word/line bbox, page metadata, table/cell geometry | Fact, context, finding, citation hai phía, rule comparison |
| Không làm | Legal/business decision, conflict semantics | OCR gốc, tự sửa raw source, suy role từ tên file |
| Reviewer | Cung cấp evidence hiển thị được | Định nghĩa hành vi finding và HITL semantics |

AI1 là dependency về chất lượng nguồn. AI2 là lớp nghiệp vụ/evidence: chỉ so sánh fact khi role, subject, unit, currency, VAT, scope và validity tương thích.

## 4. Output AI1 hiện có

Output hiện tại chứa:

```text
document_id, filename, page_count, elapsed_ms, full_text
pages[]: page_number, status, input_type, engine, model,
         processing_ms, text, line_count, geometry_available, evidence
```

Ví dụ đang là `TEXT_LAYER` với `pymupdf`; `geometry_available=true`, `native_word_count` và `native_span_count` cho thấy engine nhiều khả năng đã có toạ độ nhưng chưa serialize ra JSON.

`full_text` chỉ phục vụ search/tổng quan. AI2 dùng `pages[].text` làm nguồn chính vì giữ được `page_number`.

## 5. Bản output tối thiểu AI2 cần

Không thay output cũ; thêm metadata và geometry vào từng page:

```json
{
  "schema_version": "ai1.document.v2",
  "document_id": "contract-001",
  "snapshot_id": "contract-001:run-001",
  "source_digest": "sha256:...",
  "pages": [
    {
      "page_number": 1,
      "status": "SUCCESS",
      "input_type": "TEXT_LAYER",
      "source_page_width": 595,
      "source_page_height": 842,
      "rotation_degrees": 0,
      "text": "HỢP ĐỒNG\\n...",
      "lines": [
        {
          "line_id": "contract-001:r001:p001:l001",
          "text": "HỢP ĐỒNG",
          "page_char_start": 0,
          "page_char_end": 9,
          "bbox_normalized": [0.12, 0.08, 0.31, 0.11],
          "word_ids": ["contract-001:r001:p001:w001"]
        }
      ],
      "words": [
        {
          "word_id": "contract-001:r001:p001:w001",
          "line_id": "contract-001:r001:p001:l001",
          "text": "HỢP",
          "line_char_start": 0,
          "line_char_end": 3,
          "bbox_normalized": [0.12, 0.08, 0.20, 0.11],
          "confidence": null
        }
      ]
    }
  ]
}
```

Quy ước: `bbox_normalized=[x0,y0,x1,y1]`, giá trị `[0,1]`, origin top-left; offsets là 0-based/end-exclusive trên raw text chưa normalize.

## 6. Bản đầy đủ AI1 nên bổ sung dần

- `blocks[]`: heading/paragraph và reading order.
- `clause_regions[]`: vùng Điều/Khoản/Điểm; AI2 có thể gộp từ line bbox nếu AI1 chưa có.
- `tables[] → rows[] → cells[]`: text và bbox từng ô.
- `page_image_ref`: UI dùng ảnh nguồn để overlay bbox.
- `quality`: usable text, confidence, warning/error, blank/partial page.
- `document_structure_hints`: title, language, contract-number/annex-reference candidate.
- Re-OCR tạo `snapshot_id` mới, không ghi đè evidence cũ.

## 7. Luồng xử lý AI2 khi AI1 chỉ có OCR thuần

```text
pages[].text
→ chuẩn hóa bản dẫn xuất, giữ raw text và offset
→ parser Điều/Khoản/Điểm/bullet/table
→ fact typed: price, quantity, date, duration, party, tax_code, reference number
→ context gate/pairing
→ finding
→ reviewer action/revision
```

AI2 lưu raw OCR bất biến. Normalization, machine fact, finding, reviewer correction và ground truth là các lớp dữ liệu/version tách riêng.

Khi chưa có geometry, citation tạm chỉ ở cấp `document + page + quote + offset`; chưa đạt đề bài. Khi AI1 bổ sung line/word geometry, AI2 resolve lại citation mà không cần trích lại toàn bộ fact.

## 8. Các disposition của AI2

- `comparable_match`: context đủ và giá trị giống nhau.
- `comparable_difference`: context đủ nhưng giá trị khác.
- `candidate_amendment`: candidate kỹ thuật; cần reference, wording sửa đổi, scope phù hợp và ngày hiệu lực sau.
- `not_comparable`: khác role/subject/unit/scope hoặc không thể ghép hợp lý.
- `insufficient_evidence`: thiếu OCR, citation hoặc context cần thiết.

AI2 không biến finding thành kết luận pháp lý; reviewer chịu trách nhiệm quyết định cuối.

## 9. Bbox theo hợp đồng dài

Bbox không lấy một lần cho toàn bộ hợp đồng. Mỗi trang có danh sách word/line bbox. Ví dụ trang có 63 words, 14 lines thì có khoảng 63 word bbox và 14 line bbox. Clause kéo qua hai trang có hai clause-region, mỗi trang một region.

AI1 lấy bbox:

- Text layer: đọc trực tiếp positions bằng PyMuPDF (`words`/`rawdict`/`dict`).
- Scan: OCR engine trả word boxes trong lần OCR chính; AI1 gộp thành lines.
- AI2: gộp line bbox thành clause-region bbox.

## 10. Ước lượng thay đổi AI1

| Hạng mục | Tác động runtime | Ước lượng kỹ thuật |
|---|---|---|
| Text-layer: serialize word/line geometry từ PyMuPDF | Thấp | 0.5–1 ngày |
| Chuẩn hóa bbox, rotation, schema, IDs/offset | Thấp | 0.5–1 ngày |
| Snapshot/source digest và tests | Không đáng kể | Khoảng 1 ngày |
| Scan OCR có TSV/hOCR/word boxes sẵn | Thấp so với OCR | 1–2 ngày |
| Scan engine chỉ trả plain text | Có thể cần adapter/engine mới | 3–5 ngày |
| Table cell detection | Có thể đáng kể | 2–5 ngày, làm sau |

Số `elapsed_ms` hiện tại của text-layer không đại diện cho scan OCR hoặc geometry. Cần spike đo cùng sample ở hai mode: `text-only` và `text + word/line bbox`, báo số trang, thời gian, dung lượng JSON, engine/version và input type.

## 11. Việc ưu tiên tiếp theo

1. AI1 xuất text-layer có word/line bbox cho một trang thật.
2. AI1 chạy một PDF scan có cùng contract output shape.
3. Chốt data contract AI1 → AI2 → BE/FE.
4. AI2 dựng parser cấu trúc, fact/citation và context gate bằng `pages[].text`.
5. Tạo dossier tự soạn contract + annex, plant conflict và ground truth.
6. Sửa tài liệu scope: English/bilingual và scan/text-layer là yêu cầu bắt buộc của assignment.
7. Bổ sung kế hoạch UI bbox edit, batch, metric 5 nhóm và Sprint 2–3.

## 12. Bảo mật dữ liệu

JSON mẫu có thể chứa tên, CCCD/CMND, ngày sinh, địa chỉ và số tài khoản. Không commit PDF/JSON thật lên GitHub. Mentor data phải giữ tại OneDrive/máy cá nhân; mọi external OCR/LLM/cloud service nhận dữ liệu phải được liệt kê trong Architecture và tuân theo hạn chế mentor ban hành sau đó.
