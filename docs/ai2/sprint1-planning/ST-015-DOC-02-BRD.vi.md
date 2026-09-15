# DOC-02 — BRD Contract Intelligence

**Phiên bản:** v0.3  
**Nguồn chuẩn:** Bản tiếng Việt này; bản tiếng Anh chỉ đồng bộ sau khi leader chốt bản Việt.  
**Owner soạn:** Trần Văn Dũng — AI Engineer / AI2.  
**Trạng thái:** Draft ready — chưa có reviewer, ngày review hoặc sign-off thực tế.  
**Vai trò:** BRD do AI2 sở hữu phần yêu cầu trích xuất, so sánh có ngữ cảnh, evidence và HITL; leader quyết định việc hợp nhất thành BRD chính thức của nhóm.

> DOC-02 chuyển Product Vision thành yêu cầu nghiệp vụ. Nó không thay DOC-01/03/04/05/06 và không là bằng chứng OCR, model run, accuracy hoặc nghiệm thu tích hợp.

## 1. Bối cảnh và mục tiêu

Contract Intelligence hỗ trợ chuyên viên rà soát dossier hợp đồng giảm thời gian tìm và đối chiếu thông tin thủ công. Sản phẩm phải giúp reviewer:

1. Định vị Điều > Khoản > Điểm và bảng chứa thông tin cần kiểm tra.
2. Xem fact với raw value, normalized value khi có thể, context và evidence.
3. So sánh fact chỉ khi chúng cùng đối tượng và điều kiện áp dụng.
4. Kiểm tra evidence hai phía rồi xác nhận, sửa, từ chối hoặc yêu cầu thêm evidence.

Finding chỉ là kết quả kỹ thuật. Hệ thống không kết luận hiệu lực pháp lý, thứ tự ưu tiên tài liệu, điều khoản hiện hành hoặc thay thế quyết định của reviewer.

## 2. Stakeholder và trách nhiệm

| Vai trò | Trách nhiệm | Không tự quyết |
|---|---|---|
| Người tạo dossier / vận hành | Cung cấp dossier và xác nhận membership, role contract/annex. | Suy role từ tên file hoặc upload order. |
| Reviewer | Xem evidence; confirm, correct, reject, request evidence. | Kết luận hiệu lực pháp lý từ finding. |
| Leader / product owner | Chốt scope, priority, reviewer/adjudicator, dossier policy và Gate B targets. | Coi fixture planning là evidence thực nghiệm. |
| AI1 | Cung cấp OCR/layout snapshot và provenance đã thống nhất. | Xác nhận business/legal outcome. |
| AI2 | Định nghĩa fact/context/taxonomy/finding/evaluation requirement. | Sở hữu API, database, auth hoặc legal decision. |
| BE / FE | Hiện thực persistence/API và evidence/HITL theo yêu cầu đã chốt. | Ghi đè machine output hoặc review history. |
| Mentor | Review định hướng/chất lượng tài liệu khi được sắp lịch. | Tự động sign-off nếu không có evidence phản hồi. |

## 3. Phạm vi MVP và ràng buộc

### In scope

- Dossier gồm một hợp đồng chính và `0..n` phụ lục, khi membership và document role được manifest hoặc người có thẩm quyền xác nhận.
- PDF tiếng Việt, scan hoặc text-layer. Chất lượng OCR/layout chỉ được đo tại Gate B.
- Cấu trúc Điều > Khoản > Điểm và bảng để reviewer truy về nguồn.
- So sánh `within_document`, `contract_annex`, `annex_annex` cho fact structured ở mục 5.
- Single dossier là ưu tiên MVP; batch chờ leader xác nhận priority/capacity/owner.

### Out of scope

