# DOC-02 — Business Requirements Document

## Contract Intelligence

**Phiên bản:** v1.0 | **Ngày soạn:** 18/09/2026 | **Trạng thái:** Draft — chờ Product Owner/mentor review | **Owner:** Product Owner | **Nguồn yêu cầu duy nhất:**Product Vision v0.4 | **Ngôn ngữ:** Tiếng Việt
Tài liệu này được viết mới độc lập từ Product Vision v0.4. Product Vision là nguồn xác định problem, user, value, scope, policy và success direction. BRD chuyển các nội dung đó thành business requirements, stakeholder requirements, solution requirements ở mức hành vi, business rules, transition requirements và acceptance criteria. BRD không mô tả API wire format, database schema, UI implementation, model provider hoặc deployment topology.

## 1. Mục đích và nguyên tắc

### 1.1 Mục đích

BRD này xác định hệ thống Contract Intelligence phải cung cấp giá trị nghiệp vụ nào cho người rà soát hợp đồng khi một dossier gồm hợp đồng chính và nhiều phụ lục có thông tin phân tán giữa nhiều file, trang, điều khoản và bảng biểu.
Tài liệu dùng để:

- thống nhất phạm vi và ưu tiên của MVP;
- chuyển nhu cầu người dùng thành requirement có thể kiểm tra;
- làm cơ sở cho thiết kế chức năng, triển khai và nghiệm thu ở tài liệu tiếp theo;
- kiểm soát các ranh giới an toàn: không suy đoán evidence, không kết luận pháp lý và không làm lộ dữ liệu tenant;
- duy trì traceability từ Product Vision đến requirement và acceptance scenario.

### 1.2 Nguyên tắc requirement

Mỗi requirement trong tài liệu phải:

- có một ID duy nhất;
- thể hiện một nhu cầu hoặc điều kiện chính;
- có actor, hành vi/kết quả và điều kiện áp dụng khi cần;
- có priority, owner, nguồn Product Vision và acceptance criteria;
- có thể kiểm tra bằng scenario, audit hoặc metric;
- không chứa quyết định implementation nếu quyết định đó thuộc Architecture/API/Data Contract;
- không tạo cam kết về accuracy, latency, cost hoặc scale khi Product Vision chưa có baseline.

### 1.3 Phân loại requirement



| **LoạiÝ nghĩa trong BRD** |                                                                                                                   |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| BUS                       | Business requirement: mục tiêu, outcome và giá trị cần đạt.                                                       |
| STK                       | Stakeholder requirement: nhu cầu/quyền/trách nhiệm của từng nhóm người dùng.                                      |
| FUN                       | Functional requirement: capability và hành vi hệ thống phải cung cấp.                                             |
| NFR                       | Non-functional/policy requirement: điều kiện về bảo mật, truy vết, tính nhất quán, chi phí và vận hành.           |
| RUL                       | Business rule: quy tắc không được suy diễn hoặc thay đổi tùy ý.                                                   |
| TRN                       | Transition requirement: điều kiện đưa người dùng/dossier từ trạng thái hiện tại sang trạng thái sử dụng hệ thống. |

Priority sử dụng MoSCoW:

- **Must**: bắt buộc cho baseline MVP;
- **Should**: thuộc hướng sản phẩm nhưng chưa phải cam kết của baseline MVP;
- **Could**: có giá trị nhưng chưa phải cam kết;
- **Won't**: không triển khai trong baseline này; không đồng nghĩa loại bỏ vĩnh viễn khỏi roadmap.

## 2. Tóm tắt nghiệp vụ

### 2.1 Vision

Biến mỗi dossier hợp đồng thành một bản đồ thông tin có thể tìm kiếm, kiểm chứng và quản trị an toàn, giúp reviewer đi từ câu hỏi hoặc giá trị cần tìm đến đúng file, trang, điều khoản và phụ lục liên quan mà không phải đọc thủ công toàn bộ hồ sơ.

### 2.2 Người dùng và bối cảnh

Người dùng chính là chuyên viên rà soát hợp đồng hoặc legal operations reviewer. Người dùng phụ gồm quản lý/pháp chế nội bộ, nhân sự vận hành hợp đồng, mua hàng và bán hàng.
Mỗi doanh nghiệp là một tenant độc lập. Người dùng chỉ nhìn thấy dossier được cấp quyền trong tenant của mình. Mỗi tenant có thể có thành viên, nhóm, alias nghiệp vụ, retention và chính sách chia sẻ riêng theo quyền được cấp.

### 2.3 Painpoint

Khi hợp đồng chính kết hợp với nhiều phụ lục, người dùng phải mở nhiều file, tìm nhiều trang, tự nhớ quan hệ giữa tài liệu và quay lại bản gốc để kiểm chứng. Hệ thống cần giải quyết khó khăn định vị thông tin và evidence, không chỉ thực hiện OCR.

### 2.4 Job-to-be-done

Khi nhận một dossier hợp đồng, reviewer muốn nhập giá trị hoặc câu hỏi cần tìm và được dẫn tới đúng điều khoản trên đúng tài liệu, thấy phụ lục liên quan và evidence trên trang gốc, để hoàn thành rà soát nhanh hơn nhưng vẫn tự chịu trách nhiệm cho kết luận nghiệp vụ.

### 2.5 Business outcomes

Sản phẩm phải hướng đến các outcome sau:

1. Giảm thời gian định vị thông tin trong một dossier.
2. Giảm nguy cơ bỏ sót điều khoản bị phụ lục thay đổi hoặc điều chỉnh.
3. Biến kết quả AI thành evidence có thể kiểm chứng.
4. Có số liệu về chất lượng, chi phí, throughput và tỷ lệ cần review.
5. Cho phép nhiều tenant dùng chung nền tảng mà không làm lộ dữ liệu hoặc cấu hình.
6. Tạo niềm tin bằng quyền tối thiểu, lịch sử truy vết và khả năng khôi phục/xóa có kiểm soát.

## 3. Stakeholder, actor và trách nhiệm



| **ActorMục tiêu/quyền chínhTrách nhiệmKhông được tự động thực hiện** |                                                                                             |                                                               |                                                                                                  |
| -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| Tenant Owner/Admin                                                   | Quản lý tenant, thành viên, policy, retention, legal hold và dossier ACL.                   | Duy trì access policy và lifecycle policy.                    | Không mặc nhiên đọc nội dung dossier chỉ vì có quyền quản trị.                                   |
| Uploader/Operator                                                    | Tạo dossier, upload file, xác nhận manifest và chia sẻ trong tenant.                        | Cung cấp hoặc xác nhận membership, document role và relation. | Không suy quan hệ từ filename hoặc upload order.                                                 |
| Reviewer                                                             | Xem dossier được cấp, xem evidence, xác nhận kết quả, báo lỗi citation và gắn NEEDS_REVIEW. | Kiểm tra nguồn trước khi sử dụng finding cho nghiệp vụ.       | Không được coi candidate là kết luận pháp lý; không chỉnh sửa trực tiếp machine value trong MVP. |
| Viewer                                                               | Xem kết quả và nguồn được cấp.                                                              | Sử dụng dữ liệu đúng phạm vi quyền.                           | Không xác nhận finding hoặc thay đổi policy.                                                     |
| Auditor                                                              | Xem audit log theo quyền.                                                                   | Kiểm tra lịch sử truy cập/thay đổi.                           | Không mặc định xem raw contract content.                                                         |
| Platform Support                                                     | Hỗ trợ vận hành khi được phê duyệt.                                                         | Chỉ xử lý qua break-glass có ticket, phê duyệt và thời hạn.   | Không có quyền đọc content mặc định.                                                             |
| OCR/IDP service                                                      | Phân tích scan/text-layer, layout và cấu trúc.                                              | Tạo snapshot có provenance.                                   | Không xác nhận legal/business outcome.                                                           |
| Index/search service                                                 | Tạo index version và trả kết quả theo ACL.                                                  | Giữ version, trạng thái và fallback an toàn.                  | Không truy cập chéo tenant hoặc bỏ qua quota.                                                    |
| Audit/lifecycle service                                              | Ghi event, soft-delete, restore và purge.                                                   | Giữ lifecycle/audit policy nhất quán.                         | Không xóa audit metadata theo cách làm mất khả năng truy vết.                                    |

