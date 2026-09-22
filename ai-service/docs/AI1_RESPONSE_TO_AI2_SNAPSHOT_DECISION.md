# Phản hồi AI1 cho `AI2-DECISION-ai1-result-v0.1-vs-snapshot-v1`

**Từ:** AI1 (AI Engineer, OCR) | **Gửi:** AI2, Backend, Frontend | **Ngày:** 2026-09-22
**Theo:** Kết luận nghiên cứu của AI2 so sánh `ai1.result.v0.1` (envelope hiện tại của Backend) với `ai1.snapshot.v1` (contract AI1 tự định nghĩa trong `ai-service`)
**Trạng thái:** Đồng ý với kết luận của AI2. `ai1.snapshot.v1` là canonical contract. Tài liệu này đối chiếu từng yêu cầu field của AI2 với schema thật hiện có, và nêu rõ phần nào đã sẵn sàng, phần nào còn thiếu thật.

---

## 1. Đồng ý với kết luận

AI1 đồng ý: **`ai1.snapshot.v1` nên là contract chính thức lâu dài giữa AI1–AI2**, `ai1.result.v0.1` (JSON `machine.schema_version: "0.1"` do `backend/app/worker.py` tạo) chỉ nên là compatibility adapter tạm thời cho dữ liệu đang có. Đây đúng là ranh giới đã ghi trong [AI1 team handoff](AI1_TEAM_HANDOFF.md) mục 1 từ trước: hai contract khác nhau, không đổi tên `schema_version` để giả lập nhau.

Trong lúc AI2 đánh giá, phía AI1 đã hoàn thiện thêm phần OCR + bảng của `ai1.snapshot.v1` (không đổi shape field, chỉ đổ dữ liệu thật vào các field đã có sẵn trong schema từ trước):

- Engine `mistral` đọc bbox/confidence THẬT theo từng block (không suy diễn), tự dựng `tables[]` từ bảng markdown Mistral trả về — kể cả bảng không viền.
- `table_continuity[]` có 3 tầng quyết định (hard guard → rule score → agent DeepSeek tùy chọn cho vùng mơ hồ) khi nối bảng bị cắt ngang trang.
- Đã gỡ Paddle/DeepSeek (không dùng nữa) khỏi `ai-service`, chỉ còn PyMuPDF (native) và Mistral (OCR) — engine chính đang chạy thật.

Chi tiết kỹ thuật: [AI1 team handoff](AI1_TEAM_HANDOFF.md), [phản hồi handoff gốc](AI1_OCR_SNAPSHOT_HANDOFF_RESPONSE.md).

## 2. Đối chiếu field AI2 yêu cầu bổ sung với schema thật

AI2 liệt kê các field "cần bổ sung hoặc chuẩn hóa" trước khi dùng snapshot v1 làm baseline. Đối chiếu trực tiếp với [`domain/snapshot.py`](../src/contract_ocr/domain/snapshot.py) (nguồn xác thực) và một snapshot vừa sinh thật (`scripts/export_snapshot_demo.py`):

