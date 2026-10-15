# Chạy full AI2 cục bộ

Hướng dẫn này dùng **một checkout** của `contract-intelligence-core`. Các lệnh shell chạy trên Windows PowerShell 7+, Linux và macOS; phần bash áp dụng cho hai hệ POSIX.

## 1. Chuẩn bị

- Git.
- Docker Desktop với Docker Compose v2, đã khởi động.
- Node.js 20 trở lên cho frontend.
- Python 3.11+ và [`uv`](https://docs.astral.sh/uv/) chỉ khi chạy Backend ngoài Docker.
- Khóa nhà cung cấp AI nếu muốn OCR/inference thật. Docker và AI2 có thể khởi động khi chưa có khóa, nhưng gọi model sẽ báo không khả dụng.

Clone repo:

```bash
git clone https://github.com/AI20K-VGR/contract-intelligence-core.git
cd contract-intelligence-core
```

## 2. Cấu hình khóa cục bộ

Tạo file AI Service từ mẫu; file `.env` bị Git ignore. Điền khóa trực tiếp trong editor trên máy, không dán vào ticket, chat hoặc terminal command:

**PowerShell**

```powershell
Copy-Item ai-service/.env.example ai-service/.env
notepad ai-service/.env
git check-ignore ai-service/.env
```

**Linux/macOS**

```bash
cp ai-service/.env.example ai-service/.env
${EDITOR:-vi} ai-service/.env
git check-ignore ai-service/.env
```

Để chạy luồng đầy đủ, cấu hình `MISTRAL_API_KEY` cho OCR và `AI2_LLM_API_KEY` cùng `AI2_EMBEDDING_API_KEY` cho LLM/embedding. Có thể dùng một khóa OpenAI cho cả hai biến AI2. Không cần `AI2_EMBEDDING_DISCOVERY_ENABLED=true`: đây chỉ là chẩn đoán danh sách model, không bật vector runtime.

Contract graph (operation and pair), semantic extraction/projections, processing/query egress, query LLM/vector và vector recall được bật mặc định trong full Compose profile. Model/key, mạng outbound, DB/pgvector và consent của hồ sơ vẫn phải sẵn sàng để từng capability chạy được. Muốn chủ động giới hạn egress hoặc vector trên toàn máy local, khai báo biến tương ứng trong file `.env` ở repo root, ví dụ `AI2_PROCESSING_EGRESS_ALLOWED=false` hoặc `AI2_QUERY_USE_VECTOR=false`; bỏ biến để trở về mặc định `true`. Backend và AI2 đều áp dụng global cap, còn consent từng hồ sơ là cổng riêng. Không tắt `AI2_SERVICE_HMAC_SECRET` hoặc `AI2_QUERY_REQUIRE_SIGNATURE`.

## 3. Khởi động dịch vụ

**PowerShell, Linux và macOS**

```bash
docker compose up -d --build
docker compose ps
```

Compose tự chạy database migrations trong Backend entrypoint. Backend chỉ khởi động sau khi PostgreSQL healthy và Keycloak readiness probe trả healthy.

Các URL local chính:

| Dịch vụ | URL |
|---|---|
| Frontend | http://localhost:5173 |
| Backend API | http://127.0.0.1:8000 |
| Backend health/docs | http://127.0.0.1:8000/health · http://127.0.0.1:8000/docs |
| Keycloak | http://localhost:8080 |
| AI2 health | http://127.0.0.1:8002/health |
| MinIO console | http://localhost:9001 |
| Mailpit | http://localhost:8025 (profile `core`) |

Nếu Mailpit chưa chạy:

```bash
docker compose --profile core up -d mailpit
```

`/health` là liveness/cấu hình tổng quát. Trường embedding `NOT_RUN` có nghĩa discovery probe chưa được gọi; nó không chứng minh vector recall đang tắt hoặc đã kết nối. Hãy kiểm tra log truy vấn và kết quả thực tế.

## 4. Chạy frontend

Trong `frontend/.env.local`, đặt URL Backend này (frontend fallback cũ là cổng 8080):

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_KEYCLOAK_URL=http://localhost:8080
VITE_KEYCLOAK_REALM=contract-intelligence
VITE_KEYCLOAK_CLIENT_ID=contract-intel-frontend
```

**PowerShell**

```powershell
@'
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_KEYCLOAK_URL=http://localhost:8080
VITE_KEYCLOAK_REALM=contract-intelligence
VITE_KEYCLOAK_CLIENT_ID=contract-intel-frontend
'@ | Set-Content -Encoding utf8 frontend/.env.local
Set-Location frontend
npm ci
npm run dev
```

**Linux/macOS**

```bash
cat > frontend/.env.local <<'EOF'
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_KEYCLOAK_URL=http://localhost:8080
VITE_KEYCLOAK_REALM=contract-intelligence
VITE_KEYCLOAK_CLIENT_ID=contract-intel-frontend
EOF
cd frontend
npm ci
npm run dev
```

Mở http://localhost:5173 và đăng nhập bằng tài khoản seed local trong `keycloak/realm-export.json`. Chỉ dùng thông tin seed ở môi trường local; không tái sử dụng ở staging/production.

## 5. Thử luồng OCR → AI2 → graph → query

1. Tạo hồ sơ thử nghiệm và tải lên PDF hợp đồng được phép dùng. Dùng tài liệu mẫu không chứa dữ liệu cá nhân hoặc bí mật thật.
2. Chờ trạng thái OCR hoàn tất. Nếu OCR lỗi, xem `ai1-worker` và xác nhận `MISTRAL_API_KEY` cùng outbound network.
3. Mở cấu trúc hồ sơ. Khi AI2 hoàn tất, kiểm tra có job ID và snapshot hiện hành; xem riêng graph quan hệ điều khoản và graph sửa đổi. Chọn một cạnh để mở bằng chứng nguồn/đích. Không có quan hệ phù hợp trong hợp đồng thì graph có thể rỗng; rỗng không tự nó chứng minh pipeline hỏng.
4. Thử truy vấn hồ sơ. Kết quả AI2 cần citation/bằng chứng phù hợp với snapshot hiện tại. Model error, timeout hoặc provider key thiếu phải hiện thành trạng thái lỗi/degraded; không suy ra inference thành công chỉ từ feature flag hay `/health`.
5. Tắt consent chia sẻ nội dung ở hồ sơ thử nghiệm rồi chạy truy vấn tiếp theo. Deterministic retrieval/evidence nội bộ vẫn dùng được; nội dung không được gửi tới LLM, embedding hoặc pair classifier. Consent được lưu theo hồ sơ, không phải một global switch.

Để xem request/service logs mà không in file `.env`:

```bash
docker compose logs --tail 100 backend backend-worker ai1-worker ai2-service keycloak keycloak-readiness
```

Lỗi thường gặp:

| Triệu chứng | Kiểm tra |
|---|---|
| Frontend gọi nhầm `:8080` | Đặt `VITE_API_BASE_URL=http://127.0.0.1:8000`, khởi động lại dev server. |
| Keycloak chưa sẵn sàng | `docker compose ps keycloak keycloak-readiness backend`; xem `docker compose logs --tail 100 keycloak keycloak-readiness`. |
| `LLM_UNAVAILABLE` | Kiểm tra key/model/base URL trong `ai-service/.env` và outbound network từ container AI2. |
| `PROCESSING_TIMEOUT` | Xem log Backend worker và AI2; xác nhận DB healthy/pgvector hoạt động. |
| Graph báo thiếu job/snapshot | Đợi job AI2 hoàn tất trên snapshot OCR hiện hành; upload/re-OCR mới làm thay đổi snapshot nên cần job mới. |
| Vector `NOT_RUN` trên `/health` | Đây là model-discovery probe chưa chạy. Xác nhận embedding key/cap/consent và thử một truy vấn đủ điều kiện. |

## 6. Dừng và dọn dữ liệu local

Dừng containers nhưng giữ database/object-store volumes:

```bash
docker compose down
```

`docker compose down -v` xóa cả volumes chứa hồ sơ và dữ liệu local; chỉ chạy khi chủ động muốn xóa chúng. Không dùng lệnh đó trên môi trường dùng chung.

## 7. Chạy Backend ngoài Docker (tùy chọn)

Khởi động PostgreSQL, Kafka, MinIO và Keycloak bằng Compose trước. Trong một terminal:

```bash
cd backend
uv sync --frozen --extra dev
uv run alembic upgrade head
uv run uvicorn contract_intelligence.main:app --reload --port 8000
```

Trong terminal khác:

```bash
cd backend
uv run python -m contract_intelligence.worker
```

Khi chạy Python trên host, dùng `backend/.env.example` làm tài liệu cấu hình host và bảo đảm các địa chỉ DB/Kafka/MinIO/Keycloak dùng host ports tương ứng, không dùng tên DNS nội bộ Compose.

## 8. Kiểm tra thay đổi trước PR

```bash
cd backend
uv run ruff check src/ tests/
uv run mypy src/
uv run pytest tests/unit/ tests/architecture/
```

```bash
cd frontend
npm ci
npm run lint
npm run build
```

```bash
cd ai-service
uv sync --frozen --extra dev --extra web --extra kafka --extra mistral
uv run pytest -m "not live and not integration" --ignore=tests/test_hd_gold.py --ignore=tests/test_structure_reconstruction.py
```

CI chạy thêm integration tests với PostgreSQL/pgvector. Deploy workflow được kích hoạt bởi push vào `develop` (gồm PR merge), kiểm tra deploy config và chỉ deploy đúng SHA đó. Thiếu bất kỳ SSH secret nào thì job fail. Manual dispatch chỉ chạy trên `develop`. Environment `production` có thể yêu cầu review nếu repository admin cấu hình; khi đó deploy chờ người duyệt.
