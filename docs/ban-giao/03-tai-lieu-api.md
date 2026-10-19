# 03 · Tài liệu API (API Documentation)

| Thuộc tính | Nội dung |
|---|---|
| Người phụ trách | Chương (BE) |
| Phối hợp | Trang (FE), Văn Dũng (AI2) |
| Cập nhật | 19/10/2026 |
| Phiên bản hợp đồng API | `v4.1.0` (header `X-API-Contract`); `v4.2.0` khi PR #149 merge |
| Danh sách endpoint | [03b-api-endpoints.md](03b-api-endpoints.md): 103 endpoint, sinh tự động từ code |
| OpenAPI (Swagger) | [03c-openapi-backend.json](03c-openapi-backend.json): sinh tự động từ FastAPI |

Tài liệu này mô tả cách gọi API của backend: địa chỉ, xác thực, định dạng request và response, lỗi, giới hạn. Nó cũng mô tả hai giao tiếp nội bộ: backend với AI2 (HTTP có ký HMAC) và backend với AI1 (Kafka).

**Danh sách đầy đủ** từng endpoint, kèm quyền và mã trả về, nằm ở [03b](03b-api-endpoints.md). Request và response chi tiết nằm trong [03c](03c-openapi-backend.json). Cả hai được sinh từ chính code, nên luôn khớp với bản đang chạy.

## 1. Tài liệu nào dùng cho việc gì

| Tài liệu | Dùng khi |
|---|---|
| **03b, 03c** (thư mục này) | Cần biết API **đang có** gì: endpoint, quyền, schema. Sinh từ code |
| `docs/DOC-05b-frontend-backend-api-contract.md` | Cần **hợp đồng FE↔BE theo màn hình**: hành vi, mã lỗi, ví dụ, lịch sử phiên bản. Đây là tài liệu chính khi làm frontend |
| `frontend/API-BE.md` | Ghi chú của nhóm frontend về cách FE dùng API (do FE duy trì) |
| `docs/DOC-05-api-spec.yaml` | OpenAPI viết tay ban đầu (v0.3.0), đã bổ sung một số endpoint mới. **Không đầy đủ** bằng 03c |
| `docs/contracts/AI2-SERVICE-ENVELOPE-v1.vi.md`, `BE-AI2-PROCESSING-CONTRACT.vi.md`, `*.schema.json` | Hợp đồng backend↔AI2 (mục 7) |
| `docs/DOC-05d-kafka-ai1-ocr-contract.md` | Hợp đồng Kafka backend↔AI1 (mục 8) |

**Mở OpenAPI:**
- **Swagger:** dán nội dung 03c vào https://editor.swagger.io, hoặc chạy backend local rồi mở http://localhost:8000/docs. `/docs` tắt trên staging và production.
- **Postman:** *Import → File →* chọn `03c-openapi-backend.json`. Postman tạo collection theo nhóm. Đặt biến `baseUrl` và header `Authorization`, `X-Tenant-Id` như mục 3.

Cập nhật 03b và 03c sau khi đổi API:

```bash
cd backend && uv run python scripts/export_api_doc.py ../docs/ban-giao
```

## 2. Địa chỉ

