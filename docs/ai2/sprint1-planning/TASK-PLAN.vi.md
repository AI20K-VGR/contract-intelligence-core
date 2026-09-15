# Tracker cá nhân Trần Văn Dũng — Sprint 1 v0.2

Phạm vi: hoàn thiện planning AI2. Trạng thái tại lần biên soạn v0.2 ngày 15/09/2026: các bản nháp tài liệu đã có; chưa có sign-off nhóm hoặc execution thật. Ngày dưới đây là lịch đề xuất 15–20/09/2026, cần leader xác nhận khả dụng. Assignee mọi dòng là Trần Văn Dũng. Reviewer là người đề xuất, chưa xác nhận nhận việc.

## Task và bằng chứng planning

| ID | Công việc / đầu ra | Assignee | Reviewer đề xuất | Bắt đầu | Hạn | Effort giờ | Trạng thái | Dependency / điều kiện đóng |
|---|---|---|---|---|---|---|---|---|
| AI2-01 | Chốt phạm vi và cổng A/B: DOC-02-BRD.vi.md | Trần Văn Dũng | Kiều Trang | 15/09 | 15/09 | 2 | Draft ready | Yêu cầu hiện tại đã có; leader review ranh giới cá nhân/nhóm. |
| AI2-02 | Taxonomy, decision table: DOC-02-BRD.vi.md | Trần Văn Dũng | Đức Dũng | 15/09 | 16/09 | 3 | Draft ready | Sau AI2-01; walkthrough thiếu amendment vẫn giữ difference. |
| AI2-03 | Data contract và mẫu JSON: DATA-CONTRACT.vi.md | Trần Văn Dũng | Đức Dũng + Hoàng Chương | 16/09 | 17/09 | 3 | Draft ready | Sau AI2-02; review shape trước khi có OCR thật; hai refs/correction/rotation khép kín. |
| AI2-04 | Fixture design: FIXTURE-MANIFEST.vi.md | Trần Văn Dũng | Đức Dũng | 16/09 | 17/09 | 2 | Draft ready | Sau AI2-02; ba documents, hai representations, mapping case/nguồn. |
| AI2-05 | Gold design: CASE-CATALOG.vi.md + GROUND-TRUTH-LEDGER.template.md | Trần Văn Dũng | Đức Dũng | 17/09 | 18/09 | 4 | Draft ready | Sau AI2-02/04; 15 case có rationale; nhãn nội dung và binding tách riêng, chưa yêu cầu OCR citation thật. |
| AI2-06 | Audit protocol: OCR-BBOX-AUDIT-CHECKLIST.vi.md | Trần Văn Dũng | Đức Dũng + Kiều Trang | 18/09 | 18/09 | 2 | Draft ready | Sau AI2-03/05; checklist phân biệt lỗi mẫu với run không truy vết. |
| AI2-07 | Baseline/context và experiment plan: AI2-EXPERIMENT-CARD.vi.md | Trần Văn Dũng | Đức Dũng | 19/09 | 19/09 | 2 | Draft ready | Sau AI2-02/05; bảy type và manual context khai báo; không cần run để review thiết kế. |
| AI2-08 | Metrics: METRIC-PROTOCOL.vi.md | Trần Văn Dũng | Hoàng Chương | 19/09 | 19/09 | 2 | Draft ready | Sau AI2-05/06; matching một-một, classification/alerts và ví dụ tính tay rõ. |
| AI2-09 | Đồng bộ tài liệu, review closure, handoff | Trần Văn Dũng | Kiều Trang + Hoàng Chương | 20/09 | 20/09 | 4 | Draft ready | Sau AI2-01–08; tài liệu A đầy đủ, reviewer phản hồi và decision log cập nhật trước Accepted. |

Tên artifact trong bảng là bằng chứng bản nháp hiện có; chưa chứng minh task được nhóm chấp nhận. Workflow tài liệu: Draft ready → Pending review khi thực sự gửi/đặt lịch → Accepted khi có reviewer/ngày/evidence; Returned nếu cần sửa. Chưa gửi thông báo cho thành viên qua công cụ nào.

## Phân bổ thời gian dự kiến

Giả định 5 giờ/ngày × 6 ngày = 30 giờ khả dụng. Work/review chủ động 24 giờ + buffer 6 giờ. Đây là estimate, không phải timesheet đã làm.

| Ngày | Phân bổ task | Work giờ | Buffer giờ | Kết quả review dự kiến |
|---|---|---|---|---|
| 15/09 | AI2-01:2h; AI2-02:2h | 4 | 1 | Scope và taxonomy draft. |
| 16/09 | AI2-02:1h; AI2-03:2h; AI2-04:1h | 4 | 1 | Decision table, shape/fixture draft. |
| 17/09 | AI2-03:1h; AI2-04:1h; AI2-05:2h | 4 | 1 | Mẫu dữ liệu và case design. |
| 18/09 | AI2-05:2h; AI2-06:2h | 4 | 1 | Ledger schema và audit protocol. |
| 19/09 | AI2-07:2h; AI2-08:2h | 4 | 1 | Baseline và metric walkthrough. |
| 20/09 | AI2-09:4h | 4 | 1 | Handoff và phản hồi nhóm. |

Buffer dùng cho feedback/điều chỉnh. Nếu khả dụng dưới 5h/ngày hoặc reviewer trễ hơn 1 ngày, báo leader các dòng affected, giữ bản nháp bàn giao và dời Accepted; không lấy thời gian làm code bù cho task planning.

## Dependency và cổng evidence B

- Đề xuất gửi schema draft AI1/BE lúc 16:00 ngày 16/09, nhận phản hồi shape trước 12:00 ngày 17/09; chưa phải lịch được họ xác nhận.
- Mốc snapshot thử nghiệm đề xuất với AI1: 17:00 ngày 17/09. Chỉ bind/audit nguồn thật sau khi nhận. Nếu trễ, B-02/B-03 blocked; AI2-05/06 vẫn có thể review thiết kế.
- Reviewer nhãn đề xuất Đức Dũng; nếu chính người này đồng soạn nhãn thì đề xuất Hoàng Chương làm auditor độc lập. Leader xác nhận người có thời gian/năng lực phù hợp.

| B-ID | Evidence thực nghiệm | Owner đề xuất | Dependency | Trạng thái thực tế |
|---|---|---|---|---|
| B-01 | PDF + snapshots thực của ba documents/hai representations | AI1; Trần Văn Dũng hỗ trợ nội dung | Fixture được tạo, engine khai báo | Not started / chưa nhận evidence |
| B-02 | Bind facts/cases sang nguồn thật | Trần Văn Dũng | Sau B-01, gold version đóng băng | Not started |
| B-03 | Audit hai phía/cả hai representations | Reviewer nhãn đề xuất | Sau B-02 | Not started |
| B-04 | Extraction/comparison run + metric | Trần Văn Dũng ở mốc thực nghiệm được nhóm chốt | Sau B-01–03, rule version | Not started |

B-01–04 là kế hoạch phối hợp bổ sung, không cộng vào 24 giờ planning hoặc tự cam kết hoàn tất trong Sprint 1. Nếu mentor yêu cầu evidence trong Sprint 1, leader phải chốt owner/capacity/mốc B riêng. Plan Sprint 2–3 cho AI2 nằm trong experiment card.
