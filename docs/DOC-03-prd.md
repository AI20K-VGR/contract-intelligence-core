**DOC-03 — Product Requirements Document: Contract Intelligence (PROD-01)**
**Phiên bản:** v0.11 — Draft, Ready for Review  |  **Ngày soạn:** 18/09/2026  |  **Căn chỉnh theo:** DOC-01 Product Vision v0.4 (18/09/2026)  |  **Trạng thái:** Draft — chưa reviewer nào sign-off bản v0.11.

---

## 0. Document Control

| **TrườngNội dung**           |                                                                                                                                                                                   |
| ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Product**                  | Contract Intelligence (PROD-01)                                                                                                                                                   |
| **Document ID**              | DOC-03 — Product Requirements Document                                                                                                                                            |
| **Owner**                    | Trần Thị Kiều Trang — Leader (PRD consolidation)                                                                                                                                  |
| **Contributors**             | Trần Thị Kiều Trang (HITL/UX) · Phạm Hoàng Chương (Backend/API) · Nguyễn Đức Dũng (OCR/ingestion — AI1) · Trần Văn Dũng (Finding/semantics — AI2)                                 |
| **Version**                  | 0.11 — Draft, ready for review                                                                                                                                                    |
| **Status**                   | Draft — Ready for Review                                                                                                                                                          |
| **Date**                     | 18/09/2026                                                                                                                                                                        |
| **Sprint**                   | Sprint 1 — chốt yêu cầu, wireframe, schema, nháp API                                                                                                                              |
| **Nguồn chuẩn cấp sản phẩm** | DOC-01 Product Vision v0.4                                                                                                                                                        |
| **References**               | DOC-01 Vision · DOC-02 BRD (ST-015) · DOC-04 Architecture · DOC-05 API Spec · DOC-06 Eval Report · ST-016 Case Catalog · ST-017 Data Contract · ST-022 Traceability & Integration |

### 0.1 Nguyên tắc phân cấp tài liệu

1. DOC-01 quyết định **vấn đề, người dùng, giá trị, ranh giới sản phẩm, non-goals**.
2. DOC-03 (tài liệu này) quyết định **hệ thống phải làm gì, đo bằng gì, acceptance là gì, cái gì không làm**.
3. DOC-04 / DOC-05 / ST-017 quyết định **làm bằng cách nào**: kiến trúc, endpoint, schema, offset, hệ tọa độ, storage, index, cache.
4. Khi DOC-03 và DOC-01 lệch nhau: ghi vào §11, chốt tại buổi review, cập nhật cả hai. Không sửa ngầm một phía.

**Quy tắc viết requirement trong tài liệu này:** mỗi FR mô tả **hành vi quan sát được** của sản phẩm, không mô tả cơ chế. Nếu một câu chỉ đúng khi biết trước cách cài đặt, câu đó thuộc DOC-04.

## 0.2 Changelog

#### v0.10 → v0.11 (vòng scope normalization)

| **#Thay đổiLý do** |                                                                                                                               |                                                                                                                |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| **C-18**           | Thêm **Scope tier** `T1 MVP-OJT` / `T2 Vision-MVP` cho mọi FR; định nghĩa lại Must/Should là *trong tier của nó*              | §4 và §14 của v0.10 mâu thuẫn: cùng một capability vừa là Must-tới-hết-OJT vừa được đề xuất để sau OJT         |
| **C-19**           | Thêm §1.2 Problem Statement (tóm tắt, trỏ DOC-01 §2)                                                                          | PRD nhảy thẳng vào "hệ thống phải làm gì"                                                                      |
| **C-20**           | Thêm §1.4 Product Goals G1–G6 và mapping Goal → FR → Metric                                                                   | Có principle nhưng chưa có goal cấp sản phẩm                                                                   |
| **C-21**           | Thêm §1.6 Product Success Metrics (target `TBD after Gate B`, nguồn DOC-06)                                                   | Chưa có chỗ trả lời "thành công đo bằng gì"                                                                    |
| **C-22**           | Thêm §10 Assumptions (A-01…A-10)                                                                                              | Assumption đang rải rác trong Constraints / Decisions / Workflow                                               |
| **C-23**           | Tách §11 cũ thành **§11 Dependencies**, **§12 Risk Register**, **§13 Open Decisions**                                         | v0.10 gọi là "Open Decisions & Dependencies" nhưng bảng gần như toàn decision; risk chỉ nằm trong văn xuôi §14 |
| **C-24**           | §4 chia hai khối: **4.A Core capability** và **4.B Platform capability**, không còn đứng ngang hàng                           | Phản ánh đúng thứ tự ưu tiên; 16 nhóm FR phẳng khiến PRD đọc như system spec                                   |
| **C-25**           | Viết lại 9 FR đang mô tả cơ chế thành hành vi quan sát được (TEN-01/02, IDX-03, COST-02/07, AUD-06, SRCH-07, LCM-05, PROF-02) | Vi phạm chính quy tắc PRD tự đặt ở §0.1                                                                        |
| **C-26**           | Bỏ DC-14 và các chi tiết lưu trữ khỏi §9; nén DC trùng lặp với §4 thành invariant một dòng                                    | §9 đang chép lại §4                                                                                            |
| **C-27**           | §14 (Scope warning) hợp nhất vào §3 Scope và §12 Risk; không còn tồn tại như một mục cảnh báo riêng                           | Không thể vừa ràng buộc ở §4 vừa cảnh báo ngược lại ở cuối tài liệu                                            |

#### v0.9 → v0.10 (vòng đồng bộ DOC-01 v0.4)

| **#Thay đổiNguồn DOC-01** |                                                                                        |                    |
| ------------------------- | -------------------------------------------------------------------------------------- | ------------------ |
| **C-01**                  | Product scope viết lại theo **search-first**                                           | §1.4, §2.4, §3.2   |
| **C-02 → C-08**           | Thêm FR-TEN, FR-SRCH, FR-NAV, FR-IDX, FR-LCM, FR-COST, FR-PROF                         | §1.4, §5, §6.2, §7 |
| **C-09**                  | FR-CLA chuyển sang `StructuralNode`; Điều–Khoản–Điểm là một mapping                    | §5.3               |
| **C-10**                  | Audit trail append-only, không chứa raw contract text                                  | §7.3               |
| **C-11**                  | Thêm `NEEDS_REVIEW` / `INSUFFICIENT_EVIDENCE` cấp query, tách khỏi `model_disposition` | §1.3, §4.1         |
| **C-12**                  | `correct` / `reject` / `needs-more-evidence` đánh dấu mâu thuẫn → D-15                 | §4.3, §6.3         |
| **C-13 → C-17**           | Roles mở rộng, out-of-scope đồng bộ, CON-03b, traceability matrix                      | §4.2, §6.2, §10    |

---

# 1. Product Overview

### 1.1 Purpose của tài liệu

PRD trả lời: hệ thống **phải làm gì, cho ai, đo bằng gì, acceptance là gì, cái gì không làm**. Cơ chế triển khai thuộc DOC-04 / DOC-05 / ST-017.

### 1.2 Problem Statement

*(Tóm tắt; mô tả đầy đủ painpoint, hậu quả và job-to-be-done ở DOC-01 §2.)*
Một dossier hợp đồng gồm hợp đồng chính và nhiều phụ lục làm thông tin bị phân tán theo nhiều file, nhiều trang, nhiều điều khoản và bảng biểu. Người rà soát phải mở từng file, tìm thủ công, tự ghi nhớ phụ lục nào sửa nội dung nào, rồi quay lại bản gốc để kiểm chứng.
**Vấn đề cốt lõi không phải PDF chưa được OCR, mà là khó tìm đúng thông tin và khó xác định các nguồn liên quan trong cùng một dossier.**
Hậu quả hiện tại: mất thời gian định vị một fact; dễ mở nhầm phụ lục hoặc bỏ sót bản điều chỉnh; không phân biệt được khác biệt hợp lệ với conflict; kết quả tìm thủ công khó lặp lại và khó audit.
Quy trình hiện tại của reviewer:
Nhận dossier → mở từng PDF → đọc/Ctrl-F thủ công → tự đối chiếu hợp đồng với phụ lục
→ tự phán đoán khác biệt → quay lại bản gốc xác minh → kết luận nghiệp vụ

Sản phẩm can thiệp vào bốn bước giữa, giữ nguyên bước cuối cho con người.

### 1.3 Product scope

Hệ thống nhận một dossier hợp đồng PDF trong phạm vi một tenant và biến nó thành **bản đồ thông tin tìm kiếm được và kiểm chứng được**:

1. Nhận dossier gồm 1 hợp đồng + `0..n` phụ lục; vai trò và quan hệ tài liệu đến từ manifest hoặc evidence được xác nhận.
2. Dựng chỉ mục có cấu trúc (`StructuralNode`, bảng, fact) kèm citation/bbox.
3. Cho phép tìm kiếm trong phạm vi dossier và điều hướng tới đúng file/trang/điều khoản/vùng trên bản gốc.
4. Phát sinh **candidate difference/conflict** để reviewer kiểm tra, không tự kết luận pháp lý.
5. Cho reviewer xác nhận kết quả hoặc gắn `NEEDS_REVIEW`, ghi lịch sử append-only.
6. Cô lập dữ liệu theo tenant, kiểm soát truy cập và truy vết được.

**Thứ tự giá trị:** định vị thông tin đứng trước so sánh. OCR, clause extraction, table parsing và conflict detection là phương tiện (DOC-01 §2.4).
**Unit of processing:** một dossier = 1 hợp đồng thương mại + `0..n` phụ lục PDF, thuộc đúng một tenant. Phạm vi tìm kiếm mặc định là một dossier, không phải toàn bộ kho tài liệu. Không phải hồ sơ FAP / sinh viên.

### 1.4 Product Goals



| **IDGoalNăng lực MVP (DOC-01 §1.4)FR chínhMetric** |                                                                                        |                                                                                                                           |                                          |                  |
| -------------------------------------------------- | -------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------- | ---------------- |
| **G1**                                             | Reviewer tìm đúng thông tin trong một dossier nhanh hơn làm thủ công                   | (1) Nhận dossier, role từ manifest (2) Dựng chỉ mục StructuralNode, bảng, fact (3) Tìm kiếm hybrid trong phạm vi dossier  | FR-SRCH-01/02, FR-HITL-07/08             | M-01, M-02       |
| **G2**                                             | Mọi kết quả truy ngược được về nguồn gốc trên bản in                                   | (4) Trả kết quả kèm citation + bbox + nguồn liên quan                                                                     | FR-NAV-01/03, FR-FIND-07, FR-CLA-03      | M-03             |
| **G3**                                             | Giảm thao tác thủ công khi đối chiếu hợp đồng với phụ lục                              | (4) Nguồn liên quan giữa hợp đồng và phụ lục (5) Reviewer xác nhận / NEEDS_REVIEW                                         | FR-FIND-03/05, FR-NAV-02                 | M-04             |
| **G4**                                             | Hệ thống không tự kết luận pháp lý; trách nhiệm cuối thuộc reviewer                    | (5) Reviewer xác nhận, không phải hệ thống tự quyết                                                                       | FR-FIND-08, FR-APR-01, FR-REV-02         | M-05             |
| **G5**                                             | Sản phẩm đọc được hợp đồng có mẫu và cách đánh số khác nhau                            | (2) Chỉ mục structure-agnostic, không bắt buộc Điều–Khoản–Điểm                                                            | FR-CLA-04/05/06, FR-PROF-01              | M-06             |
| **G6**                                             | Dữ liệu của một tenant không truy cập được từ tenant khác                              | (6) Cô lập tenant, private-by-default, lọc quyền trên mọi surface                                                         | FR-TEN-01…05                             | M-07             |
| **G7**                                             | Kết quả luôn tái lập được; dữ liệu bị xóa không rò rỉ và khôi phục được trong thời hạn | (7) Audit, soft-delete, restore 30 ngày, purge theo policy (8) Index bất đồng bộ theo phiên bản, giữ bản cũ khi build lỗi | FR-AUD-01/03, FR-IDX-01/02, FR-LCM-01/02 | M-09, M-10, M-12 |
| **G8**                                             | Chi phí vận hành kiểm soát được; mọi truy vấn để lại dấu vết audit                     | (9) Điều phối truy vấn theo chi phí, cache, quota, rate limit (10) Lưu QueryTrace có kiểm soát theo ACL và retention      | FR-COST-01/04/06/07                      | M-11             |

