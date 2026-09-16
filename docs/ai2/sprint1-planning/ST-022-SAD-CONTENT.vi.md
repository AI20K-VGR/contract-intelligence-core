# Contribution cho SAD / System Architecture — AI2 v0.2

| Thuộc tính | Nội dung |
|---|---|
| **Owner soạn** | Trần Văn Dũng — AI Engineer / AI2 |
| **Trạng thái** | Draft ready; chờ AI1, BE, FE, Leader và Mentor review |
| **Mục đích** | Contribution AI2 để ghép vào SAD chung, không phải SAD toàn team |
| **Giới hạn** | Không là approval triển khai code, API Spec, DB migration hoặc bằng chứng quality/runtime |

## 1. Mục tiêu, phạm vi và nguồn chuẩn

AI2 biến OCR/layout snapshot bất biến thành structure, fact, citation, context, finding kỹ thuật và metadata đánh giá để reviewer kiểm tra. AI2 không OCR lại PDF, không tự xác định role contract/annex từ filename/upload order, không ghi đè raw OCR/machine output và không đưa ra kết luận pháp lý.

Thứ tự tham chiếu khi có mâu thuẫn: BRD đã được Leader chốt → PRD AI2 → data contract AI1→AI2 → SAD này. Các proposal chưa được Mentor duyệt chỉ là input review, không tự động thành quyết định triển khai.

Ngoài phạm vi AI2: OCR engine/source PDF, endpoint/wire format, database schema/migration, auth/RBAC implementation, storage/deployment/SLO và UI implementation. AI2 chỉ định nghĩa semantic object, invariants, input/output và acceptance cho các phần đó.

## 2. System context và luồng end-to-end

```text
Dossier manifest
  → AI1 OCR/Layout snapshot + immutable page render
  → AI2 snapshot validation
  → clause/table binding
  → fact extraction + raw evidence
  → normalization + context gate
  → structured finding / semantic candidate
  → BE persistence and versioned query
  → FE two-source evidence viewer
  → BE append-only review revision
  → audit/evaluation metadata
```

1. Backend/intake tạo dossier manifest; role `CONTRACT|ANNEX` và relation do người có thẩm quyền xác nhận.
2. AI1 tạo snapshot immutable theo document. Re-OCR phải sinh snapshot mới.
3. AI2 validator chỉ cho snapshot hợp lệ đi vào extraction/comparison; thiếu evidence không được “sửa” bằng suy đoán.
4. AI2 tạo artifact machine immutable; Backend là system of record, FE chỉ hiển thị source/evidence và gửi review action.
5. Re-OCR/rerun tạo run mới, không update result/review cũ.

## 3. Component boundary và ownership

| Thành phần | Trách nhiệm | Không được làm |
|---|---|---|
| Dossier manifest | Membership, role contract/annex, relation/effective date và source xác nhận | AI/worker suy role từ tên file hoặc upload order |
| AI1 OCR/Layout | Raw text, line/word/table geometry, page render, warnings/errors, engine/version, snapshot lineage | Fact nghiệp vụ, conflict, legal precedence |
| AI2 validator | Validate schema/ref/span/frame, phân loại valid/partial/failed/incompatible | Thay raw OCR, tự bù dữ liệu thiếu |
| AI2 extraction | Clause, fact, context, citation, semantic claim, extraction lineage | Sở hữu source PDF hoặc persistent store |
| AI2 comparison | Context gate, pair, finding run/finding, technical candidate amendment | Set review state hoặc quyết định document thắng |
| Backend | Persistence, API, async run/batch, idempotency, CAS/RBAC, current read model | Tự suy luận content/domain outcome |
| Frontend | Two-source navigation, citation/bbox overlay, review/rebase UX | Thay source/machine result hoặc tự tính provenance |
| Reviewer/adjudicator | Confirm/correct/reject/request evidence, close review theo quyền | Biến finding máy thành legal conclusion không qua policy |

## 4. Input contract AI1 → AI2

### 4.1 Dossier manifest

AI2 cần manifest versioned gồm `manifest_id`, `dossier_id`, version, actor/timestamp, document membership, role, annex number/effective date khi có và source xác nhận relation.

- `USER_DECLARED`: lưu actor/timestamp; không phải evidence từ nội dung.
- `SOURCE_EVIDENCE`: giữ citation source.
- Thiếu manifest/relation xác nhận: AI2 vẫn extract nội bộ document, nhưng trả `BLOCKED_MANIFEST` cho comparison contract–annex/annex–annex.

### 4.2 OcrSnapshot canonical

AI1 cung cấp `ai1.snapshot.v1`, immutable theo document với:

```text
snapshot_id, schema_version, dossier_id, document_id, source_digest,
engine_name/version, model_version?, prompt_version?, page_count,
processing_ms, created_at, status
```

