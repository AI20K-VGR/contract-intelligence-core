# 12 · Danh sách tài khoản (Credentials List)

| Thuộc tính | Nội dung |
|---|---|
| Người phụ trách | Chương (BE) |
| Phối hợp | Trang (Lead) |
| Cập nhật | 19/10/2026 |

> **Tài liệu này không chứa mật khẩu, khoá hay token nào, và không bao giờ được thêm vào.** Repo có nhiều người đọc, và lịch sử Git không xoá được.
>
> Tài liệu chỉ ghi: tài khoản nào tồn tại, dùng làm gì, **bí mật nằm ở đâu**, ai giữ, và đổi thế nào. Khi bàn giao, người giữ chuyển bí mật cho người nhận **qua kênh riêng** (trình quản lý mật khẩu của nhóm, hoặc gặp trực tiếp), rồi cập nhật cột "Người giữ" ở đây bằng PR.
>
> Các ô **"Cần xác nhận"** là chỗ chưa rõ người giữ: Lead điền khi chốt biên bản bàn giao (tài liệu 14).

## 1. Hạ tầng và dịch vụ ngoài

| Hệ thống | Tài khoản / định danh | Dùng để | Bí mật nằm ở | Người giữ |
|---|---|---|---|---|
| AWS | Account `706421610602`, đăng nhập bằng role `AccountFullAccessRole` (account nằm trong Organization của bên cấp) | Chạy `ci-app`, `ci-db`, `ci-staging` | Phiên đăng nhập AWS (`aws login --region ap-southeast-2`) | Chương (vận hành); chủ Organization: **Cần xác nhận** |
| AWS IAM | User `ci-github-deploy` (inline policy `ssh-window-on-ci-app`: chỉ mở và đóng cổng 22 trên security group của `ci-app`, `ci-staging`) | GitHub Actions mở SSH lúc deploy | Secret GitHub `AWS_DEPLOY_ACCESS_KEY_ID`, `AWS_DEPLOY_SECRET_ACCESS_KEY` | Admin repo |
| SSH server | User `ubuntu`, key pair AWS `ci-deploy` | SSH vào `ci-app`, `ci-staging`; `ci-db` qua `ci-app` | File `ci-deploy-aws.pem` trên máy người vận hành | Chương |
| SSH cho GitHub Actions | Khoá riêng cho runner | Workflow `deploy` | Secret `DEPLOY_SSH_KEY`, `STAGING_DEPLOY_SSH_KEY` | Admin repo |
| Cloudflare | Tài khoản sở hữu zone `contract-intelligence.tech` (gói Free) | DNS, proxy, WAF, chứng chỉ origin | Tài khoản Cloudflare; API token của zone (token cũ hết hạn 17/10/2026) | Chương (Lead chốt 14/10/2026) |
| Nhà đăng ký tên miền | Tài khoản sở hữu `contract-intelligence.tech` | Gia hạn tên miền, thêm bản ghi DS cho DNSSEC (**chưa thêm**) | Tài khoản nhà đăng ký | Chương (Lead chốt 14/10/2026) |
| Chứng chỉ origin | Cloudflare Origin Certificate (hạn 10/2041); CA riêng cho Authenticated Origin Pulls | TLS giữa Cloudflare và server | `deploy/certs/` trên server (quyền 600); khoá của CA AOP **không** để trên server | Chương |
| GitHub | Repo `AI20K-VGR/contract-intelligence-core`; environment `production`, `staging` | Mã nguồn, CI/CD | Secret của repo (mục 4) | Admin repo: **Cần xác nhận** |
| Supabase Storage | Bucket backup + S3 access key | Bản backup mã hoá ngoài máy | `BACKUP_S3_ACCESS_KEY_ID`, `BACKUP_S3_SECRET_ACCESS_KEY` trong `deploy/.env.prod` | Chương (Lead chốt 14/10/2026) |
| SMTP | Tài khoản gửi thư (nếu dùng) | Thư mời, đặt lại mật khẩu, thông báo chia sẻ | `SMTP_*` trong `deploy/.env.prod` | **Cần xác nhận** |
| Langfuse (tuỳ chọn) | Project AI2 | Vết gọi LLM của AI2 | `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` | Văn Dũng |

## 2. Khoá AI

