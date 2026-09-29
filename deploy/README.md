# Triển khai online — 1 VPS + Docker Compose

Chạy toàn bộ stack (Keycloak, Postgres ×2, Kafka, MinIO, backend, backend-worker, AI1, AI2) trên một máy Linux. Caddy đứng trước, lo HTTPS.

## Cái gì ra Internet

| Địa chỉ | Tới | Dùng bởi |
|---|---|---|
| `https://api-<ip>.sslip.io` | backend `:8000` (REST, SSE `/api/v1/runs/{id}/events`, `/docs`) | Frontend |
| `https://auth-<ip>.sslip.io` | Keycloak `:8080` (đăng nhập, OIDC). `/admin` trả 404 | Frontend, người dùng |

Những thứ không ra Internet, chỉ nằm trong mạng `ci-network`:

- **AI1** nhận lệnh và trả kết quả qua Kafka.
- **Backend gọi AI2** qua `http://ai2-service:8002`. Cổng 8002 không mở ra ngoài, theo yêu cầu mentor.
- Postgres, Kafka, MinIO, mailpit và Keycloak admin.

`sslip.io` phân giải `api-1-2-3-4.sslip.io` về `1.2.3.4`. Vì vậy không cần mua domain mà vẫn có chứng chỉ Let's Encrypt thật.

## Máy chủ cần

- Ubuntu 22.04/24.04 (hoặc Debian 12).
- Tối thiểu 4 vCPU, 8 GB RAM (khuyên dùng 16 GB), 60 GB đĩa.
- Cổng 80 và 443 mở từ Internet.

## Lần đầu

```bash
ssh <user>@<ip>
sudo git clone https://github.com/AI20K-VGR/contract-intelligence-core.git /opt/contract-intelligence
cd /opt/contract-intelligence
sudo git checkout <nhánh cần deploy>
sudo deploy/bootstrap.sh          # Docker (xoay vòng log 5 × 20 MB), firewall, swap, deploy/.env.prod với secret ngẫu nhiên
sudo nano deploy/.env.prod        # điền AI2_LLM_BASE_URL / AI2_LLM_API_KEY (Lead chốt provider)
sudo nano ai-service/.env         # MISTRAL_API_KEY cho AI1
sudo deploy/deploy.sh
```

`deploy.sh` làm các bước sau:

1. Build image.
2. `up -d`.
3. Chờ backend healthy. Backend tự chạy `alembic upgrade head`.
4. Chạy `keycloak_configure.py`:
   - Thêm `FRONTEND_ORIGINS` vào redirect/web origins.
   - Đổi secret của client backend.
   - **Đổi mật khẩu 3 tài khoản demo** (mật khẩu trong `realm-export.json` là công khai).
   - Cấu hình SMTP nếu có.
   - Bật chống dò mật khẩu: khoá tạm tài khoản sau 5 lần sai, tối đa 15 phút.
5. Smoke test: `/health`, issuer OIDC, `/admin` bị chặn, cổng 8002 đóng.

Cuối cùng script in sẵn các biến `VITE_*` cho frontend.

## Cập nhật

```bash
cd /opt/contract-intelligence && sudo deploy/deploy.sh --pull
```

## Frontend dùng API online

```env
VITE_API_BASE_URL=https://api-<ip>.sslip.io
VITE_KEYCLOAK_URL=https://auth-<ip>.sslip.io
VITE_KEYCLOAK_REALM=contract-intelligence
VITE_KEYCLOAK_CLIENT_ID=contract-intel-frontend
```

`http://localhost:5173` đã được cho phép sẵn, nên frontend chạy trên máy dev gọi thẳng server được. Khi frontend có địa chỉ online, làm như sau:

1. Thêm địa chỉ đó vào `FRONTEND_ORIGINS` trong `deploy/.env.prod`.
2. Đặt `FRONTEND_BASE_URL` cho link trong email.
3. Chạy lại `deploy.sh`.

## Việc vận hành

| Việc | Lệnh |
|---|---|
| Trạng thái | `docker compose -f docker-compose.yml -f deploy/compose.prod.yml --env-file deploy/.env.prod ps` |
| Log backend / worker | `... logs -f backend backend-worker` |
| Keycloak admin | Trên server lấy IP container: `docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' ci-keycloak`. Trên máy mình: `ssh -L 8080:<IP đó>:8080 <user>@<ip>`, rồi mở `http://localhost:8080/admin` (user `admin`, mật khẩu `KEYCLOAK_ADMIN_PASSWORD`) |
| Đọc email (mailpit) | Như trên với `ci-mailpit` và cổng `8025`, rồi mở `http://localhost:8025` |
| Backup | `sudo deploy/backup.sh` (2 DB + MinIO vào `/var/backups/contract-intelligence`, giữ 7 ngày). Cron: `0 2 * * * /opt/contract-intelligence/deploy/backup.sh >> /var/log/ci-backup.log 2>&1` |
| Khôi phục DB backend | `docker exec -i ci-backend-db pg_restore -U ci -d contract_intelligence --clean < backend.dump` |

Mật khẩu admin Keycloak, mật khẩu tài khoản demo và mọi secret nằm trong `deploy/.env.prod` trên server (quyền 600, không commit). Gửi mật khẩu demo cho nhóm qua kênh riêng.

## Giới hạn đã biết

- **Kafka không lưu ra volume.** Mất message đang bay khi restart. Watchdog AI1 sẽ fail run bị ảnh hưởng với `AI1_TIMEOUT`, người dùng bấm chạy lại OCR.
- **Một kết quả OCR gửi thẳng qua Kafka chỉ chứa được khoảng 144 trang** (khoảng 71 KiB/trang, trần 10 MiB), cho tới khi kết quả OCR đi qua MinIO + URI (DOC-11 §4.2 #2).
- **Chưa có giám sát hay cảnh báo.** Cần theo dõi `docker compose ps` và log.
