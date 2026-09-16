# Phản hồi AI1 cho `AI1-OCR-SNAPSHOT-HANDOFF.md`

**Từ:** AI1 (AI Engineer, OCR) | **Gửi:** AI2 | **Phiên bản:** v0.1
**Tài liệu gốc:** `AI1-OCR-SNAPSHOT-HANDOFF.md`

---

## 0. Tóm tắt

Đã code contract `ai1.snapshot.v1` đúng theo format yêu cầu (mục 2-4 của tài liệu gốc), tách riêng khỏi schema benchmark hiện có (`Document`/`Page` ở `domain/entities.py`, dùng để so sánh engine, không phải để bàn giao). Có CLI chạy trên PDF thật và một dossier mẫu (dữ liệu tổng hợp) chạy được ngay để AI2 test integration trước khi có tài liệu thật. Còn 3 khoảng trống thật (§4 dưới) và một vài điểm cần AI2 xác nhận trước khi chốt (§9), liệt kê đầy đủ, không che giấu.

**Code:**
- `src/contract_ocr/domain/snapshot.py` — Pydantic models, `schema_version = "ai1.snapshot.v1"`.
- `src/contract_ocr/application/use_cases/build_snapshot.py` — convert output pipeline hiện tại (`ProcessDocument`) sang snapshot.
- `src/contract_ocr/cli/main.py` lệnh `snapshot` — chạy trên 1 PDF thật.
- `scripts/export_snapshot_demo.py` — sinh dossier mẫu đầy đủ (hợp đồng + phụ lục, TEXT_LAYER + SCANNED_OCR, manifest).
- `docs/ai1.snapshot.v1.schema.json`, `docs/ai1.dossier_manifest.v1.schema.json` — JSON Schema sinh từ Pydantic models (mirror cách `output.schema.json` liên hệ với `domain/entities.py`; **nguồn xác thực chính là Pydantic models**, JSON Schema chỉ để interop/doc).
- `tests/integration/test_build_snapshot.py` — test tự động đúng 7 tiêu chí nghiệm thu ở mục 6 tài liệu gốc.

## 1. Gói bàn giao (mục 1 tài liệu gốc)

| Yêu cầu | Trạng thái |
|---|---|
| Dossier gồm 1 hợp đồng + 1 phụ lục | ✅ `scripts/export_snapshot_demo.py` sinh dossier mẫu (dữ liệu tổng hợp, có nhãn SYNTHETIC) |
| 1 PDF TEXT_LAYER + 1 PDF SCANNED_OCR | ✅ trong dossier mẫu trên |
| JSON OCR snapshot cho từng document | ✅ |
| Ảnh trang ở storage nội bộ, không commit lên GitHub | ✅ ảnh + JSON snapshot ghi vào `data/generated/...` (đã gitignore toàn bộ, xem `.gitignore`); production cần AI2/BE xác nhận storage thật (§9) |
| Dossier manifest xác nhận contract/annex | ✅ `build_dossier_manifest()`, ví dụ ở `data/generated/synthetic_demo_dossier/dossier-001/dossier_manifest.json` sau khi chạy script demo |

Chạy thử ngay:

```powershell
uv run python scripts/export_snapshot_demo.py
```

## 2-3. Document/page/line/word (mục 2-3 tài liệu gốc)

Đúng field, đúng kiểu: `schema_version`, `snapshot_id`, `source_digest` (`sha256:<hex>`, tính lại độc lập với hash trong report benchmark), `dossier_id`, `document_id`, `filename`, `document_role`, `input_type`, `engine{name,version}`, `page_count`, `processing_ms`, `pages[]`.

Mỗi lần chạy lại (`snapshot` CLI hoặc gọi `BuildSnapshot` trực tiếp) tự sinh `snapshot_id` mới theo timestamp, ghi vào thư mục riêng theo `snapshot_id` — snapshot cũ không bị ghi đè hay xoá (test `test_reocr_produces_a_new_snapshot_without_touching_the_old_one`).

`bbox_normalized = [x0, y0, x1, y1]` đúng quy ước gốc (`0 ≤ x0 < x1 ≤ 1`, gốc trên-trái, rotation đã áp dụng — kế thừa từ pipeline benchmark, xem `docs/OUTPUT_SCHEMA.md`). Offset `page_char_start/end`, `line_char_start/end` tính trên raw OCR text (Unicode code point, 0-based, end-exclusive), không normalize trước.