- Cam kết tiếng Anh/song ngữ, DOCX, email, ảnh rời hoặc định dạng không phải PDF trong MVP.
- Suy contract/annex role, quan hệ sửa đổi hoặc precedence từ tên file, upload order hoặc validity end null.
- Tự động kết luận xung đột pháp lý/hiệu lực/ưu tiên; tự động phê duyệt hoặc từ chối hợp đồng.
- API wire format, database schema, UI implementation, model/provider, SLA, security/retention chi tiết và production topology.
- Claim accuracy, latency, cost, throughput, bbox/citation quality hoặc production readiness khi chưa có Gate B evidence.

### Dữ liệu

PDF, OCR text, crop, prompt hoặc ground truth do mentor cung cấp không được vào repo hoặc dịch vụ ngoài. Fixture planning phải tự soạn và ghi `synthetic`/`example_only`; không được dùng làm bằng chứng run/evaluation thật.

## 4. Thuật ngữ

| Thuật ngữ | Nghĩa |
|---|---|
| Dossier | Nhóm tài liệu được nộp để rà soát, gồm contract và có thể có annex. |
| Fact | Giá trị typed có raw value, normalized value khi có thể, context và evidence. |
| Finding | Kết quả so sánh kỹ thuật giữa hai fact; không là kết luận pháp lý. |
| Citation | Tham chiếu document, trang và vị trí nguồn trong snapshot xác định. |
| Gold | Nhãn độc lập phục vụ evaluation, tách với review HITL sản phẩm. |

## 5. Ma trận yêu cầu nghiệp vụ

| BR-ID | Requirement | Outcome | Acceptance evidence | Trace |
|---|---|---|---|---|
| BR-01 | Dossier có membership/document role xác nhận. | Thiếu manifest thì comparison liên tài liệu bị block. | Leader xác nhận policy/owner. | DOC-03 flow; DOC-04 manifest; DOC-05 intake. |
| BR-02 | MVP nhận PDF tiếng Việt. | Scan/text-layer tiếp nhận; English/bilingual/non-PDF ngoài MVP. | Scope khớp DOC-01 + leader feedback. | DOC-03 intake; DOC-06 population. |
| BR-03 | Reviewer truy được cấu trúc và nguồn. | Fact/finding dẫn được đến điều/khoản/điểm hoặc bảng khi áp dụng. | Citation hai phía resolve document/page/location. | DOC-03 evidence; DOC-04 provenance. |
| BR-04 | Biểu diễn `price`, `quantity`, `date`, `duration`, `party`, `tax_code`, `referenced_contract_number`. | Fact giữ raw value, role, context. | C01–C13 coverage design; run thật ở Gate B. | DOC-03 extraction; DOC-06 fact metric. |
| BR-05 | Không suy đoán dữ kiện. | Normalized/context mơ hồ giữ null + reason; không điền từ gold. | C13 + missing-evidence walkthrough. | DOC-03 validation. |
| BR-06 | Chỉ so sánh facts đủ context. | Role, subject, unit/currency/VAT, scope, validity tương thích; thiếu thì `insufficient_evidence`. | C09–C13. | DOC-03 comparison; DOC-04 context. |
| BR-07 | Một pair có một disposition. | `comparable_match`, `comparable_difference`, `candidate_amendment`, `not_comparable`, `insufficient_evidence`. | Decision table + C01–C15. | DOC-03 findings; DOC-06 classification. |
| BR-08 | Amendment là candidate kỹ thuật. | Cần khác value, subject/scope phù hợp, reference + câu sửa rõ, effective date muộn hơn. | C02 candidate; C03 control. | DOC-03 review; DOC-04 evidence. |
| BR-09 | Finding có evidence hai phía và lý do outcome. | Evidence thiếu/không resolve đi evidence queue; không claim xác minh được. | C02/C13/C15 + audit protocol. | DOC-03 citation; DOC-06 citation/bbox audit. |
| BR-10 | HITL có audit history. | Confirm/correct/reject/request evidence; correction không ghi đè output máy. | Revision-chain walkthrough. | DOC-03 HITL; DOC-05 review action. |
| BR-11 | Re-OCR/rerun giữ history. | Snapshot/run/review cũ truy vết được; run mới dùng input version mới. | Re-OCR walkthrough. | DOC-04 lineage; DOC-05 job/query. |
| BR-12 | Single dossier trước; batch có điều kiện. | Batch không là Sprint 1 commitment nếu chưa có leader decision. | Priority/capacity decision evidence. | DOC-03 priority; DOC-05 jobs. |
| BR-13 | Evaluation report truy vết được số liệu. | Gate B báo `n`, denominator, version, missing/failed/not-run. | DOC-06 + run/audit evidence. | DOC-06. |
| BR-14 | Bảo vệ dữ liệu nguồn. | Không đưa dữ liệu mentor ra repo/external service. | Data-handling checklist. | DOC-03 constraint; DOC-04 security decision. |

