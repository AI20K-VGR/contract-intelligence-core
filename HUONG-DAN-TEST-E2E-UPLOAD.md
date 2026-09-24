# Hướng dẫn test full luồng Upload → AI1 → AI2

Tài liệu này mô tả cách kiểm tra end-to-end trên nhánh tích hợp
(`feature/code-full` sau khi merge PR #17 / nhánh `merge/code-full-backend-setup`):

```
Frontend upload PDF
  → Backend POST /api/v1/dossiers
  → Kafka dossier.uploaded
  → backend-worker → ci.ai1.ocr.commands
  → ai1-worker (OCR)
  → ci.ai1.ocr.results
  → backend-worker → ci.ai2.idp.commands   (AI2_WIRE_ENABLED=true)
  → ai2-worker (IDP)
  → ci.ai2.idp.results
  → dossier / job → PENDING_REVIEW
```

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
| `AI2_WIRE_ENABLED` | compose `backend-worker` | Đã = `true` | Không set → dừng sau OCR, không gọi AI2 |
| `AI2_SERVICE_HMAC_*` | compose | Không (Kafka) | Chỉ cần cho HTTP lab `/jobs/idp` |
| LLM key AI2 | — | Không (MVP Kafka) | `egress_allowed=false` trên IDP command |
| FE env | `frontend/.env.local` | Có | Xem mục 3 |

Không cần bổ sung key AI2 cho path Kafka runtime.

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
  ai1-worker ai2-worker ai2
```

Kiểm tra:

```powershell
docker compose ps
```

| Container | Kỳ vọng |
|---|---|
| `ci-backend` | healthy — http://127.0.0.1:8000/health → `"status":"ok"` |
| `ci-backend-worker` | Up — log có `worker.ai1_results.started` + `worker.ai2_results.started` |
| `ci-ai1-worker` | Up — `ai1.kafka.worker.started` |
| `ci-ai2-worker` | Up — `ai2.kafka.worker.started` |
| `ci-ai2` | Up — http://127.0.0.1:8002/health (HTTP demo, không bắt buộc cho Kafka) |
| `ci-keycloak` | Up — http://localhost:8080/realms/contract-intelligence |
| `ci-kafka` / `ci-minio` / DB | Up / healthy |

Log nhanh:

```powershell
docker logs ci-backend-worker --tail 30
docker logs ci-ai1-worker --tail 20
docker logs ci-ai2-worker --tail 20
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
2. Chọn **1 file PDF hợp đồng** (CONTRACT). Annex tuỳ chọn — MVP Kafka hiện chỉ OCR **body/CONTRACT**.
3. Nhập tên hồ sơ → Submit.
4. Kỳ vọng:
   - API trả **202** (`dossier_id`, `job_id`).
   - UI chuyển sang tiến trình OCR / analysis.
5. Chờ xử lý (OCR cloud có thể 1–several phút tùy PDF).
6. Kỳ vọng cuối:
   - Job/dossier status → **`pending_review`** / `PENDING_REVIEW`.
   - Có dữ liệu extraction / review items (tùy nội dung PDF).

**Không** dùng endpoint legacy `POST /api/v1/dossiers/upload` cho test này — path đó không publish `dossier.uploaded` Kafka.

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
docker logs ci-ai1-worker --tail 100
```

Tìm consume command + publish result.  
Backend-worker:

Tìm: `worker.ai1_result.persisted`  
→ status nội bộ **EXTRACTED**, rồi publish AI2 nếu wire bật.

### Hop C — AI2 IDP

```powershell
docker logs ci-backend-worker --tail 100
```

Tìm: `ai2_handoff.command_published`  
Nếu thấy `ai2_handoff.disabled` → `AI2_WIRE_ENABLED` chưa bật trên worker.

```powershell
docker logs ci-ai2-worker --tail 100
```

Tìm: xử lý command + `ai2.kafka.result_published` (completed/failed).

Backend-worker:

Tìm: consume `ci.ai2.idp.results` / apply result → **PENDING_REVIEW**.

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
| `ci.ai2.idp.commands` | backend-worker → ai2-worker |
| `ci.ai2.idp.results` | ai2-worker → backend-worker |

Contract: `docs/DOC-05d-kafka-ai1-ocr-contract.md`, `docs/DOC-05e-kafka-ai2-idp-contract.md`.

---

## 7. Troubleshooting nhanh

| Triệu chứng | Nguyên nhân thường gặp | Cách xử |
|---|---|---|
| Upload 401/403 | Chưa login / sai role | Dùng `admin@ci.local`, role OPERATOR+ |
| Upload OK nhưng không OCR | `backend-worker` / Kafka down | `docker compose ps`; xem log worker |
| OCR fail | Thiếu `MISTRAL_API_KEY` | Điền `ai-service/.env`, restart `ai1-worker` |
| OCR xong, không AI2 | `AI2_WIRE_ENABLED=false` hoặc thiếu snapshot | Compose worker phải `true`; log `ai2_handoff.disabled` |
| Backend unhealthy | Alembic revision cũ trong image | `docker compose build backend backend-worker` rồi up lại |
| FE gọi sai host | `VITE_API_BASE_URL` trỏ 8080 | Đặt `http://127.0.0.1:8000` trong `.env.local` |
| Annex không được phân tích | MVP body-only | Chỉ CONTRACT đi Kafka IDP giai này |

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
- [ ] 3 worker Up: `backend-worker`, `ai1-worker`, `ai2-worker`  
- [ ] FE login + Create dossier với PDF  
- [ ] Log có đủ: OCR command → AI1 result → AI2 command → AI2 result  
- [ ] Dossier/job kết thúc ở **PENDING_REVIEW** trên UI  

Pass đủ 5 mục trên = full luồng upload E2E đã chạy đúng.
