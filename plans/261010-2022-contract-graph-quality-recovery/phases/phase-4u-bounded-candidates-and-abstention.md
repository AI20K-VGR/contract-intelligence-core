# P4U — Giới hạn candidate work và phân loại abstain

## Mục tiêu

Đóng hai lỗi review trên implementation P4T mà không chạy corpus, model hay held-out: giới hạn công việc của nguồn `VALUE_MISMATCH` trước top-K, và giữ event `abstained` thành failure class riêng trong diagnostic. Expose bộ đếm abstention qua runtime coverage để không gộp nó vào `no_answer`.

## Phạm vi

- Giới hạn số cặp VALUE_MISMATCH mỗi inverted posting bằng cửa sổ deterministic; ghi số lần so sánh để kiểm chứng bound.
- Diagnostic nhận `abstained` và phân loại là `classifier_abstained`.
- Projection trả counter `abstentions` theo cặp với default zero.
- Không thay đổi schema wire, bật runtime, chạy model hoặc đọc evaluation data.

## Kiểm chứng

- Synthetic stress test chứng minh số so sánh tăng theo kích thước đầu vào nhân cửa sổ posting, không theo toàn bộ tổ hợp cặp.
- Unit test event abstained và projection counter.
- Regression các suite candidate/classifier/projection/diagnostic, lint và diff check.

## Trạng thái

Snapshot P4T giữ nguyên làm lịch sử; verification P4U là kết quả cho các sửa đổi bổ sung này.
