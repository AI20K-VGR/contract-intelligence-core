# AI2 issue #131 — dossier purge

Nguồn: https://github.com/AI20K-VGR/contract-intelligence-core/issues/131

## Phạm vi

PostgreSQL + pgvector theo D11/ADR-14. Không triển khai purge SQLite. Các fixture
SQLite cũ chỉ được chạy trong regression suite hiện có, không mở rộng runtime.
Backend integration đã được bổ sung và xác minh local theo yêu cầu tiếp theo của người dùng.
Kiểm đếm/purge lại production là bước triển khai tiếp theo; thay đổi này không tự
thao tác dữ liệu production hoặc đóng issue. Người dùng yêu cầu test local trước.

## Thay đổi phía AI2

- [x] API DELETE `/api/v1/dossiers/{dossier_id}`, HMAC envelope scope `ai2.dossier.delete`,
  binding URL/body/envelope, idempotent và trả số dòng xoá + evidence tích luỹ.
- [x] Migration 0009: tombstone lâu dài, ownership/digest history, backfill từ JSON
  có cấu trúc và DB triggers chặn writer muộn.
- [x] Purge jobs, snapshots, sessions/blobs, graph/pairs, trace/receipts,
  durable run/checkpoint/event/outbox/audit của đúng tenant/dossier.
- [x] Vector lịch sử chỉ xoá khi không còn owner sống trên mọi tenant; query vector
  upsert bind tenant/dossier để scope đã xoá không mượn shared digest ghi lại.
- [x] Job mất quyền ghi, cooperative cancellation ở checkpoint; Kafka kiểm tra cả
  đường trả kết quả từ cache; query và session từ chối nội dung sau tombstone.
- [x] File cleanup giới hạn theo session ID dưới data root; giữ manifest metadata
  để retry sau DB commit/crash; sweeper tiếp tục pending cleanup.
- [x] Contract request/response/lỗi/retry và quyết định retention được ghi trong
  BE-AI2-PROCESSING-CONTRACT §7 và phần bổ sung #131 của DEC-BE-AI2-01.
- [x] Backend gọi API có chữ ký trước completed, lưu evidence tích luỹ và giữ failed
  sau background task để sweeper retry; unit tests kiểm tra HTTP 503 và response sai.

## Kiểm chứng

Test chấp nhận dùng PostgreSQL thật trong container local riêng, gồm pgvector.

- [x] Xoá đủ store, gọi lặp/scope chưa tồn tại, tenant isolation, shared digest cùng
  và khác tenant, digest lịch sử, late write snapshot/session/job/durable/vector.
- [x] Writer chờ khoá purge không thể ghi lại sau tombstone.
- [x] Migration DB có dữ liệu phiên bản 0008 backfill session/run ownership.
- [x] File cleanup lỗi sau DB commit được retry; pending sweeper phục hồi.
- [x] Audit chưa xoá vẫn append-only; downgrade bỏ fencing sau purge bị từ chối.
- [x] Running job/graph/trace và regression đã kiểm chứng: lượt cuối 2555 passed,
  6 live tests deselected; 10 golden tests đã đạt ở hai lượt đầy đủ trước đó.
  Tổng phạm vi offline 2565 tests; 17 test purge PostgreSQL/pgvector đều đạt.
  Chi tiết và giới hạn xem `implementation-report.md`.
- [x] LLM live 2 passed; E2E local Backend → AI2 HTTP thật + PostgreSQL, hai file/OCR,
  retry, restart và evidence: 2 passed; hồi quy Backend 1001 passed, 12 deselected.
- [x] Audit read-only 8 hồ sơ tổng hợp local: residue và pending đều bằng 0 ở các bảng kiểm tra.

## Điều kiện triển khai và hoàn tất issue

1. Review và deploy migration + AI2 readers/writers mới. Không chạy lại worker cũ
   hoặc downgrade bỏ fencing sau khi purge đã hoạt động.
2. Backend gọi API trước completed, retry lỗi, lưu evidence tích luỹ: đã triển khai
   và test local; cần review phần Backend cùng phần AI2 trước rollout.
3. E2E staging: process → query/graph → DELETE → không còn nội dung → DELETE lần hai;
   có job đang chạy và shared digest.
4. Lấy đúng tenant/dossier từ backend deletion ledger, purge lại 7 scope tồn đọng
   bằng API, kiểm đếm từng store/files; không coi số vector bằng 0 là đủ bằng chứng.
5. Đóng issue sau khi các bước integration/deploy/audit được xác nhận.

## Giới hạn vận hành cần review

Các transaction ghi ngắn dùng advisory lock chung để bảo đảm thứ tự writer/purge
và shared-digest references. Không giữ khoá trong lời gọi provider. Thứ tự bắt buộc:
purge lock → row lock; đường completion có thể lấy dossier lock trước purge lock
vì purge không lấy dossier lock. DB metadata không chứa hợp đồng được giữ lâu dài.
Ownership mâu thuẫn khiến migration/write thất bại thay vì xoá nhầm tài nguyên.
