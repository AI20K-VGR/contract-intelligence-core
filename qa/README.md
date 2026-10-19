# QA — kiểm thử hệ thống (smoke, security, performance, E2E)

Bộ test chạy **từ bên ngoài** vào stack đang chạy (`docker compose up`), giống
cách frontend và người dùng thật gọi hệ thống: đăng nhập Keycloak bằng
Authorization Code + PKCE, gọi REST API của backend, gọi thẳng AI2 để kiểm tra
lớp tin cậy giữa các service. Nó bổ sung (không thay thế) unit/integration test
đã có trong `backend/tests`, `ai-service/tests`, `frontend/tests`.

Báo cáo kết quả và các phát hiện: [`docs/qa/BAO-CAO-KIEM-THU-QA.vi.md`](../docs/qa/BAO-CAO-KIEM-THU-QA.vi.md).

## Cấu trúc

```
qa/
├── smoke/        20 test — stack sống, login 3 vai trò, đường đọc chính, bundle JS FE, Kafka/worker/consumer-group
├── security/    ~120 test — JWT, RBAC, tenant, IDOR, multi-tenant, mass-assignment, token revoke,
│                 input/NUL, file xấu, MinIO, CORS, HMAC AI2, webhook, cấu hình prod, SCA
├── performance/  latency có ngân sách + scaling + stress/spike (thu CPU/RAM/DB) + throughput pipeline + locust soak
├── e2e/          upload → AI1 OCR → AI2 → PENDING_REVIEW → chia sẻ → review; + nội dung đối kháng (injection/XSS)
├── lib/          config (QA_*), login PKCE, sinh PDF, bộ tạo tải, thu tài nguyên, Keycloak admin helper
└── scripts/      run-qa, stack-mode, sca-scan, summarize
```

### Môi trường đích (`QA_ENV`)

`QA_ENV=local` (mặc định) hoặc `QA_ENV=prod`. Trên `prod` bộ test tự: bỏ qua test cần truy cập host
(docker/MinIO/Keycloak-admin/upload nặng), coi WAF-403 là hợp lệ, không chạy load, và assert các mục đã
hardening (docs bị chặn…). Trỏ tới prod bằng các biến `QA_BACKEND_URL`, `QA_KEYCLOAK_URL`,
`QA_FRONTEND_URL`, `QA_KEYCLOAK_REDIRECT_URI`, `QA_ALLOWED_ORIGIN` và mật khẩu `QA_*_PASSWORD`
(đặt qua biến môi trường, **không** ghi vào file). Xem §9 báo cáo để biết lệnh đầy đủ.

### SCA (quét dependency)

```bash
./qa/scripts/sca-scan.sh            # pip-audit (backend, ai-service) + npm audit (frontend)
./qa/scripts/sca-scan.sh --images   # thêm trivy quét image (cần cài trivy)
```

## Chạy nhanh