**Quy ước ID** (không có trong tài liệu gốc, cần AI2 xác nhận ở §9): `{document_id}:s{major}:p{page:03d}:l{seq:03d}` / `...:w{seq:04d}`, trong đó `{major}` lấy từ số hiệu chính của `schema_version` (`ai1.snapshot.v1` → `s1`) — mục đích để một ID tự nói lên nó thuộc phiên bản schema nào kể cả khi tách rời khỏi document bao quanh. Word/line ID chỉ để trỏ ngược trong cùng document, **không** phải khoá ổn định giữa các lần OCR khác nhau — mỗi `snapshot_id` có bộ ID riêng.

## 4. Block/clause region và bảng (mục 4 tài liệu gốc) — chưa xong, không giả lập

- `blocks[]`: **luôn rỗng** ở bản này. Không dựng heading/paragraph vì hiện chưa có logic gộp dòng đáng tin cậy (rủi ro nhóm sai Điều/Khoản nếu làm ẩu). Tài liệu gốc đã cho phép AI2 tự gộp line bbox thành clause-region ở giai đoạn đầu — đề nghị dùng đường đó cho tới khi AI1 có bản blocks thật.
- `tables[]`: **luôn rỗng** ở bản này. Chưa có module nhận diện cấu trúc bảng trong pipeline (PyMuPDF chỉ trả word/line, Paddle chỉ trả line) — đây là hạng mục mới cần làm từ đầu, giống ghi nhận ở `docs/BACKEND_CONTRACT_RESPONSE_v0.1.md` mục 6.7 ("Format bảng phụ lục... chưa chốt"). Schema `Table → Row → Cell` đã sẵn sàng để AI2 code song song phần đọc, nhưng AI1 chưa có gì đổ vào đó.

## 5. Các trường hợp cần thể hiện (mục 5 tài liệu gốc)

| Trường hợp | Yêu cầu | Trạng thái AI1 |
|---|---|---|
| PDF text layer | `TEXT_LAYER`, word/line bbox | ✅ PyMuPDF, có word bbox thật |
| PDF scan | `SCANNED_OCR`, confidence + word/line bbox | ⚠️ Paddle hiện chỉ trả **line-level** bbox + confidence, **không có word bbox** (giữ nguyên giới hạn đã ghi trong `docs/OUTPUT_SCHEMA.md`: "Paddle supplies text-line geometry without invented word boxes" — AI1 không tự bịa word bbox). `words[]` rỗng cho các dòng đó; `line.word_ids` cũng rỗng tương ứng, không lệch. |
| Trang trắng | `SUCCESS`, rỗng, warning `blank_page` | ✅ phát hiện bằng chính nội dung PDF nguồn (không text, không ảnh), không phụ thuộc heuristic routing OCR |
| OCR một phần | `PARTIAL`, giữ phần đọc được + warning | ✅ nhưng theo 2 tín hiệu tạm thời tự định nghĩa, **cần AI2 xác nhận** (§9): (a) `missing_line_geometry` — một số dòng có text nhưng engine không trả bbox (ví dụ DeepSeek hiện tại, xem mục 6 dưới); (b) `low_confidence_lines` — có dòng confidence < 0.5. Chưa có tín hiệu "OCR một phần" thật từ bản thân engine. |
| OCR lỗi | `FAILED`, error code/message, job không biến mất | ✅ kể cả khi trang gốc không đọc lại được (lỗi PDF) — không làm rơi cả document, chỉ trang đó `FAILED` (test `test_broken_page_load_does_not_drop_the_whole_document`) |
| Trang xoay | `rotation_degrees`, bbox theo frame đã xoay | ✅ kế thừa từ pipeline hiện có |
| Trang có bảng | Table/row/cell + bbox | ❌ chưa có, xem mục 4 |
| Re-OCR | Snapshot mới, cũ vẫn truy vấn được | ✅ |

**Lưu ý về engine hiện tại:** DeepSeek/Vision (GPT-5.6 Terra Light theo `docs/BACKEND_CONTRACT_RESPONSE_v0.1.md`) hiện **không có grounding geometry** — khi dùng engine này, mọi dòng rơi vào nhánh "missing_line_geometry" ở trên (`status: PARTIAL`, `lines: []`, chỉ còn `text`). Route này **chưa dùng được cho citation cần bbox**; chỉ Paddle (line-level) và PyMuPDF (word-level đầy đủ) mới cho geometry dùng được ngay.