## 4. Phạm vi và ranh giới

### 4.1 Capability baseline

| **Capability**           | **Phạm vi BRD v1.0**                                                                                   | **Priority** |
| ------------------------ | ------------------------------------------------------------------------------------------------------ | ------------ |
| Dossier contract + annex | Một hợp đồng chính và 0..n phụ lục trong cùng dossier.                                                 | Must         |
| Input                    | PDF scan hoặc PDF có text layer; bộ mẫu có tiếng Việt, tiếng Anh và song ngữ Việt–Anh.                 | Must         |
| Structure                | StructuralNode, clause/paragraph/section, table/row/cell, citation/bbox và cấu trúc không đánh số.     | Must         |
| No-query navigation      | Sau upload, hiển thị cây hồ sơ, cây cấu trúc và nguồn liên quan dù chưa có câu hỏi.                    | Must         |
| Hybrid search            | Exact/keyword, structured retrieval và semantic retrieval trong phạm vi dossier.                       | Must         |
| Bounded dossier Q&A     | Câu hỏi tự do về contract + annex trong dossier, có citation và safe state.                              | Must         |
| Evidence navigation      | Mở đúng file, trang, node/table và vùng highlight trên bản gốc.                                        | Must         |
| Candidate finding        | Hiển thị candidate difference/structured/semantic để reviewer kiểm tra, không kết luận pháp lý.        | Must         |
| Reviewer                 | Kiểm tra, xác nhận, báo lỗi citation hoặc gắn NEEDS_REVIEW.                                            | Must         |
| Tenant policy            | Logical isolation, private-by-default, same-tenant sharing và dossier ACL.                             | Must         |
| Tenant profile           | Version hóa document type, alias, taxonomy và canonical fields cơ bản.                                 | Must         |
| Index                    | Async IndexVersion, publish atomic, fallback index cũ và retry/rollback.                               | Must         |
| Query governance         | QueryTrace, cache, usage tracking, quota, rate limit và cost tracking.                                 | Must         |
| Batch run                | Có job state và khả năng batch theo policy/capacity; luồng acceptance đầu tiên ưu tiên single dossier. | Must         |
| Archive                  | Có thể archive/restore về active theo policy và audit, tách với soft-delete/purge.                     | Must         |
| Lifecycle                | Soft-delete, restore mặc định 30 ngày, legal hold, purge và audit.                                     | Must         |

### 4.2 Giai đoạn sau hoặc tài liệu riêng

Các capability sau không phải trải nghiệm lõi của MVP:

- chỉnh sửa trực tiếp giá trị trích xuất;
- từ chối finding như một workflow riêng;
- request thêm evidence như một workflow riêng;
- feedback loop cải thiện rule, profile hoặc model;
- phát hiện, phân loại và adjudicate conflict nâng cao;
- bbox editing ở Sprint 3;
- template builder, fine-tuning hoặc custom model riêng từng tenant.

Trong MVP, reviewer chỉ kiểm tra/xác nhận kết quả, báo lỗi citation hoặc gắn NEEDS_REVIEW. Candidate difference/conflict không được xem là kết luận pháp lý.

### 4.3 Ngoài phạm vi

- Legal advice hoặc tự xác định hiệu lực/precedence pháp lý.
- Xác minh chữ ký, con dấu hoặc chữ viết tay ngoài khả năng OCR.
- Tự động phê duyệt/từ chối hợp đồng.
- Redline hoặc tạo lại nội dung PDF.
- DOCX, email, ảnh rời hoặc định dạng ngoài PDF trong MVP.
- External guest, chia sẻ chéo tenant, SSO/SCIM, dedicated storage, customer-managed key, private cloud, on-prem và data residency theo quốc gia.
- Cam kết accuracy, SLA, latency, cost hoặc scale trước khi có baseline thực nghiệm.

## 5. Luồng nghiệp vụ mục tiêu

### 5.1 Luồng upload và chuẩn bị dossier

Tạo tenant
→ mời thành viên
→ upload dossier
→ xác nhận membership/document role/relation
→ phát hiện loại input
→ OCR/parse/layout/structure
→ tạo snapshot và IndexVersion
→ publish index khi thành công
→ hiển thị cây hồ sơ và nguồn liên quan

Nguyên tắc:

- Dossier không được coi là hoàn chỉnh nếu relation hoặc role chỉ được suy từ filename/upload order.
- Khi không đủ evidence để phân loại, hệ thống phải trả UNKNOWN/NEEDS_REVIEW.
- Upload không cần query để tạo cây hồ sơ, cây cấu trúc, bảng/row/cell, citation và cảnh báo.
- Xử lý bất đồng bộ phải hiển thị trạng thái rõ ràng.

### 5.2 Luồng search và navigation

Query exact/keyword
→ structured retrieval
→ semantic retrieval
→ model reasoning khi retrieval chưa đủ
→ trả result/citation/context/status
→ mở đúng nguồn và nguồn liên quan

Query được giới hạn trong dossier và phải qua tenant/dossier ACL trước khi trả kết quả. Query lặp lại có thể dùng cache theo tenant, dossier và index version.

### 5.3 Luồng reviewer

Reviewer mở result
→ xem citation/highlight/bbox
→ kiểm tra nguồn gốc
→ xác nhận kết quả
hoặc → báo lỗi citation / gắn NEEDS_REVIEW
→ ghi audit và QueryTrace

MVP không triển khai direct edit, reject finding hoặc request-evidence workflow. Machine output, raw OCR, source snapshot và citation gốc không bị ghi đè.

### 5.4 Luồng update và index

Upload/update
→ tạo IndexVersion mới
→ PROCESSING
→ publish atomic nếu thành công
→ giữ index cũ nếu thất bại
→ retry hoặc rollback theo policy

Kết quả phải pin document snapshot, tenant profile, policy và index/model version liên quan.

### 5.5 Luồng xóa và khôi phục

ACTIVE ⇄ ARCHIVED (tùy policy)
ACTIVE/ARCHIVED
→ SOFT_DELETED
→ PURGE_PENDING
→ PURGED

- ARCHIVED: dossier không nằm trong active search nhưng source/history vẫn được giữ theo policy; owner có thể đưa lại ACTIVE nếu có quyền.
- SOFT_DELETED: biến khỏi UI/search, thu hồi quyền và signed URL, dừng job đang chạy.
- Trong 30 ngày mặc định, người tạo dossier hoặc Tenant Admin có quyền có thể restore.
- Restore giữ PDF, OCR, structure, citation và review history; không tự chạy lại OCR.
- LegalHold chặn purge.
- Sau retention, purge source, render, OCR, extraction, embedding, index, cache và bản sao vận hành theo policy.

## 6. Requirement catalogue

Các requirement trong các bảng dưới đây dùng metadata registry sau để tránh lặp lại cùng một giá trị ở từng dòng. Mỗi ID thuộc đúng một range; metadata của range được kế thừa cho từng requirement, còn requirement-specific acceptance được ghi tại bảng catalogue và coverage matrix ở §10.

