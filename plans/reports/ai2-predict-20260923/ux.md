# AI2 predict — UX/operator findings

**Persona:** UX/operator  
**Phạm vi:** proposal AI2 hiện tại: safe states, citation, free-form Q&A về hợp đồng–phụ lục, tiếng Việt, thông báo thiếu/mâu thuẫn và evaluation.  
**Phương pháp:** chỉ đọc proposal/docs, code contract/UI hiện có và live-review artifacts; không sửa production.

## Verdict

**CAUTION cho hướng kiến trúc; STOP cho operator-facing acceptance hiện tại.**

Hướng **evidence-first semantic dossier + bounded query** là đúng hướng UX: reviewer có thể truy nguyên về hồ sơ và hệ thống không biến thiếu evidence thành kết luận. Tuy nhiên, proposal chưa chốt một hợp đồng hiển thị đủ rõ giữa job state, extraction/review state, answer state, grounding và citation usability. Artifact live đã cho thấy một câu trả lời có thể mang nhãn `ANSWERED` trong khi `grounded=false` và các review item của citation là `INVALID`/`NEEDS_REVIEW`; đây là rủi ro false reassurance P0 nếu đưa thẳng cho operator.

## Findings đã kiểm chứng

### UX-001 — P0: Các trạng thái chưa có một semantics operator duy nhất

**Bằng chứng:**

- `ai-service/app/contracts/models.py:10-16` có cùng một enum gồm `ANSWERED`, `NEEDS_REVIEW`, `INSUFFICIENT_EVIDENCE`, `BLOCKED`, `NOT_COMPARABLE` và `PASS`.
- Wire processing lại tách job lifecycle với `review_state`, và public processing schema chỉ cho `PASS`, `NEEDS_REVIEW`, `INSUFFICIENT_EVIDENCE`, `BLOCKED`: `docs/contracts/BE-AI2-PROCESSING-CONTRACT.vi.md:75-85`, `docs/contracts/ai2.be.processing.result.v1.schema.json:80-83`.
- Live review ghi `HAPPY-001` là extraction `NEEDS_REVIEW` nhưng answer `ANSWERED`: `ai-service/artifacts/ai2-live-audit-v2/review/review.md:9-20`.

**Tác động:** operator không biết `ANSWERED` nghĩa là “đã trả lời”, “đã grounded”, hay “được phép tin/publish”. `PASS` cũng dễ bị hiểu là answer đã được phê duyệt, dù contract nói review/publish vẫn thuộc Backend.

**Khuyến nghị:** chốt response view với các chiều độc lập: `job_status`, `answer_state`, `evidence_state`, `citation_state`, `next_action`. Chỉ hiển thị nhãn người dùng kiểu “Có câu trả lời — cần kiểm tra nguồn” khi các chiều chưa đồng thuận; không để `ANSWERED` đứng một mình. Cần precedence rule rõ: citation invalid hoặc grounding fail không được tạo trạng thái “đã xác minh”.

### UX-002 — P0: Có thể tạo false reassurance: `ANSWERED` nhưng nguồn không dùng được

**Bằng chứng:**

- `HAPPY-001` trong `ai-service/artifacts/ai2-live-audit-v2/review/cases/HAPPY-001__live.json:1` trả `review_state=ANSWERED`, nhưng `grounded=false`; cùng payload có review item `citation:...:INVALID` với lý do `citation bbox is invalid` và `review_state=NEEDS_REVIEW`.
- `HAPPY-004` cũng có `review_state=ANSWERED`, `grounded=false`; artifact vẫn ghi citation hợp lệ ở mức machine check, trong khi review items của fact/citation cần verify: `ai-service/artifacts/ai2-live-audit-v2/review/cases/HAPPY-004__live.json:1`.
- Resolver thực sự kiểm tra page revision, source hash, quote hash, bbox, span/line/table/cell: `ai-service/app/pipeline/citations.py:57-105`.

**Tác động:** người rà soát có thể tin giá trị vì thấy `ANSWERED`, nhưng không mở được/không xác minh được nguồn. Đặc biệt nguy hiểm với MST, giá, ngày và điều khoản sửa đổi.

**Khuyến nghị:** trong acceptance, bắt buộc invariant `ANSWERED ⇒ grounded=true ∧ mọi claim citation usable`. Nếu không đạt, trả `NEEDS_REVIEW` hoặc `INSUFFICIENT_EVIDENCE` kèm lý do cụ thể; giữ phần answer chỉ như candidate, không dùng visual treatment của success.

### UX-003 — P1: Citation có dữ liệu kỹ thuật phong phú nhưng chưa đủ usable cho operator

**Bằng chứng:**

