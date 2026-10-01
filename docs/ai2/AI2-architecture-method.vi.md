# AI2 — Phương pháp mô tả kiến trúc

**Phiên bản:** v1.0
**Ngày:** 21/09/2026
**Phạm vi:** phương pháp review và tổ chức architecture cho AI2 demo hiện tại.

Tài liệu này quy định vai trò riêng của từng chuẩn/phương pháp được tham khảo. Không coi chúng là các kiến trúc thay thế nhau và không tuyên bố dự án đã được chứng nhận theo các tiêu chuẩn đó.

## 1. Nguyên tắc chọn phương pháp

AI2 dùng một architecture description có nhiều view. Mỗi view trả lời một nhóm câu hỏi khác nhau; cùng một component có thể xuất hiện ở nhiều view nhưng phải giữ tên, boundary và trạng thái nhất quán.

Nguồn sự thật khi review theo thứ tự:

1. Code và API đang chạy.
2. Contract/schema và test hiện có.
3. Tài liệu architecture.
4. Target/production idea chỉ được ghi ở phần giới hạn hoặc hướng phát triển.

## 2. Vai trò riêng của từng nguồn

| Nguồn | Mục đích riêng trong AI2 | Sản phẩm áp dụng |
|---|---|---|
| ISO/IEC/IEEE 42010 | Khung để xác định stakeholder, concern, viewpoint, view, rationale và consistency của architecture description | `DOC-04` có context, concerns, views, decisions và known gaps |
| Kruchten 4+1 | Cách nhóm các view kỹ thuật để người đọc không phải xem một sơ đồ duy nhất quá lớn | Nhóm logical, process, development, deployment; scenarios là extraction/ask flow |
| SEI Views and Beyond | Cách viết từng view: purpose, elements, relations, constraints, rationale và consistency với view khác | Mỗi phần C0–C4, input boundary, extraction và reasoning có mục tiêu/notation/giới hạn |
| Rozanski & Woods | Catalog viewpoint và perspective để kiểm tra đủ stakeholder concern, không bỏ quên information, operation, security, performance và evolution | Context, functional, information, deployment, operational và các cross-cutting perspective |
| TOGAF / ArchiMate | Đặt AI2 trong bối cảnh enterprise và biểu diễn quan hệ business/application/technology khi cần | Chỉ dùng cho boundary với DMS/BE/AI1/NineRouter; không dùng để biến demo thành enterprise platform |
| IEEE 1016 | Kỷ luật của Software Design Description ở mức component, interface, data, behavior, dependency và traceability | `AI2-05`, API matrix, component contracts, data model và code mapping |

### 2.1. Điều không làm

- Không dùng 4+1 để thay thế C0–C4.
- Không dùng TOGAF/ArchiMate để mô tả những service production chưa tồn tại.
- Không dùng IEEE 1016 để biến architecture document thành source code listing.
- Không gọi tài liệu này là compliance/certification report.
- Không dùng một diagram duy nhất để trả lời context, runtime, data, code và policy cùng lúc.

## 3. Bộ view được áp dụng cho AI2

| View AI2 | Stakeholder chính | Concern | Cơ sở phương pháp |
|---|---|---|---|
| Context view | Product owner, reviewer | AI2 nhận gì, không nhận gì, external boundary nào | 42010, Rozanski & Woods, ArchiMate |
| Functional / pipeline view | Product, AI2 engineer | Ingest, validate, extract, graph, index proposal, ask | 4+1 logical, Views and Beyond, IEEE 1016 |
| Information / evidence view | Data/AI engineer, reviewer | Snapshot, page, node, table, fact, chunk, citation, digest | Rozanski & Woods, IEEE 1016 |
| Process / runtime view | Operator, backend engineer | Synchronous demo flow, L0–L3, policy gates, fallback | 4+1 process, IEEE 1016 |
| Development / code view | Developer | Module, route, class, dependency và code mapping | 4+1 development, IEEE 1016 |
| Deployment / boundary view | Developer, operator | Browser, Uvicorn, SQLite, blob store, NineRouter | 4+1 deployment, ArchiMate |
| Operational / policy perspective | Reviewer, security/operator | ACL/lifecycle/pins, egress, budget, vector status, audit | Rozanski & Woods perspective, 42010 rationale |
| Scenario view | Product, QA | No-table, long document, multi-source relation, missing evidence, provider failure | 4+1 scenarios, Views and Beyond |

## 4. Mapping vào tài liệu hiện tại

| Tài liệu | Vai trò |
|---|---|
| `AI2-DOC-04-architecture.vi.md` | Architecture description chính theo 42010; index toàn bộ view |
| `AI2-05-architecture.vi.md` | SDD/component view theo IEEE 1016 |
| `AI2-08-architecture-c0-c4.vi.md` | Nhóm view C0–C4 theo 4+1 và boundary theo ArchiMate |
| `AI2-10-current-flow.vi.md` | Scenario/process view theo từng bước input → xử lý → output |
| `AI2-09-ai1-snapshot-handoff.vi.md` | Contract và information view của AI1 → AI2 |
| `diagrams/*.mmd` | Sẽ được tổ chức lại trong đợt chuẩn hóa diagrams; không phải source of truth độc lập |

## 5. Quy tắc review consistency

Mỗi component/flow trong tài liệu phải truy được tới:

```text
stakeholder concern
    -> view/viewpoint
    -> diagram hoặc bảng
    -> API/module/code
    -> test hoặc known gap
```

Nếu code và tài liệu khác nhau:

- mô tả behavior đang chạy;
- ghi mismatch/known gap;
- không tự chuyển target design thành current implementation;
- cập nhật diagram và API matrix cùng một lần.

## 6. Tài liệu tham khảo

- [ISO/IEC/IEEE 42010:2022](https://www.iso.org/standard/74393.html)
- [Kruchten — Architectural Blueprints, 4+1 View Model](https://www.cs.ubc.ca/~gregor/teaching/papers/4%2B1view-architecture.pdf)
- [SEI — Views and Beyond](https://www.sei.cmu.edu/library/views-and-beyond-the-sei-approach-for-architecture-documentation/)
- [Rozanski & Woods — Viewpoint Catalog](https://www.informit.com/articles/article.aspx?p=1766161&seqNum=6)
- [The Open Group — TOGAF and ArchiMate](https://www.opengroup.org/togaf)
- [IEEE 1016-2009](https://standards.ieee.org/ieee/1016/4502/)
