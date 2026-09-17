# Report review kiến trúc — Contract Intelligence (DOC-04)

| Thuộc tính | Nội dung |
|---|---|
| **Dự án** | Contract Intelligence (PROD-01) |
| **Tài liệu được review** | `CONTRACT_INTELLIGENCE_ARCHITECTURE.md` v0.1 |
| **Căn cứ đối chiếu** | `assignment.pdf` (11 trang) và `TỔNG QUAN DỰ ÁN & QUY TẮC LÀM VIỆC.txt` |
| **Thời điểm review** | 16/09/2026 |
| **Kết luận** | **Chưa nên phê duyệt để triển khai.** Cần xử lý các blocker P0 bên dưới. |

---

## 1. Phạm vi và phương pháp

Review đối chiếu DOC-04 với các yêu cầu bắt buộc của đề bài: dossier gồm hợp đồng và phụ lục, OCR/geometry, cấu trúc điều khoản và bảng, citation kiểm chứng được, hai họ conflict, HITL, single/batch processing, số liệu đánh giá và khả năng chạy demo.

Đây là review thiết kế. Nó không khẳng định chất lượng OCR, chi phí, throughput hay production readiness khi chưa có run/audit thực tế.

## 2. Tóm tắt điều hành

DOC-04 chọn hướng kỹ thuật phù hợp với quy mô OJT: một backend FastAPI, worker bất đồng bộ, PostgreSQL, object storage và giao diện HITL. Các nguyên tắc native-first, không suy đoán nội dung, không tự động chốt các trường quan trọng, và route local cho tài liệu nhạy cảm là đúng hướng.

Tuy nhiên, kiến trúc đang lấy `Document` làm đơn vị trung tâm, trong khi đề bài lấy **dossier** — một hợp đồng cùng 0..n phụ lục — làm đơn vị xử lý và đánh giá. Hệ quả là data model hiện chưa diễn tả được quan hệ hợp đồng–phụ lục, precedence, citation hai phía của finding, batch lifecycle, hoặc lịch sử correction bất biến. Đây là các yêu cầu chấm demo, không phải chi tiết triển khai tùy chọn.

## 3. Phát hiện bắt buộc xử lý trước khi duyệt (P0)

### P0-01 — Thiếu mô hình dossier và membership hợp đồng–phụ lục

**Yêu cầu đề bài:** một đơn vị công việc là một dossier gồm một contract và 0..n annexes, nộp cùng nhau. Conflict phải hỗ trợ within-document, contract–annex và annex–annex.

**Hiện trạng DOC-04:** ERD có `DOCUMENT` và `APPENDIX`, nhưng không có `DOSSIER`, membership, vai trò tài liệu, thứ tự hoặc ngày hiệu lực phụ lục. `APPENDIX` cũng không có quan hệ rõ với contract.

**Rủi ro:** không xác định được tập tài liệu cần xử lý cùng nhau; không triển khai đúng annex–annex hoặc precedence của phụ lục; API/job/review dễ bị thiết kế sai ngay từ đầu.

**Yêu cầu sửa:** thêm tối thiểu:

- `Dossier`;
- `DossierDocument(dossier_id, document_id, role, upload_order, annex_no, effective_date, relationship_evidence)`;
- enum `role = CONTRACT | ANNEX`;
- pipeline, review queue và batch summary lấy `dossier_id` làm aggregate chính.

### P0-02 — Citation không đủ provenance để kiểm chứng một-click

**Yêu cầu đề bài:** citation của mỗi value và finding phải resolve theo chuỗi `document → page → OCR line(s) → character span → bbox`; finding cross-document phải trỏ được cả hai phía.

**Hiện trạng DOC-04:** citation được mô tả là `{document_id, page, bbox | clause_id}`; bảng `CITATION` chỉ có `document_id`, `page`, `bbox`. Không có snapshot/version OCR, line ID, character span, word ID hay bbox reference. `Conflict` không có citation riêng.

**Rủi ro:** UI không thể chứng minh citation chính xác; re-OCR sẽ làm reference mơ hồ; conflict không thể highlight hai nguồn; không thể đo citation correctness theo rubric.