## 6. Quy tắc so sánh và taxonomy

| Entity type | Role ví dụ | Context cần cho comparison khi áp dụng |
|---|---|---|
| price | unit_price / total_price | subject, currency, unit, VAT basis, scope, validity |
| quantity | ordered / delivered | subject, unit, role, scope, validity |
| date | signed / effective / delivery | role, đối tượng, scope, validity |
| duration | contract_term / delivery_lead | anchor, unit, scope, validity |
| party | seller / buyer | party role, scope, validity |
| tax_code | party_a / party_b | party role, scope, validity |
| referenced_contract_number | dossier_reference | dossier context và source reference |

- Không tự đổi currency/unit hoặc quy đổi tháng thành 30 ngày nếu chưa có rule được duyệt.
- Khác party name chỉ là textual difference; thiếu MST không suy entity identity/legal outcome.
- Clause và table có evidence parity khi citation truy được nguồn.
- Nhiều fact cùng type chỉ pair khi role/subject/scope/validity đủ rõ; nếu còn mơ hồ, không chọn tùy ý mà trả `insufficient_evidence` hoặc tạo candidate riêng có lý do.

`finding_type` là chiều kiểm tra, `model_disposition` là outcome, `review_state` là trạng thái reviewer; không dùng thay thế nhau.

| Thứ tự | Điều kiện | Outcome / hành động |
|---|---|---|
| 1 | Thiếu evidence để đọc value, pairing hoặc điều kiện áp dụng. | `insufficient_evidence`; hiển thị lý do, request evidence. |
| 2 | Khác role/subject/unit/VAT/scope; hoặc kỳ độc lập không giao nhau và không có amendment evidence. | `not_comparable`; không alert conflict. |
| 3 | Context đủ, normalized values bằng nhau. | `comparable_match`; giữ audit, không ưu tiên alert. |
| 4 | Context đủ, values khác, chưa đủ điều kiện amendment. | `comparable_difference`; reviewer kiểm tra. |
| 5 | Khác values, subject/scope phù hợp, reference + câu sửa rõ, effective date muộn hơn. | `candidate_amendment`; reviewer quyết định business interpretation, không kết luận pháp lý. |

Thời gian không rõ chỉ block khi nó trọng yếu. Thiếu amendment language nhưng context đủ và value khác vẫn là `comparable_difference`.

### Semantic pilot

Semantic polarity là pilot hẹp với subject/action/object/recipient/time/condition/polarity tương thích. Từ khóa phủ định đơn lẻ không đủ. `semantic_polarity_candidate` chỉ là `finding_type`; outcome vẫn theo năm disposition. C04/C14/C15 là controls thiết kế, không là legal conflict.

## 7. Evidence, HITL và lifecycle

Reviewer mở hai nguồn, xem citation/highlight, rồi chọn confirm/correct/reject/request evidence. Request evidence đưa finding về hàng đợi bổ sung; thay membership/document role là trách nhiệm owner được chỉ định, không phải AI2 suy đoán.