Goal cấp nền tảng (T2): quản trị vòng đời dữ liệu, chi phí truy vấn và khả năng tái lập kết quả — xem §4.B, chưa đặt goal có metric trong OJT.

### 1.5 Product Principles (DOC-01 §3.2)

Mọi FR phải thỏa các nguyên tắc sau; FR vi phạm phải sửa hoặc đưa ra §13.

| **Nguyên tắc**                     | **Hệ quả bắt buộc**                                                           |
| ---------------------------------- | ----------------------------------------------------------------------------- |
| Search-first                       | Mỗi capability phải chỉ ra nó cải thiện việc tìm/định vị thông tin thế nào    |
| Hybrid retrieval                   | Exact/structured ưu tiên hơn semantic; semantic không ghi đè kết quả exact    |
| Evidence-first                     | Không có citation thì không được dùng để khẳng định                           |
| Context before comparison          | Chỉ so sánh khi đủ role, subject, unit, scope, validity                       |
| Human remains accountable          | Hệ thống tạo candidate; reviewer kết luận                                     |
| Traceable history                  | Machine output, OCR rerun và review correction là các lớp riêng, không ghi đè |
| Feedback-driven, not auto-learning | Không auto-retrain từ một report đơn lẻ                                       |
| Versioned indexing                 | Kết quả cũ vẫn phục vụ được khi bản mới chưa sẵn sàng                         |
| Cost-aware                         | Không gọi model cho mọi truy vấn                                              |
| Structure-agnostic                 | Không ép mọi tài liệu về Điều–Khoản–Điểm                                      |
| Auditable query                    | Query, result, citation, version tái hiện được theo quyền                     |
| Sensitive-data aware               | Outbound tới external service chỉ khi policy cho phép (CON-04, CON-05)        |
| Tenant isolation                   | Kết quả không được làm lộ sự tồn tại của resource ngoài ACL                   |
| Least privilege                    | Quyền quản trị tenant ≠ quyền đọc nội dung                                    |
| Recoverable deletion               | Xóa nhầm phải khôi phục được; legal hold chặn purge                           |

> Phân biệt: **principle** ràng buộc cách thiết kế; **goal** (§1.4) là kết quả mong muốn và đo được.

### 1.6 Product Success Metrics

PRD không đặt số target khi chưa có baseline (DOC-01 §8.2). Mọi số công bố phải kèm `n`, tên bộ mẫu và điều kiện chạy (FR-EVAL-02).

| **ID** | **Metric**                             | **Định nghĩa**                                                                          | **Tier**    | **Target**                   | **Nguồn** |
| ------ | -------------------------------------- | --------------------------------------------------------------------------------------- | ----------- | ---------------------------- | --------- |
| M-01   | Time-to-correct-source                 | Thời gian từ câu hỏi tới khi mở đúng file/trang/node                                    | T1          | TBD after Gate B             | DOC-06    |
| M-02   | Retrieval Recall\@k                    | Tỷ lệ task có nguồn đúng trong `k` kết quả đầu, tách theo exact / structured / semantic | T1          | TBD after Gate B             | DOC-06    |
| M-03   | Citation correctness                   | Citation trỏ đúng document, page, line/span và bbox                                     | T1          | TBD after Gate B             | DOC-06    |
| M-04   | Task success rate                      | Tỷ lệ task tìm đúng thông tin **và** đúng nguồn, so với baseline thủ công               | T1          | TBD after Gate B             | DOC-06    |
| M-05   | Reviewer escalation rate               | Tỷ lệ output reviewer phải gắn `NEEDS_REVIEW` hoặc báo lỗi citation                     | T1          | Theo dõi, không đặt ngưỡng   | DOC-06    |
| M-06   | Structural mapping coverage            | Tỷ lệ node map đúng **hoặc** chuyển `NEEDS_REVIEW` đúng cách                            | T1          | TBD after Gate B             | DOC-06    |
| M-07   | Tenant isolation violation rate        | Tỷ lệ request trả dữ liệu ngoài tenant/ACL                                              | T1          | **0** (ngưỡng cứng duy nhất) | DOC-06    |
| M-08   | OCR quality (text + dấu tiếng Việt)    | Theo protocol AI1                                                                       | T1          | TBD after Gate B             | DOC-06    |
| M-09   | Audit completeness                     | Tỷ lệ thao tác bắt buộc có event hợp lệ, không chứa raw content                         | T1 (subset) | TBD                          | DOC-06    |
| M-10   | Index freshness / rollback correctness | Thời gian tới khi bản chỉ mục mới phục vụ; job lỗi giữ đúng bản cũ                      | T2          | —                            | DOC-06    |
| M-11   | Cost per query / cache hit rate        | Chi phí và tỷ lệ phục vụ lại theo user, tenant, query mode                              | T2          | —                            | DOC-06    |
| M-12   | Delete/restore correctness             | Tỷ lệ lifecycle xóa/restore/purge đúng trạng thái                                       | T2          | —                            | DOC-06    |

**Baseline bắt buộc trước khi đọc M-01 và M-04:** reviewer làm thủ công trên cùng dossier (DOC-01 §9.3 mục 3). Owner: Leader + Trang. Không có baseline thì hai metric này không có ý nghĩa.

### 1.7 Terminology

Thuật ngữ nghiệp vụ (bắt buộc hiểu để đọc PRD):

| **Thuật ngữ**         | **Định nghĩa**                                                                                                                                                          |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Tenant                | Doanh nghiệp sử dụng nền tảng. Đơn vị cô lập dữ liệu cao nhất                                                                                                           |
| Dossier               | 1 hợp đồng + `0..n` phụ lục; đơn vị xử lý và đơn vị phân quyền                                                                                                          |
| Dossier ACL           | Tập quyền xem/sửa/tải/chia sẻ/xóa trên một dossier; độc lập với vai trò quản trị tenant                                                                                 |
| StructuralNode        | Đơn vị cấu trúc chuẩn hóa: heading, article, section, clause, paragraph, list item, table, table row, annex hoặc `UNNUMBERED_BLOCK`. Điều–Khoản–Điểm là **một mapping** |
| Fact                  | Giá trị typed được trích từ tài liệu, có raw, normalized, context và citation                                                                                           |
| Finding               | Output so sánh của AI2: hai fact refs + `model_disposition` + lý do + evidence                                                                                          |
| Conflict              | Tên product/API surface của tập finding cần reviewer xử lý. Không phải pipeline thứ hai                                                                                 |
| Candidate             | Finding là đề xuất kỹ thuật; reviewer là người kết luận                                                                                                                 |
| Review revision       | Một lần thao tác của reviewer trên finding hoặc node, append-only                                                                                                       |
| NEEDS_REVIEW          | Trạng thái cấp kết quả/node/tài liệu: máy không đủ căn cứ, cần người xử lý                                                                                              |
| INSUFFICIENT_EVIDENCE | Trạng thái cấp **query/result**: không đủ evidence để trả lời, hệ thống không suy đoán                                                                                  |

Thuật ngữ kỹ thuật (`Snapshot`, `Run`, `IndexVersion`, `QueryTrace`, `TenantProfile`, `StorageObject`, `RetentionPolicy`, `LegalHold`) định nghĩa tại **ST-017 Data Contract**; PRD chỉ tham chiếu.

> Phân lớp trạng thái: `insufficient_evidence` (§5.4.1) là disposition **cấp finding**; `INSUFFICIENT_EVIDENCE` là status **cấp query**. Không gộp. Quy ước đặt tên chốt tại D-24.

---

# 2. Users, Actors & Stakeholders

### 2.1 Product users

| **Persona**          | **Là ai**                                       | **Cần gì**                                                                                                                                        | **Tier** |
| -------------------- | ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| Reviewer (HITL)      | Chuyên viên rà soát hợp đồng / legal operations | Tìm đúng điều khoản hoặc giá trị, đối chiếu ảnh gốc với text OCR, xem finding kèm hai phía nguồn, xác nhận hoặc gắn `NEEDS_REVIEW`, duyệt dossier | T1       |
| Operator / Uploader  | Người vận hành pipeline                         | Đưa dossier vào hệ thống, xác nhận manifest và vai trò tài liệu, biết job ở đâu và vì sao lỗi                                                     | T1       |
| Tenant Owner / Admin | Quản trị doanh nghiệp                           | Quản lý thành viên, policy, retention, legal hold, dossier ACL. **Không tự động có quyền đọc nội dung**                                           | T2       |
| Viewer               | Pháp chế, mua hàng, bán hàng                    | Chỉ xem kết quả và nguồn được cấp quyền                                                                                                           | T2       |
| Auditor              | Người soát tuân thủ                             | Xem audit log theo quyền, không mặc định xem nội dung                                                                                             | T2       |
| Platform Support     | Nội bộ vận hành nền tảng                        | Không có quyền mặc định; chỉ break-glass có phê duyệt và thời hạn                                                                                 | T2       |

### 2.2 System actors

| **Actor**               | **Vai trò trong luồng**                                                                                                                    |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| AI1 — ingestion/OCR     | Tạo snapshot bất biến theo schema chuẩn                                                                                                    |
| AI2 — finding/semantics | Nhận snapshot, phát sinh fact + finding có evidence; **không** kết luận hiệu lực pháp lý, thứ tự ưu tiên tài liệu hay điều khoản hiện hành |
| Backend                 | Điều phối job, thực thi ACL, phục vụ payload                                                                                               |
| Search/index            | Phục vụ truy vấn trong phạm vi dossier và ACL                                                                                              |

System actor không phải persona; không có nhu cầu người dùng, chỉ có contract đầu vào/đầu ra (§8).

### 2.3 Stakeholders

Mentor VSF (duyệt architecture, gate vào Sprint 2) · Leader (scope, priority, nghiệm thu) · Product Owner (chủ DOC-01).
Ownership theo area và RACI của nhóm: **Project Plan / Sprint Plan**, không thuộc PRD. PRD chỉ giữ cột Owner ở §5 để biết ai chịu trách nhiệm cho từng requirement.

### 2.4 Key use cases

| **UC** | **Mô tả**                                                                               | **Goal** | **FR**                 |
| ------ | --------------------------------------------------------------------------------------- | -------- | ---------------------- |
| UC-01  | Operator nạp một dossier và theo dõi tới khi xem được                                   | —        | FR-UPL-01, FR-JOB-01   |
| UC-02  | Reviewer mở dossier vừa xử lý xong, **chưa đặt câu hỏi nào**, xem cây hồ sơ và cấu trúc | G1       | FR-HITL-07             |
| UC-03  | Reviewer tìm một giá trị cụ thể (đơn giá, MST, thời hạn) và mở đúng vị trí trên bản gốc | G1, G2   | FR-SRCH-01, FR-NAV-01  |
| UC-04  | Reviewer xem một điều khoản và thấy phụ lục nào có liên quan                            | G3       | FR-NAV-02              |
| UC-05  | Reviewer duyệt danh sách candidate difference giữa hợp đồng và phụ lục                  | G3, G4   | FR-FIND-05, FR-HITL-05 |
| UC-06  | Reviewer xác nhận kết quả hoặc gắn `NEEDS_REVIEW` / báo lỗi citation                    | G4       | FR-REV-02, FR-REV-03   |
| UC-07  | Reviewer duyệt dossier                                                                  | G4       | FR-APR-01              |
| UC-08  | Hệ thống gặp tài liệu mẫu lạ, không đoán bừa mà chuyển `NEEDS_REVIEW`                   | G5       | FR-PROF-04, FR-CLA-06  |

---

# 3. Scope

### 3.1 Hai tầng phạm vi

DOC-01 v0.4 mô tả một MVP SaaS multi-tenant. Ràng buộc OJT (CON-01 tối đa 3 repo, CON-02 monolith, CON-06 gate architecture, 3 sprint) không cho phép làm hết trong kỳ. PRD vì vậy gắn **tier** cho từng requirement:

| **Tier**            | **Nghĩa**                              | **Phạm vi**                                                                                                                                                                              |
| ------------------- | -------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **T1 — MVP-OJT**    | Bắt buộc hoàn thành trong Sprint 1–3   | Upload → OCR → structure → **exact/structured search** → citation/navigation → finding → HITL → approval; tenant/ACL ở mức đủ để không rò rỉ; audit ở mức subset; lineage bất biến       |
| **T2 — Vision-MVP** | Thuộc MVP của DOC-01 nhưng **sau OJT** | Semantic search, index version & rollback, delete/restore/purge, legal hold, quota/cost governance, query trace, tenant profile đầy đủ, màn quản trị tenant, role Viewer/Auditor/Support |

