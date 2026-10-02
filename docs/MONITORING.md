# Giám sát hệ thống — Prometheus, Grafana, Node Exporter, cAdvisor

Quản trị viên xem dashboard Grafana ngay trong ứng dụng, ở **Quản trị → Giám sát hệ thống** (`/admin/monitoring`).
Langfuse Cloud vẫn giữ trace từng tài liệu (model, độ trễ, chi phí, lỗi, fallback, số trang).
Prometheus chỉ giữ số liệu tổng hợp.

## Kiến trúc

```
Trình duyệt (admin)
  │  /admin/monitoring  (React, RequireRole admin)
  │  POST /api/v1/admin/monitoring/session   Bearer Keycloak → cookie /grafana (HttpOnly, 5 phút)
  │  <iframe src="https://API_HOST/grafana/d/ci-overview?kiosk">
  ▼
Caddy (prod) ── xoá X-Webauth-* ──▶ backend:8000
                                     │ /grafana/*: kiểm tra ADMINISTRATOR (401 / 403)
                                     │ xoá X-Webauth-*, Authorization, Cookie, X-Forwarded-*
                                     │ đặt X-WEBAUTH-USER=ci-admin-<hash>, X-WEBAUTH-ROLE=Viewer
                                     ▼  (mạng ci-monitoring, IP cố định 172.30.240.10)
                                   grafana:3000 ──▶ prometheus:9090 ──▶ node-exporter:9100
                                                                     ├─▶ cadvisor:8080
                                                                     ├─▶ backend:9101   (HTTP metrics)
                                                                     └─▶ ai1-worker:9108 (OCR metrics)
```

- Grafana, Prometheus, Node Exporter và cAdvisor **không publish cổng nào**. Chúng nằm trong mạng `ci-monitoring` (`internal: true`, không có đường ra Internet).
- Không thêm nginx. Production đã có Caddy, và `/grafana` đi chung host với API (`API_HOST`), nên backend làm reverse proxy có kiểm tra quyền. Cách này chạy giống nhau ở local và production.

## Luồng phân quyền

1. Menu và route `/admin/monitoring` dùng `RequireRole allow="admin"` có sẵn. User thường thấy trang 403.
2. Trang gọi `POST /api/v1/admin/monitoring/session` kèm Bearer Keycloak. Backend kiểm tra bằng `require_role("ADMINISTRATOR")`. User thường nhận **403**, không có token thì **401**.
3. Nếu hợp lệ, backend đặt cookie `ci_monitoring_session`: JWT HS256 ký bằng `MONITORING_SESSION_SECRET`, có `HttpOnly`, `Path=/grafana`, `Max-Age=300`, `Secure`. Khi frontend và API khác site thì thêm `SameSite=None; Partitioned`. Lý do cần cookie: iframe không gửi được header Bearer.
4. Mỗi request `/grafana/*` đều được kiểm tra lại (Bearer hoặc cookie, role phải là ADMINISTRATOR):
   - Không có hoặc sai thông tin xác thực: **401**.
   - Role khác ADMINISTRATOR: **403**.
   - Chỉ cho `GET`, `HEAD`, `POST`. `PUT`, `PATCH`, `DELETE` trả **405**.
   - `/grafana/api/admin/*` trả **403**.
   - `POST` có `Origin` từ site khác trả **403**.
5. Trang tự gia hạn cookie ở nửa vòng đời bằng token Keycloak mới. Admin bị gỡ quyền sẽ mất quyền xem trong tối đa 5 phút.

## Xác thực với Grafana (auth proxy)

| Cấu hình | Giá trị |
|---|---|
| `GF_AUTH_PROXY_ENABLED` | `true`, header `X-WEBAUTH-USER`, `Role:X-WEBAUTH-ROLE` |
| `GF_AUTH_PROXY_WHITELIST` | chỉ IP backend trên `ci-monitoring` (`MONITORING_PROXY_IP`) |
| `GF_AUTH_ANONYMOUS_ENABLED` | `false` |
| `GF_AUTH_DISABLE_LOGIN_FORM`, `GF_AUTH_BASIC_ENABLED` | không có đường đăng nhập nào khác |
| `GF_USERS_AUTO_ASSIGN_ORG_ROLE` | `Viewer`. Admin ứng dụng **không** thành Grafana Admin |
| `GF_SECURITY_ALLOW_EMBEDDING` | `true`. Backend thêm `Content-Security-Policy: frame-ancestors 'self' <CORS origins>` |
| Datasource, dashboard | provision từ git: `editable: false`, `allowUiUpdates: false`, `disableDeletion: true` |