- OCR snapshot, machine fact và finding run có version; re-OCR/rerun tạo version mới.
- Review revision append-only; current state suy từ chain hợp lệ.
- Correction không sửa raw OCR, citation, source snapshot hoặc model disposition gốc.
- Gold/evaluation workflow tách với product review.

Schema, offset, bbox frame, concurrency, API và persistence thuộc Data Contract, Architecture và API Spec; BRD yêu cầu reviewer truy được đúng nguồn và không mất history.

## 8. Success criteria và evidence gates

| Lớp | Điều kiện | Evidence / owner |
|---|---|---|
| Gate A — planning | Scope, BR matrix, decision table, workflow, case coverage, traceability nhất quán; open decision có owner/impact. | Leader/reviewer feedback có ngày + link evidence. |
| Product experience | Finding alertable có hai nguồn; missing/not-comparable có lý do; bốn action HITL có history. | Design walkthrough; integration evidence sau này. |
| Gate B — evaluation | OCR, bbox, citation, fact, conflict, time/cost báo với `n`, denominator, snapshot/rule/gold version. | PDF/OCR thật, binding, audit, run log, DOC-06. |

Không đặt accuracy/cost threshold ở v0.3. Leader/mentor chốt metric target, sample và owner trước Gate B. C01–C15 × hai representation chỉ là planning coverage, không là evaluation result.

## 9. Dependency và traceability

| ID | Quyết định / dependency | Owner | Ảnh hưởng khi pending |
|---|---|---|---|
| INT-01 | Dossier manifest, membership, document-role source. | Leader + BE/product | Block cross-document comparison tự động. |
| INT-02 | Snapshot/citation/highlight frame. | AI1 + FE + BE | Provenance integration chưa freeze. |
| INT-03 | Run lineage và schema version. | AI2 + BE | Rerun reproducibility chưa đủ. |
| INT-04 | API, persistence, retry/error. | BE | Không implement endpoint/job contract. |
| INT-05 | Identity, RBAC, retention, security classification. | Leader + BE | Không claim production/security. |
| INT-06 | Reviewer/adjudicator, amendment, semantic policy. | Leader + reviewer | Candidate chưa thành accepted business outcome. |

DOC-01 định hướng problem/users/value/out-of-scope; DOC-02 định nghĩa business rules; DOC-03 capability; DOC-04 lifecycle/components; DOC-05 API; DOC-06 evidence evaluation. Mapping chi tiết: [ST-022-TRACEABILITY-AND-INTEGRATION.vi.md](ST-022-TRACEABILITY-AND-INTEGRATION.vi.md).

## 10. Review và sign-off

| Trạng thái | Điều kiện | Evidence |
|---|---|---|
| Draft ready | Bản nháp + self-review hoàn chỉnh. | Version/link artefact. |
| Pending leader review | Đã gửi hoặc đặt lịch review thật. | Message/lịch, reviewer, ngày. |
| Returned | Có feedback yêu cầu sửa. | Feedback + danh sách xử lý. |
| Pending mentor review | Leader đã phản hồi/đồng ý phạm vi, bản gửi mentor. | Evidence gửi mentor + quyết định leader. |
| Accepted | Reviewer xác nhận bằng chữ, có ngày/evidence và không còn P0 blocker. | Feedback/sign-off durable. |
| Done | Người dùng xác nhận bàn giao/đóng task. | Evidence bàn giao. |

Gate A accepted không chứng minh Gate B đã chạy.

## 11. Artefact liên quan

- [DOC-01 Product Vision](ST-014-DOC-01-PRODUCT-VISION.vi.md)
- [Case catalog C01–C15](ST-016-CASE-CATALOG.vi.md)
- [Data contract](ST-017-DATA-CONTRACT.vi.md)
- [Metric protocol](ST-021-METRIC-PROTOCOL.vi.md)
- [Traceability/integration register](ST-022-TRACEABILITY-AND-INTEGRATION.vi.md)
- [Decision/risk/review register](ST-022-DECISIONS-RISKS-REVIEW.vi.md)
