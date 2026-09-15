# Kế hoạch ground truth v0.2

Nguồn chuẩn nội dung tình huống: [ST-016-CASE-CATALOG.vi.md](ST-016-CASE-CATALOG.vi.md). Schema ledger: [ST-019-GROUND-TRUTH-LEDGER.template.md](ST-019-GROUND-TRUTH-LEDGER.template.md). Đây là thiết kế nhãn; gán nhãn thật và chạy model còn chưa thực hiện.

## Cỡ mẫu dự kiến và đơn vị đếm

- Một dossier nội dung, ba document (contract, annex-01, annex-02).
- `n_representation_types=2`: `text_layer`, `scanned`; không dùng biến này đếm số lần chạy.
- `n_logical_cases=15`: C01–C15; 12 structured, 3 semantic.
- `n_planned_case_representation=30` mỗi evaluation round (15 × 2). Đây là 30 tổ hợp dự kiến, không phải 30 mẫu độc lập hoặc giới hạn tổng output.
- `n_rounds`, `n_executed_case_representation`, `n_output_records`, `n_gold_facts`, `n_audited_facts`, `n_audited_logical_cases`, `n_audited_bindings` chỉ ghi số thực đo khi thực hiện. Hiện không có run evidence.
- Duplicate prediction làm tăng output records; rerun tạo round/run ID mới, không sửa kết quả cũ. Hai representations không được chia ngẫu nhiên sang train/test rồi coi độc lập.

## Quy trình nhãn và evidence

1. Trần Văn Dũng soạn logical facts/cases từ nguồn tự soạn, ghi expected disposition và rationale trước extraction.
2. Reviewer đọc nguồn và đề xuất sửa bằng label revision; chỉ nhãn đã adjudicated mới dùng làm gold đo lường. `label_review_status` riêng với HITL `review_state`.
3. AI1 cung cấp PDF/snapshot sau đó mới bind logical fact sang `fact_id`, `snapshot_id`, document/page/line/span/bbox của mỗi representation. OCR hỏng không làm thay đổi gold nội dung; binding có thể ghi missing/unreadable.
4. Evaluation round đóng băng gold version và snapshots. Prediction lưu riêng cùng run/rule version; không copy prediction vào expected disposition.
5. Đối chiếu theo [ST-021-METRIC-PROTOCOL.vi.md](ST-021-METRIC-PROTOCOL.vi.md), audit có ghi actor, ngày và disagreement.

## Audit dự kiến

Audit nội dung tối thiểu `ceil(0.2 × 15)=3` logical cases; chọn trước C02, C13, C15 để phủ amendment, OCR thiếu và ngoại lệ semantic. Kiểm tra cả hai phía trên cả hai representations khi có bindings: 6 case-representation, tối đa 12 phía nguồn. Ngoài ra audit tối thiểu `ceil(0.2 × n_gold_facts)` logical facts, thêm mẫu theo type nếu mẫu trên chưa đủ. Ghi riêng số fact, case, binding thực sự đã xem và bindings bị thiếu.

Đây là tập phát triển có chủ đích dùng để thiết kế rule. Kết quả trên tập này không đo khả năng khái quát hóa. Planning nghiệm thu bằng catalog, schema, protocol và lịch; audit thực tế là cổng evidence riêng.