**Priority đọc trong tier của nó.** "Must" ở một FR tier T2 nghĩa là *bắt buộc khi làm T2*, không phải bắt buộc trong OJT. Đây là điểm v0.10 mâu thuẫn và v0.11 sửa.
Hệ quả bắt buộc: T1 **không được thiết kế theo cách chặn đường T2**. Cụ thể — dữ liệu phải xác định được tenant ngay từ đầu (FR-TEN-01), machine output không bị ghi đè (FR-REV-01), lineage giữ qua rerun (FR-AUD-01). Ba thứ này rẻ khi làm sớm và rất đắt khi vá sau.

> DOC-01 hiện không phân tier. Nếu nhóm chấp nhận cách chia này, **DOC-01 cần thêm một mục "MVP theo giai đoạn"** để không tạo kỳ vọng rằng toàn bộ §4.1 của Vision có mặt trong OJT — xem D-17.

### 3.2 Constraints (ràng buộc đề bài)

| **ID**  | **Ràng buộc**                                                                                                                                    |
| ------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| CON-01  | Chỉ dùng GitHub repo mentor cấp; tối đa 3 repo (BE / FE / AI). Không tự tạo repo                                                                 |
| CON-02  | Một monolith + DDD; không microservices trong OJT                                                                                                |
| CON-03  | Input Sprint 1–3: chỉ PDF, ≤ 50 MB/file. Ảnh JPG/PNG là mở rộng sau                                                                              |
| CON-03b | Ngoài CON-03, phải **công bố giới hạn đã đo** theo pages/document, annexes/dossier, dossiers/batch trong DOC-06. Không tuyên bố giới hạn chưa đo |
| CON-04  | External OCR/AI service baseline = none; đổi provider cần mentor phê duyệt                                                                       |
| CON-05  | Dữ liệu mẫu của mentor không vào repo hay dịch vụ ngoài                                                                                          |
| CON-06  | Không code feature trước khi mentor duyệt architecture + project structure                                                                       |

### 3.3 Out of scope (đồng bộ DOC-01 §4.2)

- Tư vấn pháp lý; kết luận hiệu lực pháp lý, thứ tự ưu tiên tài liệu, điều khoản hiện hành (`candidate_amendment` **không phải** kết luận này)
- Xác minh chữ ký, con dấu, chữ viết tay ngoài khả năng OCR
- Tự động phê duyệt/từ chối hợp đồng hoặc thay thế reviewer
- Chỉnh sửa, redline hoặc tạo lại nội dung PDF gốc
- DOCX, email, ảnh rời hoặc định dạng ngoài PDF (JPG/PNG — D-12)
- Cam kết phát hiện **mọi** conflict thực tế hoặc tự giải quyết conflict
- Chatbot / trợ lý hỏi đáp tổng quát ngoài dossier hoặc không grounded; bounded free-form Q&A trong một dossier, có citation và safe state, là phạm vi AI2 đã được phê duyệt
- Tìm kiếm toàn bộ kho hồ sơ (cross-dossier search)
- External guest, chia sẻ chéo tenant, SSO/SCIM, dedicated storage, customer-managed key, private cloud, on-prem, data residency theo quốc gia
- Template builder trực quan, fine-tuning / custom model riêng từng tenant, tự động học từ dữ liệu tenant khác
- Tự động cấp quyền đọc nội dung cho Tenant Admin hoặc Platform Support vì lý do vai trò quản trị
- Cam kết truy vấn đồng bộ real-time trong lúc upload
- Microservices; Kubernetes; tự tạo GitHub repo; hệ thống quản lý tài liệu doanh nghiệp; enterprise identity management
- Train OCR model hoặc foundation model riêng; app mobile native; hồ sơ FAP / sinh viên
- Cam kết SLA hoặc ngưỡng chất lượng production trước khi có DOC-06

---

# 4. Product Workflow

### 4.1 Bối cảnh tenant

Mọi bước diễn ra trong phạm vi một tenant. Tenant của một request được xác định từ danh tính đã xác thực, không từ dữ liệu do client khai báo (FR-TEN-02).
Tạo tenant → mời thành viên → upload dossier → xác nhận membership/role/relation
→ OCR + dựng cây cấu trúc → sẵn sàng tìm kiếm → tìm kiếm/điều hướng
→ chia sẻ cho reviewer → review/xác nhận → archive hoặc xóa theo policy

### 4.2 Các bước

| **#** | **Bước**          | **Nội dung**                                                                                                                           |
| ----- | ----------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| 1     | Upload            | Operator nạp một hoặc nhiều dossier, nhận định danh dossier + job. Dossier mới private-by-default                                      |
| 2     | Processing        | Xác định loại từng trang (text-layer / scanned / mixed), chọn cách lấy nội dung theo trang                                             |
| 3     | OCR / extraction  | Ghi snapshot bất biến theo schema chuẩn; dựng cây `StructuralNode` và fact typed có citation                                           |
| 4     | Sẵn sàng tìm kiếm | Nội dung mới trở nên tìm kiếm được sau khi xử lý xong. Trong lúc xử lý, kết quả hiện hữu vẫn phục vụ được (FR-IDX-02)                  |
| 5     | Search & navigate | Nhập giá trị hoặc câu hỏi → kết quả kèm citation + bbox + nguồn liên quan. Không đủ evidence → `INSUFFICIENT_EVIDENCE`, không suy đoán |
| 6     | Fact / finding    | AI2 so sánh qua context gate, phát sinh finding với đúng một `model_disposition` và evidence                                           |
| 7     | HITL review       | Ảnh gốc \| text OCR theo trang, bbox highlight, danh sách finding; mỗi thao tác ghi một revision append-only                           |
| 8     | Approval          | Dossier chỉ chuyển `approved` khi reviewer chủ động duyệt                                                                              |
| 9     | Rerun / lineage   | Re-OCR hoặc chạy lại comparison tạo bản xử lý mới; fact, finding và review cũ không bị sửa                                             |

**Ngay sau upload, khi chưa có truy vấn nào**, hệ thống phải hiển thị cây hồ sơ, cây cấu trúc, bảng/row/cell, citation, cảnh báo và relation cần xác nhận (DOC-01 §6.1).
Định tuyến truy vấn theo chi phí:
Exact/keyword → Structured retrieval → Semantic retrieval (T2) → Model reasoning khi retrieval chưa đủ (T2)

### 4.3 Job status lifecycle

uploaded → processing → extracted → indexed → pending_review → reviewed → approved
  └──► failed (kèm lý do; job không bao giờ mất trạng thái)

Điều kiện phái sinh: `extracted → [conflict_detected: chỉ khi tồn tại ≥ 1 finding] → pending_review`

| **Trạng thái**    | **Nghĩa**                                                                                     |
| ----------------- | --------------------------------------------------------------------------------------------- |
| extracted         | Đã có structural node + fact; chưa có kết luận so sánh                                        |
| indexed           | Nội dung đã tìm kiếm được                                                                     |
| conflict_detected | Nhãn phái sinh, không phải chặng bắt buộc. Dossier không có finding đi thẳng `pending_review` |
| pending_review    | Chờ người xử lý                                                                               |
| reviewed          | Reviewer đã xử lý xong các finding đang mở (định nghĩa "xong" — D-03)                         |
| approved          | Reviewer chủ động duyệt dossier                                                               |
| failed            | Có lý do đọc được, không lộ secret                                                            |

Còn mở: D-02 (`conflict_detected` state hay flag), D-03 (`pending_review → approved` trực tiếp), D-18 (`indexed` là state riêng hay thuộc tính).

### 4.4 Data lifecycle (T2)

ACTIVE → SOFT_DELETED → PURGE_PENDING → PURGED

Vòng đời **dữ liệu dossier**, chạy song song và độc lập với vòng đời job. Yêu cầu chi tiết ở §5.13.

---

## 5. Functional Requirements

**Priority:** Must = bắt buộc trong tier của nó · Should = làm khi Must xong và có evidence · Later = ngoài cả hai tier, chỉ giữ chỗ. **Tier:** T1 = MVP-OJT · T2 = Vision-MVP (§3.1).

### 5.A — Core capability

> Khối này là sản phẩm. Nếu cắt scope, cắt từ 5.B trước.

#### 5.1 Upload & dossier — FR-UPL

| **ID**    | **Requirement**                                                                                                           | **Tier** | **Priority** | **Owner**         | **Acceptance**                                                                                                            |
| --------- | ------------------------------------------------------------------------------------------------------------------------- | -------- | ------------ | ----------------- | ------------------------------------------------------------------------------------------------------------------------- |
| FR-UPL-01 | Nạp một dossier gồm 1 hợp đồng + `0..n` phụ lục, trả định danh dossier + job                                              | T1       | Must         | Chương            | Tài liệu trong cùng dossier liên kết logic với nhau                                                                       |
| FR-UPL-02 | Nạp nhiều dossier trong một lần; lỗi một dossier không làm chết cả lô                                                     | T1       | Must         | Chương            | Mỗi dossier có job riêng, lô có tổng kết trạng thái (D-01)                                                                |
| FR-UPL-03 | Thực thi ràng buộc input (CON-03) và tên file Unicode tiếng Việt                                                          | T1       | Must         | Chương            | File quá dung lượng / sai định dạng bị từ chối kèm message, tiến trình không chết; tên file tiếng Việt không lỗi encoding |
| FR-UPL-04 | Vai trò tài liệu (hợp đồng / phụ lục) do sản phẩm xác định, **không suy từ tên file, thứ tự upload hay vị trí trong PDF** | T1       | Must         | Chương + Văn Dũng | Đổi tên file hoặc đảo thứ tự upload không làm đổi vai trò tài liệu                                                        |
| FR-UPL-05 | Manifest/role/relation chưa đủ evidence ở trạng thái `UNKNOWN/NEEDS_REVIEW`, chờ người có thẩm quyền xác nhận             | T1       | Must         | Chương + Đức Dũng | Không có role nào được gán ngầm; UI hiện relation cần xác nhận                                                            |
| FR-UPL-06 | Dossier mới private-by-default với người tạo/nhóm chỉ định                                                                | T1       | Must         | Chương            | Người khác trong cùng tenant không thấy dossier cho tới khi được chia sẻ                                                  |
| FR-UPL-07 | Không tạo dossier trùng khi nạp lại cùng một file                                                                         | T1       | Should       | Chương            | Nếu kịp Sprint 3                                                                                                          |

#### 5.2 Ingestion & OCR — FR-OCR

| **ID**    | **Requirement**                                                                              | **Tier** | **Priority** | **Owner**        | **Acceptance**                                                                                                      |
| --------- | -------------------------------------------------------------------------------------------- | -------- | ------------ | ---------------- | ------------------------------------------------------------------------------------------------------------------- |
| FR-OCR-01 | Xác định loại từng trang (text-layer / scanned / mixed) và chọn cách lấy nội dung theo trang | T1       | Must         | Đức Dũng         | Trang mixed xử lý theo từng trang, không áp một cách cho cả file                                                    |
| FR-OCR-02 | OCR/layout output theo một schema chuẩn dùng chung cho Backend, AI2 và HITL                  | T1       | Must         | Đức Dũng         | Schema mang được text, độ tin cậy, vị trí (word/line), kích thước và chiều trang — ST-017                           |
| FR-OCR-03 | Module phía sau chỉ đọc schema chuẩn, không phụ thuộc engine cụ thể                          | T1       | Must         | Đức Dũng         | Đổi engine không phải sửa structural node / finding / HITL                                                          |
| FR-OCR-04 | Snapshot OCR/layout bất biến, có định danh và đủ provenance để dẫn chứng lại                 | T1       | Must         | Đức Dũng         | AI2 validate được; input thiếu provenance bị coi là thiếu evidence / lỗi integration, không phải fact hợp lệ (D-08) |
| FR-OCR-05 | Giữ đúng dấu tiếng Việt; hỗ trợ trang/tài liệu song ngữ Việt–Anh trong bộ mẫu                | T1       | Must         | Đức Dũng         | Có phép đo riêng về dấu (M-08); **không cam kết production cho mọi ngôn ngữ/font/bố cục song ngữ**                  |
| FR-OCR-06 | Chọn engine dựa trên số đo trên cùng một bộ mẫu, không theo phỏng đoán                       | T1       | Must         | Đức Dũng         | Có bảng so sánh + lý do chọn trong DOC-06                                                                           |
| FR-OCR-07 | Tiền xử lý ảnh chỉ bật khi số đo chứng minh cải thiện                                        | T1       | Should       | Đức Dũng         | Không bật khi chưa có số (D-07)                                                                                     |
| FR-OCR-08 | Đề xuất ngưỡng highlight độ tin cậy thấp dựa trên phân phối điểm thực tế                     | T1       | Should       | Đức Dũng + Trang | Không hard-code ngưỡng trong PRD (D-05)                                                                             |

