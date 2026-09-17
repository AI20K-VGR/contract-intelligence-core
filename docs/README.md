# Contract Intelligence Documentation

## Nguồn chuẩn

| Tài liệu | Nội dung |
|---|---|
| [DOC-01](DOC-01-product-vision.md) | Product vision, phạm vi và nguyên tắc evidence-first. |
| [DOC-02](DOC-02-brd.md) | Business rules, fact/finding taxonomy và acceptance. |
| [DOC-03](DOC-03-prd.md) | User journey, functional/non-functional requirements. |
| [DOC-04](DOC-04-architecture.md) | System architecture, ownership, long-document OCR/IDP lifecycle, security và optimization plane. |
| [DOC-05](DOC-05-api-spec.yaml) | OpenAPI contract. |
| [DOC-06](DOC-06-eval-report.md) | Evaluation protocol, report và promotion gates. |
| [AI2 pipeline](AI2-IDP-OPTIMIZATION-PIPELINE.md) | Luồng OCR ↔ IDP ↔ targeted re-OCR có sơ đồ. |
| [Contracts](contracts/README.md) | Wire/semantic contracts hiện hành. |

Quy tắc authority, metadata, change record và archive policy nằm tại [DOCUMENT-GOVERNANCE.md](DOCUMENT-GOVERNANCE.md). DOC-01/02 quyết định product scope/business semantics; DOC-04 chỉ quyết định technical lifecycle; DOC-05 quyết định public API; JSON schema quyết định wire shape.

## Lịch sử

Tài liệu Sprint 1, pipeline tuần tự cũ và snapshot v1 đã được giữ nguyên trong [archive/](archive/). Chúng chỉ phục vụ audit/migration, không được dùng làm contract hoặc thiết kế triển khai mới.
