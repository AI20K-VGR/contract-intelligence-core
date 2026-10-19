# DOC-05b · FRONTEND-BACKEND API CONTRACT — Contract Intelligence

**Đặc tả Hợp đồng Giao tiếp Kỹ thuật Frontend ↔ Backend**

| Thuộc tính | Nội dung |
|---|---|
| Mã tài liệu | **DOC-05b** / Contract Intelligence (PROD-01) |
| Phiên bản / SemVer | **`v4.2.0`** — tải hồ sơ theo khúc (`/uploads`) để không bị Cloudflare cắt ở khoảng 125 giây (#145). **`v4.1.0`** — đăng xuất có hiệu lực ngay: token của phiên Keycloak đã kết thúc nhận `401` `{"detail": "Session has ended"}`. **`v4.0.0`** (breaking) — chia sẻ hồ sơ chỉ với người dùng có thật cùng tenant: `PUT /dossiers/{id}/access` kiểm tra người nhận mới trong Keycloak (`422 share_recipient_not_found`), `shared_with` tối đa 100; thêm `GET /users/lookup`; `GET /users/directory` bắt OPERATOR gửi `q` từ 3 ký tự; không gửi thư tới tên miền dành riêng (`422 email_domain_undeliverable` khi tạo người dùng hoặc gửi lại lời mời). **`v3.3.0`** — `GET /dossiers` thêm `document_counts`, `contract_ocr` cho mỗi hồ sơ (bỏ 3 lần gọi mỗi dòng); header `Server-Timing`. **`v3.2.0`** — tiến độ trong bước: `progress` trên `GET /runs/{id}/steps` và SSE `step.changed`; mã lỗi `AI1_NO_READABLE_PAGE`. **`v3.1.0`** — bật consent AI2 tự reindex hồ sơ, response thêm `ai2_reindex_queued`. **`v3.0.0`** — siết quyền trước pentest (#96): token không có role ứng dụng trả `403` thay vì thành `OPERATOR`; `/ai/jobs/{id}` chỉ `ADMINISTRATOR`; batch cancel/resume chỉ người tạo hoặc `ADMINISTRATOR`. Xem [Lịch sử phiên bản](#lịch-sử-phiên-bản) |
| Trạng thái | Đã chốt — Sẵn sàng triển khai Frontend & Backend |
| Owner | Tech Lead / Frontend Lead / Backend Lead |
| Ngày hiệu lực | 17/09/2026 |
| Upstream | `docs/DOC-05-api-spec.yaml` (v0.3.0), `docs/DOC-04-architecture.md` (v0.7.0), `docs/DOC-04b-postgres-schema.sql` (v1.2.0) |
| Downstream | `frontend/` (React/Vue/Vite/Next.js), `backend/` (FastAPI Routers, DTOs) |

---

## Mục lục

1. [Nguyên tắc Thiết kế & Giao thức Chung](#1-nguyên-tắc-thiết-kế--giao-thức-chung)
2. [Cơ chế Xác thực & Phân quyền (Auth & RBAC)](#2-cơ-chế-xác-thực--phân-quyền-auth--rbac)
3. [Chuẩn Định dạng Dữ liệu & Xử lý Lỗi](#3-chuẩn-định-dạng-dữ-liệu--xử-lý-lỗi)
4. [Tọa độ Bounding Box & Hiển thị PDF (CPS)](#4-tọa-độ-bounding-box--hiển-thị-pdf-cps)
5. [Chi tiết API Phân theo 10 Màn hình Frontend](#5-chi-tiết-api-phân-theo-10-màn-hình-frontend)
   - [Màn hình 1: Authentication & Tenant Switcher](#màn-hình-1-authentication--tenant-switcher)
   - [Màn hình 2: Dashboard & Batch Operations](#màn-hình-2-dashboard--batch-operations)
   - [Màn hình 3: Dossier Creation, Upload & Manifest Confirmation](#màn-hình-3-dossier-creation-upload--manifest-confirmation)
   - [Màn hình 4: Pipeline Run & Realtime Processing Monitor](#màn-hình-4-pipeline-run--realtime-processing-monitor)
   - [Màn hình 5: PDF Document Explorer & Clause Tree Viewer](#màn-hình-5-pdf-document-explorer--clause-tree-viewer)
   - [Màn hình 6: Fact & Extraction Inspector](#màn-hình-6-fact--extraction-inspector)
   - [Màn hình 7: Conflict Resolution & Review Workbench](#màn-hình-7-conflict-resolution--review-workbench)
   - [Màn hình 8: Dossier Approval & External Grants](#màn-hình-8-dossier-approval--external-grants)
   - [Màn hình 9: Re-OCR Workbench](#màn-hình-9-re-ocr-workbench)
   - [Màn hình 10: Optimization Studio (Admin)](#màn-hình-10-optimization-studio-admin)
   - [Chia sẻ hồ sơ & hàng chờ thẩm định (v1.7.0)](#chia-sẻ-hồ-sơ--hàng-chờ-thẩm-định-v170)
   - [Thông báo cá nhân (đề xuất, BE chưa có)](#thông-báo-cá-nhân-đề-xuất-be-chưa-có)
6. [Bộ TypeScript Interfaces & DTOs Chuẩn](#6-bộ-typescript-interfaces--dtos-chuẩn)
7. [Chiến lược Polling & Thời gian thực (Realtime)](#7-chiến-lược-polling--thời-gian-thực-realtime)
8. [Quy trình Quản lý Thay đổi (Versioning & Change Management)](#8-quy-trình-quản-lý-thay-đổi-versioning--change-management)

---

## 1. Nguyên tắc Thiết kế & Giao thức Chung

### 1.1 Base URL & Phiên bản API
- Mọi endpoint API nghiệp vụ được phục vụ tại:
  ```http
  https://{host}/api/v1
  ```
- Định dạng URL: sử dụng `kebab-case` cho các segment đường dẫn (ví dụ: `/review-items`, `/external-approvals`, `/re-ocr`).
- Danh từ số nhiều cho các resource collections (`/dossiers`, `/documents`, `/batches`, `/runs`).

### 1.2 Content-Type & Headers
| Header | Bắt buộc? | Mô tả |
|---|:---:|---|
| `Authorization` | Có | `Bearer <access_jwt_token>` (RFC 7519) — JWT được cấp bởi **Keycloak**, frontend lưu trong Memory/Secure Cookie. |
| `X-Tenant-Id` | Có | ID định danh không gian tenant (ví dụ: `tenant_vgr_01`) |
| `Content-Type` | Có | `application/json` (cho request payloads) hoặc `multipart/form-data` (khi upload file) |
| `Accept` | Có | `application/json` hoặc `application/pdf` (khi tải file gốc) |
| `X-Request-Id` | Tùy chọn | Client sinh UUIDv4 để truy vết log từ Frontend sang Backend |

Header backend trả về để đo hiệu năng (**v3.3.0**). Bật mặc định khi chạy local (`ENV` là `dev`, `test`); staging và production (`ENV` là `staging`, `prod`) tắt mặc định, chỉ bật bằng `SERVER_TIMING_ENABLED=true` (production: trong `deploy/.env.prod`) trong lúc cần đo, vì header lộ thời gian xử lý cho mọi người gọi API:

| Header | Mô tả |
|---|---|
| `Server-Timing` | `app;dur=<ms>, db;dur=<ms>;desc="<n> queries"`: thời gian xử lý trong API (tới khi gửi header, với SSE là tới byte đầu) và tổng thời gian + số câu SQL của request. Xem ở DevTools → Network → Timing; phần còn lại của thời gian request là mạng (Cloudflare → origin). |
| `Timing-Allow-Origin` | Các origin trong `CORS_ALLOW_ORIGINS`, để frontend đọc được giá trị trên qua `performance.getEntriesByType('resource')[i].serverTiming`. |

---

## 2. Cơ chế Xác thực & Phân quyền (Auth & RBAC)

### 2.1 Luồng Xác thực Keycloak SSO

**Backend TUYỆT ĐỐI KHÔNG issue Access Token / Refresh Token.**

Frontend (React) xử lý toàn bộ auth flow với Keycloak:
```
Frontend                          Keycloak                  Backend
    │                                │                        │
    ├──► Login Page ──────────────►│ Login Credentials      │
    │◄── access_token (RS256), id_token ◄─│ (không có refresh_token) │
    │                                │                        │
    │   (Frontend giữ phiên trong bộ nhớ tab, #133)          │
    │                                │                        │
    │   Gần hết hạn / F5 / tab mới:                          │
    ├──► iframe /auth?prompt=none ──►│ cookie SSO HttpOnly    │
    │◄── access_token mới ◄─────────│                        │
    │                                │                        │
    │   Khi gọi API:                                         │
    │─── Authorization: Bearer <token> ─────────────────────►│ (Backend verify RS256 via JWKS)
```

**Backend chỉ làm nhiệm vụ:**
1. **Verify** chữ ký RS256 của access_token bằng public key từ Keycloak JWKS endpoint.
2. **Parse** JWT claims → `AuthenticatedUser` context cho mỗi request.
3. **Map** Keycloak `realm_access.roles[]` → RBAC role nội bộ.

**Keycloak event webhook:**
- Keycloak gọi `POST /auth/webhooks/keycloak` khi user LOGIN/REGISTER/UPDATE_PROFILE/DELETE_ACCOUNT.
- Backend sync user vào local `app_user` table (để join với audit logs).
- Frontend **KHÔNG** gọi endpoint này.

**JWT Token Structure (Keycloak RS256):**
```json
{
  "sub": "usr_01J9X1K8...",
  "email": "john@company.com",
  "name": "Nguyễn Văn Reviewer",
  "tenant_id": "tenant_vgr_01",
  "realm_access": {"roles": ["ci_reviewer"]},
  "iss": "https://sso.company.com/realms/contract-intelligence",
  "aud": "ci-backend",
  "exp": 1790000000,
  "iat": 1789964000
}
```

**RBAC Role Mapping:**
| Keycloak Realm Role | Backend RBAC Role |
|---|---|
| `ci_administrator` | `ADMINISTRATOR` |
| `ci_reviewer` | `REVIEWER` |
| `ci_operator` | `OPERATOR` |
| *(không match)* | **Không có.** Request bị từ chối `403 FORBIDDEN` (**v3.0.0**; trước đây được coi là `OPERATOR`) |

### 2.2 Quy tắc Tenant Isolation
- Client **bắt buộc** truyền header `X-Tenant-Id: <tenant_id>`.
- Backend kiểm tra nếu `X-Tenant-Id` khác với `claim.tenant_id` trong JWT -> trả về ngay lập tức **`403 Forbidden` (`TenantMismatch`)**.
- Mọi truy vấn dữ liệu từ database đều được lọc theo `tenant_id` để ngăn ngừa tuyệt đối việc rò rỉ dữ liệu giữa các khách hàng doanh nghiệp.

### 2.3 Ma trận 3 Vai trò RBAC (`x-rbac`)
| Vai trò (`role`) | Quyền hạn trên Frontend | Các chức năng chính |
|---|---|---|
| `OPERATOR` | Vận hành nhập liệu & xử lý | Upload tài liệu, tạo hồ sơ, kích hoạt pipeline runs, theo dõi batch, yêu cầu Re-OCR |
| `REVIEWER` | Thẩm định & Xác nhận | Xem hồ sơ, thẩm định fact/conflict, xác nhận manifest, submit review actions, xem lịch sử revision |
| `ADMINISTRATOR` | Quản trị toàn diện | Quản trị người dùng, phê duyệt chính thức dossier, phát hành External Grants, quản lý chiến dịch tối ưu hóa prompt |

---

## 3. Chuẩn Định dạng Dữ liệu & Xử lý Lỗi

### 3.1 Định dạng Danh sách Phân trang (Pagination Envelope)
Mọi endpoint trả về danh sách đều áp dụng chuẩn phân trang thống nhất:
```json
{
  "items": [ ... ],
  "total": 142,
  "page": 1,
  "page_size": 20,
  "total_pages": 8
}
```
Query parameters chuẩn:
- `page`: Số trang (1-indexed, mặc định: `1`)
- `page_size`: Kích thước trang (mặc định: `20`, tối đa: `100`)

### 3.2 Chuẩn Xử lý Lỗi (RFC 7807 Problem Details)
Mọi phản hồi lỗi (HTTP status >= 400) đều tuân theo chuẩn RFC 7807 với `Content-Type: application/problem+json`:
```json
{
  "type": "https://api.contract-ai.io/errors/VERSION_CONFLICT",
  "title": "Conflict Detected",
  "status": 409,
  "detail": "Review item was updated by another reviewer. Current version is 3.",
  "instance": "/api/v1/review-items/ri_01J9X2P/actions",
  "code": "VERSION_CONFLICT",
  "current_version": 3,
  "timestamp": "2026-09-17T15:30:00Z"
}
```

### 3.3 Mã Lỗi Doanh nghiệp Thường Gặp
| HTTP Status | Code Doanh nghiệp | Khi nào xảy ra? | Hành động của Frontend |
|:---:|---|---|---|
| `401` | `UNAUTHORIZED` | Token hết hạn hoặc không hợp lệ. **v3.0.0:** `error.message` chỉ là `Token has expired` hoặc `Invalid token`, không nói kiểm tra nào hỏng (issuer, audience, kid); lý do ghi ở log backend. **v4.1.0:** thêm `Session has ended` khi phiên Keycloak của token đã kết thúc (người dùng đăng xuất, quản trị khoá tài khoản), dù token chưa hết hạn. Lưu ý: body `401` thực tế là `{"detail": "..."}` của FastAPI, không theo khung `error` | Điều hướng người dùng về màn hình Login hoặc gọi refresh token. Không dựa vào nội dung `message` |
| `403` | `FORBIDDEN` | Sai `X-Tenant-Id` hoặc không đủ quyền `x-rbac` | Hiển thị thông báo "Không có quyền thực hiện chức năng này" |
| `404` | `NOT_FOUND` | Không tìm thấy ID hồ sơ / tài liệu / run | Hiển thị màn hình 404 hoặc thông báo mục đã bị xóa |
| `409` | `VERSION_CONFLICT` | Phiên bản `base_version` gửi lên cũ hơn DB | **Refetch item mới nhất**, cảnh báo reviewer có xung đột chỉnh sửa |
| `422` | `VALIDATION_ERROR` | Request body sai kiểu dữ liệu hoặc thiếu trường | Hiển thị lỗi tương ứng trên form input |
| `422` | `DOSSIER_TOO_MANY_DOCUMENTS` | **v1.2.0.** Hồ sơ quá 6 tài liệu, khi tải lên (`POST /dossiers`) hoặc sau khi tách (`POST /dossiers/{id}/split`). `details`: `{ limit, count }`. Giới hạn đếm **tài liệu** (mỗi file PDF tải lên, mỗi phần sau khi tách là một tài liệu), không đếm trang | Hiện `error.message`. Tải lên: "Hồ sơ tối đa 6 file PDF (1 hợp đồng và tối đa 5 phụ lục). Bạn đã chọn 7 file." Tách: "Sau khi tách, hồ sơ tối đa 6 tài liệu. Cách tách này làm hồ sơ có 7 tài liệu." (số lấy từ `details`) |
| `413` | `detail`: `"<tên file>: file exceeds 50 MB"` | **v2.0.1.** Một file PDF vượt `UPLOAD_MAX_FILE_BYTES` (mặc định 50 MiB), ở `POST /dossiers` và `POST /dossiers/{id}/documents`. Backend trả JSON | Báo file nào quá lớn. Nên kiểm `file.size` trước khi gửi |
| `413` | (không có, body là **HTML** của Cloudflare) | **v2.0.1.** Bản online (`api.contract-intelligence.tech`, sau Cloudflare gói Free): **cả request vượt 100 MB** bị Cloudflare chặn trước khi tới backend. `POST /dossiers` gửi hợp đồng và mọi phụ lục trong **một** request, nên bộ hồ sơ tổng trên 100 MB gặp lỗi này | Kiểm tổng dung lượng các file trước khi gửi, chừa vài MB cho phần đầu multipart. Gặp 413 mà body không phải JSON thì báo "Bộ hồ sơ vượt 100 MB, hãy bớt phụ lục hoặc nén file", đừng parse body |
| `422` | `share_recipient_not_found` | **v4.0.0.** `PUT /dossiers/{id}/access`: một người nhận mới không phải người dùng đang bật cùng tenant với người gọi (sai email, khác đơn vị, bị khoá, không tồn tại). `details`: `{ rejected_emails: [...] }`. Không lưu gì và không gửi thư nào | Hiện `error.message` ("Không tìm thấy email này trong đơn vị của bạn, hoặc người này chưa kích hoạt tài khoản. Vui lòng kiểm tra lại."), đánh dấu các email trong `details.rejected_emails` |
| `422` | `email_domain_undeliverable` | **v4.0.0.** `POST /users`, `POST /users/{id}/invite`: email thuộc tên miền không nhận thư (`.local`, `.test`, `.example`, `.invalid`, `localhost`, `example.com/net/org`). Không tạo người dùng, không gửi thư. `details`: `{ field }` ở `POST /users`, `{ email }` ở `/invite` | Hiện `error.message` ("Tên miền email không nhận được thư, vui lòng kiểm tra lại.") ở ô email |
| `422` | `directory_query_required` | **v4.0.0.** `GET /users/directory` do OPERATOR gọi mà không có `q` hoặc `q` dưới 3 ký tự. `details`: `{ min_length: 3 }` | Chỉ gọi khi người dùng đã gõ đủ 3 ký tự; chia sẻ theo email thì dùng `GET /users/lookup` |
| `422` | `contract_required` / `contract_not_unique` | **v1.2.0.** Hồ sơ không có, hoặc có nhiều hơn một, hợp đồng chính (`POST /dossiers/{id}/split`, `POST /dossiers/{id}/manifest/confirm`) | Yêu cầu chọn đúng một phần hoặc tài liệu là hợp đồng |
| `500` | `INTERNAL_ERROR` | Lỗi phía server / database / AI service | Hiển thị toast lỗi và mã `X-Request-Id` để liên hệ IT |

---

## 4. Tọa độ Bounding Box & Hiển thị PDF (CPS)

Để đảm bảo Bounding Box khớp chính xác trên giao diện PDF canvas bất kể kích thước màn hình và độ thu phóng (zoom/scale):
- Tọa độ trả về từ API luôn theo chuẩn **Canonical Page Space (CPS, tỉ lệ chuẩn hóa 0..1)**:
  ```json
  "bbox": [x0, y0, x1, y1]
  ```
  - `x0`: Tọa độ cạnh trái (0.0 = mép trái trang, 1.0 = mép phải trang)
  - `y0`: Tọa độ cạnh trên (0.0 = mép trên cùng, 1.0 = mép đáy trang)
  - `x1`: Tọa độ cạnh phải
  - `y1`: Tọa độ cạnh dưới

### Công thức Render Bbox của Frontend:
Khi vẽ khung highlight lên canvas PDF với kích thước render thực tế là `renderedWidth` và `renderedHeight`:
```typescript
const pixelBox = {
  left: bbox[0] * renderedWidth,
  top: bbox[1] * renderedHeight,
  width: (bbox[2] - bbox[0]) * renderedWidth,
  height: (bbox[3] - bbox[1]) * renderedHeight,
};
```

---

## 5. Chi tiết API Phân theo 10 Màn hình Frontend

### Màn hình 1: Authentication & Tenant Switcher
Màn hình hiển thị thông tin user hiện tại (từ Keycloak JWT). Frontend xử lý login/refresh/logout trực tiếp với Keycloak.

**Luồng Frontend:**
1. User click "Đăng nhập" → redirect đến Keycloak login page.
2. Keycloak trả `access_token` + `id_token` về frontend (OIDC callback). Client `contract-intel-frontend` đặt `use.refresh.tokens=false`, nên **không có `refresh_token`**.
3. Frontend giữ phiên chỉ trong bộ nhớ của tab (`InMemoryWebStorage`, #133); không có token trong `localStorage`/`sessionStorage`.
4. Gần hết hạn, khi F5 hay mở tab mới, frontend lấy access token mới bằng iframe `prompt=none` theo cookie phiên SSO HttpOnly của Keycloak (`signinSilent({ forceIframeAuth: true })`). Phiên SSO đã hết thì Keycloak trả `login_required` và frontend về màn đăng nhập.
5. Khi user click "Đăng xuất", frontend gọi Keycloak logout endpoint trực tiếp.
6. **v4.1.0:** khi một phiên kết thúc (đăng xuất, quản trị đăng xuất hộ hoặc khoá tài khoản), Keycloak gọi `POST /auth/backchannel-logout` của backend trong mạng nội bộ (OIDC Back-Channel Logout). Từ đó mọi access token của phiên (`sid`) nhận `401` với body `{"detail": "Session has ended"}`, thay vì còn dùng được tới khi hết hạn (tối đa 15 phút). Frontend không phải gọi gì thêm; `401` vẫn xử lý như hiện tại (về màn đăng nhập). Phiên kết thúc vì hết thời gian chờ không gửi thông báo này: token còn dùng được tới `exp`.

| Phương thức | Endpoint | Phân quyền | Chức năng |
|:---:|---|:---:|---|
| `GET` | `/auth/me` | Mọi role | Lấy thông tin user hiện tại (từ Keycloak JWT claims) |
| `POST` | `/auth/webhooks/keycloak` | Webhook (Keycloak) | Sync user từ Keycloak event vào local DB |
| `POST` | `/auth/backchannel-logout` | Chỉ Keycloak (mạng nội bộ; Caddy trả `404` từ Internet) | **v4.1.0.** Nhận `logout_token` (form) khi một phiên kết thúc; backend ghi `sid` để từ chối token của phiên đó. `200` khi hợp lệ, `400` `{"error": "invalid_request"}` khi token không hợp lệ. Không có trong OpenAPI |

**GET /auth/me Response:**
```json
{
  "data": {
    "id": "usr_01J9X1K8...",
    "email": "john@company.com",
    "display_name": "Nguyễn Văn Reviewer",
    "role": "REVIEWER",
    "tenant_id": "tenant_vgr_01"
  },
  "meta": {}
}
```

**POST /auth/webhooks/keycloak (Keycloak → Backend):**
- Event types: `LOGIN`, `REGISTER`, `UPDATE_PROFILE`, `DELETE_ACCOUNT`
- Backend sync user vào `app_user` table (keycloak_sub, email, display_name, role).
- Response: `{"data": {"synced": true, "user_id": "...", "action": "LOGIN"}}`

---

### Màn hình 2: Dashboard & Batch Operations
Hiển thị tổng quan các lô xử lý (Batches), KPI trạng thái hợp đồng, tổng chi phí LLM, và bảng điều khiển Pause/Resume.

| Phương thức | Endpoint | Phân quyền `x-rbac` | Chức năng |
|:---:|---|:---:|---|
| `GET` | `/batches` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | Danh sách các lô hợp đồng kèm tiến độ xử lý |
| `POST` | `/batches` | `OPERATOR`, `ADMINISTRATOR` | Tạo lô mới (hỗ trợ upload gói ZIP chứa nhiều hồ sơ) |
| `GET` | `/batches/{id}` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | Chi tiết một lô và danh sách dossier bên trong |
| `GET` | `/batches/{id}/summary` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | Thống kê số lượng hồ sơ (thành công, lỗi, cần review, chi phí) |
| `POST` | `/batches/{id}/cancel` | `OPERATOR`, `ADMINISTRATOR` | Dừng khẩn cấp toàn bộ tác vụ đang chạy trong batch. **v3.0.0:** OPERATOR chỉ với batch do mình tạo; batch của người khác trả `404`. ADMINISTRATOR: mọi batch trong tenant |
| `POST` | `/batches/{id}/resume` | `OPERATOR`, `ADMINISTRATOR` | Tiếp tục chạy lại các hồ sơ bị tạm dừng / lỗi. **v3.0.0:** như `cancel`, OPERATOR chỉ với batch của mình |
| `GET` | `/ops/metrics` | `ADMINISTRATOR` | Dashboard thống kê tải server, độ trễ và chi phí token theo ngày |

---

### Màn hình 3: Dossier Creation, Upload & Manifest Confirmation
Màn hình khởi tạo hồ sơ, tải lên các file PDF (hợp đồng gốc + các phụ lục) và kiểm tra xác nhận danh mục tài liệu dự kiến.

> **Frontend từ 16/10/2026 (PR #122):** không còn màn xác nhận manifest. Vai trò hợp đồng/phụ lục người dùng chọn lúc tải lên (`POST /dossiers`) hoặc lúc tách tệp (`POST /dossiers/{id}/split`) được backend tự xác nhận (`confirm_uploaded_manifest`) trước khi trả `202`, nên AI2 chạy ngay khi OCR xong. `GET /dossiers/{id}/manifest` và `POST /dossiers/{id}/manifest/confirm` vẫn giữ nguyên; frontend không gọi. API không đổi nên phiên bản hợp đồng không đổi.

| Phương thức | Endpoint | Phân quyền `x-rbac` | Chức năng |
|:---:|---|:---:|---|
| `POST` | `/dossiers` | `OPERATOR`, `ADMINISTRATOR` | Tạo mới hồ sơ hợp đồng (Dossier) |
| `GET` | `/dossiers` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | Danh sách hồ sơ có lọc theo `status`, `has_conflicts`. **v3.3.0:** mỗi hồ sơ có thêm `document_counts`, `contract_ocr` (xem dưới bảng) |
| `GET` | `/dossiers/{id}` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | Xem chi tiết hồ sơ |
| `PATCH` | `/dossiers/{id}` | `OPERATOR`, `ADMINISTRATOR` | Đổi tên hoặc cập nhật metadata của hồ sơ |
| `POST` | `/dossiers/{id}/documents` | `OPERATOR`, `ADMINISTRATOR` | Upload file PDF vào hồ sơ (`multipart/form-data`) |
| `GET` | `/dossiers/{id}/documents` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | Danh sách các file PDF kèm vai trò `CONTRACT` hoặc `ANNEX` |
| `GET` | `/dossiers/{id}/manifest` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | Xem Manifest dự thảo phân loại tài liệu sau bước tiền xử lý |
| `POST` | `/dossiers/{id}/manifest/confirm` | `OPERATOR`, `ADMINISTRATOR` | Xác nhận phân loại tài liệu để kích hoạt bước phân tích sâu |
| `POST` | `/dossiers/{id}/split` | `OPERATOR`, `ADMINISTRATOR` | **v1.1.0.** Tách một PDF trộn (hợp đồng + phụ lục) thành từng tài liệu theo khoảng trang người dùng xác nhận |
| `POST` | `/uploads` | `OPERATOR`, `ADMINISTRATOR` | **v4.2.0.** Mở phiên tải hồ sơ theo khúc: khai báo các file và `metadata` (xem dưới bảng) |
| `PUT` | `/uploads/{upload_id}/files/{index}/chunks/{n}` | người mở phiên | **v4.2.0.** Gửi một khúc (byte thô) |
| `GET` | `/uploads/{upload_id}` | người mở phiên | **v4.2.0.** Các khúc đã nhận, để gửi tiếp sau khi mất mạng |
| `POST` | `/uploads/{upload_id}/complete` | người mở phiên | **v4.2.0.** Ghép các khúc và tạo hồ sơ, trả như `POST /dossiers` |
| `DELETE` | `/uploads/{upload_id}` | người mở phiên | **v4.2.0.** Huỷ phiên, xoá các khúc đã gửi |

- **Số tài liệu và trạng thái OCR trong danh sách (v3.3.0):** mỗi phần tử của `GET /dossiers` có thêm hai trường, để màn danh sách không phải gọi `GET /dossiers/{id}/documents` và `GET /documents/{id}/pages` cho từng dòng:
  ```json
  {
    "document_counts": { "contracts": 1, "annexes": 2 },
    "contract_ocr": {
      "document_id": "doc_…",
      "filename": "hop-dong.pdf",
      "page_count": 4,
      "failed_pages": 1,
      "first_error": "SKIPPED: OpenAI vision unavailable"
    }
  }
  ```
  - `document_counts`: số tài liệu vai trò `CONTRACT` và `ANNEX` của hồ sơ (`0` khi chưa có tài liệu).
  - `contract_ocr`: tình trạng OCR của **hợp đồng đầu tiên** (theo `order_index`, rồi thời điểm tạo); hồ sơ không có hợp đồng thì lấy tài liệu đầu tiên. Đây là tài liệu màn danh sách vẫn kiểm.
    - `filename`: tên file lúc upload; có thể là `null` khi tài liệu không lưu tên file.
    - `page_count`: số trang **đã có kết quả OCR** (số bản ghi trang AI1 đã trả), không phải số trang của file PDF. OCR chưa chạy xong thì nhỏ hơn số trang thật, có thể là `0`.
    - `failed_pages`: số trang trong đó có `ai1_page_status` là `FAILED` hoặc có lỗi.
    - `first_error`: lỗi của trang lỗi đầu tiên theo số trang, tối đa 500 ký tự; `null` khi không có trang lỗi, hoặc khi trang lỗi đầu tiên không kèm thông báo lỗi (giống cách màn danh sách vẫn đọc từ `/pages`).
  - **Khi nào là `null`:**
    - Mỗi trường theo quyền của endpoint mà nó thay thế:
      - `document_counts` là `null` khi người gọi không có quyền `CITATION_READ`, như `GET /dossiers/{id}/documents` trả `403`.
      - `contract_ocr` là `null` khi người gọi không có quyền `QUERY`, như `GET /documents/{id}/pages` trả `403`. Lượt chia sẻ có thể chỉ cho một số `actions`, nên người được chia sẻ có thể thấy số tài liệu mà không thấy `contract_ocr`.
      - Frontend phải xử lý `null`: khi đó không hiện phần tương ứng (gọi `/documents` hay `/pages` cũng sẽ bị `403`).
    - `contract_ocr` là `null` (còn `document_counts` là `{0, 0}`) khi hồ sơ chưa có tài liệu nào.
    - Backend cũ (trước v3.3.0) không gửi hai trường này: frontend coi thiếu trường như `null` và gọi theo cách cũ.

- **Request Upload Document (`multipart/form-data`):**
  - `file`: Binary file PDF
  - `role`: `"CONTRACT"` hoặc `"ANNEX"`
  - `order_index`: `0` (số thứ tự)

- **Giới hạn dung lượng (v2.0.1):** mỗi file tối đa 50 MiB (backend trả `413` JSON); tối đa 6 tài liệu (`422 DOSSIER_TOO_MANY_DOCUMENTS`); trên bản online, **mỗi request tối đa 100 MB** vì Cloudflare gói Free. Quá mức này Cloudflare trả `413` với body HTML, không phải envelope `{ error }` (xem §3.3). Bộ hồ sơ lớn hơn 100 MB phải bớt hoặc nén file; tải từng phụ lục qua `POST /dossiers/{id}/documents` cũng tránh được giới hạn.

- **Tải hồ sơ theo khúc (v4.2.0, #145):** trên bản online, Cloudflare gói Free **cắt request còn đang gửi body sau khoảng 125 giây** (đo 19/10/2026; Caddy ghi `502` vì body không tới đủ). Với mạng 35–87 KB/s đo được trên production, `POST /dossiers` chỉ gửi kịp 4–10 MB. Hồ sơ lớn hơn gửi theo khúc, mỗi khúc một request ngắn:
  1. `POST /uploads` (JSON) → `201`:
     ```json
     {
       "metadata": { "name": "Hồ sơ A", "code": "HD-01", "split_pending": false },
       "files": [
         { "role": "contract", "filename": "hop-dong.pdf", "size": 15891385 },
         { "role": "annex", "filename": "phu-luc-1.pdf", "size": 2138220 }
       ]
     }
     ```
     - `metadata` giống trường `metadata` của `POST /dossiers` (JSON object, không phải chuỗi).
     - `files`: đúng **một** `contract`; tối đa 6 file. `size` là số byte của file **đúng như sẽ gửi** (sau khi ảnh đã gói thành PDF).
     - Kiểm ngay khi mở phiên, trước khi gửi byte nào: quá 6 file → `422 DOSSIER_TOO_MANY_DOCUMENTS`; không đúng một hợp đồng hoặc `metadata` sai → `422`; một file quá 50 MiB → `413`; người dùng đang có 3 phiên chưa xong → `429`.
     - Trả về `upload_id`, `chunk_size` (mặc định 1 MiB), `expires_at` (24 giờ), và `files[]` theo thứ tự hợp đồng trước (`index` 0), phụ lục sau, mỗi file có `chunks` (số khúc) và `received` (các khúc đã nhận, lúc đầu rỗng).
  2. Với mỗi file `index`, mỗi khúc `n` từ `0` tới `chunks - 1`: `PUT /uploads/{upload_id}/files/{index}/chunks/{n}`, body là byte thô (`Content-Type: application/octet-stream`) của đoạn `[n × chunk_size, (n + 1) × chunk_size)`. → `204`.
     - Mọi khúc dài đúng `chunk_size`, trừ khúc cuối (phần còn lại). Sai độ dài → `422`. `index` hoặc `n` ngoài phạm vi → `404`.
     - **Gửi lại cùng một khúc thì ghi đè**, nên khúc lỗi mạng cứ gửi lại. Thứ tự gửi không quan trọng.
     - Ở 35 KB/s, một khúc 1 MiB mất khoảng 30 giây, xa mốc 125 giây.
  3. `POST /uploads/{upload_id}/complete` → `202` với **đúng** `{dossier_id, job_id}` như `POST /dossiers`. Backend ghép các khúc rồi chạy cùng luồng tạo hồ sơ (kiểm PDF, số trang, `split_pending`, tự xác nhận vai trò, gửi OCR).
     - Thiếu khúc → `409`, `detail.missing_chunks` là `{ "<index>": [n, …] }`. Gửi các khúc đó rồi gọi lại.
     - File không phải PDF đọc được → `422` (như `POST /dossiers`). Phiên **vẫn mở**: có thể huỷ và tải file khác.
     - **Gọi lại sau khi đã thành công trả cùng hồ sơ**, nên mất response lần đầu thì cứ gọi lại, không tạo hồ sơ thứ hai. Hai lần gọi cùng lúc: một lần tạo hồ sơ, lần kia nhận `409` (gọi lại sau vài giây sẽ nhận hồ sơ).
  - `GET /uploads/{upload_id}` trả lại trạng thái như bước 1 (`status`: `open`, `completing`, `completed` kèm `dossier_id`, hoặc `cancelled`). Mất mạng hoặc tải lại trang thì đọc `received` và chỉ gửi khúc còn thiếu.
  - `DELETE /uploads/{upload_id}` → `204` (huỷ hai lần không lỗi); phiên đã thành hồ sơ → `409`, xoá hồ sơ bằng `DELETE /dossiers/{id}`.
  - Phiên chỉ của người mở: người khác (kể cả cùng tenant) nhận `404`. Quá `expires_at` mà chưa `complete` → `410`, backend xoá phiên và các khúc.
  - `POST /dossiers` **không đổi**. Frontend có thể giữ nó cho hồ sơ nhỏ (ví dụ tổng dưới 4 MB) và dùng `/uploads` cho hồ sơ lớn hơn. Giới hạn 100 MB mỗi request của Cloudflare không còn áp lên cả bộ hồ sơ khi gửi theo khúc; giới hạn 50 MiB mỗi file và 6 file vẫn giữ.

- **Tách file trộn (v1.1.0):**
  1. `POST /dossiers` với `metadata.split_pending = true`: Backend lưu file nhưng **chưa gửi OCR**.
  2. `POST /dossiers/{id}/split` → `202`:
     ```json
     {
       "document_id": "doc_…",
       "parts": [
         { "page_start": 1, "page_end": 6, "role": "contract" },
         { "page_start": 7, "page_end": 10, "role": "annex" }
       ]
     }
     ```
     Response `202`, bọc trong `{ data, meta }` như mọi endpoint của backend:
     ```json
     {
       "data": {
         "dossier_id": "dos_…",
         "status": "queued",
         "documents": [
           { "id": "doc_…", "role": "contract", "filename": "hop-dong-p1-6.pdf", "page_start": 1, "page_end": 6, "page_count": 6 },
           { "id": "doc_…", "role": "annex", "filename": "hop-dong-p7-10.pdf", "page_start": 7, "page_end": 10, "page_count": 4 }
         ]
       },
       "meta": { "trace_id": null, "request_id": null, "page": null, "page_size": null, "total": null }
     }
     ```
     Mỗi phần thành một tài liệu riêng, rồi đi OCR riêng. Một phần phủ cả file nghĩa là không tách.
  - Lỗi: `422` khi các phần không phủ đủ trang 1..N theo thứ tự, `page_end < page_start`, không có đúng một hợp đồng (`contract_required`, `contract_not_unique`, v1.2.0), hoặc sau khi tách hồ sơ quá 6 tài liệu (`DOSSIER_TOO_MANY_DOCUMENTS`, v1.2.0); `409` khi hồ sơ không tải lên với `split_pending` hoặc đã bắt đầu xử lý; `403` khi không có quyền sửa hồ sơ.
  - Hiện người dùng tự nhập khoảng trang. Khi AI1 đề xuất được chỗ cắt, đề xuất điền sẵn `parts`; API giữ nguyên.

---

### Màn hình 4: Pipeline Run & Realtime Processing Monitor
Theo dõi hành trình chạy của Pipeline AI qua 11 bước (S0..S10), xem log sự kiện, thông số hiệu năng và kích hoạt replay.

| Phương thức | Endpoint | Phân quyền `x-rbac` | Chức năng |
|:---:|---|:---:|---|
| `POST` | `/dossiers/{id}/runs` | `OPERATOR`, `ADMINISTRATOR` | Kích hoạt lần chạy phân tích mới (Pipeline Run) |
| `GET` | `/runs` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | Danh sách các lần chạy trong tenant |
| `GET` | `/runs/{id}` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | Trạng thái run, git sha, cấu hình snapshot, thời gian hoàn thành |
| `GET` | `/runs/{id}/steps` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | Chi tiết tiến độ 11 bước (S0..S10) kèm số trang, thời gian ms và **v3.2.0** tiến độ trong bước (`progress`) |
| `POST` | `/runs/{id}/cancel` | `OPERATOR`, `ADMINISTRATOR` | Hủy run đang trong trạng thái `running` |
| `POST` | `/dossiers/{id}/ocr/retry-failed` | `OPERATOR`, `ADMINISTRATOR` | **v1.1.0.** Hồ sơ lỗi ở bước OCR: mở run mới, giữ kết quả OCR đã có, chỉ OCR lại tài liệu còn thiếu |
| `POST` | `/dossiers/{id}/ai2/reindex` | `OPERATOR`, `ADMINISTRATOR` | **v1.4.0.** Hồ sơ đã phân tích xong: gửi lại kết quả OCR đã lưu cho AI2 dựng lại dữ liệu hỏi đáp. Không OCR lại |
| `GET` | `/dossiers/{id}/ai2/contract-graph/{graph_kind}` | quyền đọc trích dẫn (`CITATION_READ`) | **v2.1.0.** Trang các cạnh đồ thị hợp đồng AI2. `graph_kind` là `operation` hoặc `pair`. Query bắt buộc `job_id`, `snapshot_digest`; tuỳ chọn `cursor` (≤ 2048 ký tự), `limit` (1–100, mặc định 50). Trả `status`, `edges[]`, `total_count`, `has_more`, `next_cursor` |
| `GET` | `/dossiers/{id}/ai2/contract-graph/{graph_kind}/evidence` | `CITATION_READ` | **v2.1.0.** Bằng chứng (trích dẫn) cho một nút của đồ thị. Query bắt buộc `job_id`, `snapshot_digest`, `node_id`, `citation_ref` |
| `GET` | `/dossiers/{id}/ai2/processing-trace` | `CITATION_READ` | **v2.1.0.** Vết xử lý của AI2 cho một lần chạy. Query bắt buộc `job_id`, `snapshot_digest`. Trả `{job_id, ...trace}` |
| `PATCH` | `/dossiers/{id}/ai2-content-sharing-consent` | chủ hồ sơ hoặc `ADMINISTRATOR` (`DOSSIER_MANAGE`) | **v2.1.0.** Bật/tắt việc gửi nội dung hồ sơ ra LLM bên ngoài. Body `{"enabled": true\|false}` (`StrictBool`, chuỗi `"true"` bị `422`). Trả `{dossier_id, enabled, effective_from: "next_request", ai2_reindex_queued}`. Có audit `ai2.content_sharing_consent_changed`. **v3.1.0:** bật consent (từ chưa bật sang `true`) khi lượt chạy cuối đã qua AI2 (`pending_review`/`reviewed`/`approved`) thì backend tự cho AI2 dựng lại hồ sơ, như `POST /dossiers/{id}/ai2/reindex`; `ai2_reindex_queued: true` |

- **Tiến độ trong bước (v3.2.0):** mỗi phần tử của `GET /runs/{id}/steps` và payload SSE `step.changed` (`GET /runs/{id}/events`) có thêm `progress`:
  ```json
  { "step": "S2", "status": "running", "attempt": 1, "pages": null, "duration_ms": null,
    "progress": { "done": 37, "total": 202, "unit": "page" } }
  ```
  - `unit`: `page` (trang), `document` (tài liệu), `chunk` (đoạn), `clause` (điều khoản), `pair` (cặp). Frontend ghi "37/202 trang" theo `unit`; giá trị lạ thì hiện như `null`.
  - `progress: null` khi bước không đo được tiến độ: frontend hiện vòng quay. Luôn có `0 <= done <= total`, `total >= 1`.
  - Bước `succeeded` có `done = total`. Bước quay lại `queued` (chạy lại) có `progress: null`. `done` không giảm trong một lần chạy của bước.
  - Trong lúc bước `running`, backend phát lại `step.changed` khi `progress` đổi đủ nhiều: không quá 1 lần mỗi giây, và chỉ khi `done` đã tăng: tăng ít nhất 5% (tối đa khoảng 20 lần), hoặc tăng bất kỳ sau 15 giây kể từ lần trước (bước chậm). Bước đứng yên (`done` không đổi) thì không có sự kiện mới. Frontend không cần tự giới hạn.
  - Nguồn số liệu hiện có:

    | Bước | `unit` | Nguồn | Có từ |
    |---|---|---|---|
    | S2 | `page` (`document` khi một tài liệu chưa biết số trang) | Số trang đã OCR trên tổng số trang cả hồ sơ. Từng tài liệu xong cộng đủ số trang của nó; giữa chừng cần AI1 gửi `ai1.ocr.progress` (DOC-05d) | Ngay (theo tài liệu); theo trang khi AI1 gửi `ai1.ocr.progress` |
    | S3, S8 | như S2 | Đánh dấu khi AI1 xong cả hồ sơ, nên chỉ thấy `done = total` | Ngay |
    | S4–S7, S9, S10 | `chunk`, `clause`, `pair`… | Trường `progress` trong `GET /jobs/{id}` của AI2 (`contracts/BE-AI2-PROCESSING-CONTRACT.vi.md` §3). AI2 báo bước nào thì các bước AI2 trước nó thành `succeeded`, bước đó `running` | Khi AI2 gửi `progress`; trước đó `null` |
    | S0, S1 | — | Không đo | `null` |

  Ghi chú: tên bước S4 trên frontend ("Nhận diện chữ, bố cục, bảng") chưa khớp backend. Backend dùng S4 cho bước AI2 bắt đầu xử lý; OCR, bố cục và bảng nằm trong S2 của AI1.
- **Không đọc được trang nào (v3.2.0):** khi mọi trang của một tài liệu bị AI1 trả trạng thái khác `SUCCESS`/`PARTIAL` (ví dụ `FAILED` với lỗi `SKIPPED: OpenAI vision unavailable` khi thiếu khoá vision), job thành `failed` với `error_code: "AI1_NO_READABLE_PAGE"`, `error_detail` nêu số trang và lỗi của trang đầu; S2, S3, S8 thành `failed`, hồ sơ không được gửi sang AI2. Trước đây các bước này `succeeded` và AI2 nhận một hồ sơ rỗng. Chạy lại bằng `POST /dossiers/{id}/ocr/retry-failed` sau khi sửa cấu hình AI1.
- **Chạy lại OCR lỗi (v1.1.0):** response `202`:
  ```json
  { "data": { "dossier_id": "dos_…", "status": "queued" }, "meta": { "trace_id": null, "request_id": null, "page": null, "page_size": null, "total": null } }
  ```
  Nếu mọi tài liệu đã có kết quả thì run sang thẳng AI2, không OCR lại trang nào. Theo dõi bằng SSE của run mới. `409` khi job không lỗi ở bước OCR (lỗi AI2 thì dùng `POST /dossiers/{id}/ai2/retry`); `403` khi không có quyền sửa hồ sơ.
- **Dựng lại dữ liệu AI2 (v1.4.0):** dùng khi hỏi đáp báo AI2 chưa nhận snapshot (`AI2_QUERY_SNAPSHOT_NOT_FOUND`) dù hồ sơ đã phân tích xong, ví dụ sau khi AI2 mất dữ liệu. Response `202` giống trên. Worker gửi lại các snapshot AI1 đã lưu trên run hiện tại cho AI2, dưới lượt (`attempt`) kế tiếp:
  - **Không OCR lại**, AI1 không nhận lệnh nào.
  - Facts, xung đột, thẩm định và trạng thái job **giữ nguyên**; chỉ cập nhật `ai2_snapshot_digest` mà hỏi đáp dùng.
  - Lỗi AI2 không làm hỏng hồ sơ; audit ghi `ai2.reindex_failed`, thành công ghi `ai2.reindexed`.
  - API chỉ xét trạng thái job. Hồ sơ không có kết quả AI2 hoặc manifest chưa xác nhận (hồ sơ xử lý trước khi có tích hợp AI2) vẫn nhận `202`, nhưng worker không gửi gì cho AI2 và audit ghi `ai2.reindex_refused` kèm `reason` (`job_status`, `no_ai2_result`, `manifest`, `snapshots`).
  - `409` khi job chưa ở `pending_review` / `reviewed` / `approved`; `403` khi không có quyền sửa hồ sơ.

---

### Màn hình 5: PDF Document Explorer & Clause Tree Viewer
Giao diện xem văn bản trực quan chia đôi màn hình: Bên trái là cây cấu trúc Điều khoản (Điều → Khoản → Điểm), Bên phải là PDF Viewer hiển thị tài liệu gốc kèm bảng biểu và highlight.

| Phương thức | Endpoint | Phân quyền `x-rbac` | Chức năng |
|:---:|---|:---:|---|
| `GET` | `/documents/{id}` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | Lấy chi tiết thông tin file, tổng số trang, ngôn ngữ |
| `GET` | `/documents/{id}/content` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | Tải về hoặc stream nhị phân file PDF gốc (`application/pdf`). **v2.0.2:** tải theo khoảng byte (`Range` → `206`), dùng lại bản đã tải (`If-None-Match` → `304`); xem mục "Tải PDF theo khoảng" bên dưới |
| `GET` | `/documents/{id}/pages` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | Danh sách trang, kích thước points và link ảnh thumbnail |
| `GET` | `/pages/{id}` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | Chi tiết trang kèm danh sách các dòng OCR (`ocr_line`) và Bbox |
| `GET` | `/documents/{id}/lines` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | **v1.5.0.** Dòng OCR của mọi trang trong một response: `[{ page_no, width_pt, height_pt, ocr_lines: [{ id, line_no, text, bbox, confidence }] }]`, theo thứ tự trang rồi dòng. Trang chưa có dòng trả `ocr_lines: []`. Không phân trang. Thay cho gọi `/pages/{id}` từng trang |
| `GET` | `/documents/{id}/clauses` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | Cây Điều khoản hoàn chỉnh dựng theo quan hệ cha-con (`parent_id`) |
| `GET` | `/documents/{id}/tables` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | Danh sách bảng phát hiện được, danh sách cell (`row`, `col`, `span`, text) |
| `GET` | `/dossiers/{id}/queries` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | **v1.1.0, đổi ở v2.0.0.** Lịch sử hỏi đáp **của chính người gọi** trên hồ sơ, mới nhất trước; còn sau khi server khởi động lại |

- **Tải PDF theo khoảng (v2.0.2):** `GET /documents/{id}/content` gửi file thẳng từ storage theo từng khúc, không chờ đọc hết file. Quyền xem hồ sơ được kiểm trước mọi trường hợp, kể cả `304`.

  | Request | Response |
  |---|---|
  | Không có `Range` | `200`, cả file. Header `Accept-Ranges: bytes`, `ETag: "<sha256>"`, `Cache-Control: private, no-cache`, `Content-Length` |
  | `Range: bytes=a-b`, `bytes=a-` hoặc `bytes=-n` (một khoảng) | `206`, đúng khoảng đó. `Content-Range: bytes a-b/<tổng>`, `Content-Length` = độ dài khoảng. Khoảng vượt cuối file được cắt về byte cuối |
  | Khoảng nằm ngoài file (`bytes=<≥ tổng>-`, `bytes=-0`) | `416`, không có body, `Content-Range: bytes */<tổng>` |
  | Nhiều khoảng (`bytes=0-1,5-6`) hoặc header sai | Bỏ qua `Range`, trả `200` cả file |
  | `If-Range` khác `ETag` hiện tại | Bỏ qua `Range`, trả `200` cả file |
  | `If-None-Match` khớp `ETag` (cả dạng `W/"…"` và `*`) | `304`, không có body, không đọc storage |

  - CORS cho trình duyệt đọc `Accept-Ranges`, `Content-Range`, `Content-Length`, `ETag` từ origin của frontend (`api.…` khác origin với trang).
  - Để hiện trang đầu mà không chờ tải cả file, pdf.js nên nhận URL thay cho bytes: `getDocument({ url, httpHeaders: { Authorization: 'Bearer …' } })`; pdf.js tự gửi `Range`. Cách cũ (`arrayBuffer()` rồi `getDocument({ data })`) vẫn chạy, response `200` không đổi.
  - `Cache-Control: private, no-cache`: Cloudflare không giữ file; trình duyệt giữ được nhưng phải hỏi lại server (có kiểm quyền) trước khi dùng.

- **Lịch sử hỏi đáp (v1.1.0, đổi ở v2.0.0):** `GET /dossiers/{id}/queries?limit=20&offset=0`. Chỉ trả câu hỏi **của người gọi**, kể cả khi người gọi là chủ hồ sơ hoặc `ADMINISTRATOR`: không ai xem được câu hỏi của người khác (Lead chốt 14/10/2026). `scope` chỉ còn nhận `mine` (mặc định); `scope=all` trả `422`. Cần quyền xem hồ sơ. Phân trang bằng `limit` và `offset`, **không** theo `page`/`page_size` của §3.1. Response bọc trong `{ data, meta }`; `meta.page` = `offset / limit + 1`:
  ```json
  {
    "data": [
      {
        "trace_id": "qtr_…",
        "endpoint": "ask",
        "actor_id": "usr_…",
        "question": "Giá trị hợp đồng là bao nhiêu?",
        "answer": "1.286.400.000 đồng",
        "state": "PASS",
        "citations": [],
        "error_code": null,
        "created_at": "2026-10-01T09:12:00+00:00"
      }
    ],
    "meta": { "trace_id": null, "request_id": null, "page": 1, "page_size": 20, "total": 1 }
  }
  ```
  `endpoint` là `ask`, `query` hoặc `search` (thanh hỏi đáp, từ v1.5.1). Lần hỏi mà AI2 lỗi vẫn có trong lịch sử, với `answer: null` và `error_code`. Với `search`, `error_code` là `AI2_UNAVAILABLE` khi AI2 lỗi hoặc quá thời gian chờ. Câu hỏi gửi qua `search` trước v1.5.1 chỉ có trace, nên hiện với `answer: null` và `error_code: null`.

---

### Màn hình 6: Fact & Extraction Inspector
Kiểm tra các thực thể pháp lý quan trọng được AI trích xuất (Ngày ký, Ngày hiệu lực, Giá trị thanh toán, Các bên tham gia). Click vào Fact sẽ lập tức cuộn trang PDF và tô sáng đoạn văn bản trích dẫn (`citation`).

| Phương thức | Endpoint | Phân quyền `x-rbac` | Chức năng |
|:---:|---|:---:|---|
| `GET` | `/documents/{id}/facts` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | Danh sách fact có kiểu (`key`, `raw_text`, `normalized_value`) |
| `GET` | `/facts/{id}` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | Xem chi tiết một fact, extractor sử dụng, điểm tin cậy `confidence` |
| `GET` | `/citations/{id}` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | Lấy bằng chứng trích dẫn: nguyên văn `quote` và mảng tọa độ `segments` |

---

### Màn hình 7: Conflict Resolution & Review Workbench
Giao diện thẩm định chính của Chuyên viên Pháp lý (Reviewer): Đối chiếu song song Hợp đồng chính (Side A) và Phụ lục (Side B), hiển thị cảnh báo mâu thuẫn (`finding`), hàng đợi công việc (`review_item`), và submit chỉnh sửa với cơ chế khóa lạc quan chống ghi đè (`base_version`).

| Phương thức | Endpoint | Phân quyền `x-rbac` | Chức năng |
|:---:|---|:---:|---|
| `GET` | `/dossiers/{id}/findings` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | Danh sách phát hiện xung đột / điều chỉnh giữa hợp đồng & phụ lục |
| `GET` | `/findings/{id}` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | Chi tiết finding, mức độ nghiêm trọng `severity`, 2 phía đối sánh |
| `GET` | `/dossiers/{id}/review-items` | `REVIEWER`, `ADMINISTRATOR` | Hàng đợi các mục cần chuyên viên xử lý theo thứ tự ưu tiên `P1 > P2 > P3` |
| `GET` | `/review-items/{id}` | `REVIEWER`, `ADMINISTRATOR` | Chi tiết item cần duyệt kèm version hiện tại (`version`) |
| `GET` | `/review-items/{id}/revisions` | `REVIEWER`, `ADMINISTRATOR` | Toàn bộ lịch sử thao tác của các reviewer trước đó (Audit trail bất biến) |
| `POST` | `/review-items/{id}/actions` | `REVIEWER`, `ADMINISTRATOR` | Ghi nhận hành động: `confirm`, `correct`, `reject`, `needs_more_evidence` |

- **Request Body Submit Review Action (Chống Ghi Đè):**
  ```json
  {
    "action": "correct",
    "base_version": 1,
    "corrected_value": {
      "value": 150000000,
      "currency": "VND"
    },
    "corrected_bbox": [
      {
        "page_no": 2,
        "bbox": [0.12, 0.45, 0.88, 0.48]
      }
    ],
    "comment": "Chuyên viên đính chính giá trị thực tế sau thuế VAT quy định tại Điều 3"
  }
  ```
- **Xử lý mã `409 Conflict`:** Nếu người khác đã submit trước (khiến version tăng lên 2), API trả về `409`. Frontend sẽ reload lại dữ liệu mới nhất và thông báo cho reviewer.

---

### Màn hình 8: Dossier Approval & External Grants
Khóa hồ sơ, ký duyệt chính thức nội bộ và phát hành quyền phê duyệt liên kết cho đối tác hoặc lãnh đạo bên ngoài.

| Phương thức | Endpoint | Phân quyền `x-rbac` | Chức năng |
|:---:|---|:---:|---|
| `POST` | `/dossiers/{id}/lock` | `REVIEWER`, `ADMINISTRATOR` | Khóa hồ sơ, không cho phép sửa đổi thêm |
| `POST` | `/dossiers/{id}/approve` | `ADMINISTRATOR` | Ký duyệt chính thức nội bộ, tạo snapshot checksum toàn bộ dữ liệu |
| `POST` | `/dossiers/{id}/external-approvals` | `ADMINISTRATOR` | Cấp phát token & gửi link phê duyệt cho đối tác bên ngoài |
| `GET` | `/dossiers/{id}/external-approvals` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | Tra cứu danh sách và trạng thái các liên kết phê duyệt đã cấp |
| `POST` | `/external-approvals/callback` | Webhook / Public | Tiếp nhận kết quả ký duyệt từ hệ thống ngoài (DocuSign, SAP, ERP) |

---

### Màn hình 9: Re-OCR Workbench
Xử lý các trang scan bị mờ, nghiêng, độ phân giải thấp. Chuyên viên có thể yêu cầu chạy lại OCR với profile xử lý ảnh chuyên sâu.

| Phương thức | Endpoint | Phân quyền `x-rbac` | Chức năng |
|:---:|---|:---:|---|
| `POST` | `/documents/{id}/re-ocr` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | Tạo yêu cầu chạy lại OCR cho các trang chỉ định |
| `GET` | `/documents/{id}/re-ocr-requests` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | Theo dõi tiến độ và trạng thái các yêu cầu Re-OCR |

- **Request Body Re-OCR:**
  ```json
  {
    "page_ids": ["pg_01J9X2A", "pg_01J9X2B"],
    "reason": "Văn bản scan bị bóng mờ và đứt nét ở điều khoản thanh toán",
    "options": {
      "deskew": true,
      "denoise": true,
      "enhance_dpi": 300,
      "engine": "terra_advanced"
    }
  }
  ```

---

### Màn hình 10: Optimization Studio (Admin)
Phân hệ dành riêng cho Quản trị viên (Administrator) và AI Engineer: Tạo chiến dịch tối ưu hóa prompt, quản lý biến thể siêu tham số, chạy thử nghiệm trên tập dữ liệu chuẩn (Golden set) và promote phiên bản tốt nhất lên production.

| Phương thức | Endpoint | Phân quyền `x-rbac` | Chức năng |
|:---:|---|:---:|---|
| `GET` | `/optimization/campaigns` | `ADMINISTRATOR` | Danh sách chiến dịch tối ưu hóa prompt |
| `POST` | `/optimization/campaigns` | `ADMINISTRATOR` | Tạo chiến dịch mới |
| `GET` | `/optimization/campaigns/{id}` | `ADMINISTRATOR` | Chi tiết chiến dịch và các metrics mục tiêu |
| `GET` | `/optimization/candidates` | `ADMINISTRATOR` | Danh sách các ứng viên prompt template |
| `POST` | `/optimization/candidates` | `ADMINISTRATOR` | Đăng ký biến thể prompt / siêu tham số mới |
| `POST` | `/optimization/candidates/{id}/promote` | `ADMINISTRATOR` | Nâng cấp ứng viên này thành Prompt chính thức của hệ thống |
| `GET` | `/optimization/experiments` | `ADMINISTRATOR` | Danh sách các bài test thử nghiệm |
| `POST` | `/optimization/experiments` | `ADMINISTRATOR` | Tạo bài test thử nghiệm trên tập dữ liệu benchmark |
| `POST` | `/optimization/experiments/{id}/run` | `ADMINISTRATOR` | Kích hoạt chạy thực nghiệm |
| `GET` | `/optimization/experiments/{id}/results` | `ADMINISTRATOR` | Báo cáo so sánh điểm F1, độ chính xác, độ trễ và chi phí |

---

### Đồ thị hợp đồng, vết xử lý và consent AI2 (v2.1.0)

Ba `GET` đọc kết quả AI2 qua Backend; frontend không gọi AI2 trực tiếp.

- **Điều kiện chung.** `snapshot_digest` phải bằng `ai2_snapshot_digest` hiện tại của hồ sơ, nếu không trả `409 AI2_SNAPSHOT_CHANGED`. Backend kiểm lại quyền đọc sau khi AI2 trả dữ liệu; quyền bị thu hồi giữa chừng thì `403 CITATION_READ_REVOKED`. Các trường định danh nội bộ (`tenant_id`, `dossier_id`, `job_id`, `snapshot_digest`) bị bỏ khỏi từng cạnh.
- **Phân trang.** `next_cursor` là con trỏ ký HMAC, gắn với tenant, hồ sơ, `job_id`, `snapshot_digest` và `graph_kind`. Con trỏ sai chữ ký hoặc quá dài: `400 GRAPH_CURSOR_INVALID`; con trỏ của hồ sơ, lần chạy hoặc snapshot khác: `409 GRAPH_CURSOR_STALE`. Client gửi lại nguyên văn, không tự dựng.
- **Quan hệ do đồ thị sinh ra mặc định ở trạng thái chờ rà soát** (`AI2_CONTRACT_GRAPH_AUTO_PASS=false`); UI không được hiển thị như đã duyệt.
- **Lỗi riêng:**

| Mã | HTTP | Khi nào |
|---|---|---|
| `AI2_SNAPSHOT_CHANGED` | 409 | `snapshot_digest` không còn là của hồ sơ |
| `AI2_GRAPH_STALE` | 409 | AI2 báo đồ thị cũ so với snapshot (`status=STALE`) |
| `GRAPH_CURSOR_INVALID` | 400 | Con trỏ hỏng, sai chữ ký hoặc quá dài |
| `GRAPH_CURSOR_STALE` | 409 | Con trỏ thuộc hồ sơ, lần chạy hoặc snapshot khác |
| `CITATION_READ_REVOKED` | 403 | Quyền đọc bị thu hồi trong lúc xử lý |
| `AI2_GRAPH_UNAVAILABLE` | 503 | AI2 không trả được trang đồ thị |
| `AI2_GRAPH_EVIDENCE_UNAVAILABLE` | 503 | AI2 không trả được bằng chứng |
| `AI2_TRACE_UNAVAILABLE` | 503 | AI2 không trả được vết xử lý |
| `AI2_GRAPH_CURSOR_UNAVAILABLE` | 503 | Backend thiếu khoá ký con trỏ (`AI2_SERVICE_HMAC_SECRET`) |

- **Consent (`PATCH .../ai2-content-sharing-consent`).** Giá trị nằm ở `metadata.ai2_content_sharing_consent` của hồ sơ; frontend đọc `detail.metadata.ai2_content_sharing_consent === true`. Hồ sơ mới nhận mặc định của server (bản online: bật), có audit `ai2.content_sharing_consent_default_applied`. `PATCH /dossiers/{id}` thường **bỏ qua** khoá này, nên người chỉ có quyền sửa không tự bật được. Tắt consent thì lần xử lý và lần hỏi kế tiếp không gọi LLM ngoài (xem DEC-BE-AI2-01 D6). **Bật consent (v3.1.0)**: nếu lượt chạy cuối của hồ sơ đã qua AI2, backend gửi lại kết quả OCR đã lưu cho AI2 dựng lại (không OCR lại), có audit `ai2.reindex_on_consent`, và trả `ai2_reindex_queued: true`; kết quả mới (ví dụ đồ thị quan hệ điều khoản không còn `RULE_ONLY_NO_CONSENT`) có sau khi lượt đó xong, nên frontend nên báo "Đang chạy lại AI2" và tải lại khi run xong. `false` khi hồ sơ chưa qua AI2 (lượt đầu sẽ dùng consent mới), khi tắt consent, khi consent đã bật sẵn, hoặc khi không gửi được sự kiện (consent vẫn được lưu; dùng `POST /dossiers/{id}/ai2/reindex`). Lỗi: `404` (không có hồ sơ hoặc đã xoá), `403` (không đủ `DOSSIER_MANAGE`), `422` (body không phải boolean thật).

### Chia sẻ hồ sơ & hàng chờ thẩm định (v1.7.0)

Backend đã có cả hai endpoint và các trường dưới đây. Response bọc trong `{ data, meta }`, phân trang bằng `limit` (1–100, mặc định 20) và `offset`; `meta.total` là tổng số dòng.

| Phương thức | Endpoint | Phân quyền `x-rbac` | Chức năng |
|:---:|---|:---:|---|
| `GET` | `/users/directory?q=&role=&limit=20&offset=0` | `OPERATOR`, `ADMINISTRATOR` | Danh bạ thành viên cùng tenant để chọn người chia sẻ hồ sơ. `REVIEWER` nhận `403`. **v4.0.0:** OPERATOR phải gửi `q` từ 3 ký tự |
| `GET` | `/users/lookup?email=` | `OPERATOR`, `ADMINISTRATOR` | **v4.0.0.** Đúng một thành viên cùng tenant theo email chính xác, để chia sẻ bằng cách nhập email. `REVIEWER` nhận `403` |
| `PUT` | `/dossiers/{id}/access` | `OPERATOR`, `ADMINISTRATOR` (chủ hồ sơ hoặc `ADMINISTRATOR`) | Đặt phạm vi và người được chia sẻ. **v4.0.0:** backend kiểm tra người nhận mới trong Keycloak |
| `GET` | `/review-queue?limit=20&offset=0` | `REVIEWER`, `ADMINISTRATOR` | Hồ sơ còn mục review mở mà người gọi được thẩm định. `OPERATOR` nhận `403` |

**`GET /users/directory`**

```json
{
  "data": [
    { "id": "8f1c…", "email": "reviewer@ci.local", "display_name": "Demo Reviewer", "role": "REVIEWER" }
  ],
  "meta": { "trace_id": null, "request_id": null, "page": 1, "page_size": 20, "total": 1 }
}
```

- Mỗi người chỉ có đúng 4 trường trên. `id` là giá trị `id` của từng phần tử `shared_with` trong `PUT /dossiers/{id}/access`.
- `role=REVIEWER` để dựng ô "Giao cho người thẩm định". `q` tìm theo email hoặc tên hiển thị.
- Chỉ trả người đang `active` và có `tenant_id` trong Keycloak trùng tenant của người gọi. User không có `tenant_id`, người chưa đặt mật khẩu (`invited`) và người bị khoá (`disabled`) không có trong danh bạ. Điểm này khác `GET /users` của `ADMINISTRATOR`, nơi user không có `tenant_id` vẫn hiện.
- **v4.0.0:** OPERATOR phải gửi `q` có ít nhất 3 ký tự (sau khi bỏ khoảng trắng hai đầu), nếu không nhận `422 directory_query_required`. Như vậy người gọi API trực tiếp không lấy được cả danh sách tenant. `ADMINISTRATOR` vẫn gọi được khi để trống `q`.
- Keycloak không trả lời thì trả `503` với mã `keycloak_unavailable`.

**`GET /users/lookup?email=<email>`** (v4.0.0)

```json
{
  "data": { "id": "8f1c…", "email": "rita@lexis.vn", "display_name": "Rita", "role": "REVIEWER" },
  "meta": { "trace_id": null, "request_id": null, "page": null, "page_size": null, "total": null }
}
```

- Khớp **chính xác** email, không phân biệt hoa thường, bỏ khoảng trắng hai đầu. Không tìm gần đúng như `q` của danh bạ.
- Trả `200` khi có đúng một người `active` có `tenant_id` trùng tenant người gọi. Mọi trường hợp khác (khác tenant, bị khoá, chưa đặt mật khẩu, không tồn tại) đều trả `404` với mã `user_not_found` và cùng một câu, để API không cho biết email có trong hệ thống hay không.
- `email` bắt buộc, 3–320 ký tự. Thiếu thì trả `422` của FastAPI.
- Keycloak không trả lời thì trả `503` với mã `keycloak_unavailable`.

**`PUT /dossiers/{id}/access`** (kiểm tra người nhận từ v4.0.0)

```json
{
  "scope": "shared_out",
  "shared_with": [
    { "id": "8f1c…", "email": "rita@lexis.vn", "permission": "read", "expires_at": "2026-11-01T00:00:00+07:00" }
  ]
}
```

- Chỉ chủ hồ sơ hoặc `ADMINISTRATOR` cùng tenant; người khác nhận `403`. `scope`: `mine` (bỏ mọi chia sẻ), `shared_out`, `shared_in`. `permission`: `read` hoặc `edit` (mặc định `edit`). `expires_at` mới đặt hoặc vừa đổi phải ở tương lai, nếu không trả `422`.
- **Người nhận mới** là phần tử có `id` chưa có trong danh sách đang lưu. Backend tra Keycloak theo `id`, hoặc theo `email` (khớp chính xác) khi `id` rỗng. Người đó phải đang bật (`active`, hoặc `invited` chưa đặt mật khẩu) và có `tenant_id` trùng tenant người gọi. `id`, `email`, `display_name`, `status` được lấy từ Keycloak; giá trị trong body bị bỏ qua.
- Có người nhận mới không hợp lệ thì trả `422`, **không lưu gì và không gửi thư nào**:

  ```json
  {
    "error": {
      "code": "share_recipient_not_found",
      "message": "Không tìm thấy email này trong đơn vị của bạn, hoặc người này chưa kích hoạt tài khoản. Vui lòng kiểm tra lại.",
      "details": { "rejected_emails": ["ten-sai@lexis.vn"] }
    },
    "meta": { "trace_id": null, "request_id": null, "page": null, "page_size": null, "total": null }
  }
  ```

  `rejected_emails` là email gửi lên, hoặc `id` khi phần tử không có email.
- **Lượt chia sẻ cũ** gửi lại (cùng `id`) giữ nguyên `email`, `display_name`, `status` đang lưu, chỉ lấy `permission` và `expires_at` từ body, và không kiểm tra lại. Nhờ vậy chủ hồ sơ sửa người khác không bị chặn bởi một người đã bị khoá sau đó.
- Nhiều phần tử trỏ tới cùng một người thì chỉ lưu phần tử đầu, và backend chỉ tra Keycloak một lần cho mỗi `id` hoặc email. Response `shared_with` là danh sách đã lưu.
- `shared_with` tối đa 100 phần tử; nhiều hơn thì nhận `422` của FastAPI trước khi tra Keycloak.
- Keycloak không trả lời thì trả `503 keycloak_unavailable` và không lưu gì.
- Với `scope=shared_out`, người nhận mới nhận thư: thư đặt mật khẩu nếu còn `invited`, thư mở hồ sơ nếu không.

**Không gửi thư tới tên miền không nhận thư** (v4.0.0)

- Tên miền dành riêng `.local`, `.test`, `.example`, `.invalid`, `localhost`, `example.com`, `example.net`, `example.org` không có máy chủ nhận thư, nên thư gửi tới đó bị trả về hộp thư người gửi. Ba tài khoản demo trong `keycloak/realm-export.json` dùng `@ci.local`.
- Chia sẻ (`PUT /dossiers/{id}/access`): vẫn lưu lượt chia sẻ, chỉ không gửi thư; backend ghi log `email.skipped_undeliverable`.
- `POST /users` và `POST /users/{id}/invite`: trả `422 email_domain_undeliverable`, không tạo người dùng và không gửi thư.
- Backend chưa kiểm tra bản ghi MX, và không thể biết trước một hộp thư như `ten-sai@gmail.com` có tồn tại hay không: máy chủ thư chỉ báo sau khi đã gửi. Báo "thư mời không gửi được" cần đọc thư bị trả về hoặc webhook của nhà cung cấp email; phần này để sau.

**`GET /review-queue`**

```json
{
  "data": [
    {
      "dossier_id": "dos_…",
      "dossier_name": "Hợp đồng mua bán 2026",
      "dossier_status": "pending_review",
      "created_at": "2026-10-09T09:12:00+00:00",
      "is_owner": false,
      "grant_expires_at": "2026-10-20T00:00:00+00:00",
      "open_review_items": 5,
      "pending_conflicts": 2,
      "p1": 1,
      "p2": 3,
      "p3": 1
    }
  ],
  "meta": { "trace_id": null, "request_id": null, "page": 1, "page_size": 20, "total": 1 }
}
```

- Hồ sơ có trong danh sách khi còn mục `open` hoặc `awaiting_evidence` và người gọi là chủ hồ sơ hoặc được chia sẻ quyền `edit` còn hạn. `ADMINISTRATOR` cũng cần là chủ hoặc có chia sẻ.
- Sắp xếp: nhiều mục P1 hơn xếp trước, rồi tới hồ sơ tạo sớm hơn.
- `open_review_items` bằng `p1 + p2 + p3`; `pending_conflicts` là phần nằm trên finding.
- `grant_expires_at` là `null` với chủ hồ sơ hoặc lượt chia sẻ không có hạn.

**Trường mới trên hồ sơ** (từng phần tử của `GET /dossiers` và `GET /dossiers/{id}`):

```json
{
  "locked": false,
  "approved_at": null,
  "my_access": {
    "owner": false,
    "permission": "edit",
    "expires_at": "2026-10-20T00:00:00+00:00",
    "expired": false,
    "can_edit": false,
    "can_review": true,
    "can_see_review": true,
    "can_manage": false,
    "can_approve": false
  }
}
```

- Frontend dùng các cờ `can_*` để ẩn/hiện nút, không tự suy ra từ `metadata.shared_with`. Mỗi cờ là kết quả ACL của backend cho đúng người gọi; ví dụ trên là một `REVIEWER` được chia sẻ quyền `edit`.
- `permission` là `"edit"`, `"read"` hoặc `null`: lượt chia sẻ còn hạn lâu nhất dành cho người gọi (ưu tiên `edit`). Không còn lượt nào còn hạn thì là lượt hết hạn gần nhất, kèm `expired: true`. Chủ hồ sơ không cần chia sẻ nên `permission` là `null`.
- `my_access` chỉ trả lời theo ACL. Hồ sơ `locked: true` vẫn từ chối thay đổi và review dù `can_*` là `true`, nên frontend phải xét thêm `locked`.
- `approved_at` là `null` khi hồ sơ chưa được duyệt.

---

### Thông báo cá nhân (đề xuất, BE chưa có)

**v1.6.0, đề xuất.** Backend chưa có các endpoint này. Frontend đã có chuông thông báo (`NotificationBell`) gọi đúng 4 endpoint dưới đây, nhưng chuông chỉ hiện khi build với `VITE_ENABLE_NOTIFICATIONS=true`. Mặc định cờ tắt, nên không phát sinh request 404. Khi backend làm xong thì bật cờ, không cần sửa frontend.

Mỗi thông báo thuộc về đúng một người dùng (người nhận) trong tenant của họ. Người dùng chỉ đọc và đánh dấu thông báo của chính mình.

| Phương thức | Endpoint | Phân quyền `x-rbac` | Chức năng |
|:---:|---|:---:|---|
| `GET` | `/notifications?limit=10&offset=0` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | Thông báo của người gọi, mới nhất trước. Phân trang bằng `limit`/`offset`; `meta.total` là tổng số thông báo |
| `GET` | `/notifications/unread-count` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | `{ "data": { "count": 3 } }`. Frontend gọi mỗi 30 giây |
| `POST` | `/notifications/{id}/read` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | Đánh dấu một thông báo đã đọc. Thông báo của người khác trả `404` |
| `POST` | `/notifications/read-all` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | Đánh dấu mọi thông báo của người gọi là đã đọc |

Response của `GET /notifications` bọc trong `{ data, meta }`:

```json
{
  "data": [
    {
      "id": "ntf_…",
      "type": "analysis_succeeded",
      "title": "Phân tích xong hồ sơ",
      "detail": null,
      "dossier_id": "dos_…",
      "dossier_name": "Hợp đồng mua bán 2026",
      "actor_display_name": null,
      "created_at": "2026-10-09T09:12:00+00:00",
      "read_at": null
    }
  ],
  "meta": { "trace_id": null, "request_id": null, "page": 1, "page_size": 10, "total": 1 }
}
```

- `type` đề xuất: `analysis_succeeded`, `analysis_failed`, `dossier_approved`, `dossier_rejected`, `dossier_needs_more_evidence`, `dossier_shared`, `review_requested`. Frontend vẫn hiện được loại lạ, chỉ không có link tới hồ sơ.
- `read_at` là `null` khi chưa đọc. `dossier_id`, `dossier_name`, `detail`, `actor_display_name` có thể `null`.
- Hồ sơ bị xoá, hoặc người nhận mất quyền xem hồ sơ (§20 trong `frontend/API-BE.md`), thì không trả thông báo đó nữa, hoặc trả với `dossier_id: null`.

---

## 6. Bộ TypeScript Interfaces & DTOs Chuẩn

Đội ngũ Frontend có thể copy trực tiếp khối định nghĩa TypeScript dưới đây vào thư mục `src/types/api.ts`:

```typescript
/**
 * CONTRACT INTELLIGENCE — FRONTEND DATA CONTRACT
 * Phiên bản: v1.0.0 (SemVer)
 */

export type UserRole = 'OPERATOR' | 'REVIEWER' | 'ADMINISTRATOR';
export type DocumentRole = 'CONTRACT' | 'ANNEX';
export type JobStatus = 'uploaded' | 'processing' | 'extracted' | 'pending_review' | 'reviewed' | 'approved' | 'failed';
export type StepStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'retrying';
export type ReviewPriority = 'P1' | 'P2' | 'P3';
export type ReviewStatus = 'open' | 'resolved' | 'awaiting_evidence';
export type ReviewActionType = 'confirm' | 'correct' | 'reject' | 'needs_more_evidence';

export type BBox = [number, number, number, number]; // [x0, y0, x1, y1] CPS normalized 0..1

// Envelope phản hồi phân trang
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// User & Auth
export interface UserDTO {
  id: string;
  display_name: string;
  role: UserRole;
  tenant_id: string;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: 'Bearer';
  expires_in: number;
  user: UserDTO;
}

// Dossier
export interface DossierDTO {
  id: string;
  tenant_id: string;
  name: string;
  batch_id: string | null;
  has_conflicts: boolean;
  status?: JobStatus;
  total_documents?: number;
  created_at: string;
  updated_at: string;
  // v3.3.0, chỉ có trong GET /dossiers; null khi không có quyền xem tài liệu
  document_counts?: { contracts: number; annexes: number } | null;
  contract_ocr?: {
    document_id: string;
    filename: string | null;
    page_count: number; // số trang đã có kết quả OCR
    failed_pages: number;
    first_error: string | null;
  } | null;
}

// Document
export interface DocumentDTO {
  id: string;
  dossier_id: string;
  role: DocumentRole;
  order_index: number;
  filename: string;
  sha256: string;
  blob_uri: string;
  page_count: number;
  lang_detected: string;
  signing_date: string | null;
  effective_date: string | null;
  created_at: string;
}

// Manifest
export interface ManifestItemDTO {
  id: string;
  manifest_id: string;
  filename: string;
  doc_type: string;
  sha256?: string;
}

export interface ManifestDTO {
  id: string;
  tenant_id: string;
  dossier_id: string;
  status: 'DRAFT' | 'CONFIRMED';
  items: ManifestItemDTO[];
  confirmed_at: string | null;
  created_at: string;
}

// Pipeline Run & Steps
export interface JobStepDTO {
  id: number;
  run_id: string;
  document_id: string | null;
  step: string;
  status: StepStatus;
  attempt: number;
  pages?: number;
  duration_ms?: number;
  metrics?: Record<string, unknown>;
}

export interface PipelineRunDTO {
  id: string;
  tenant_id: string;
  job_id: string;
  dossier_id: string;
  status: 'running' | 'succeeded' | 'failed';
  pipeline_version: string;
  git_sha: string;
  trace_id?: string;
  created_at: string;
  finished_at?: string;
}

// Clause Tree
export interface ClauseNodeDTO {
  id: string;
  document_id: string;
  parent_id: string | null;
  node_type: string;
  label: string;
  number: string;
  title: string;
  text: string;
  page_start: number;
  page_end: number;
  confidence: number;
  children?: ClauseNodeDTO[];
}

// Citation & Fact
export interface CitationSegment {
  page_no: number;
  line_id: string;
  char_start: number;
  char_end: number;
  bbox: BBox;
}

export interface CitationDTO {
  id: string;
  document_id: string;
  quote: string;
  quote_sha256: string;
  segments: CitationSegment[];
}

export interface FactDTO {
  id: string;
  document_id: string;
  key: string;
  fact_type: string;
  raw_text: string;
  normalized_value: Record<string, unknown>;
  confidence: number;
  citation_id: string;
  citation?: CitationDTO;
}

// Conflict & Findings
export interface FindingSideDTO {
  finding_id: string;
  side: 'a' | 'b';
  document_id: string;
  fact_id?: string;
  clause_node_id?: string;
  citation_id: string;
  value_snapshot?: Record<string, unknown>;
  citation?: CitationDTO;
}

export interface FindingDTO {
  id: string;
  dossier_id: string;
  finding_type: 'structured' | 'semantic';
  scope: 'within_document' | 'contract_annex' | 'annex_annex';
  key_or_topic: string;
  disposition: string;
  severity: 'high' | 'medium' | 'low';
  confidence: number;
  rationale?: string;
  sides: FindingSideDTO[];
  review?: FindingReviewDTO | null;
}

export interface FindingReviewDTO {
  item_id: string;
  status: string;
  current_version?: number;
  // v1.3.0: lượt thẩm định gần nhất; null khi chưa ai thẩm định.
  latest?: {
    action: string; // confirm | reject (dữ liệu cũ có thể là correct)
    comment?: string | null;
    reviewer_id?: string | null;
    reviewer_name?: string | null;
    reviewer_email?: string | null;
    reviewed_at?: string | null;
    action_count?: number;
  } | null;
}

// Review Queue & Actions
export interface ReviewItemDTO {
  id: string;
  dossier_id: string;
  target_type: 'fact' | 'finding' | 'annex_link' | 'clause_node' | 'table_cell' | 'citation';
  target_id: string;
  reason: string;
  priority: ReviewPriority;
  status: ReviewStatus;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface ReviewActionRequest {
  action: ReviewActionType;
  base_version: number;
  corrected_value?: Record<string, unknown>;
  corrected_bbox?: Array<{ page_no: number; bbox: BBox }>;
  comment?: string;
}

export interface ReviewRevisionDTO {
  id: string;
  review_item_id: string;
  action: ReviewActionType;
  base_version: number;
  corrected_value?: Record<string, unknown>;
  comment?: string;
  reviewer_id: string;
  created_at: string;
}

// Error Format (RFC 7807)
export interface ApiErrorProblemDetails {
  type: string;
  title: string;
  status: number;
  detail: string;
  instance?: string;
  code?: string;
  current_version?: number;
}
```

---

## 7. Chiến lược Polling & Thời gian thực (Realtime)

Khi người dùng upload hồ sơ hoặc kích hoạt Run phân tích hợp đồng:
1. **Chiến lược Polling khuyến nghị (Short-term):**
   - Áp dụng **Exponential Backoff Polling** khi một Run đang ở trạng thái `running`:
     - 5 giây đầu: Polling mỗi 1 giây một lần.
     - 30 giây tiếp theo: Polling mỗi 3 giây một lần.
     - Sau đó: Polling mỗi 5 giây một lần cho đến khi trạng thái chuyển sang `succeeded` hoặc `failed`.
2. **Chuẩn bị Server-Sent Events (SSE / Long-term):**
   - Backend đã thiết kế sẵn các kênh sự kiện theo `run_id` và `job_id`. Khi chuyển sang SSE, Frontend sẽ lắng nghe endpoint `GET /runs/{id}/events` để cập nhật trạng thái từng bước S0..S10 theo thời gian thực mà không cần gửi liên tục HTTP requests.

---

## 8. Quy trình Quản lý Thay đổi (Versioning & Change Management)

1. **Quy tắc Bất Biến API (No Breaking Changes without Notice):**
   - Không được đổi tên trường hoặc xóa trường đã có trong bản contract `v1.0.0`.
   - Các trường mới bổ sung bắt buộc phải là **Optional** (`nullable` hoặc có giá trị mặc định).
2. **Quy trình Đề Xuất Thay Đổi:**
   - Mọi đề xuất thêm endpoint hoặc thay đổi payload phải được cập nhật vào [DOC-05-api-spec.yaml](file:///e:/Project_OJT/contract-intelligence-core/docs/DOC-05-api-spec.yaml) trước, sau đó đồng bộ vào tài liệu contract này và nâng phiên bản theo chuẩn SemVer (`v1.1.0` cho tính năng mới, `v2.0.0` nếu có breaking change).

### Lịch sử phiên bản

| Phiên bản | Ngày | Thay đổi |
|---|---|---|
| `v1.0.0` | 17/09/2026 | Baseline |
| `v4.1.0` | 19/10/2026 | Đăng xuất có hiệu lực ngay (Màn hình 1). Keycloak báo phiên kết thúc qua back-channel logout (`POST /auth/backchannel-logout`, chỉ trong mạng nội bộ), backend lưu `sid` (bảng `revoked_session`, giữ 1 giờ) và trả `401` `Session has ended` cho mọi access token của phiên đó thay vì chờ hết hạn (15 phút). Quản trị khoá tài khoản cũng kết thúc mọi phiên của người đó. Thêm một `message` cho `401` và một endpoint nội bộ, frontend không phải sửa, nên là MINOR |
| `v4.2.0` | 19/10/2026 | Tải hồ sơ theo khúc (Màn hình 3, #145). Cloudflare gói Free cắt request còn đang gửi body sau khoảng 125 giây, nên trên mạng chậm `POST /dossiers` chỉ gửi kịp 4–10 MB. Thêm `POST /uploads`, `PUT /uploads/{id}/files/{index}/chunks/{n}`, `GET /uploads/{id}`, `POST /uploads/{id}/complete`, `DELETE /uploads/{id}`; khúc 1 MiB, gửi lại được, tiếp tục sau khi mất mạng; `complete` trả như `POST /dossiers` và gọi lại an toàn. `POST /dossiers` không đổi. Chỉ thêm endpoint nên là MINOR |
| `v4.0.0` | 18/10/2026 | Chia sẻ hồ sơ chỉ với người dùng có thật trong cùng tenant (mục "Chia sẻ hồ sơ & hàng chờ thẩm định" ở §5). `PUT /dossiers/{id}/access` (lần đầu ghi vào DOC-05b) kiểm tra mỗi người nhận mới trong Keycloak, trả `422 share_recipient_not_found` (`details.rejected_emails`) và không lưu, không gửi thư khi có người không hợp lệ; danh tính người nhận lấy từ Keycloak. Thêm `GET /users/lookup?email=`. `shared_with` tối đa 100 phần tử. Không gửi thư tới tên miền dành riêng (`.local`, `.test`...); `POST /users` và `POST /users/{id}/invite` trả `422 email_domain_undeliverable`. **Breaking** theo §8 vì thu hẹp hành vi đã công bố: `GET /users/directory` do OPERATOR gọi phải có `q` từ 3 ký tự (`422 directory_query_required`), và `PUT /access` từ chối người nhận trước đây được nhận. Frontend chia sẻ bằng email đã tra `q=<email>` nên không bị ảnh hưởng; nên chuyển sang `GET /users/lookup` |
| `v3.3.0` | 17/10/2026 | `GET /dossiers`: mỗi hồ sơ thêm `document_counts` (`{contracts, annexes}`) và `contract_ocr` (`{document_id, filename, page_count, failed_pages, first_error}`), `null` khi người gọi không có quyền tương ứng: `CITATION_READ` cho `document_counts`, `QUERY` cho `contract_ocr` (mục "Số tài liệu và trạng thái OCR trong danh sách" ở Màn hình 3). Màn danh sách bỏ được 3 lần gọi cho mỗi dòng. Header `Server-Timing` và `Timing-Allow-Origin` (§1.2), staging và production tắt mặc định. Chỉ thêm trường và header, nên là MINOR |
| `v3.2.0` | 16/10/2026 | Tiến độ trong bước: `progress` (`{done, total, unit}` hoặc `null`) trên mỗi phần tử `GET /runs/{id}/steps` và payload SSE `step.changed`, phát lại có giới hạn tần suất khi bước đang chạy (mục "Tiến độ trong bước" ở Màn hình 4). Mã lỗi job mới `AI1_NO_READABLE_PAGE`: AI1 không đọc được trang nào thì OCR thất bại thay vì `succeeded`. Chỉ thêm trường và mã lỗi, nên là MINOR |
| `v3.1.0` | 15/10/2026 | `PATCH /dossiers/{id}/ai2-content-sharing-consent`: bật consent khi lượt chạy cuối đã qua AI2 thì backend tự reindex AI2 (như `POST /dossiers/{id}/ai2/reindex`); response thêm `ai2_reindex_queued` (boolean). Trước đây bật consent chỉ lưu giá trị và kết quả cũ (`RULE_ONLY_NO_CONSENT`) vẫn hiển thị. Thêm trường và hành vi, không bỏ gì, nên là MINOR |
| `v3.0.0` | 15/10/2026 | Siết quyền trước đợt pentest bản online (#96). **Breaking** theo §8 vì thu hẹp quyền đã công bố: (1) token không có role ứng dụng nào trả `403 FORBIDDEN` thay vì được coi là `OPERATOR` (§2.1); (2) `GET`/`DELETE /ai/jobs/{id}` chỉ `ADMINISTRATOR`, trước đây `OPERATOR`/`REVIEWER` cũng gọi được; (3) `POST /batches/{id}/cancel` và `/resume`: OPERATOR chỉ với batch do mình tạo, batch của người khác trả `404`. Không đổi payload hay mã lỗi: `401` chỉ còn `message` `Token has expired`/`Invalid token`; `502 AI2_QUERY_FAILED` của `/query`, `/ask` không còn kèm URL và nội dung lỗi của AI2. Staging/prod không phục vụ `/docs`, `/redoc`, `/openapi.json` và không gửi `X-Backend-Version`; `/health` chỉ trả `{"status":"ok"}` ở **mọi** môi trường (dev/test cũng không còn phiên bản). Frontend không dùng các endpoint và header này nên không phải sửa |
| `v2.1.0` | 15/10/2026 | Thêm `GET /dossiers/{id}/ai2/contract-graph/{graph_kind}` (+ `/evidence`), `GET /dossiers/{id}/ai2/processing-trace` và `PATCH /dossiers/{id}/ai2-content-sharing-consent` (mục "Đồ thị hợp đồng, vết xử lý và consent AI2" ở §5), kèm các mã lỗi `AI2_SNAPSHOT_CHANGED`, `AI2_GRAPH_STALE`, `GRAPH_CURSOR_INVALID`, `GRAPH_CURSOR_STALE`, `CITATION_READ_REVOKED`, `AI2_GRAPH_UNAVAILABLE`, `AI2_GRAPH_EVIDENCE_UNAVAILABLE`, `AI2_TRACE_UNAVAILABLE`. `PATCH /dossiers/{id}` bỏ qua `metadata.ai2_content_sharing_consent`. Chỉ thêm endpoint và mã lỗi, nên là MINOR |
| `v2.0.2` | 15/10/2026 | `GET /documents/{id}/content` (mục "Tải PDF theo khoảng" ở Màn hình 5): stream từ storage thay vì đọc cả file vào bộ nhớ; nhận một khoảng `Range` → `206` + `Content-Range`, khoảng ngoài file → `416`; `If-Range`; `ETag` = sha256 và `If-None-Match` → `304`; `Cache-Control: private, no-cache`; CORS cho đọc `Accept-Ranges`, `Content-Range`, `Content-Length`, `ETag`. Response `200` không đổi, chỉ thêm mã và header, nên là PATCH |
| `v2.0.1` | 14/10/2026 | Ghi giới hạn dung lượng tải hồ sơ (mục "Giới hạn dung lượng" ở Màn hình 3 và hai dòng `413` ở §3.3): 50 MiB mỗi file, do backend trả JSON; 100 MB mỗi request trên bản online, do Cloudflare gói Free trả HTML. `POST /dossiers` gửi mọi file trong một request nên bộ hồ sơ trên 100 MB bị chặn. API không đổi, nên là PATCH |
| `v2.0.0` | 14/10/2026 | **Lead chốt bỏ** `scope=all` của `GET /dossiers/{id}/queries`: ai hỏi thì chỉ xem lịch sử của mình, kể cả chủ hồ sơ và `ADMINISTRATOR`. `scope` chỉ còn nhận `mine`; `scope=all` trả `422` (trước đây trả lịch sử của mọi người cho chủ hồ sơ/ADMINISTRATOR, `403` cho người khác). Frontend bỏ `'all'` khỏi `queries.ts` và cập nhật `API-BE.md`. Bỏ một giá trị đang dùng được, nên là MAJOR theo §8 |
| `v1.7.0` | 13/10/2026 | Thêm `GET /users/directory` (danh bạ thành viên cùng tenant để chia sẻ hồ sơ) và `GET /review-queue` (hồ sơ đang chờ người gọi thẩm định); hồ sơ có thêm `my_access`, `locked`, `approved_at` (mục "Chia sẻ hồ sơ & hàng chờ thẩm định" ở §5). Backend đã có. Header `X-API-Contract` lên thẳng `v1.7.0` từ `v1.5.1`: backend **chưa** làm 4 endpoint `/notifications` của `v1.6.0`, chúng vẫn là đề xuất. Chỉ thêm endpoint và trường tuỳ chọn, nên là MINOR |
| `v1.6.0` | 09/10/2026 | Đề xuất `GET /notifications`, `GET /notifications/unread-count`, `POST /notifications/{id}/read`, `POST /notifications/read-all` (mục "Thông báo cá nhân" ở §5). **BE chưa có**; frontend ẩn chuông bằng cờ `VITE_ENABLE_NOTIFICATIONS` cho tới khi có. Chỉ thêm endpoint, nên là MINOR |
| `v1.5.1` | 07/10/2026 | `GET /dossiers/{id}/queries` trả thêm câu hỏi gửi qua `POST /dossiers/{id}/search` (`endpoint: "search"`) và mã lỗi `AI2_UNAVAILABLE`. Endpoint và các trường giữ nguyên, nên là PATCH |
| `v1.5.0` | 04/10/2026 | Thêm `GET /documents/{id}/lines`. `POST /dossiers/{id}/ocr` trả `409` khi hồ sơ đang OCR (job `processing`) thay vì thay run đang chạy; chờ xong hoặc hủy run rồi chạy lại. Response JSON trên 1 KB được gzip khi client gửi `Accept-Encoding: gzip` (SSE, ảnh và PDF không nén). Chỉ thêm endpoint và mã lỗi, nên là MINOR |
| `v1.4.0` | 04/10/2026 | Thêm `POST /dossiers/{id}/ai2/reindex`: AI2 dựng lại dữ liệu hỏi đáp từ kết quả OCR đã lưu, không OCR lại. Chỉ thêm endpoint, nên là MINOR |
| `v1.3.0` | 02/10/2026 | Finding có thêm `review.latest` (`action`, `comment`, người thẩm định, `reviewed_at`, `action_count`), `null` khi chưa ai thẩm định. Trước đây Backend đã lấy giá trị này nhưng DTO làm rơi, nên FE không biết xung đột đã được đánh Đúng/Sai (liên quan #51). Chỉ thêm trường tuỳ chọn, nên là MINOR |
| `v1.2.0` | 30/09/2026 | Theo DEC-BE-AI2-01 D5 (việc B4): hồ sơ tối đa 6 tài liệu (đếm file và phần sau khi tách, không đếm trang), `422 DOSSIER_TOO_MANY_DOCUMENTS` ở `POST /dossiers` và `POST /dossiers/{id}/split`, câu lỗi riêng cho từng chỗ; hồ sơ cần đúng một hợp đồng, `422 contract_not_unique` (mới) cạnh `contract_required` ở `POST /dossiers/{id}/split` và `POST /dossiers/{id}/manifest/confirm`. Chỉ thêm mã lỗi; hồ sơ bị chặn là loại AI2 vốn không xử lý được, nên là MINOR |
| `v1.1.0` | 30/09/2026 | Thêm `GET /dossiers/{id}/queries`, `POST /dossiers/{id}/ocr/retry-failed`, `POST /dossiers/{id}/split` và `metadata.split_pending` (đã có trong `DOC-05-api-spec.yaml`, PR #36). Chỉ thêm, không đổi hay xoá trường nào, nên là MINOR. Response của ba API mô tả theo envelope thật `{ data, meta }` (xem ghi chú §3.1 bên dưới). Các endpoint backend bỏ ở v2.0.0 (`POST /dossiers/upload`, webhook AI1/AI2, `/reviews` cũ) chưa từng có trong DOC-05b, nên không ảnh hưởng contract này |

**§3.1 chưa khớp backend (đã biết):** backend trả mọi response, kể cả danh sách, trong `{ data, meta }`, với `meta` gồm `trace_id`, `request_id`, `page`, `page_size`, `total`. Envelope ở §3.1 (`items`, `total`, `page`, `page_size`, `total_pages`) không khớp endpoint danh sách nào. Ba API của v1.1.0 được mô tả theo `{ data, meta }`. Sửa §3.1 cho mọi endpoint là thay đổi contract chung, để ở bản sau khi frontend chốt.

**Chưa đồng bộ (đã biết):** backend còn các route có trong `DOC-05-api-spec.yaml` hoặc `frontend/API-BE.md` nhưng chưa có trong DOC-05b. Sẽ đồng bộ ở bản sau, mỗi nhóm một lần:

- Quản trị người dùng: `/users`, `/users/{id}`, `/users/{id}/disable|enable|invite`, `/admin/activity`, `/admin/storage`.
- Hồ sơ: `DELETE /dossiers/{id}`, `POST /dossiers/{id}/ocr`, `/reprocess`, `/ai2/retry`, `/dossiers/{id}/facts`, `/conflicts`.
- Hỏi đáp: `POST /dossiers/{id}/search`, `/ask`, `/query`.
- Review: `GET|POST /clause-nodes/{id}/review`, `GET|POST /findings/{id}/review`.
- Khác: `GET /runs/{id}/events` (SSE), `GET /documents/{id}/pages/{page_no}/image`, `GET /re-ocr-requests/{id}`, `/ai/jobs/{id}` (**v3.0.0:** `GET` và `DELETE` chỉ `ADMINISTRATOR`; huỷ lần xử lý của hồ sơ dùng `POST /runs/{run_id}/cancel`), `/readyz`.

---

**Hết DOC-05b · Frontend-Backend API Contract v3.3.0 (SemVer)**
