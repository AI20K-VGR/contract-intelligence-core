# Traceability và quyết định tích hợp — AI2 v0.2

**Owner soạn:** Trần Văn Dũng — AI2  
**Trạng thái:** Draft ready — register đề xuất, chưa có reviewer/ngày/evidence xác nhận.

## 1. Traceability

| Nguồn BRD/data contract | PRD requirement | SAD / integration | Case hoặc kiểm tra thiết kế |
|---|---|---|---|
| BR-04/BR-05: 7 entity types, raw/normalized/context/citation | FR-02 | `Fact` và citation boundary | C01–C13 structured facts |
| BR-06/BR-07: context gate và 5 dispositions | FR-03, FR-04 | AI2 context/comparison component | C01–C03, C05–C13 |
| BR-08: amendment evidence, non-legal boundary | FR-05 | Finding precedence evidence | C02; C03 control |
| BR-07: semantic pilot hẹp | FR-06 | Semantic finding family | C04/C14/C15 |
| BR-10/BR-11: snapshot/run/review lifecycle | FR-07–FR-09 | Immutable artefacts, append-only revision | Re-OCR, concurrent review scenarios |
| BR-03/BR-09: citation/highlight provenance | FR-07 | AI1→AI2→FE citation contract | Unicode `A😀B`; upright highlight |
| BR-13: audit/metrics protocol | FR-10 | Run/audit metadata | C02/C13/C15, Gate B audit |

## 2. Review checklist theo owner

| Reviewer/owner | Cần xác nhận | Điều kiện hoàn tất review |
|---|---|---|
| AI1 | Snapshot granularity, digest, engine/version, line/word/clause/table refs, page frame/rotation, re-OCR behavior | Walkthrough một citation thực trên snapshot đã xác định. |
| BE | System of record, IDs/schema version, API boundary, ref integrity, review CAS/rebase, run lineage và error behavior | Xác nhận design hoặc feedback có ngày/evidence. |
| FE | Hai-source navigation, raw span rendering, bbox transform, disposition/review-state rendering | Walkthrough design với frame được AI1 xác nhận. |
| Leader/product | BR-01/02/12 scope, dossier role source, reviewer/adjudicator, semantic policy và Gate B target owner | Scope, reviewer và open-decision disposition được xác nhận bằng chữ. |

## 3. Decision register liên nhóm

| ID | Quyết định cần chốt | Owner đề xuất | Trạng thái | Hệ quả nếu chưa chốt |
|---|---|---|---|---|
| INT-01 | Canonical dossier manifest: membership, document role và source xác nhận quan hệ contract/annex | Leader + BE/product | Pending review | Không được tạo contract-annex/annex-annex comparison tự động. |
| INT-02 | Snapshot per page hay per document; namespace page/line/word/bbox và multi-page/table provenance | AI1 + FE + BE | Pending review | Citation/highlight contract chưa freeze. |
| INT-03 | Extraction run lineage, schema evolution/version pin và `finding_run` envelope semantics | AI2 + BE | Pending review | Rerun reproducibility chưa đủ. |
| INT-04 | API transport, persistence, retry/idempotency, run trigger/current run và error model | BE | Pending review | Không implement endpoint/schema. |
| INT-05 | Actor identity, RBAC, retention/logging, security classification và deployment | Leader + BE | Pending review | Không đưa claim bảo mật/production vào SAD. |
| INT-06 | Reviewer/amendment policy và semantic scope | Leader + reviewer | Pending review | Candidate vẫn là technical finding, không accepted legal outcome. |

## 4. Planned validation và Gate B

- Self-review: enum canonical; không lẫn `finding_type`, `model_disposition`, `review_state`; refs/data ownership nhất quán giữa PRD/SAD/data contract.
- Integration design: cross-document evidence, missing evidence, multi-page/table citation, re-OCR preserves history, concurrent review conflict, upright-frame highlight.
- Case catalogue C01–C15 × hai representation là coverage thiết kế. Không dùng làm claim OCR quality, integration pass hoặc metric.
- Gate B chỉ chạy sau khi có PDF/OCR thật, source digest, bindings, audit và run log. Khi đó dùng [ST-020-OCR-BBOX-AUDIT-CHECKLIST.vi.md](ST-020-OCR-BBOX-AUDIT-CHECKLIST.vi.md) và [ST-021-METRIC-PROTOCOL.vi.md](ST-021-METRIC-PROTOCOL.vi.md).

## 5. Ảnh hưởng tài liệu nhóm

| Artefact nhóm | Ảnh hưởng của AI2 | Cách phối hợp |
|---|---|---|
| Product Vision | Chỉ cần nhất quán giá trị “hỗ trợ reviewer” và non-legal boundary. | Đề xuất wording, không viết lại DOC-01. |
| BRD | Là nguồn taxonomy/lifecycle AI2. | PRD/SAD tham chiếu, không tạo enum mới. |
| PRD chung | Thêm flow, FR, acceptance và constraints AI2. | Người tổng hợp PRD quyết định vị trí chương. |
| SAD chung | Pipeline, contract, provenance và review lifecycle là interface shared. | Chờ AI1/BE/FE review trước Accepted. |
| API Spec/UI | Semantics object/citation/revision ảnh hưởng interface. | BE/FE sở hữu wire format và implementation. |
| Tracker | Chỉ thêm dependency/evidence sau leader xác nhận. | Không tự đổi status nhóm. |