Tên user trong Grafana là bút danh `ci-admin-<sha256(tenant:user)[:16]>`. Grafana không nhận email hay tên người dùng.
Viewer không sửa được datasource hay dashboard, không tạo được user, không đổi được cấu hình. Đã kiểm tra thực tế: các thao tác này trả 403 hoặc 405.

## Dashboard `ci-overview` — "Contract Intelligence — Operations"

| Mục | Panel |
|---|---|
| Services | OCR API (AI1 worker), Backend API, Prometheus, Grafana, Node Exporter, cAdvisor: **Healthy / Degraded / Down** |
| System | CPU, RAM, Disk usage, Disk IO, Network, Load average |
| Docker | Container CPU, Container RAM, Container status (Running/Stopped), Container restarts |
| Application / OCR | OCR requests, Success rate, Failure rate, Pages processed, P50/P95/P99 latency, Fallback rate, HITL rate, lỗi theo mã, Backend API req/s và P95 |
| Cost | Total OCR cost, Cost per page, Cost by model, chi phí theo giờ |

Quy tắc trạng thái dịch vụ:

- **Down**: Prometheus không scrape được.
- **Degraded** cho AI1: từ 20% lệnh OCR thất bại trong 15 phút.
- **Degraded** cho backend: từ 5% response 5xx trong 5 phút.

File nguồn: `infra/monitoring/grafana/dashboards/ci-overview.json`. Sửa JSON trong git rồi chờ Grafana nạp lại (khoảng 60 giây).

## Metrics

| Metric | Nhãn | Nguồn |
|---|---|---|
| `ai1_ocr_requests_total` | `engine`, `status` | AI1 worker, mỗi lệnh OCR |
| `ai1_ocr_failures_total` | `engine`, `error_code` | AI1 worker |
| `ai1_ocr_request_duration_seconds` (histogram) | `engine` | AI1 worker |
| `ai1_ocr_pages_processed_total` | `engine`, `page_status` | snapshot kết quả |
| `ai1_ocr_fallback_pages_total` | `engine` | trang có `ocr:text_reader_fallback*` |
| `ai1_ocr_review_pages_total` | `engine` | trang có `needs_review:*` / `possible_duplicate_of:*` |
| `ai1_ocr_model_calls_total`, `ai1_ocr_cost_usd_total` | `model` | cùng `cost_details` gửi Langfuse |
| `ai1_ocr_in_progress` | — | AI1 worker |
| `ci_backend_http_requests_total`, `ci_backend_http_request_duration_seconds` | `method`, `route` (template), `status_class` | backend |
| `node_*` | — | Node Exporter |
| `container_*` | `container`, `short_id`, `image` | cAdvisor (qua containerd) |

**Không có** trong label: nội dung hợp đồng, text OCR, tên file, document id, tenant, user, token, API key.
Giá trị label lấy từ tập đóng (engine, mã lỗi `[A-Z0-9_]`, model id). Giá trị lạ được gom về `other` / `OTHER`. Route là template, ví dụ `/api/v1/dossiers/{dossier_id}`, không bao giờ là đường dẫn thật.

## Biến môi trường mới

| Biến | Ở đâu | Mặc định local | Ghi chú |
|---|---|---|---|
| `GRAFANA_UPSTREAM_URL` | backend | `http://grafana:3000` | trống = tắt giám sát |
| `GRAFANA_DASHBOARD_UID` | backend | `ci-overview` | dashboard hiển thị trong iframe |
| `MONITORING_SESSION_SECRET` | backend | `ci_monitoring_session_secret_dev` | **bắt buộc** ở prod. Prod từ chối giá trị `*_dev` |
| `MONITORING_SESSION_TTL_SECONDS` | backend | `300` | 60–3600 |
| `MONITORING_COOKIE_SAMESITE` | backend | `none` | `lax` khi frontend và API cùng site |
| `MONITORING_COOKIE_SECURE` | backend | `true` | |
| `METRICS_PORT` | backend | `9101` | cổng scrape nội bộ |
| `AI1_METRICS_PORT` | ai1-worker | `9108` | cổng scrape nội bộ |
| `GRAFANA_ROOT_URL` | grafana | `http://127.0.0.1:8000/grafana/` | prod: `https://$API_HOST/grafana/` |
| `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD` | grafana | `ci-grafana-admin` / `ci_grafana_admin_dev` | **bắt buộc** ở prod |
| `MONITORING_SUBNET` / `MONITORING_PROXY_IP` | compose | `172.30.240.0/24` / `172.30.240.10` | đổi nếu trùng subnet |
| `PROMETHEUS_RETENTION_TIME` / `PROMETHEUS_RETENTION_SIZE` | prometheus | `15d` / `5GB` | |

