# Triển khai online — 1 máy chủ Linux + Docker Compose

Chạy toàn bộ stack (Keycloak, Postgres ×2, Kafka, MinIO, backend, backend-worker, AI1, AI2, giám sát) trên một máy chủ cloud Linux, bằng chính `docker-compose.yml` của dự án cộng với `deploy/compose.prod.yml`. Caddy đứng trước, lo HTTPS. Frontend có thể chạy trên cùng máy (tuỳ chọn).

Mọi thao tác làm qua SSH từ máy dev. Không cần công cụ của nhà cung cấp cloud nào.

## Cái gì ra Internet

| Địa chỉ | Tới | Dùng bởi |
|---|---|---|
| `https://api-<ip>.sslip.io` | backend `:8000` (REST, SSE `/api/v1/runs/{id}/events`, `/docs`) | Frontend |
| `https://auth-<ip>.sslip.io` | Keycloak `:8080` (đăng nhập, OIDC). `/admin` trả 404 | Frontend, người dùng |
| `https://app-<ip>.sslip.io` | frontend (bản build tĩnh). Chỉ có khi `APP_HOST` được đặt trong `deploy/.env.prod` | Người dùng |
| `https://api-<ip>.sslip.io/grafana/` | Grafana qua backend. Chỉ ADMINISTRATOR; người lạ 401, user thường 403 | Trang `/admin/monitoring` |

Những thứ không ra Internet, chỉ nằm trong mạng `ci-network`:

- **AI1** nhận lệnh và trả kết quả qua Kafka.
- **Backend gọi AI2** qua `http://ai2-service:8002`. Cổng 8002 không mở ra ngoài, theo yêu cầu mentor.
- Postgres, Kafka, MinIO, mailpit và Keycloak admin.
- Grafana, Prometheus, Node Exporter, cAdvisor: nằm trong mạng nội bộ `ci-monitoring`, không có cổng. Xem [docs/MONITORING.md](../docs/MONITORING.md).

`sslip.io` phân giải `api-1-2-3-4.sslip.io` về `1.2.3.4`. Vì vậy không cần mua domain mà vẫn có chứng chỉ Let's Encrypt thật.

## Máy chủ cần

- Ubuntu 22.04/24.04 (hoặc Debian 12), kiến trúc x86-64, có quyền `sudo`.
- Tối thiểu 4 vCPU, 8 GB RAM (khuyên dùng 16 GB), 60 GB đĩa. Stack local dùng khoảng 2,7 GB RAM khi nhàn rỗi (đo 04/10/2026); build image và OCR hồ sơ lớn cần thêm.
- Một IPv4 công khai **cố định**: tên miền `sslip.io` và chứng chỉ gắn với IP này.
- Cổng 80 và 443 mở từ Internet ở firewall của nhà cung cấp (security group). Cổng 22 mở cho người vận hành.

## Kế hoạch triển khai qua SSH

### Thông tin cần có trước khi bắt đầu

| Thông tin | Dùng để |
|---|---|
| IP công khai, user SSH, khoá SSH (hoặc mật khẩu) | Đăng nhập máy chủ |
| Nhánh cần deploy (thường `develop`) | `git checkout` |
| Quyền đọc repo từ máy chủ | Repo riêng tư thì cần Personal Access Token hoặc deploy key |
| `MISTRAL_API_KEY`, `OPENAI_API_KEY` | AI1 OCR (`ai-service/.env`) |
| `AI2_LLM_BASE_URL`, `AI2_LLM_API_KEY` | AI2 (`deploy/.env.prod`) |
| SMTP (tuỳ chọn) | Thư mời và chia sẻ; trống thì thư vào mailpit |
| Frontend chạy trên máy này hay ở nơi khác | Quyết định `APP_HOST` |

### Bước 1. Kiểm tra máy chủ

```bash
ssh <user>@<ip> 'lsb_release -ds; uname -m; nproc; free -g | sed -n 2p; df -h / | tail -1; sudo -n true && echo "sudo ok"'
ssh <user>@<ip> 'sudo ss -ltnp | grep -E ":(80|443) " || echo "80/443 free"'
```

Cần thấy: Ubuntu/Debian, `x86_64`, đủ CPU/RAM/đĩa như trên, `sudo ok`, và chưa có gì chiếm cổng 80/443. Nếu máy đã chạy web server khác ở 80/443 thì phải dừng nó hoặc chọn máy khác: Caddy cần hai cổng này để xin chứng chỉ.

### Bước 2. Lấy mã nguồn và cài nền

```bash
ssh <user>@<ip>
sudo git clone https://github.com/AI20K-VGR/contract-intelligence-core.git /opt/contract-intelligence
cd /opt/contract-intelligence
sudo git checkout <nhánh cần deploy>
sudo deploy/bootstrap.sh
```