| **Requirement range** | **Actor/beneficiary**                                                              | **Rationale**                                                             | **Accountable owner** | **Status** | **Dependency/risk**                           |
| --------------------- | ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------- | --------------------- | ---------- | --------------------------------------------- |
| BR-BUS-001..005       | Reviewer, tenant và Product Owner                                                  | Định vị đúng nguồn, kiểm chứng được và mở rộng an toàn.                   | Product Owner         | Draft      | Ground truth, tenant policy, baseline metrics |
| BR-STK-001..005       | Reviewer, Uploader/Operator, Tenant Owner/Admin, Viewer, Auditor, Platform Support | Mỗi role chỉ thực hiện đúng quyền và trách nhiệm.                         | Product Owner         | Draft      | ACL, approval, audit                          |
| BR-FUN-001..017       | Uploader/Operator, Reviewer, Viewer                                                | Tạo dossier có cấu trúc, search và evidence có thể kiểm chứng.            | Product Owner         | Draft      | Input quality, relation evidence, citation    |
| BR-FUN-018..019       | Reviewer, Product Owner                                                            | Giữ direct edit/reject/request-evidence/feedback ngoài MVP.               | Product Owner         | Deferred   | Future workflow và verified feedback          |
| BR-FUN-020..034       | Tenant Owner/Admin, Reviewer, Viewer, Auditor                                      | Thích ứng tenant, index/query governance và lifecycle/share an toàn.      | Product Owner         | Draft      | Profile, ACL, index, retention, policy        |
| BR-FUN-035            | Reviewer, Product Owner                                                            | Feedback chỉ trở thành correction/rule/profile/evaluation sau khi verify. | Product Owner         | Deferred   | Future feedback governance                    |
| BR-NFR-001..012       | Tất cả actor trong tenant                                                          | Bảo vệ dữ liệu, truy vết và đo lường có kiểm soát.                        | Product Owner         | Draft      | Security policy, retention, baseline          |
| BR-TRN-001..004       | Tenant Owner/Admin, Uploader/Operator, Reviewer                                    | Đưa tenant và dossier từ upload đến trạng thái sử dụng/khôi phục.         | Product Owner         | Draft      | Onboarding, processing status, lifecycle      |
| BR-RUL-001..011       | Hệ thống, Reviewer, Product Owner                                                  | Ngăn suy đoán và thống nhất trạng thái/evidence.                          | Product Owner         | Draft      | Evidence, status policy, legal boundary       |

Acceptance evidence, dependency và risk của từng nhóm được liên kết ở §8, §9, §10 và §11. Accountable owner trong BRD chịu trách nhiệm chốt nghiệp vụ; implementation owner được phân công ở tài liệu delivery sau.

### 6.1 Business requirements

| **ID**     | **Requirement**                                                                                   | **Priority** | **Product Vision source** | **Acceptance**                                                                        |
| ---------- | ------------------------------------------------------------------------------------------------- | ------------ | ------------------------- | ------------------------------------------------------------------------------------- |
| BR-BUS-001 | Sản phẩm phải giảm thời gian định vị thông tin trong dossier contract/annex.                      | Must         | §1.1, §1.5, §2.1          | Có task tìm kiếm gắn expected source và đo được time-to-correct-source.               |
| BR-BUS-002 | Sản phẩm phải giúp reviewer tìm đúng file, trang, điều khoản, bảng và phụ lục liên quan.          | Must         | §1.3, §3.1                | Kết quả mở được citation/bbox và nguồn liên quan.                                     |
| BR-BUS-003 | Sản phẩm phải biến kết quả AI thành evidence có thể kiểm chứng.                                   | Must         | §1.5, §3.1, §3.2          | Mỗi result/finding được truy về snapshot nguồn hoặc chuyển trạng thái thiếu evidence. |
| BR-BUS-004 | Sản phẩm phải hỗ trợ nhiều tenant mà không làm lộ dữ liệu, cấu hình hoặc kết quả giữa các tenant. | Must         | §1.2, §1.5, §3.2          | Bộ kiểm thử truy cập chéo tenant không trả content, metadata hoặc sự tồn tại dossier. |
| BR-BUS-005 | Sản phẩm phải tạo cơ sở đo quality, cost, throughput và reviewer escalation trước khi mở rộng.    | Must         | §1.5, §8                  | Báo cáo có metric definition, sample, denominator và giới hạn diễn giải.              |

### 6.2 Stakeholder requirements

| **ID**     | **Requirement**                                                                      | **Priority** | **Product Vision source** | **Acceptance**                                                                                       |
| ---------- | ------------------------------------------------------------------------------------ | ------------ | ------------------------- | ---------------------------------------------------------------------------------------------------- |
| BR-STK-001 | Reviewer phải xem được nguồn, kiểm tra và xác nhận result hoặc gắn NEEDS_REVIEW.     | Must         | §1.3, §4.3, §6.2          | Reviewer hoàn thành được scenario xác nhận và scenario citation lỗi; không có direct edit trong MVP. |
| BR-STK-002 | Uploader/Operator phải xác nhận membership, document role và relation của dossier.   | Must         | §4.1, §6.1                | Dossier thiếu xác nhận không tạo cross-document relation tự động.                                    |
| BR-STK-003 | Tenant Owner/Admin phải quản lý thành viên, ACL, retention và legal hold.            | Must         | §1.2, §6.2, §7.2          | Policy thay đổi tạo audit event và có hiệu lực theo scope tenant.                                    |
| BR-STK-004 | Viewer chỉ được xem result/source được cấp; Auditor chỉ được xem audit theo quyền.   | Must         | §6.2                      | Viewer/Auditor không thể xác nhận finding hoặc đọc content ngoài ACL.                                |
| BR-STK-005 | Platform Support chỉ được truy cập qua break-glass có phê duyệt, ticket và thời hạn. | Must         | §6.2, §7.3                | Mọi break-glass event có actor, reason, approval và thời gian.                                       |

### 6.3 Functional requirements — dossier và structure

| **ID**     | **Requirement**                                                                                                                                                            | **Priority** | **Product Vision source** | **Acceptance**                                                                                        |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ | ------------------------- | ----------------------------------------------------------------------------------------------------- |
| BR-FUN-001 | Hệ thống phải hỗ trợ dossier gồm một contract và 0..n annex.                                                                                                               | Must         | §1.4, §4.1                | Dossier hiển thị contract/annex membership và trạng thái xử lý.                                       |
| BR-FUN-002 | Hệ thống phải dùng manifest hoặc evidence do người có thẩm quyền xác nhận cho membership, role và relation.                                                                | Must         | §1.4, §5.2, §6.1          | Filename và upload order không đủ để tạo relation.                                                    |
| BR-FUN-003 | Sau upload, hệ thống phải hiển thị cây hồ sơ và cây cấu trúc dù người dùng chưa đặt query.                                                                                 | Must         | §1.3, §4.1, §6.1          | Upload không query vẫn tạo dossier tree, structure tree, table/row/cell và cảnh báo.                  |
| BR-FUN-004 | Hệ thống phải hỗ trợ PDF scan và PDF text-layer, đồng thời xác định trạng thái input.                                                                                      | Must         | §4.1                      | Dossier hiển thị loại input và trạng thái xử lý; lỗi input không bị coi là kết quả rỗng.              |
| BR-FUN-005 | Hệ thống phải biểu diễn cấu trúc bằng StructuralNode, giữ label gốc, normalized type khi evidence đủ, parent/child, order và citation/bbox.                                | Must         | §4.1, §5.3                | Hợp đồng không đánh số vẫn có node; khi evidence không đủ, node giữ label gốc và chuyển NEEDS_REVIEW. |
| BR-FUN-006 | Hệ thống phải biểu diễn heading, article, section, clause, paragraph, list item, table, row, cell, annex hoặc UNNUMBERED_BLOCK khi cấu trúc nguồn thể hiện loại tương ứng. | Must         | §4.1, §5.3                | Bộ scenario có numbered và unnumbered structure; loại không nhận diện được không bị gán tùy ý.        |
| BR-FUN-007 | Template không nhận diện được phải trả UNKNOWN/NEEDS_REVIEW, không tự suy role hoặc structure.                                                                             | Must         | §4.1, §5.2                | Không đủ bằng chứng không tạo canonical mapping giả.                                                  |
| BR-FUN-008 | Hệ thống phải hiển thị các phụ lục, clause hoặc source liên quan cùng với result.                                                                                          | Must         | §1.3, §3.1, §6.1          | Reviewer mở được source chính và danh sách relation cần kiểm tra.                                     |