| Khoá | Dùng cho | Nằm ở | Người giữ | Ghi chú |
|---|---|---|---|---|
| OpenAI production | AI2: LLM, embedding, phân loại cặp điều khoản (`AI2_LLM_API_KEY`, `AI2_EMBEDDING_API_KEY`, `AI2_CONTRACT_GRAPH_PAIRS_API_KEY`); AI1 (`OPENAI_API_KEY`) | `deploy/.env.prod`, `ai-service/.env` trên `ci-app` | **Cần xác nhận** (khoá mới cấp ngày 18/10/2026, Lead và AI2 đồng ý) | Có trần chi tiêu tháng. Hết tiền thì deploy dừng ở preflight AI2 |
| Mistral | OCR của AI1 (`MISTRAL_API_KEY`) | `ai-service/.env` trên `ci-app` | Đức Dũng: **Cần xác nhận** | |
| OpenAI staging | AI2 trên staging | `deploy/.env.prod` trên `ci-staging` | Văn Dũng (Lead chốt 16/10/2026) | Hạn mức thấp, riêng với production |

## 3. Tài khoản trong hệ thống (production)

Mọi mật khẩu dưới đây được `deploy/bootstrap.sh` **sinh ngẫu nhiên** khi dựng server, và nằm trong `deploy/.env.prod` trên `ci-app` (quyền 600, người đọc được là người có `sudo` trên server).

| Hệ thống | Tài khoản | Dùng để | Biến trong `deploy/.env.prod` |
|---|---|---|---|
| Keycloak (realm `master`) | `admin` | Quản trị Keycloak qua SSH tunnel ([11](11-admin-guide.md) §6) | `KEYCLOAK_ADMIN_PASSWORD` |
| Keycloak (realm `contract-intelligence`) | `admin@ci.local` (Quản trị), `operator@ci.local` (Vận hành), `reviewer@ci.local` (Thẩm định) | Tài khoản demo; `keycloak_configure.py` đặt lại mật khẩu mỗi lần deploy | `DEMO_ADMIN_PASSWORD`, `DEMO_OPERATOR_PASSWORD`, `DEMO_REVIEWER_PASSWORD` |
| Keycloak client | `contract-intel-backend` (service account) | Backend gọi Keycloak Admin API (tạo user, khoá, đọc sự kiện đăng nhập) | `BACKEND_KEYCLOAK_ADMIN_SECRET` |
| Keycloak webhook | | Keycloak báo sự kiện người dùng cho backend | `KEYCLOAK_WEBHOOK_SECRET` |
| PostgreSQL backend (`ci-db:5432`) | `ci` | Backend | `BACKEND_DB_PASSWORD` |
| | `ai2` | AI2, chỉ có quyền trên schema `ai2` | `AI2_DB_PASSWORD` |
| PostgreSQL Keycloak (`ci-db:5433`) | `keycloak` | Keycloak | `KEYCLOAK_DB_PASSWORD` |
| MinIO | root user | Backend, AI1 đọc ghi file | `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` |
| Backend ↔ AI2 | | Ký HMAC mỗi request ([03](03-tai-lieu-api.md) §7) | `AI2_SERVICE_HMAC_SECRET` |
| Grafana | `admin` | Grafana nội bộ (người dùng vào qua app, không dùng tài khoản này) | `GRAFANA_ADMIN_PASSWORD` |
| Cookie giám sát | | Ký cookie phiên `/grafana` | `MONITORING_SESSION_SECRET` |
| Backup | | Mã hoá bản backup ngoài máy | `BACKUP_ENCRYPTION_PASSPHRASE`: **phải có bản lưu ngoài server**, người giữ: Chương (Lead chốt 14/10/2026) |

Tài khoản người dùng thật do Quản trị tạo trong app ([11](11-admin-guide.md) §1); mỗi người tự đặt mật khẩu qua email mời.

**Gửi mật khẩu demo cho thành viên:** qua kênh riêng. Mật khẩu demo trong `keycloak/realm-export.json` là **công khai** (nằm trong repo) và **không dùng được trên production**, vì `keycloak_configure.py` đã thay chúng.

## 4. Secret của GitHub

Đặt ở *Settings → Secrets and variables → Actions*. Cần quyền admin repo; giá trị không đọc lại được, chỉ ghi đè.