| AI2 yêu cầu | Trạng thái thật | Ghi chú |
|---|---|---|
| `snapshot_id` | ✅ **Đã có** | `DocumentSnapshot.snapshot_id`, không phải field thiếu. |
| `created_at` | ❌ **Thiếu thật** | Không có timestamp nào trên `DocumentSnapshot`. `processing_ms` là thời lượng xử lý, không phải mốc thời gian tạo. |
| `execution` | ❌ **Thiếu thật** | Không có object nào ghi lại thông tin lần chạy (run id, môi trường...). |
| `producer` | ⚠️ **Có một phần** | `engine: {name, version}` ghi engine đã tạo ra dữ liệu, nhưng không có field "producer" tách riêng (vd. tên service/build AI1). Cần AI2 xác nhận có đủ dùng `engine` thay `producer` không, hay cần thêm field riêng. |
| `language` | ❌ **Thiếu thật** | Không có field ngôn ngữ ở bất kỳ cấp nào (document/page). |
| `page_revision_id` | ❌ **Thiếu thật** | Không có khái niệm "revision" cho từng trang. |
| `raw_text_digest` | ❌ **Thiếu thật** | Chỉ có `source_digest` (hash **toàn bộ PDF gốc**, mức document), không có digest riêng theo text đã OCR của từng trang. |
| `quality` | ❌ **Thiếu thật** | Có `warnings[]` (`missing_line_geometry`, `low_confidence_lines`) mang tính chất tương tự nhưng không phải field "quality" có cấu trúc. |
| `table_coverage` | ❌ **Thiếu thật** | Có `table_status` (`NOT_CHECKED`/`NOT_PRESENT`/`DETECTED`) — phân loại thô, không phải chỉ số coverage. |
| `geometry_status` | ⚠️ **Có phần tương đương** | Không có field tên `geometry_status` riêng, nhưng `status`/`warnings` cấp trang (`PARTIAL` + `missing_line_geometry`) đã phủ đúng ý "trạng thái geometry của trang". |
| `bbox_source` | ✅ **Đã có, tên khác** | Chính là `geometry_provenance` (`MEASURED`/`DERIVED`/`CLAIMED`) — có ở **mọi** word/line/cell/node, đúng ý AI2 muốn ("AI2 không được coi geometry CLAIMED là citation-grade" — nguyên tắc này AI1 đã ghi sẵn trong docstring schema, khớp cảnh báo mục 6 của AI2). |
| `line_ids` cho table cell khi có grounding | ❌ **Thiếu thật** | `Cell` hiện chỉ có `cell_id, text, bbox_normalized, geometry_provenance` — không có đường trỏ ngược về `SnapshotLine` đã sinh ra nội dung ô. Đây là gap cụ thể nhất, đáng làm trước: đúng lúc dữ liệu bảng qua Mistral có `geometry_provenance: CLAIMED` (bbox chia đều, không đo riêng từng ô — xem mục 4 handoff), `line_ids` sẽ là đường audit thay thế khi bbox không đủ tin cậy để trích dẫn. |

**Tóm lại:** 2/11 mục AI2 nêu **đã có sẵn** (chỉ cần AI2 map đúng tên field), 2/11 **có phần tương đương** cần xác nhận có đủ dùng không, 7/11 **thiếu thật** — nhiều nhất và cụ thể nhất là `line_ids` cho table cell.

## 3. Nguyên tắc AI2 nêu — đối chiếu với hệ thống hiện tại

- *"Không đổi tên `schema_version` để giả lập snapshot v1"* — đã là quy tắc ghi trong [AI1 team handoff](AI1_TEAM_HANDOFF.md) mục 1 từ trước khi có kết luận này.
- *"Không coi `findings = 0` là bằng chứng dữ liệu nhất quán"* — snapshot AI1 không tự tạo `findings` (thuộc phạm vi AI2, xem mục 7 tài liệu gốc), không áp dụng trực tiếp cho AI1 nhưng AI1 xác nhận cùng quan điểm.
- *"Không coi citation có bbox hợp lệ là đã được xác minh"* — đây chính xác là lý do tồn tại của `geometry_provenance`/`bbox_source`: `CLAIMED` là nhãn "đừng tin cho trích dẫn chính xác", ghi rõ trong docstring `domain/snapshot.py` dòng 35 ("AI2 must not treat CLAIMED geometry as citation-grade").
- *"Không publish khi AI1 còn `pending_review` hoặc evidence issue chưa xử lý"* — snapshot AI1 không có khái niệm `pending_review`/`review.blocked` (đó là field của `ai1.result.v0.1`/Backend, ngoài phạm vi AI1). Mỗi `SnapshotPage` có `status` (`SUCCESS`/`PARTIAL`/`FAILED`) độc lập theo trang thay vì một cờ block ở mức toàn tài liệu — AI2 nên đọc theo trang, không có một "gate" tổng duy nhất từ phía AI1.

