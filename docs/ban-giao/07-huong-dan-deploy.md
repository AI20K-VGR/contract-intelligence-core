# 07 · Hướng dẫn Deploy lên Server (Deployment Guide)

| Thuộc tính | Nội dung |
|---|---|
| Người phụ trách | Chương (BE) |
| Phối hợp | Đức Dũng (AI1) |
| Cập nhật | 19/10/2026 |
| Tài liệu chi tiết | `deploy/README.md` (từng lệnh, các tình huống đặc biệt), `docs/DOC-12-ke-hoach-deploy-backend.md` (kế hoạch, rủi ro), `docs/DOC-15-cicd-github-actions.md` (CI/CD) |

Tài liệu này cho người tiếp quản biết hệ thống đang chạy ở đâu, mỗi lần merge thì deploy diễn ra thế nào, và cách tự deploy, kiểm tra hay quay lại bản cũ. Các lệnh chi tiết hơn và các tình huống ít gặp nằm trong `deploy/README.md`; tài liệu này dẫn tới đúng mục ở đó.

## 1. Hệ thống production

```text
Người dùng ──HTTPS──▶ Cloudflare (gói Free, WAF, proxy)
                           │  chỉ Cloudflare vào được cổng 80/443
                           ▼
          ci-app  (AWS EC2 m7i-flex.large, Sydney, Elastic IP 52.63.103.239)
          ┌─────────────────────────────────────────────────────────────┐
          │ Caddy (TLS, reverse proxy)                                  │
          │   contract-intelligence.tech      → frontend, /api/* → backend
          │   api.contract-intelligence.tech  → backend                 │
          │   auth.contract-intelligence.tech → Keycloak                │
          │ backend, backend-worker, ai1-worker, ai2-service, Keycloak, │
          │ Kafka, MinIO, Prometheus, Grafana (mạng Docker nội bộ)      │
          └─────────────────────────────────────────────────────────────┘
                           │ IP nội bộ, chỉ từ ci-app
                           ▼
          ci-db   (AWS EC2 t4g.small): PostgreSQL backend :5432, Keycloak :5433
```

| Thành phần | Giá trị |
|---|---|
| Tên miền | `contract-intelligence.tech` (app), `api.` (API), `auth.` (Keycloak), DNS ở Cloudflare, cả ba **Proxied** |
| Tài khoản AWS | `706421610602`, chỉ dùng vùng `ap-southeast-2` (Sydney), gói Free |
| `ci-app` | `i-0ba58095660bd8aa1`, security group `sg-070e3d258f1793c3e` |
| `ci-db` | `i-064e05b6e1fff946f`, IP nội bộ `172.31.17.169`, security group `sg-0130139f71d6e1e71`; SSH chỉ qua `ci-app` |
| Staging (`ci-staging`) | `i-0ff88ddd45b1dc39b`, Elastic IP `13.236.32.157`, `https://app-13-236-32-157.sslip.io`; **bình thường tắt** (mục 6) |
| Thư mục trên server | `/opt/contract-intelligence` (bản clone của repo, chạy bằng `sudo`) |
| Cấu hình bí mật | `deploy/.env.prod` và `ai-service/.env` trên server, quyền 600, không có trong repo |
| SSH | user `ubuntu`, khoá `ci-deploy` (`~/.ssh/ci-deploy-aws.pem` trên máy người vận hành; xem [12](12-danh-sach-tai-khoan.md)) |

**Những gì không ra Internet:**
- Cổng 8002 của AI2, PostgreSQL, Kafka, MinIO, Keycloak admin, Mailpit và giám sát chỉ nằm trong mạng Docker hoặc mạng nội bộ AWS.
- Security group `ci-app` chỉ mở 80/443 cho dải IP của Cloudflare (prefix list `pl-0bb37c6203e631aff`), và 22 cho IP người vận hành.

## 2. Deploy thường ngày: merge là deploy

