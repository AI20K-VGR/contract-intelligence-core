# Data contract AI2 v0.2

Trạng thái: thiết kế để AI1/BE/FE review. Mẫu JSON đi kèm là ví dụ khép kín tự soạn; bbox/layout đều giả lập và không được dùng chứng minh OCR đúng. source_digest=null có lý do; khi chạy thật phải có digest nguồn và engine thực. Đây là từ điển contract, chưa phải JSON Schema validator production.

## Kiểu và field bắt buộc

| Đối tượng | Field required | Nullable / quy ước |
|---|---|---|
| Envelope | schema_version:string, example_only:boolean, offset_unit:string, snapshots:array, facts:array, finding_run:object, findings:array, review_revisions:array | Arrays rỗng chỉ khi không có đối tượng tương ứng; mẫu có đủ hai phía. |
| OcrSnapshot | snapshot_id:string, document_id:string, source_digest:string hoặc null, engine{name,version}, representation, page, lines, words, bboxes, clauses, table_rows, table_cells | digest null chỉ cho example_only; real snapshot có SHA-256 source. Table arrays rỗng nếu không có bảng. |
| Page | page_no:int>=1, width_px:int>0,height_px:int>0,source_rotation_degrees:number,frame,coord_space | Frame là upright_rendered_page sau rotation; geometry đo trên đúng ảnh upright này. |
| Line/word | line_id/raw_text/bbox_ref; word_id/line_id/text/char_start/char_end/bbox_ref | IDs ổn định trong một snapshot; re-OCR sinh ID mới. |
| Citation | snapshot_id,document_id,page_no,line_id,char_start,char_end,word_ids,bbox_refs | Không null cho evidence được dùng để so sánh; missing được thể hiện ở binding_status trước khi tạo fact có evidence. |
| Fact | fact_id,entity_type,business_role,raw_value,normalized_value,context,citation,context_citations | normalized_value=null nếu không đọc đủ, có reason; context cần thiết thiếu → insufficient_evidence. Clause/table refs nullable nếu không áp dụng. |
| Context | subject,unit,currency nếu nằm trong value hoặc context,tax_basis,applicability_scope,validity_start,validity_end,context_origin | Các field không áp dụng = null; validity_end=null là chưa ghi ngày kết thúc; context_origin=manual/source_rule. |
| FindingRun | run_id,snapshot_ids,rule_version,fact_ids,finding_ids,execution_status | Nhiều snapshots cho cross-document. execution_status mẫu=illustrative_only. |
| Finding | finding_id,run_id,family,finding_type,comparison_scope,model_disposition,left_fact_id,right_fact_id,precedence_evidence | Amendment có 4 điều kiện và citations; các disposition khác có thể dùng array rỗng. Không chứa review_state. |
| ReviewRevision | revision_id,previous_revision_id,finding_id,actor,timestamp,review_state,reason,corrected_payload,example_only | previous_revision_id=null ở đầu; corrected_payload=null khi không sửa; timestamp ISO có timezone. |

Offset tính bằng Unicode code points trên raw_text chưa normalize, 0-based/end-exclusive. JavaScript phải dùng Array.from(text).slice(start,end), không giả định UTF-16 length. Test thiết kế: A😀B có 3 code points; span [1,2) là 😀. Ký tự dấu tổ hợp giữ đúng encoding gốc, không normalize rồi tính offset.

Bbox [x0,y0,x1,y1] trong [0,1], x0<x1,y0<y1, origin top-left trên upright render. FE hiển thị cùng frame/size; nếu dùng PDF viewer frame khác thì phải biến đổi tọa độ đã được AI1/FE xác nhận. Bbox normalized nhân width/height ra pixel; source_rotation chỉ metadata, không xoay lần hai.

## IDs, correction và current state

Citation luôn có snapshot_id để giải namespace word/line/bbox. Fact/finding/run/revision ID duy nhất trong package; ref phải tồn tại. Clause parent null cho article gốc; row/cell có refs khép kín. Dossier nhiều tài liệu có nhiều snapshots; run liệt kê tất cả input.

Correction payload = target_type (fact hoặc finding), target_id, changes. Allowlist đề xuất: finding.review_priority/reviewed_disposition; fact.reviewed_normalized_value/reviewed_business_role. Không cho sửa citation/raw text/input snapshot qua correction. Nếu source sai, tạo snapshot/run mới. reviewed_disposition/values là overlay HITL, không đổi model_disposition/normalized_value gốc.

Current state = revision cuối trong chuỗi previous_revision_id hợp lệ; không có revision → unreviewed. Nếu hai reviewer cùng base revision, BE phải phát hiện cạnh tranh bằng expected previous revision và yêu cầu rebase; không chọn theo timestamp đơn thuần. Mẫu có confirm rồi corrected review_priority; cả hai là hành động minh họa, không phải sign-off thật.

## Walkthrough cần nhóm xác nhận

1. finding-C02 → hai fact IDs → hai citations → snapshots/document/page/line/word/bbox. Span hai amount đúng raw_value.
2. Bốn condition amendment có câu nguồn cho reference, amendment, scope/unit/tax và ngày hiệu lực.
3. Re-OCR annex → snapshot mới; tạo run mới dùng contract cũ + annex mới; findings/reviews cũ vẫn truy vết snapshot cũ.
4. review-example-02 → previous revision → target finding; current review_priority=high trong overlay; output máy giữ nguyên.

Đây là hành vi hợp đồng dữ liệu đề xuất; kiểm tra file mẫu không thay sign-off tích hợp AI1/BE/FE.