Cần stack đang chạy (xem `HUONG-DAN-TEST-E2E-UPLOAD.md`) và [`uv`](https://docs.astral.sh/uv/).

```powershell
# Smoke + security + performance (không upload, không tốn phí)
.\qa\scripts\run-qa.ps1

# Một suite
.\qa\scripts\run-qa.ps1 -Suites smoke

# Thêm E2E pipeline thật (xem mục "Chi phí" bên dưới)
.\qa\scripts\run-qa.ps1 -Pipeline
```

```bash
./qa/scripts/run-qa.sh                         # smoke security performance
QA_RUN_PIPELINE=1 ./qa/scripts/run-qa.sh smoke e2e
```

Hoặc gọi pytest trực tiếp:

```bash
cd qa
uv run --with-requirements requirements.txt pytest smoke security -v
uv run --with-requirements requirements.txt pytest -m "security and static"   # không cần stack (dùng cho CI)
```

Kết quả nằm ở `qa/reports/` (bị git ignore): `SUMMARY.md` (bảng tổng hợp, đính kèm khi bàn giao),
`junit-*.xml` (cho CI), `results.json`, `perf.json`, `e2e.json`.

## Cấu hình (biến môi trường)

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `QA_BACKEND_URL` | `http://127.0.0.1:8000` | Backend API |
| `QA_AI2_URL` | `http://127.0.0.1:8002` | AI2 (prod không publish cổng → test AI2 tự skip) |
| `QA_KEYCLOAK_URL` / `QA_KEYCLOAK_REALM` | `http://localhost:8080` / `contract-intelligence` | Keycloak |
| `QA_FRONTEND_URL` | `http://localhost:5173` | Frontend (skip nếu không chạy) |
| `QA_ADMIN_USER` / `QA_ADMIN_PASSWORD` … `QA_OPERATOR_*`, `QA_REVIEWER_*` | user seed trong `keycloak/realm-export.json` | Tài khoản 3 vai trò |
| `QA_RUN_PIPELINE` | tắt | `1` để chạy E2E upload thật |
| `QA_PIPELINE_TIMEOUT_S` | `600` | Chờ tối đa tới PENDING_REVIEW |
| `QA_KEEP_DOSSIER` | tắt | `1` để giữ hồ sơ E2E (mặc định xoá sau test) |
| `QA_PERF_REQUESTS` / `QA_PERF_CONCURRENCY` | `200` / `20` | Hình dạng tải |
| `QA_PERF_HEALTH_P95_MS` / `QA_PERF_API_P95_MS` | `150` / `800` | Ngân sách p95 |
| `QA_PERF_MAX_ERROR_RATE` | `0.01` | Tỉ lệ lỗi tối đa |

Chạy với môi trường khác (staging): đặt `QA_BACKEND_URL`, `QA_KEYCLOAK_URL`,
`QA_KEYCLOAK_REDIRECT_URI`, `QA_ALLOWED_ORIGIN` và tài khoản test của môi trường đó.
Không chạy `performance/` vào production giờ hành chính.

## Chi phí và chế độ "free"

Test mặc định **không** upload PDF hợp lệ nên không khởi động OCR/AI2. Riêng `e2e/`:

- PDF mẫu được sinh lúc chạy (repo cấm commit PDF), có sẵn lớp text, nên AI1
  đọc thẳng bằng `pymupdf` và không gọi Mistral (đã kiểm chứng trong log `ci-ai1-worker`: `"engine": "pymupdf"`).
- Muốn chắc chắn không có lời gọi trả phí nào (kể cả AI2 LLM), chuyển stack sang chế độ free trước:

  ```powershell
  .\qa\scripts\stack-mode.ps1 free    # AI1_OCR_ENGINE=pymupdf, tắt egress AI2
  .\qa\scripts\run-qa.ps1 -Pipeline
  .\qa\scripts\stack-mode.ps1 paid    # quay về mặc định docker-compose.yml
  ```

  `stack-mode` recreate `backend-worker` và `ai2-service` theo `docker-compose.yml` hiện tại.
  Biến chỉ truyền qua shell lúc tạo container (vd. `AI2_LLM_API_KEY`) cần được set lại trước khi chạy `paid`.

## Quy ước

- Test chỉ gửi những request **bị từ chối** hoặc chỉ đọc; E2E là test duy nhất tạo dữ liệu và tự xoá.
- Lỗ hổng/khoảng trống đã biết được đánh dấu `xfail` với mã `FINDING SEC-xx`, nên suite vẫn là
  cổng hồi quy: khi lỗi được sửa, test chuyển thành `XPASS` → xoá marker `xfail`.
- Test performance **fail thật** khi vượt ngân sách (không xfail): đó là cam kết SLO, chỉnh ngân sách
  qua biến môi trường nếu team thống nhất con số khác.
- Soak test dài hơn: xem docstring `performance/locustfile.py`.
