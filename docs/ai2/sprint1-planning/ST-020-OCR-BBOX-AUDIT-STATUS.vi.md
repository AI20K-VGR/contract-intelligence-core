# ST-020 — Trạng thái audit OCR/bbox

**Trạng thái: In Review / blocked by input evidence (16/09/2026).**

Không có PDF nguồn, page render, OCR snapshot có digest, hoặc run ID trong workspace. Vì vậy không có phép đo nào để gán `pass` hay `fail` một cách kiểm chứng được; checklist vẫn là protocol, không phải kết quả audit.

| Điều kiện đầu vào | Trạng thái | Cần từ AI1/BE |
|---|---|---|
| Contract + annex PDF/render | Missing | URI/path an toàn để đối chiếu overlay |
| OCR snapshot cho từng document | Missing | JSON có page, line/word, clause/table, bbox |
| Digest, engine/version, run ID | Missing | Metadata truy vết bất biến |
| Dossier role mapping | Missing | Xác nhận `contract` / `annex` |

Khi nhận đủ input, chạy checklist [ST-020-OCR-BBOX-AUDIT-CHECKLIST.vi.md](ST-020-OCR-BBOX-AUDIT-CHECKLIST.vi.md), ghi từng case/side vào error log, và chỉ chuyển ticket Done khi có bằng chứng pass/fail đính kèm.