| Secret | Dùng cho |
|---|---|
| `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, `DEPLOY_KNOWN_HOSTS` | Deploy production (SSH vào `ci-app`) |
| `STAGING_DEPLOY_HOST`, `STAGING_DEPLOY_USER`, `STAGING_DEPLOY_SSH_KEY`, `STAGING_DEPLOY_KNOWN_HOSTS` | Deploy staging |
| `AWS_DEPLOY_ACCESS_KEY_ID`, `AWS_DEPLOY_SECRET_ACCESS_KEY` | IAM user `ci-github-deploy` |

Biến (không bí mật): xem [07](07-huong-dan-deploy.md) §7.

## 5. Môi trường local (không phải bí mật)

`docker compose up` trên máy dev dùng giá trị **cố định trong repo**:
- tài khoản `admin@ci.local`, `operator@ci.local`, `reviewer@ci.local`, mật khẩu ở `keycloak/realm-export.json`;
- Keycloak admin `admin`, mật khẩu `admin` (biến `KEYCLOAK_ADMIN_PASSWORD`);
- MinIO `admin` / `password123`; database user `ci`;
- secret dev trong `docker-compose.yml` và `backend/.env.example`.

Các giá trị này **chỉ dùng ở local**. Ở staging và production, backend **từ chối khởi động** nếu một trong các secret của nó còn là giá trị dev:
- các secret được kiểm: mật khẩu database, MinIO, secret client Keycloak, webhook, HMAC AI2, cookie giám sát;
- giá trị dev là: `password123`, `changeme`, `generate`, `secret`, hoặc kết thúc bằng `_dev` (`settings.py: _refuse_dev_secrets_outside_dev`).

Mật khẩu admin Keycloak và tài khoản demo không nằm trong phần kiểm này: `bootstrap.sh` sinh ngẫu nhiên, và `keycloak_configure.py` đặt lại mật khẩu demo.

Khoá AI cho local thì mỗi người tự điền vào `ai-service/.env` (bị Git bỏ qua).

## 6. Quy định bảo mật

1. **Không** commit, dán vào chat, issue, PR, comment hay lệnh terminal bất kỳ mật khẩu, khoá, token nào. Sửa file bí mật bằng editor trên chính máy chứa nó.
2. **Mỗi môi trường một bộ bí mật riêng.** Không dùng lại mật khẩu production cho staging hay local, và ngược lại.
3. **Trước khi sửa `deploy/.env.prod`**, sao lưu vào `/root/ci-env-backups/` (không để trong thư mục repo, vì deploy sẽ từ chối).
4. **Quyền tối thiểu:**
   - `ai2` chỉ có schema `ai2`;
   - `ci-github-deploy` chỉ mở và đóng được cổng 22;
   - SSH chỉ mở cho IP người vận hành;
   - trang quản trị Keycloak chỉ vào được qua SSH tunnel.
5. **Khi một người rời nhóm:**
   - khoá tài khoản của họ trong app (mọi phiên kết thúc ngay);
   - gỡ quyền repo và quyền AWS;
   - đổi mọi bí mật họ từng giữ (mục 7).
6. **Nghi lộ một bí mật:** đổi **ngay**, rồi mới điều tra. Ghi lại ngày đổi trong PR cập nhật tài liệu này.

## 7. Đổi (xoay vòng) bí mật

| Bí mật | Cách đổi | Ảnh hưởng |
|---|---|---|
| Mật khẩu demo, `BACKEND_KEYCLOAK_ADMIN_SECRET` | Sửa `deploy/.env.prod`, chạy `sudo deploy/deploy.sh`: `keycloak_configure.py` áp giá trị mới | Người đang đăng nhập không bị ảnh hưởng |
| `KEYCLOAK_ADMIN_PASSWORD` | Đổi trong Keycloak admin (realm `master`) **và** trong `deploy/.env.prod` cùng lúc | `deploy.sh` dùng mật khẩu này để cấu hình Keycloak |
| Mật khẩu database (`BACKEND_DB_PASSWORD`, `KEYCLOAK_DB_PASSWORD`) | `ALTER ROLE … PASSWORD` trên `ci-db`, sửa `deploy/.env.prod`, deploy lại | Dịch vụ dùng database đó restart vài giây |
| `AI2_DB_PASSWORD` | Sửa `deploy/.env.prod`, deploy lại: backend tự đặt lại mật khẩu của role `ai2` khi khởi động | AI2 restart |
| `AI2_SERVICE_HMAC_SECRET`, `KEYCLOAK_WEBHOOK_SECRET`, `MONITORING_SESSION_SECRET` | `openssl rand -hex 32`, sửa `deploy/.env.prod`, deploy lại | Phiên giám sát Grafana đang mở phải mở lại |
| Khoá LLM, OCR | Tạo khoá mới ở nhà cung cấp, thay trong `deploy/.env.prod`/`ai-service/.env`, deploy lại, **rồi** thu hồi khoá cũ | Preflight AI2 kiểm khoá mới trước khi restart |
| Khoá SSH `ci-deploy` | Tạo key pair mới, thêm vào `~/.ssh/authorized_keys` trên các server, cập nhật secret GitHub, rồi gỡ khoá cũ | |
| Khoá IAM `ci-github-deploy` | Tạo access key mới, cập nhật hai secret GitHub, xoá key cũ | |
| `BACKUP_ENCRYPTION_PASSPHRASE` | Đổi trong `deploy/.env.prod` **và** nơi lưu ngoài server | Bản backup cũ vẫn cần passphrase cũ: giữ passphrase cũ tới khi các bản đó hết hạn (7 ngày) |
