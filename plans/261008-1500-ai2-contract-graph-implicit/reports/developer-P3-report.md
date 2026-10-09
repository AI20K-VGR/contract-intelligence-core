# P3 — triển khai và kiểm chứng

Triển khai model, classifier, builder, trace `served_model`, predictor và CLI theo phase 3. `pair_candidates.py` không đổi; `PROMPT_VERSION=pairs-v1`, vòng tune 0.

Developer ghi nhận RED trước triển khai: classifier/builder 2 collection errors; predictor 1 collection error; client trace 2 failed/1 passed. GREEN tập trung sau sửa: 102 test ai-service (gồm golden flag-off), 16 test predictor. Lint theo cấu hình dự án sạch. Nguồn RED/GREEN tập trung: thông báo của developer trong phiên; lead chạy regression độc lập dưới đây.

Lead chạy suite ai-service: `13 failed, 1440 passed, 9 skipped` (78.27s), đúng 13 lỗi baseline trong HANDOFF; sáu lỗi cô lập môi trường đã được sửa bằng fixture xóa env pairs của test fake. Log cục bộ: `tmp/p3-full-final.log`. Evals: `161 passed` (6.98s), log `tmp/p3-eval-final.log`.

Probe production: `ag/claude-sonnet-4-6` trả `claude-sonnet-4-6`, family `anthropic`, JSON hợp lệ, 4.265s, 2176/20 token; xem `p3-production-probe.json`. Dev: 11 quan hệ/7 văn bản, 9 lời gọi; một DUPLICATE khác gold GPT chưa được duyệt. Báo cáo tổng hợp lưu `evals/contract_graph/reports/l2-p3-classifier-dev.{json,md}`, có k/n, Wilson và khoảng theo cụm. Giữ cờ mặc định tắt.

Review độc lập vòng đầu phát hiện đường gold held-out và khoảng tổng theo cụm; code/test đã sửa, lead kiểm chứng regression xanh. Lượt recheck độc lập và simplifier không hoàn tất do agent bị giới hạn sử dụng. Đây là phần review còn mở; chưa được xem là PASS cuối toàn kế hoạch.

Cập nhật sau retry: review độc lập tại bffe37e3 PASS, F1/F2 đã được recheck bằng probe; 93 test ai-service + 16 eval xanh, ruff sạch, khoảng theo cụm tái tính khớp. Xem reviewer-P3-report.md. Simplifier giữ code do chưa có lợi ích đủ rõ để thêm abstraction. Giới hạn agent đã được khắc phục bằng lượt retry; review toàn nhánh P4/P5 vẫn chưa chạy.
