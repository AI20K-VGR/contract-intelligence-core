# Trạng thái codebase theo architecture.md

Bản nền 0.1 triển khai tại `backend/`, `apps/web/`, `infra/`, `scripts/`. Đây là vertical slice có persistence và worker, không tuyên bố đã nghiệm thu toàn bộ kiến trúc hoặc mục tiêu chất lượng.

| Phạm vi kiến trúc | Hiện trạng |
|---|---|
| §3–4 Modular monolith | FastAPI + worker import cùng modules/schema; không Redis/Celery |
| §5 Ingestion | PDF header/parser validation, size/page cap, một contract, freeze manifest, SHA-256 artifacts |
| §6 Native/scan | PyMuPDF native; trang có image chuyển full-page Tesseract `vie+eng`; chưa tối ưu mixed theo region |
| §7 Evidence | Citation source hash, run, page, line, quote, bbox normalized trên canonical PNG; validator trước publish |
| §8 Structure/facts | Article heading, money VND/date/party/duration candidates; chưa clause tree đầy đủ, bảng/cell, context typing |
| §9 Comparison | Contract–appendix có hai citation; abstain `insufficient_evidence` vì chưa verify scope/trigger; chưa semantic rộng, amendment hay within-document/annex-annex |
| §10 Versioning | Frozen document/run snapshot, review/approval append-only; PostgreSQL triggers chặn update/delete; retry có run mới |
| §10 Relational graph | Core entities là SQL tables; page artifacts/clauses/facts/citations/findings trong JSON snapshot versioned; chưa normalize toàn bộ ER model |
| §11 Queue | Per-page tasks, SKIP LOCKED, token fencing, heartbeat, bounded attempts, checkpoint reuse, batch denominator |
| §12 API | Dossiers, upload, jobs/retry, results, facts/clauses/findings/conflicts, citations/pages, review, approval, batch, health |
| §13 Review | Role checks, optimistic version, history, effective view; correction tạo immutable analysis revision, recompute finding phụ thuộc, mở lại review/completeness; approval gắn effective hash. Reject vẫn chặn approval |
| §14–15 Observability | Request IDs, Prometheus HTTP counters/latency; chưa OTel context, Collector, Jaeger, Grafana, Langfuse, alert hoàn chỉnh |
| §16–17 Reports | Batch counts; quality `not_evaluated`; provider cost 0, compute cost `not_measured`; không có accuracy/cost giả |
| §18 Security | Bearer accounts server-owned, roles, local bind, generated storage keys, limited uploads; chưa dossier ACL hoặc process sandbox |
| §19 Deployment | Compose core + Prometheus profile, bootstrap, lockfiles; chưa backup/restore automation |
| §27 Long-document | Page tasks/checkpoints, per-page render; reducer đọc page outputs vào RAM, chưa chunk ledger/reference graph/context-budget pipeline |
| External inference | Chưa wiring Terra/provider: không gửi nội dung ra ngoài. Cần policy/permission, provider submissions và cost ledger trước khi bật external |

## Hành vi cần biết

- Citation exact-match không chứng minh context/ý nghĩa đúng. Reviewer vẫn phải kiểm tra. Confidence là signals; numeric score null. Money là decimal string.
- Empty OCR giữ `needs_review`, không suy ra trang trắng. Page failure giữ issue/partial output và chặn approval.
- Dossier sau start không nhận thêm file. Thêm/thay file cần dossier mới; chưa có API revision manifest.
- Correction validate theo loại fact, giữ machine và source citation, lưu human provenance; revision dẫn xuất có finding ID mới và `supersedes`. Finding không liên quan giữ review cũ. Job mới không tự áp correction cũ vào extraction. Reject chặn approval.
- Account đọc toàn workspace local; role phân quyền mutation. Chưa hỗ trợ multi-tenant/public deployment.
- Một worker xử lý một page tại một thời điểm; chưa global semaphore nhiều worker. Parser chưa có subprocess memory/CPU timeout.
- Migration `0001` dùng schema JSON đóng băng. Không chạy lại script freeze sau deploy; thay đổi schema phải có migration mới.
- Dependencies khóa bằng `backend/uv.lock`, `apps/web/package-lock.json`. Docker tags được pin; review giấy phép PyMuPDF trước phân phối.

## Validation

Tests dùng synthetic data tạo ở runtime: native end-to-end, idempotency/roles, stale review, immutable machine overlay, approval gate, lease fencing, checkpoint retry, batch accounting, crop/rotation geometry, scan routing qua mock, migration SQLite. Build TypeScript/Vite và `docker compose config --quiet` kiểm riêng.

Máy hiện chưa có Docker daemon hoạt động và không tìm thấy Tesseract trong PATH: chưa chạy full Compose/PostgreSQL multi-worker hoặc OCR scan thật. Mock routing không phải benchmark OCR.
