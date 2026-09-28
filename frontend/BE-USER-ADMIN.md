# Quản lý người dùng — việc backend và Keycloak cần làm

Frontend đã có màn `/nguoi-dung-phan-quyen` (`src/pages/UsersPage.tsx`) và đã gọi các API trong file này (`src/api/users.ts`). Backend chưa có các path này. Browser không gọi Keycloak Admin API và không giữ client secret.

Admin tạo user trong app. Backend tạo account trên Keycloak rồi bảo Keycloak gửi email đặt mật khẩu. User bấm link, đặt mật khẩu, sau đó đăng nhập SSO như hiện tại (email trên app chỉ là `login_hint`).

`OPERATOR` và `REVIEWER` dùng chung giao diện user. Chỉ `ADMINISTRATOR` vào trang quản lý.

---

## 1. API backend

Prefix `/api/v1`. Envelope giống các API khác:

```json
{ "data": {}, "meta": { "total": 0, "page": 1, "page_size": 20 } }
```

Header request FE đã gửi: `Authorization: Bearer <jwt admin>`, `X-Tenant-Id`, `Accept: application/json`, `X-Request-Id`. Body JSON kèm `Content-Type: application/json`.

RBAC mọi endpoint dưới đây: **chỉ `ADMINISTRATOR`**. Role khác trả **403**.

### `UserDTO`

```ts
type UserRole = 'OPERATOR' | 'REVIEWER' | 'ADMINISTRATOR'
type UserStatus = 'invited' | 'active' | 'disabled'

type UserDTO = {
  id: string                 // Keycloak user id
  email: string
  display_name: string
  role: UserRole
  status: UserStatus
  created_at: string         // ISO-8601
  invited_at: string | null  // lần gửi email đặt mật khẩu gần nhất
  last_login_at: string | null
}
```

`status` lấy từ Keycloak, không lưu tay:

| Điều kiện | `status` |
|---|---|
| `enabled == false` | `disabled` |
| `enabled` và `requiredActions` chứa `UPDATE_PASSWORD` | `invited` |
| còn lại | `active` |

`last_login_at` được null. FE hiện "Chưa đăng nhập" khi `status = invited`, và "—" khi active/disabled mà chưa có mốc. Có thể điền sau từ sự kiện LOGIN của webhook.

### `GET /api/v1/users`

Query:

| Param | Quy tắc |
|---|---|
| `q` | optional, tối đa 200 ký tự, tìm theo email hoặc tên |
| `role` | optional, một trong ba role |
| `status` | optional, `invited` \| `active` \| `disabled` |
| `limit` | 1..100, mặc định 20 |
| `offset` | ≥ 0, mặc định 0 |

`200` → `data: UserDTO[]`. `meta.total` là tổng sau lọc. `meta.page` = `offset / limit + 1` (1-based). `meta.page_size` = `limit`.

### `POST /api/v1/users`

```json
{
  "email": "ten@congty.com",
  "display_name": "Nguyễn Văn A",
  "role": "OPERATOR"
}
```

- `email`: đúng định dạng, lưu lowercase. Username Keycloak = email.
- `display_name`: 1..255 ký tự sau trim.
- `role`: enum ở trên.

`201` → `data: UserDTO` với `status: "invited"`.

Việc backend làm, theo thứ tự:

1. Tạo user Keycloak, không đặt password.
2. Gán đúng một realm role trong ba role trên.
3. Gọi gửi email action `UPDATE_PASSWORD`.
4. Ghi `app_user` ngay trong request này (đừng chờ webhook login). `keycloak_sub` = id Keycloak.

Nếu bước 1–2 xong mà bước 3 lỗi SMTP: user vẫn tồn tại, trả **503** `email_not_configured`. FE hiện lỗi trên form; admin gửi lại bằng `POST .../invite`.

### `PATCH /api/v1/users/{id}`

```json
{ "role": "REVIEWER" }
```

Đổi realm role: gỡ `OPERATOR` / `REVIEWER` / `ADMINISTRATOR` cũ, gán role mới. `200` → `UserDTO`.

### `POST /api/v1/users/{id}/disable`

Không body. Keycloak `enabled: false`. `200` → `UserDTO` `status: "disabled"`.

### `POST /api/v1/users/{id}/enable`

Không body. Keycloak `enabled: true`. Nếu còn `UPDATE_PASSWORD` thì `status` về `invited`, không thì `active`.

### `POST /api/v1/users/{id}/invite`

Không body. Gửi lại email `UPDATE_PASSWORD`. Chỉ khi user đang `invited`. `200` → `UserDTO`, cập nhật `invited_at`.

### Lỗi

FE đọc `detail` (string) và `code` (nếu có).

```json
{ "detail": "Email đã tồn tại", "code": "email_exists" }
```

