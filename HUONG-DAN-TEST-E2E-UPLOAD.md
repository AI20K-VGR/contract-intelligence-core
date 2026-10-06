# Hướng dẫn test full luồng Upload → AI1 → AI2

Tài liệu này mô tả cách kiểm tra end-to-end trên nhánh tích hợp
(`feature/code-full` sau khi merge PR #17 / nhánh `merge/code-full-backend-setup`):

```
Frontend upload PDF
  → Backend POST /api/v1/dossiers
  → Kafka dossier.uploaded
  → backend-worker → ci.ai1.ocr.commands
  → ai1-worker (OCR, mỗi tài liệu một lệnh)
  → ci.ai1.ocr.results
  → backend-worker: đủ snapshot mọi tài liệu → job EXTRACTED
  → backend-worker gọi HTTP ai2-service: POST /jobs/idp + poll GET /jobs/{id}
  → dossier / job → PENDING_REVIEW
```

AI1 đi Kafka, AI2 đi HTTP. Không có webhook và không có topic Kafka cho AI2.

Cần Docker Desktop, Node.js 20+, và quyền OPERATOR/ADMINISTRATOR để upload.

---

## 1. Chuẩn bị

### 1.1. Checkout nhánh đã gộp FE + BE + AI

```powershell
cd E:\Project_OJT\contract-intelligence-core
git fetch origin
git checkout merge/code-full-backend-setup
# hoặc sau khi merge PR #17:
# git checkout feature/code-full
# git pull
```

### 1.2. Key / env bắt buộc

| Biến | File / nơi set | Bắt buộc? | Ghi chú |
|---|---|---|---|
| `MISTRAL_API_KEY` | `ai-service/.env` | **Có** (nếu engine = mistral) | Compose mặc định `AI1_OCR_ENGINE=mistral` |
| `AI2_SERVICE_HMAC_SECRET` | compose `backend-worker` + `ai2-service` | Có | Ký `service_envelope` khi worker gọi `/jobs/idp` |
| LLM key AI2 | — | Không | `egress_allowed=false` mặc định (cấu hình server, client không đổi được) |
| FE env | `frontend/.env.local` | Có | Xem mục 3 |

Tuỳ chọn (OCR không dùng cloud):

```powershell
# trong shell trước khi up, hoặc sửa docker-compose backend-worker
$env:AI1_OCR_ENGINE = "pymupdf"
```

### 1.3. Frontend env

`frontend/.env.local`:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_KEYCLOAK_URL=http://localhost:8080
VITE_KEYCLOAK_REALM=contract-intelligence
VITE_KEYCLOAK_CLIENT_ID=contract-intel-frontend
```

---

## 2. Bật stack Docker

Từ **root repo** (không phải thư mục `backend/`):

```powershell
cd E:\Project_OJT\contract-intelligence-core

docker compose up -d --build `
  keycloak-db keycloak `
  backend-db kafka minio minio-init `
  backend backend-worker `
  ai1-worker ai2-service
```

Kiểm tra:

```powershell
docker compose ps
```

| Container | Kỳ vọng |
|---|---|
| `ci-backend` | healthy — http://127.0.0.1:8000/health → `"status":"ok"` |
| `ci-backend-worker` | Up — log có `worker.dossier_events.started` + `worker.ai1_results.started` |
| `ai1-worker` (2 replica) | Up — `ai1.kafka.worker.started` |
| `ci-ai2-service` | Up — http://127.0.0.1:8002/health (worker gọi AI2 qua HTTP) |
| `ci-keycloak` | Up — http://localhost:8080/realms/contract-intelligence |
| `ci-kafka` / `ci-minio` / DB | Up / healthy |

Log nhanh:

```powershell
docker logs ci-backend-worker --tail 30
docker compose logs ai1-worker --tail 20
docker logs ci-ai2-service --tail 20
```

Nếu `ci-backend` fail migration (`Can't locate revision…`): rebuild image rồi up lại:

```powershell
docker compose build backend backend-worker
docker compose up -d backend backend-worker
```

---

## 3. Chạy Frontend

```powershell
cd E:\Project_OJT\contract-intelligence-core\frontend
npm install
npm run dev
```

Mở http://localhost:5173

Đăng nhập (seed Keycloak):

- Email: `admin@ci.local`
- Mật khẩu: `Admin@CI123`

Role cần có: **OPERATOR** hoặc **ADMINISTRATOR**.

---

## 4. Kịch bản test UI (happy path)

1. Vào trang **Tạo hồ sơ / Create dossier**.
2. Chọn **1 file PDF hợp đồng** (CONTRACT), annex tuỳ chọn. AI2 chỉ chạy khi OCR xong **mọi** file.
3. Nhập tên hồ sơ → Submit.
4. Kỳ vọng:
   - API trả **202** (`dossier_id`, `job_id`).
   - UI chuyển sang tiến trình OCR / analysis.
5. Chờ xử lý (OCR cloud có thể 1–several phút tùy PDF).
6. Kỳ vọng cuối:
   - Job/dossier status → **`pending_review`** / `PENDING_REVIEW`.
   - Có dữ liệu extraction / review items (tùy nội dung PDF).

Endpoint legacy `POST /api/v1/dossiers/upload` đã bị gỡ; `POST /api/v1/dossiers` là đường upload duy nhất.

Record worker xử lý lỗi quá `WORKER_HANDLER_MAX_ATTEMPTS` lần (mặc định 3) được chuyển sang topic `<topic>.dlq` (vd `dossier_events.dlq`, `ci.ai1.ocr.results.dlq`) kèm lỗi và offset gốc — kiểm tra ở đó khi hồ sơ đứng yên.

---

## 5. Checklist verify từng hop (bắt buộc khi nghi ngờ)

Mở thêm terminal, theo dõi log **ngay sau** lúc bấm Upload.

### Hop A — Backend nhận upload + publish event

```powershell
docker logs ci-backend --tail 50
```

Tìm request `POST /api/v1/dossiers` **202**.  
Worker:

```powershell
docker logs ci-backend-worker --tail 80
```

Tìm: `worker.dossier_uploaded.ocr_command_published`  
→ đã gửi `ci.ai1.ocr.commands`.

### Hop B — AI1 OCR

```powershell
docker compose logs ai1-worker --tail 100
```

Tìm consume command + publish result.  
Backend-worker:

Tìm: `worker.ai1_result.persisted` với `all_extracted=true` ở file cuối  
→ status nội bộ **EXTRACTED** (các file trước vẫn `processing`).  
Nếu thấy `worker.ai1_result.rejected` → snapshot sai/thiếu, job chuyển **FAILED** (có audit `ai1.snapshot_rejected`).

### Hop C — AI2 IDP (HTTP)

```powershell
docker logs ci-backend-worker --tail 100
docker logs ci-ai2-service --tail 100
```

Tìm ở worker: `worker.ai2.completed` → **PENDING_REVIEW**.  
Nếu thấy `worker.ai2.waiting_for_manifest` / `worker.ai2.waiting_for_snapshots` → chưa đủ điều kiện gọi AI2.  
Nếu thấy `worker.ai2.failed` → job **FAILED** với `AI2_PROCESSING_FAILED`.

### Hop D — API / UI

```powershell
# Thay {id} bằng dossier_id; cần Bearer token từ browser DevTools
# hoặc kiểm tra trực tiếp trên UI trang dossier / OCR progress
Invoke-RestMethod http://127.0.0.1:8000/health
```

Trên UI: dossier không kẹt `processing` / `extracted` mãi; chuyển sang chờ review.

---

## 6. Topics Kafka (tham chiếu)

| Topic | Hướng |
|---|---|
| `dossier_events` | BE API → backend-worker (`dossier.uploaded`) |
| `ci.ai1.ocr.commands` | backend-worker → ai1-worker |
| `ci.ai1.ocr.results` | ai1-worker → backend-worker |

AI2 không có topic: xem `docs/contracts/BE-AI2-PROCESSING-CONTRACT.vi.md` (HTTP).  
Contract AI1: `docs/DOC-05d-kafka-ai1-ocr-contract.md`.

---

## 7. Troubleshooting nhanh

| Triệu chứng | Nguyên nhân thường gặp | Cách xử |
|---|---|---|
| Upload 401/403 | Chưa login / sai role | Dùng `admin@ci.local`, role OPERATOR+ |
| Upload OK nhưng không OCR | `backend-worker` / Kafka down | `docker compose ps`; xem log worker |
| OCR fail | Thiếu `MISTRAL_API_KEY` | Điền `ai-service/.env`, restart `ai1-worker` |
| OCR xong, không AI2 | Chưa đủ snapshot mọi file / manifest chưa xác nhận / `ai2-service` down | Log `worker.ai2.waiting_*`; `docker compose ps ai2-service` |
| Backend unhealthy | Alembic revision cũ trong image | `docker compose build backend backend-worker` rồi up lại |
| FE gọi sai host | `VITE_API_BASE_URL` trỏ 8080 | Đặt `http://127.0.0.1:8000` trong `.env.local` |
---

## 8. Dừng stack

```powershell
cd E:\Project_OJT\contract-intelligence-core
docker compose down
```

Giữ data: **không** thêm `-v`. Xoá volume DB/Kafka: `docker compose down -v` (mất dữ liệu local).

---

## 9. Definition of Done cho lần test này

- [ ] Health backend + Keycloak realm OK  
- [ ] Up: `backend-worker`, `ai1-worker`, `ai2-service`  
- [ ] FE login + Create dossier với PDF  
- [ ] Log có đủ: OCR command → AI1 result (mọi file) → `worker.ai2.completed`  
- [ ] Dossier/job kết thúc ở **PENDING_REVIEW** trên UI  

Pass đủ 5 mục trên = full luồng upload E2E đã chạy đúng.
