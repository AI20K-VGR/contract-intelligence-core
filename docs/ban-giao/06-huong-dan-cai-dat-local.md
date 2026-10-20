# 06 · Hướng dẫn cài đặt Local (Local Setup Guide)

| Thuộc tính | Nội dung |
|---|---|
| Người phụ trách | Chương (BE) |
| Phối hợp | Trang (FE), Đức Dũng (AI1), Văn Dũng (AI2) |
| Cập nhật | 20/10/2026 |
| Đã kiểm với | `docker-compose.yml` trên `develop` (19/10/2026) |

Hướng dẫn chạy toàn bộ hệ thống trên một máy: frontend, backend, worker, AI1 (OCR), AI2, Keycloak, PostgreSQL, Kafka, MinIO và giám sát. Mọi thứ chạy bằng Docker Compose từ **một checkout** của repo.

Cấu hình riêng cho AI2 (graph, vector, consent) và các lỗi thường gặp của AI2: `docs/AI2-LOCAL-SETUP.md`.

## 1. Yêu cầu máy

| Thành phần | Yêu cầu |
|---|---|
| RAM | Tối thiểu 16 GB. Docker Desktop cấp **ít nhất 8 GB** (tổng giới hạn RAM của các container là 12,4 GiB; lúc rảnh dùng ít hơn nhiều) |
| Ổ đĩa | Khoảng 15 GB trống cho image và volume |
| Docker | Docker Desktop (Windows/macOS) hoặc Docker Engine (Linux), có **Compose v2** (`docker compose version`) |
| Git | Bất kỳ bản mới |
| Node.js | 20 trở lên, chỉ khi chạy frontend ở chế độ dev (mục 5) |
| Python + `uv` | Python 3.11+ và [`uv`](https://docs.astral.sh/uv/), chỉ khi chạy backend ngoài Docker hoặc chạy test |
| Khoá AI | Khoá Mistral (OCR) và OpenAI (LLM, embedding) nếu muốn chạy OCR và AI2 thật. Không có khoá thì hệ thống vẫn khởi động, nhưng OCR và AI2 báo không khả dụng |

Yêu cầu hệ thống chi tiết (CPU, GPU, phiên bản): tài liệu 5 của Đức Dũng.

## 2. Lấy mã nguồn và cấu hình

```bash
git clone https://github.com/AI20K-VGR/contract-intelligence-core.git
cd contract-intelligence-core
git checkout develop
```

Tạo file khoá cho AI service. File này bị Git bỏ qua; điền khoá trong editor, **không** dán khoá vào chat, ticket hay lệnh terminal:

```bash
cp ai-service/.env.example ai-service/.env       # PowerShell: Copy-Item ai-service/.env.example ai-service/.env
git check-ignore ai-service/.env                 # phải in ra đường dẫn: file đã bị bỏ qua
```

Các biến cần điền để chạy luồng đầy đủ:

| Biến (trong `ai-service/.env`) | Dùng cho |
|---|---|
| `MISTRAL_API_KEY` | OCR (AI1) |
| `AI2_LLM_API_KEY` | LLM của AI2 (có thể dùng khoá OpenAI) |
| `AI2_EMBEDDING_API_KEY` | Embedding của AI2 (có thể cùng khoá OpenAI ở trên) |

Mọi cấu hình khác của local đã có giá trị mặc định trong `docker-compose.yml`, gồm mật khẩu database, MinIO, Keycloak và secret HMAC giữa backend và AI2. Các giá trị đó **chỉ dùng cho local**, không bao giờ dùng trên server.

## 3. Khởi động

```bash
docker compose up -d --build
docker compose ps
```

- Lần đầu mất khoảng 5–15 phút để build image và kéo các image nền.
- Compose khởi động theo thứ tự phụ thuộc: database → Keycloak (chờ healthy) → backend (tự chạy migration) → worker và các dịch vụ khác.
- Mọi container nên ở trạng thái `running` hoặc `healthy`. `minio-init` chạy một lần để tạo bucket rồi thoát (`exited (0)` là bình thường).

**Địa chỉ trên máy local:**

| Dịch vụ | Địa chỉ | Ghi chú |
|---|---|---|
| Ứng dụng (frontend) | http://localhost:5173 | Container `ci-frontend` (bản build) |
| Backend API | http://localhost:8000 | Swagger: http://localhost:8000/docs; sống: `/health` |
| Keycloak | http://localhost:8080 | Quản trị: http://localhost:8080/admin (tài khoản ở [12](12-danh-sach-tai-khoan.md)) |
| MinIO | http://localhost:9001 (giao diện), `:9000` (S3 API) | |
| PostgreSQL backend | `localhost:5434`, DB `contract_intelligence` | User `ci` |
| PostgreSQL Keycloak | `localhost:5433` | |
| Kafka | `localhost:9093` | |
| Mailpit (email) | http://localhost:8025 | Chỉ chạy khi bật profile `core` (mục 6) |
| Grafana | Qua ứng dụng: **Quản trị → Giám sát hệ thống** | Không mở cổng riêng |

AI2 (`ci-ai2-service`, cổng 8002) và AI1 (`ci-ai1-worker`) **không mở cổng ra máy host**: chỉ backend gọi được, qua mạng Docker. Kiểm tra AI2 còn sống:

```bash
docker compose exec ai2-service /app/.venv/bin/python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8002/healthz').read())"
```

## 4. Đăng nhập và thử luồng chính

Mở http://localhost:5173, đăng nhập bằng một trong ba tài khoản seed của realm local (`keycloak/realm-export.json`, tenant `tenant_vgr_01`):

| Tài khoản | Vai trò |
|---|---|
| `admin@ci.local` | Quản trị |
| `operator@ci.local` | Vận hành |
| `reviewer@ci.local` | Thẩm định |

Mật khẩu nằm trong `keycloak/realm-export.json` (xem [12](12-danh-sach-tai-khoan.md)); chỉ dùng ở local.

**Thử luồng:**
1. Đăng nhập `operator@ci.local`, tải một PDF hợp đồng **mẫu** (không chứa dữ liệu thật). Repo không chứa PDF mẫu; lấy bộ mẫu từ OneDrive của nhóm.
2. Theo dõi trang Tiến trình: OCR (AI1) → phân tích (AI2).
3. Mở cấu trúc hồ sơ, mâu thuẫn, hỏi đáp.
4. Đăng nhập `admin@ci.local` để xem trang Quản trị và Giám sát hệ thống.

**Dữ liệu mẫu:**
- Không có bước seed hồ sơ. Database bắt đầu rỗng, trừ ba người dùng trên (Keycloak import realm lúc khởi động lần đầu).
- Hồ sơ mẫu tạo bằng cách tải PDF lên như bước 1.

## 5. Sửa frontend với hot reload (tuỳ chọn)

Container `ci-frontend` đã chiếm cổng 5173, và Keycloak local **chỉ chấp nhận redirect về cổng 5173**. Muốn chạy Vite dev server thì dừng container frontend trước:

```bash
docker compose stop frontend
```

Tạo `frontend/.env.local`:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_KEYCLOAK_URL=http://localhost:8080
VITE_KEYCLOAK_REALM=contract-intelligence
VITE_KEYCLOAK_CLIENT_ID=contract-intel-frontend
```

```bash
cd frontend
npm ci
npm run dev        # http://localhost:5173
```

Xong việc thì `docker compose start frontend` để dùng lại bản build.

## 6. Email local (Mailpit)

Mời người dùng và đặt lại mật khẩu đều gửi email. Ở local, email đi vào Mailpit:

```bash
docker compose --profile core up -d mailpit
```

Xem thư tại http://localhost:8025.

## 7. Chạy backend ngoài Docker (tuỳ chọn, để debug)

Giữ các dịch vụ hạ tầng trong Docker, dừng hai container backend:

```bash
docker compose stop backend backend-worker
cd backend
cp .env.example .env              # địa chỉ trỏ tới cổng trên máy host (localhost:5434, :9093, :9000, :8080)
uv sync --frozen --extra dev
uv run alembic upgrade head
uv run uvicorn contract_intelligence.main:app --reload --port 8000
```

Worker (nhận sự kiện Kafka, điều phối OCR và AI2) chạy ở terminal khác:

```bash
cd backend
uv run python -m contract_intelligence.worker
```

`.env.example` đã có `AI2_BASE_URL=http://localhost:8002/api/v1` và `AI2_SERVICE_HMAC_SECRET` (giá trị dev, khớp với container AI2). Container AI2 không mở cổng ra host, nên muốn backend chạy ngoài Docker gọi được AI2 thì thêm `ports: ["8002:8002"]` cho `ai2-service` trong một file `docker-compose.override.yml` (không commit). Không làm vậy thì các chức năng gọi AI2 báo không khả dụng.

## 8. Chạy test và kiểm tra trước khi mở PR

```bash
# Backend
cd backend
uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/
uv run mypy src/
uv run python -m import_linter --config .importlinter
uv run pytest tests/unit/ tests/architecture/
uv run pytest tests/integration/ -m "not ai2_local_e2e"      # SQLite; test Postgres, MinIO tự bỏ qua

# Frontend
cd frontend && npm ci && npm run lint && npm run build && npm test

# AI service
cd ai-service
uv sync --frozen --extra dev --extra web --extra kafka --extra mistral
AI2_REQUIRE_DATABASE=false uv run pytest -m "not live and not integration" \
  --ignore=tests/test_hd_gold.py --ignore=tests/test_structure_reconstruction.py
```

**Lưu ý:**
- Backend dùng `ruff` khoá trong `uv.lock`. Nếu `uv run ruff` cho kết quả khác CI, chạy đúng bản CI: `uvx ruff@0.16.8`.
- **Test cần PostgreSQL** (CI chạy; local thì tuỳ chọn):
  ```bash
  docker run -d --rm --name ci-pg-test -e POSTGRES_USER=ci -e POSTGRES_PASSWORD=ci \
    -e POSTGRES_DB=ci_test -p 55432:5432 pgvector/pgvector:pg16
  docker exec ci-pg-test psql -U ci -d ci_test -c "CREATE DATABASE ci_lexicon"
  CI_TEST_POSTGRES_URL=postgresql+asyncpg://ci:ci@127.0.0.1:55432/ci_test \
  LEXICON_TEST_DATABASE_URL=postgresql+asyncpg://ci:ci@127.0.0.1:55432/ci_lexicon \
    uv run pytest tests/integration/ -m "not ai2_local_e2e"
  ```
- **Test tải theo khúc trên MinIO thật** (CI chạy; local thì tuỳ chọn). Dùng cùng image với production:
  ```bash
  docker run -d --name ci-minio-test --user 0:0 -p 127.0.0.1:59000:9000 \
    -e MINIO_ROOT_USER=citest -e MINIO_ROOT_PASSWORD=citest-secret-123 \
    cgr.dev/chainguard/minio:latest server /data
  CI_TEST_MINIO_URL=http://127.0.0.1:59000 CI_TEST_MINIO_USER=citest CI_TEST_MINIO_PASSWORD=citest-secret-123 \
    uv run pytest tests/integration/test_upload_sessions_minio.py
  docker rm -f ci-minio-test
  ```
- `uv sync --frozen` **không kèm** `--extra dev` sẽ gỡ pytest khỏi `.venv`. Sau đó `uv run pytest` lấy nhầm pytest cài ở máy, và báo lỗi import lạ (ví dụ `starlette`). Chạy lại `uv sync --frozen --extra dev`.

## 9. Dừng, xem log, dọn dữ liệu

```bash
docker compose logs --tail 100 backend backend-worker ai1-worker ai2-service   # xem log
docker compose restart backend                                                 # khởi động lại một dịch vụ
docker compose down                                                            # dừng, GIỮ dữ liệu
docker compose down -v                                                         # dừng và XOÁ toàn bộ dữ liệu local
```

`down -v` xoá database, file MinIO và cấu hình Keycloak đã sửa. Lần chạy sau Keycloak import lại realm từ đầu.

## 10. Lỗi thường gặp

| Triệu chứng | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| `backend` không lên, log báo chờ Keycloak | Keycloak khởi động chậm lần đầu | Chờ 1–2 phút; `docker compose logs keycloak keycloak-readiness` |
| Đăng nhập báo `Invalid redirect_uri` | Frontend chạy ở cổng khác 5173 | Chạy đúng cổng 5173 (mục 5) |
| `npm run dev` báo cổng 5173 đã dùng | Container `ci-frontend` đang chạy | `docker compose stop frontend` |
| Container bị khởi động lại liên tục, `OOMKilled` | Docker không đủ RAM | Tăng RAM cho Docker Desktop (≥ 8 GB) |
| Upload xong nhưng OCR không chạy | Thiếu `MISTRAL_API_KEY` hoặc không có mạng ra ngoài | `docker compose logs ai1-worker` |
| AI2 báo `LLM_UNAVAILABLE` | Thiếu khoá AI2 hoặc model sai | Kiểm `ai-service/.env`, rồi `docker compose up -d ai2-service` |
| Port 5432/5433/5434/8000/8080/9000 đã dùng | Có dịch vụ khác trên máy | Tắt dịch vụ đó, hoặc đổi cổng host trong `docker-compose.yml` (cổng 5173 thì đặt `FRONTEND_HOST_PORT`, nhưng Keycloak chỉ chấp nhận 5173) |
| Sửa code backend mà không thấy thay đổi | Image cũ | `docker compose up -d --build backend backend-worker` |
