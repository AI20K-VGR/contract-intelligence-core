# Documentation Governance

## Authority theo lĩnh vực

| Lĩnh vực | Authority | Quy tắc |
|---|---|---|
| Vision, scope, out-of-scope | DOC-01 | Không tài liệu downstream nào được mở rộng hoặc phủ định scope này. |
| Personas, business rule, OJT requirement | DOC-02 | Lifecycle nghiệp vụ và acceptance phải giữ trace tới BR-ID. |
| Product behavior và UX acceptance | DOC-03 | Cụ thể hóa DOC-01/02, không thay business semantics. |
| Ownership, worker/run, persistence | DOC-04 | Chỉ quyết định implementation/internal lifecycle. |
| Public HTTP API | DOC-05 | Mọi endpoint/enum public phải khớp product và contracts. |
| Wire/event shape | `contracts/` | JSON Schema là shape chính xác; API dùng DTO adapter được ghi rõ. |
| Metric, quality claim, promotion | DOC-06 | Không claim quality nếu thiếu report fields bắt buộc. |

Khi có mâu thuẫn, ghi ADR/change record với owner, ngày, lý do, requirement bị ảnh hưởng và các tài liệu phải sửa. Downstream được refine nhưng không được override upstream.

## Metadata chuẩn

Mọi canonical DOC-01…DOC-06 có: document ID/title, version, status, owner, contributors, reviewer, effective/review date, upstream dependencies và tài liệu bị thay thế. `Draft — Ready for Review` không là production/evaluation sign-off.

## Archive policy

Canonical docs không link vào archive, trừ một link gắn nhãn `legacy/audit compatibility`. Archive phải có manifest mapping path cũ, canonical replacement, reason, date và compatibility window.
