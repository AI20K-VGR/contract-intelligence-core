# Architecture Review v2 — phạm vi AI2 và lỗi cần xử lý

**Tài liệu được review:** [`/architecture.md`](../../../architecture.md)
**Ngày review:** 16/09/2026
**Trạng thái khuyến nghị:** Không chốt implementation AI2 trước khi đóng các finding P0.
**Phạm vi:** Review contract giữa OCR/provenance, fact/citation, liên kết phụ lục, comparison/finding và review workflow. Đây không phải báo cáo chất lượng OCR thực nghiệm.

## 1. Kết luận điều hành

`architecture.md` có nền tảng phù hợp: modular monolith, dossier aggregate, pipeline bất đồng bộ, output máy bất biến, review append-only, citation hai phía và OCR hybrid. Tuy nhiên, contract AI1 → AI2 chưa đóng băng: có mâu thuẫn về offset, thiếu mapping snapshot/provenance, và có khả năng coi bbox ước lượng là bằng chứng đo được. Các lỗi này sẽ làm audit OCR/bbox, finding contract–annex và review khó tái lập.

## 2. Phân định trách nhiệm AI2

| Pipeline / artifact | Owner chính | Trách nhiệm AI2 |
|---|---|---|
| S0 — ingest, dossier/job/batch | Backend | Cung cấp rule dossier và điều kiện comparison. |
| S1–S4 — classify, render, OCR, line/word/bbox/snapshot | AI1 | Nhận và validate input; không tự tạo bbox thiếu. |
| S5 — physical layout/table detection, cell bbox | AI1 | Tiêu thụ bảng/cell đã có evidence; định nghĩa nhu cầu semantic. |
| S6 — cây Điều/Khoản/Điểm | AI2 | Parse/gộp từ lines, giữ provenance và confidence. |
| S7 — fact + validation | AI2 | Extract, normalize, context gate, citation. |
| S8 — annex linking | AI2 | Link evidence, thứ tự và trạng thái liên kết; không suy đoán quan hệ từ filename. |
| S9 — finding | AI2 | Structured + semantic comparison, taxonomy, disposition, precedence evidence. |
| S10 — review items | AI2 + Backend/FE | AI2 thiết kế rule/priority; Backend persist; FE review/highlight. |
| Queue, DB, API, auth, UI | Backend/Frontend | AI2 cung cấp contract, không sở hữu hạ tầng. |

## 3. Finding P0 — phải xử lý trước implementation AI2

### P0-01 — Offset citation mâu thuẫn với handoff v2

