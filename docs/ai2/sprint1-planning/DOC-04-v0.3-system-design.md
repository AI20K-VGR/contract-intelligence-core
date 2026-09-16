# DOC-04 v0.3 — Thiết kế hệ thống chuẩn: Contract Intelligence (PROD-01)
**Trạng thái:** Draft để team + mentor review | **Giải quyết:** toàn bộ P0 (1-6) và P1 (1-6) trong `CONTRACT_INTELLIGENCE_ARCHITECTURE_REVIEW.vi.md`
**Không đổi so với v0.1:** FastAPI + worker/queue, native-first, anti-hallucination, HITL gate, routing local cho tài liệu nhạy cảm, không Kubernetes/microservices.

> Ghi chú vai trò: tài liệu này thiết kế **toàn bộ data model + domain logic** theo đúng yêu cầu đề bài (để không phải thiết kế lại giữa chừng), nhưng phần "Phạm vi implement Sprint 2-3" ở mục 10 khoanh vùng rõ **cái gì bắt buộc code trong 1 tháng OJT** và cái gì là contract đã chốt nhưng có thể triển khai tối giản trước, mở rộng sau — tránh việc điều chỉnh scope biến thành lý do trì hoãn thiết kế đúng.

---

## 1. Aggregate trung tâm: Dossier (giải quyết P0-01)

Đơn vị xử lý và chấm điểm không phải `Document` mà là **Dossier**: một hợp đồng + 0..n phụ lục nộp cùng nhau.

```
Dossier
├── id, tenant_id, status, created_at, batch_id (nullable nếu upload đơn)
└── DossierDocument[]  (bảng nối, giữ vai trò từng file trong dossier)
     ├── dossier_id, document_id
     ├── role: CONTRACT | ANNEX
     ├── upload_order: int
     ├── annex_no: int (null nếu role=CONTRACT)
     ├── effective_date: date (nullable — ngày hiệu lực phụ lục, dùng cho precedence)
     └── relationship_evidence: text (căn cứ xác định phụ lục này thuộc hợp đồng nào — trích dẫn từ nội dung, hoặc "user-declared" nếu do người upload chỉ định thủ công)
```

**Nguyên tắc:** mọi pipeline, review queue, batch summary, và API đều lấy `dossier_id` làm khóa chính điều phối — không phải `document_id`. `Document` chỉ còn là 1 file vật lý thuộc về đúng 1 dossier qua `DossierDocument`.

**Conflict scope dùng lại cấu trúc này trực tiếp:**
- `WITHIN_DOCUMENT`: 2 clause cùng 1 `document_id`
- `CONTRACT_ANNEX`: 1 clause có `document.role=CONTRACT`, 1 clause có `role=ANNEX`, cùng `dossier_id`
- `ANNEX_ANNEX`: cả 2 clause có `role=ANNEX`, cùng `dossier_id`, khác `document_id`

---

## 2. Provenance end-to-end: OCR snapshot → bbox → citation (giải quyết P0-02, P0-03)

### 2.1 Nguyên tắc bbox bắt buộc
- Toạ độ **chuẩn hoá 0..1**, origin **top-left**, theo **upright frame** (đã xoay đúng theo `rotation` thực đo — không lưu bbox theo ảnh gốc chưa xoay).
- Mọi bbox đều tham chiếu đến 1 `snapshot_id` cụ thể — không có bbox "trôi nổi" không gắn version OCR.

### 2.2 Bảng dữ liệu mới

```
PageFrame
├── id, document_id, page_no
├── width, height          # kích thước thực đo (pixel gốc, trước chuẩn hoá)
└── rotation                # 0/90/180/270, đo thực tế lúc OCR

OcrSnapshot                 # version hoá kết quả OCR — GIẢI QUYẾT vấn đề "re-OCR làm reference mơ hồ"
├── id, document_id
├── engine                  # native | gpt-5.6-luna | paddle-ocr
├── model_version, prompt_version, schema_version
└── created_at

OcrLine
├── id, snapshot_id, page_no, line_index
├── text_raw                # text thô, dùng làm cơ sở cho char offset
└── bbox (x, y, w, h)        # 0..1, upright frame

OcrWord
├── id, line_id
├── text, char_start, char_end   # Unicode code point, 0-based, end-exclusive, trên text_raw của OcrLine
└── bbox (x, y, w, h)

ClauseRegion                 # 1 clause có thể trải nhiều vùng/nhiều trang
├── id, clause_id, page_no
└── bbox (x, y, w, h)

Table
├── id, document_id, page_no
└── bbox (x, y, w, h)

TableRow
├── id, table_id, row_index

TableCell
├── id, row_id, col_index
├── text
├── bbox (x, y, w, h)
└── citation_id              # mỗi cell tự trỏ về citation riêng, không gộp thành text blob
```