#### 5.3 Contract structure — FR-CLA

| **ID**    | **Requirement**                                                                                           | **Tier** | **Priority** | **Owner**           | **Acceptance**                                                                        |
| --------- | --------------------------------------------------------------------------------------------------------- | -------- | ------------ | ------------------- | ------------------------------------------------------------------------------------- |
| FR-CLA-01 | Dựng và lưu cây `StructuralNode` với quan hệ cha–con và thứ tự                                            | T1       | Must         | Đức Dũng + Chương   | Quan hệ cha–con đọc lại đúng cấp (D-21)                                               |
| FR-CLA-02 | Phụ lục và bảng giữ dạng có cấu trúc, không dồn thành một khối text                                       | T1       | Must         | Đức Dũng            | Bảng còn phân biệt được hàng/ô; bảng kéo dài nhiều trang vẫn nối đúng                 |
| FR-CLA-03 | Mỗi node truy được về trang và vùng trên tài liệu gốc                                                     | T1       | Must         | Đức Dũng + Chương   | HITL vẽ được vùng node lên ảnh gốc                                                    |
| FR-CLA-04 | Mỗi node giữ **nhãn gốc** + loại chuẩn hóa (nếu nhận diện được) + trạng thái `CONFIRMED` / `NEEDS_REVIEW` | T1       | Must         | Đức Dũng + Văn Dũng | Hợp đồng nước ngoài / tự soạn giữ nguyên cấu trúc gốc, không bị ép về Điều–Khoản–Điểm |
| FR-CLA-05 | Hỗ trợ `UNNUMBERED_BLOCK` cho đoạn không đánh số                                                          | T1       | Must         | Đức Dũng            | Nội dung không đánh số vẫn có citation và vẫn tìm kiếm được                           |
| FR-CLA-06 | Map sang Điều–Khoản–Điểm chỉ khi đủ evidence; thiếu evidence → `NEEDS_REVIEW`, không đoán                 | T1       | Must         | Đức Dũng + Văn Dũng | Đo bằng M-06                                                                          |

#### 5.4 Search — FR-SRCH

| **ID**     | **Requirement**                                                                                          | **Tier** | **Priority** | **Owner**         | **Acceptance**                                                                                    |
| ---------- | -------------------------------------------------------------------------------------------------------- | -------- | ------------ | ----------------- | ------------------------------------------------------------------------------------------------- |
| FR-SRCH-01 | Tìm kiếm exact/keyword trong phạm vi một dossier                                                         | T1       | Must         | Chương            | Tìm đúng giá trị nguyên văn (số tiền, mã số thuế, số hợp đồng)                                    |
| FR-SRCH-02 | Tìm theo cấu trúc và theo trường (ví dụ: "đơn giá trong phụ lục 2")                                      | T1       | Must         | Chương + Văn Dũng | Truy vấn theo trường trả đúng node/ô bảng                                                         |
| FR-SRCH-03 | Kết quả chỉ gồm dossier mà người dùng được cấp quyền; xếp hạng và gợi ý không làm lộ dossier ngoài quyền | T1       | Must         | Chương + Văn Dũng | Bộ test truy cập chéo trả kết quả rỗng, không phải phản hồi phân biệt được "tồn tại nhưng bị cấm" |
| FR-SRCH-04 | Không đủ evidence → `INSUFFICIENT_EVIDENCE` hoặc `NEEDS_REVIEW`, **không suy đoán**                      | T1       | Must         | Văn Dũng + Chương | Có case test truy vấn không có đáp án trong dossier                                               |
| FR-SRCH-05 | Kết quả exact/structured luôn được ưu tiên; kết quả suy diễn không thay thế kết quả nguyên văn           | T1       | Must         | Chương + Văn Dũng | Truy vấn có đáp án nguyên văn luôn trả đáp án đó ở vị trí đầu                                     |
| FR-SRCH-06 | Chi phí xử lý một truy vấn không tăng theo toàn bộ kích thước dossier                                    | T1       | Should       | Chương            | Đo thời gian/chi phí truy vấn trên dossier nhỏ và dossier lớn nhất trong bộ mẫu                   |
| FR-SRCH-07 | Tìm kiếm ngữ nghĩa cho cách diễn đạt khác nguyên văn                                                     | **T2**   | Must         | Văn Dũng          | Không được ghi đè hoặc xếp trên kết quả exact/structured (D-09, D-17)                             |
| FR-SRCH-08 | Cho phép câu hỏi tự do trong một dossier contract + annex, qua bounded retrieval và grounding                         | T1       | Must         | Văn Dũng          | Câu trả lời có citation/trace; ngoài scope hoặc thiếu evidence → `INSUFFICIENT_EVIDENCE`/`NEEDS_REVIEW` |

#### 5.5 Navigation & citation — FR-NAV

| **ID**    | **Requirement**                                                                    | **Tier** | **Priority** | **Owner**         | **Acceptance**                                                     |
| --------- | ---------------------------------------------------------------------------------- | -------- | ------------ | ----------------- | ------------------------------------------------------------------ |
| FR-NAV-01 | Từ kết quả mở đúng file → trang → node/bảng → vùng highlight trên bản gốc          | T1       | Must         | Trang + Chương    | Một thao tác tới đúng vị trí                                       |
| FR-NAV-02 | Hiển thị **nguồn liên quan** (phụ lục/điều khoản có relation với kết quả đang xem) | T1       | Must         | Trang + Văn Dũng  | Relation chưa xác nhận hiện rõ là chưa xác nhận                    |
| FR-NAV-03 | Citation resolve được tới document → page → line → span → bbox                     | T1       | Must         | Đức Dũng + Chương | Citation không resolve được không được dùng để khẳng định (NFR-01) |

#### 5.6 Finding & conflict detection — FR-FIND

| **ID**     | **Requirement**                                                                                                                                                           | **Tier** | **Priority** | **Owner**            | **Acceptance**                                                                                   | **ID cũ**     |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | ------------ | -------------------- | ------------------------------------------------------------------------------------------------ | ------------- |
| FR-FIND-01 | Chỉ nhận snapshot đủ provenance để dẫn chứng; input thiếu bị phản ánh là thiếu evidence hoặc lỗi integration                                                              | T1       | Must         | Văn Dũng             | Không coi input thiếu là fact đủ chứng cứ                                                        | PRD-AI2-FR-01 |
| FR-FIND-02 | Trích fact typed (giá, số lượng, ngày, thời hạn, bên, MST, số hợp đồng tham chiếu) với raw, normalized + lý do khi không chuẩn hóa được, business role, context, citation | T1       | Must         | Văn Dũng             | Giá trị không đọc được / ngày mơ hồ để normalized rỗng kèm lý do, không đoán                     | PRD-AI2-FR-02 |
| FR-FIND-03 | Context gate: chỉ so sánh khi role, subject, đơn vị, tiền tệ, cơ sở VAT, scope và hiệu lực áp dụng phù hợp                                                                | T1       | Must         | Văn Dũng             | Không đủ ngữ cảnh → `not_comparable`; thiếu evidence → `insufficient_evidence`; mapping ở ST-016 | PRD-AI2-FR-03 |
| FR-FIND-04 | Mỗi finding mang đúng một `model_disposition` (§5.6.1)                                                                                                                    | T1       | Must         | Văn Dũng             | `finding_type` chỉ nêu chiều kiểm tra, không thay disposition                                    | PRD-AI2-FR-04 |
| FR-FIND-05 | `candidate_amendment` chỉ phát sinh khi giá trị khác nhau, cùng subject/scope phù hợp, có tham chiếu và câu sửa đổi rõ, và ngày hiệu lực mới muộn hơn                     | T1       | Must         | Văn Dũng             | Thiếu câu sửa đổi nhưng đủ ngữ cảnh và giá trị khác vẫn chỉ là `comparable_difference`           | PRD-AI2-FR-05 |
| FR-FIND-06 | So sánh ngữ nghĩa dựa trên biểu diễn nội dung điều khoản; từ khóa phủ định đơn lẻ không đủ để kết luận                                                                    | T1       | Must         | Văn Dũng             | Kết quả là candidate kỹ thuật, không phải kết luận (D-09)                                        | PRD-AI2-FR-06 |
| FR-FIND-07 | Mọi fact/finding dùng để so sánh phải dẫn được về nguồn; finding cross-document có evidence hai phía                                                                      | T1       | Must         | Văn Dũng + AI1/BE/FE | Citation không resolve được thì không dùng để khẳng định; evidence thiếu phải hiện rõ            | PRD-AI2-FR-07 |
| FR-FIND-08 | Finding hiển thị cho reviewer là **candidate**; quyền kết luận thuộc reviewer                                                                                             | T1       | Must         | Văn Dũng + Trang     | UI không trình bày finding như kết luận pháp lý                                                  | Mục 1 AI2     |
| FR-FIND-09 | Demo end-to-end tối thiểu: 1 hợp đồng + 1 phụ lục, hiển thị candidate difference/conflict để reviewer kiểm tra                                                            | T1       | Must         | Văn Dũng + Trang     | DOC-01 §4.1                                                                                      | —             |

##### 5.6.1 `model_disposition`

| **Disposition**       | **Nghĩa**                                                                |
| --------------------- | ------------------------------------------------------------------------ |
| comparable_match      | Đủ ngữ cảnh, giá trị khớp                                                |
| comparable_difference | Đủ ngữ cảnh, giá trị khác, chưa đủ điều kiện amendment                   |
| candidate_amendment   | Candidate kỹ thuật theo FR-FIND-05; không phải kết luận hiệu lực pháp lý |
| not_comparable        | Context gate không cho phép so sánh                                      |
| insufficient_evidence | Thiếu ngữ cảnh hoặc evidence cần thiết                                   |

Mapping đầy đủ disposition ↔ case C01–C15 × 2 representations: ST-016.

##### 5.6.2 Ba lớp trạng thái — không được gộp

| **Lớp**                    | **Giá trị**                                                                                                       | **Ai đặt**          |
| -------------------------- | ----------------------------------------------------------------------------------------------------------------- | ------------------- |
| Finding                    | `comparable_match` / `comparable_difference` / `candidate_amendment` / `not_comparable` / `insufficient_evidence` | AI2                 |
| Query / result             | `ANSWERED` / `INSUFFICIENT_EVIDENCE` / `FAILED` / `RATE_LIMITED`                                                  | Query orchestrator  |
| Node / document / relation | `CONFIRMED` / `NEEDS_REVIEW` / `UNKNOWN`                                                                          | Pipeline + reviewer |

Một query trả `ANSWERED` vẫn có thể chứa finding `insufficient_evidence`, và ngược lại.

#### 5.7 Human-in-the-loop review — FR-HITL

