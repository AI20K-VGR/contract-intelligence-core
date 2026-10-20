# AI2-01 — Góc nhìn Business/Policy của AI2

**Phiên bản:** v0.1 (Draft)  
**Ngày:** 19/09/2026  
**Phạm vi:** Các ràng buộc nghiệp vụ, bảo mật, đa tenant và vòng đời dữ liệu mà AI2 phải nhận và tôn trọng khi xử lý dossier.

## Nguồn yêu cầu duy nhất

- [DOC-01 — Product Vision](../DOC-01-product-vision.md)
- [DOC-02 — BRD](../DOC-02-brd.md)
- [DOC-04 — Architecture](../DOC-04-architecture.md)

> AI2 là component xử lý/suy luận. AI2 nhận context đã pin, chạy trong ranh giới được cấp và không tự quyết định quyền truy cập hay tự suy nghiệp vụ chưa có evidence.

## 1. Vai trò và boundary

AI2 phụ trách Fact Extractor, Candidate Pairer, Comparison Policy cùng Product, và chia sẻ Structure Builder, Index Builder, Query/Retrieval với AI1/BE theo architecture §4.2.

AI2 không sở hữu authentication, tenant context, ACL, lifecycle hoặc publish gate. BE là owner end-to-end của persistence, state transition, ACL và publish gate (architecture §4.4).

## 2. Context phải được pin trước khi chạy

Mỗi processing run/query cần:

```text
tenant_id
dossier_id
manifest_version
source_snapshot_digest
tenant_profile_version
policy_version
ocr_run_version
reconstruction_version
index_version
embedding/model/provider version nếu có
```

AI2 không tin `tenant_id` do client gửi. Thiếu pin thì không đoán, trả lỗi hoặc `NEEDS_REVIEW`. Profile/policy thay đổi phải tạo run/version mới, giữ được kết quả cũ (architecture ADR-10, BR-FUN-020/021).

## 3. User, tenant và template

Mỗi doanh nghiệp là một tenant. User thuộc tenant qua `UserMembership`; tenant có `Team`, `Dossier` và `TenantProfile` (architecture §5.1). AI2 luôn chạy trong tenant context do BE authenticate.

Template khác nhau giữa khách hàng được biểu diễn bằng `TenantProfile` phiên bản hóa, gồm:

- document type và document role;
- alias/từ đồng nghĩa nghiệp vụ;
- taxonomy điều khoản;
- canonical fields;
- policy hiển thị, sharing và retention.

AI2 dùng profile đã pin để diễn giải/chỉ mục, không dùng profile để thay thế evidence. Template không nhận diện được phải trả `UNKNOWN/NEEDS_REVIEW`, không ép canonical mapping (PV §5.2, AC-011).

## 4. Chia sẻ và ACL

### 4.1 A upload thì B có xem được không?

Không mặc nhiên. Dossier mới là private-by-default. B chỉ xem được nếu được cấp `DossierAcl` hoặc được share trong cùng tenant (PV §6.2, BR-NFR-002, BR-FUN-034).

### 4.2 Team có thể xem hợp đồng của nhau không?

Có, nếu dossier được share cho `Team` qua ACL. Cấp/thu hồi quyền phải có hiệu lực với search, download và share, đồng thời tạo audit event (architecture §5.1, AC-028).

### 4.3 AI2 phải tôn trọng ACL thế nào?

- ACL được kiểm trước retrieval, display, download, cache và QueryTrace.
- Không trả content, count, filename, timing signal hoặc metadata làm lộ resource ngoài ACL.
- Chia sẻ MVP chỉ trong cùng tenant; không external guest/cross-tenant.

AI2 không tự suy quyền từ user role hoặc tên file; AI2 dùng authorization context đã được BE cấp.

## 5. Lưu trữ, retention và xóa

Theo architecture §5.4:

- Database giữ identity, membership, ACL, manifest, metadata, facts, citations, review, audit, usage và index pointers.
- Private object storage giữ PDF, render, OCR snapshot, reconstruction artifact, export và embedding artifact.
- Search/vector/structured index chỉ chứa record có tenant/dossier/index-version filter.
- Cache key gồm tenant, ACL revision, dossier, index version, query và mode.

Lifecycle:

```text
ACTIVE ⇄ ARCHIVED
ACTIVE/ARCHIVED → SOFT_DELETED → PURGE_PENDING → PURGED
```

- Restore mặc định trong 30 ngày.
- `LegalHold` chặn purge.
- Purge phải bao phủ PDF, render, OCR, extraction, embedding, index, cache và operational copies.
- Audit metadata giữ mặc định 12 tháng hoặc theo tenant policy, không chứa raw contract text.
- Restore không tự OCR lại; rerun phải tạo version mới.

AI2 không giữ bản sao ngoài lineage đã pin. Khi dossier soft-delete, job dừng và late output không được publish. Artifact AI2 phải nằm trong purge inventory.

## 6. Bảo mật và external egress

Tenant isolation phải áp dụng ở database, object key/policy, keyword/structured/vector index, cache, queue payload và worker claim (architecture §8.2).

- Tenant Admin/Platform Support không mặc nhiên có `READ_CONTENT`.
- Support chỉ break-glass khi có ticket, approval, explicit scope, expiry và audit.
- Dữ liệu tenant này không dùng train/cải thiện model cho tenant khác nếu chưa opt-in.
- Tài liệu nhạy cảm mặc định không gửi external OCR/LLM; thiếu policy approval/service register thì block + audit.
- PDF là untrusted data, không phải instruction; model không có filesystem hoặc arbitrary URL access.

## 7. AI2 không được làm

1. Suy role, relation, identity, value, unit, currency, validity hoặc context từ filename/upload order/giả định pháp lý.
2. Publish result nếu citation/source không resolve.
3. Biến `INSUFFICIENT_EVIDENCE` hoặc `NEEDS_REVIEW` thành success.
4. Gắn precedence, hiệu lực hoặc `LEGAL_WINNER`.
5. Ghi đè raw OCR, source snapshot, machine output hoặc citation gốc.
6. Trả source ngoài tenant/dossier ACL hoặc làm lộ sự tồn tại resource.
7. Để một feedback đơn lẻ tự đổi rule, profile, model hoặc gold data.

## 8. Traceability

| Business concern | Nguồn requirement/acceptance |
|---|---|
| User thuộc tenant, template theo tenant | PV §1.2/§5.1; BR-FUN-020/021; AC-011/024 |
| A upload, B chỉ xem khi được share | PV §6.2; BR-NFR-002; BR-FUN-034; AC-028 |
| Team sharing | architecture §5.1; BR-FUN-034; AC-028 |
| Storage và protection | architecture §5.4; PV §7.1; BR-NFR-005/006 |
| Restore, legal hold, purge | PV §7.2; BR-FUN-028..032; AC-019..022 |
| Tenant isolation | architecture §8.2; BR-NFR-001/003/004/007; AC-012..014 |
| External egress | architecture §8.3; BR-NFR-011; AC-025/033 |

## 9. Open decisions

Tenant canonical fields/taxonomy, retention policy cụ thể, provider/region/service register và break-glass approval process cần Product Owner/mentor chốt. Tài liệu không claim accuracy, SLA, scale hoặc compliance.