**Evidence:** [architecture.md line 546](../../../architecture.md#L546) tạo `document_text` NFC và thêm line ending trước khi tính `doc_char_span`; handoff v2 yêu cầu offset theo Unicode code point trên raw OCR text, không normalize hay reformat trước.

**Rủi ro:** Ký tự tổ hợp/dấu tiếng Việt hoặc cách xuống dòng bị đổi làm `char_span` không còn trỏ đúng text hiển thị. Citation, highlight và audit không tái lập được.

**Yêu cầu sửa:** Lưu `raw_text` bất biến làm basis duy nhất của citation. Text NFC chỉ dùng cho matching/search, phải có mapping về raw text nếu dùng. Bổ sung `offset_unit = unicode_code_point_0_based_end_exclusive` vào schema và test `A😀B` cùng ký tự tổ hợp.

### P0-02 — Chưa có mapping chuẩn giữa AI1 snapshot và architecture

**Evidence:** Handoff v2 dùng `snapshot_id`, `source_digest`, `page_image_ref`, `bbox_normalized`, `SCANNED_OCR`; architecture dùng `pipeline_run`, `render_uri`, `bbox`, `page.kind`. Citation tại [lines 1053–1078](../../../architecture.md#L1053) không chứa `snapshot_id` hay source digest.

**Rủi ro:** Re-OCR không xác định được citation thuộc output nào; UI/audit không kiểm chứng được PDF/render đúng phiên bản.

**Yêu cầu sửa:** Đóng băng adapter `ai1.snapshot.v1 → PageText/Citation`. Mỗi citation segment MUST giữ `snapshot_id`, `document_id`, `page_no`, `line_id`, `char_start/end`, `word_ids`, `bbox_refs`, source PDF digest và render digest. Quy định mapping enum `TEXT_LAYER | SCANNED_OCR | MIXED` với `native | scanned | hybrid` nội bộ.

### P0-03 — Bbox estimated/line-only bị lẫn với geometry có thể audit

**Evidence:** [line 498](../../../architecture.md#L498) chia bbox dòng theo độ dài ký tự cho token Terra không khớp; [line 1087](../../../architecture.md#L1087) fallback sang line bbox khi không có word bbox.

**Rủi ro:** Bbox ước lượng có thể được hiển thị như evidence thật và bị tính vào IoU/citation accuracy. Output Feddy có text nhưng `geometry_available=false`, minh họa trường hợp không thể cite được.

**Yêu cầu sửa:** Bổ sung `bbox_source = native | detector | line_only | estimated` và `geometry_status = complete | line_only | absent`. `estimated`/`line_only` MUST không pass word-level audit; fact/finding quan trọng không có geometry hợp lệ MUST thành `insufficient_evidence` hoặc review item.

### P0-04 — Schema fact thiếu context nhưng comparator đang phụ thuộc context

**Evidence:** Comparator tại [line 662](../../../architecture.md#L662) dùng hàng hóa, chi nhánh, VAT và đơn vị để quyết định `not_comparable`; DDL `fact` tại [lines 912–930](../../../architecture.md#L912) chỉ có `context_clause_id` và `context_text`.

**Rủi ro:** AI2 phải suy luận lại context từ free text; cùng rule có thể trả kết quả khác nhau và false-positive conflict tăng.

**Yêu cầu sửa:** Bổ sung typed context: `business_role`, `subject`, `unit`, `currency`, `tax_basis`, `applicability_scope`, `validity_start`, `validity_end`, `context_origin`. Rule comparison chỉ chạy khi context gate xác định được và lưu kết quả gate.

### P0-05 — Candidate amendment thiếu điều kiện pháp lý/kỹ thuật tối thiểu

**Evidence:** [lines 698–702](../../../architecture.md#L698) tạo `candidate_amendment` khi có khác biệt và signal sửa đổi; [line 724](../../../architecture.md#L724) dùng ngày tài liệu sau để đề xuất hiệu lực.

**Rủi ro:** Câu sửa đổi không liên quan hoặc khác scope/unit/VAT có thể bị coi là amendment. Đây là suy luận vượt quá evidence.

**Yêu cầu sửa:** Candidate amendment MUST có bốn evidence gates: annex link đáng tin; reference tới clause/field; context tương thích; ngày/validity hợp lệ. Thiếu một gate → `comparable_difference` hoặc `insufficient_evidence`; không suy ra hiệu lực pháp lý tự động.

### P0-06 — Conflict view trộn conflict với dữ liệu thiếu evidence

**Evidence:** [lines 713–717](../../../architecture.md#L713) đưa `insufficient_evidence` và confidence thấp vào `v_conflict`.

**Rủi ro:** Reviewer thấy cảnh báo “conflict” trong khi hệ thống thực ra không đủ chứng cứ. Metric conflict precision/F1 bị sai denominator.

**Yêu cầu sửa:** Tách `Needs evidence` khỏi Conflict panel. Conflict panel chỉ chứa `comparable_difference` và `candidate_amendment`; `insufficient_evidence` là review queue riêng. Định nghĩa rõ denominator từng metric.

## 4. Finding P1 — xử lý trong thiết kế Sprint 2

| ID | Finding | Evidence / rủi ro | Yêu cầu |
|---|---|---|---|
| P1-01 | Review đồng thời | `review_action` append-only nhưng không có `previous_revision_id` / expected base revision. | Revision chain + optimistic concurrency; reject/rebase khi stale. |
| P1-02 | Semantic candidate bị cắt | `MAX_SEMANTIC_PAIRS` tại [line 658](../../../architecture.md#L658) không lưu candidates bỏ qua. | Lưu ranking, policy/version, lý do skip và candidate recall. |
| P1-03 | Citation segments là JSONB | FK/validation không bắt được line/word/bbox ref đã tồn tại. | Application/schema validation bắt buộc trước INSERT; export JSON có refs explicit. |
| P1-04 | Annex sequence | Trọng số/ngưỡng liên kết tại [lines 631–645](../../../architecture.md#L631) còn TBD. | Versioned decision table, ground-truth cases và trạng thái `linked_needs_review`. |
| P1-05 | Handoff state | Output Feddy thiếu geometry nhưng architecture giả định scan luôn có detector geometry. | Input thiếu geometry phải `PARTIAL` + warning, không đi comparison như evidence đầy đủ. |
| P1-06 | Owner visibility | S0–S10 rõ nhưng không có owner. | Thêm responsibility matrix ở mục 6/20 của architecture. |

## 5. Những phần nên giữ

- Dossier là aggregate trung tâm; S8–S10 chạy sau khi đủ document.
- OCR hybrid tách recognition và geometry, không tin tọa độ do VLM tự sinh.
- Citation segment nhiều dòng/trang, finding có hai sides.
- Machine output INSERT-only; review append-only; UI hiển thị bbox gốc và bbox sửa.
- Native-first, local fallback, budget guard và model trace/version.

## 6. Thứ tự xử lý đề xuất

1. Chốt `ai1.snapshot.v1` adapter, raw-text offset và citation provenance (P0-01, P0-02).
2. Chốt geometry quality/status và policy `insufficient_evidence` (P0-03).
3. Mở rộng fact context + decision table comparison/amendment (P0-04, P0-05).
4. Tách Conflict/Needs-evidence và cập nhật metrics (P0-06).
5. Thêm revision concurrency, candidate audit và owner matrix (P1).

## 7. Ghi chú model

Claim `gpt-5.6-terra` nhận image input và hỗ trợ Structured Outputs là phù hợp với [official OpenAI model documentation](https://developers.openai.com/api/docs/models/gpt-5.6-terra). Giá token trong architecture ($2 input / $12 output trên 1M tokens) cũng khớp tại thời điểm review. Điều này không thay thế benchmark OCR/bbox trên dữ liệu đã được phép dùng.

## 8. Điều kiện accept architecture cho AI2

Architecture sẵn sàng cho AI2 khi có: schema snapshot/manifest validator; một fixture dossier contract+annex với PDF/render/digest; citation round-trip raw text; fact context schema; decision table disposition; test geometry/overlay; và owner matrix được Leader/Mentor xác nhận.