**Yêu cầu sửa:** chốt data contract citation gồm `snapshot_id`, `document_id`, `page_no`, `line_id`, `char_start`, `char_end`, `word_ids`, `bbox_refs`. Offsets phải có quy ước rõ: Unicode code point, 0-based, end-exclusive trên raw OCR text. Finding giữ `left_citation_ids` và `right_citation_ids`.

### P0-03 — Bbox và dữ liệu bảng chưa đáp ứng schema bắt buộc

**Yêu cầu đề bài:** có bbox ở ba tầng word, line và clause region; tọa độ chuẩn hóa 0..1, origin top-left; lưu page size và rotation thực đo; bảng phải là rows/cells, không phải text blob.

**Hiện trạng DOC-04:** `PAGE.evidence` và các trường `source_bbox`/`bbox` là JSON chung chung. `APPENDIX.table_data` không có row/cell/citation/bbox. Không có page frame, rotation, word/line entity.

**Rủi ro:** không render overlay đáng tin cậy, không cho chỉnh bbox trong UI, không audit được IoU/hit rate và không bảo toàn cấu trúc bảng phụ lục.

**Yêu cầu sửa:** bổ sung `PageFrame`, `OcrLine`, `OcrWord`, `ClauseRegion`, `Table`, `TableRow`, `TableCell`; quy định toàn bộ bbox theo upright frame và liên kết đến snapshot. Một clause kéo qua nhiều trang cần nhiều region, không phải một `source_page` duy nhất.

### P0-04 — Conflict domain chưa đủ hai family, ba scope và precedence

**Yêu cầu đề bài:** phát hiện structured conflicts và semantic conflicts trên ba scope; có taxonomy, severity và quy tắc tài liệu nào thắng khi phụ lục sau sửa hợp đồng/phụ lục trước.

**Hiện trạng DOC-04:** worker chủ yếu mô tả embedding + LLM judge; `Conflict` chỉ có hai clause IDs, severity, explanation và status. Không có family, finding type, comparison scope, disposition, context, precedence evidence hay annex–annex rule.

**Rủi ro:** dễ báo khác biệt bề mặt thành conflict; không phân biệt amendment candidate, not comparable và insufficient evidence; kết quả mang sắc thái kết luận pháp lý.

**Yêu cầu sửa:**

- Tách `structured` và `semantic`; structured ưu tiên normalizer/rule có version.
- Chỉ so sánh khi role, subject, unit/currency/VAT, scope và validity tương thích.
- Có `model_disposition`: `comparable_match`, `comparable_difference`, `candidate_amendment`, `not_comparable`, `insufficient_evidence`.
- Lưu `comparison_scope`, `precedence_evidence`, hai fact/citation refs; review state phải tách khỏi machine disposition.

### P0-05 — HITL không bảo đảm machine output bất biến và chưa hỗ trợ bbox edit

**Yêu cầu đề bài:** reviewer confirm/correct/reject value và conflict, có thể vẽ/chỉnh bbox; dữ liệu correction giữ ai/khi nào và **không được phá hủy** machine output.

**Hiện trạng DOC-04:** mô tả reviewer “ghi đè lên bản máy trích xuất”; `ReviewAction` chỉ có old/new value, không có revision chain, base revision, bbox revision hay snapshot lineage.

**Rủi ro:** mất auditability, không tái lập được kết quả; concurrent review có thể last-write-wins; chỉnh bbox không có persistence contract.

**Yêu cầu sửa:** machine snapshot/output immutable; mỗi action tạo `ReviewRevision` append-only chứa actor, timestamp, reason, predecessor/base revision, patch value và patch bbox. Khi concurrent update, API phải reject/rebase thay vì ghi đè im lặng.

### P0-06 — Thiếu lifecycle single/batch, idempotency và recovery

**Yêu cầu đề bài:** single có job ID/state; batch chạy nền có retry, summary done/failed/needs-review, back-pressure; crash giữa batch không làm job biến mất im lặng.

**Hiện trạng DOC-04:** có Redis/queue và retry 429 ở mức ý tưởng, nhưng ERD không có `Batch`, `Job`, `Run` hay `Attempt`; chỉ có `Document.status=PENDING`.

**Rủi ro:** không thể trả API state đáng tin cậy, retry an toàn hoặc chứng minh batch behavior tại demo.