### 6.4 Functional requirements — search và result

| **ID**     | **Requirement**                                                                                                                                                                                    | **Priority** | **Product Vision source** | **Acceptance**                                                                                                         |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ | ------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| BR-FUN-009 | Hệ thống phải hỗ trợ exact/keyword search trong phạm vi dossier.                                                                                                                                   | Must         | §1.4, §4.1                | Query exact value trả đúng source nếu source có trong dossier và user có quyền.                                        |
| BR-FUN-010 | Hệ thống phải hỗ trợ structured retrieval cho field, structure và context được lập chỉ mục.                                                                                                        | Must         | §1.4, §3.2, §4.1          | Structured query trả result có context và citation.                                                                    |
| BR-FUN-011 | Hệ thống phải hỗ trợ semantic retrieval cho câu hỏi diễn đạt khác nguyên văn.                                                                                                                      | Must         | §1.4, §4.1                | Semantic query trả result có source hoặc INSUFFICIENT_EVIDENCE.                                                        |
| BR-FUN-012 | Hệ thống phải ưu tiên exact/structured retrieval trước semantic/model reasoning.                                                                                                                   | Must         | §3.2, §7.5, §9.1          | Query trace thể hiện retrieval mode và bước xử lý đã dùng.                                                             |
| BR-FUN-013 | Hệ thống phải trả result kèm context, document, page, node/table, citation, bbox và status.                                                                                                        | Must         | §1.3, §3.1, §4.1, §7.5    | Reviewer mở được nguồn đúng; citation không resolve được chuyển NEEDS_REVIEW.                                          |
| BR-FUN-014 | Khi không đủ evidence để trả lời, result phải có status INSUFFICIENT_EVIDENCE; khi citation/classification cần reviewer kiểm tra, review state phải là NEEDS_REVIEW; hệ thống không được suy đoán. | Must         | §4.1, §6.3, §7.5          | Không có value/source trong snapshot thì không được tạo câu trả lời khẳng định; status và review state được ghi riêng. |
| BR-FUN-015 | Hệ thống phải hiển thị candidate structured/semantic difference trong sample/gold đã được Product Owner xác nhận nhưng không kết luận legal conflict.                                              | Must         | §4.2, §4.3                | Candidate có evidence/reason; không gắn nhãn hiệu lực hoặc precedence pháp lý.                                         |

### 6.5 Functional requirements — reviewer và feedback boundary

| **ID**     | **Requirement**                                                                                                  | **Priority** | **Product Vision source** | **Acceptance**                                                                      |
| ---------- | ---------------------------------------------------------------------------------------------------------------- | ------------ | ------------------------- | ----------------------------------------------------------------------------------- |
| BR-FUN-016 | Reviewer phải có action xác nhận result sau khi kiểm tra citation/bbox.                                          | Must         | §1.3, §4.3, §6.2          | Action có actor, timestamp, dossier, query và version liên quan.                    |
| BR-FUN-017 | Reviewer phải có action báo lỗi citation hoặc gắn NEEDS_REVIEW khi evidence sai, thiếu hoặc không resolve.       | Must         | §1.3, §4.1, §6.3          | Trạng thái và lý do được ghi vào audit/QueryTrace; machine output không bị ghi đè.  |
| BR-FUN-018 | MVP không được cung cấp direct edit, reject finding hoặc request-evidence workflow riêng.                        | Won't        | §4.3, §6.3                | UI/flow MVP không tạo các action này.                                               |
| BR-FUN-019 | Feedback cải thiện rule/profile/model phải là workflow giai đoạn sau và không auto-retrain từ một report đơn lẻ. | Won't        | §3.2, §4.3, §6.3          | MVP chỉ ghi nhận citation error/NEEDS_REVIEW; không cập nhật model/profile tự động. |

### 6.6 Functional requirements — tenant adaptation và indexing

| **ID**     | **Requirement**                                                                                                         | **Priority** | **Product Vision source** | **Acceptance**                                                                                      |
| ---------- | ----------------------------------------------------------------------------------------------------------------------- | ------------ | ------------------------- | --------------------------------------------------------------------------------------------------- |
| BR-FUN-020 | Mỗi tenant phải có TenantProfile phiên bản hóa cho document type, alias, taxonomy, canonical field và policy liên quan. | Must         | §5.1                      | Result và processing run pin tenant_profile_version.                                                |
| BR-FUN-021 | Khi tenant profile thay đổi, run mới phải giữ lại snapshot, citation, machine output và review history cũ.              | Must         | §5.1                      | Kết quả cũ tái hiện được theo profile version cũ.                                                   |
| BR-FUN-022 | Upload/update phải tạo IndexVersion mới bất đồng bộ.                                                                    | Must         | §1.4, §4.1, §7.5          | Dossier có trạng thái processing và index version mới.                                              |
| BR-FUN-023 | Index mới chỉ active sau khi xử lý thành công; index cũ tiếp tục phục vụ khi index mới processing/failed.               | Must         | §1.4, §3.2, §7.5          | Failure test không làm mất index active; retry/rollback được ghi nhận.                              |
| BR-FUN-024 | Hệ thống phải hỗ trợ single run và batch run với job state rõ ràng.                                                     | Must         | §4.1                      | Batch job hiển thị trạng thái thành công/thất bại/đang xử lý; single dossier không phụ thuộc batch. |

### 6.7 Functional requirements — query governance, lifecycle và sharing

| **ID**     | **Requirement**                                                                                                                                                | **Priority** | **Product Vision source** | **Acceptance**                                                                                                   |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ | ------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| BR-FUN-025 | Hệ thống phải lưu QueryTrace gồm query, result/answer, citation IDs, actor, dossier, timestamp, status và document/index/profile/model versions.               | Must         | §7.4, §7.5                | QueryTrace tái hiện được nguồn và version trong phạm vi ACL/retention.                                           |
| BR-FUN-026 | Hệ thống phải hỗ trợ cache query lặp lại theo tenant, dossier và index version.                                                                                | Must         | §7.5, §8.1                | Cache không dùng chéo tenant hoặc chéo index version.                                                            |
| BR-FUN-027 | Hệ thống phải áp dụng quota/rate limit theo user, tenant, query mode và time window.                                                                           | Must         | §1.4, §7.5, §8.1          | Vượt policy trả RATE_LIMITED, không retry vô hạn.                                                                |
| BR-FUN-028 | Hệ thống phải hỗ trợ lifecycle ACTIVE ⇄ ARCHIVED và ACTIVE/ARCHIVED → SOFT_DELETED → PURGE_PENDING → PURGED.                                                   | Must         | §4.1, §6.1, §7.2          | Mỗi chuyển trạng thái có policy và audit event.                                                                  |
| BR-FUN-029 | Dossier soft-delete phải biến khỏi UI/search, thu hồi quyền/signed URL và dừng job đang chạy.                                                                  | Must         | §7.2                      | Search và download không còn trả nội dung sau soft-delete.                                                       |
| BR-FUN-030 | Dossier phải restore được trong thời gian mặc định 30 ngày bởi người có quyền.                                                                                 | Must         | §1.4, §7.2, §9.1          | Restore khôi phục PDF/OCR/structure/citation/history và không tự chạy lại OCR.                                   |
| BR-FUN-031 | LegalHold phải chặn purge cho đến khi được gỡ.                                                                                                                 | Must         | §7.2, §9.3                | Purge bị từ chối và trạng thái hold hiển thị rõ.                                                                 |
| BR-FUN-032 | Purge phải bao phủ PDF, render, OCR, extraction, embedding, index, cache và bản sao vận hành theo retention policy.                                            | Must         | §7.2, §9.2                | Lifecycle drill xác nhận không còn content qua product sau PURGED.                                               |
| BR-FUN-033 | Hệ thống phải hỗ trợ archive dossier theo policy trước khi xóa hoặc purge.                                                                                     | Must         | §6.1                      | Dossier archived không xuất hiện trong active search nhưng vẫn giữ được theo policy và audit.                    |
| BR-FUN-034 | Người có quyền phải xem, cấp, thu hồi và kiểm tra sharing/ACL của dossier theo cùng tenant.                                                                    | Must         | §1.3, §3.2, §6.2          | Thay đổi quyền có hiệu lực với search/download/share và tạo audit event; user không có quyền không thấy dossier. |
| BR-FUN-035 | Feedback cải thiện sau MVP phải đi qua REPORTED → TRIAGED → VERIFIED → APPLIED/REJECTED và liên kết query, dossier, document/index version, citation và actor. | Won't        | §6.3                      | Chỉ feedback đã VERIFIED mới được đưa vào rule/profile/evaluation; không auto-retrain từ một report.             |