| HTTP | `code` | Khi nào |
|---|---|---|
| 401 | | JWT không hợp lệ |
| 403 | | Không phải `ADMINISTRATOR` |
| 404 | | `{id}` không có trong tenant. Detail `Not Found` thuần (route chưa mount) FE hiểu là API chưa được triển khai |
| 409 | `email_exists` | Email/username đã có |
| 409 | `cannot_disable_self` | Admin khóa chính mình |
| 409 | `cannot_change_own_role` | Admin đổi role của chính mình |
| 409 | `last_administrator` | Khóa hoặc hạ role của quản trị viên cuối cùng |
| 409 | `invite_not_applicable` | Gửi lại email khi user không còn `invited` |
| 422 | | Sai email, tên, role, query |
| 502 | `keycloak_unavailable` | Admin API Keycloak lỗi |
| 503 | `email_not_configured` | Chưa có SMTP hoặc Keycloak từ chối gửi mail |

Từ chối khóa / đổi role của chính người gọi (so `sub` hoặc email trong JWT).

---

## 2. Keycloak

Realm `contract-intelligence`. Client public `contract-intel-frontend` giữ nguyên cho SSO. Client bí mật `contract-intel-backend` là phía gọi Admin API. Secret nằm ở env backend (`KEYCLOAK_ADMIN_CLIENT_SECRET` / `keycloak_admin_client_secret`), không đưa sang frontend.

Access token của frontend phải có `realm_access.roles` (scope mặc định `roles` trên client `contract-intel-frontend`). Không có claim này thì app không biết `ADMINISTRATOR` và đưa admin vào giao diện user, trang quản lý không mở được. Local đã gắn scope `roles` vào client đang chạy; realm export cũng cần scope này khi import lại.

`registrationAllowed` giữ `false`. User không tự đăng ký.

### Quyền service account

Service account `contract-intel-backend` hiện chỉ có `view-users`, `view-realm`, `view-clients`, `view-events`, `manage-events`. Client admin hiện chỉ `GET` user để webhook đọc profile.

Thêm realm-management role:

- `manage-users` — tạo, sửa, khóa user và gán realm role
- `query-users` — tìm danh sách

Token admin: client credentials grant bằng client id/secret đã có, rồi gọi `/admin/realms/contract-intelligence/...`.

### Tạo user

`POST /admin/realms/contract-intelligence/users`

```json
{
  "username": "ten@congty.com",
  "email": "ten@congty.com",
  "firstName": "Nguyễn Văn A",
  "enabled": true,
  "emailVerified": true,
  "requiredActions": ["UPDATE_PASSWORD"],
  "attributes": {
    "tenant_id": ["tenant_vgr_01"]
  }
}
```

Không gửi `credentials`. `emailVerified: true` vì realm đang `verifyEmail: false` và email mời chỉ để đặt mật khẩu, không phải bước xác minh email riêng.

Mapper `tenant_id` trên client đang hardcode `tenant_vgr_01`, nên JWT vẫn có tenant dù quên attribute. Vẫn ghi attribute để khỏi gãy khi mapper chuyển sang đọc attribute user.

Đọc `Location` header để lấy user id.

### Gán role

Lấy representation: `GET /admin/realms/contract-intelligence/roles/{OPERATOR|REVIEWER|ADMINISTRATOR}`

Gán: `POST /admin/realms/contract-intelligence/users/{id}/role-mappings/realm`

```json
[{ "id": "<role-uuid>", "name": "OPERATOR" }]
```

Khi đổi role: `DELETE` cùng path với role cũ, rồi `POST` role mới. Role trên JWT mà frontend đọc là **realm role**, không chỉ client role.

### Email đặt mật khẩu

`PUT /admin/realms/contract-intelligence/users/{id}/execute-actions-email?client_id=contract-intel-frontend&lifespan=43200&redirect_uri=http://localhost:5173/`

Body:

```json
["UPDATE_PASSWORD"]
```

`lifespan` tính bằng giây (ở đây 12 giờ, trùng `actionTokenGeneratedByAdminLifespan` hiện tại). Có thể nâng lifespan nếu muốn link mời sống lâu hơn.

`redirect_uri` phải nằm trong Valid Redirect URIs của `contract-intel-frontend`. Hiện mới có:

- `http://localhost:5173/auth/callback`
- `http://localhost:5173/auth/silent-callback`

Cần thêm `http://localhost:5173/` để sau khi đặt mật khẩu user về trang đăng nhập app. Không dùng `/auth/callback` cho link này — path đó chỉ nhận authorization code.

Khóa / mở: `PUT /admin/realms/contract-intelligence/users/{id}` với `enabled: false` hoặc `true`.

### SMTP

Realm export chưa có `smtpServer`, nên `execute-actions-email` không gửi được thư. Bật SMTP trên realm (host, port, from, auth, starttls/ssl). `fromDisplayName` gợi ý: `Lexis Contract Intelligence`. Theme email đang là `base`; có thể giữ, không chặn luồng mời.

Local có thể trỏ SMTP tới một mailbox bắt thư (Mailhog hoặc tương đương) để admin bấm link đặt mật khẩu mà không cần hộp thư thật.

Sau khi user đặt mật khẩu, `UPDATE_PASSWORD` rời `requiredActions`, `status` thành `active`. Lần đăng nhập sau đi SSO bình thường.