Frontend không có biến mới. Backend trả về đường dẫn dashboard nên không hardcode UID. `LANGFUSE_SECRET_KEY` chỉ nằm trong `ai-service/.env`, không bao giờ tới frontend.

## Chạy local

```powershell
docker compose up -d --build            # lần đầu: build lại backend + ai1-worker (thêm prometheus-client)
cd frontend; npm run dev                # http://localhost:5173
```

Đăng nhập `admin@ci.local` rồi mở **Quản trị → Giám sát hệ thống**.

- Docker Desktop: Node Exporter đọc VM của Docker Desktop, không phải Windows. Ổ `C:\`, `D:\` hiện dưới dạng filesystem của VM.
- Chạy frontend ở `localhost:5173` và API ở `127.0.0.1:8000` là hai site khác nhau. Cookie là `SameSite=None; Secure; Partitioned`, được Chrome, Edge và Firefox chấp nhận trên localhost. Safari không lưu cookie `Secure` qua http. Muốn dùng Safari thì đặt `MONITORING_COOKIE_SAMESITE=lax` + `MONITORING_COOKIE_SECURE=false`, và dùng `VITE_API_BASE_URL=http://localhost:8000` (cùng site với `localhost:5173`).

## Triển khai production

1. `deploy/.env.prod`: `bootstrap.sh` tự sinh `MONITORING_SESSION_SECRET` và `GRAFANA_ADMIN_PASSWORD` (giá trị `generate`). Server cũ thì thêm 2 biến này bằng tay (`openssl rand -hex 24`).
2. `sudo deploy/deploy.sh --pull`. Smoke test kiểm tra `/grafana/` trả 401 với người lạ.
3. Từ máy khác: `deploy/check_external.sh API_HOST AUTH_HOST`. Script kiểm tra thêm `/grafana` 401 và các cổng 3000, 9090, 9100, 9101, 9108 đều đóng.
4. Nếu frontend có domain cùng site với API (vd. `app.x.com` + `api.x.com`): đặt `MONITORING_COOKIE_SAMESITE=lax`.

## Kiểm tra quyền

| Kiểm tra | Kỳ vọng |
|---|---|
| Admin → `/admin/monitoring` | iframe dashboard hiển thị |
| User thường → `/admin/monitoring` | trang 403. `POST …/monitoring/session` → 403 |
| User thường (Bearer) → `/grafana/` | 403 |
| Không đăng nhập → `/grafana/` (kể cả gửi `X-WEBAUTH-USER: admin`) | 401 |
| Admin → `/grafana/api/user/orgs` | `role: Viewer` |
| Admin → `PUT /grafana/api/datasources/…` | 405. Tạo datasource / user / lưu dashboard → 403 |

```bash
# Prometheus targets — chạy trên server
docker exec ci-prometheus wget -qO- 'http://localhost:9090/api/v1/targets?state=active' | grep -o '"health":"[a-z]*"'
```

Test tự động:

- `backend/tests/unit/test_monitoring.py`: session, 401/403, header giả, Viewer, 405, CSRF, nhãn metrics.
- `ai-service/tests/unit/test_ocr_metrics.py`
- `frontend/tests/monitoring.test.ts`

## Rủi ro còn lại

- **Thu hồi quyền chậm tối đa 5 phút** (TTL cookie). Muốn chặt hơn thì giảm `MONITORING_SESSION_TTL_SECONDS`.
- **Cookie bên thứ ba**: Safari (và trình duyệt chặn cookie partitioned) không xem được iframe khi frontend và API khác site. Nên đặt frontend cùng site với API ở production.
- **Viewer chạy được PromQL tuỳ ý** qua `/api/ds/query`. Dữ liệu chỉ là số liệu tổng hợp, không có dữ liệu nhạy cảm.
- **cAdvisor chạy `privileged`** và đọc socket containerd (quyền tương đương root trên host). Đây là yêu cầu của cAdvisor. Container này không có cổng ra ngoài.
- **Node Exporter dùng `pid: host` + mount `/` read-only.** Network của host lấy từ cAdvisor (cgroup gốc), vì Node Exporter không chạy `network_mode: host` (tránh mở cổng 9100 trên host).
- **Grafana tự tạo user Viewer** (auto sign-up) cho mỗi admin, với tên bút danh. Nếu cần gỡ, dùng `docker exec` với tài khoản server admin.
- **Chưa có cảnh báo** (Alertmanager). Dashboard chỉ để xem.
- **Mạng `ci-monitoring` có ai1-worker**: nếu ai1-worker bị chiếm quyền thì đọc được Prometheus (chỉ đọc), nhưng không giả danh được với Grafana, vì Grafana chỉ tin IP của backend.
