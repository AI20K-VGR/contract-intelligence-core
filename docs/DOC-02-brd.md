# DOC-02 · Business Requirements Document

## Contract Intelligence — OCR · IDP · Bounding Box · Trích dẫn cho Hợp đồng và Phụ lục

| Trường | Nội dung |
|---|---|
| Dự án | VSF OJT Batch 3 |
| Mã / trạng thái | DOC-02 / Draft — Ready for Review |
| Phiên bản | 0.2 — Bản nháp · Sprint 1 |
| Ngày tạo / cập nhật | 15/09/2026 · 16/09/2026 |
| Người phụ trách | Trần Văn Dũng |
| Người tham gia | Cả team |
| Reviewer / effective-review date | Mentor / 16-09-2026 · TBD |
| Upstream / thay thế | DOC-01 / Không có |
| Downstream | DOC-03, DOC-04, DOC-05, DOC-06, contracts |

## 0. Thuật ngữ

- **Fact:** giá trị typed trích từ tài liệu, gồm raw, normalized, context và citation.
- **Finding:** kết quả so sánh kỹ thuật có đúng một disposition wire canonical: `COMPARABLE_MATCH`, `COMPARABLE_DIFFERENCE`, `CANDIDATE_AMENDMENT`, `NOT_COMPARABLE`, `INSUFFICIENT_EVIDENCE`; không là kết luận pháp lý. UI có thể hiển thị nhãn thường.
- **Conflict:** tên product/UI/API cho tập finding cần reviewer xử lý; không phải pipeline/entity riêng và không phải mọi finding là xung đột.
- **Worker state:** OCR, structuring và checking là trạng thái nội bộ; UI chỉ hiển thị trạng thái dossier/job tổng hợp.

## 1. Tóm tắt

Contract Intelligence xử lý một dossier gồm một hợp đồng thương mại và `0..n` phụ lục. Hệ thống nhận PDF có text layer hoặc scan, chuyển chúng thành dữ liệu có cấu trúc và duy trì trace chính xác từ output về tài liệu nguồn.

Năng lực gồm intake, phân loại PDF, OCR, clause/table extraction, bounding box, citation, structured/semantic finding, HITL và single/batch processing. Giá trị không dừng ở OCR: sản phẩm phải tạo điều khoản có cấu trúc, citations, bounding boxes và findings để reviewer kiểm chứng.

## 2. Bối cảnh và phát biểu vấn đề

Doanh nghiệp thường có hợp đồng chính cùng phụ lục thay đổi giá, số lượng, giao hàng, thanh toán, thời hạn, parties, mã số thuế, chi nhánh hoặc nghĩa vụ. Người kiểm tra hiện phải tự đọc hàng chục/hàng trăm trang, tìm điều khoản, so sánh nhiều tài liệu, xác định thay đổi và quay lại source. Điều này tốn công, khó mở rộng, dễ bỏ sót hoặc hiểu sai thông tin không nhất quán.

Hệ thống cần chuyển hợp đồng/phụ lục thành thông tin có cấu trúc, truy vết được và được con người kiểm tra lại.

## 3. Mục tiêu nghiệp vụ

| ID | Mục tiêu |
|---|---|
| BO-01 | Giảm công sức đọc và so sánh hợp đồng/phụ lục thủ công. |
| BO-02 | Cấu trúc hóa Điều, Khoản, Điểm, phụ lục, bảng và contractual facts. |
| BO-03 | Truy vết fact/finding theo `Tài liệu → Trang → Dòng OCR → Khoảng ký tự → Bounding Box`. |
| BO-04 | Phát hiện finding structured và semantic trong một tài liệu, contract–annex, annex–annex. |
| BO-05 | Cho phép HITL confirm, correct, reject và, từ Sprint 2–3, chỉnh bbox mà không xóa output máy. |
| BO-06 | Đo OCR, bbox, citation, finding, throughput và cost, luôn kèm sample/denominator. |

## 4. Phạm vi

### Trong phạm vi

- Hợp đồng thương mại, mua bán, dịch vụ, khung, thuê và phụ lục.
- PDF có text layer và PDF scan; phát hiện loại input theo từng trang.
- **Must:** tiếng Việt. **Should:** tiếng Anh/song ngữ trên bộ mẫu, không cam kết production đa ngữ.
- Output gồm structured clauses, values, tables/rows, bbox, citations, findings và kết quả review.

### Ngoài phạm vi

- Tư vấn pháp lý, xác minh chữ ký, chỉnh PDF gốc, handwriting nâng cao.
- Train OCR/foundation model riêng, DMS/enterprise IAM hoàn chỉnh, Kubernetes, microservice phân tán, chatbot pháp lý tổng quát.
- Cam kết SLA/quality/cost production trước khi có benchmark/evidence.

## 5. Stakeholders

| Vai trò | Trách nhiệm |
|---|---|
| Human reviewer | Kiểm clause/value/finding/citation, sửa dữ liệu sai, chỉnh bbox ở phạm vi Should. |
| Operator | Upload contract/annex, khởi chạy/theo dõi job, xem kết quả và retry khi được phép. |
| Team phát triển | OCR, structure, bbox, citation, finding, HITL, background processing và evaluation. |
| Mentor | Review capability, architecture, sprint deliverables, evaluation, cost/throughput và scope discipline. |

## 6. Yêu cầu nghiệp vụ

### Intake, OCR và cấu trúc