| **ID**     | **Requirement**                                                                                                                           | **Tier** | **Priority**      | **Owner**      | **Acceptance**                                                             |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------------------- | -------- | ----------------- | -------------- | -------------------------------------------------------------------------- |
| FR-HITL-01 | Đối chiếu hai cột: ảnh/PDF gốc \| text OCR (hoặc node đang chọn), theo từng trang                                                         | T1       | Must              | Trang          | Đổi trang hai cột vẫn khớp                                                 |
| FR-HITL-02 | Highlight vùng trên ảnh gốc, ưu tiên vùng độ tin cậy thấp                                                                                 | T1       | Must              | Trang          | Vùng vẽ đúng vị trí                                                        |
| FR-HITL-03 | Trang xoay 90°/180° hiển thị đúng chiều                                                                                                   | T1       | Must              | Trang          | Không lệch vùng highlight khi xoay                                         |
| FR-HITL-04 | Sửa tay text/node và lưu                                                                                                                  | T1       | Must              | Trang          | Mỗi lần sửa sinh revision (FR-REV-01)                                      |
| FR-HITL-05 | Panel finding: danh sách, bấm vào nhảy đúng chỗ dẫn chứng; finding cross-document mở cả hai nguồn                                         | T1       | Must              | Trang          | Một thao tác tới đúng nguồn                                                |
| FR-HITL-06 | Desktop dùng tốt, tablet đọc được                                                                                                         | T1       | Must              | Trang          | Mobile native ngoài phạm vi                                                |
| FR-HITL-07 | **Sau upload, chưa cần đặt câu hỏi**, UI vẫn hiển thị cây hồ sơ, cây cấu trúc, bảng/row/cell, citation, cảnh báo và relation cần xác nhận | T1       | Must              | Trang + Chương | Màn dossier dùng được khi chưa có truy vấn nào                             |
| FR-HITL-08 | Ô tìm kiếm trong phạm vi dossier, kết quả kèm nguồn và mở được citation                                                                   | T1       | Must              | Trang + Chương | Từ ô tìm kiếm tới đúng trang/vùng trong ≤ 1 thao tác                       |
| FR-HITL-09 | Từ một giá trị (tiền / ngày / tên bên) nhảy về vùng nguồn                                                                                 | T1       | Should            | Trang          | —                                                                          |
| FR-HITL-10 | Kéo–thả nhiều PDF cho một dossier hoặc một lô                                                                                             | T1       | Should            | Trang + Chương | Theo mô hình batch đã chốt (D-01)                                          |
| FR-HITL-11 | Reviewer điều chỉnh/vẽ lại vùng dẫn chứng, vùng sau chỉnh được lưu vào kết quả review                                                     | T1       | Should (Sprint 3) | Trang + Chương | Bbox máy và bbox reviewer là hai lớp lịch sử riêng; không mất citation gốc |

#### 5.8 Review & revision — FR-REV

| **ID**    | **Requirement**                                                                                   | **Tier**     | **Priority** | **Owner**                                | **Acceptance**                                                                                                    |
| --------- | ------------------------------------------------------------------------------------------------- | ------------ | ------------ | ---------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| FR-REV-01 | Review lưu append-only, không ghi đè output máy                                                   | T1           | Must         | Chương (thực thi) · Văn Dũng (semantics) | Chưa có revision → trạng thái là chưa review; mỗi revision giữ người, thời điểm, lý do và liên kết revision trước |
| FR-REV-02 | Reviewer **xác nhận** kết quả hoặc gắn `NEEDS_REVIEW`                                             | T1           | Must         | Trang + Chương + Văn Dũng                | Hai thao tác này đủ cho luồng T1 (D-15)                                                                           |
| FR-REV-03 | Reviewer **báo lỗi citation** trên một kết quả/finding                                            | T1           | Must         | Trang + Chương                           | Ghi nhận theo query / dossier / document / bản xử lý                                                              |
| FR-REV-04 | Thao tác `correct` (sửa giá trị trích xuất), `reject` finding, `needs-more-evidence`              | **Chờ D-15** | —            | Trang + Chương + Văn Dũng                | DOC-01 §4.3 xếp giai đoạn sau; PRD v0.9 để Must. **Không code trước khi D-15 chốt**                               |
| FR-REV-05 | Hai reviewer thao tác trên cùng một mốc review không được ghi đè nhau                             | T1           | Must         | Chương                                   | Xung đột buộc đồng bộ lại, không lấy bản ghi sau cùng                                                             |
| FR-REV-06 | Sửa dữ liệu không làm mất liên kết tới nguồn gốc                                                  | T1           | Must         | Chương + Văn Dũng                        | Giữ được cả giá trị máy, giá trị đã sửa và dẫn chứng                                                              |
| FR-REV-07 | Feedback loop cải thiện rule/profile/model: `REPORTED → TRIAGED → VERIFIED → APPLIED \| REJECTED` | Later        | —            | —                                        | PRD chỉ ràng buộc: không auto-retrain từ một report đơn lẻ; không ghi đè machine output                           |

#### 5.9 Approval & job — FR-APR, FR-JOB

| **ID**    | **Requirement**                                                                 | **Tier** | **Priority** | **Owner**      | **Acceptance**                                  |
| --------- | ------------------------------------------------------------------------------- | -------- | ------------ | -------------- | ----------------------------------------------- |
| FR-APR-01 | Dossier chỉ chuyển `approved` khi reviewer chủ động duyệt                       | T1       | Must         | Chương + Trang | Hệ thống không tự duyệt (D-03)                  |
| FR-APR-02 | Trạng thái dossier phản ánh đúng lifecycle §4.3, kể cả khi không có finding     | T1       | Must         | Chương         | Dossier không có finding không bị kẹt (D-02)    |
| FR-JOB-01 | Operator tra được trạng thái job theo định danh                                 | T1       | Must         | Chương         | Trả đúng trạng thái §4.3                        |
| FR-JOB-02 | Job lỗi có trạng thái và lý do; không biến mất                                  | T1       | Must         | Chương         | Lý do đủ để lần nguyên nhân, không lộ secret    |
| FR-JOB-03 | Xử lý là bất đồng bộ; không cam kết truy vấn đồng bộ real-time trong lúc upload | T1       | Must         | Chương         | UI hiển thị trạng thái rõ ràng thay vì chờ khóa |
| FR-JOB-04 | Lô có tổng kết: xong / lỗi / chờ review                                         | T1       | Should       | Chương         | D-01                                            |
| FR-JOB-05 | Chạy lại job lỗi không cần nạp lại file                                         | T1       | Should       | Chương         | —                                               |

### 5.B — Platform capability

> Khối này làm sản phẩm dùng được trong môi trường doanh nghiệp. Phần lớn là T2; phần T1 ở đây là **mức tối thiểu để T2 không phải làm lại từ đầu** (§3.1).

#### 5.10 Tenant & access control — FR-TEN

| **ID**    | **Requirement**                                                                                                                 | **Tier** | **Priority** | **Owner**         | **Acceptance**                                                                                                         |
| --------- | ------------------------------------------------------------------------------------------------------------------------------- | -------- | ------------ | ----------------- | ---------------------------------------------------------------------------------------------------------------------- |
| FR-TEN-01 | Mọi dữ liệu do hệ thống tạo ra thuộc về đúng một tenant và xác định được tenant đó ở mọi nơi hệ thống lưu trữ hoặc đánh chỉ mục | T1       | Must         | Chương            | Không tồn tại bản ghi, file hay mục chỉ mục nào không xác định được tenant. *Cơ chế (cột, prefix, namespace) → DOC-04* |
| FR-TEN-02 | Tenant của một request được xác định từ danh tính đã xác thực, không từ dữ liệu do client khai báo                              | T1       | Must         | Chương            | Request khai báo tenant khác với danh tính bị từ chối và được ghi nhận                                                 |
| FR-TEN-03 | Kiểm tra quyền trên dossier trước khi đọc / tải / chia sẻ / xóa                                                                 | T1       | Must         | Chương            | Ma trận quyền kiểm thử đạt; thu hồi quyền có hiệu lực ngay, đường truy cập đã cấp trước đó không còn dùng được         |
| FR-TEN-04 | Quyền quản trị tenant **không mặc định** kèm quyền đọc nội dung                                                                 | T1       | Must         | Chương            | Tenant Admin không đọc được dossier chưa được cấp                                                                      |
| FR-TEN-05 | Không ai suy ra được sự tồn tại của dossier ngoài quyền của mình qua kết quả tìm kiếm, số lượng hay tên file                    | T1       | Must         | Chương + Văn Dũng | Đo bằng M-07, ngưỡng 0                                                                                                 |
| FR-TEN-06 | Dữ liệu tenant này không dùng để train/cải thiện model cho tenant khác nếu chưa opt-in                                          | T1       | Must         | Văn Dũng + Mentor | Ràng buộc policy; kiểm chứng bằng cấu hình pipeline (CON-04, CON-05)                                                   |
| FR-TEN-07 | Vai trò Viewer / Auditor và màn quản trị tenant (thành viên, policy, chia sẻ)                                                   | T2       | Must         | Chương + Trang    | D-23                                                                                                                   |
| FR-TEN-08 | Nhân sự vận hành nền tảng không có quyền mặc định; truy cập ngoại lệ cần phê duyệt, có thời hạn và để lại dấu vết               | T2       | Should       | Chương + Mentor   | Không có đường vào mặc định                                                                                            |

#### 5.11 Bản xử lý & khả năng phục vụ liên tục — FR-IDX

| **ID**    | **Requirement**                                                                   | **Tier** | **Priority** | **Owner**         | **Acceptance**                                                                         |
| --------- | --------------------------------------------------------------------------------- | -------- | ------------ | ----------------- | -------------------------------------------------------------------------------------- |
| FR-IDX-01 | Trong lúc hệ thống đang xử lý lại một dossier, kết quả hiện hữu vẫn tìm kiếm được | T1       | Should       | Chương            | Rebuild không làm search trả rỗng hoặc lỗi                                             |
| FR-IDX-02 | Kết quả tìm kiếm không bao giờ trộn giữa hai lần xử lý khác nhau                  | T1       | Must         | Chương            | Kill job giữa chừng: search trả toàn bộ kết quả của lần xử lý trước, không trả hỗn hợp |
| FR-IDX-03 | Upload/update sinh một bản xử lý mới có định danh và trạng thái                   | T2       | Must         | Chương            | D-18                                                                                   |
| FR-IDX-04 | Job lỗi không làm mất kết quả đang phục vụ; hỗ trợ chạy lại và quay về bản trước  | T2       | Must         | Chương            | Đo bằng M-10                                                                           |
| FR-IDX-05 | Một bản xử lý tái lập được: biết nó dựa trên snapshot, profile và policy nào      | T2       | Must         | Chương + Văn Dũng | ST-017                                                                                 |

#### 5.12 Audit & lineage — FR-AUD, FR-EVAL

| **ID**     | **Requirement**                                                                                                                                 | **Tier** | **Priority** | **Owner**                    | **Acceptance**                                           | **ID cũ**     |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------- | -------- | ------------ | ---------------------------- | -------------------------------------------------------- | ------------- |
| FR-AUD-01  | Re-OCR / rerun giữ lineage bất biến; bản xử lý mới không sửa fact, finding, review cũ                                                           | T1       | Must         | Đức Dũng + Văn Dũng + Chương | Finding cross-document liệt kê mọi nguồn đầu vào         | PRD-AI2-FR-09 |
| FR-AUD-02  | Luôn phân biệt được output máy và phần người đã sửa/xác nhận                                                                                    | T1       | Must         | Chương + Trang               | Output máy không bị overwrite âm thầm                    | —             |
| FR-AUD-03  | Lịch sử thao tác chỉ ghi thêm, không sửa, không xóa; không chứa nội dung hợp đồng                                                               | T1       | Must         | Chương                       | Kiểm tra mẫu: không tìm thấy nội dung hợp đồng trong log | <br>          |
| FR-AUD-04  | Không có đường nào trong sản phẩm cho phép sửa hoặc xóa machine output và lịch sử thao tác                                                      | T1       | Must         | Chương                       | Rà soát mọi surface của sản phẩm                         | <br>          |
| FR-AUD-05  | Tập sự kiện tối thiểu T1: upload, xử lý, xem, tải, sửa node, xác nhận, báo lỗi citation, gắn `NEEDS_REVIEW`, re-OCR/rerun, duyệt dossier        | T1       | Must         | Chương                       | Có expected event ledger để đo M-09                      | <br>          |
| FR-AUD-06  | Mỗi sự kiện tối thiểu có: ai, tenant, dossier, thời điểm, hành động, kết quả, lý do và định danh để lần lại job/request                         | T1       | Must         | Chương                       | Event thiếu trường bắt buộc bị coi là lỗi                | <br>          |
| FR-AUD-07  | Tập sự kiện đầy đủ (login/failed login, export, chia sẻ, thu hồi quyền, xóa, restore, purge, thay đổi policy/ACL/legal hold, truy cập ngoại lệ) | T2       | Must         | Chương                       | DOC-01 §7.3                                              | <br>          |
| FR-EVAL-01 | Ghi đủ metadata để audit và đánh giá: phiên bản nguồn/rule/gold, representation, số lượng, mục thiếu/lỗi/chưa chạy, liên kết đối chiếu          | T1       | Must         | Văn Dũng                     | Metric chỉ chạy sau Gate B với nguồn và đối chiếu thật   | PRD-AI2-FR-10 |
| FR-EVAL-02 | Mỗi số đo công bố kèm `n`, tên bộ mẫu và điều kiện chạy                                                                                         | T1       | Must         | Đức Dũng + Văn Dũng          | Không công bố số trần                                    | —             |