Mọi thay đổi lên production đi qua PR vào `develop`:
- **Ruleset của `develop`:** 2 approval (có code owner), resolve hết review thread, `pr-guard` xanh.
- **Merge vào `develop` là deploy production**, qua workflow `deploy`.
- Thay đổi hạ tầng sống (Cloudflare, security group, cấu hình server) cũng mở PR và chờ duyệt rồi mới áp dụng (Lead chốt 14/10/2026).

```text
merge PR ──▶ GitHub Actions "deploy"
   1. preflight     kiểm cấu hình deploy, test deploy/tests
   2. staging       chỉ khi biến repo STAGING_ENABLED=true; lỗi thì dừng, production giữ bản cũ
   3. deploy        (deploy-target.yml, environment "production")
      - mở cổng 22 của ci-app cho đúng IP runner (IAM user ci-github-deploy)
      - SSH, fast-forward checkout tới đúng SHA vừa merge, chạy deploy/deploy.sh
      - kiểm từ bên ngoài: HTTPS, OIDC, /admin bị chặn, các cổng nội bộ đóng
      - đóng lại cổng 22
```

**`deploy/deploy.sh` trên server**, theo thứ tự log `[deploy] …`:

| Bước | Việc | Lỗi thì |
|---|---|---|
| 1 | So SHA của checkout với SHA được yêu cầu | Dừng |
| 2 | Kiểm hai database trên `ci-db` có trả lời | Dừng, **chưa restart gì** |
| 3 | Build image; chạy **preflight AI2** trên image mới (gọi thử LLM và embedding) | Dừng, stack cũ vẫn chạy |
| 4 | `docker compose up -d` (backend tự chạy `alembic upgrade head` khi khởi động) | |
| 5 | Caddy: file cấu hình mount đổi thì `caddy validate` rồi restart (#134) | Dừng, Caddy giữ cấu hình cũ |
| 6 | Prometheus: `prometheus.yml` đổi thì `promtool check config` rồi restart (#142) | Dừng, Prometheus giữ cấu hình cũ |
| 7 | Chờ backend healthy, Keycloak sẵn sàng, AI2 đủ khả năng (LLM, vector) | Báo lỗi |
| 8 | `keycloak_configure.py`: redirect URI, secret client backend, mật khẩu tài khoản demo, SMTP, chống dò mật khẩu, back-channel logout, tắt refresh token | |
| 9 | Smoke test trên server: `/health`, issuer OIDC, `/admin` 404, back-channel 404, `/grafana` 401, frontend 200, API trên domain app | In `WARNING` |

**Theo dõi một lần deploy:**

```bash
gh run list --workflow deploy.yml --limit 5
gh run watch <run-id>
gh run view <run-id> --log | grep -E "\[deploy\]|WARNING|ok$"
```

Một lần deploy thành công có các dòng `AI2 preflight: llm=ready embedding=READY`, `AI2 full capability: ready`, và mọi dòng smoke test kết thúc bằng `ok`.

## 3. Deploy bằng tay (khi cần)

Khi workflow không chạy được (ví dụ GitHub Actions lỗi), deploy trực tiếp trên server. Vẫn chỉ deploy code đã merge vào `develop`:

```bash
ssh -i ~/.ssh/ci-deploy-aws.pem ubuntu@52.63.103.239
cd /opt/contract-intelligence
sudo git fetch origin develop && sudo git checkout --detach origin/develop
sudo deploy/deploy.sh
```

**Lưu ý:**
- **Checkout trên server phải sạch.** Workflow từ chối deploy nếu `/opt/contract-intelligence` có file lạ hoặc file bị sửa ("deployment checkout has local changes"). Bản sao lưu cấu hình để ở `/root/ci-env-backups/`, **không** để trong thư mục repo.
- **Khi SSH bị timeout:** thường do IP nhà người vận hành đổi.
  1. Xem IP hiện tại: `curl -4 https://checkip.amazonaws.com`.
  2. Thêm rule SSH cho IP đó vào `sg-070e3d258f1793c3e`, xoá rule của IP cũ. Lệnh mẫu ở [11](11-admin-guide.md) §6.

## 4. Kiểm tra sau deploy

**Tự động:** bước cuối của workflow (`deploy/check_external.sh`) đã kiểm từ bên ngoài.

**Bằng tay:**
1. Mở https://contract-intelligence.tech và đăng nhập.
2. Tải một hồ sơ mẫu, xem OCR rồi AI2 chạy xong.
3. Thử hỏi đáp; mở **Quản trị → Giám sát hệ thống**.

**Kiểm từ máy dev:**

```bash
ORIGIN_IP=52.63.103.239 deploy/check_external.sh \
  api.contract-intelligence.tech auth.contract-intelligence.tech contract-intelligence.tech
```

**Nếu PR có đổi file cấu hình mount từng file** (`deploy/Caddyfile`, `deploy/frontend.caddy`, `infra/monitoring/prometheus/prometheus.yml`):
- Log deploy phải có dòng `… config changed` và `… restarted with the new config`.
- Nếu không có, container vẫn chạy cấu hình cũ: so sha256 file trên host với file trong container. Cách làm ở [11](11-admin-guide.md) §5.

## 5. Quay lại bản trước (rollback)

Ưu tiên **revert bằng PR**:
1. `git revert <commit hoặc merge>` trên một nhánh mới, mở PR vào `develop`, xin 2 approval, merge.
2. Workflow deploy lại như thường.

Ví dụ đã làm: #137 revert #135, khi image AI2 mới không khởi động được.

**Khẩn cấp, chưa kịp có PR:** checkout commit cũ trên server rồi chạy lại `deploy.sh`.

```bash
cd /opt/contract-intelligence
sudo git checkout --detach <sha cũ đã chạy tốt>
sudo deploy/deploy.sh
```

Sau đó vẫn phải mở PR revert, để `develop` khớp với server.

**Migration database không tự quay lại.**
- Bản mới đã chạy migration thêm bảng hoặc cột, thì bản cũ vẫn chạy được (bản cũ bỏ qua bảng, cột mới).
- Migration xoá hoặc đổi kiểu dữ liệu thì phải khôi phục từ backup ([11](11-admin-guide.md) §4). Vì vậy **luôn backup trước** khi merge một migration như vậy.

**Khi preflight AI2 lỗi** (khoá LLM hết tiền, model đổi): deploy dừng ở bước 3 và **không restart gì**, nên production vẫn chạy bản cũ. Sửa khoá hoặc model trong `deploy/.env.prod` rồi chạy lại workflow. Ví dụ ngày 18/10/2026: khoá OpenAI báo `credit_balance_exhausted`.

## 6. Staging

Staging là một máy riêng, dựng giống production, dùng để thử nhánh trước khi merge. Chi tiết: `deploy/README.md` §Staging.

| Việc | Lệnh hoặc thao tác |
|---|---|
| Bật máy | AWS Console → EC2 → `ci-staging` → Start, hoặc `aws ec2 start-instances --region ap-southeast-2 --instance-ids i-0ff88ddd45b1dc39b` |
| Thử một nhánh | `gh workflow run deploy.yml --ref <nhánh> -f target=staging` |
| Cho mỗi lần merge chạy staging trước production | Đặt biến repo `STAGING_ENABLED=true`, **chỉ sau khi** đã có một lần `-f target=staging` thành công |
| Tắt máy | **Đặt `STAGING_ENABLED=false` trước**, rồi mới Stop máy. Nếu không, mọi lần merge sẽ lỗi ở staging và production không được deploy |

**Dữ liệu trên staging:** chỉ hợp đồng mẫu đã ẩn thông tin, không chép dữ liệu production sang.

**Khoá LLM:** staging dùng khoá riêng, hạn mức thấp, do Văn Dũng giữ.

## 7. Dựng server mới từ đầu

Ví dụ khi đổi máy, đổi nhà cung cấp, hoặc dựng lại sau sự cố. Thứ tự và lệnh chi tiết theo `deploy/README.md`:

| Bước | Mục trong `deploy/README.md` |
|---|---|
| Tạo máy EC2, Elastic IP, security group | "Triển khai trên AWS EC2" |
| Dựng DB server riêng | "Tách DB ra máy riêng" |
| Clone repo, `deploy/bootstrap.sh` (cài Docker, firewall, swap, sinh `deploy/.env.prod` với secret ngẫu nhiên) | "Kế hoạch triển khai qua SSH", bước 1–2 |
| Điền khoá AI (`deploy/.env.prod`, `ai-service/.env`) | Bước 3 |
| `sudo deploy/deploy.sh`, kiểm từ ngoài, chạy thử luồng chính | Bước 4–6 |
| Đưa sau Cloudflare: Origin Certificate, chỉ nhận dải IP Cloudflare | "Đứng sau Cloudflare" |
| Chuyển dữ liệu từ máy cũ (backup, chép, khôi phục 2 DB + MinIO) | "Chuyển sang máy mới cùng dữ liệu" |
| Khai secret GitHub cho CI/CD | "Cài CI/CD (một lần)" |

**Secret và biến GitHub mà workflow cần** (Settings → Secrets and variables → Actions; cần quyền admin repo):

| Loại | Tên | Ghi chú |
|---|---|---|
| Secret | `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, `DEPLOY_KNOWN_HOSTS` | SSH vào `ci-app`. Xoá `DEPLOY_HOST` để tạm dừng deploy tự động |
| Secret | `AWS_DEPLOY_ACCESS_KEY_ID`, `AWS_DEPLOY_SECRET_ACCESS_KEY` | IAM user `ci-github-deploy`, chỉ được mở và đóng cổng 22 trên security group của `ci-app` và `ci-staging` |
| Secret | `STAGING_DEPLOY_HOST`, `STAGING_DEPLOY_USER`, `STAGING_DEPLOY_SSH_KEY`, `STAGING_DEPLOY_KNOWN_HOSTS` | Như trên, cho staging |
| Biến | `DEPLOY_SECURITY_GROUP_ID`, `DEPLOY_AWS_REGION`, `STAGING_SECURITY_GROUP_ID` | Security group để mở cổng 22 cho runner. Hiện tại: `sg-070e3d258f1793c3e`, `ap-southeast-2`, `sg-06f1c382fab7f8a53` |
| Biến | `DEPLOY_BEHIND_CLOUDFLARE` | `true`: bước kiểm từ ngoài gọi thẳng IP origin và kiểm origin từ chối người gọi không phải Cloudflare |
| Biến | `STAGING_ENABLED` | Mục 6. Hiện tại: `false` (từ 18/10/2026, staging đang tắt) |

## 8. Những lỗi đã gặp và bài học

| Ngày | Lỗi | Bài học |
|---|---|---|
| 15/10/2026 | AI2 bị OOM-kill với hồ sơ 202 trang (#113) | Trần RAM theo container trong `deploy/.env.prod` (`AI2_MEM_LIMIT=3584m`); theo dõi ở Grafana |
| 16/10/2026 | Preflight AI2 chặn mọi lần deploy vì model `gpt-5.5` chưa được probe đúng (#106, #110) | Preflight lỗi thì production giữ bản cũ; sửa rồi chạy lại |
| 18/10/2026 | Khoá OpenAI hết tiền, mọi lần deploy dừng ở preflight | Theo dõi hạn mức khoá LLM; người giữ khoá ở [12](12-danh-sach-tai-khoan.md) |
| 19/10/2026 | Image AI2 thiếu module AI1 (`contract_ocr`), deploy dừng ở preflight (#135, revert #137) | CI giờ dựng `Dockerfile.ai2` và import thử trong image (#139) |
| 19/10/2026 | Sửa `Caddyfile`, `prometheus.yml` mà container vẫn chạy bản cũ (mount từng file) | `deploy.sh` tự so sha256, kiểm cấu hình rồi restart (#134, #142) |
| 19/10/2026 | Upload qua Cloudflare bị cắt ở khoảng 125 giây (#145) | Gói Free không đổi được; tải theo khúc (`/uploads`, PR #149) |