Mỗi page có `page_no`, input type `TEXT_LAYER|SCANNED_OCR|MIXED`, status `SUCCESS|PARTIAL|FAILED`, raw text/digest, warnings/error, upright render URI/digest, pixel dimensions, source page index, rotation, render profile/transform.

Mỗi line/word/table ref có ID scoped theo snapshot. Bbox dùng duy nhất `[x0,y0,x1,y1]`, normalized 0..1, origin top-left trên upright render. Offset là Unicode code point, 0-based/end-exclusive trên `line.text_raw`; consumer JavaScript xử lý bằng `Array.from`, không dùng UTF-16 offset.

Table không được là text blob: `table → fragment → row → cell`; cell có text, bbox, row/column index, rowspan/colspan khi áp dụng và line refs. Snapshot phải giữ reading order, page status và re-OCR lineage.

### 4.3 Validator behavior

AI2 validator reject/quarantine input có schema unsupported, source/render digest thiếu, snapshot-document mismatch, ref không tồn tại, bbox ngoài frame, span vượt line, word không thuộc line hoặc raw-text invariant sai.

- `SUCCESS`: đủ điều kiện extraction/comparison.
- `PARTIAL`: chỉ tạo fact có evidence; comparative finding dùng nguồn thiếu phải là `insufficient_evidence` hoặc run `PARTIAL_FAILED`.
- `FAILED`: không sinh fact/finding khẳng định từ page đó; giữ error cho BE/FE hiển thị/retry.

## 5. AI2 domain objects và invariants

### 5.1 Citation, clause và table evidence

```text
Citation(id, snapshot_id, document_id, components[])
CitationComponent(page_no, line_id, char_start, char_end, word_ids[], bbox_refs[])
```

`bbox_refs` có thể trỏ `LINE`, `WORD`, `CLAUSE_REGION`, `TABLE`, `TABLE_CELL`. Citation có thể nhiều component cho source đa dòng/đa trang. Mỗi component bắt buộc có line/raw span; cell citation thêm table-cell ref, không thay line/span bằng bbox cell. UI highlight từng component trên đúng page, không union bbox qua trang.

Clause có ID, hierarchy Điều→Khoản→Điểm, title/text raw, citation IDs và một/many clause regions. Table cell/Clause được đưa ra UI phải có ít nhất một citation resolve được.

### 5.2 Extraction, facts và semantic claims

```text
ExtractionRun(id, manifest_id, snapshot_ids[], rule_version, normalizer_version,
              producer_version, status)
Fact(id, extraction_run_id, entity_type, business_role, raw_value,
     normalized_value?, normalization_reason?, context, citation_ids[],
     context_citation_ids[], clause_id?, table_cell_id?, status)
SemanticClaim(id, extraction_run_id, clause_id, subject, action, object,
              recipient, modality, polarity, time, conditions, citation_ids[], status, reason?)
```

Fact types: `PRICE`, `QUANTITY`, `DATE`, `DURATION`, `PARTY`, `TAX_CODE`, `REFERENCED_CONTRACT_NUMBER`. Raw value luôn giữ nguyên; unreadable/ambiguous giữ `normalized_value=null` cùng reason. Fact được compare cần citation resolve được; context quan trọng phải có citation riêng.

Semantic claim không suy từ keyword phủ định đơn lẻ. Thiếu subject/action/condition/evidence cần thiết phải nêu `INSUFFICIENT_EVIDENCE`.

### 5.3 Comparison và finding

AI2 chỉ pair/compare sau compatibility gate: business role, subject, unit, currency, VAT basis, scope và validity phải tương thích.

```text
FindingRun(id, manifest_id, extraction_run_ids[], snapshot_ids[],
           pair_policy_version, rule_version, execution_status)
Finding(id, finding_run_id, dossier_id, family, finding_type, comparison_scope,
        model_disposition, severity?, explanation, left_fact_or_claim_id,
        right_fact_or_claim_id, left_citation_ids[], right_citation_ids[],
        precedence_evidence_citation_ids[])
```

- `family`: `STRUCTURED | SEMANTIC`.
- `comparison_scope`: `WITHIN_DOCUMENT | CONTRACT_ANNEX | ANNEX_ANNEX`.
- `model_disposition`: `comparable_match | comparable_difference | candidate_amendment | not_comparable | insufficient_evidence`.
- Finding machine không có `review_state`; mỗi finding liên tài liệu có evidence hai phía.
- `candidate_amendment` cần reference base, wording sửa đổi, scope tương thích và effective date muộn hơn. Đây là candidate kỹ thuật; AI2 không chọn document thắng.

## 6. HITL, rerun và failure semantics

```text
ReviewRevision(id, target_type, target_id, parent_revision_id?, actor_id,
               created_at, action, reason?, patch_value?, patch_evidence_selection?)
```