`bootstrap.sh` cài Docker (xoay vòng log 5 × 20 MB), bật firewall trong máy (chỉ SSH, 80, 443), thêm swap nếu RAM dưới 16 GB, và tạo `deploy/.env.prod` với:

- `API_HOST`, `AUTH_HOST`, `APP_HOST` theo IP công khai của máy;
- `FRONTEND_ORIGINS`, `FRONTEND_BASE_URL` trỏ về `https://app-<ip>.sslip.io`;
- mọi secret được sinh ngẫu nhiên.

Chạy lại được: `deploy/.env.prod` đã có thì script không đụng tới.

### Bước 3. Điền cấu hình

```bash
sudo nano deploy/.env.prod        # AI2_LLM_BASE_URL, AI2_LLM_API_KEY; SMTP_* nếu gửi thư thật
sudo nano ai-service/.env         # MISTRAL_API_KEY, OPENAI_API_KEY; AI2_EMBEDDING_* nếu dùng vector
```

Có sẵn `ai-service/.env` trên máy dev thì chép lên thay vì gõ lại:

```bash
scp ai-service/.env <user>@<ip>:/tmp/ai.env
ssh <user>@<ip> 'sudo install -m 600 /tmp/ai.env /opt/contract-intelligence/ai-service/.env && rm /tmp/ai.env'
```

Không muốn máy này phục vụ frontend: để `APP_HOST=` trống và bỏ `https://app-…` khỏi `FRONTEND_ORIGINS`.

### Bước 4. Triển khai

```bash
sudo deploy/deploy.sh
```

`deploy.sh` làm các bước sau:

1. Build image (và frontend nếu có `APP_HOST`).
2. `up -d`.
3. Chờ backend healthy. Backend tự chạy `alembic upgrade head`.
4. Chạy `keycloak_configure.py`:
   - Thêm `FRONTEND_ORIGINS` vào redirect/web origins.
   - Đổi secret của client backend.
   - **Đổi mật khẩu 3 tài khoản demo** (mật khẩu trong `realm-export.json` là công khai).
   - Cấu hình SMTP nếu có.
   - Bật chống dò mật khẩu: khoá tạm tài khoản sau 5 lần sai, tối đa 15 phút.
5. Smoke test trên máy chủ: `/health`, issuer OIDC, `/admin` bị chặn, `/grafana` từ chối người lạ, frontend trả 200 (nếu có).

Lần đầu Caddy cần khoảng một phút để xin chứng chỉ. Cuối cùng script in địa chỉ frontend và các biến `VITE_*` cho frontend chạy trên máy dev.

### Bước 5. Kiểm tra từ bên ngoài

**Kiểm tra cổng phải chạy từ máy khác.** Từ chính máy chủ gọi IP công khai của nó có thể đi vòng trong máy và bỏ qua firewall. Cách chạy:

- trên máy dev: `deploy/check_external.sh api-<ip>.sslip.io auth-<ip>.sslip.io [app-<ip>.sslip.io]`; hoặc
- GitHub → Actions → `deploy-external-check` → nhập các host.

Script kiểm HTTPS, issuer OIDC, `/admin` 404, `/grafana` 401, frontend 200 (nếu truyền host) và 19 cổng nội bộ (8002, DB, Kafka, MinIO, Keycloak, mailpit, giám sát) đều đóng.

### Bước 6. Chạy thử luồng chính

Trên `https://app-<ip>.sslip.io` (hoặc frontend ở máy dev trỏ vào server):

| # | Việc | Kết quả mong đợi |
|---|---|---|
| 1 | Đăng nhập `operator@ci.local` (mật khẩu `DEMO_OPERATOR_PASSWORD` trong `deploy/.env.prod`) | Vào được trang danh sách hồ sơ |
| 2 | Tải lên một hợp đồng PDF vài trang | Hồ sơ chuyển sang OCR, tiến độ cập nhật trực tiếp (SSE) |
| 3 | Xác nhận manifest | Hồ sơ sang bước AI2 rồi `pending_review` |
| 4 | Mở trang cấu trúc và hỏi đáp trên hồ sơ | Có cây điều khoản; câu trả lời kèm trích dẫn |
| 5 | Đăng nhập `reviewer@ci.local`, thẩm định một xung đột | Trạng thái xung đột đổi |
| 6 | Đăng nhập `admin@ci.local`, mở Giám sát hệ thống | Dashboard Grafana hiện, có số liệu OCR vừa chạy |

## Cập nhật

```bash
cd /opt/contract-intelligence && sudo deploy/deploy.sh --pull
```