- Model có `page`, `page_range`, `line_ids`, `breadcrumb`, `structure_path`, `bbox`, `table_id`, `cell_id`, `validation_status`: `ai-service/app/contracts/models.py:210-234`.
- UI hiện tại chỉ render `node_id` và `text_span`, không render page/path/validation hay hành động mở đúng nguồn: `ai-service/app/static/lab.js:87-100`.
- Proposal yêu cầu citation/trace cho mọi answer nhưng chưa định nghĩa presentation contract: `docs/ai2/AI2-15-contract-profiles-structure-relations-and-free-form-qa.vi.md:97-111`.

**Tác động:** citation tồn tại về mặt schema nhưng người dùng vẫn phải tự tìm trong hồ sơ. Với bảng, continuation, body–annex trùng số điều và nhiều span, `node_id` là mã nội bộ chứ không phải điểm định vị có thể dùng.

**Khuyến nghị:** mỗi claim hiển thị citation card gồm tên file/member, trang, breadcrumb/điều khoản, đoạn trích, trạng thái xác minh, version/revision và nút mở đúng vùng; với comparison hiển thị hai phía cạnh nhau. Khi citation stale sau re-OCR, nói rõ “nguồn cũ đã stale; mở revision mới”, không chỉ đổi badge.

### UX-004 — P1: Thiếu dữ liệu/mâu thuẫn chưa tạo đủ đường phục hồi cho reviewer

**Bằng chứng:**

- Proposal đúng khi yêu cầu thiếu source/relation/context phải trả safe state: `docs/ai2/AI2-15-contract-profiles-structure-relations-and-free-form-qa.vi.md:105-111`.
- Case thiếu phụ lục trả `INSUFFICIENT_EVIDENCE` với câu “Phụ lục 7 không có trên outline”, nhưng không có citation nào để đưa operator về nơi hợp đồng nhắc tới phụ lục: `ai-service/artifacts/ai2-live-audit-v2/review/cases/EC-009__live.json:1` (`actual_ask_state=INSUFFICIENT_EVIDENCE`, `n_citations=0`).
- Review UX đã nhận diện yêu cầu mở raw span/citation, giữ unresolved missing-annex khi export và xử lý approval theo dependency: `plans/reports/ai2-operational-scenario-catalog-260923.md:211-219`.

**Tác động:** thông báo “thiếu evidence” đúng về safety nhưng chưa giúp operator biết thiếu cái gì, ảnh hưởng claim nào, cần upload/relink/re-OCR hay chỉ cần người có thẩm quyền review. `NEEDS_REVIEW` và `INSUFFICIENT_EVIDENCE` dễ thành cùng một hộp lỗi.

**Khuyến nghị:** issue phải có `missing_source/member`, claim bị ảnh hưởng, evidence hiện có, lý do, next action và mức độ chặn export. Với missing annex, vẫn cite đoạn tham chiếu trong body; với conflict, hiển thị cả hai phía và giữ “không chọn bản đúng”.

### UX-005 — P1: Câu hỏi nhiều bước về hợp đồng–phụ lục chưa có contract hiển thị cho chuỗi bằng chứng

**Bằng chứng:**

- Proposal yêu cầu câu hỏi như “Phụ lục này thay đổi điều khoản nào?” đi qua `structure/relation/comparison`, không mở sang hồ sơ khác: `docs/ai2/AI2-15-contract-profiles-structure-relations-and-free-form-qa.vi.md:99-107`.
- Scenario catalog yêu cầu câu hỏi “Phụ lục nào đổi giá Điều 5 và áp dụng từ ngày nào?” phải đi qua `structure → relation → comparison → date evidence`; thiếu mắt xích thì `review/insufficient`: `plans/reports/ai2-operational-scenario-catalog-260923.md:151-159`.

**Tác động:** nếu chỉ trả một câu tổng hợp, operator không phân biệt được hệ thống đã chứng minh “phụ lục nào”, “đổi gì”, “áp dụng từ ngày nào” hay mới chỉ tìm thấy candidate. Đây là điểm dễ biến candidate amendment thành kết luận pháp lý.

**Khuyến nghị:** trả kết quả theo claim/chain: `source clause → relation → changed field → effective-date evidence`, đánh dấu mắt xích thiếu ngay tại vị trí đó. `NOT_COMPARABLE` phải giải thích khác ở `scope/unit/currency/validity` và hướng dẫn “không thể so trực tiếp”, không dùng như một lỗi chung.

### UX-006 — P1: Tiếng Việt là requirement chức năng nhưng chưa có UX acceptance riêng

**Bằng chứng:**