#### 5.13 Vòng đời dữ liệu — FR-LCM *(toàn bộ T2)*

| **ID**    | **Requirement**                                                                                                | **Tier** | **Priority** | **Owner**         | **Acceptance**                                                                                        |
| --------- | -------------------------------------------------------------------------------------------------------------- | -------- | ------------ | ----------------- | ----------------------------------------------------------------------------------------------------- |
| FR-LCM-01 | Xóa dossier là xóa mềm: biến khỏi UI/search, thu hồi quyền và mọi đường truy cập đã cấp, dừng job đang chạy    | T2       | Must         | Chương            | Sau khi xóa, search và mọi surface đều không trả dossier                                              |
| FR-LCM-02 | Khôi phục toàn bộ dossier như một aggregate trong 30 ngày mặc định                                             | T2       | Must         | Chương            | Restore giữ PDF, OCR, cây cấu trúc, citation và review history                                        |
| FR-LCM-03 | Restore **không** tự cấp lại quyền cho user đã bị xóa khỏi tenant                                              | T2       | Must         | Chương            | Kiểm thử quyền sau restore                                                                            |
| FR-LCM-04 | Restore không tự chạy lại OCR; nếu cần phải tạo re-OCR/rerun mới                                               | T2       | Must         | Chương + Đức Dũng | Không sinh bản xử lý ngầm                                                                             |
| FR-LCM-05 | Sau thời gian khôi phục, nội dung dossier không còn tồn tại ở bất kỳ nơi nào sản phẩm đã lưu hoặc đánh chỉ mục | T2       | Must         | Chương            | Kiểm thử không truy xuất được nội dung qua bất kỳ surface nào sau purge. *Danh sách nơi lưu → DOC-04* |
| FR-LCM-06 | Legal hold chặn purge cho tới khi được gỡ; trạng thái hiển thị rõ cho Tenant Admin                             | T2       | Should       | Chương            | Purge bị từ chối kèm lý do                                                                            |
| FR-LCM-07 | Lịch sử thao tác được giữ sau purge (mặc định 12 tháng hoặc theo policy), không chứa nội dung                  | T2       | Must         | Chương            | Chứng minh được lịch sử sau khi nội dung đã xóa                                                       |

#### 5.14 Chi phí truy vấn & query trace — FR-COST *(toàn bộ T2)*

| **ID**     | **Requirement**                                                                                                       | **Tier** | **Priority** | **Owner**         | **Acceptance**                                                                      |
| ---------- | --------------------------------------------------------------------------------------------------------------------- | -------- | ------------ | ----------------- | ----------------------------------------------------------------------------------- |
| FR-COST-01 | Chỉ dùng tới model AI khi các cách tìm kiếm rẻ hơn chưa đủ trả lời                                                    | T2       | Must         | Chương + Văn Dũng | Truy vấn có đáp án nguyên văn không phát sinh model call                            |
| FR-COST-02 | Truy vấn lặp lại có thể được phục vụ lại, nhưng không bao giờ trả kết quả của tenant khác hoặc của lần xử lý đã cũ    | T2       | Should       | Chương            | Test phục vụ lại sau khi dossier được xử lý lại: kết quả phải là bản mới            |
| FR-COST-03 | Giới hạn sử dụng theo user, tenant, loại truy vấn và khoảng thời gian                                                 | T2       | Should       | Chương            | Vượt giới hạn trả `RATE_LIMITED`; hệ thống không thử lại vô hạn                     |
| FR-COST-04 | Giới hạn sử dụng có hiệu lực đồng nhất trên mọi đường vào sản phẩm                                                    | T2       | Must         | Chương            | Không có surface nào cho phép vượt giới hạn                                         |
| FR-COST-05 | Theo dõi mức sử dụng và chi phí theo user và tenant                                                                   | T2       | Should       | Chương            | Đo bằng M-11                                                                        |
| FR-COST-06 | Mỗi truy vấn để lại bản ghi: ai, hỏi gì, trả gì, citation nào, trạng thái gì, dựa trên bản xử lý và model version nào | T2       | Must         | Chương + Văn Dũng | Trạng thái tối thiểu: `ANSWERED`, `INSUFFICIENT_EVIDENCE`, `FAILED`, `RATE_LIMITED` |
| FR-COST-07 | Bản ghi truy vấn chịu cùng quyền truy cập và cùng chính sách lưu trữ như nội dung                                     | T2       | Must         | Chương            | User không xem được bản ghi ngoài quyền                                             |

#### 5.15 Tenant profile & template — FR-PROF

| **ID**     | **Requirement**                                                                                                                | **Tier** | **Priority** | **Owner**           | **Acceptance**                                                 |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------ | -------- | ------------ | ------------------- | -------------------------------------------------------------- |
| FR-PROF-01 | Template không nhận diện được → `UNKNOWN/NEEDS_REVIEW`; không suy role từ filename, upload order hay vị trí cố định            | T1       | Must         | Đức Dũng + Văn Dũng | Đo bằng M-06; liên kết FR-UPL-04                               |
| FR-PROF-02 | Cấu hình tenant chỉ hỗ trợ diễn giải/chỉ mục, **không thay thế evidence** trên tài liệu gốc                                    | T1       | Must         | Văn Dũng            | Không có giá trị nào chỉ dựa vào cấu hình mà không có citation |
| FR-PROF-03 | Một kết quả luôn cho biết nó được tạo ra dưới cấu hình tenant nào                                                              | T1       | Should       | Chương              | Đổi cấu hình không làm mất khả năng tái lập kết quả cũ         |
| FR-PROF-04 | Tenant cấu hình được document type, alias nghiệp vụ, taxonomy điều khoản, trường tùy chỉnh, quy tắc hiển thị/chia sẻ/retention | T2       | Must         | Chương + Văn Dũng   | D-21                                                           |
| FR-PROF-05 | Đổi cấu hình tạo bản xử lý mới, giữ nguyên citation, machine output và review history cũ                                       | T2       | Must         | Chương + Văn Dũng   | Không ghi đè lịch sử                                           |

---

## 6. UX Requirements

| **Màn**                | **Nội dung tối thiểu**                                                                                                                 | **Tier** | **Owner**        |
| ---------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | -------- | ---------------- |
| 6.1 Danh sách job      | Dossier, trạng thái theo §4.3, lý do khi lỗi                                                                                           | T1       | Trang            |
| 6.2 Dossier overview   | Cây hồ sơ + cây cấu trúc + bảng + relation cần xác nhận, dùng được **khi chưa có truy vấn nào**                                        | T1       | Trang            |
| 6.3 Tìm kiếm & kết quả | Ô tìm kiếm trong dossier, kết quả kèm nguồn, trạng thái `INSUFFICIENT_EVIDENCE`, mở citation                                           | T1       | Trang            |
| 6.4 Chi tiết trang     | Ảnh gốc \| text OCR theo trang, highlight vùng, điều hướng trang, xử lý trang xoay                                                     | T1       | Trang            |
| 6.5 Sửa node           | Sửa text/node, lưu, thấy được lần sửa trước                                                                                            | T1       | Trang            |
| 6.6 Panel finding      | Danh sách finding, disposition, nhảy tới dẫn chứng hai phía, xác nhận / `NEEDS_REVIEW` / báo lỗi citation, chỗ đánh dấu thiếu evidence | T1       | Trang + Văn Dũng |
| 6.7 Quản trị tenant    | Thành viên, quyền, policy, legal hold, dossier đã xóa                                                                                  | T2       | Trang + Chương   |

**Ràng buộc thiết bị:** desktop đầy đủ, tablet đọc được, không app native.
Sprint 1 chỉ cần wireframe/mockup; UI thật từ Sprint 2. Wireframe phải ghi rõ chỗ nào chờ dữ liệu từ Backend (trạng thái, kết quả tìm kiếm, payload review, sửa node, xử lý finding, duyệt dossier).

---

## 7. Non-functional Requirements

| **ID** | **Hạng mục**               | **Requirement**                                                                                                                                | **Tier** |
| ------ | -------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| NFR-01 | Provenance                 | Bản OCR thô bất biến; mọi giá trị dẫn được về tài liệu → trang → dòng → đoạn ký tự → vùng. Quy ước offset và hệ tọa độ: ST-017                 | T1       |
| NFR-02 | Explainability             | Finding luôn mang hai fact refs + lý do/disposition; evidence thiếu hoặc lỗi phải nhìn thấy được, không im lặng bỏ qua                         | T1       |
| NFR-03 | Reproducibility            | Giữ đủ phiên bản để dựng lại kết quả của một lần chạy                                                                                          | T1       |
| NFR-04 | Concurrency                | Thao tác review đồng thời không mất dữ liệu (FR-REV-05)                                                                                        | T1       |
| NFR-05 | Failure handling           | File sai / quá dung lượng không làm sập tiến trình; job luôn có trạng thái cuối kèm lý do                                                      | T1       |
| NFR-06 | Data handling              | Theo CON-04, CON-05; dữ liệu được bảo vệ khi truyền và khi lưu; log vận hành không chứa nội dung hợp đồng                                      | T1       |
| NFR-07 | Quality measurement policy | Chưa cam kết latency, throughput, cost, accuracy, availability, chất lượng đa ngữ/scan hay production readiness cho tới khi có số trong DOC-06 | T1       |
| NFR-08 | Evidence quản trị          | Mọi task Done trên tracker có link PR / commit / doc                                                                                           | T1       |
| NFR-09 | Tenant isolation           | Không tồn tại đường nào trả dữ liệu ngoài tenant/ACL. Ngưỡng M-07 = 0                                                                          | T1       |
| NFR-10 | Least privilege            | Quyền xem / sửa / tải / chia sẻ / xóa kiểm soát riêng; vai trò quản trị không kèm quyền đọc nội dung                                           | T1       |
| NFR-11 | Search continuity          | Việc xử lý lại một dossier không làm gián đoạn khả năng tìm kiếm trên kết quả hiện hữu                                                         | T1       |
| NFR-12 | Recoverability             | Xóa nhầm khôi phục được trong thời hạn; purge chỉ sau thời gian chờ và bị chặn khi có legal hold                                               | T2       |
| NFR-13 | Cost predictability        | Truy vấn bất thường hoặc thử lại liên tục không làm chi phí tăng không kiểm soát                                                               | T2       |

---

## 8. Integration & API Surface

| **Hướng**          | **Nội dung trao đổi**                                                                                | **Chốt chi tiết tại** |
| ------------------ | ---------------------------------------------------------------------------------------------------- | --------------------- |
| AI1 → Backend      | Snapshot OCR/layout bất biến theo schema chuẩn, đủ provenance                                        | ST-017, DOC-04        |
| Backend → AI2      | Thành phần dossier, vai trò tài liệu, snapshot đã xác định                                           | ST-022                |
| AI2 → Backend      | Fact, finding, disposition, evidence hai phía, metadata audit                                        | ST-017                |
| Backend → Frontend | Payload review, kết quả tìm kiếm, danh sách finding, dẫn chứng để highlight, kết quả thao tác review | DOC-05                |

**Capability cần có** (đường dẫn, envelope và schema do DOC-05 chốt): nạp một/nhiều dossier · xác nhận manifest và vai trò tài liệu · tra trạng thái job · lấy cây hồ sơ và cây cấu trúc khi chưa có truy vấn · tìm kiếm trong dossier · lấy kết quả node kèm dẫn chứng · lấy danh sách finding · lấy payload màn review · sửa node · thao tác review · duyệt dossier · chia sẻ và thu hồi quyền. T2 bổ sung: xóa/khôi phục dossier, truy vấn lịch sử thao tác và bản ghi truy vấn.
Tên surface ("conflicts" vs "findings") và cách map thao tác review vào API: **D-04**.

---

## 9. Domain Model & Invariants