### 2.3 Citation — data contract chốt cứng

```
Citation
├── id
├── snapshot_id              # OCR version cụ thể được trích dẫn
├── document_id, page_no
├── line_id                  # OcrLine
├── char_start, char_end     # Unicode code point, 0-based, end-exclusive
├── word_ids: [OcrWord.id]
└── bbox_refs: [ {type: "line"|"word"|"clause_region", id} ]
```

Mọi **Value** (citation trong trích dẫn số tiền/ngày tháng...) và mọi **Finding** (xung đột) đều dùng chung entity `Citation` này — Finding giữ 2 danh sách:

```
Finding.left_citation_ids:  [Citation.id]
Finding.right_citation_ids: [Citation.id]
```

→ UI resolve được chuỗi đầy đủ `document → page → line → char span → bbox` cho cả 2 phía của 1 xung đột, kể cả sau khi re-OCR (vì citation cũ vẫn trỏ đúng `snapshot_id` cũ, không bị ghi đè).

---

## 3. Conflict domain: 2 family, 3 scope, disposition, precedence (giải quyết P0-04)

### 3.1 Tách 2 family

| Family | Cách phát hiện | Ví dụ |
|---|---|---|
| `STRUCTURED` | Rule/normalizer có version — so sánh giá trị đã chuẩn hoá (số tiền quy về cùng đơn vị, ngày quy về ISO) | Số tiền Điều 3 ≠ số tiền Phụ lục 1 |
| `SEMANTIC` | Embedding similarity + LLM judge | Điều khoản diễn đạt khác câu chữ nhưng mâu thuẫn ý nghĩa |

`STRUCTURED` luôn chạy trước và có version cụ thể (`normalizer_version`) — ưu tiên hơn `SEMANTIC` vì rẻ hơn, xác định hơn, ít rủi ro "bịa" mâu thuẫn.

### 3.2 Compatibility gate — bắt buộc trước khi so sánh

Chỉ so sánh 2 clause khi tương thích về: `role` (không so sánh Điều khoản định nghĩa với Điều khoản thanh toán), `subject`, `unit/currency/VAT`, `scope`, `validity` (còn hiệu lực hay đã bị thay thế). Việc này **chặn** loại lỗi "báo khác biệt bề mặt thành conflict" mà review đã cảnh báo.

### 3.3 Model Disposition (tách khỏi Review Status)

```
Finding
├── id, dossier_id
├── family: STRUCTURED | SEMANTIC
├── finding_type            # AMOUNT_MISMATCH, DATE_MISMATCH, PARTY_MISMATCH, ...
├── comparison_scope: WITHIN_DOCUMENT | CONTRACT_ANNEX | ANNEX_ANNEX
├── model_disposition: comparable_match | comparable_difference | candidate_amendment | not_comparable | insufficient_evidence
├── severity
├── context                  # đoạn văn cảnh liên quan, phục vụ reviewer đọc nhanh
├── precedence_evidence       # căn cứ xác định văn bản nào "thắng" (VD: annex có effective_date sau)
├── left_citation_ids, right_citation_ids
└── review_status: PENDING | RESOLVED | IGNORED   # ĐỘC LẬP với model_disposition
```

**Vì sao tách `model_disposition` khỏi `review_status`:** máy có thể nói "đây là candidate_amendment" (máy đề xuất), nhưng con người mới là người quyết định "resolved" hay "ignored" — gộp 2 field này sẽ khiến review action ghi đè luôn cả kết luận của máy, mất khả năng audit sau này máy đã nghĩ gì trước khi người sửa.

### 3.4 Precedence rule (annex sau sửa annex/hợp đồng trước)

Rule: nếu 2 `document.role=ANNEX` cùng `dossier_id` có `effective_date` khác nhau và cùng đề cập 1 subject, annex có `effective_date` **muộn hơn** được coi là `precedence_evidence` mặc định — nhưng luôn hiển thị cho reviewer xác nhận, không tự động ẩn annex cũ.

---

## 4. HITL: machine output bất biến + revision chain (giải quyết P0-05)

### 4.1 Nguyên tắc bất biến

`OcrSnapshot`, `Clause` (bản gốc từ máy), `Finding` (bản gốc) — **không bao giờ bị UPDATE trực tiếp**. Mọi hành động của Reviewer tạo ra 1 bản ghi mới trong `ReviewRevision`.

```
ReviewRevision
├── id
├── target_type: CLAUSE | FINDING | BBOX
├── target_id
├── actor_id, created_at, reason
├── base_revision_id         # revision mà action này dựa trên (null nếu là action đầu tiên trên bản gốc máy)
├── patch_value               # thay đổi giá trị (JSON diff hoặc giá trị mới)
├── patch_bbox                 # thay đổi bbox nếu reviewer vẽ/chỉnh lại vùng
└── action: CONFIRM | CORRECT | REJECT
```