### 6.8 Non-functional, policy và measurement-governance requirements

BR-NFR-010 là requirement quản trị measurement/reporting của product initiative, không phải một runtime feature; nó được giữ trong nhóm này để ngăn việc công bố chất lượng vượt quá evidence.

| **ID**     | **Requirement**                                                                                                                                                                                                                                                                                                                                                       | **Priority** | **Product Vision source** | **Acceptance**                                                                                      |
| ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ | ------------------------- | --------------------------------------------------------------------------------------------------- |
| BR-NFR-001 | Mọi dossier, job, object, index và audit event phải gắn tenant boundary.                                                                                                                                                                                                                                                                                              | Must         | §3.2, §7.1                | Negative access test không đọc/tìm/tải/suy ra resource tenant khác.                                 |
| BR-NFR-002 | Dossier mới phải private-by-default và chia sẻ MVP chỉ trong cùng tenant.                                                                                                                                                                                                                                                                                             | Must         | §4.1, §6.2, §9.1          | Dossier chưa share không xuất hiện với user ngoài ACL.                                              |
| BR-NFR-003 | Tenant Admin/Platform Support không mặc nhiên được đọc content; Platform Support chỉ break-glass.                                                                                                                                                                                                                                                                     | Must         | §4.2, §6.2, §7.1          | ACL test phân biệt quyền quản trị và quyền đọc content.                                             |
| BR-NFR-004 | Search, keyword index, semantic index, API, download URL và object storage phải áp dụng tenant+dossier ACL.                                                                                                                                                                                                                                                           | Must         | §6.2, §7.1, §7.4          | Không có đường truy cập thay thế để bypass ACL.                                                     |
| BR-NFR-005 | Dữ liệu được mã hóa khi truyền/lưu trữ và file chỉ truy cập qua signed URL ngắn hạn.                                                                                                                                                                                                                                                                                  | Must         | §7.1                      | Security acceptance kiểm tra policy và URL expiry; chi tiết implementation thuộc tài liệu kỹ thuật. |
| BR-NFR-006 | Operational/audit log không được chứa raw contract text hoặc bản sao nội dung.                                                                                                                                                                                                                                                                                        | Must         | §7.1, §7.3                | Audit sample không chứa raw contract text.                                                          |
| BR-NFR-007 | Dữ liệu tenant không được dùng để train/cải thiện model cho tenant khác nếu chưa opt-in rõ ràng.                                                                                                                                                                                                                                                                      | Must         | §7.1, §7.5, §9.1          | Cross-tenant training/data-use audit có bằng chứng opt-in hoặc bị từ chối.                          |
| BR-NFR-008 | Audit append-only phải bao phủ login/failed login, upload, classification, processing, view, download/export, share/revoke, confirm, citation error, NEEDS_REVIEW, rerun, archive, delete, restore, purge, policy/ACL/legal hold và break-glass; mỗi event có actor/service, tenant, dossier, timestamp, action, result, reason, request/job ID và version liên quan. | Must         | §7.3                      | Audit completeness đo được trên expected event ledger; audit không chứa raw contract text.          |
| BR-NFR-009 | Index và QueryTrace phải giữ version đủ để tái lập result trong giới hạn retention và ACL.                                                                                                                                                                                                                                                                            | Must         | §3.2, §7.4, §7.5          | Cùng snapshot/profile/index/model version cho phép truy lại nguồn tương ứng.                        |
| BR-NFR-010 | Không được đặt numeric target accuracy, latency, cost hoặc throughput trước baseline.                                                                                                                                                                                                                                                                                 | Must         | §4.2, §8, §9.1            | Metric report luôn ghi sample, denominator, version và giới hạn diễn giải.                          |
| BR-NFR-011 | Tài liệu nhạy cảm mặc định không được gửi tới external OCR/LLM; outbound chỉ được phép khi có policy phê duyệt và service register.                                                                                                                                                                                                                                   | Must         | §7.1                      | Request không có approval/service register bị chặn và tạo audit event.                              |
| BR-NFR-012 | Audit metadata phải giữ mặc định 12 tháng hoặc theo retention policy của tenant, không chứa raw contract content.                                                                                                                                                                                                                                                     | Must         | §7.3                      | Audit event vẫn truy được trong retention window; retention change có policy/audit evidence.        |

### 6.9 Transition requirements

| **ID**     | **Requirement**                                                                                                       | **Priority** | **Product Vision source** | **Acceptance**                                                     |
| ---------- | --------------------------------------------------------------------------------------------------------------------- | ------------ | ------------------------- | ------------------------------------------------------------------ |
| BR-TRN-001 | Người dùng phải đi được từ tạo tenant, mời thành viên, upload dossier đến xác nhận role/relation và chia sẻ reviewer. | Must         | §6.1                      | Onboarding walkthrough hoàn thành được với một dossier mẫu.        |
| BR-TRN-002 | Dossier processing phải có trạng thái rõ trong thời gian OCR/index bất đồng bộ.                                       | Must         | §2.4, §4.1, §7.5          | User biết dossier đang processing, active, failed hoặc cần review. |
| BR-TRN-003 | Khi profile hoặc document thay đổi, hệ thống phải tạo run/version mới thay vì ghi đè lịch sử cũ.                      | Must         | §5.1, §7.4, §7.5          | Rerun walkthrough truy được cả bản cũ và bản mới.                  |
| BR-TRN-004 | Khi xóa nhầm, người có quyền phải có đường restore rõ ràng trong 30 ngày mặc định.                                    | Must         | §1.3, §7.2                | User thực hiện được delete → restore và thấy lại history hợp lệ.   |

## 7. Business rules và glossary

### 7.1 Business rules

| **ID**     | **Rule**                                                                                                                                                                                                            |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| BR-RUL-001 | Không suy contract/annex role, relation, entity identity, value, unit, currency, validity hoặc context từ filename, upload order hoặc giả định pháp lý khi evidence không đủ.                                       |
| BR-RUL-002 | Cấu trúc gốc phải được giữ lại; normalized mapping chỉ được tạo khi đủ evidence.                                                                                                                                    |
| BR-RUL-003 | INSUFFICIENT_EVIDENCE là query/result status khi hệ thống không đủ evidence để trả lời; NEEDS_REVIEW là trạng thái cần reviewer kiểm tra hoặc xử lý tiếp; UNKNOWN/NEEDS_REVIEW áp dụng cho phân loại chưa xác định. |
| BR-RUL-004 | Candidate difference/conflict là technical finding, không phải legal conclusion, không tự xác định precedence hoặc hiệu lực.                                                                                        |
| BR-RUL-005 | Review action không được ghi đè raw OCR, source snapshot, machine output, citation gốc hoặc model disposition.                                                                                                      |
| BR-RUL-006 | Mọi result phải chịu tenant/dossier ACL trước retrieval, display, download và QueryTrace access.                                                                                                                    |
| BR-RUL-007 | Index active cũ được giữ cho đến khi index mới publish thành công hoặc được rollback theo policy.                                                                                                                   |
| BR-RUL-008 | Restore không tự chạy lại OCR; nếu cần xử lý mới, phải tạo rerun/version mới.                                                                                                                                       |
| BR-RUL-009 | Legal hold chặn purge bất kể retention window đã hết.                                                                                                                                                               |
| BR-RUL-010 | Một feedback/citation report không tự động thay đổi rule, profile, gold data hoặc model.                                                                                                                            |
| BR-RUL-011 | Dùng INSUFFICIENT_EVIDENCE khi hệ thống không thể trả lời đáng tin do thiếu source/value/context; dùng NEEDS_REVIEW khi result/classification cần reviewer kiểm tra hoặc citation bị báo lỗi.                       |