- Target: `FACT | FINDING | CLAUSE | EVIDENCE_SELECTION`.
- Action: `CONFIRM | CORRECT | REJECT | REQUEST_EVIDENCE`.
- Machine OCR, citation, bbox, fact/finding và revision cũ immutable. Bbox edit là overlay evidence selection trong cùng snapshot/render.
- Backend nhận `expected_parent_revision_id`; stale action trả `409` cùng current revision để FE rebase. Không last-write-wins.
- Current review state là read model fold từ revision chain; không ghi đè artifact machine.
- Re-OCR tạo snapshot mới; extraction/comparison tạo run mới pin snapshot/manifest/rule version. Cũ vẫn truy vấn/audit được.

## 7. Integration, lifecycle và error contract

Backend/AI1 sở hữu queue/job implementation, nhưng SAD yêu cầu semantics:

```text
QUEUED → VALIDATING → WAITING_FOR_AI1 → EXTRACTING → COMPARING → NEEDS_REVIEW
      → COMPLETED | PARTIAL_FAILED | FAILED | QUARANTINED
```

- Mọi OCR source required terminal trước khi structuring/extraction dossier được enqueue.
- Source `PARTIAL`/`FAILED` không tạo comparative alert khẳng định; run giữ reason/missing evidence.
- Idempotency pin dossier, manifest version, snapshot/source set và rule version.
- Retry có giới hạn, backoff và JobAttempt history; worker crash/retry exhausted chuyển `QUARANTINED`, không biến mất im lặng.
- Batch summary theo dossier: `done`, `failed`, `partial_failed`, `needs_review`.

## 8. Integration acceptance theo owner

| Owner | Điều kiện AI2 cần nhận/kiểm tra | Evidence hoàn tất |
|---|---|---|
| AI1 | Scan/text-layer cùng schema, line/word geometry, rotation, render digest, table cell, blank/partial/failed, re-OCR | Citation thật resolve và overlay đúng trên hai representation |
| Backend | Manifest version, IDs/ref integrity, run lineage, retry/idempotency, immutable revision và CAS | Design/API review có ngày; stale review trả rebase conflict |
| Frontend | Hai-source navigation, Unicode raw span, upright bbox transform, machine/reviewer overlay | Walkthrough highlight/correction trên render đã xác định |
| Leader/Reviewer | Scope, manifest owner, semantic boundary, reviewer/adjudicator, Gate B target | Quyết định bằng chữ và ADR status cập nhật |

## 9. Security, observability và evaluation

- Không log PDF, page image, raw OCR, prompt hoặc mentor ground truth. Log chỉ gồm run/snapshot/document/page/engine/status/count/error code.
- Source/render không commit Git. External service chỉ nhận data sau policy/Mentor approval; service, data type, purpose, retention và approver phải có trong register.
- Encryption/RBAC/retention/deployment do Leader/BE chốt; SAD không claim đã có trước sign-off.
- Gate B báo fact/citation/bbox/finding, throughput/cost cùng `n`, denominator, source/gold/rule/snapshot/engine version và failed/missing/not-run. Fixture planning không là evidence runtime.

## 10. ADR register

| ADR | Quyết định | Owner | Safe behavior khi pending | Điều kiện đóng |
|---|---|---|---|---|
| ADR-01 | Manifest, role và annex relation source | Leader + BE | Chặn compare liên document | Manifest contract được review |
| ADR-02 | Snapshot schema/granularity, table/multi-page provenance | AI1 + BE + FE | Chỉ fixture/example-only, chưa freeze integration | Conformance walkthrough |
| ADR-03 | API/persistence/run/retry/idempotency | BE | AI2 không định nghĩa endpoint/schema cuối | BE review có evidence |
| ADR-04 | Reviewer/adjudicator, amendment và semantic scope | Leader + Reviewer | Candidate kỹ thuật, không legal conclusion | Policy xác nhận bằng chữ |
| ADR-05 | External OCR/LLM, retention, sensitivity | Mentor + Leader | External route disabled; local/example-only | Service register được duyệt |
| ADR-06 | Gate B sample, owner, target và audit protocol | Mentor + AI team | Không claim metric/quality | Gold/source/auditor được chốt |

## 11. Review gate và test checklist

SAD chỉ chuyển `Ready for Review` khi trace từ BRD/PRD requirement đến component, contract, case và owner đã self-review. Test thiết kế tối thiểu:

1. Citation multi-line, multi-page, table-cell; Unicode `A😀B`; tiếng Việt composed/decomposed; rotation/frame đúng.
2. Manifest thiếu, annex relation sai, citation không resolve, page partial/failed đều có behavior rõ.
3. Structured controls trả `not_comparable`/`insufficient_evidence`; semantic polarity/condition candidate không dựa vào keyword.
4. Re-OCR/rerun giữ old lineage; duplicate pair không tạo finding trùng.
5. Concurrent review rebase, bbox overlay và machine artifact bất biến.
6. Batch retry/crash/quarantine và summary dossier không làm job biến mất.

Không phần nào trong SAD này thay thế Mentor approval architecture/project structure trước product code.