### 4.2 Xử lý concurrent edit

Khi Reviewer B gửi action với `base_revision_id` không còn là revision mới nhất (Reviewer A đã sửa trước) → API **reject** (409 Conflict) kèm `current_revision_id` mới nhất để FE tự rebase, **không** ghi đè im lặng (last-write-wins bị cấm theo review).

### 4.3 Trạng thái hiển thị hiện tại

`current_value(target)` = fold toàn bộ `ReviewRevision` theo `target_id`, sắp theo `base_revision_id` — tính runtime hoặc cache lại, nhưng nguồn sự thật luôn là chuỗi revision, không phải 1 cột "giá trị hiện tại" có thể bị ghi đè.

---

## 5. Job & Batch lifecycle (giải quyết P0-06)

```
Batch
├── id, tenant_id, status: RUNNING | COMPLETED | FAILED_PARTIAL
└── created_at

PipelineRun                    # 1 run xử lý 1 dossier qua toàn bộ pipeline
├── id, dossier_id, batch_id (nullable)
├── status: QUEUED | RUNNING | NEEDS_REVIEW | COMPLETED | FAILED | QUARANTINED
└── idempotency_key            # chống submit trùng

Job                             # 1 bước trong pipeline (OCR 1 document, structuring 1 dossier...)
├── id, pipeline_run_id, step: OCR | STRUCTURING | EXTRACTION | CONFLICT_DETECTION
├── target_id                  # document_id hoặc dossier_id tuỳ step
└── status

JobAttempt                      # mỗi lần retry là 1 attempt riêng, giữ lại lịch sử
├── id, job_id, attempt_no
├── status, error_code, error_message
└── started_at, finished_at
```

**Completion barrier:** `STRUCTURING` job của 1 dossier chỉ được enqueue khi **toàn bộ** `OCR` job của mọi document trong dossier đó đã ở trạng thái terminal (`COMPLETED` hoặc `FAILED`) — tránh structuring chạy khi phụ lục chưa OCR xong.

**Retry & dead-letter:** mỗi `Job` có retry policy riêng theo `step` (OCR retry nhiều hơn vì phụ thuộc API ngoài); sau N lần fail → chuyển `PipelineRun.status = QUARANTINED`, không tự động retry vô hạn, không "biến mất im lặng" — luôn có `Job`/`JobAttempt` record để trace.

**Idempotency:** `idempotency_key` (hash của file + dossier grouping) chặn việc submit trùng dossier tạo 2 `PipelineRun` song song.

---

## 6. Bảng chi phí theo bước xử lý (giải quyết P1-2)

| Bước | Engine | Lý do chọn | Chi phí ước tính/dossier* | Ghi chú |
|---|---|---|---|---|
| OCR (text-layer) | PyMuPDF native | Miễn phí, nhanh | $0 | Chỉ áp dụng PDF có text layer thật |
| OCR (scan) | GPT-5.6 Luna | Rẻ nhất trong nhóm vision API đã benchmark | ~$0.20-1.20/1M token, cần đo số token/trang thật | **Cần benchmark trước khi route dữ liệu thật (xem mục 9)** |
| OCR (nhạy cảm/fallback) | PaddleOCR local | Không rời máy, miễn phí (tốn compute) | $0 tiền, tốn thời gian CPU | Bắt buộc cho tài liệu sensitive |
| Structuring | LLM (OpenAI) | Tái dùng client đã có | *(cần đo)* | |
| Extraction/Citation | LLM (OpenAI) | Tái dùng client đã có | *(cần đo)* | |
| Embedding (semantic conflict) | OpenAI embedding | Chuẩn bị so khớp ngữ nghĩa | *(cần đo)* | |
| Semantic judge | LLM (OpenAI) | Ra quyết định cuối cho semantic conflict | *(cần đo)* | Chỉ chạy sau khi qua compatibility gate — giảm số lần gọi |

*Cần điền số liệu thật sau benchmark; sau đó nhân với **projection 1.000 dossier/tháng** để có con số trình mentor.

---

## 7. Đa ngôn ngữ (giải quyết P1-3)

```
Document.document_language   # vi | en | mixed
Page.page_language            # có thể khác document_language (trang song ngữ)
```

Quy tắc: nếu `page_language = mixed`, áp dụng reading order theo block riêng biệt (không trộn dòng 2 ngôn ngữ vào 1 `OcrLine`); test sample tối thiểu: 1 hợp đồng thuần Việt, 1 thuần Anh, 1 trang song ngữ thật.

---

## 8. Cache versioning (giải quyết P1-4)

