# Sprint 1 — bộ tài liệu AI2 hiện hành

**Owner:** Trần Văn Dũng — AI2  
**Trạng thái:** `Draft ready`; chưa có leader/mentor sign-off, OCR thật hoặc Gate B evidence.  
**Nguồn chuẩn:** Các tài liệu tiếng Việt trong danh sách dưới đây.

Thư mục này chỉ giữ tài liệu đang dùng cho phần AI2. Lịch sử review, patch và bản Anh v0.2 được chuyển sang [`archive/`](archive/) để bảo toàn evidence nhưng không dùng làm nguồn nộp.

## Bộ nộp leader hiện tại

| Tài liệu | Mục đích | Trạng thái |
|---|---|---|
| [DOC-02-BRD.vi.md](DOC-02-BRD.vi.md) | BRD AI2: MVP PDF tiếng Việt, 14 BR-ID, business rules, evidence và HITL. | Draft ready |
| [AI2-PRD-CONTENT.vi.md](AI2-PRD-CONTENT.vi.md) | Contribution AI2 để owner DOC-03 PRD chung hợp nhất. | Draft ready |
| [AI2-SAD-CONTENT.vi.md](AI2-SAD-CONTENT.vi.md) | Contribution AI2 cho DOC-04 Architecture/SAD chung. | Draft ready |
| [DATA-CONTRACT.vi.md](DATA-CONTRACT.vi.md) | Contract dữ liệu/provenance để AI1, BE và FE review. | Draft ready |
| [AI2-TRACEABILITY-AND-INTEGRATION.vi.md](AI2-TRACEABILITY-AND-INTEGRATION.vi.md) | Mapping BRD → PRD → Architecture → evaluation và dependency liên nhóm. | Draft ready |
| [DOC-02-LEADER-REVIEW-BRIEF.vi.md](DOC-02-LEADER-REVIEW-BRIEF.vi.md) | Một trang quyết định/checklist gửi leader. | Draft ready |
| [DECISIONS-RISKS-REVIEW.vi.md](DECISIONS-RISKS-REVIEW.vi.md) | Quyết định, risk, reviewer và sign-off register. | Draft ready |
| [TASK-PLAN.vi.md](TASK-PLAN.vi.md) | Tracker cá nhân AI2; ngày/effort là đề xuất, không là timesheet. | Draft ready |

## Phụ lục thiết kế và Gate B

Các artefact dưới đây hỗ trợ review thiết kế hoặc evaluation sau này; không phải bằng chứng OCR/model run thật.

| Tài liệu | Dùng khi |
|---|---|
| [CASE-CATALOG.vi.md](CASE-CATALOG.vi.md) | Review taxonomy và decision table C01–C15. |
| [FIXTURE-MANIFEST.vi.md](FIXTURE-MANIFEST.vi.md) | Chuẩn bị fixture tự soạn, an toàn dữ liệu. |
| [GROUND-TRUTH-PLAN.vi.md](GROUND-TRUTH-PLAN.vi.md) | Thiết kế gold/adjudication. |
| [GROUND-TRUTH-LEDGER.template.md](GROUND-TRUTH-LEDGER.template.md) | Ghi gold, binding, run và revision sau khi có nguồn thật. |
| [AI2-EXPERIMENT-CARD.vi.md](AI2-EXPERIMENT-CARD.vi.md) | Chốt baseline/context experiment. |
| [OCR-BBOX-AUDIT-CHECKLIST.vi.md](OCR-BBOX-AUDIT-CHECKLIST.vi.md) | Audit sau khi nhận snapshot/PDF thật. |
| [METRIC-PROTOCOL.vi.md](METRIC-PROTOCOL.vi.md) | Đo DOC-06 sau Gate B, bắt buộc có `n`, denominator và version. |
| [DATA-CONTRACT-EXAMPLE.vi.json](DATA-CONTRACT-EXAMPLE.vi.json) | Ví dụ synthetic; không phải OCR output. |

## Tài liệu chung và điểm còn thiếu

- [DOC-01 Product Vision](DOC-01-PRODUCT-VISION.vi.md) là tài liệu chung của cả team, không phải deliverable riêng AI2.
- **DOC-06 Evaluation Report thực tế chưa tồn tại và chưa được phép tự tạo số liệu:** cần PDF/OCR thật, binding, audit và run log ở Gate B.
- DOC-03/04/05 chính thức là tài liệu toàn nhóm. AI2 chỉ bàn giao contribution PRD/SAD và requirements/data contract liên quan.

## Cách dùng

1. Gửi leader review brief, DOC-02, AI2 PRD, AI2 SAD, data contract và traceability register.
2. Chỉ đổi trạng thái sang `Pending review` khi đã gửi hoặc có lịch review thật; lưu link bằng chứng trong decision register.
3. Dùng phụ lục Gate B sau khi AI1/BE/FE và leader chốt dependency tương ứng.
4. Không dùng nội dung trong `archive/` để báo cáo tiến độ hoặc làm nguồn chuẩn.