## 4. Sample thật để AI2 kiểm tra ngay

AI2 yêu cầu: *"Yêu cầu AI1 phát một sample thực theo `ai1.snapshot.v1`"*. Hai cách, tùy AI2 cần gì trước:

**Có ngay, không cần PDF thật (dữ liệu tổng hợp, đủ để kiểm tra shape/field):**

```powershell
cd ai-service
uv run python scripts/export_snapshot_demo.py --output data/generated/ai2-sample-check
```

Ra 1 hợp đồng TEXT_LAYER (có bảng native, đủ `tables[]`/`nodes[]`) + 1 phụ lục SCANNED_OCR trong `data/generated/ai2-sample-check/dossier-001/`. Đã kiểm tra thật lúc viết tài liệu này — đúng 14 field top-level, đúng field từng bảng/ô như bảng đối chiếu ở mục 2.

**Trên PDF thật của AI2 (cần `MISTRAL_API_KEY`):**

```powershell
uv run --env-file .env contract-ocr snapshot --file <pdf-that>.pdf --document-id <id> --dossier-id <id> --role contract --engine mistral --output data/generated/snapshots
```

Lưu ý: mỗi trang tự định tuyến — trang có text-layer native đọc qua PyMuPDF, chỉ trang SCANNED/MIXED mới gọi Mistral (xem `pages[].input_type` để biết trang nào đi đường nào; snapshot không có field engine riêng theo trang). Chi tiết ở [AI1 team handoff](AI1_TEAM_HANDOFF.md) mục 5.

## 5. Đề xuất bước tiếp theo (chưa tự làm, cần chốt phạm vi trước)

Với 7 field thiếu thật ở mục 2, đề xuất AI1 làm theo thứ tự ưu tiên nếu team đồng ý:

1. **`line_ids` cho table cell** — giá trị cao nhất cho audit/citation, đặc biệt với bảng Mistral (`CLAIMED`). Cần thiết kế: cell hiện không giữ tham chiếu ngược tới dòng OCR nguồn.
2. **`created_at`** — đơn giản, rủi ro thấp, nên làm sớm.
3. **`raw_text_digest` theo trang** — bổ sung cho `source_digest` (mức document) đã có, phục vụ replay/audit từng trang như AI2 yêu cầu.
4. **`language`, `execution`, `producer`, `quality`, `table_coverage`** — cần AI2 xác nhận rõ hình dạng field mong muốn (enum hay free text, tính theo trang hay theo document) trước khi AI1 code, tránh phải đổi lại.

Đây là đề xuất, chưa triển khai — cần Backend/AI2 xác nhận thứ tự ưu tiên trước khi AI1 sửa schema.

---

## 6. Tài liệu liên quan

- [AI1 team handoff](AI1_TEAM_HANDOFF.md) — luồng PDF, ranh giới trách nhiệm, việc cần chốt để tích hợp runtime.
- [Phản hồi handoff gốc](AI1_OCR_SNAPSHOT_HANDOFF_RESPONSE.md) — mapping đầy đủ theo yêu cầu bàn giao ban đầu.
- [`domain/snapshot.py`](../src/contract_ocr/domain/snapshot.py) — nguồn xác thực của schema; [`docs/ai1.snapshot.v1.schema.json`](ai1.snapshot.v1.schema.json) là bản xuất JSON Schema tương ứng, luôn đồng bộ (kiểm bằng `tests/unit/test_handoff_schema.py`).
- Tài liệu kết luận của AI2 (`AI2-DECISION-ai1-result-v0.1-vs-snapshot-v1.vi.md`) — không nằm trong repo này, AI1 nhận được bản riêng; nếu team muốn đối chiếu lâu dài, nên đưa cả 2 phía tài liệu (AI1 + AI2) vào cùng một chỗ lưu trữ chung.