Cache key = `hash(tenant_id, dossier_scope, source_digest, preprocessing_version, render_version, engine, model_version, prompt_version, schema_version)`. Đổi bất kỳ thành phần nào (kể cả đổi prompt) → cache miss, không tái dùng kết quả cũ sai ngữ cảnh. Retention policy: xoá cache sau N ngày hoặc khi dossier chuyển `COMPLETED`.

---

## 9. Benchmark gate (giải quyết P1-1)

**Không** dùng GPT-5.6 Luna cho dữ liệu thật ở Sprint 2 nếu chưa benchmark. Hai lựa chọn:
- **(a)** Chạy benchmark CER/WER trên bộ mẫu đã gán nhãn **trước** khi bắt đầu Sprint 2 (đẩy benchmark từ Sprint 3 lên ngay đầu Sprint 2), hoặc
- **(b)** Nếu không kịp, đánh dấu route Luna là **experimental**, cấm dùng kết quả để đưa ra claim chất lượng trong demo — chỉ dùng PaddleOCR (đã biết baseline) cho dữ liệu trình bày chính thức.

## 10. Bảo mật bổ sung (giải quyết P1-5)

Ngoài cờ sensitivity đã có: encryption in transit (TLS nội bộ giữa Backend↔AI Service) và at rest (Object Storage + Postgres), policy retention/deletion theo thời gian, phân quyền upload/download theo role, log redaction (không log `text_raw`, chỉ log ID), key rotation định kỳ cho OpenAI API key, audit access log (ai đã xem/tải document nào, khi nào).

---

## 11. Phạm vi implement Sprint 2-3 trong bối cảnh OJT 1 backend engineer

Toàn bộ mục 1-8 là **contract chốt cứng** (schema, taxonomy, state machine) — nên chốt và trình mentor ngay, vì thiết kế đúng từ đầu rẻ hơn nhiều so với sửa giữa chừng. Nhưng **không nhất thiết implement đầy đủ 100% trong 1 tháng**. Đề xuất phân lớp ưu tiên implement:

| Mức độ | Bao gồm | Lý do |
|---|---|---|
| **Bắt buộc Sprint 2** | Dossier + DossierDocument, OcrSnapshot cơ bản (không cần versioning phức tạp ngay), Citation với char_span + bbox, Job/PipelineRun cơ bản (không cần JobAttempt chi tiết ngay) | Đây là xương sống — thiếu sẽ phải đập lại toàn bộ |
| **Bắt buộc Sprint 3** | ReviewRevision (immutable, tối thiểu 1 loại action CONFIRM/CORRECT), Finding với disposition + 3 scope, precedence cơ bản (1 rule: effective_date muộn hơn thắng) | Đủ để demo đúng yêu cầu đề bài |
| **Có thể tối giản/hoãn nếu thiếu thời gian** | OcrWord ở mức word-level đầy đủ (có thể tạm dừng ở line-level, note rõ là known limitation), multi-language contract đầy đủ (làm đúng cho tiếng Việt trước, tiếng Anh sau), cache versioning đầy đủ (có thể tắt cache ở Sprint 2, bật ở Sprint 3), dead-letter/quarantine tự động (Sprint 2 có thể xử lý thủ công qua log, tự động hoá ở Sprint 3) | Review có nêu nhưng không phải yêu cầu chấm điểm cứng theo assignment gốc — cần Chương xác nhận lại với đề bài gốc xem mục nào thực sự "must" |

**Khuyến nghị:** mang bảng phân lớp này ra họp với Trang/AI Engineer/mentor — không tự quyết định một mình việc gì hoãn được, vì review dựa trên `assignment.pdf` (đề bài chấm điểm), cần đối chiếu lại từng mục P0 với đúng yêu cầu chấm để biết cái nào là "phải có để qua", cái nào là "nên có nhưng có thể ghi chú known limitation".

---

## 12. Điều kiện để chuyển DOC-04 sang "gửi mentor review" (theo mục 7 của bản review)

- [ ] Team xác nhận mô hình Dossier (mục 1) và cập nhật vào ERD chính thức
- [ ] Đóng băng citation/bbox/table contract (mục 2) — có ví dụ thật từ 1 trang hợp đồng mẫu
- [ ] Chốt taxonomy/disposition conflict (mục 3) cùng AI Engineer
- [ ] Chốt revision contract cho HITL (mục 4) — đặc biệt cơ chế concurrent edit
- [ ] Vẽ state machine batch/job (mục 5), phản ánh vào API boundary (`dossier_id` thay vì `document_id` trong path)
- [ ] Bảng cost-per-dossier (mục 6) có số liệu thật, không chỉ giá token
- [ ] Quyết định benchmark gate (mục 9): benchmark sớm hay đánh dấu experimental
- [ ] Thống nhất bảng phân lớp ưu tiên implement (mục 11) với cả team + mentor