### 7.2 Glossary

| **Thuật ngữ**                 | **Định nghĩa nghiệp vụ**                                                                                   |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------- |
| Dossier                       | Nhóm tài liệu gồm contract và có thể có annex cần được rà soát cùng nhau.                                  |
| Contract/Annex                | Vai trò tài liệu trong dossier; phải có nguồn xác nhận.                                                    |
| Relation                      | Quan hệ nghiệp vụ hoặc quan hệ cần kiểm tra giữa các document/node.                                        |
| StructuralNode                | Đơn vị cấu trúc giữ label gốc, normalized type, hierarchy, order và citation/bbox.                         |
| Fact                          | Giá trị nghiệp vụ có raw value, normalized value khi có thể, context và evidence.                          |
| Ground truth/Gold             | Nhãn hoặc đáp án độc lập dùng để đánh giá; không được dùng để điền vào result khi hệ thống thiếu evidence. |
| Citation                      | Tham chiếu tới document, page, node/line/span và bbox trong snapshot.                                      |
| Candidate difference/conflict | Khác biệt kỹ thuật được đưa ra để reviewer kiểm tra, không phải kết luận pháp lý.                          |
| TenantProfile                 | Cấu hình phiên bản hóa theo tenant cho document type, alias, taxonomy và canonical fields.                 |
| IndexVersion                  | Phiên bản index gắn với document snapshot, profile và policy version.                                      |
| QueryTrace                    | Dấu vết query/result/citation/status/version/actor chịu ACL và retention.                                  |
| NEEDS_REVIEW                  | Trạng thái cần reviewer xem xét tiếp do evidence thiếu, sai, không resolve hoặc classification chưa rõ.    |
| INSUFFICIENT_EVIDENCE         | Result status khi hệ thống không đủ evidence để trả lời đáng tin cậy.                                      |
| ReviewRevision                | Bản ghi review append-only; trong MVP lưu action xác nhận/báo lỗi mà không ghi đè machine output.          |
| FeedbackReport                | Báo cáo feedback citation/finding ở giai đoạn sau, liên kết query và evidence version.                     |
| FeedbackRevision              | Bản revision chỉ được tạo sau khi feedback được xác minh theo workflow future.                             |
| UsagePolicy                   | Policy về query mode, cost, quota, rate limit và cache của tenant.                                         |
| QuotaPolicy                   | Giới hạn usage theo user, tenant, query mode và time window.                                               |
| LegalHold                     | Trạng thái ngăn purge dossier cho đến khi được gỡ theo policy.                                             |
| Archive                       | Trạng thái dossier không còn trong active search nhưng vẫn được giữ theo retention/audit policy.           |

## 8. Acceptance scenarios

