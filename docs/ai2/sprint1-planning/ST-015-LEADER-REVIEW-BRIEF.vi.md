# Review brief — DOC-02 BRD Contract Intelligence v0.3

**Người gửi đề xuất:** Trần Văn Dũng, AI2  
**Mục đích:** xin leader review trước khi chuẩn bị bản gửi mentor.  
**Trạng thái:** Draft ready — chưa gửi/đặt lịch review thực tế.

## Tóm tắt

DOC-02 v0.3 chốt BRD cho MVP dossier PDF tiếng Việt: fact có evidence, comparison có context và HITL. Không cam kết OCR quality, model accuracy hay hiệu lực pháp lý. Gate A là planning/document review; Gate B chỉ bắt đầu khi có PDF/OCR thật, binding, audit và run log.

## Quyết định cần leader xác nhận

| ID | Quyết định | Mặc định đề xuất | Ảnh hưởng nếu chưa chốt |
|---|---|---|---|
| D-LEAD-01 | MVP language/input | PDF tiếng Việt; scan/text-layer; English/bilingual/non-PDF out of scope. | Scope/acceptance chưa freeze. |
| D-LEAD-02 | Dossier manifest | Product/BE giữ nguồn role contract/annex; AI2 không suy upload order. | Cross-document comparison blocked. |
| D-LEAD-03 | Reviewer/adjudicator | Reviewer xác nhận business outcome; leader chỉ định adjudicator. | HITL/amendment policy pending. |
| D-LEAD-04 | Semantic scope | Semantic polarity là pilot, không là legal conflict. | Không đưa vào commitment MVP. |
| D-LEAD-05 | Batch priority | Single dossier trước; batch deferred. | Không tạo commitment batch. |
| D-LEAD-06 | Gate B targets | Threshold/sample/owner chốt trước run thật. | DOC-06 chỉ có protocol, chưa có result. |

## Checklist leader review

- Scope khớp DOC-01 và non-legal boundary.
- 14 BR-ID có acceptance evidence và trace DOC-03–DOC-06.
- Decision table phân biệt match/difference/amendment/not-comparable/insufficient-evidence.
- HITL có evidence hai phía và append-only history.
- INT-01 đến INT-06 có owner và impact.
- Fixture synthetic không được mô tả như OCR/evaluation evidence.

## Artefact review

- [DOC-02 BRD v0.3](ST-015-DOC-02-BRD.vi.md)
- [Traceability register](ST-022-TRACEABILITY-AND-INTEGRATION.vi.md)
- [Decision/risk register](ST-022-DECISIONS-RISKS-REVIEW.vi.md)
- [Case catalog](ST-016-CASE-CATALOG.vi.md)
- [Data contract](ST-017-DATA-CONTRACT.vi.md)
- [Metric protocol](ST-021-METRIC-PROTOCOL.vi.md)

Chỉ chuyển `Pending leader review` khi brief/tài liệu thực sự được gửi hoặc có lịch review; khi feedback yêu cầu sửa dùng `Returned`.
