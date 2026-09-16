# Đính chính EOD — 15/09/2026

## Kết luận có thể kiểm chứng

Tại EOD 15/09, bằng chứng GitHub chỉ xác nhận rằng các **bản nháp planning** đã được đưa vào repository. Nó không xác nhận các ticket đã được hoàn thiện, được review/accepted, hay đã có OCR/evaluation thực tế.

- `70d55d8` (15/09 16:19 +07): thêm 17 tài liệu planning drafts.
- `062ef34` (15/09 16:38 +07): chỉ tổ chức/đổi tên các file theo mã task; không phải bằng chứng hoàn thành nội dung mới.
- `9d63c4e` (15/09 16:50 +07): chỉ đổi tên `README.vi.md` thành `README.md`; không phải bằng chứng hoàn thành nội dung mới.

Trạng thái chính thức vẫn phải lấy từ tracker của nhóm. Bản tracker cá nhân trong thư mục này dùng trạng thái `Draft ready` và nói rõ chưa có sign-off nhóm hoặc execution thật.

## Cách báo cáo đã hiệu chỉnh

| Ticket và đầu ra được giao | Cách nói được phép tại EOD 15/09 | Không được suy diễn thành |
|---|---|---|
| ST-014 — đóng góp DOC-01: Users + Out of scope | DOC-01 có mục `Users` và `What is out of scope`; có thể nói đã có bản nháp phần đóng góp. | Đã hoàn tất toàn bộ DOC-01, hoặc đã gửi Leader, nếu không có link/message/lịch review. |
| ST-015 — DOC-02 BRD, phạm vi và cổng A/B | Có BRD draft nêu scope, workflow reviewer, success criteria và Gate A/B. | BRD đã được chốt/Done khi tracker còn In Progress hoặc chưa có sign-off. |
| ST-016 — taxonomy + decision table | Có taxonomy/decision table trong BRD và case catalog draft. | Taxonomy đã được leader/reviewer chấp nhận. |
| ST-017 — JSON fact/provenance | Có data-contract draft và ví dụ synthetic để AI1/AI2/BE review. | Contract đã freeze, có JSON Schema production, hoặc đã tích hợp. |
| ST-018 — fixture/context | Có fixture manifest ở mức thiết kế. | Fixture đã chạy với dữ liệu/OCR thật. |
| ST-019 — case catalog + ground-truth ledger | Có case catalog, ground-truth plan và ledger template. | Gold đã được gán nhãn/adjudicate hoặc có kết quả đo. |
| ST-020 — audit OCR/bbox | Có checklist audit; audit/run vẫn chờ OCR snapshot có bbox từ AI1. | Đã audit bbox hoặc đã có evidence Gate B. |
| ST-021 — experiment + metric protocol | Có experiment card và metric protocol ở mức thiết kế. | Baseline/metric đã chạy hoặc có số liệu. |
| ST-022 — review closure + handoff | Có handoff và các tài liệu liên kết, sẵn sàng để gửi review. | Đã đóng review/handoff hoặc đã hoàn tất cả pack trước hạn/sign-off. |

## Mẫu EOD thay thế

> Đã đưa lên repository các bản nháp planning cho ST-014–ST-022. Với ST-014, bản nháp có phần Users và Out of scope; việc gửi Leader cần link/message hoặc lịch review riêng. Đây là đầu vào cho review, không phải xác nhận các ticket đã Done. Theo tracker nhóm: ST-014 đã Done (Vision đã liên kết); ST-015–ST-022 vẫn In Progress theo từng hạn. Riêng ST-020 đang chờ AI1 cung cấp OCR snapshot có bbox để thực hiện binding/audit. Không có claim về OCR run, bbox audit, metric, review closure hoặc sign-off.

## Hành động tiếp theo

1. Giữ nguyên trạng thái tracker do owner/leader quản lý; chỉ cập nhật khi có bằng chứng review/acceptance tương ứng.
2. Gửi từng artefact draft kèm yêu cầu review và ghi nhận reviewer, thời điểm, phản hồi, quyết định.
3. Khi nhận OCR/bbox thật, tạo bằng chứng B-01 đến B-04 theo `ST-022-TASK-PLAN.vi.md`; không dùng fixture/synthetic example để thay thế.