## 6. Tiêu chí AI2 nghiệm thu (mục 6 tài liệu gốc)

| # | Tiêu chí | Trạng thái | Test |
|---|---|---|---|
| 1 | Truy ngược document→page→line→char span→word/line bbox | ✅ | `test_traceability_geometry_and_document_metadata` |
| 2 | Bbox render đúng trên ảnh trang gốc | ✅ (bbox tính trên cùng frame với `page_image_ref`, đã áp rotation) | thủ công qua `contract-ocr visualize` (bản benchmark) — **AI2 nên tự vẽ thử trên `page_image_ref` thật trước khi chốt**, AI1 chưa có tool overlay riêng cho snapshot format |
| 3 | Finding contract–annex mang citation từ cả 2 phía | N/A phía AI1 — dossier mẫu có đủ `document_role` contract/annex để AI2 test | — |
| 4 | 1 trang text-layer + 1 trang scan cùng output shape | ✅ | `test_traceability_geometry_and_document_metadata` |
| 5 | Re-OCR không đổi snapshot cũ | ✅ | `test_reocr_produces_a_new_snapshot_without_touching_the_old_one` |
| 6 | Trang thiếu text/geometry có warning/error rõ | ✅ | `test_missing_geometry_marks_partial_not_silent_success`, `test_skipped_page_becomes_failed_with_explicit_error`, `test_blank_page_is_success_with_warning_not_an_error` |
| 7 | Engine/version, thời gian chạy, input type, source digest | ✅ | `test_traceability_geometry_and_document_metadata` |

Tiêu chí #3 cần AI2 tự thử trên dossier mẫu vì đó là logic phía AI2 (ghép contract-annex), AI1 chỉ đảm bảo cả hai phía có đủ dữ liệu để trỏ tới.

## 7. Ngoài phạm vi (mục 7 tài liệu gốc)

Không đổi — AI1 xác nhận lại: trích fact nghiệp vụ, ghép contract/annex, phát hiện xung đột/precedence, reviewer workflow vẫn thuộc AI2/Backend/Frontend, không nằm trong `ai1.snapshot.v1`.

## 8. Việc AI2 có thể bắt đầu ngay

- Đọc/parse `ai1.snapshot.v1` bằng dossier mẫu (`scripts/export_snapshot_demo.py`) — không cần chờ tài liệu thật.
- Code đường đọc `tables[]`/`blocks[]` với schema rỗng (không lỗi khi rỗng, chỉ không có dữ liệu) để không phải đổi contract khi AI1 đổ dữ liệu vào sau.
- Validate JSON bằng `docs/ai1.snapshot.v1.schema.json` nếu AI2 không dùng Python/Pydantic; nếu dùng Python, import thẳng `contract_ocr.schemas.snapshot.DocumentSnapshot`.

## 9. Việc cần 2 bên chốt trước khi code song song

- [ ] Định nghĩa "OCR một phần" (`PARTIAL`) ở mục 5 hiện là heuristic tạm của AI1 (`missing_line_geometry`, `low_confidence_lines`, ngưỡng confidence 0.5) — AI2 có cần thêm/đổi tín hiệu khác không?
- [ ] Quy ước ID `{document_id}:s{major}:p{page}:l{seq}` — AI2 xác nhận chỉ cần ID ổn định/duy nhất trong 1 snapshot (không parse cấu trúc bên trong), hay cần format khác để khớp DB/index phía Backend?
- [ ] `page_image_ref.uri` hiện dùng `storage://ocr/{snapshot_id}/page-{n}.png` theo đúng ví dụ trong tài liệu gốc — cần đối chiếu với layout object storage đã phác thảo ở `architecture.md` (`runs/{run_id}/pages/{page_number}/...`) để không có 2 quy ước song song.
- [ ] Timeline `blocks[]`/`tables[]` — ai làm, làm khi nào (xem mục 4).
- [ ] Word-level bbox cho SCANNED_OCR (hiện Paddle chỉ có line-level) — có bắt buộc phải có trước khi AI2 tích hợp, hay AI2 chấp nhận line-level trước?