| **ID** | **Scenario**              | **Given**                                            | **When**                                  | **Then**                                                                                                                     | **Covers**                                                             |
| ------ | ------------------------- | ---------------------------------------------------- | ----------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| AC-001 | Upload chưa query         | User upload dossier hợp đồng và phụ lục              | Chưa nhập câu hỏi                         | Hệ thống hiển thị cây dossier, structure, table/row/cell, citation và cảnh báo.                                              | BR-FUN-001, BR-FUN-003, BR-FUN-004, BR-FUN-008, BR-TRN-001, BR-TRN-002 |
| AC-002 | Xác nhận relation         | Dossier có nhiều file và manifest                    | Operator xác nhận role/relation           | Cross-document navigation sử dụng relation đã xác nhận.                                                                      | BR-FUN-002, BR-STK-002, BR-RUL-001                                     |
| AC-003 | Relation không rõ         | Filename/order không đủ evidence                     | Hệ thống xử lý dossier                    | Relation chuyển UNKNOWN/NEEDS_REVIEW, không tự suy.                                                                          | BR-FUN-002, BR-FUN-007, BR-RUL-001                                     |
| AC-004 | Cấu trúc không chuẩn      | PDF không có Điều–Khoản–Điểm                         | Hệ thống dựng structure                   | Giữ label gốc và tạo StructuralNode/UNNUMBERED_BLOCK phù hợp.                                                                | BR-FUN-005, BR-FUN-006, BR-RUL-002                                     |
| AC-005 | Exact search              | Query trùng giá trị trong PDF                        | Reviewer chạy exact/keyword search        | Result chứa đúng document/page/citation/bbox nếu user có quyền.                                                              | BR-BUS-001, BR-BUS-002, BR-FUN-009, BR-FUN-013                         |
| AC-006 | Structured search         | Query theo field/structure/context                   | Reviewer chạy structured retrieval        | Result có field/context và source tương ứng.                                                                                 | BR-FUN-010, BR-FUN-012, BR-FUN-013                                     |
| AC-007 | Semantic search           | Câu hỏi không trùng nguyên văn                       | Reviewer chạy semantic search             | Result có source hoặc INSUFFICIENT_EVIDENCE, không trả khẳng định không có evidence.                                         | BR-FUN-011, BR-FUN-014, BR-RUL-003, BR-RUL-011                         |
| AC-008 | Candidate difference      | Hai nguồn có khác biệt                               | Hệ thống tạo candidate                    | Candidate hiển thị hai nguồn, reason và không kết luận legal conflict.                                                       | BR-BUS-003, BR-FUN-015, BR-RUL-004                                     |
| AC-009 | Citation lỗi              | Citation sai hoặc không resolve                      | Reviewer báo lỗi/gắn NEEDS_REVIEW         | Trạng thái, actor, time, query và version được audit.                                                                        | BR-FUN-013, BR-FUN-017, BR-NFR-008, BR-RUL-003                         |
| AC-010 | Reviewer confirm          | Evidence resolve đúng source                         | Reviewer xác nhận                         | Review action được lưu mà không ghi đè machine output.                                                                       | BR-STK-001, BR-FUN-016, BR-RUL-005                                     |
| AC-011 | Template unknown          | Tenant document không khớp profile                   | Hệ thống phân loại                        | Trả UNKNOWN/NEEDS_REVIEW, không ép canonical mapping.                                                                        | BR-FUN-007, BR-FUN-020                                                 |
| AC-012 | Tenant isolation          | User tenant A không có ACL dossier B                 | User search/download/trace                | Không trả content, metadata hoặc sự tồn tại dossier B.                                                                       | BR-BUS-004, BR-STK-004, BR-NFR-001, BR-NFR-002, BR-NFR-004, BR-RUL-006 |
| AC-013 | Admin least privilege     | Tenant Admin không có dossier content permission     | Admin truy cập dossier                    | Bị từ chối content nhưng vẫn quản lý policy theo quyền.                                                                      | BR-STK-003, BR-NFR-003                                                 |
| AC-014 | Break-glass               | Support có ticket/phê duyệt/thời hạn                 | Support truy cập tạm thời                 | Access được audit đầy đủ và tự hết hiệu lực.                                                                                 | BR-STK-005, BR-NFR-008                                                 |
| AC-015 | Index success             | Index cũ active, index mới processing                | Index mới hoàn tất                        | Index mới publish atomic và result pin version mới.                                                                          | BR-FUN-022, BR-FUN-023, BR-TRN-003, BR-NFR-009                         |
| AC-016 | Index failure             | Index mới failed                                     | User search                               | Index cũ tiếp tục phục vụ, lỗi/retry được hiển thị và audit.                                                                 | BR-FUN-023, BR-RUL-007                                                 |
| AC-017 | Query governance          | User vượt quota/rate policy                          | User tiếp tục query                       | Trả RATE_LIMITED, không retry vô hạn hoặc vượt tenant budget.                                                                | BR-FUN-026, BR-FUN-027                                                 |
| AC-018 | Query trace               | Query đã trả result                                  | Auditor hoặc user có quyền xem trace      | Trace có actor/query/result/citation/status/document/index/profile/model version.                                            | BR-FUN-025, BR-NFR-008, BR-NFR-009                                     |
| AC-019 | Soft-delete               | Dossier ở ACTIVE                                     | User có quyền xóa                         | Dossier chuyển SOFT_DELETED, biến khỏi search/UI và signed URL bị thu hồi.                                                   | BR-FUN-028, BR-FUN-029, BR-TRN-004                                     |
| AC-020 | Restore                   | Dossier soft-delete chưa quá 30 ngày                 | Người có quyền restore                    | PDF/OCR/structure/citation/history trở lại; không tự rerun OCR.                                                              | BR-FUN-030, BR-RUL-008                                                 |
| AC-021 | Legal hold                | Dossier có LegalHold                                 | Retention hết hạn                         | Purge bị chặn và trạng thái hold hiển thị.                                                                                   | BR-FUN-031, BR-RUL-009                                                 |
| AC-022 | Purge                     | Dossier hết retention, không legal hold              | Lifecycle purge chạy                      | Source, render, OCR, extraction, embedding, index, cache và bản sao vận hành bị xử lý theo policy.                           | BR-FUN-032, BR-NFR-012                                                 |
| AC-023 | Feedback boundary         | Reviewer báo citation sai                            | MVP xử lý report                          | Chỉ ghi nhận lỗi/NEEDS_REVIEW; không auto-update model/profile/rule.                                                         | BR-FUN-018, BR-FUN-019, BR-RUL-010                                     |
| AC-024 | Profile rerun             | TenantProfile được thay đổi                          | Hệ thống tạo run mới                      | Result cũ giữ snapshot/profile/version cũ; result mới pin version mới.                                                       | BR-FUN-020, BR-FUN-021, BR-TRN-003                                     |
| AC-025 | External egress           | Request muốn gửi tài liệu tới OCR/LLM ngoài hệ thống | Không có approval/service register        | Request bị chặn và audit event được tạo.                                                                                     | BR-NFR-011, BR-RUL-006                                                 |
| AC-026 | Audit retention           | Audit event đã được tạo                              | Đến thời điểm kiểm tra retention          | Event còn trong 12 tháng mặc định hoặc retention policy đã duyệt, không có raw content.                                      | BR-NFR-006, BR-NFR-008, BR-NFR-012                                     |
| AC-027 | Archive                   | Dossier đang active                                  | Người có quyền archive                    | Dossier không nằm trong active search nhưng vẫn giữ source/history theo policy và audit.                                     | BR-FUN-033                                                             |
| AC-028 | Sharing/revoke            | Dossier được share trong cùng tenant                 | Owner cấp hoặc thu hồi quyền              | Search/download/share thay đổi theo ACL; action được audit.                                                                  | BR-FUN-034, BR-NFR-002, BR-NFR-004                                     |
| AC-029 | Future feedback lifecycle | Feedback được tạo ở phase sau                        | Feedback đi qua workflow                  | Chỉ VERIFIED mới có thể APPLIED hoặc REJECTED; report chưa verify không đổi model/profile.                                   | BR-FUN-035                                                             |
| AC-030 | Measurement baseline      | Có task/query set và ground truth                    | Nhóm tạo evaluation report                | Report có metric definition, n, denominator, sample, version, missing/failed/not-run và không dùng confidence thay accuracy. | BR-BUS-005, BR-NFR-010                                                 |
| AC-031 | Batch job state           | Dossier batch có nhiều processing job                | Operator chạy batch                       | Mỗi job có trạng thái rõ; lỗi một job không làm mất trạng thái các job khác.                                                 | BR-FUN-024                                                             |
| AC-032 | Storage protection        | File và data flow thuộc tenant                       | Hệ thống lưu/truyền hoặc tạo download URL | Dữ liệu được bảo vệ theo policy; URL hết hạn; audit không chứa raw contract text.                                            | BR-NFR-005, BR-NFR-006                                                 |
| AC-033 | External data use         | Tenant chưa opt-in cross-tenant training             | Service xử lý hoặc cải thiện model        | Dữ liệu tenant không được dùng cho tenant khác; outbound OCR/LLM phải có approval/service register.                          | BR-NFR-007, BR-NFR-011                                                 |
| AC-034 | Audit retention           | Audit event đã được tạo                              | Kiểm tra sau retention boundary           | Audit metadata giữ 12 tháng mặc định hoặc policy tenant; thay đổi retention có audit.                                        | BR-NFR-012                                                             |

## 9. Metrics và phương pháp nghiệm thu

### 9.1 Metrics cần đo

| **Metric**                      | **Mục đích**                                             | **Ground truth/evidence**                |
| ------------------------------- | -------------------------------------------------------- | ---------------------------------------- |
| Time-to-correct-source          | Đo thời gian từ query đến source đúng.                   | Task và citation đích.                   |
| Task success rate               | Đo tỷ lệ tìm đúng thông tin và nguồn.                    | Đáp án và document/page/clause expected. |
| Retrieval Recall\@k             | Đo source đúng trong top-k.                              | Citation gold theo query.                |
| Citation correctness            | Đo document/page/line/span/bbox đúng.                    | Manual audit sample.                     |
| Reviewer escalation rate        | Đo tỷ lệ cần NEEDS_REVIEW hoặc citation error.           | Review/audit record.                     |
| Template recognition coverage   | Đo phân loại đúng hoặc chuyển review đúng.               | Label document type/clause/relation.     |
| Tenant isolation violation rate | Đo request trả dữ liệu ngoài ACL.                        | Cross-tenant/dossier access test.        |
| Audit completeness              | Đo thao tác bắt buộc có event hợp lệ, không raw content. | Expected event ledger.                   |
| Delete/restore correctness      | Đo lifecycle source/OCR/index/cache/history.             | Lifecycle drill.                         |
| Hybrid retrieval Recall\@k      | Đo riêng keyword/structured/semantic.                    | Query set và citation gold.              |
| Index freshness                 | Đo upload/update đến index active.                       | Processing/index timestamps.             |
| Index rollback correctness      | Đo giữ index cũ khi job lỗi.                             | Failure/retry/rollback scenarios.        |
| Cost per query                  | Đo cost theo user, tenant và query mode.                 | Usage ledger và pricing version.         |
| Cache hit rate                  | Đo truy vấn lặp lại dùng cache hợp lệ.                   | Query/cache events.                      |
| Query trace completeness        | Đo trace đủ result/status/citation/version.              | Expected trace ledger.                   |
| Structural mapping coverage     | Đo mapping numbered/unnumbered đúng hoặc review đúng.    | Gold labels.                             |

### 9.2 Quy tắc diễn giải

- Không dùng model confidence thay cho ground-truth accuracy.
- Không công bố target số khi chưa có baseline.
- Mọi report phải ghi n, denominator, sample, version, missing/failed/not-run và giới hạn diễn giải.
- Product Vision acceptance ở Sprint 1 là thống nhất problem, user, value, boundary, non-goals và cách kiểm chứng; không đồng nghĩa production readiness.

## 10. Traceability Product Vision → BRD

