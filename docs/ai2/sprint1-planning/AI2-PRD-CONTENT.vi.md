# Contribution cho PRD — AI2 v0.1

**Owner soạn:** Trần Văn Dũng — AI2  
**Trạng thái:** Draft ready — nội dung để người tổng hợp chèn vào PRD chung; chưa có sign-off AI1/BE/FE/leader.  
**Nguồn chuẩn:** [DOC-02-BRD.vi.md](DOC-02-BRD.vi.md), [DATA-CONTRACT.vi.md](DATA-CONTRACT.vi.md), [CASE-CATALOG.vi.md](CASE-CATALOG.vi.md).

## 1. Mục tiêu, người dùng và ngoài phạm vi

Hệ thống hỗ trợ reviewer kiểm dossier gồm một hợp đồng và `0..n` phụ lục: nhận fact có dẫn chứng, so sánh fact trong đúng ngữ cảnh và đưa ra finding kỹ thuật để reviewer kiểm tra hai phía nguồn.

- Người dùng trực tiếp: reviewer/HITL xử lý hợp đồng.
- AI2 tạo candidate và evidence; reviewer quyết định confirm, correct, reject hoặc yêu cầu thêm evidence.
- `candidate_amendment` không phải kết luận về hiệu lực pháp lý, thứ tự ưu tiên tài liệu hoặc điều khoản hiện hành.
- Không thuộc contribution AI2: UI implementation, endpoint/API wire format, database schema, OCR engine, quyền truy cập, retention, deployment, SLA hoặc ngưỡng chất lượng production.

## 2. Luồng người dùng yêu cầu tích hợp

1. Thành phần dossier do sản phẩm xác định document membership và vai trò tài liệu; AI2 **không** suy hợp đồng/phụ lục hay precedence từ thứ tự upload.
2. AI1 cung cấp OCR/layout snapshot bất biến cho tài liệu đã xác định.
3. AI2 tạo fact có raw value, normalized value, context và citation; sau đó context-gate, ghép và tạo finding.
4. BE lưu/phục vụ output máy theo run và cung cấp finding cùng evidence hai phía cho FE.
5. FE mở đúng hai nguồn, highlight citation và gửi thao tác review; BE ghi `ReviewRevision` append-only.
6. Re-OCR hoặc rerun tạo snapshot/run mới; kết quả và review cũ vẫn truy vết được.

## 3. Functional requirements

| ID | Requirement | Acceptance criteria thiết kế | Owner / dependency |
|---|---|---|---|
| PRD-AI2-FR-01 | Nhận snapshot OCR/layout có định danh, engine/version, representation, source digest, page/frame/rotation và các refs cần cho citation. | Input thiếu schema/evidence cần để so sánh không được coi là fact đủ chứng cứ; được phản ánh là thiếu evidence hoặc lỗi integration theo SAD. | AI1 cung cấp; AI2 validate contract. |
| PRD-AI2-FR-02 | Trích xuất fact typed `price`, `quantity`, `date`, `duration`, `party`, `tax_code`, `referenced_contract_number` với raw, normalized/null+reason, business role, context và citation. | Giá trị không đọc được hoặc ngày mơ hồ giữ normalized `null` kèm lý do, không đoán giá trị. | AI2; phụ thuộc snapshot AI1. |
| PRD-AI2-FR-03 | Context-gate chỉ so sánh facts khi role, subject, unit, currency, VAT basis, scope và validity áp dụng phù hợp. | C09 là `comparable_match`; C10–C12 là `not_comparable`; thiếu context/evidence cần thiết là `insufficient_evidence`. | AI2; taxonomy BRD. |
| PRD-AI2-FR-04 | Xuất đúng một `model_disposition`: `comparable_match`, `comparable_difference`, `candidate_amendment`, `not_comparable`, `insufficient_evidence`. | C01/C03/C05–C08 là comparable difference; `finding_type` chỉ nêu chiều kiểm tra, không thay disposition. | AI2. |
| PRD-AI2-FR-05 | Chỉ tạo `candidate_amendment` khi values khác nhau, cùng subject/scope phù hợp, có reference và câu sửa đổi rõ, ngày hiệu lực mới muộn hơn. | C02 là candidate cần reviewer đánh giá; thiếu câu amendment nhưng context đủ và value khác như C03 vẫn là `comparable_difference`. | AI2; reviewer xác nhận nghiệp vụ. |
| PRD-AI2-FR-06 | Semantic spike biểu diễn subject/action/object/recipient/time/condition/polarity; từ khóa phủ định đơn lẻ không đủ kết luận. | C04 là difference, C14 là not comparable, C15 là insufficient evidence. Kết quả là candidate kỹ thuật. | AI2; reviewer xác nhận scope semantic. |
| PRD-AI2-FR-07 | Mỗi fact/finding được dùng để so sánh phải truy được evidence theo snapshot, document, page, raw line/span, word và bbox; finding cross-document có hai phía evidence. | C02/C13/C15 có evidence/missing evidence hiển thị rõ; citation không resolve không được dùng để khẳng định highlight hay quality pass. | AI2 semantics; AI1/BE/FE tích hợp. |
| PRD-AI2-FR-08 | HITL lưu revision append-only và không ghi đè output máy. | Không có revision thì state là `unreviewed`; confirm/correct/reject/needs-more-evidence giữ actor, time, reason và chain predecessor. Cạnh tranh cùng base revision phải yêu cầu rebase, không last-write-wins. | BE thực thi persistence/concurrency; FE thao tác; AI2 định nghĩa semantics. |
| PRD-AI2-FR-09 | Re-OCR/rerun giữ lineage bất biến theo snapshot, rule và run version. | Snapshot/run mới không sửa facts/findings/reviews cũ; finding run cross-document liệt kê mọi snapshot input. | AI1, AI2, BE. |
| PRD-AI2-FR-10 | Hệ thống ghi đủ metadata để audit/evaluate: snapshot/rule/gold version, representation, counts, missing/failed/not-run và bindings. | C01–C15 × 2 representations là design acceptance; metric chỉ chạy sau Gate B với source/binding/audit thật. | AI2; AI1/reviewer cho Gate B. |

## 4. Ràng buộc chất lượng và an toàn AI2

- **Provenance:** raw OCR bất biến; offset là Unicode code points, 0-based/end-exclusive trên raw text; bbox normalized trên upright frame.
- **Explainability:** finding phải mang hai fact refs và lý do/disposition; missing/failed evidence phải nhìn thấy được.
- **Reproducibility:** giữ schema/source digest, OCR engine, rule version, snapshot/run/revision IDs.
- **Data handling:** không đưa PDF/OCR/crop/prompt/ground truth của mentor vào repo hay external service. Baseline đề xuất external services = none; mọi thay đổi provider cần phê duyệt mới.
- Chưa có dữ liệu để cam kết latency, throughput, cost, accuracy, availability, multilingual/scan quality hoặc production readiness.

## 5. Handoff và trạng thái review

PRD chung chỉ cần tham chiếu khối này thay vì sao chép data contract/metric formula. Trước khi accepted, AI1 review snapshot/geometry; BE review persistence/API/concurrency; FE review two-sided evidence/highlight; leader xác nhận priority, scope và reviewer. Các quyết định chưa được chốt nằm tại [AI2-TRACEABILITY-AND-INTEGRATION.vi.md](AI2-TRACEABILITY-AND-INTEGRATION.vi.md).
