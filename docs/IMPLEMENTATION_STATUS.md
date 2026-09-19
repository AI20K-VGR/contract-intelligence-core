# Trạng thái codebase theo architecture.md

Bản nền 0.1 triển khai tại `backend/`, `apps/web/`, `infra/`, `scripts/`. Đây là vertical slice có persistence và worker, không tuyên bố đã nghiệm thu toàn bộ kiến trúc hoặc mục tiêu chất lượng.

| Phạm vi kiến trúc | Hiện trạng |
|---|---|
| §3–4 Modular monolith | FastAPI + worker import cùng modules/schema; không Redis/Celery |
| §5 Ingestion | PDF header/parser validation, size/page cap, một contract, freeze manifest, SHA-256 artifacts |
| §6 Native/scan | PyMuPDF native; trang có image chuyển full-page Tesseract `vie+eng`; chưa tối ưu mixed theo region |
| §7 Evidence | Citation source hash, run, page, line, quote, bbox normalized trên canonical PNG; validator trước publish |
| §8 Structure/facts | 3 cấp Điều → Khoản → Điểm (regex "Điều/Article N", "N." hoặc "N)", "x)" hoặc "x."), fragment con bám theo node sâu nhất đang mở, hai fragment liền kề được nối lại thành một câu khi dòng trước chưa kết thúc câu; bảng/row/cell thật cho PDF native qua PyMuPDF `find_tables`; trang scan/ảnh dùng `document_processing.py:_ocr_tables` — gom các dòng OCR liên tiếp tách được ≥3 nhóm từ theo khoảng cách, cùng số nhóm mỗi dòng và biên trái các nhóm trùng cụm (dung sai jitter) thành bảng; lệch số nhóm/số cụm giữa các dòng thì bỏ khối đó thay vì đoán (giảm false-positive trên đoạn văn + nhiễu watermark, verify bằng OCR thật trên 12 trang scan mẫu); money VND/date/party/duration candidates gắn `clause_ref` (vẫn ở cấp Điều); bảng bị ngắt qua trang (chỉ tiêu đề ở trang đầu) được liên kết bằng heuristic vị trí (`tables.py:link_continuations` — bảng trước sát đáy trang, bảng sau sát đỉnh trang kế; `continuation_confidence=high` nếu số cột khớp, `low` nếu lệch — không tự merge ô, chỉ gắn link cho UI/reviewer); numbering dạng khác (số La Mã, "1.1", chữ cái lồng dòng) chưa nhận diện, rơi về fragment |
| §9 Comparison | Match/difference/candidate_amendment thật khi hai fact cùng loại **và cùng `clause_ref`** (tolerance theo field, exact cho amount cùng currency, từ khoá sửa đổi/thay thế → amendment); abstain `insufficient_evidence` khi không cùng điều khoản hoặc khác currency — value/type một mình không đủ xác lập scope. Chưa semantic rộng, chưa within-document/annex-annex |
| §10 Versioning | Frozen document/run snapshot, review/approval append-only; PostgreSQL triggers chặn update/delete; retry có run mới |
| §10 Relational graph | Core entities là SQL tables; page artifacts/clauses/tables/facts/citations/findings trong JSON snapshot versioned; chưa normalize toàn bộ ER model |
| §10 Audit trail | Bảng `audit_events` append-only (actor/action/object/request_id/result/detail), ghi tại upload/enqueue/retry/review/approve/batch và job pending_review/failed; `GET /dossiers/{id}/audit` trả dòng thời gian đầy đủ một hồ sơ |
| §11 Queue | Per-page tasks, SKIP LOCKED, token fencing, heartbeat, bounded attempts, checkpoint reuse, batch denominator |
| §12 API | Dossiers, upload, jobs/retry, results, facts/clauses/tables/findings/conflicts, documents (file gốc + văn bản theo trang), citations/pages, audit, review, approval, batch, health |
| §13 Review | Optimistic version, history, effective view; correction tạo immutable analysis revision, recompute finding phụ thuộc, mở lại review/completeness; approval gắn effective hash. Reject vẫn chặn approval. `Actor`/role vẫn tồn tại trong code (audit trail, idempotency key) nhưng không còn login — mọi request là actor cục bộ cố định |
| §14–15 Observability | Request IDs, Prometheus HTTP counters/latency; chưa OTel context, Collector, Jaeger, Grafana, Langfuse, alert hoàn chỉnh |
| §16–17 Reports | Batch counts; quality `not_evaluated`; provider cost 0, compute cost `not_measured`; không có accuracy/cost giả |
| §18 Security | Không login (không phải multi-user); local bind, generated storage keys, limited uploads; chưa dossier ACL hoặc process sandbox |
| §19 Deployment | Compose core + Prometheus profile, bootstrap, lockfiles; chưa backup/restore automation |
| §27 Long-document | Page tasks/checkpoints, per-page render; reducer đọc page outputs vào RAM, chưa chunk ledger/reference graph/context-budget pipeline |
| External inference | `CI_OCR_ENGINE=gpt_vision` bật `terra_assisted`: Tesseract vẫn chạy để neo bbox/thứ tự dòng, `gpt-5.6-terra` đọc lại cả trang và thay text từng dòng theo đúng vị trí khi hai bên khớp số dòng; lệch số dòng thì giữ text Tesseract và gắn issue `GPT_VISION_LINE_COUNT_MISMATCH` (không suy đoán ánh xạ). Chưa có provider submissions/cost ledger/permission workflow — tắt mặc định (`tesseract`, không gửi nội dung ra ngoài) |

