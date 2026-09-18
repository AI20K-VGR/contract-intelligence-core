# ST-020 — Trạng thái audit OCR/bbox

**Trạng thái: In Review / Blocked by input evidence (18/09/2026).**

Chưa nhận được PDF nguồn, page render, OCR snapshot có digest, hoặc run ID từ AI1/BE. Vì vậy chưa có phép đo nào để gán `pass` hay `fail` một cách kiểm chứng được; checklist hiện vẫn là protocol, không phải kết quả audit. ST-020 chưa thể chuyển Done ở trạng thái này.

| Điều kiện đầu vào | Trạng thái | Cần từ AI1/BE |
|---|---|---|
| Contract + annex PDF/render | Missing | URI/path an toàn để đối chiếu overlay |
| OCR snapshot cho từng document | Missing | JSON có page, line/word, clause/table, bbox |
| Digest, engine/version, run ID | Missing | Metadata truy vết bất biến |
| Dossier role mapping | Missing | Xác nhận `contract` / `annex` |

## Yêu cầu evidence gửi AI1/BE

Vui lòng cung cấp một gói input có thể truy vết, gồm:

1. PDF contract/annex hoặc URI/path an toàn và page render dùng để overlay.
2. OCR snapshot JSON theo document/page, có raw text, line/word/clause/table refs và bbox.
3. `snapshot_id`, `run_id`, source digest, engine/version, render profile, page dimensions và rotation/frame.
4. Dossier manifest xác nhận document role (`contract` / `annex`) và quan hệ giữa các tài liệu.

Khi nhận đủ input, audit theo C02, C13, C15 trên hai phía và các representation có sẵn; ghi rõ case/side thiếu nguồn thay vì loại khỏi denominator.

## Điều kiện chuyển trạng thái

| Trạng thái | Điều kiện |
|---|---|
| `In Review / Blocked` | Chưa có đủ PDF/render, snapshot và provenance như bảng trên. |
| `Pending review` | Đã có audit result file với pass/fail, error log và evidence link. |
| `Done` | Reviewer xác nhận kết quả audit bằng ngày và link evidence; không còn input bắt buộc thiếu. |

Khi nhận đủ input, chạy checklist [ST-020-OCR-BBOX-AUDIT-CHECKLIST.vi.md](ST-020-OCR-BBOX-AUDIT-CHECKLIST.vi.md), ghi từng case/side vào error log, và chỉ chuyển ticket Done khi có bằng chứng pass/fail đính kèm.