Sơ đồ quan hệ ở mức cao; schema chi tiết (field, kiểu, offset, hệ tọa độ, digest) thuộc **ST-017**; lưu trữ vật lý thuộc **DOC-04**.
Tenant
 └── Dossier  (ACL, lifecycle)
      ├── Document
      │    ├── Snapshot (bất biến)
      │    ├── StructuralNode ──► Citation
      │    └── Table / Row / Cell
      ├── Fact ──► Citation
      ├── Finding (2 fact refs) ──► Evidence
      └── ReviewRevision (append-only)

Invariant cắt ngang nhiều FR — vi phạm bất kỳ dòng nào là lỗi, không phải lựa chọn thiết kế:

| **ID** | **Invariant**                                                                                              | **Tier** |
| ------ | ---------------------------------------------------------------------------------------------------------- | -------- |
| DC-01  | Một dossier = 1 hợp đồng + `0..n` phụ lục, thuộc đúng một tenant; vai trò tài liệu do sản phẩm xác định    | T1       |
| DC-02  | Mọi dữ liệu do hệ thống tạo ra xác định được tenant sở hữu                                                 | T1       |
| DC-03  | Mọi fact và finding dẫn được về nguồn ở mức document → page → line → span → vùng vẽ được                   | T1       |
| DC-04  | Machine output không bị ghi đè; review là lớp riêng, append-only, giữ người/thời điểm/lý do/liên kết trước | T1       |
| DC-05  | Snapshot và bản xử lý là bất biến; lineage giữ qua rerun                                                   | T1       |
| DC-06  | Mỗi lần xử lý biết nó chạy trên dossier nào, manifest nào, cấu hình và policy phiên bản nào                | T1       |
| DC-07  | Lịch sử thao tác chỉ ghi thêm và không chứa nội dung hợp đồng                                              | T1       |
| DC-08  | Dossier có vòng đời `ACTIVE → SOFT_DELETED → PURGE_PENDING → PURGED` với retention policy và legal hold    | T2       |
| DC-09  | Mỗi truy vấn để lại bản ghi chịu cùng quyền truy cập như nội dung                                          | T2       |

---

## 10. Assumptions

| **ID** | **Assumption**                                                                           | **Sai thì ảnh hưởng**   | **Kiểm chứng ở**        |
| ------ | ---------------------------------------------------------------------------------------- | ----------------------- | ----------------------- |
| A-01   | Reviewer / legal operations là người dùng chính, không phải lãnh đạo hay kế toán         | Toàn bộ §2, §6          | Phỏng vấn / DOC-01 §9.3 |
| A-02   | Đơn vị tìm kiếm là một dossier, không phải toàn bộ kho tài liệu                          | §1.3, FR-SRCH           | DOC-01 §9.1             |
| A-03   | Input MVP chỉ là PDF (scan và text layer)                                                | CON-03, FR-OCR-01       | D-12                    |
| A-04   | Reviewer có quyền truy cập bản gốc để đối chiếu                                          | FR-HITL-01, G2          | —                       |
| A-05   | Reviewer là người chịu trách nhiệm cuối; hệ thống không kết luận pháp lý                 | G4, FR-FIND-08          | DOC-01 §3.2             |
| A-06   | Bộ mẫu ≥ 30 hợp đồng đủ đại diện để benchmark OCR và đo Recall\@k                        | DOC-06, M-02, M-08      | Gate B                  |
| A-07   | Quan hệ hợp đồng–phụ lục xác định được từ nội dung hoặc manifest, không phải từ tên file | FR-UPL-04, FR-UPL-05    | D-11                    |
| A-08   | Baseline thủ công đo được trên cùng dossier với cùng reviewer                            | M-01, M-04              | DOC-06                  |
| A-09   | Architecture được mentor duyệt trước Sprint 2                                            | Toàn bộ lịch trình      | CON-06                  |
| A-10   | Không dùng external OCR/AI service trong OJT (baseline none)                             | FR-COST toàn bộ, CON-04 | D-13                    |

---

## 11. Dependencies

| **ID** | **Dependency**                                                          | **Cần cho**                               | **Trạng thái**       |
| ------ | ----------------------------------------------------------------------- | ----------------------------------------- | -------------------- |
| DEP-01 | DOC-01 Product Vision được xác nhận (và bổ sung mục MVP theo giai đoạn) | Ranh giới §3.1                            | Draft, chưa sign-off |
| DEP-02 | Mentor duyệt architecture + project structure                           | Mọi code Sprint 2 (CON-06)                | Chưa                 |
| DEP-03 | DOC-04 Architecture                                                     | D-02, D-03, D-10, D-11, D-18              | Chưa                 |
| DEP-04 | DOC-05 API Spec                                                         | D-01, D-04, D-12                          | Nháp Sprint 1        |
| DEP-05 | ST-017 Data Contract                                                    | FR-OCR-02/04, FR-CLA, FR-FIND, D-08, D-21 | Nháp Sprint 1        |
| DEP-06 | ST-016 Case Catalog C01–C15 × 2 representations                         | FR-FIND-03/04, mapping disposition        | Nháp Sprint 1        |
| DEP-07 | DOC-06 bộ mẫu + ground truth + baseline thủ công                        | Mọi metric M-01…M-09, Gate B              | Chưa                 |
| DEP-08 | Repo do mentor cấp                                                      | CON-01                                    | —                    |
| DEP-09 | Quyết định D-15                                                         | FR-REV-04, màn 6.6, DOC-05                | Blocking             |
| DEP-10 | Quyết định D-16, D-17                                                   | Ranh giới T1/T2                           | Blocking             |

---

## 12. Risk Register

| **ID** | **Rủi ro**                                                                      | **Impact**   | **Prob.** | **Mitigation**                                                                        | **Owner**           |
| ------ | ------------------------------------------------------------------------------- | ------------ | --------- | ------------------------------------------------------------------------------------- | ------------------- |
| R-01   | Scope T1 vẫn quá rộng cho 3 sprint, không kịp milestone                         | High         | High      | Tier T1/T2 (§3.1); cắt từ §5.B trước; review scope tại Gate A                         | Leader + Mentor     |
| R-02   | OCR không đạt chất lượng trên scan kém / bảng nhiều trang → citation sai        | High         | Medium    | Benchmark nhiều engine trên cùng bộ mẫu (FR-OCR-06); golden dataset; M-03/M-08        | Đức Dũng            |
| R-03   | Quan hệ hợp đồng–phụ lục không suy được an toàn                                 | High         | Medium    | `UNKNOWN/NEEDS_REVIEW` thay vì đoán (FR-UPL-05, FR-PROF-01); D-11                     | Đức Dũng + Chương   |
| R-04   | Model confidence cao nhưng kết quả sai; confidence bị dùng thay accuracy        | High         | Medium    | Cấm dùng confidence làm bằng chứng chất lượng; chỉ đọc M-02/M-03 trên gold            | Văn Dũng            |
| R-05   | Sai ACL hoặc lọc tenant gây rò rỉ dữ liệu dù extraction chính xác               | **Critical** | Low       | M-07 ngưỡng 0; bộ test truy cập chéo bắt buộc trước mỗi release                       | Chương              |
| R-06   | Ép mọi tài liệu về Điều–Khoản–Điểm làm mất cấu trúc hợp đồng nước ngoài/tự soạn | Medium       | Medium    | `StructuralNode` + `UNNUMBERED_BLOCK` (FR-CLA-04/05); D-21                            | Đức Dũng + Văn Dũng |
| R-07   | Mentor gate chậm → Sprint 2 không có gì để code                                 | High         | Medium    | Sprint 1 dồn vào tài liệu và spike không cần gate; chuẩn bị sẵn architecture proposal | Leader              |
| R-08   | D-15 không chốt kịp, FE và BE hiểu khác nhau về thao tác review                 | Medium       | Medium    | FR-REV-04 khóa lại, cấm code trước khi chốt; đưa vào agenda review Sprint 1           | Trang + Mentor      |
| R-09   | Semantic search (T2) tốn chi phí và khó kiểm chứng                              | Medium       | Medium    | Search-first: exact/structured trước; semantic chỉ vào sau khi có baseline Recall\@k  | Văn Dũng + Chương   |
| R-10   | Đo quá nhiều capability cùng lúc, mất trọng tâm painpoint                       | High         | Medium    | Chỉ M-01…M-04 là metric quyết định của T1; phần còn lại theo dõi                      | Leader              |
| R-11   | Bộ mẫu không đủ đại diện → mọi số đo mất ý nghĩa                                | High         | Medium    | Coverage matrix trong DOC-06; công bố `n` và giới hạn (FR-EVAL-02)                    | Đức Dũng            |

---

## 13. Open Decisions

### 13.1 Blocking

| **ID**   | **Decision**                                                                                                                                                                                 | **Chặn cái gì**                | **Owner**                          | **Chốt tại**    |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------ | ---------------------------------- | --------------- |
| **D-15** | DOC-01 §4.3 xếp `correct` / `reject` / `needs-more-evidence` vào giai đoạn sau, PRD v0.9 để Must. Chọn: (a) sửa DOC-01 mở lại, hay (b) giữ DOC-01 và để FR-REV-04 ngoài T1                   | FR-REV-04, màn 6.6, DOC-05     | Leader + Mentor + Trang + Văn Dũng | Review Sprint 1 |
| **D-16** | Mức multi-tenant trong OJT: (a) tenant + ACL thực thi từ Sprint 1, (b) chỉ có trong mô hình dữ liệu, chưa thực thi, (c) hoãn. Liên quan CON-02 và "phân quyền phức tạp ngoài scope Sprint 1" | Toàn bộ FR-TEN tier T1, ERD    | Mentor + Chương + Leader           | DOC-04          |
| **D-17** | Xác nhận ranh giới T1/T2 ở §3.1, và DOC-01 có bổ sung mục "MVP theo giai đoạn" không                                                                                                         | Scope Sprint 2–3, DOC-01       | Mentor + Leader + Product Owner    | Review Sprint 1 |
| **D-18** | Quan hệ giữa `Snapshot`/`Run` và bản chỉ mục: ba khái niệm riêng hay một                                                                                                                     | ST-017, lifecycle §4.3, FR-IDX | Chương + Đức Dũng + Văn Dũng       | ST-017 / DOC-04 |
| D-01     | Mô hình batch: một lô nhiều dossier hay một lô nhiều file rời                                                                                                                                | Upload + batch API             | Chương + Trang                     | DOC-05          |
| D-02     | `conflict_detected` là state hay nhãn phái sinh                                                                                                                                              | Lifecycle Backend              | Chương + Mentor                    | DOC-04          |
| D-03     | Định nghĩa `reviewed`; có cho `pending_review → approved` trực tiếp                                                                                                                          | Lifecycle + UI                 | Chương + Trang + Văn Dũng          | DOC-04 / DOC-05 |
| D-04     | Tên surface "conflicts" vs "findings"; map thao tác review vào API                                                                                                                           | Hợp đồng BE–FE                 | Chương + Trang + Văn Dũng          | DOC-05          |
| D-08     | Wire format snapshot AI1 ↔ AI2                                                                                                                                                               | FR-FIND-01                     | Đức Dũng + Văn Dũng                | ST-017 / DOC-04 |
| D-21     | ST-017 chọn `StructuralNode` tổng quát hay cây Điều–Khoản–Điểm cứng; tập `node_type` gồm những gì                                                                                            | Schema node/finding            | Đức Dũng + Văn Dũng + Chương       | ST-017          |

### 13.2 Non-blocking