**Yêu cầu sửa:** thêm `Batch`, `PipelineRun`, `Job`, `JobAttempt`, idempotency key, retry policy, dead-letter/quarantine và explicit state machine. Cần có completion barrier chỉ chạy structuring khi toàn bộ page result của dossier đã ở terminal state.

## 4. Phát hiện quan trọng (P1)

1. **Benchmark gate đặt quá muộn.** DOC-04 dự kiến dùng Luna trong Sprint 2 nhưng benchmark Luna–Terra ở Sprint 3. Cần benchmark tối thiểu trước route dữ liệu thật, hoặc gọi route này là experimental và cấm đưa kết quả thành claim chất lượng.
2. **Thiếu bảng bước xử lý → engine → lý do → chi phí/dossier.** Đề yêu cầu bảng cho mọi bước; DOC-04 mới có giá token OCR. Cần tách OCR, structuring, extraction, embedding, semantic judge và fallback; đo/ước tính tiền và phút trên một dossier, rồi projection 1.000 dossier/tháng.
3. **Đa ngôn ngữ chưa thành contract.** Đề yêu cầu thiết kế nhiều ngôn ngữ, ưu tiên tiếng Việt/Anh và trang song ngữ. Cần `document_language`, `page_language`, quy tắc bilingual reading order/normalization và test sample tương ứng.
4. **Cache thiếu versioning và phạm vi cô lập.** Cache page hash phải bao gồm tenant/dossier scope, source digest, preprocessing/render version, engine/model/prompt/schema version và retention policy; nếu không có thể tái dùng kết quả sai hoặc gây rủi ro privacy.
5. **Security còn thiếu policy vận hành.** Bổ sung encryption in transit/at rest, retention/deletion, quyền upload/download, log redaction, key rotation và audit access. Cờ sensitivity ở worker là cần thiết nhưng chưa đủ.
6. **Ngôn ngữ tài liệu cần làm rõ.** “OpenAI GPT-5.6 Luna (Lunar Light)” nên dùng model ID chính xác `gpt-5.6-luna`; không nên ngầm coi model vision là OCR engine có word/line geometry nếu chưa có cơ chế evidence mapping độc lập.

## 5. Xác nhận về model và giá

Tên model `gpt-5.6-luna` và mức giá $0.20/1M input, $1.20/1M output là phù hợp với tài liệu OpenAI hiện hành. Model nhận image input và hỗ trợ structured outputs. Tuy nhiên, đó là giá token, **không thay thế** yêu cầu của đề bài về cost per dossier và cost tại 1.000 dossier/tháng.

Nguồn: [OpenAI Docs — GPT-5.6 Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna).

## 6. Những phần nên giữ

- FastAPI + worker/queue thay vì xử lý OCR trong HTTP request.
- Native-first để giảm chi phí và tăng tốc cho PDF có text layer.
- Chống suy đoán; dữ liệu thiếu phải được biểu diễn rõ thay vì tự điền.
- HITL là gate trước khi coi trường quan trọng là final.
- Routing local cho tài liệu nhạy cảm và không log text nội dung.
- Không over-engineer thành Kubernetes/microservices trong phạm vi OJT.

## 7. Điều kiện đề xuất để Mentor phê duyệt DOC-04

1. Bổ sung mô hình dossier, document role và precedence/membership.
2. Đóng băng data contract citation/bbox/table/snapshot có ví dụ từ một trang thật.
3. Chốt taxonomy/disposition conflict cùng rule context gate và precedence.
4. Bổ sung immutable review revision + bbox edit contract.
5. Vẽ state machine cho single/batch run, retry và recovery; phản ánh nó trong ERD/API boundary.
6. Bổ sung bảng model/engine/cost-per-dossier và benchmark gate trước khi đưa Luna vào dữ liệu thật.
7. Chỉ sau các mục trên mới chuyển trạng thái từ `Draft / Chờ Mentor review` sang gửi mentor review.

## 8. Kết luận

DOC-04 có nền tảng kỹ thuật hợp lý, nhưng hiện mới là architecture ở mức container và ý tưởng pipeline. Để đáp ứng đề bài, nó phải trở thành architecture có **dossier aggregate, provenance end-to-end, finding semantics, immutable review history và job lifecycle có khả năng khôi phục**. Không nên bắt đầu implementation mở rộng trước khi các contract này được chốt và mentor review.
