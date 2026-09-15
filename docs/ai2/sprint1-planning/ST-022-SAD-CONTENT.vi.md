# Contribution cho SAD / Architecture — AI2 v0.1

**Owner soạn:** Trần Văn Dũng — AI2  
**Trạng thái:** Draft ready — đề xuất interface/pipeline, chờ AI1/BE/FE/leader review.  
**Nguồn chuẩn:** [ST-017-DATA-CONTRACT.vi.md](ST-017-DATA-CONTRACT.vi.md), [ST-015-DOC-02-BRD.vi.md](ST-015-DOC-02-BRD.vi.md), [ST-021-EXPERIMENT-CARD.vi.md](ST-021-EXPERIMENT-CARD.vi.md).

## 1. Context và pipeline logic

`Dossier manifest → AI1 OCR/Layout snapshot → AI2 contract validation → fact extraction/raw evidence → normalization + context gate → comparison/finding → BE persistence/query → FE two-sided evidence viewer → BE append-only review revision`

Pipeline tạo finding kỹ thuật; không tự chọn điều khoản hiện hành, tự kết luận legal validity hoặc suy relationship từ thứ tự upload. `Gold`/label evaluation tách riêng với product HITL review.

## 2. Component boundary và ownership

| Thành phần | Trách nhiệm | Không thuộc thành phần |
|---|---|---|
| Dossier composition | Xác định `dossier_id`, document membership và nguồn xác nhận vai trò hợp đồng/phụ lục. | AI2 không suy role/preference từ upload order. Owner cần nhóm chốt. |
| AI1 OCR/Layout producer | Tạo `OcrSnapshot` bất biến: digest, engine/version, representation, pages, raw text, hierarchy/table refs và geometry. Re-OCR tạo snapshot/child IDs mới. | AI2 không xác nhận chất lượng OCR/layout. |
| AI2 validator + extraction | Validate refs/offset/frame; tạo `Fact` typed với raw/normalized/context/citation, rule version và extraction lineage. | Không sở hữu source PDF/OCR hoặc persistent store. |
| AI2 context/comparison | Pair/gate context, tạo immutable `FindingRun` và `Finding`, candidate amendment/evidence semantics. | Không đặt `review_state` hoặc legal precedence. |
| BE repository/API | System of record cho snapshots, machine artefacts, revisions; enforce ref integrity, append-only review và concurrency. | AI2 không quyết endpoint, DB schema hoặc auth. |
| FE HITL viewer | Điều hướng hai nguồn, render raw span/bbox trong frame đã chốt, gửi review action. | FE không tự tính current state hoặc ghi đè output máy. |
| Reviewer | Tạo `ReviewRevision`, xác nhận/sửa/từ chối/yêu cầu evidence. | Không thay raw OCR/citation/input snapshot qua correction. |

## 3. Interface và data invariants

### AI1 → AI2

- Snapshot thật yêu cầu `schema_version`, `snapshot_id`, `document_id`, SHA-256 `source_digest`, `engine{name,version}`, `representation` và metadata page/frame/rotation/coord space.
- Citation phải resolve về snapshot/document/page/line/raw span/word/bbox. Span dùng Unicode code points trên raw text; không normalize trước offset và JavaScript không dùng UTF-16 length.
- Geometry dùng `upright_rendered_page`, origin top-left, normalized `[0,1]`; FE chỉ transform khi AI1–FE xác nhận viewer frame khác.
- Nhóm phải chốt snapshot-per-page hoặc snapshot-per-document (`pages[]`) trước integration; contract v0.2 hiện không đủ rõ để tự giả định.
- Multi-page, multi-line, clause/table-cell provenance phải có một shape frozen trước khi FE implement highlight.

### AI2 → BE/FE

- `Fact`, `FindingRun`, `Finding`, `Citation` có IDs unique và refs khép kín. `FindingRun` liệt kê toàn bộ `snapshot_ids`, rule version, input/output IDs và execution status.
- Machine finding chỉ mang `family`, `finding_type`, `comparison_scope`, `model_disposition`, hai fact refs và precedence evidence khi áp dụng; **không chứa `review_state`**.
- `ReviewRevision` có `revision_id`, `previous_revision_id`, `finding_id`, actor, timestamp, state, reason và corrected payload allowlist. Current state là overlay từ revision chain hợp lệ.
- Backend nhận `expected_previous_revision_id`, xác thực actor/quyền thao tác ở server-side và trả conflict/rebase cho concurrent review; không lấy timestamp để quyết định thắng.
- Corrected payload không sửa raw text, citation, snapshot hoặc model disposition. Rerun tạo output mới.

## 4. Lifecycle, failure và vận hành

- **Missing evidence:** context/value/evidence cần thiết thiếu → `insufficient_evidence`; citation không resolve → failed binding/unverifiable được ghi riêng, không che denominator audit.
- **Known mismatch:** role/subject/unit/VAT/scope khác hoặc kỳ độc lập không giao nhau → `not_comparable`.
- **Rerun:** re-OCR tạo snapshot mới; extraction/comparison tạo run mới; old run/reviews vẫn query/truy vết được.
- **Lineage:** SAD cần bổ sung extraction-run/producer version cho Fact, schema compatibility/version pin và quy ước envelope `finding_run` là package một run hay lịch sử nhiều run.
- **Operational unknowns:** malformed/unsupported-schema/partial snapshot, retry/idempotency và async run status cần BE/AI1 chốt trước API implementation.

## 5. Bảo mật, quan sát và deployment

- Chỉ ghi fact có bằng chứng: baseline đề xuất dùng local rule/normalizer, external services = none; compute/latency/hardware chưa đo.
- Phải tách audit/run metadata, failed/missing citations và metric counts khỏi raw OCR log. Logging/retention raw OCR là quyết định privacy của nhóm.
- Không khẳng định topology, queue, database, endpoint, RBAC, encryption, retention, SLO hay production monitoring khi chưa có quyết định/evidence.
- Các quyết định integration và test đã được đưa vào [ST-022-TRACEABILITY-AND-INTEGRATION.vi.md](ST-022-TRACEABILITY-AND-INTEGRATION.vi.md).