| Môi trường | Base URL | Ghi chú |
|---|---|---|
| Production (frontend dùng) | `https://contract-intelligence.tech/api/v1` | Cùng origin với app (#140): trình duyệt không gửi CORS preflight |
| Production (host API) | `https://api.contract-intelligence.tech/api/v1` | Cho script và máy dev. Cùng backend |
| Local | `http://localhost:8000/api/v1` | `docker compose up` hoặc `uv run uvicorn` (xem [06](06-huong-dan-cai-dat-local.md)) |

Production đứng sau **Cloudflare (gói Free)**:
- **Mỗi request tối đa 100 MB** (vượt thì Cloudflare trả `413` dạng HTML).
- **Gửi body tối đa khoảng 125 giây** (#145; cách xử lý ở mục 6).
- **Chờ server trả lời tối đa 100 giây** (vượt thì `524`).

Không có endpoint nào phải chạy lâu như vậy: việc nặng (OCR, AI2) chạy nền, client theo dõi qua SSE.

## 3. Xác thực và phân quyền

- **Đăng nhập:** OpenID Connect với Keycloak, realm `contract-intelligence`.
  - Frontend dùng client công khai `contract-intel-frontend` (Authorization Code + PKCE), **không có refresh token** (#136).
  - Access token sống **15 phút** (`accessTokenLifespan: 900`); frontend lấy token mới bằng silent SSO.
  - Phiên SSO hết sau 30 phút không hoạt động, tối đa 10 giờ.
- **Mỗi request cần hai header:**
  ```http
  Authorization: Bearer <access_token>
  X-Tenant-Id: <tenant_id trong token>
  ```
  - `X-Tenant-Id` phải khớp claim `tenant_id` của token, sai thì `403`.
  - Thiếu hoặc sai token thì `401`.
  - Phiên đã đăng xuất (back-channel logout, #129) thì `401` `{"detail": "Session has ended"}`, kể cả khi token chưa hết hạn.
- **Vai trò:** `OPERATOR` (Vận hành), `REVIEWER` (Thẩm định), `ADMINISTRATOR` (Quản trị). **Quản trị luôn được** mọi endpoint có kiểm vai trò. Token không có vai trò nào của ứng dụng thì `403`.
- **Quyền theo hồ sơ (ACL):** ngoài vai trò, mỗi hồ sơ có chủ và danh sách chia sẻ (`read` hoặc `edit`, có hạn).
  - Endpoint ghi "Đã đăng nhập (quyền theo hồ sơ)" trong 03b sẽ kiểm ACL. Không có quyền thì `403`; hồ sơ không thấy được thì `404`.
  - Chi tiết: DOC-05b §2 và `backend/src/contract_intelligence/shared/acl.py`.

**Lấy token để thử API** (Postman, curl): client `contract-intel-frontend` **không bật** grant `password` (`directAccessGrantsEnabled: false`), kể cả trên local.
1. Đăng nhập app trên trình duyệt (local hoặc production).
2. Mở DevTools → Network, chọn một request `/api/v1/...`, chép giá trị header `Authorization` (`Bearer …`) và `X-Tenant-Id`.

Token sống 15 phút. Tài khoản test: xem [12 · Danh sách tài khoản](12-danh-sach-tai-khoan.md).

## 4. Định dạng request và response

- **Body JSON**, UTF-8. Upload dùng `multipart/form-data` (`POST /dossiers`) hoặc byte thô (`PUT /uploads/.../chunks/{n}`, #149).
- **Response thành công:** envelope `{ "data": …, "meta": { … } }`. Danh sách có `meta.total`, `meta.page`, `meta.page_size`.
- **Response lỗi:** hai dạng.

  | Nguồn lỗi | Dạng |
  |---|---|
  | Lỗi nghiệp vụ (domain) | `{"error": {"code": "DOSSIER_TOO_MANY_DOCUMENTS", "message": "…", "details": {…}}}` |
  | Lỗi HTTP thông thường và validate | `{"detail": "…"}` hoặc `{"detail": [ … ]}` (FastAPI) |

  Frontend đọc `error.message` nếu có, không thì `detail`. Bảng mã lỗi đầy đủ: DOC-05b §3.3.
- **Header backend luôn trả:**
  - `X-Request-Id`: echo header client gửi, hoặc server tự sinh. Dùng để tìm log.
  - `X-API-Contract`: phiên bản hợp đồng (DOC-05b).
  - `X-Backend-Version`: chỉ có ở dev/test.
  - `Server-Timing`: chỉ khi bật cấu hình, cho thời gian app và SQL.
- **Thời gian:** ISO 8601 có múi giờ (UTC).
- **ID:** chuỗi có tiền tố: `dos_…`, `doc_…`, `job_…`, `run_…` (xem [02](02-thiet-ke-csdl.md) §5).

## 5. Các luồng chính

| Luồng | Endpoint (theo thứ tự) |
|---|---|
| Tạo hồ sơ | `POST /dossiers` (multipart: `contract`, `annexes[]`, `metadata`) → `202 {dossier_id, job_id}` → OCR tự chạy |
| Theo dõi xử lý | `GET /runs?dossier_id=…` → `GET /runs/{id}/steps` + SSE `GET /runs/{id}/events` (sự kiện `step.changed`, `run.completed`, heartbeat 15 giây) |
| Xem kết quả OCR | `GET /dossiers/{id}/documents` → `GET /documents/{id}/pages`, `/lines`, `/content` (PDF, có `Range`) |
| Cây điều khoản | `GET /documents/{id}/clauses` |
| Mâu thuẫn | `GET /dossiers/{id}/conflicts`; graph AI2: `GET /dossiers/{id}/ai2/contract-graph/{graph_kind}` (+ `/evidence`), vết xử lý `GET /dossiers/{id}/ai2/processing-trace` |
| Hỏi đáp | `POST /dossiers/{id}/query` (ACL, hạn mức, lưu `query_trace`) hoặc `POST /dossiers/{id}/search`; lịch sử `GET /dossiers/{id}/queries` |
| Thẩm định, phê duyệt | `GET /review-queue`, thao tác trên `review_item`, khoá và duyệt hồ sơ |
| Chia sẻ | `PUT /dossiers/{id}/access`, tra người nhận `GET /users/lookup` |
| Quản trị | `/admin/*` (người dùng, hoạt động, dung lượng, giám sát Grafana `/admin/monitoring/session`), `/users*` |

Request và response mẫu của từng luồng: DOC-05b §5, theo 10 màn hình.

## 6. Giới hạn

| Giới hạn | Giá trị | Vượt thì |
|---|---|---|
| Dung lượng mỗi file PDF | 50 MiB (`UPLOAD_MAX_FILE_BYTES`) | `413` |
| Số file mỗi hồ sơ | 6 (1 hợp đồng + 5 phụ lục) | `422 DOSSIER_TOO_MANY_DOCUMENTS` |
| Một request qua Cloudflare | 100 MB, gửi body trong khoảng 125 s | `413` (HTML) hoặc kết nối bị reset |
| Hỏi đáp mỗi người dùng | 20 lần/phút (`QUERY_RATE_LIMIT_PER_MINUTE`) | `429` |
| Hỏi đáp mỗi tenant | 2.000 lần/24 giờ (`QUERY_DAILY_QUOTA_PER_TENANT`) | `429` |
| Người nhận chia sẻ mỗi lần | 100 | `422` |

**Tải hồ sơ lớn trên mạng chậm:** từ PR #149 (API v4.2.0), dùng `/uploads`.
- Mở phiên, gửi từng khúc 1 MiB, rồi `complete`. Cách này tránh được giới hạn 125 giây và 100 MB mỗi request.
- Chi tiết: DOC-05b §Màn hình 3 "Tải hồ sơ theo khúc".

## 7. Backend ↔ AI2 (HTTP nội bộ, ký HMAC)

AI2 (`ci-ai2-service`) chỉ nghe trong mạng Docker nội bộ; trình duyệt không gọi thẳng. Backend gọi:

| Việc | Method, đường dẫn trên AI2 |
|---|---|
| Gửi job tìm mâu thuẫn | `POST /jobs/idp`, theo dõi `GET /jobs/{job_id}` |
| Hỏi đáp | `POST {AI2_BASE_URL}/query` (mặc định `http://ai2-service:8002/query`; envelope trong body, trường `service_envelope`) |
| Đọc graph và vết xử lý | `GET /internal/contract-graph/{job_id}`, `…/evidence`, `GET /internal/processing-trace/{job_id}` |
| Xoá dữ liệu AI2 của hồ sơ | `DELETE /api/v1/dossiers/{dossier_id}` (scope `ai2.dossier.delete`, #131) |
| Kiểm tra sống | `GET /healthz`, `GET /readyz` |

**Envelope ký** (`ai2.service-envelope.v1`; code: `backend/.../infrastructure/ai_adapters.py: _service_envelope`):
- Gửi trong header `X-AI2-Service-Envelope` (JSON), hoặc trong body với `/query`:
  ```json
  {
    "schema_version": "ai2.service-envelope.v1",
    "issuer": "backend-service", "audience": "vsf-ai2", "key_id": "default",
    "tenant_id": "…", "actor_id": "…", "dossier_id": "…",
    "scopes": ["ai2.jobs.submit"],
    "issued_at": 1792400000, "expires_at": 1792400300,
    "nonce": "<uuid hex>",
    "payload_sha256": "<sha256 của payload chuẩn hoá>",
    "signature": "<hex>"
  }
  ```
- `payload_sha256` là SHA-256 của payload JSON (bỏ trường `service_envelope`), `sort_keys`, không khoảng trắng (`separators=(",", ":")`), UTF-8.
- `signature` là HMAC-SHA256 với khoá `AI2_SERVICE_HMAC_SECRET` (hai bên dùng chung), tính trên **envelope chuẩn hoá cùng cách, không có `signature`**.
- Envelope có hiệu lực **5 phút**. AI2 lưu `nonce` (`ai2.service_nonces`) để chặn gửi lại.
- Backend **từ chối gọi** khi chưa cấu hình secret (fail-closed).

Hợp đồng đầy đủ: `docs/contracts/AI2-SERVICE-ENVELOPE-v1.vi.md`, `AI2-IDP-REQUEST-v1.vi.md`, `BE-AI2-PROCESSING-CONTRACT.vi.md` và các `*.schema.json` cùng thư mục.

## 8. Backend ↔ AI1 (Kafka và MinIO)

AI1 (OCR) không có HTTP API cho backend; hai bên trao đổi qua Kafka (`ci-kafka`, nội bộ).

| Topic | Chiều | Nội dung |
|---|---|---|
| `dossier_events` | Backend → worker của backend | `dossier.uploaded`: hồ sơ mới hoặc chạy lại; worker mở run và gửi lệnh OCR |
| `ci.ai1.ocr.commands` | Backend → AI1 | Lệnh OCR theo tài liệu, kèm URL MinIO có chữ ký (presigned) để AI1 tải PDF và đẩy ảnh trang |
| `ci.ai1.ocr.results` | AI1 → Backend | Kết quả OCR (consumer group `ci-backend-ai1-results`); kết quả lớn hơn giới hạn Kafka thì để ở MinIO (`result_ref`) |
| `<topic>.dlq` | Backend | Message không xử lý được; chỉ giữ phần đầu và hash |

Backend chống xử lý trùng theo `event_id` (`processed_event`). Hợp đồng đầy đủ: `docs/DOC-05d-kafka-ai1-ocr-contract.md`, `docs/contracts/AI1-AI2-CONTRACT.vi.md`.

## 9. Keycloak → Backend (webhook)

`POST /api/v1/auth/webhooks/keycloak`:
- Keycloak báo sự kiện người dùng (tạo, sửa, xoá) để backend đồng bộ bảng `app_user`.
- Không dùng token. Thay vào đó, header `X-Keycloak-Signature` là HMAC-SHA256 của body, với `KEYCLOAK_WEBHOOK_SECRET`.

`POST /api/v1/auth/backchannel-logout` (#129):
- Keycloak gọi khi một phiên kết thúc, trong mạng nội bộ; Caddy trả `404` cho mọi request từ Internet.
- Không có trong OpenAPI (`include_in_schema=False`).