## Hành vi cần biết

- Citation exact-match không chứng minh context/ý nghĩa đúng. Reviewer vẫn phải kiểm tra. Confidence là signals; numeric score null. Money là decimal string.
- Empty OCR giữ `needs_review`, không suy ra trang trắng. Page failure giữ issue/partial output và chặn approval.
- Dossier sau start không nhận thêm file. Thêm/thay file cần dossier mới; chưa có API revision manifest.
- Correction validate theo loại fact, giữ machine và source citation, lưu human provenance; revision dẫn xuất có finding ID mới và `supersedes`. Finding không liên quan giữ review cũ. Job mới không tự áp correction cũ vào extraction. Reject chặn approval.
- Không có login/token: API không xác thực, ai gọi được vào máy/network cũng đọc và mutate được toàn bộ workspace. Chỉ dành cho chạy local một người vận hành; chưa hỗ trợ multi-tenant/public deployment.
- Một worker xử lý một page tại một thời điểm; chưa global semaphore nhiều worker. Parser chưa có subprocess memory/CPU timeout.
- Migration `0001` dùng schema JSON đóng băng. Không chạy lại script freeze sau deploy; thay đổi schema phải có migration mới.
- Dependencies khóa bằng `backend/uv.lock`, `apps/web/package-lock.json`. Docker tags được pin; review giấy phép PyMuPDF trước phân phối.

## Validation

Tests dùng synthetic data tạo ở runtime: native end-to-end, idempotency, stale review, immutable machine overlay, approval gate, lease fencing, checkpoint retry, batch accounting, crop/rotation geometry, scan routing qua mock, migration SQLite (đến `0003`), audit trail đầy đủ vòng đời một hồ sơ, structured comparison thật (match/difference/candidate_amendment theo clause), native table extraction (row/cell/bbox), clause hierarchy Điều/Khoản/Điểm/fragment parent/child theo từng document. Build TypeScript/Vite và `docker compose config --quiet` kiểm riêng.

Máy hiện chưa có Docker daemon hoạt động và không tìm thấy Tesseract trong PATH: chưa chạy full Compose/PostgreSQL multi-worker hoặc OCR scan thật. Mock routing không phải benchmark OCR.