| **ID** | **Decision**                                                                                   | **Owner**                  | **Chốt tại** |
| ------ | ---------------------------------------------------------------------------------------------- | -------------------------- | ------------ |
| D-05   | Ngưỡng highlight độ tin cậy thấp (đề xuất 0.6, chưa hard-code)                                 | Đức Dũng + Trang           | DOC-06       |
| D-06   | OCR engine chính và fallback                                                                   | Đức Dũng                   | DOC-04       |
| D-07   | Có bật tiền xử lý ảnh                                                                          | Đức Dũng                   | DOC-06       |
| D-09   | Phạm vi so sánh ngữ nghĩa reviewer chấp nhận                                                   | Văn Dũng + Leader + Mentor | DOC-02       |
| D-10   | Cơ chế xử lý bất đồng bộ và giới hạn chạy song song                                            | Chương + Đức Dũng          | DOC-04       |
| D-11   | Liên kết phụ lục với hợp đồng bằng cách nào                                                    | Đức Dũng + Chương          | DOC-04       |
| D-12   | Mở rộng định dạng ảnh JPG/PNG                                                                  | Mentor + Chương            | DOC-05       |
| D-13   | Dịch vụ OCR/AI bên ngoài (baseline none)                                                       | Mentor                     | DOC-04       |
| D-19   | Mốc 30 ngày khôi phục và 12 tháng audit có phù hợp không                                       | Mentor + Chương            | DOC-04       |
| D-20   | Quota/cost governance chỉ áp dụng khi thực sự có model call                                    | Chương + Mentor            | DOC-04       |
| D-22   | Giới hạn quy mô đã đo công bố ở đâu, đo thế nào (CON-03b)                                      | Đức Dũng + Văn Dũng        | DOC-06       |
| D-23   | Role Viewer / Auditor / Support triển khai ở T2 hay chỉ mô tả ở DOC-01                         | Mentor + Leader            | DOC-04       |
| D-24   | `INSUFFICIENT_EVIDENCE` (query) vs `insufficient_evidence` (finding): có đổi tên một bên không | Văn Dũng + Chương          | DOC-05       |
| D-14   | Các quyết định tích hợp còn lại                                                                | Văn Dũng                   | ST-022       |

---

## 14. Acceptance Strategy

Ba tầng acceptance khác nhau, không được nhầm lẫn:

| **Tầng**              | **Đối tượng**                   | **Ở đâu**          | **Ai nghiệm thu**        |
| --------------------- | ------------------------------- | ------------------ | ------------------------ |
| **Requirement-level** | Từng FR                         | Cột Acceptance §5  | Reviewer theo area (§15) |
| **Product-level**     | Goal G1–G6 qua metric M-01…M-09 | DOC-06, sau Gate B | Mentor + Leader          |
| **Release-level**     | Tier T1 hoàn thành              | §14.1 dưới đây     | Mentor                   |

Sprint deliverable (ai làm gì trong sprint nào) **không phải acceptance** và thuộc **Sprint Plan**, không thuộc PRD.

### 14.1 Definition of Done cho tier T1

Tier T1 được coi là xong khi đủ các điều kiện sau:

1. Mọi FR tier T1 priority Must có acceptance được kiểm chứng và ghi nhận.
2. UC-01 → UC-08 chạy được end-to-end trên ít nhất một dossier thật (1 hợp đồng + 1 phụ lục).
3. M-07 (tenant isolation violation) = 0 trên bộ test truy cập chéo.
4. M-01 → M-04, M-06, M-08 có số đo kèm `n`, bộ mẫu và điều kiện chạy, so được với baseline thủ công.
5. Không còn decision blocking nào ở §13.1 ảnh hưởng tới phạm vi T1.
6. Mọi task Done có link PR / commit / doc (NFR-08).

Không đặt ngưỡng đạt/không đạt cho M-01…M-06 và M-08 trước khi có baseline — đó là nội dung của DOC-06 sau Gate B.

---

## 15. Review & Approval

| **Reviewer**                   | **Phạm vi phải xác nhận**                                                        |
| ------------------------------ | -------------------------------------------------------------------------------- |
| AI1 — Nguyễn Đức Dũng          | Snapshot, provenance, hình học vùng, `StructuralNode` đủ cho citation và HITL    |
| Backend — Phạm Hoàng Chương    | API, đồng thời, tenant/ACL, audit, ranh giới T1/T2 phía backend                  |
| Frontend — Trần Thị Kiều Trang | Evidence hai phía, highlight, 6 màn T1, dossier overview và tìm kiếm             |
| AI2 — Trần Văn Dũng            | Semantics fact/finding/disposition, ba lớp trạng thái §5.6.2, phần semantic ở T2 |
| Leader — Trần Thị Kiều Trang   | Goals, scope tier, priority, risk register                                       |
| Mentor                         | Architecture + project structure; D-15, D-16, D-17, D-18                         |

| **Reviewer** | **Status**                 | **Date** |
| ------------ | -------------------------- | -------- |
| AI1          | ☐ Reviewed                 | —        |
| Backend      | ☐ Reviewed                 | —        |
| Frontend     | ☐ Reviewed                 | —        |
| AI2          | ☐ Reviewed                 | —        |
| Leader       | ☐ Consolidated             | —        |
| Mentor       | ☐ Architecture + D-15…D-18 | —        |

Version chuyển sang **1.0 — Approved baseline** khi đủ 6 mục ☑, mentor duyệt architecture và §13.1 không còn decision blocking ảnh hưởng T1.

---

## Appendix A — Traceability Matrix

### A.1 DOC-03 ↔ DOC-01 v0.4

| **DOC-01** | **Nội dung**                                        | **FR/NFR trong DOC-03 v0.11**              | **Tier** |
| ---------- | --------------------------------------------------- | ------------------------------------------ | -------- |
| §1.4 (1)   | Nhận dossier, role từ manifest/evidence             | FR-UPL-01, FR-UPL-04, FR-UPL-05            | T1       |
| §1.4 (2)   | Chỉ mục có cấu trúc, không bắt buộc Điều–Khoản–Điểm | FR-CLA-01, FR-CLA-04, FR-CLA-05            | T1       |
| §1.4 (3)   | Hybrid search trong dossier                         | FR-SRCH-01/02/05 (T1), FR-SRCH-07 (T2)     | T1 + T2  |
| §1.4 (4)   | Citation/bbox + nguồn liên quan                     | FR-NAV-01/02/03                            | T1       |
| §1.4 (5)   | Reviewer xác nhận / `NEEDS_REVIEW`                  | FR-REV-02, FR-REV-03                       | T1       |
| §1.4 (6)   | Tenant isolation, private-by-default                | FR-TEN-01…06, FR-UPL-06                    | T1       |
| §1.4 (7)   | Audit, soft-delete, restore, purge                  | FR-AUD-03…06 (T1), FR-AUD-07 + FR-LCM (T2) | T1 + T2  |
| §1.4 (8)   | Index bất đồng bộ theo phiên bản                    | FR-IDX-01/02 (T1), FR-IDX-03…05 (T2)       | T1 + T2  |
| §1.4 (9)   | Điều phối truy vấn theo chi phí                     | FR-SRCH-06 (T1), FR-COST-01…05 (T2)        | T1 + T2  |
| §1.4 (10)  | QueryTrace                                          | FR-COST-06/07                              | T2       |
| §2         | Painpoint, hậu quả, JTBD                            | §1.2                                       | —        |
| §3.2       | Nguyên tắc sản phẩm                                 | §1.5, NFR-09…13                            | —        |
| §4.1       | Phạm vi MVP                                         | §1.3, §3.1, FR-FIND-09, FR-HITL-11         | —        |
| §4.2       | Ngoài phạm vi                                       | §3.3                                       | —        |
| §4.3       | Giai đoạn sau                                       | FR-REV-04 (D-15), FR-REV-07                | —        |
| §5.1–§5.2  | TenantProfile, template không nhận diện             | FR-PROF-01…05                              | T1 + T2  |
| §5.3       | StructuralNode                                      | FR-CLA-04/05, DC-03, D-21                  | T1       |
| §6.1       | Cây hồ sơ khi chưa có truy vấn                      | FR-HITL-07, màn 6.2                        | T1       |
| §6.2       | Vai trò và chia sẻ                                  | §2.1, FR-TEN-03/04/07                      | T1 + T2  |
| §6.3       | Feedback loop giai đoạn sau                         | FR-REV-07                                  | Later    |
| §7.1       | Lưu trữ và bảo mật                                  | NFR-06, FR-TEN-03/06                       | T1       |
| §7.2       | Xóa và khôi phục                                    | FR-LCM-01…07                               | T2       |
| §7.3       | Audit trail                                         | FR-AUD-03…07                               | T1 + T2  |
| §7.4       | Object và interface                                 | §9 (DC-01…09)                              | —        |
| §7.5       | Index, query trace, cost governance                 | FR-IDX, FR-COST                            | T1 + T2  |
| §8.1       | Chỉ số sản phẩm                                     | §1.6 (M-01…M-12), FR-EVAL-01/02            | —        |
| §9.1       | Giả định                                            | §10 (A-01…A-10)                            | —        |
| §9.2       | Rủi ro                                              | §12 (R-01…R-11)                            | —        |
| §9.3       | Kế hoạch kiểm chứng                                 | Cột Acceptance §5 + §14.1 + DOC-06         | —        |

### A.2 Goal → FR → Metric

| **Goal**                       | **FR**                              | **Metric**       | **Tier** |
| ------------------------------ | ----------------------------------- | ---------------- | -------- |
| G1 Tìm nhanh hơn               | FR-SRCH-01/02, FR-HITL-07/08        | M-01, M-02, M-04 | T1       |
| G2 Truy ngược về nguồn         | FR-NAV-01/03, FR-FIND-07, FR-CLA-03 | M-03             | T1       |
| G3 Giảm thao tác đối chiếu     | FR-FIND-03/05, FR-NAV-02            | M-04             | T1       |
| G4 Không tự kết luận pháp lý   | FR-FIND-08, FR-APR-01, FR-REV-02    | M-05             | T1       |
| G5 Đọc được nhiều mẫu hợp đồng | FR-CLA-04/05/06, FR-PROF-01         | M-06             | T1       |
| G6 Không rò rỉ giữa tenant     | FR-TEN-01…05                        | M-07 (ngưỡng 0)  | T1       |

### A.3 ID mapping

**Contribution AI2 v0.1:** PRD-AI2-FR-01 → FR-FIND-01 · -02 → FR-FIND-02 · -03 → FR-FIND-03 · -04 → FR-FIND-04 · -05 → FR-FIND-05 · -06 → FR-FIND-06 · -07 → FR-FIND-07 · -08 → FR-REV-01 · -09 → FR-AUD-01 · -10 → FR-EVAL-01
**v0.9 → v0.10:** FR-UPL-05 → FR-UPL-07 · FR-HITL-07/08/09 → FR-HITL-09/10/11 · FR-REV-02 → tách thành FR-REV-02/03/04 · FR-REV-03 → FR-REV-05 · FR-REV-04 → FR-REV-06 · FR-JOB-03/04 → FR-JOB-04/05
**v0.10 → v0.11:** ID của FR giữ nguyên, trừ hai nhóm đã đổi số thứ tự nội bộ — FR-SRCH (SRCH-03 semantic cũ → **SRCH-07** T2; SRCH-04/05/06/07 cũ → SRCH-04/05/03/06) và FR-AUD (AUD-04/05/06 cũ → AUD-05/06/04, thêm AUD-07 T2); FR-PROF đảo thứ tự để T1 lên trước (PROF-04/05 cũ → PROF-01/02). Số mục của tài liệu dịch: §4 FR → §5, §5 UX → §6, §8 Data → §9, §11 → §11–§13, §12 Traceability → Appendix A.

---

## Appendix B — References

| **Reference**                     | **Purpose**                                                                             | **Nội dung PRD đã đẩy sang**                                           |
| --------------------------------- | --------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| DOC-01 Product Vision v0.4        | Problem, value, non-goals, nguyên tắc                                                   | — (PRD bám theo)                                                       |
| DOC-02 BRD (ST-015)               | Business taxonomy, ngữ cảnh, cổng so sánh                                               | Decision table conflict                                                |
| DOC-04 Architecture               | Kiến trúc, lưu trữ, queue, tenant boundary, index publish/rollback, cache, vector store | Monolith/DDD, loại DB & kiểu cột, object storage key, thư viện đọc PDF |
| DOC-05 API Spec                   | Đường dẫn, envelope, schema, tên surface, quy ước status                                | Chi tiết endpoint và payload                                           |
| DOC-06 Eval Report                | Metric formula, bộ mẫu, baseline, số đo có `n`                                          | Kết quả spike engine, giới hạn quy mô đã đo                            |
| ST-016 Case Catalog               | C01–C15 × 2 representations                                                             | Mapping case ↔ disposition                                             |
| ST-017 Data Contract              | Schema fact / finding / snapshot / citation / revision / node / index / query trace     | Field list, offset, hệ tọa độ, representation, digest                  |
| ST-022 Traceability & Integration | Quyết định tích hợp còn mở                                                              | Binding và metric binding                                              |
| Sprint Plan / Project Plan        | Sprint deliverable, RACI, ownership theo area                                           | §9 và §2.5 của v0.10                                                   |