- Edge-case đã yêu cầu query English trên document tiếng Việt, giữ citation bắt buộc: `docs/ai2/AI2-04-edge-case-test-matrix.vi.md:52-56`.
- Edge-case OCR mất dấu yêu cầu tách raw/normalized và audit span: `docs/ai2/AI2-04-edge-case-test-matrix.vi.md:59-63`.
- Proposal hiện mô tả route và evidence, nhưng chưa chốt answer language, cách hiển thị raw tiếng Việt có lỗi OCR, hay cách phân biệt normalized value với text gốc: `docs/ai2/AI2-15-contract-profiles-structure-relations-and-free-form-qa.vi.md:65-70`, `:97-111`.

**Tác động:** operator Việt Nam có thể thấy nhãn kỹ thuật/tiếng Anh, mất dấu hoặc bản normalized được trình bày như nguyên văn. Điều này làm giảm khả năng đối chiếu văn bản gốc dù extraction vẫn “đúng” ở mức schema.

**Khuyến nghị:** eval phải tách `raw source text`, `normalized display value`, `answer language`, và `citation quote`; UI phải cho xem raw nguyên bản cạnh diễn giải tiếng Việt. Mixed VI/EN, dấu câu/số tiền/đơn vị và thuật ngữ `Phụ lục`/`Điều` cần có task riêng.

### UX-007 — P1: Evaluation hiện đo nhiều correctness nhưng chưa đo trải nghiệm xác minh và phục hồi

**Bằng chứng:**

- Proposal đã có các metric tốt như citation correctness, Q&A faithfulness, abstention quality: `plans/reports/ai2-all-parts-research-260923.md:423-438`.
- Product vision đã nêu `Time-to-correct-source`, `Task success rate`, `Reviewer correction rate` và `Query trace completeness`: `docs/DOC-01-product-vision.md:439-477`.
- Nhưng live review vẫn để `Manual verdict: PENDING` và `Reviewer notes:` trống cho case answer/citation: `ai-service/artifacts/ai2-live-audit-v2/review/review.md:9-21`; current report chủ yếu ghi state, số citation và machine flags.

**Tác động:** hệ thống có thể tăng citation resolve rate nhưng vẫn khiến reviewer mất thời gian, không hiểu trạng thái hoặc không biết cách sửa. `ANSWERED` sai cũng có thể làm task “pass” nếu chỉ đo HTTP/state match.

**Khuyến nghị:** bổ sung task-based UX eval trên reviewed golden set: status comprehension, citation navigation success, time-to-correct-source, missing-data recovery success, conflict interpretation accuracy, partial-answer usefulness, Vietnamese comprehension và false-reassurance rate. Tách rõ candidate corpus, golden, failed/not-run như proposal đã yêu cầu: `docs/ai2/AI2-15-contract-profiles-structure-relations-and-free-form-qa.vi.md:113-131`.

## State contract đề xuất cho operator

| Machine state | Cách nói với operator | Điều kiện UX tối thiểu | Hành động tiếp theo |
|---|---|---|---|
| `ANSWERED` | Đã trả lời, nguồn đã kiểm chứng | Claim-level citation usable; `grounded=true`; không còn issue ảnh hưởng claim | Có thể mở nguồn và đối chiếu |
| `NEEDS_REVIEW` | Có candidate/partial answer nhưng cần người kiểm tra | Nêu rõ claim/field/relation nào chưa chắc và vì sao | Mở evidence, xác nhận/sửa/từ chối |
| `INSUFFICIENT_EVIDENCE` | Chưa đủ hồ sơ để trả lời chắc chắn | Nêu source/member/context còn thiếu; không để người dùng đoán “không có” | Upload/relink/re-OCR hoặc thu hẹp câu hỏi |
| `BLOCKED` | Không thể xử lý trong policy/authorization/runtime hiện tại | Nêu boundary an toàn và có retryable hay không; không lộ dữ liệu ngoài ACL | Sửa quyền/policy/input hoặc retry có kiểm soát |
| `NOT_COMPARABLE` | Hai giá trị không thể so trực tiếp | Chỉ ra khác `scope`, `unit`, `currency` hoặc `validity`; giữ cả hai citation | Xác nhận mapping/conversion authority hoặc review |

`PASS` nên là trạng thái chất lượng processing/publish gate, không phải synonym của câu trả lời đã được operator xác minh. `ANSWERED` và `NOT_COMPARABLE` cần nằm trong query/result contract riêng hoặc được ánh xạ rõ ràng sang wire processing contract.

## Kết luận handoff

1. Không nên chấp nhận operator-facing release khi còn khả năng `ANSWERED` đi cùng `grounded=false` hoặc citation invalid.
2. Trước khi mở rộng profile/Q&A, cần chốt canonical state contract, citation presentation contract và missing/conflict recovery contract.
3. Khi các contract trên được chốt, hướng evidence-first vẫn phù hợp để tiếp tục; UX gate phải đo được khả năng reviewer tìm đúng nguồn và xử lý safe state, không chỉ đo schema/state match.
