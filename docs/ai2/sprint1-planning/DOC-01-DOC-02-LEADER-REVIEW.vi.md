# Report review DOC-01 Product Vision và DOC-02 BRD — Dành cho Leader

| Thuộc tính | Nội dung |
|---|---|
| **Dự án** | Contract Intelligence (PROD-01) |
| **Tài liệu review** | DOC-01 Product Vision v0.3 và DOC-02 BRD v0.2 |
| **Căn cứ** | Đề bài `assignment.pdf` và nội dung hai tài liệu hiện hành |
| **Mục tiêu** | Chỉ ra nội dung cần Leader sửa/chốt trước khi gửi Mentor review |
| **Kết luận** | Hai tài liệu có nền tảng tốt nhưng chưa nên freeze vì còn mâu thuẫn về scope, requirement bắt buộc và lifecycle review. |

## 1. Tóm tắt điều hành

DOC-01 làm rõ đúng problem, users, value và out-of-scope. DOC-02 có coverage tốt cho OCR, clause, citation, bbox, conflict, HITL, batch, metric và rủi ro. Điểm mạnh chung là evidence-first, không suy đoán, không coi finding là kết luận pháp lý và giữ lịch sử human correction.

Tuy nhiên, một số capability mà đề bài quy định là bắt buộc đang bị hạ thành `Should` hoặc có wording mơ hồ. Leader cần chốt lại để product scope, BRD, PRD và tài liệu kỹ thuật không đi theo các hướng khác nhau.

## 2. Các vấn đề P0 cần sửa trước Mentor review

| ID | Vấn đề | DOC-01 | DOC-02 | Hướng sửa Leader cần chốt |
|---|---|---|---|---|
| P0-01 | Language scope mâu thuẫn | Việt là Must; Anh/song ngữ là Should | §1/§21 có nêu Anh/song ngữ nhưng §5.1 là Should | Nếu Mentor không miễn scope, ghi thống nhất Must cho tiếng Việt, tiếng Anh và trang/tài liệu song ngữ Việt–Anh trong bộ mẫu. Không cam kết production cho mọi ngôn ngữ/font/biến thể. |
| P0-02 | Demo dossier chưa chứng minh conflict liên tài liệu | Dossier “có thể kèm phụ lục” | BR-01 đúng 1 contract + 0..n annex | Giữ data model 0..n, nhưng quy định demo/test tối thiểu là 1 contract + 1 annex; Sprint 3 có coverage annex–annex. |
| P0-03 | Conflict core bị diễn đạt như optional | OOS nói không tự động phát hiện/giải quyết toàn bộ conflict | BR-11–14 yêu cầu hai family/ba scope | Ghi rõ không cam kết phát hiện mọi conflict thực tế, nhưng phải demo structured + semantic finding trên within-document, contract–annex và annex–annex, có evidence hai phía. |
| P0-04 | Word/line geometry bị hạ thành “nên lưu” | Evidence-first yêu cầu truy nguồn | BR-03 | Đổi thành “phải lưu” word/line geometry, page size, rotation, raw text, page status và warnings/errors. |
| P0-05 | Bbox edit bị coi là optional | BO-05 mô tả Should | BR-17 mô tả Should | Ghi “Must by Sprint 3; không bắt buộc Sprint 1”. Bbox edit phải giữ machine bbox và reviewer bbox qua revision, không overwrite. |
| P0-06 | Contract–annex relation cho phép suy từ upload order | Không tự suy relation/amendment | BR-06 liệt kê upload order như phương án link | Role/relation phải từ dossier manifest do owner xác nhận hoặc source evidence có citation. Upload order chỉ là metadata. |
| P0-07 | Review closure bị lẫn với job approval | Không trao legal approval cho hệ thống | BR-16/§14 dùng `approved` | Tách pipeline/job status khỏi review decision. Dùng `review_closed` hoặc `reviewer_approved` với actor/time/permission; không diễn giải là legal/business approval. |
| P0-08 | Context gate chưa là requirement enforceable | DOC-01 nêu context before comparison | BR-11 chỉ mô tả giá khác là conflict | Thêm gate bắt buộc: role, subject, unit/currency/VAT, scope, validity. Khác context = `not_comparable`; thiếu evidence = `insufficient_evidence`. |
| P0-09 | Semantic example không đúng family | Nêu finding kỹ thuật có evidence | BR-12 dùng 30 ngày vs 15 ngày | Đây là structured duration mismatch. Thay bằng xung đột obligation/polarity cùng subject/action/condition. |
| P0-10 | Batch/recovery chưa đủ rõ | Operator theo dõi pipeline | BR-19/§14 | Thêm partial failure, retry attempt, quarantine, crash recovery và batch summary từng dossier. Job không được biến mất im lặng. |

## 3. Nội dung Leader cần sửa trong DOC-01

### 3.1 Language scope

Thay wording tiếng Việt-only/English-Should bằng:

> Hỗ trợ bắt buộc trong phạm vi đánh giá: PDF scan và PDF có text-layer bằng tiếng Việt, tiếng Anh, và trang/tài liệu song ngữ Việt–Anh trong bộ mẫu. Sản phẩm không cam kết chất lượng production cho mọi ngôn ngữ, font hoặc bố cục song ngữ.

### 3.2 Demo tối thiểu

Thay “dossier gồm hợp đồng và có thể kèm phụ lục” bằng:

> Đơn vị xử lý là dossier gồm một hợp đồng và 0..n phụ lục. Demo end-to-end tối thiểu dùng một hợp đồng và một phụ lục để chứng minh evidence và comparison liên tài liệu.

### 3.3 Scope conflict

Thay out-of-scope quá rộng bằng:

> Không cam kết phát hiện mọi xung đột thực tế hoặc tự giải quyết xung đột. Sản phẩm vẫn phải demo structured và semantic finding trên ba comparison scope của bộ sample/gold đã xác định.

### 3.4 Lifecycle wording

Đổi trạng thái “đã duyệt” thành “đã đóng review”, đồng thời ghi rõ đó là thao tác của reviewer có thẩm quyền đối với kết quả kỹ thuật, không phải hệ thống phê duyệt hợp đồng.

### 3.5 Sensitive-data principle

Thêm nguyên tắc:

> Hợp đồng có thể là dữ liệu nhạy cảm. Chỉ người có quyền mới được xem, tải hoặc review dossier; dữ liệu chỉ được gửi tới external service theo policy đã được phê duyệt.

## 4. Nội dung Leader cần sửa trong DOC-02

### 4.1 Geometry, clause và table provenance

- BR-03: thay “nên lưu” bằng “phải lưu” word/line geometry.
- BR-04: table phải là `table → row → cell`, không chỉ row hoặc text blob.
- BR-05: mỗi clause có citation và một/many clause-region bbox; clause nhiều trang giữ source riêng theo từng trang.
- BR-07: citation gắn một version input/OCR cụ thể, có thể gồm nhiều component khi source trải nhiều dòng/trang.
- BR-08: correction tạo revision/overlay; machine value, citation, bbox và source cũ không bị update/xóa.

### 4.2 Dossier manifest

Thay BR-06 bằng requirement:

> Mỗi dossier có manifest xác nhận contract/annex role và relation. Manifest do operator/reviewer/product owner xác nhận; AI không suy relation từ filename hoặc upload order. Relation từ nội dung phải có citation evidence. Thiếu manifest xác nhận thì chặn comparison liên tài liệu.

### 4.3 Conflict semantics

Bổ sung trước BR-11:

> Hệ thống chỉ compare fact tương thích về role, subject, unit/currency/VAT, scope và validity. Khác context trả `not_comparable`; thiếu value/context/evidence trả `insufficient_evidence`.

Thay semantic example bằng:

| Hợp đồng | Bên A phải giao lô X trước ngày 10/10/2026. |
|---|---|
| Phụ lục | Bên A không được giao lô X trước ngày 10/10/2026. |

Thêm: semantic candidate chỉ được tạo khi subject, action, object, recipient, time và condition đủ evidence; từ phủ định riêng lẻ không đủ.

### 4.4 HITL và job lifecycle

- BR-16: `Confirm`, `Correct`, `Reject`, `Needs-more-evidence` áp dụng cho fact/finding. `Review closed` là action dossier-level riêng, có permission/actor/timestamp.
- BR-17: đổi thành “Must by Sprint 3; not required Sprint 1”.
- §14: state tối thiểu `queued → validating → waiting_for_input → extracting → comparing → needs_review → review_closed → completed | partial_failed | failed | quarantined`.
- BR-19: bắt buộc retry có giới hạn, recovery sau crash, history attempt và batch summary `done/failed/partial_failed/needs_review`.

### 4.5 Dataset, metrics và privacy

- Thay “30 mẫu” bằng số rõ `n_dossiers`, `n_documents`, `n_pages`, `n_logical_cases`, `n_scan`, `n_text_layer`, `n_vi`, `n_en`, `n_bilingual`.
- Tách development set và evaluation set; metric report luôn có n, denominator, sample, gold/rule/engine version, failed/missing/not-run.
- Dữ liệu Mentor không được commit lên **bất kỳ** repository nào, không chỉ repository public.
- `seal/signature overlap` chỉ là OCR-noise case, không biến thành signature-verification feature.
- External-service register cần ghi service, loại dữ liệu gửi, mục đích, sensitivity policy, retention và người phê duyệt.

## 5. Quyết định Leader/Mentor cần chốt

| ID | Quyết định | Owner đề xuất | Hệ quả nếu chưa chốt |
|---|---|---|---|
| D-01 | English/bilingual là Must hay được miễn? | Mentor + Leader | Product scope mâu thuẫn, sample/evaluation không xác định. |
| D-02 | Demo/test dossier tối thiểu và coverage annex–annex | Leader + Mentor | Không chứng minh được conflict liên tài liệu. |
| D-03 | Ai xác nhận manifest, role, effective date và relation? | Leader/Product | AI không được compare liên tài liệu an toàn. |
| D-04 | `Review closed` có nghĩa gì, ai có quyền? | Leader + Reviewer | Dễ nhầm technical review với legal approval. |
| D-05 | Semantic MVP chỉ polarity/obligation hay thêm exception/condition? | Mentor + AI team | Không có acceptance test rõ. |
| D-06 | “30 mẫu” đo theo dossier/document/page/case nào? | AI team + Mentor | Không báo metric có n/denominator hợp lệ. |
| D-07 | Service external nào được dùng với mentor/customer data? | Mentor + Leader | Không được route dữ liệu thật hoặc claim privacy. |

## 6. Điều kiện chuyển sang Mentor review

- [ ] DOC-01 và DOC-02 dùng cùng language scope.
- [ ] Đã chốt minimum demo dossier và conflict coverage.
- [ ] BR-03/04/05/07/08/17 phản ánh provenance, table/cell và bbox requirement bắt buộc.
- [ ] BR-06 không còn cho AI suy relation từ upload order.
- [ ] BR-11/12 có context gate và semantic example đúng.
- [ ] Review closure tách khỏi pipeline/job approval.
- [ ] Batch/recovery, dataset denominator và external data policy có owner/decision.
- [ ] Open decision có trạng thái, owner, hạn chốt và evidence sau khi xác nhận.

Sau khi checklist này hoàn tất, Leader có thể đổi trạng thái tài liệu từ `Draft` sang `Ready for Mentor Review` mà không tạo claim về OCR quality hay production readiness.