Server cài trước 02/10/2026 (trước issue #52) cần làm thêm một lần trước lần cập nhật đầu tiên:

1. `sudo deploy/backup.sh`. Image `backend-db` đổi từ `postgres:16-alpine` sang `pgvector/pgvector:pg16`; cùng Postgres 16 và DB dùng `--locale=C` nên dữ liệu dùng tiếp được, nhưng vẫn nên có bản backup.
2. Thêm `AI2_DB_PASSWORD=$(openssl rand -hex 24)` vào `deploy/.env.prod`.

Mỗi lần khởi động, backend tạo hoặc cập nhật role `ai2` với mật khẩu này. Role chỉ sở hữu schema `ai2` (ADR-14), không có quyền trên bảng nghiệp vụ.

## Frontend dùng API online

```env
VITE_API_BASE_URL=https://api-<ip>.sslip.io
VITE_KEYCLOAK_URL=https://auth-<ip>.sslip.io
VITE_KEYCLOAK_REALM=contract-intelligence
VITE_KEYCLOAK_CLIENT_ID=contract-intel-frontend
```

## Frontend chạy trên chính server

Khi `APP_HOST` có giá trị trong `deploy/.env.prod` (server cài mới: `bootstrap.sh` đặt sẵn `app-<ip>.sslip.io`), `deploy.sh` thêm `deploy/compose.frontend.yml`: build frontend với địa chỉ API và Keycloak của server, rồi Caddy phục vụ nó ở `https://$APP_HOST`. `FRONTEND_ORIGINS` phải chứa `https://$APP_HOST`; `deploy.sh` dừng lại nếu thiếu.

Server đã cài từ trước không có `APP_HOST` nên không đổi gì. Muốn bật thì thêm ba dòng `APP_HOST`, `FRONTEND_ORIGINS`, `FRONTEND_BASE_URL` như trong `deploy/.env.prod.example` rồi chạy lại `deploy.sh`.

## Frontend chạy ở nơi khác

`http://localhost:5173` đã được cho phép sẵn, nên frontend chạy trên máy dev gọi thẳng server được. Khi frontend có địa chỉ online riêng, làm như sau:

1. Thêm địa chỉ đó vào `FRONTEND_ORIGINS` trong `deploy/.env.prod`.
2. Đặt `FRONTEND_BASE_URL` cho link trong email.
3. Chạy lại `deploy.sh`.

## Việc vận hành

| Việc | Lệnh |
|---|---|
| Trạng thái | `docker compose -f docker-compose.yml -f deploy/compose.prod.yml --env-file deploy/.env.prod ps` (thêm `-f deploy/compose.frontend.yml` trước `--env-file` khi `APP_HOST` có giá trị) |
| Log backend / worker | `... logs -f backend backend-worker` |
| Keycloak admin | Trên server lấy IP container: `docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' ci-keycloak`. Trên máy mình: `ssh -L 8080:<IP đó>:8080 <user>@<ip>`, rồi mở `http://localhost:8080/admin` (user `admin`, mật khẩu `KEYCLOAK_ADMIN_PASSWORD`) |
| Đọc email (mailpit) | Như trên với `ci-mailpit` và cổng `8025`, rồi mở `http://localhost:8025` |
| Backup | `sudo deploy/backup.sh` (2 DB + MinIO vào `/var/backups/contract-intelligence`, giữ 7 ngày). Cron: `0 2 * * * /opt/contract-intelligence/deploy/backup.sh >> /var/log/ci-backup.log 2>&1` |
| Khôi phục DB backend | Chạy stack trước để backend tạo extension `vector` và role `ai2` (`pg_dump` không lưu role), rồi `docker exec -i ci-backend-db pg_restore -U ci -d contract_intelligence --clean < backend.dump` |

Mật khẩu admin Keycloak, mật khẩu tài khoản demo và mọi secret nằm trong `deploy/.env.prod` trên server (quyền 600, không commit). Gửi mật khẩu demo cho nhóm qua kênh riêng.

## Giới hạn đã biết

- **Kafka không lưu ra volume.** Mất message đang bay khi restart. Watchdog AI1 sẽ fail run bị ảnh hưởng với `AI1_TIMEOUT`, người dùng bấm chạy lại OCR.
- **Một kết quả OCR gửi thẳng qua Kafka chỉ chứa được khoảng 144 trang** (khoảng 71 KiB/trang, trần 10 MiB), cho tới khi kết quả OCR đi qua MinIO + URI (DOC-11 §4.2 #2).
- **Có giám sát, chưa có cảnh báo.** Dashboard Grafana ở `/admin/monitoring` (docs/MONITORING.md). Chưa có Alertmanager, nên vẫn phải có người xem.
