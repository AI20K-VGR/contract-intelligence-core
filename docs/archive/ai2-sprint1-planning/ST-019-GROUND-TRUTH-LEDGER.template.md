# Ledger planning v0.2

Template tiếng Việt. Từ điển này là nguồn chuẩn cho các bảng ledger; chưa có label review hoặc run thực tế. Cỡ mẫu và quy trình nằm trong [ST-019-GROUND-TRUTH-PLAN.vi.md](ST-019-GROUND-TRUTH-PLAN.vi.md).

## A. Logical gold facts

Khóa: `(gold_version, logical_fact_id)`. Cột: `document_id, document_role, source_clause_ref, entity_type, business_role, raw_value, normalized_value, subject, unit, currency, tax_basis, applicability_scope, validity_start, validity_end, label_revision_id, previous_label_revision_id, labeler, label_review_status, reviewer, reviewed_at, review_note`.

`label_review_status`: draft / proposed_correction / adjudicated. Reviewer chưa phản hồi: reviewer và reviewed_at = null. Giá trị không đọc được: normalized_value = null kèm lý do. Source refs giai đoạn planning dùng vị trí đoạn tự soạn; chưa giả làm OCR citation.

## B. Logical gold cases

Khóa: `(gold_version, case_id)`. Cột: `left_logical_fact_id, right_logical_fact_id, comparison_scope, family, finding_type, expected_disposition, rationale, label_revision_id, previous_label_revision_id, label_review_status, labeler, reviewer, reviewed_at, review_note`.

Nội dung C01–C15 nằm ở [ST-016-CASE-CATALOG.vi.md](ST-016-CASE-CATALOG.vi.md). Semantic dùng logical proposition IDs trong hai trường logical_fact_id với entity_type=proposition; không tính chúng vào metric bảy structured entity types. Mỗi proposition ghi subject/action/object/recipient/time/condition/polarity.

## C. Evidence bindings theo snapshot

Khóa: `(gold_version, logical_fact_id, snapshot_id)`. Cột: `representation, fact_id, document_id, clause_id, table_row_id, table_cell_id, citation, binding_status, audit_actor, audited_at, audit_note`.

`binding_status`: unbound / bound / unreadable / missing. Citation chỉ khác null khi resolve được. Table refs nullable khi fact không ở bảng. Namespace word/line/bbox nằm trong snapshot; citation luôn có snapshot_id. Cùng logical fact ở hai representations có hai binding riêng. Citation trái/phải được lấy qua binding, không chép vào gold case.

## D. Evaluation runs và predictions

Round: `round_id, gold_version, rule_version, snapshot_ids, started_at, completed_at`. Case result: `round_id, run_id, case_id, representation, execution_status, prediction_ids, error_reason`. Prediction: `prediction_id, run_id, left_fact_id, right_fact_id, comparison_scope, family, finding_type, predicted_disposition`.

Case key `(round_id, case_id, representation)`; prediction key `prediction_id`. execution_status = not_run / completed / failed. Danh sách prediction_ids cho phép 0 hoặc nhiều predictions để đo duplicate; 30 là tổ hợp dự kiến mỗi round, không giới hạn output. Trong output sản phẩm dùng `model_disposition`; khi đưa vào evaluation ánh xạ sang `predicted_disposition`.

## E. Review HITL sản phẩm

ReviewRevision có finding_id, previous_revision_id, actor, timestamp, review_state, reason, corrected_payload theo data contract. Không dùng review_state này để thay label_review_status. Gold corrections, model reruns và HITL corrections là ba lịch sử khác nhau.

## Dòng mẫu chưa thực hiện

| Gold version | Case | Label status | Evidence binding | Execution |
|---|---|---|---|---|
| v0.2-draft | C01–C15, xem catalog | draft | unbound | not_run |

Khi nhập tracker/Excel, giữ nguyên các khóa và các bảng riêng. Chưa xuất workbook trong gói Markdown này.
