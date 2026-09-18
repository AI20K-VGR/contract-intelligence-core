# Checklist audit OCR/bbox v0.2

Đây là protocol audit. Bản hiện tại chưa phải audit result vì chưa có input từ AI1/BE. Owner audit đề xuất theo TASK-PLAN.vi.md. Khi chạy phải ghi run/round ID, gold version, representation, document/snapshot IDs, source digest, engine/version, auditor, timestamp và đường dẫn PDF/render.

## Gate truy vết

| Kiểm tra | Kết quả cần điền | Evidence |
|---|---|---|
| Nguồn PDF/render có thể mở và khớp digest/snapshot | pending / pass / fail | path + digest |
| Page 1-based, width/height/frame/rotation khai báo | pending / pass / fail | snapshot metadata |
| Word/line/clause/table refs có đích khi áp dụng | pending / pass / fail / not_applicable | IDs + screenshot/ghi chú |
| Span code points lấy đúng raw text, không normalize trước | pending / pass / fail | raw/span/value |
| Bbox nằm trên upright page và highlight đúng nguồn | pending / pass / fail | overlay evidence |

Không có nguồn hoặc snapshot xác định → run unverifiable, chưa tính citation validity như đã audit. Một citation hỏng trên run có nguồn rõ → ghi failed binding/citation, giữ trong số lỗi, audit các mẫu còn lại. Không xóa cả run chỉ vì OCR sai một chữ.

## Mẫu audit đã lên kế hoạch

C02,C13,C15: ba logical cases, hai phía/cả hai representations; tối đa 12 phía nguồn, ghi từng phía bị missing. Thêm facts để đủ ceil(20% × n_gold_facts). Ghi riêng audited_facts, audited_logical_cases, audited_bindings và missing/unreadable; không gộp thành một n_audited.

## Error log cần điền khi chạy

| Round / snapshot / case / side | Hạng mục | Expected | Observed | Pass/fail | Reason / reviewer / evidence |
|---|---|---|---|---|---|
| Chưa chạy | pending | Theo gold/source | Chưa quan sát | pending | Chưa audit |

Lỗi OCR dấu/số, unit, text song ngữ, table association là kết quả phải ghi nhận. Baseline dùng tập phát triển nên kết quả chỉ hỗ trợ feasibility; không suy rộng chất lượng corpus thực tế.

## Gate đóng ST-020

Không chuyển ticket sang Done chỉ vì checklist đã được viết. Cần có PDF/render và snapshot thật, audit log cho từng case/side, evidence link tới raw text và overlay bbox, cùng reviewer/date. Nếu input chưa đến, giữ `In Review / Blocked by input evidence` và ghi rõ owner cung cấp input.