| **Product Vision**                       | **Nội dung chuyển thành BRD**                                                                                | **Requirement/acceptance**                                                                           |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------- |
| §1.1–§1.5 Vision Board                   | Vision, target group, needs, product capabilities và business goals.                                         | BR-BUS-001..005; §2                                                                                  |
| §2.1–§2.4 Painpoint và value flow        | Painpoint tìm đúng nguồn, JTBD, upload-to-review flow.                                                       | BR-BUS-001..003; BR-TRN-001..004; §5                                                                 |
| §3.1–§3.2 Giá trị và nguyên tắc          | Search-first, evidence-first, context, human accountability, versioning, cost-aware, tenant isolation.       | BR-FUN-009..017; BR-RUL-001..010                                                                     |
| §4.1 Trong phạm vi MVP                   | Dossier, PDF, structure, search, candidate, role, index, query, lifecycle.                                   | BR-FUN-001..017, BR-FUN-020..032; BR-NFR-001..012; BR-TRN-002; AC-001..022, AC-024..026, AC-030..034 |
| §4.2 Ngoài phạm vi                       | Legal, signature, PDF editing, non-PDF, external guest, dedicated topology và production claims.             | §4.3                                                                                                 |
| §4.3 Giai đoạn sau                       | Direct edit, reject, request evidence, feedback loop, advanced conflict, bbox editing.                       | BR-FUN-018..019, BR-FUN-035; §4.2; AC-023, AC-029                                                    |
| §5.1–§5.3 Tenant adaptation              | TenantProfile, unknown template, StructuralNode schema-agnostic.                                             | BR-FUN-005..007, BR-FUN-020..021; BR-RUL-002                                                         |
| §6.1–§6.3 User/access/feedback           | Onboarding, roles, ACL, archive, sharing và feedback boundary.                                               | BR-STK-001..005; BR-TRN-001; BR-FUN-033..035; BR-NFR-001..004; AC-001..014, AC-023, AC-027..029      |
| §7.1–§7.5 Security/lifecycle/index/query | Tenant boundary, encryption/egress policy, audit, restore/purge, index version, QueryTrace, cost governance. | BR-FUN-022..034; BR-NFR-001..012; AC-015..022, AC-024..028, AC-032..034                              |
| §8.1–§8.3 Metrics/acceptance             | Metric catalogue, ground truth, baseline và evidence gate.                                                   | BR-BUS-005, BR-NFR-010; AC-030                                                                       |
| §9.1–§9.3 Assumptions/risks/validation   | Risk controls, clarification register và test scenarios.                                                     | BR-RUL-001..011; §8, §9, §11                                                                         |

Mọi thay đổi Product Vision sau khi BRD được accepted phải tạo revision impact assessment cho các requirement và acceptance scenario bị ảnh hưởng. Cột Covers trong §8 là reverse trace từ acceptance scenario về requirement; không requirement nào được coi là ready nếu chưa có ít nhất một acceptance ID hoặc lý do Not applicable được Product Owner phê duyệt.

## 11. Rủi ro và source clarification register

| **ID**   | **Nội dung**                                                                                      | **Cách xử lý trong BRD**                                                                                                                  | **Owner/status**                                 |
| -------- | ------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| CL-001   | Luồng người dùng có cụm “review, sửa, xác nhận”, trong khi §4.3 đưa direct edit ra giai đoạn sau. | Baseline MVP dùng check/confirm/report citation/NEEDS_REVIEW; direct edit không được triển khai.                                          | Product Owner / Resolved for BRD                 |
| CL-002   | Product Vision có single run và batch run trong MVP nhưng chưa có target scale.                   | Giữ batch là Must capability; walkthrough ưu tiên single dossier nhưng phải có acceptance job state cho batch; không invent scale target. | Product Owner / Resolved for BRD                 |
| CL-003   | INSUFFICIENT_EVIDENCE và NEEDS_REVIEW phục vụ hai lớp khác nhau.                                  | INSUFFICIENT_EVIDENCE là result status; NEEDS_REVIEW là review/classification state.                                                      | Product Owner / Resolved for BRD                 |
| CL-004   | Không có baseline accuracy/cost/latency/throughput.                                               | Chỉ định nghĩa metric và ground truth; chưa đặt threshold.                                                                                | Product Owner / Open benchmark                   |
| RISK-001 | Người dùng có thể chỉ cần keyword thay vì semantic question.                                      | Đo riêng các query mode và task success.                                                                                                  | Product Owner / Must monitor                     |
| RISK-002 | Relation contract/annex không suy ra an toàn.                                                     | Bắt buộc manifest/evidence; không suy filename/order.                                                                                     | Product Owner + Uploader/Operator / Must control |
| RISK-003 | Bảng dài, scan kém hoặc text layer sai làm citation/bbox không tin cậy.                           | Không suy đoán; chuyển NEEDS_REVIEW; đo citation correctness.                                                                             | Product Owner / Must monitor                     |
| RISK-004 | Model confidence cao nhưng result sai.                                                            | Ground-truth evaluation độc lập với confidence.                                                                                           | Product Owner / Must control                     |
| RISK-005 | ACL/tenant filter sai gây rò rỉ dữ liệu.                                                          | Private-by-default, ACL trước retrieval/display và negative access test.                                                                  | Tenant Owner/Admin / Must verify                 |
| RISK-006 | Purge bỏ sót index/cache/bản sao vận hành.                                                        | Lifecycle drill bao phủ toàn bộ content representation.                                                                                   | Tenant Owner/Admin / Must verify                 |
| RISK-007 | Profile/policy thay đổi làm result cũ không tái lập.                                              | Pin snapshot/profile/policy/index/model version.                                                                                          | Product Owner / Must verify                      |
| RISK-008 | Query bất thường hoặc retry vô hạn làm chi phí tăng.                                              | Quota, rate limit, cache, circuit breaker và usage ledger.                                                                                | Product Owner / Must verify                      |

## 12. Review, approval và change control

| **Trạng thái** | **Điều kiện**                                                                          | **Evidence**                                   |
| -------------- | -------------------------------------------------------------------------------------- | ---------------------------------------------- |
| Draft          | BRD mới đã soạn, chưa review.                                                          | File version và self-check.                    |
| Product review | Product Owner kiểm tra scope, priority và business rules.                              | Comment/decision có ngày.                      |
| Mentor review  | Mentor kiểm tra problem, value, scope và acceptance direction.                         | Review record có ngày.                         |
| Returned       | Có feedback cần chỉnh sửa.                                                             | Feedback và change list.                       |
| Accepted       | Product Owner/mentor chấp nhận, không còn blocker về scope/security/reviewer boundary. | Sign-off durable.                              |
| Superseded     | Có bản BRD mới thay thế.                                                               | Link tới version kế tiếp và impact assessment. |

Change control:

1. Mọi thay đổi requirement phải cập nhật version và changelog.
2. Thay đổi Product Vision phải rà lại traceability và acceptance.
3. Không xóa requirement đã accepted; chuyển trạng thái Superseded hoặc Deferred kèm lý do.
4. Requirement không có source Product Vision phải được đánh dấu là proposed change, không tự đưa vào baseline.

## 13. Phương pháp và tài liệu tham chiếu

- Product Vision: ST-014-DOC-01-PRODUCT-VISION.vi.md
- IIBA — [Understanding Requirements and Designs](https://www.iiba.org/knowledgehub/the-business-analysis-standard/4-implementing-business-analysis/4-4-understanding-requirements-and-designs/)
- IEEE — [IEEE/ISO/IEC 29148:2018](https://standards.ieee.org/ieee/29148/6937/)
- ISO — [ISO/IEC/IEEE 29148:2018](https://www.iso.org/obp/ui?_escaped_fragment_=iso%3Astd%3Aiso-iec-ieee%3A29148%3Aed-2%3Av1%3Aen)

Các chuẩn trên chỉ định hướng cách phân loại, viết, kiểm tra và quản lý requirement. Nội dung yêu cầu sản phẩm trong BRD này chỉ được lấy từ Product Vision v0.4.

## 14. Changelog

| **Version** | **Date**   | **Change**                                       |
| ----------- | ---------- | ------------------------------------------------ |
| v1.0        | 18/09/2026 | Tạo baseline BRD độc lập từ Product Vision v0.4. |