| ID | Yêu cầu |
|---|---|
| BR-01 | Xử lý một dossier: `1 CONTRACT + 0..n ANNEX`; các tài liệu được liên kết logic qua manifest/metadata được xác nhận. |
| BR-02 | Phân loại mỗi trang `TEXT_LAYER`, `SCANNED_OCR` hoặc `MIXED` và chọn xử lý phù hợp. |
| BR-03 | OCR/trích text cho scan và text layer; lưu text, confidence khi có, page/word/line geometry và giữ đúng dấu tiếng Việt. |
| BR-04 | Nhận diện hierarchy `Điều → Khoản → Điểm`, phụ lục, bảng và hàng bảng; bảng không được là text blob. |
| BR-05 | Clause node có identifier, title nếu có, text, trang nguồn và clause-region bbox. |
| BR-06 | Operator có thể khai báo quan hệ annex trong manifest để chạy workflow, nhưng cross-document comparison/amendment candidate chỉ dùng `SOURCE_EVIDENCE` citation hoặc declaration đã được reviewer xác nhận; không suy kết quan hệ pháp lý chỉ từ filename/upload order. |

### Citation và Bounding Box

| ID | Yêu cầu |
|---|---|
| BR-07 | Mọi value/finding cần citation resolve được theo document, page, OCR line, character span và bbox. |
| BR-08 | Human correction giữ machine result, correction, citation, reviewer và timestamp; không mất provenance. |
| BR-09 | Hỗ trợ bbox word, line, clause region. |
| BR-10 | Bbox normalized `0..1`, origin top-left; lưu kích thước/rotation và render được trên ảnh trang gốc. |

### Findings và HITL

| ID | Yêu cầu |
|---|---|
| BR-11 | Phát hiện khác biệt structured: price, quantity, date, duration, party, tax code, referenced contract number. |
| BR-12 | Phát hiện semantic candidate, ví dụ điều khoản thanh toán 30 ngày so với 15 ngày; không là kết luận pháp lý. |
| BR-13 | So sánh within-document, contract–annex và annex–annex khi đủ context/evidence. |
| BR-14 | Finding cross-document cite được hai phía. |
| BR-15 | UI có dossier/status/page image/clause/fact/finding/citation/bbox highlight. |
| BR-16 | Review actions: Confirm, Correct, Reject, Needs-more-evidence; approve dossier là hành động cấp dossier riêng. |
| BR-17 | Chỉnh bbox là Should Sprint 2–3; review overlay không overwrite OCR bbox. |

### Single, batch và status

| ID | Yêu cầu |
|---|---|
| BR-18 | Single dossier qua UI/API trả job ID, trạng thái và kết quả. |
| BR-19 | Batch có background execution, retry, failure handling và summary `Done`, `Failed`, `Needs Review`. |
| BR-20 | UI lifecycle tổng hợp: uploaded → processing → extracted → pending_review → reviewed → approved/failed; job không được biến mất im lặng. |

## 7. Non-functional requirements

| ID | Yêu cầu |
|---|---|
| NFR-01 | Demo local khởi động được trên laptop theo README đơn giản. |
| NFR-02 | Đo và công bố giới hạn trang/document, annex/dossier, dossier/batch và thời gian xử lý. |
| NFR-03 | Báo cost/dossier, thời gian/dossier và ước tính 1.000 dossier/tháng khi có số đo. |
| NFR-04 | Sample mentor chỉ ở OneDrive/máy được phép, không commit/public; external OCR/AI phải khai báo trong architecture. |
| NFR-05 | Lưu machine result, human correction, reviewer và review time; không silent overwrite. |
| NFR-06 | Ưu tiên đơn giản, rõ ràng, dễ bàn giao, local và tránh over-engineering. |

## 8. Dữ liệu và đánh giá

Team xây sample dataset hợp pháp từ template public hoặc tài liệu tự tạo, bao phủ text-layer, clean/low-quality scan, Việt/Anh/song ngữ, bảng, phụ lục, skew, blur, low contrast và compression noise. Ground truth, khi phù hợp, gồm text, critical fields, bbox, hierarchy và finding labels.

Đánh giá phải báo OCR (CER/WER/critical-field/diacritic), bbox (IoU/hit rate theo word/line/clause), citation validity, finding precision/recall/F1 theo scope/family, throughput và cost. Metric cụ thể, matching, denominator và Gate B được chuẩn hóa trong [DOC-06](DOC-06-eval-report.md).

## 9. Giả định, ràng buộc và rủi ro

- Nội dung chủ yếu là in; handwriting không phải yêu cầu chính; human review vẫn cần cho kết quả không chắc chắn.
- Baseline local-first; external AI cần approval và được chọn theo accuracy/speed/cost đo được.
- Development/demo trên laptop CPU, GPU free tier khi cần, phải demo local và báo cost.
- Rủi ro chính: scan xấu, sai dấu tiếng Việt, sai critical number, external cost và over-engineering. Hướng xử lý là benchmark/preprocess, diacritic/critical-field evaluation, evidence/review queue, local baseline, đo trước khi tăng complexity.

## 10. Tiêu chí thành công và quyết định mở

Đến hết OJT, hệ thống cần chứng minh scan/text-layer OCR, Việt/Anh trên scope đã đo, clause hierarchy, contract–annex linkage, structured table, citation/bbox, reviewer correction, structured/semantic demo, single/batch, metrics và local demo. Đây không phải AC của demo Sprint 1.

Các quyết định còn mở: OCR engine/fallback, render DPI, preprocess, table extraction, semantic taxonomy, contract–annex precedence, batch concurrency/limit, external provider và cost. Quyết định triển khai hiện hành được ghi tại [DOC-04](DOC-04-architecture.md), API ở [DOC-05](DOC-05-api-spec.yaml), và wire contracts ở [contracts](contracts/README.md).

## 11. Phê duyệt

| Vai trò | Chữ ký / Tên | Ngày |
|---|---|---|
| Người chuẩn bị | — | — |
| Người review | — | — |
| Người phê duyệt | — | — |
