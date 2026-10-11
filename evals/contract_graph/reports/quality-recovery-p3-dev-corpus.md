# P3 — Gói duyệt dữ liệu development

**Trạng thái:** `BLOCKED_REVIEW_PENDING`  
**Dataset:** `quality-recovery-dev-20261011-v1`  
**Frame:** `contract-graph-quality-frame/1`

## Nội dung gói

- Phiếu gán nhãn mù chính: 600 cặp; phân tầng nguồn × pool stratum, không có nhãn gợi ý từ model.
- Phiếu kiểm tra độc lập mù: 150 cặp (25%), chọn trước khi người gán nhãn chính trả kết quả. Người gán nhãn thứ hai phải là người khác.
- Cả hai CSV chứa văn bản điều khoản và chỉ nằm trong `.harness/state/quality-recovery-p3-dev-20261011/`; không đưa văn bản hay membership ID vào Git.
- Seed `precision_frame` hiện chia sẻ 600 membership recall với `role=both`, để giữ manifest schema P2 nhất quán. Đây chưa phải candidate union; P4 phải bổ sung và review các candidate mới trước khi chấm precision.
- Rubric: `evals/contract_graph/pairs/LABELING.vi.md`. Với mỗi dòng, điền `decision=label` và nhãn đóng; GENERAL_SPECIFIC/REFERENCE cần `direction=A|B`. Chọn `decision=reject` nếu cặp không dùng được. Không điền theo gợi ý model.

## Kiểm tra nguồn và mẫu

Trong tranche có 29 tài liệu và 4.810 cặp trong pool. So cluster cả tranche với held-out lịch sử tìm thấy một tài liệu thuộc cụm đã exposed; loại tài liệu/cụm đó. Còn 28 tài liệu, 28 cụm fresh và 4.770 cặp pool: S1 3.500, S2 200, S3 1.070. Mẫu chính gồm 600 cặp; phiếu độc lập gồm 150 cặp.

P2 xác định mục tiêu planning tối thiểu 30 cụm độc lập để có khả năng đạt Wilson cluster lower `>=0.85`; tranche hiện chỉ có 28 cụm. Ngưỡng không bị hạ. Pool là finite frame sau khi loại cặp ancestor–descendant và cặp đã có cạnh luồng 1; `pi` trong membership ngoài Git gồm xác suất pool selection và review sampling.

## Gate còn mở

- Chưa có annotation hoặc quyết định nào. Số positive/negative được duyệt, direction, tỷ lệ đồng thuận và adjudication đều chưa biết.
- Reviewer thứ hai chưa xác định; phiếu 150 dòng chỉ là mẫu mù ban đầu. Sau khi có annotation chính, phải kiểm tra subset đã phủ đủ từng nhãn, negatives và mọi cặp ambiguous; tạo blind top-up nếu thiếu.
- Chưa có precision candidate union; P4 phải lập phần mở rộng sau khi corpus được duyệt và trước model scoring.
- Chưa có HG-QR1 receipt, approved gold hay P2 `review_lock`. File `quality-recovery-manifest.v1.json` là **review-packet manifest draft**, không phải manifest dataset P2 có thể đọc.

## Review cần thực hiện

1. Người gán nhãn chính hoàn thành `primary-blind-v1.csv`.
2. Một reviewer độc lập hoàn thành `independent-blind-v1.csv` mà không xem phiếu/kết quả của người thứ nhất.
3. Gửi lại hai CSV đã điền và chỉ rõ reviewer ID/role; các disagreement sẽ được tách thành packet adjudication.
4. Sau kiểm tra scope/count/hash và quyết định adjudication, người dùng xác nhận HG-QR1 cụ thể. Chỉ sau đó mới tạo P2 quality dataset manifest và review lock.

## Hashes

- Rubric: `a2a2c5e507b831164034aad5f3fcb17d25f89205c5e01c2fa3901ee56122ecb4`
- Primary packet: `7d417daed123ad50f961b950bd9d6316f10015982bd86164b9257816bf4d765a`
- Independent packet: `138df5af62b1eea19aa3e606c7413c7e09a9b5f7a6a317fe6e87d8fc38631442`
- Recall membership: `6c65a30a2a693f2ac700f3c4151dfd723aef5d803eda8af1799fe01c3be2fdfa`
- Independent membership: `c1f5cce276e6eb45582af4accff7dda9de592a2f89744a0467114a998817c72f`
- Seed precision membership: `e01595f8e22222b73c84f0496bfc4510ac6d4b73b90d4cb958cd607040567664`
