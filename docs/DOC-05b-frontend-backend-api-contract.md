# DOC-05b · FRONTEND-BACKEND API CONTRACT — Contract Intelligence

**Đặc tả Hợp đồng Giao tiếp Kỹ thuật Frontend ↔ Backend**

| Thuộc tính | Nội dung |
|---|---|
| Mã tài liệu | **DOC-05b** / Contract Intelligence (PROD-01) |
| Phiên bản / SemVer | **`v1.0.0`** — Official Contract Baseline |
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

---

## 2. Cơ chế Xác thực & Phân quyền (Auth & RBAC)

### 2.1 Luồng Xác thực Keycloak SSO

**Backend TUYỆT ĐỐI KHÔNG issue Access Token / Refresh Token.**

Frontend (React) xử lý toàn bộ auth flow với Keycloak:
```
Frontend                          Keycloak                  Backend
    │                                │                        │
    ├──► Login Page ──────────────►│ Login Credentials      │
    │◄── access_token (RS256) ◄────│                        │
    │◄── refresh_token ◄───────────│                        │
    │                                │                        │
    │   (Frontend lưu tokens trong Memory/Secure Cookie)     │
    │                                │                        │
    │   Khi access_token hết hạn:                              │
    ├──► Keycloak refresh URL ◄───────────────────────────────│
    │◄── access_token mới ◄─────────────────────────────────│
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
| *(không match)* | `OPERATOR` (fallback) |

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
| `401` | `UNAUTHORIZED` | Token hết hạn hoặc không hợp lệ | Điều hướng người dùng về màn hình Login hoặc gọi refresh token |
| `403` | `FORBIDDEN` | Sai `X-Tenant-Id` hoặc không đủ quyền `x-rbac` | Hiển thị thông báo "Không có quyền thực hiện chức năng này" |
| `404` | `NOT_FOUND` | Không tìm thấy ID hồ sơ / tài liệu / run | Hiển thị màn hình 404 hoặc thông báo mục đã bị xóa |
| `409` | `VERSION_CONFLICT` | Phiên bản `base_version` gửi lên cũ hơn DB | **Refetch item mới nhất**, cảnh báo reviewer có xung đột chỉnh sửa |
| `422` | `VALIDATION_ERROR` | Request body sai kiểu dữ liệu hoặc thiếu trường | Hiển thị lỗi tương ứng trên form input |
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
2. Keycloak trả `access_token` + `refresh_token` về frontend (OIDC callback).
3. Frontend lưu `access_token` trong Memory hoặc Secure Cookie.
4. Khi `access_token` hết hạn, frontend gọi Keycloak refresh endpoint trực tiếp.
5. Khi user click "Đăng xuất", frontend gọi Keycloak logout endpoint trực tiếp.

| Phương thức | Endpoint | Phân quyền | Chức năng |
|:---:|---|:---:|---|
| `GET` | `/auth/me` | Mọi role | Lấy thông tin user hiện tại (từ Keycloak JWT claims) |
| `POST` | `/auth/webhooks/keycloak` | Webhook (Keycloak) | Sync user từ Keycloak event vào local DB |

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
| `POST` | `/batches/{id}/cancel` | `OPERATOR`, `ADMINISTRATOR` | Dừng khẩn cấp toàn bộ tác vụ đang chạy trong batch |
| `POST` | `/batches/{id}/resume` | `OPERATOR`, `ADMINISTRATOR` | Tiếp tục chạy lại các hồ sơ bị tạm dừng / lỗi |
| `GET` | `/ops/metrics` | `ADMINISTRATOR` | Dashboard thống kê tải server, độ trễ và chi phí token theo ngày |

---

### Màn hình 3: Dossier Creation, Upload & Manifest Confirmation
Màn hình khởi tạo hồ sơ, tải lên các file PDF (hợp đồng gốc + các phụ lục) và kiểm tra xác nhận danh mục tài liệu dự kiến.

| Phương thức | Endpoint | Phân quyền `x-rbac` | Chức năng |
|:---:|---|:---:|---|
| `POST` | `/dossiers` | `OPERATOR`, `ADMINISTRATOR` | Tạo mới hồ sơ hợp đồng (Dossier) |
| `GET` | `/dossiers` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | Danh sách hồ sơ có lọc theo `status`, `has_conflicts` |
| `GET` | `/dossiers/{id}` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | Xem chi tiết hồ sơ |
| `PATCH` | `/dossiers/{id}` | `OPERATOR`, `ADMINISTRATOR` | Đổi tên hoặc cập nhật metadata của hồ sơ |
| `POST` | `/dossiers/{id}/documents` | `OPERATOR`, `ADMINISTRATOR` | Upload file PDF vào hồ sơ (`multipart/form-data`) |
| `GET` | `/dossiers/{id}/documents` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | Danh sách các file PDF kèm vai trò `CONTRACT` hoặc `ANNEX` |
| `GET` | `/dossiers/{id}/manifest` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | Xem Manifest dự thảo phân loại tài liệu sau bước tiền xử lý |
| `POST` | `/dossiers/{id}/manifest/confirm` | `OPERATOR`, `ADMINISTRATOR` | Xác nhận phân loại tài liệu để kích hoạt bước phân tích sâu |

- **Request Upload Document (`multipart/form-data`):**
  - `file`: Binary file PDF
  - `role`: `"CONTRACT"` hoặc `"ANNEX"`
  - `order_index`: `0` (số thứ tự)

---

### Màn hình 4: Pipeline Run & Realtime Processing Monitor
Theo dõi hành trình chạy của Pipeline AI qua 11 bước (S0..S10), xem log sự kiện, thông số hiệu năng và kích hoạt replay.

| Phương thức | Endpoint | Phân quyền `x-rbac` | Chức năng |
|:---:|---|:---:|---|
| `POST` | `/dossiers/{id}/runs` | `OPERATOR`, `ADMINISTRATOR` | Kích hoạt lần chạy phân tích mới (Pipeline Run) |
| `GET` | `/runs` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | Danh sách các lần chạy trong tenant |
| `GET` | `/runs/{id}` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | Trạng thái run, git sha, cấu hình snapshot, thời gian hoàn thành |
| `GET` | `/runs/{id}/steps` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | Chi tiết tiến độ 11 bước (S0..S10) kèm số trang và thời gian ms |
| `POST` | `/runs/{id}/cancel` | `OPERATOR`, `ADMINISTRATOR` | Hủy run đang trong trạng thái `running` |

---

### Màn hình 5: PDF Document Explorer & Clause Tree Viewer
Giao diện xem văn bản trực quan chia đôi màn hình: Bên trái là cây cấu trúc Điều khoản (Điều → Khoản → Điểm), Bên phải là PDF Viewer hiển thị tài liệu gốc kèm bảng biểu và highlight.

| Phương thức | Endpoint | Phân quyền `x-rbac` | Chức năng |
|:---:|---|:---:|---|
| `GET` | `/documents/{id}` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | Lấy chi tiết thông tin file, tổng số trang, ngôn ngữ |
| `GET` | `/documents/{id}/content` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | Tải về hoặc stream nhị phân file PDF gốc (`application/pdf`) |
| `GET` | `/documents/{id}/pages` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | Danh sách trang, kích thước points và link ảnh thumbnail |
| `GET` | `/pages/{id}` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | Chi tiết trang kèm danh sách các dòng OCR (`ocr_line`) và Bbox |
| `GET` | `/documents/{id}/clauses` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | Cây Điều khoản hoàn chỉnh dựng theo quan hệ cha-con (`parent_id`) |
| `GET` | `/documents/{id}/tables` | `OPERATOR`, `REVIEWER`, `ADMINISTRATOR` | Danh sách bảng phát hiện được, danh sách cell (`row`, `col`, `span`, text) |

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

---

**Hết DOC-05b · Frontend-Backend API Contract v1.0.0 (SemVer)**
