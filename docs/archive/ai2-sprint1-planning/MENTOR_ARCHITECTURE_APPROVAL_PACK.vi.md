# Gói trình Mentor duyệt kiến trúc — Gate 0

| Thuộc tính | Nội dung |
|---|---|
| Dự án | Contract Intelligence (PROD-01) |
| Mục đích | Xin duyệt architecture/project structure trước khi viết product code |
| Căn cứ | `assignment.pdf`, DOC-04 và architecture review report |
| Trạng thái | Chờ Mentor/Leader xác nhận bằng chữ |

## 1. Quyết định kiến trúc đề nghị duyệt

1. Đơn vị nghiệp vụ là `Dossier`, gồm một `CONTRACT` và 0..n `ANNEX`; document role do intake/leader xác nhận, AI không suy từ tên file hoặc upload order.
2. AI1 chịu trách nhiệm OCR/layout/provenance; AI2 chịu trách nhiệm fact, context, comparison, finding và evaluation semantics; BE sở hữu persistence/job/API/RBAC; FE sở hữu evidence viewer và thao tác review.
3. AI1 bàn giao snapshot bất biến `ai1.snapshot.v1` theo document, chứa `pages[]`; re-OCR luôn sinh `snapshot_id` mới.
4. Citation dùng provenance đa thành phần: `snapshot → document → page → line → raw Unicode span → word/bbox`. Finding cross-document luôn cần evidence hai phía.
5. Output máy, source OCR và citation máy là bất biến. HITL chỉ tạo revision/overlay append-only; chỉnh bbox là reviewed evidence selection, không ghi đè geometry AI1.
6. AI2 baseline dùng rule/normalizer local có version. Semantic conflict là candidate kỹ thuật hẹp, không là kết luận pháp lý.
7. Batch là capability bắt buộc Sprint 3; job có state, idempotency, retry/backoff, quarantine lỗi và summary done/failed/needs-review.

## 2. Contract AI1 → AI2 cần phê duyệt

Mỗi document snapshot phải có:

- `schema_version`, `snapshot_id`, `source_digest`, `dossier_id`, `document_id`, engine/version, document role và page count.
- Từng page có trạng thái, raw text, page render reference/digest, pixel size, upright frame, rotation, warnings/errors.
- `lines[]`, `words[]`, stable IDs, Unicode code-point offsets và normalized bbox `[x0,y0,x1,y1]` (origin top-left).
- `tables[] → rows[] → cells[]`, cell text và bbox; không nhận table blob.
- `PARTIAL`/`FAILED` giữ nguyên warning/error. AI2 trả missing/insufficient evidence thay vì suy đoán.

AI2 chỉ nhận input integration sau khi một value đi được chuỗi source đầy đủ và overlay đúng trên render nguồn.

## 3. Điều kiện bắt đầu code

Chỉ bắt đầu code khi đồng thời có:

- Mentor duyệt architecture và project structure.
- Leader xác nhận dossier policy, reviewer/adjudicator, multilingual scope và ưu tiên batch.
- AI1, AI2, BE, FE xác nhận data contract/coordinate frame/run lineage.
- BE xác nhận persistence/API/retry/revision CAS; FE xác nhận render/highlight/bbox-edit behavior.
- Chính sách dữ liệu thật: nơi lưu source/render, services ngoài được phép gửi, retention, logging, secret/RBAC.

Trước các điều kiện trên, chỉ được làm tài liệu, fixture `example_only`, schema design và test planning; không claim OCR quality, latency, cost hoặc production readiness.

## 4. Câu hỏi cần Mentor/Leader trả lời

1. Dữ liệu mentor cung cấp có được gửi ra external OCR/LLM không? Nếu có, những dịch vụ nào và điều kiện nào?
2. Ai là owner xác nhận dossier membership, contract/annex role, annex relation và effective date?
3. Scope release bắt buộc là Việt/Anh/bilingual theo đề bài hay có thay đổi scope được phê duyệt?
4. Reviewer nào có quyền confirm/correct/reject/request evidence; candidate amendment có cần adjudicator riêng không?
5. Hạ tầng dev/demo/staging nào được dùng; Redis/PostgreSQL/Object Storage có sẵn hay cần Docker Compose?
6. Budget/limit API và target evaluation Gate B (sample, owner, mốc đo) là gì?

## 5. Checklist ký duyệt

| Người xác nhận | Nội dung cần xác nhận | Trạng thái / ngày / link evidence |
|---|---|---|
| Mentor | Architecture, project structure, scope và các câu hỏi mở | Pending |
| Leader/Product | Dossier policy, reviewer policy, priority/capacity | Pending |
| AI1 | Snapshot, geometry, table, re-OCR handoff | Pending |
| Backend | API/persistence/job/revision semantics | Pending |
| Frontend | Viewer, two-source highlight, bbox edit | Pending |

## 6. Bước tiếp theo sau phê duyệt

1. Freeze version `ai1.snapshot.v1` và dossier manifest.
2. AI1 bàn giao một dossier contract + annex ở scan và text-layer.
3. AI2 chạy validator/citation conformance; chỉ khi pass mới triển khai extraction/comparison integration.
4. BE/FE tích hợp vertical slice single dossier; batch và bbox-edit hoàn thiện Sprint 3.
