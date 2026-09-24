# Keycloak SSO Setup Guide

**Mục lục**
- [Tổng quan kiến trúc](#tổng-quan-kiến-trúc)
- [Quick Start — Spin up mọi thứ](#quick-start--spin-up-mọi-thứ)
- [Chi tiết từng thành phần](#chi-tiết-từng-thành-phần)
- [Webhook Delivery — Phase Two keycloak-events](#webhook-delivery--phase-two-keycloak-events)
- [Cấu hình Webhook qua Admin Console](#cấu-hình-webhook-qua-admin-console)
- [Payload Format & Tích hợp với Backend](#payload-format--tích-hợp-với-backend)
- [Kiểm thử cục bộ (Local Testing)](#kiểm-thử-cục-bộ-local-testing)
- [Backend .env — Biến môi trường](#backend-env--biến-môi-trường)
- [Troubleshooting](#troubleshooting)
- [Staging / Production Checklist](#staging--production-checklist)

---

## Tổng quan kiến trúc

```
Browser (React)                Keycloak                         CI Backend
─────────────────            ───────────────────           ─────────────────────
                              ┌─────────────────────────┐
Login click ────────────────►│  Keycloak Login Page    │◄── User credentials
                              │  /realms/contract-      │
                              │  intelligence/login     │
                              └──────────┬──────────────┘
                                         │ access_token (RS256)
                                         │ refresh_token
                              ◄──────────┘
                              │
Frontend gửi token
trong Authorization header
 ─────────────────────────────────────────────────────────────►
                              │
                              │  Keycloak gọi webhook (Phase Two
                              │  keycloak-events extension)
                              │  POST /auth/webhooks/keycloak
                              │  X-Keycloak-Signature: HMAC-SHA256
                              │  (LOGIN, REGISTER, UPDATE_PROFILE,
                              │   DELETE_ACCOUNT)
                              ▼
                              ──────────────────────────────────────►
```

**Luồng auth chuẩn:**

1. User click "Login" trên React → redirect đến Keycloak login page
2. Keycloak xác thực → redirect về React với `code` hoặc trực tiếp `access_token`
3. React lưu `access_token` + `refresh_token`
4. Mỗi API call: `Authorization: Bearer <access_token>`
5. Backend verify RS256 signature bằng Keycloak JWKS → trả data hoặc 401
6. Khi `access_token` hết hạn: React gọi Keycloak refresh endpoint → token mới
7. Đồng thời: Keycloak gọi webhook `POST /api/v1/auth/webhooks/keycloak` (HMAC-signed) → backend sync user vào DB

---

## Quick Start — Spin up mọi thứ

### 1. Yêu cầu hệ thống

- Docker Desktop (hoặc Docker Engine + Docker Compose v2)
- 4 GB RAM trở lên (Keycloak + 2 PostgreSQL + Backend)

### 2. Build custom Keycloak image (lần đầu)

Image này chỉ chứa Keycloak + extension JAR tải sẵn từ Maven Central, **không cần Java/Maven trên host**.

```bash
# Từ thư mục gốc project
docker compose build keycloak

# Lần đầu: ~2-3 phút (pull Keycloak base image ~250 MB + extension JAR ~3 MB)
# Các lần sau: cached layer, gần như tức thì
```

`keycloak/Dockerfile` thực hiện:
1. `FROM quay.io/keycloak/keycloak:26.0`
2. `curl` xuống `keycloak-events-0.62.jar` từ Maven Central
3. `sha256sum -c` verify checksum
4. `COPY` vào `/opt/keycloak/providers/`

Keycloak Quarkus tự động scan thư mục `providers/` khi boot và register tất cả SPI thông qua Java `ServiceLoader`.

### 3. Khởi động toàn bộ stack

```bash
# Khởi động Keycloak (cần DB healthy trước)
docker compose up keycloak-db keycloak -d

# Đợi Keycloak ready (~60s cho lần đầu, xem healthcheck)
docker compose ps
# STATUS keycloak phải là "healthy" trước khi tiếp tục

# Khởi động backend database
docker compose up backend-db -d

# Khởi động backend
docker compose up backend -d
```

### 4. Verify

```bash
# Trạng thái container
docker compose ps

# Keycloak health
curl -s http://localhost:8080/health | jq .

# Keycloak Admin Console — mở browser
open http://localhost:8080/admin
# Login: admin / admin  → chọn realm "contract-intelligence"

# Backend health
curl http://localhost:8000/health
```

Bạn sẽ thấy trong Admin Console:

- **Realm Roles**: `OPERATOR`, `REVIEWER`, `ADMINISTRATOR`
- **Clients**: `contract-intel-frontend` (public SPA) + `contract-intel-backend` (confidential)
- **Events → Event listeners**: `jboss-logging`, `ext-event-http`, `ext-event-webhook`
- **Users**: 3 dev users đã pre-seeded

---

## Chi tiết từng thành phần

### Docker Compose Services

| Service | Container | Port | Description |
|---|---|---|---|
| `keycloak-db` | PostgreSQL 16 | — | Database cho Keycloak |
| `keycloak` | Custom Keycloak 26 + Phase Two extension | 8080 | Keycloak SSO + event listener |
| `backend-db` | PostgreSQL 16 | — | Database cho CI backend |
| `backend` | Python FastAPI | 8000 | CI Backend API |

### Realm `contract-intelligence` — Pre-configured

Realm được auto-import từ `keycloak/realm-export.json` khi Keycloak khởi động (nhờ `--import-realm`).

**Clients pre-configured:**

| Client ID | Loại | Mục đích |
|---|---|---|
| `contract-intel-frontend` | Public (Authorization Code + PKCE S256) | React SPA — OIDC login, nhận tokens (không client secret) |
| `contract-intel-backend` | Confidential | Backend FastAPI — verifies JWT / service account |

> SPA **không** được cấu hình `clientAuthenticatorType: client-secret`. Client authentication phải tắt (`publicClient: true`), Standard flow bật, PKCE method `S256`.

**Dev users pre-seeded:**

| Email | Password | Role | tenant_id |
|---|---|---|---|
| `admin@ci.local` | `Admin@CI123` | ADMINISTRATOR | `tenant_vgr_01` |
| `reviewer@ci.local` | `Reviewer@CI123` | REVIEWER | `tenant_vgr_01` |
| `operator@ci.local` | `Operator@CI123` | OPERATOR | `tenant_vgr_01` |

**Realm Roles:**

| Role | Backend RBAC | Description |
|---|---|---|
| `OPERATOR` | OPERATOR | Vận hành nhập liệu, upload tài liệu |
| `REVIEWER` | REVIEWER | Thẩm định hồ sơ, xác nhận manifest |
| `ADMINISTRATOR` | ADMINISTRATOR | Quản trị toàn diện |

---

## Webhook Delivery — Phase Two keycloak-events

### Vì sao không tự viết SPI?

Project là Python-only — không muốn duy trì Java toolchain cho mỗi event mới. Thay vào đó dùng extension JAR upstream đã được compile, test, và shade sẵn.

### Extension: `io.phasetwo.keycloak:keycloak-events`

- **Source**: https://github.com/p2-inc/keycloak-events
- **Maven Central**: `io.phasetwo.keycloak:keycloak-events:0.62`
- **JAR URL**: https://repo1.maven.org/maven2/io/phasetwo/keycloak/keycloak-events/0.62/keycloak-events-0.62.jar
- **Keycloak version**: compiled với Keycloak 26.6.3, API-compatible với Keycloak 26.0+

Extension đăng ký 4 EventListener provider (id + mục đích):

| Provider ID | Mục đích | Dev dùng? |
|---|---|---|
| `ext-event-http` | HttpSender — gửi raw Keycloak Event JSON tới một URL cố định (HMAC-signed, retry w/ exponential backoff) | Có (qua `WEBHOOK_URI` env var) |
| `ext-event-webhook` | Managed webhooks — REST API để CRUD webhook subscription per realm | Optional |
| `ext-event-script` | Script listener — chạy inline JS (Nashorn) khi có event | Không |
| `ext-event-mdc-logger-store` | Ghi event vào MDC cho structured logging | Không |

### Catch-all webhook (cách dùng trong dev/staging)

`docker-compose.yml` set 3 biến môi trường sau cho service `keycloak`:

```yaml
WEBHOOK_URI: http://host.docker.internal:8000/api/v1/auth/webhooks/keycloak
WEBHOOK_AUTH_TYPE: hmac
WEBHOOK_SECRET: ci_webhook_shared_secret_dev
```

Khi `WEBHOOK_URI` được set, **mọi event trong realm** được POST tới URL đó với body là raw Keycloak Event JSON, và chữ ký HMAC-SHA256 của body được gửi trong header `X-Keycloak-Signature`. Backend verify chữ ký bằng cùng `WEBHOOK_SECRET` trước khi xử lý.

### Tại sao catch-all mà không phải managed webhook?

- **Catch-all** không cần config trong realm → phù hợp với IaC (realm export JSON giữ nguyên)
- Backend là consumer duy nhất, không có subscription phức tạp
- Staging/Prod muốn per-event filtering (chỉ LOGIN/REGISTER/...) → dùng `ext-event-webhook` REST API

---

## Cấu hình Webhook qua Admin Console

Nếu muốn chuyển từ catch-all sang managed webhook (per-subscription, có UI):

1. **Đăng nhập** http://localhost:8080/admin → realm `contract-intelligence`
2. **Realm Settings → Events tab → Event listeners**
   - Đảm bảo `ext-event-webhook` đã được thêm (đã có trong realm-export.json)
   - Xóa `ext-event-http` nếu không muốn dùng catch-all
3. **Tạo webhook subscription** qua REST API (cần realm admin token):

```bash
# Lấy admin token
TOKEN=$(curl -s -X POST \
  "http://localhost:8080/realms/master/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" \
  -d "client_id=admin-cli" \
  -d "username=admin" \
  -d "password=admin" \
  | jq -r .access_token)

# Tạo webhook cho contract-intelligence realm
curl -X POST \
  "http://localhost:8080/admin/realms/contract-intelligence/webhooks" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": "true",
    "url": "http://host.docker.internal:8000/api/v1/auth/webhooks/keycloak",
    "authType": "hmac",
    "secret": "ci_webhook_shared_secret_dev",
    "algorithm": "HmacSHA256",
    "eventTypes": ["LOGIN", "REGISTER", "UPDATE_PROFILE", "DELETE_ACCOUNT"]
  }'
```

Sau khi webhook subscription tồn tại, có thể **xóa `WEBHOOK_URI` env var** khỏi `docker-compose.yml`.

---

## Payload Format & Tích hợp với Backend

### Payload Phase Two gửi

Phase Two dùng `ModelToRepresentation.toRepresentation(event)` để serialize raw Keycloak `Event`/`AdminEvent`. Format user-event (LOGIN/REGISTER/UPDATE_PROFILE/DELETE_ACCOUNT):

```json
{
  "time": 1737370000000,
  "type": "LOGIN",
  "realmId": "abc-123",
  "clientId": "contract-intel-frontend",
  "userId": "f8a7...-...-...-...",
  "sessionId": "...",
  "ipAddress": "172.17.0.1",
  "error": null,
  "details": {
    "username": "admin@ci.local",
    "auth_method": "openid-connect",
    "redirect_uri": "http://localhost:3000/",
    "consent": "no",
    "code_id": "...",
    "email": "admin@ci.local",
    "client_id": "contract-intel-frontend"
  }
}
```

Header kèm theo:

```
Content-Type: application/json
X-Keycloak-Signature: 3f2a1b...   (HMAC-SHA256 hex của raw body, secret = WEBHOOK_SECRET)
User-Agent: Keycloak/26.0 ext-event-http
```

`X-Keycloak-Signature` cho phép backend verify request thực sự đến từ Keycloak.

### Backend handler — Approach A (Admin API fetch)

Vì payload Phase Two chỉ có `userId` (không có `firstName`/`lastName`/`email`), backend flow theo **Approach A**:

```
Phase Two → POST /api/v1/auth/webhooks/keycloak (raw Event JSON)
                │
                ▼
        ┌───────────────────────────────────────────────┐
        │  webhook_router.py                            │
        │  1. Đọc raw body bytes                        │
        │  2. Verify HMAC-SHA256 (X-Keycloak-Signature) │
        │  3. Parse JSON → KeycloakUserEvent            │
        └────────────────────┬──────────────────────────┘
                             │
                             ▼
        ┌───────────────────────────────────────────────┐
        │  KeycloakUserSyncService                      │
        │  ┌─────────────────────────────────────────┐  │
        │  │ Cho REGISTER/LOGIN/UPDATE_PROFILE:      │  │
        │  │   keycloak_admin_client                 │  │
        │  │     .get_user_profile(user_id)          │──┼──► GET /admin/realms/{realm}/users/{id}
        │  │   keycloak_admin_client                 │  │   (Client Credentials Grant)
        │  │     .get_user_realm_roles(user_id)      │──┼──► GET /admin/realms/{realm}/users/{id}/role-mappings/realm
        │  │   user_repository                       │  │
        │  │     .upsert_from_keycloak(...)          │──┼──► INSERT/UPDATE app_user
        │  └─────────────────────────────────────────┘  │
        │  Cho DELETE_ACCOUNT:                          │
        │   user_repository.deactivate_by_keycloak_sub  │
        └───────────────────────────────────────────────┘
```

Service Account `contract-intel-backend` phải có realm-management client role `view-users` — đã config trong `realm-export.json` (xem "Service Account Permissions" bên dưới).

### HMAC verification (đã implement)

```python
# webhook_router.py
def _verify_keycloak_signature(body_bytes, signature_header):
    expected = hmac.new(
        key=KEYCLOAK_WEBHOOK_SECRET.encode(),
        msg=body_bytes,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header.lower())
```

Config: `KEYCLOAK_WEBHOOK_VERIFY_SIGNATURE=true|false`. Default: `true`. Set `false` CHỈ trong local debug.

### Service Account Permissions

Service account của client `contract-intel-backend` cần realm-management client roles:

| Role | Cần cho |
|---|---|
| `view-users` | `GET /admin/realms/{realm}/users/{id}` |
| `view-events` | (optional) `GET /admin/realms/{realm}/events` |
| `manage-events` | (optional) webhook resend feature |

Đã pre-configured trong `realm-export.json` qua user entry:

```json
{
  "id": "service-account-contract-intel-backend",
  "username": "service-account-contract-intel-backend",
  "enabled": true,
  "serviceAccountClientId": "contract-intel-backend",
  "clientRoles": {
    "realm-management": ["view-users", "view-realm", "view-clients", "view-events", "manage-events"]
  }
}
```

Keycloak tự động link user này với client `contract-intel-backend` thông qua `serviceAccountClientId`. Khi service account authenticate, nó nhận các roles này trong access token.

---

## Kiểm thử cục bộ (Local Testing)

### 1. Lấy Access Token bằng curl

```bash
KC_URL="http://localhost:8080/realms/contract-intelligence"

TOKEN=$(curl -s -X POST \
  "${KC_URL}/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" \
  -d "client_id=contract-intel-frontend" \
  -d "username=admin@ci.local" \
  -d "password=Admin@CI123" \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo $TOKEN
```

### 2. Gọi backend API với token

```bash
curl -s http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Tenant-Id: tenant_vgr_01"
```

### 3. Kiểm tra webhook đã được gọi

Backend log mỗi webhook request. Trigger bằng cách login:

```bash
# Theo dõi log
docker compose logs -f backend | grep -i webhook

# Trong terminal khác: trigger LOGIN event
curl -s -X POST "${KC_URL}/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" \
  -d "client_id=contract-intel-frontend" \
  -d "username=operator@ci.local" \
  -d "password=Operator@CI123" \
  > /dev/null
```

### 4. Test webhook endpoint trực tiếp

```bash
# Tính HMAC
SECRET="ci_webhook_shared_secret_dev"
BODY='{"type":"LOGIN","time":1737370000000,"realmId":"contract-intelligence","clientId":"contract-intel-frontend","userId":"dev-operator-keycloak-id","details":{"username":"operator@ci.local"}}'
SIG=$(echo -n "$BODY" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $2}')

curl -i -X POST http://localhost:8000/api/v1/auth/webhooks/keycloak \
  -H "Content-Type: application/json" \
  -H "X-Keycloak-Signature: $SIG" \
  -d "$BODY"
```

### 5. Refresh Token Flow

```bash
KC_URL="http://localhost:8080/realms/contract-intelligence"

REFRESH=$(curl -s -X POST \
  "${KC_URL}/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" \
  -d "client_id=contract-intel-frontend" \
  -d "username=admin@ci.local" \
  -d "password=Admin@CI123" \
  | python -c "import sys,json; print(json.load(sys.stdin)['refresh_token'])")

curl -s -X POST "${KC_URL}/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=refresh_token" \
  -d "client_id=contract-intel-frontend" \
  -d "refresh_token=$REFRESH"
```

---

## Backend .env — Biến môi trường

```bash
cp backend/.env.example backend/.env
```

**Biến bắt buộc cho Keycloak SSO:**

```bash
AUTH_MODE=keycloak
KEYCLOAK_SERVER_URL=http://host.docker.internal:8080     # Docker dev
# KEYCLOAK_SERVER_URL=https://sso.company.com            # Staging/Prod
KEYCLOAK_REALM=contract-intelligence
KEYCLOAK_CLIENT_ID=contract-intel-backend
KEYCLOAK_AUDIENCE=contract-intel-backend

# Webhook signing — phải khớp với WEBHOOK_SECRET trong docker-compose.yml
KEYCLOAK_WEBHOOK_SECRET=ci_webhook_shared_secret_dev
KEYCLOAK_WEBHOOK_VERIFY_SIGNATURE=true

# Keycloak Admin REST API — dùng để fetch full user profile khi webhook
# tới (Phase Two chỉ gửi userId). Service account cần role view-users.
KEYCLOAK_ADMIN_CLIENT_ID=contract-intel-backend
KEYCLOAK_ADMIN_CLIENT_SECRET=backend_secret_dev
KEYCLOAK_ADMIN_TOKEN_TTL_SECONDS=300
KEYCLOAK_ADMIN_HTTP_TIMEOUT_SECONDS=10.0
```

**Lấy giá trị từ Keycloak Admin Console:**

1. `KEYCLOAK_SERVER_URL`: Base URL của Keycloak server
2. `KEYCLOAK_REALM`: Realm name (Admin Console → Realm Settings → General)
3. `KEYCLOAK_CLIENT_ID`: Client ID của backend client
4. `KEYCLOAK_AUDIENCE`: Thường = `KEYCLOAK_CLIENT_ID`
5. `KEYCLOAK_ADMIN_CLIENT_ID/SECRET`: Service Account credentials
   (Admin Console → Clients → contract-intel-backend → Credentials tab)

---

## Troubleshooting

### Keycloak không khởi động được

```bash
docker compose logs keycloak --tail=100
```

Nguyên nhân phổ biến:

- `keycloak-db` chưa healthy → đợi thêm
- Port 8080 đã bị chiếm → `docker compose down && docker compose up`
- Realm import thất bại → kiểm tra JSON syntax trong `realm-export.json` (dùng `python -m json.tool`)

### Extension JAR không load

```bash
docker compose logs keycloak | grep -iE "provider|phasetwo|extension"
# Phải thấy: "Loaded SPI ... HttpSenderEventListenerProviderFactory"
```

Nếu không thấy:

```bash
# Verify JAR có trong image
docker compose exec keycloak ls -lh /opt/keycloak/providers/

# Verify SHA256 (phải khớp với file .sha256 trên Maven Central)
docker compose exec keycloak sha256sum /opt/keycloak/providers/keycloak-events-*.jar
```

### Webhook không được gọi

```bash
# 1. Verify event listeners enabled
docker compose logs keycloak | grep -i "events"

# 2. Admin Console → Realm Settings → Events tab
#    Events enabled: ON
#    Admin events enabled: ON
#    Event listeners: jboss-logging, ext-event-http, ext-event-webhook

# 3. Trigger event và xem log
docker compose logs -f keycloak | grep -iE "webhook|ext-event"

# 4. Backend log
docker compose logs backend | grep -i webhook
```

### Backend trả 401

```bash
# 1. Verify Keycloak đang chạy
curl http://localhost:8080/realms/contract-intelligence/.well-known/openid-configuration

# 2. Decode JWT và verify claims (jwt.io):
#    iss = http://localhost:8080/realms/contract-intelligence
#    aud = contract-intel-backend

# 3. Verify KEYCLOAK_SERVER_URL đúng:
#    - Backend trong Docker: http://host.docker.internal:8080
#    - Backend native:      http://localhost:8080
```

### Lệnh hữu ích

```bash
# Restart toàn bộ
docker compose down && docker compose up -d

# Rebuild Keycloak (sau khi đổi Dockerfile hoặc muốn bump extension version)
docker compose build keycloak --no-cache
docker compose up -d keycloak

# Xem Keycloak log realtime
docker compose logs -f keycloak

# Reset Keycloak (xóa data + realm import lại)
docker compose down -v       # xóa volumes
docker compose up keycloak-db keycloak -d

# Truy cập Keycloak PostgreSQL
docker compose exec keycloak-db psql -U keycloak -d keycloak

# Verify extension JAR SHA256
curl -s https://repo1.maven.org/maven2/io/phasetwo/keycloak/keycloak-events/0.62/keycloak-events-0.62.jar.sha256
```

---

## Staging / Production Checklist

### Keycloak

- [ ] Keycloak chạy trên HTTPS (TLS certificate thật)
- [ ] `WEBHOOK_URI` trỏ tới public HTTPS backend URL
- [ ] `WEBHOOK_SECRET` đã được rotate, không dùng dev value
- [ ] Chuyển từ catch-all `WEBHOOK_URI` sang managed webhook subscription qua REST API để filter event types
- [x] Frontend client `contract-intel-frontend` là PKCE thuần (không `client-secret`), `publicClient: true`
- [ ] Backend client `contract-intel-backend` rotate `client-secret`, hoặc dùng `client-jwt` auth
- [ ] User passwords đã đổi (3 dev users xoá)
- [ ] Remove `KEYCLOAK_ADMIN` / `KEYCLOAK_ADMIN_PASSWORD` env vars (dùng Service Account thay vì bootstrap admin)
- [ ] Realm export `keycloakVersion` bump theo KC version đang chạy
- [ ] Phase Two extension bumped theo Keycloak patch version (0.62 ↔ KC 26.6.3)

### Backend

- [ ] `KEYCLOAK_SERVER_URL=https://sso.company.com`
- [ ] `KEYCLOAK_AUDIENCE=contract-intel-backend`
- [ ] `KEYCLOAK_WEBHOOK_VERIFY_SIGNATURE=true`
- [ ] `KEYCLOAK_WEBHOOK_SECRET` được load từ secrets manager (Vault, AWS SM, K8s Secret)
- [ ] `KEYCLOAK_ADMIN_CLIENT_SECRET` được load từ secrets manager (rotate từ Keycloak Admin Console)
- [ ] Network policy / firewall chỉ cho phép Keycloak pods gọi `/api/v1/auth/webhooks/keycloak`
- [ ] Backend có Keycloak Admin client credentials để fetch user details từ webhook payload (Approach A)
- [ ] Audit log cho mọi webhook request (HMAC verification pass/fail)
