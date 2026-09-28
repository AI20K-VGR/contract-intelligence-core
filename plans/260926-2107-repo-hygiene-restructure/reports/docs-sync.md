# Docs sync — repo hygiene restructure

- Scope: tất cả markdown tracked dưới `docs/**` (61 file) + markdown ở repo root (`README.md`, `CONTRIBUTING.md`, `GITFLOWS.md`, `HUONG-DAN-CHAY.md`, `HUONG-DAN-TEST-E2E-UPLOAD.md`); loại `harness/`, `plans/`.
- Lệnh dùng: `git grep -n -i -E "\b(java|spring|maven|celery)\b"` trên đúng pathspec trên, cộng check biến thể `springboot`/`spring boot`/`celeryq`/`jvm`.
- `README.md` đã đúng: `backend/` = Python 3.11+/FastAPI/Kafka worker (`README.md:22`), `ai-service/` = Python (FastAPI / Kafka worker) (`README.md:24`) — không sửa.
- Hit duy nhất trong scope: `docs/DOC-04-architecture.md:92,94,988` và `docs/KEYCLOAK-SETUP.md` (nhiều dòng).
- `DOC-04-architecture.md:92` + `:988`: changelog/ADR nói backend **đã đổi từ** Java 17/Spring Boot 3 **sang** Python 3.12/FastAPI — mô tả lịch sử đúng, không phải claim hiện tại.
- `DOC-04-architecture.md:94`: ADR-03 nói rõ "không thêm Redis/Celery" — phủ định, không phải claim service dùng Celery.
- `KEYCLOAK-SETUP.md`: Java/Maven ở đây nói về JAR extension của Keycloak (bên thứ ba), dòng 173 còn nói rõ "Project là Python-only".
- File ngoài scope (không kiểm, do nằm dưới `ai-service/`/`backend/` chứ không phải `docs/`/root): `ai-service/architecture.md`, `ai-service/docs/CONTRACT_INTELLIGENCE_ARCHITECTURE.md`, `backend/CONTEXT.md`.
- Kết quả: không tìm thấy claim backend là Java/Spring hoặc service dùng Celery còn sót trong scope → **không sửa file nào**.
- Không commit gì trong lượt này.
