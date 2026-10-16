# Triển khai online — Linux + Docker Compose

H??ng d?n ch?y stack AI2 c?c b? n?m t?i [docs/AI2-LOCAL-SETUP.md](../docs/AI2-LOCAL-SETUP.md).

Chạy toàn bộ stack (Keycloak, Postgres ×2, Kafka, MinIO, backend, backend-worker, AI1, AI2, giám sát) trên một máy chủ cloud Linux, bằng chính `docker-compose.yml` của dự án cộng với `deploy/compose.prod.yml`. Caddy đứng trước, lo HTTPS. Frontend có thể chạy trên cùng máy (tuỳ chọn).

Hai Postgres có thể chạy trên một máy riêng (DB server): xem "Tách DB ra máy riêng". Trên AWS dùng cách này (mục "Triển khai trên AWS EC2").

Mọi thao tác làm qua SSH từ máy dev. Không cần công cụ của nhà cung cấp cloud nào.

## Cái gì ra Internet

| Địa chỉ | Tới | Dùng bởi |
|---|---|---|
| `https://app-<ip>.sslip.io` | frontend `:80` qua Caddy | Người dùng cuối |
| `https://api-<ip>.sslip.io` | backend `:8000` (REST, SSE `/api/v1/runs/{id}/events`, `/docs`; trên bản online `/docs` và `/openapi.json` bị chặn ở Cloudflare) | Frontend |
| `https://auth-<ip>.sslip.io` | Keycloak `:8080` (đăng nhập, OIDC). `/admin` trả 404 | Frontend, người dùng |
| `https://app-<ip>.sslip.io` | frontend (bản build tĩnh). Chỉ có khi `APP_HOST` được đặt trong `deploy/.env.prod` | Người dùng |
| `https://api-<ip>.sslip.io/grafana/` | Grafana qua backend. Chỉ ADMINISTRATOR; người lạ 401, user thường 403 | Trang `/admin/monitoring` |
| **Bản online:** `https://contract-intelligence.tech`, `https://api.contract-intelligence.tech`, `https://auth.contract-intelligence.tech` | Lần lượt frontend, backend, Keycloak, như ba dòng sslip.io ở trên. Đi qua Cloudflare tới app server AWS `52.63.103.239` (Sydney) | Người dùng, frontend |

Các dòng `sslip.io` ở trên là địa chỉ ví dụ của một máy chủ dựng thử. Bản online dùng tên miền thật ở dòng cuối.

Những thứ không ra Internet, chỉ nằm trong mạng `ci-network`:

- **AI1** nhận lệnh và trả kết quả qua Kafka.
- **Backend gọi AI2** qua `http://ai2-service:8002`. Cổng 8002 không mở ra ngoài, theo yêu cầu mentor.
- Postgres, Kafka, MinIO, mailpit và Keycloak admin.
- Grafana, Prometheus, Node Exporter, cAdvisor: nằm trong mạng nội bộ `ci-monitoring`, không có cổng. Xem [docs/MONITORING.md](../docs/MONITORING.md).

`sslip.io` phân giải `app-1-2-3-4.sslip.io`, `api-1-2-3-4.sslip.io` và
`auth-1-2-3-4.sslip.io` về `1.2.3.4`. Vì vậy không cần mua domain mà vẫn có
chứng chỉ Let's Encrypt thật.

Bản online (`contract-intelligence.tech`, AWS) đứng sau Cloudflare: cả ba tên miền đi qua proxy của Cloudflare, và máy chủ chỉ nhận kết nối web từ Cloudflare. Xem "Đứng sau Cloudflare".

## Máy chủ cần

- Ubuntu 22.04/24.04 (hoặc Debian 12), kiến trúc x86-64, có quyền `sudo`.
- Tối thiểu 4 vCPU, 8 GB RAM (khuyên dùng 16 GB), 60 GB đĩa. Stack local dùng khoảng 2,7 GB RAM khi nhàn rỗi (đo 04/10/2026); build image và OCR hồ sơ lớn cần thêm.
- Một IPv4 công khai **cố định**: tên miền `sslip.io` và chứng chỉ gắn với IP này.
- Cổng 80 và 443 mở từ Internet ở firewall của nhà cung cấp (security group). Cổng 22 mở cho người vận hành.

### Máy chủ ít RAM (4 GB)

Chạy được cho demo ít người dùng, chậm hơn và ít dư địa hơn. Làm ba việc trước khi chạy `deploy.sh`:

1. Swap tổng cộng 4 GB trở lên, để lúc build hoặc OCR vọt bộ nhớ thì máy chậm lại chứ tiến trình không bị giết. `bootstrap.sh` chỉ thêm swap khi máy chưa có swap nào; máy đã có sẵn swap nhỏ thì thêm tay:

   ```bash
   sudo fallocate -l 4G /swapfile2 && sudo chmod 600 /swapfile2 && sudo mkswap /swapfile2 && sudo swapon /swapfile2
   echo '/swapfile2 none swap sw 0 0' | sudo tee -a /etc/fstab
   ```

2. Trong `deploy/.env.prod`:

   ```env
   KAFKA_HEAP_OPTS="-Xmx256m -Xms256m"
   KEYCLOAK_HEAP_OPTS="-Xms128m -Xmx384m"
   ```

3. Trong `ai-service/.env`, giảm số trang OCR song song: `AI1_MAX_PAGES_IN_FLIGHT=2`.

Hồ sơ hàng trăm trang vẫn có thể đẩy máy vào swap. Máy 2 GB không đủ: stack dùng khoảng 2,7 GB ngay khi nhàn rỗi.

### Bộ nhớ

Đo trên bản online ngày 15/10/2026 (máy 8 GB, DB ở máy riêng): khi nhàn rỗi stack dùng khoảng 2,5 GB. Trước bản sửa này, AI2 giữ lại kết quả và bản ghi của mọi hồ sơ đã xử lý nên RAM chỉ tăng, không giảm: 142 MiB lúc khởi động, 1,3 GiB sau hai lượt xử lý ngày 14–15/10. AI1 cũng giữ snapshot OCR của mọi tài liệu. Đo lại AI2 với ba hồ sơ 202 trang liên tiếp: bản cũ 417 → 614 → 772 MiB, bản mới 230 → 288 → 281 MiB (đỉnh trong lúc xử lý khoảng 620 MiB).

Mỗi container có trần bộ nhớ (`mem_limit` trong `docker-compose.yml`). Trần là giới hạn trên, không phải phần RAM giữ trước, nên tổng các trần được phép lớn hơn RAM của máy: trên app server tổng là khoảng 10 GiB (11 GiB nếu chạy cả hai Postgres trên cùng máy) cho máy 8 GB. Các service không chạm trần cùng lúc; trần chỉ chặn một service chạy loạn. Container vượt trần thì dùng swap tới mức bằng trần, sau đó bị khởi động lại, thay vì kéo cả máy vào swap. Đổi trần trong `deploy/.env.prod`:

| Biến | Mặc định | Ghi chú |
|---|---|---|
| `AI2_MEM_LIMIT` | `2g` | Một hồ sơ 202 trang chạm đỉnh khoảng 620 MiB |
| `AI1_MEM_LIMIT` | `1536m` | 8 trang OCR song song (`AI1_MAX_PAGES_IN_FLIGHT`) |
| `BACKEND_MEM_LIMIT`, `BACKEND_WORKER_MEM_LIMIT` | `1g` | Upload giữ cả bộ hồ sơ (≤ 100 MB qua Cloudflare) trong RAM |
| `KEYCLOAK_MEM_LIMIT` / `KEYCLOAK_HEAP_OPTS` | `1g` / `-Xms256m -Xmx512m` | Không đặt heap thì Keycloak lấy tới 70% RAM |
| `KAFKA_MEM_LIMIT` / `KAFKA_HEAP_OPTS` | `1g` / `-Xmx512m -Xms128m` | `-Xms` bằng `-Xmx` giữ cả heap ngay từ đầu |
| `MINIO_MEM_LIMIT`, `PROMETHEUS_MEM_LIMIT` | `768m`, `512m` | |
| `CADDY_MEM_LIMIT` | `256m` | Giữ mọi kết nối TLS; công cụ quét mở hàng nghìn kết nối |

AI2 chạy mỗi lần một hồ sơ (`AI2_MAX_CONCURRENT_JOBS=1`), và backend-worker gửi sang AI2 đúng chừng ấy hồ sơ cùng lúc (`WORKER_AI2_MAX_CONCURRENCY` lấy cùng biến trong `docker-compose.yml`). Hồ sơ đến sau chờ ở backend, ở bước AI2 (S4) chưa bắt đầu; chỗ chờ này không có hạn và được giữ qua restart (run vẫn `EXTRACTED`). Nếu một job vẫn phải chờ ở AI2 (`QUEUED`, ví dụ khi chạy nhiều backend-worker), backend không tính thời gian đó vào hạn xử lý và chỉ cho chờ tối đa `AI2_MAX_QUEUE_WAIT_SECONDS` giây (mặc định 1800). Chỉ tăng `AI2_MAX_CONCURRENT_JOBS` khi máy còn dư RAM: mỗi job cộng thêm khoảng 500 MiB lúc đỉnh.

Theo dõi ở `/admin/monitoring` (Grafana, biểu đồ RAM theo container). Nếu một container cứ bị khởi động lại, kiểm tra bằng `docker inspect -f '{{.State.OOMKilled}}' ci-ai2-service` rồi tăng trần của nó.

Máy đã cài trước bản này có thể còn `KAFKA_HEAP_OPTS="-Xmx512m -Xms512m"` trong `deploy/.env.prod` (chép từ bản mẫu cũ). Để trống dòng đó để dùng mặc định mới.

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
- GitHub → Actions → `deploy-external-check` → nhập `api-…` và `auth-…`; hoặc
- trên máy dev: `deploy/check_external.sh api-<ip>.sslip.io auth-<ip>.sslip.io app-<ip>.sslip.io`.

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

## Tách DB ra máy riêng

Hai Postgres (`backend-db` có pgvector, `keycloak-db`) chạy trên một DB server bằng `deploy/compose.db.yml`: cùng image, user, database và tuỳ chọn initdb như stack một máy, nên dump của stack một máy khôi phục được nguyên vẹn. Mọi thứ khác vẫn ở app server.

| Máy | File | Env |
|---|---|---|
| DB server | `deploy/compose.db.yml` | `deploy/.env.db` (`bootstrap.sh --db` tạo) |
| App server | `docker-compose.yml` + `deploy/compose.prod.yml` + `deploy/compose.external-db.yml` | `deploy/.env.prod` có `BACKEND_DB_HOST`, `BACKEND_DB_PORT`, `KEYCLOAK_DB_HOST`, `KEYCLOAK_DB_PORT` |

- DB chỉ lắng nghe trên **IP nội bộ** của DB server (`DB_BIND_ADDR`): backend ở cổng 5432, Keycloak ở cổng 5433.
- Docker mở cổng vượt qua `ufw`, nên thứ chặn người lạ là **firewall của nhà cung cấp**: chỉ cho app server vào 5432–5433.
- Kết nối app → DB đi trong mạng nội bộ của nhà cung cấp, không mã hoá TLS.
- `deploy.sh` tự thêm `compose.external-db.yml` khi `BACKEND_DB_HOST` có giá trị. Trước khi `up -d`, nó kiểm tra hai DB có trả lời không: không trả lời thì dừng, stack đang chạy không bị đụng tới.
- `backup.sh` trên app server dump hai DB qua mạng. Không cần cài gì trên DB server.

### Dựng DB server

```bash
ssh <user>@<db-server>
sudo git clone https://github.com/AI20K-VGR/contract-intelligence-core.git /opt/contract-intelligence
cd /opt/contract-intelligence && sudo git checkout <nhánh>
sudo deploy/bootstrap.sh --db     # Docker, ufw chỉ SSH, swap, deploy/.env.db với IP nội bộ + mật khẩu ngẫu nhiên
sudo docker compose -f deploy/compose.db.yml --env-file deploy/.env.db up -d --wait
sudo cat deploy/.env.db           # chép DB_BIND_ADDR, 2 mật khẩu, 2 cổng sang app server
```

Kiểm tra `DB_BIND_ADDR` là IP **nội bộ** (AWS: `172.31.x.x` trong VPC mặc định), không phải IP công khai.

### App server dùng DB server

Làm Bước 1–3 của "Kế hoạch triển khai qua SSH", rồi sửa `deploy/.env.prod` trước Bước 4:

```env
BACKEND_DB_HOST=<DB_BIND_ADDR>
BACKEND_DB_PORT=5432
KEYCLOAK_DB_HOST=<DB_BIND_ADDR>
KEYCLOAK_DB_PORT=5433
BACKEND_DB_PASSWORD=<như deploy/.env.db>
KEYCLOAK_DB_PASSWORD=<như deploy/.env.db>
```

Sau đó `sudo deploy/deploy.sh` như thường. Kiểm tra từ bên ngoài thì thêm IP công khai của DB server làm tham số thứ tư: `deploy/check_external.sh api-… auth-… app-… <ip-công-khai-db>`. Workflow `deploy` làm việc này khi có secret `DEPLOY_DB_PUBLIC_IP`.

## Triển khai trên AWS EC2

Hai máy EC2 trong cùng VPC, theo mục "Tách DB ra máy riêng". Giá và điều kiện gói miễn phí thay đổi theo thời gian: kiểm tra trên trang Billing và AWS Pricing Calculator trước khi tạo máy.

Tài khoản của dự án (14/10/2026) có hai giới hạn:

- **Chỉ dùng được region Sydney (`ap-southeast-2`).** Policy của Organization chặn EC2 ở các region khác, kể cả Singapore.
- **Free plan chỉ cho chạy các loại máy Free Tier:** `t3.micro`, `t3.small`, `t4g.micro`, `t4g.small`, `t8i.micro`, `t8i.small`, `c7i-flex.large`, `m7i-flex.large`. Xem lại danh sách bằng `aws ec2 describe-instance-types --filters Name=free-tier-eligible,Values=true`.

### Tạo máy

| Mục | App server | DB server |
|---|---|---|
| AMI | Ubuntu Server 24.04 LTS, **x86-64** | Ubuntu Server 24.04 LTS, **Arm64** |
| Loại máy | `m7i-flex.large` (2 vCPU, 8 GB, ~$87/tháng ở Sydney) | `t4g.small` (2 vCPU, 2 GB, ~$15/tháng) |
| Đĩa gốc | 40 GB gp3 | 20 GB gp3 |
| Security group | `ci-app`: TCP 22 từ IP người vận hành; TCP 80, 443 và UDP 443 từ mọi nơi | `ci-db`: TCP 5432–5433 **chỉ từ security group `ci-app`**; TCP 22 chỉ từ `ci-app` |
| IP công khai | Elastic IP (bắt buộc, xem dưới) | IP tự cấp (chỉ để tải image; không cổng nào mở ra ngoài) |
| Key pair | Tạo mới, giữ file `.pem`. User SSH là `ubuntu` | Cùng key pair |

- Stack app chưa chạy trên ARM, nên app server dùng x86. Hai image Postgres có bản ARM, nên DB server dùng `t4g` cho rẻ.
- App server 8 GB không cần các chỉnh ở "Máy chủ ít RAM". `c7i-flex.large` (4 GB, ~$81/tháng) rẻ hơn ít mà phải chỉnh, nên không chọn. Khi `ai1-worker` chạy nhiều replica, đặt `AI1_WORKER_REPLICAS=1`.
- Dòng `t*`: đặt Credit specification là `standard`. `m7i-flex`/`c7i-flex` không dùng CPU credit.
- SSH vào DB server đi qua app server: `ssh -J ubuntu@<elastic-ip> ubuntu@<ip-nội-bộ-db>`.

Thứ tự: tạo hai security group, tạo DB server rồi app server, gắn Elastic IP cho app server, dựng DB server, rồi dựng app server.

### Gắn Elastic IP trước khi chạy `bootstrap.sh` trên app server

`bootstrap.sh` đọc IP công khai của máy và ghi vào `API_HOST`, `AUTH_HOST`, `APP_HOST` (`api-<ip>.sslip.io`, …) trong `deploy/.env.prod`. IP công khai mặc định của EC2 **đổi mỗi lần stop rồi start**; khi đó cả ba tên miền, chứng chỉ và cấu hình Keycloak đều sai.

1. EC2 → Elastic IPs → Allocate, rồi Associate với app server.
2. SSH bằng IP đó: `ssh -i <key>.pem ubuntu@<elastic-ip>`.
3. Sau đó mới làm Bước 1–6 ở trên.

Đã lỡ chạy `bootstrap.sh` trước khi gắn Elastic IP:

- **Chưa chạy `deploy.sh`:** xoá `deploy/.env.prod` rồi chạy lại `bootstrap.sh`.
- **Đã chạy `deploy.sh`:** không xoá file, vì mật khẩu trong đó đã nằm trong dữ liệu. Sửa tay `API_HOST`, `AUTH_HOST`, `APP_HOST`, `FRONTEND_ORIGINS` và `FRONTEND_BASE_URL` sang IP mới, rồi chạy lại `deploy.sh`.

IP nội bộ của DB server không đổi khi stop/start, nên `BACKEND_DB_HOST` vẫn đúng.

### Giữ chi phí thấp

- Đặt cảnh báo ngân sách (Billing → Budgets) ngay khi tạo tài khoản, ví dụ ở $50, $100, $150.
- Không dùng thì **stop** app server, đừng terminate: dữ liệu trên đĩa còn nguyên, chỉ còn trả tiền đĩa và Elastic IP. Start lại thì các container tự chạy (`restart: unless-stopped`) và địa chỉ không đổi. Stop cả DB server thì start nó **trước** app server.
- Dòng `t3`/`t4g`: đặt Credit specification là `standard`. Chế độ `unlimited` tính thêm tiền khi CPU chạy cao kéo dài (build, OCR hồ sơ lớn).
- Máy chạy bằng credits thì có ngày hết: bật "Backup ra ngoài máy" bên dưới trước khi có dữ liệu cần giữ.

### Khác với máy chủ thường

- **Thư:** EC2 chặn cổng 25 chiều ra theo mặc định. Đặt `SMTP_PORT=587` với nhà cung cấp SMTP, hoặc để mặc định (thư vào mailpit).
- **Đổi máy chủ:** địa chỉ `sslip.io` đổi theo IP. Gửi nhóm frontend các biến `VITE_*` mà `deploy.sh` in ra, và cập nhật secret của workflow deploy trên GitHub (mục "Cài CI/CD") sang máy mới.

## Chuyển sang máy mới cùng dữ liệu

Chuyển hồ sơ, người dùng và file từ server đang chạy sang cặp app server + DB server mới. Làm sau khi máy mới đã chạy thử được với địa chỉ `sslip.io`. Có downtime từ bước 3 tới bước 7, thường 15–30 phút; báo nhóm trước.

Trong các lệnh dưới, `COMPOSE` là lệnh compose của app server mới:

```bash
COMPOSE="docker compose -f docker-compose.yml -f deploy/compose.prod.yml -f deploy/compose.frontend.yml -f deploy/compose.external-db.yml --env-file deploy/.env.prod"
```

1. **Xoá dữ liệu chạy thử trên máy mới.** App server: `sudo $COMPOSE down -v`. DB server: `sudo docker compose -f deploy/compose.db.yml --env-file deploy/.env.db down -v && sudo docker compose -f deploy/compose.db.yml --env-file deploy/.env.db up -d --wait`.
2. **Dùng env của server cũ.** Chép `deploy/.env.prod` và `ai-service/.env` của server cũ sang app server mới (`chmod 600`). Trong `deploy/.env.prod`, thêm hoặc sửa 6 dòng DB như mục "App server dùng DB server". Giữ nguyên mọi dòng khác:
   - Mật khẩu admin Keycloak nằm trong dữ liệu Keycloak, và `deploy.sh` đăng nhập bằng `KEYCLOAK_ADMIN_PASSWORD`. Đổi giá trị này thì bước cấu hình Keycloak bị từ chối.
   - `API_HOST`, `AUTH_HOST`, `APP_HOST` giữ tên miền đang dùng.
3. **Dừng ghi trên server cũ rồi backup.**

   ```bash
   sudo docker compose -f docker-compose.yml -f deploy/compose.prod.yml -f deploy/compose.frontend.yml --env-file deploy/.env.prod \
     stop frontend backend backend-worker keycloak ai1-worker ai2-service
   sudo deploy/backup.sh     # in ra /var/backups/contract-intelligence/<thời điểm>
   ```

4. **Chép backup sang app server mới**, đi qua máy mình, không cần khoá SSH giữa hai server:

   ```bash
   ssh <user>@<server-cũ> "sudo tar -C /var/backups/contract-intelligence -cf - <thời điểm>" \
     | ssh ubuntu@<elastic-ip> "sudo mkdir -p /var/backups/contract-intelligence && sudo tar -C /var/backups/contract-intelligence -xf -"
   ```

5. **Khôi phục hai DB vào DB server**, chạy trên app server mới. Role `ai2` phải có trước, vì `pg_dump` không lưu role; backend đặt lại mật khẩu và quyền của nó khi khởi động.

   ```bash
   cd /opt/contract-intelligence
   B=/var/backups/contract-intelligence/<thời điểm>
   envval() { grep -E "^$1=" deploy/.env.prod | tail -1 | cut -d= -f2-; }
   pg() { sudo docker run --rm -i -e PGPASSWORD="$1" pgvector/pgvector:pg16 "${@:2}"; }
   pg "$(envval BACKEND_DB_PASSWORD)" psql -h "$(envval BACKEND_DB_HOST)" -p "$(envval BACKEND_DB_PORT)" -U ci -d contract_intelligence \
     -v ON_ERROR_STOP=1 -c "CREATE ROLE ai2 LOGIN"
   pg "$(envval BACKEND_DB_PASSWORD)" pg_restore -h "$(envval BACKEND_DB_HOST)" -p "$(envval BACKEND_DB_PORT)" -U ci \
     -d contract_intelligence --exit-on-error < "$B/backend.dump"
   pg "$(envval KEYCLOAK_DB_PASSWORD)" pg_restore -h "$(envval KEYCLOAK_DB_HOST)" -p "$(envval KEYCLOAK_DB_PORT)" -U keycloak \
     -d keycloak --exit-on-error < "$B/keycloak.dump"
   ```

6. **Trỏ tên miền sang máy mới.** Đổi bản ghi DNS của `API_HOST`, `AUTH_HOST`, `APP_HOST` sang Elastic IP mới, giữ nguyên cấu hình còn lại ở nhà cung cấp DNS. Chờ tới khi `dig +short <API_HOST>` trả về IP mới, hoặc IP của proxy nếu tên miền đi qua proxy.
7. **Chạy stack mới:** `sudo deploy/deploy.sh`. Caddy xin chứng chỉ cho tên miền; backend chạy migration còn thiếu (nếu có) và đặt mật khẩu role `ai2`.
8. **Khôi phục file MinIO**, rồi so số object với server cũ:

   ```bash
   sudo docker run --rm --user 0:0 --network ci-network -v "$B/minio:/backup:ro" \
     -e MC_HOST_dst="http://$(envval MINIO_ROOT_USER):$(envval MINIO_ROOT_PASSWORD)@minio:9000" \
     cgr.dev/chainguard/minio-client:latest mirror --overwrite /backup dst
   find "$B/minio" -type f | wc -l     # phải bằng số object sau lệnh dưới
   sudo docker run --rm --network ci-network \
     -e MC_HOST_dst="http://$(envval MINIO_ROOT_USER):$(envval MINIO_ROOT_PASSWORD)@minio:9000" \
     cgr.dev/chainguard/minio-client:latest ls --recursive dst | wc -l
   ```

9. **Kiểm tra:** chạy `deploy/check_external.sh` (kèm IP công khai của DB server) và Bước 6 "Chạy thử luồng chính". Mở một hồ sơ cũ: PDF gốc phải hiện, nghĩa là MinIO đã về đủ.
10. **Cập nhật CI/CD:** đổi secret `DEPLOY_HOST`, `DEPLOY_KNOWN_HOSTS`, thêm `DEPLOY_DB_PUBLIC_IP` (mục "Cài CI/CD").
11. **Giữ server cũ** (đã dừng app) khoảng một tuần rồi mới xoá. Có sự cố thì trỏ DNS về lại và `start` các service đã dừng.

## Đứng sau Cloudflare

Bản online từ 14/10/2026: DNS `contract-intelligence.tech` ở Cloudflare (gói Free), cả ba tên miền **Proxied**, và security group `ci-app` chỉ cho dải IP của Cloudflare vào cổng 80/443. Gọi thẳng IP máy chủ không còn tới được site, nên WAF, giới hạn tần suất và chống DDoS của Cloudflare không bị đi vòng.

**Lead chốt ngày 14/10/2026 (review #91):**

- **Đồng ý dùng proxy Cloudflare.** Cloudflare giải mã HTTPS ở giữa đường, nên PDF và dữ liệu API đi qua Cloudflare ở dạng đọc được. Điều này chấp nhận được vì bản online chỉ xử lý hợp đồng mẫu đã ẩn thông tin (DEC-BE-AI2-01 D6). Bản online nhận hợp đồng thật thì phải xem lại.
- **Người giữ:** Phạm Hoàng Chương giữ tài khoản Cloudflare của zone, API token của zone và quyền vào nhà đăng ký tên miền (cần để thêm bản ghi DS của DNSSEC). Đổi người giữ thì ghi lại ở đây, và người cũ bàn giao đủ cả ba.
- **Quy trình:** thay đổi trên bản online (Cloudflare, security group, cấu hình máy chủ) mở PR và chờ duyệt rồi mới áp dụng. Các thiết lập ở mục này được áp trước khi #91 được duyệt; Lead ghi nhận và yêu cầu từ nay làm theo thứ tự PR → duyệt → áp dụng.

### Cấu hình trên Cloudflare

| Mục | Giá trị | Vì sao |
|---|---|---|
| DNS | `@`, `api`, `auth` → Elastic IP, đều **Proxied** | Không tên nào lộ đường vào thẳng máy chủ |
| SSL/TLS | **Full (strict)**, Always Use HTTPS, TLS tối thiểu **1.2**, TLS 1.3 bật | Cloudflare chỉ nối tới máy chủ bằng chứng chỉ hợp lệ; bỏ TLS 1.0/1.1 |
| WAF managed | Cloudflare Managed Free Ruleset, DDoS L7 (có sẵn) | |
| WAF custom rule 1 | Chặn `auth.…/admin*` và `auth.…/realms/master*` | Admin Keycloak chỉ dùng qua SSH tunnel; backend và `keycloak_configure.py` gọi realm `master` qua mạng nội bộ |
| WAF custom rule 2 | Chặn đường dò: `/.env`, `/.git`, `/.aws`, `/.ssh`, `wp-admin`, `wp-login`, `xmlrpc`, `phpmyadmin`, `*.php` | Site không có các thứ này; chặn sớm để bớt rác ở log |
| WAF custom rule 3 | Chặn method `TRACE`, `TRACK` | |
| WAF custom rule 4 | Chặn `api.…/docs`, `/docs/*`, `/redoc`, `/openapi.json` | Không công khai cấu trúc API trên bản online. Cần xem thì chạy local, hoặc tạm tắt rule này trên Cloudflare |
| Rate limiting | POST `auth.…/login-actions/authenticate`: quá 5 lần / 10 giây / IP thì chặn 10 giây | Thêm một lớp trước cơ chế khoá tài khoản của Keycloak. Cloudflare đếm theo từng PoP nên không chính xác tuyệt đối |
| Cache Rule | `auth.…/resources/*`: Cloudflare giữ tối đa 10 phút (Edge TTL 600 giây) | Keycloak gửi `max-age` 30 ngày cho file theme, và đường dẫn `/resources/<tag>/` không đổi khi sửa theme. Ngày 14/10 Cloudflare đã giữ `login.css` cũ khoảng 29 giờ, nên nút con mắt ở trang đăng nhập không hiện. Phía trình duyệt, Caddy ghi đè thành `max-age=600`, vì Cloudflare chỉ kéo dài được chứ không rút ngắn được thời gian cache của trình duyệt |
| Browser Integrity Check | Bật | Chặn User-Agent đáng ngờ, ví dụ `Python-urllib`. Hệ thống không bị ảnh hưởng vì backend lấy JWKS qua `http://keycloak:8080` |
| DNSSEC | Bật trên Cloudflare, **chờ thêm bản ghi DS ở nhà đăng ký tên miền** | `contract-intelligence.tech. 3600 IN DS 2371 13 2 5F2D6EB7666C3643266B3B71E35783F9086210E4C8CF2BE040AFFBC177989CAD` |

Giới hạn của gói Free cần biết: **mỗi request tối đa 100 MB** (ghi trong DOC-05b `v2.0.1`, mục tải hồ sơ). Một lần tải hồ sơ cho phép tới 6 file × 50 MB, nên gửi chung quá 100 MB sẽ bị Cloudflare trả 413 trước khi tới máy chủ. Tải từng đợt nhỏ hơn, hoặc nâng gói.

Khi đang bị tấn công: Security → Settings → **Under Attack Mode** (mọi người vào đều qua một trang kiểm tra). Tắt lại khi hết.

### Máy chủ

- **Security group `ci-app`:** TCP 80 và 443 chỉ từ prefix list `cloudflare-ipv4` (`pl-0bb37c6203e631aff`, các dải ở https://api.cloudflare.com/client/v4/ips); không mở UDP 443 hay IPv6 vì Cloudflare nối tới máy chủ bằng TCP IPv4. TCP 22 chỉ từ IP người vận hành.
- **Chứng chỉ:** Cloudflare Origin Certificate cho `contract-intelligence.tech` và `*.contract-intelligence.tech`, hạn 10/2041, ở `deploy/certs/origin.pem` và `origin.key` trên máy chủ (quyền 600, không commit). Let's Encrypt không dùng được nữa vì máy chủ không nhận kết nối của họ. Khi hai file này có mặt, `deploy.sh` thêm `deploy/compose.cloudflare.yml`.
- **IP người dùng thật:** Caddy đọc `CF-Connecting-IP`, và chỉ tin header này khi kết nối đến từ dải IP Cloudflare (`compose.cloudflare.yml`). Backend và Keycloak nhận `X-Forwarded-For` là IP người dùng, không phải IP của Cloudflare.
- **Chỉ nhận lưu lượng mang chứng chỉ của zone này (Authenticated Origin Pulls cấp zone):** dải IP Cloudflare dùng chung cho mọi tài khoản Cloudflare, nên security group chỉ chứng minh request đi qua mạng Cloudflare, không chứng minh nó thuộc zone `contract-intelligence.tech`. Chứng chỉ AOP "global" của Cloudflare cũng dùng chung cho mọi tài khoản, nên **không** dùng nó. Thay vào đó máy chủ có CA riêng; Cloudflare chỉ có client certificate do CA này cấp vì ta tải nó lên **zone này**; Caddy chỉ tin CA này (`deploy/cloudflare-tls-aop.caddy`).

  Khi chưa có `deploy/certs/origin-pull-ca.pem`, `deploy.sh` không thêm `deploy/compose.cloudflare-aop.yml` và Caddy chạy TLS như cũ. Bật **đúng thứ tự**, ngược lại mọi site sập:
  1. Tạo CA và client certificate trên máy chủ (RSA 2048). Khoá của CA nằm ở `/root/ci-origin-pull-ca/`, **không** trong `deploy/certs/`: thư mục đó được mount vào container Caddy (đứng ra Internet), chiếm được Caddy thì đọc được khoá và tự ký chứng chỉ mà origin chấp nhận. Vào `deploy/certs/` chỉ có `origin-pull-ca.pem` (công khai). Khoá của client certificate chỉ dùng để tải lên Cloudflare:

     ```bash
     cd /opt/contract-intelligence
     sudo install -d -m 700 /root/ci-origin-pull-ca
     sudo openssl req -x509 -newkey rsa:2048 -nodes -sha256 -days 3650 \
       -subj "/CN=contract-intelligence origin-pull CA" \
       -keyout /root/ci-origin-pull-ca/origin-pull-ca.key -out /root/ci-origin-pull-ca/origin-pull-ca.pem
     sudo openssl req -newkey rsa:2048 -nodes -subj "/CN=cloudflare-origin-pull" \
       -keyout /root/ci-origin-pull-ca/client.key -out /root/ci-origin-pull-ca/client.csr
     printf 'basicConstraints=CA:FALSE\nkeyUsage=digitalSignature,keyEncipherment\nextendedKeyUsage=clientAuth\n' \
       | sudo tee /root/ci-origin-pull-ca/client.ext >/dev/null
     sudo openssl x509 -req -sha256 -days 730 -in /root/ci-origin-pull-ca/client.csr \
       -CA /root/ci-origin-pull-ca/origin-pull-ca.pem -CAkey /root/ci-origin-pull-ca/origin-pull-ca.key \
       -CAcreateserial -extfile /root/ci-origin-pull-ca/client.ext -out /root/ci-origin-pull-ca/client.pem
     sudo install -m 644 /root/ci-origin-pull-ca/origin-pull-ca.pem deploy/certs/origin-pull-ca.pem
     ```
  2. Cloudflare → SSL/TLS → Origin Server → Authenticated Origin Pulls → **Zone-level** → Upload certificate: dán `/root/ci-origin-pull-ca/client.pem` và `client.key`, rồi bật toggle **Zone-level**. Không bật toggle global. Xong thì `sudo shred -u /root/ci-origin-pull-ca/client.*`, và chuyển `origin-pull-ca.key` ra khỏi máy chủ (người giữ tài khoản Cloudflare giữ, rồi `sudo shred -u /root/ci-origin-pull-ca/origin-pull-ca.key`) để ai chiếm được máy chủ cũng không cấp được chứng chỉ mới.
  3. `sudo deploy/deploy.sh`: có CA nên Caddy chuyển sang `cloudflare-tls-aop.caddy`, vẫn `verify_if_given`. Kiểm: mở web, đăng nhập, xem một hồ sơ.
  4. `deploy/.env.prod`: `ORIGIN_CLIENT_AUTH=require_and_verify`, rồi `sudo deploy/deploy.sh`. Kiểm như bước 3; `deploy/check_external.sh` (hoặc bước kiểm tra trong workflow `deploy`) vẫn xanh. Site trả 525/526: Caddy đang đòi chứng chỉ mà Cloudflare chưa gửi, đặt lại `verify_if_given` và deploy.

  Xoay chứng chỉ (client certificate hạn 2 năm; Cloudflare báo trước 30 và 14 ngày): lấy khoá CA từ người giữ về `/root/ci-origin-pull-ca/` (không bao giờ vào `deploy/certs/`), cấp chứng chỉ mới như bước 1, tải lên zone-level, xoá lại khoá CA khỏi máy chủ, xoá chứng chỉ cũ trên Cloudflare. CA không đổi nên máy chủ không cần deploy lại. Đổi CA thì đặt `verify_if_given` trước, thay `origin-pull-ca.pem`, tải chứng chỉ mới, rồi mới `require_and_verify`.
  Gỡ: đặt lại `verify_if_given`, deploy, rồi mới tắt toggle Zone-level trên Cloudflare. Bỏ hẳn: xoá `deploy/certs/origin-pull-ca.pem` rồi deploy.
- **Header bảo mật của frontend** (`deploy/frontend.caddy`): `Content-Security-Policy` chỉ cho nạp script từ chính site, gọi tới API và Keycloak, nhúng iframe của API (`/grafana`) và Keycloak (làm mới token), font của Google; `frame-ancestors 'self'` và `X-Frame-Options: SAMEORIGIN` chống clickjacking; `Permissions-Policy` tắt camera, micro, vị trí, thanh toán. Thêm nguồn mới ở frontend (CDN, iframe khác) thì sửa CSP ở đây cùng lúc.
- **Realm `master`:** Caddy trả 404 cho `auth.…/realms/master*` (WAF rule 1 cũng chặn); `keycloak_configure.py` gọi realm này qua `http://keycloak:8080` nội bộ.
- **Redirect về localhost của client frontend:** `keycloak_configure.py` gỡ `http://localhost…` và `http://127.0.0.1…` khỏi redirect URI, web origin và post-logout của `contract-intel-frontend`, trừ khi `KEYCLOAK_KEEP_LOCAL_REDIRECTS=true`. CORS của API vẫn theo `FRONTEND_ORIGINS`.

Tạo lại Origin Certificate (ví dụ khi đổi máy chủ). Khoá riêng sinh trên máy chủ và không rời máy; chỉ gửi CSR lên Cloudflare:

```bash
sudo install -d -m 700 deploy/certs
sudo openssl ecparam -name prime256v1 -genkey -noout -out deploy/certs/origin.key
sudo openssl req -new -key deploy/certs/origin.key -subj "/CN=contract-intelligence.tech" \
  -addext "subjectAltName=DNS:contract-intelligence.tech,DNS:*.contract-intelligence.tech" > origin.csr
# Cloudflare → SSL/TLS → Origin Server → Create Certificate → "Use my private key and CSR",
# dán origin.csr, hạn 15 năm; lưu chứng chỉ vào deploy/certs/origin.pem, rồi sudo deploy/deploy.sh
```

Sửa theme Keycloak mà cần thấy ngay, không chờ 10 phút: Cloudflare → Caching → Configuration → Purge Cache → Custom Purge, dán URL của file (ví dụ `https://auth.contract-intelligence.tech/resources/839wz/login/lexis/css/login.css`; phần `839wz` lấy từ HTML trang đăng nhập). Gói Free không purge theo tiền tố được.

Cloudflare đổi dải IP (hiếm): cập nhật danh sách trong `deploy/compose.cloudflare.yml` và các entry của prefix list `cloudflare-ipv4` trên AWS cùng lúc.

### Kiểm tra từ bên ngoài

Tên miền giờ phân giải về Cloudflare, mà Cloudflare tự mở 8080, 8443 và vài cổng khác, nên dò cổng trên tên miền sẽ báo sai. Truyền IP máy chủ qua `ORIGIN_IP`:

```bash
ORIGIN_IP=52.63.103.239 deploy/check_external.sh api.contract-intelligence.tech auth.contract-intelligence.tech contract-intelligence.tech <ip-công-khai-db>
```

Script khi đó dò các cổng nội bộ trên máy chủ, và kiểm thêm rằng máy chủ **từ chối 80/443** với người gọi không phải Cloudflare. Workflow `deploy` làm việc này khi có repo variable `DEPLOY_BEHIND_CLOUDFLARE=true`; `deploy-external-check` có input `origin_ip`.

## Cập nhật

Tự động: workflow `deploy` (`.github/workflows/deploy.yml`) chạy sau mỗi lần merge vào `develop`, hoặc bấm tay ở GitHub → Actions → `deploy` → Run workflow. Khi đã bật staging (mục "Staging" bên dưới), mỗi lần merge chạy trên staging trước, rồi mới đến production. Nó SSH vào server, fast-forward checkout tới commit vừa merge, chạy `deploy/deploy.sh`, rồi chạy `deploy/check_external.sh` từ runner (tức từ bên ngoài server).

Bằng tay, trên server:

```bash
cd /opt/contract-intelligence && sudo deploy/deploy.sh --pull
```

### Cài CI/CD (một lần)

Server phải được chuẩn bị xong bước 1–3 ở trên trước. Sau đó tạo một khoá riêng cho GitHub Actions và khai bốn secret của repo (Settings → Secrets and variables → Actions):

```bash
ssh-keygen -t ed25519 -N "" -C github-actions-deploy -f ./deploy_key
ssh <user>@<ip> 'cat >> ~/.ssh/authorized_keys' < ./deploy_key.pub
ssh-keyscan -t ed25519 <ip>        # so với khoá máy chủ đã biết rồi mới dùng
```

| Secret | Giá trị |
|---|---|
| `DEPLOY_HOST` | IP hoặc tên máy chủ |
| `DEPLOY_USER` | User SSH (`root`, hoặc user có `sudo` không hỏi mật khẩu) |
| `DEPLOY_SSH_KEY` | Nội dung file `deploy_key` (khoá bí mật). Xoá file sau khi khai |
| `DEPLOY_KNOWN_HOSTS` | Dòng `ssh-keyscan` ở trên |

Chưa có `DEPLOY_HOST` thì workflow báo "not configured" và không làm gì. Muốn tạm dừng deploy tự động (ví dụ khi bảo trì server), xoá secret `DEPLOY_HOST`.

Workflow chỉ fast-forward: nếu checkout trên server có commit riêng thì deploy dừng lại, không ghi đè. Hai lần deploy không chạy chồng nhau; lần sau chờ lần trước xong.

### Duyệt trước khi deploy

Job `deploy` chạy trong GitHub Environment `production`. Khi environment này có người duyệt bắt buộc, mỗi lần merge vào `develop` chỉ tạo một lần chạy ở trạng thái "Waiting"; server không đổi cho tới khi người duyệt bấm **Review deployments → Approve** ở trang của lần chạy đó. Từ chối thì lần chạy bị huỷ. Lần chạy chờ quá 30 ngày tự hết hạn.

Luật duyệt nằm ở cấu hình repo, không nằm trong file workflow, và **chỉ tài khoản có quyền admin repo đặt được**:

- Giao diện: Settings → Environments → `production` → Required reviewers → thêm người duyệt (hiện là `Chuongpham2004`) → Save. Nên đặt thêm Deployment branches = `develop`.
- Hoặc bằng API (thay `<id>` bằng kết quả của `gh api users/<login> --jq .id`):

  ```bash
  gh api -X PUT repos/AI20K-VGR/contract-intelligence-core/environments/production --input - <<'JSON'
  {"wait_timer": 0, "prevent_self_review": false,
   "reviewers": [{"type": "User", "id": <id>}],
   "deployment_branch_policy": {"protected_branches": false, "custom_branch_policies": true}}
  JSON
  gh api -X POST repos/AI20K-VGR/contract-intelligence-core/environments/production/deployment-branch-policies -f name=develop
  ```

Chưa có luật này thì environment `production` chỉ là một cái tên: workflow chạy ngay như trước. Kiểm tra luật đã có chưa: `gh api repos/AI20K-VGR/contract-intelligence-core/environments/production --jq .protection_rules`.

Server cài trước 02/10/2026 (trước issue #52) cần làm thêm một lần trước lần cập nhật đầu tiên:

1. `sudo deploy/backup.sh`. Image `backend-db` đổi từ `postgres:16-alpine` sang `pgvector/pgvector:pg16`; cùng Postgres 16 và DB dùng `--locale=C` nên dữ liệu dùng tiếp được, nhưng vẫn nên có bản backup.
2. Thêm `AI2_DB_PASSWORD=$(openssl rand -hex 24)` vào `deploy/.env.prod`.

Mỗi lần khởi động, backend tạo hoặc cập nhật role `ai2` với mật khẩu này. Role chỉ sở hữu schema `ai2` (ADR-14), không có quyền trên bảng nghiệp vụ.

## Staging

Một máy riêng, dựng giống production, để thử bản mới **trước** khi nó lên production: thử một nhánh trước khi merge, và chặn lần deploy lên production khi bản mới không chạy được trên staging.

| | Production | Staging |
|---|---|---|
| Lúc deploy | Merge vào `develop`, hoặc bấm tay từ `develop` | Merge vào `develop` (chạy trước production), hoặc bấm tay từ **bất kỳ nhánh nào** |
| Máy | `ci-app` + DB server `ci-db` | Một máy, DB chạy ngay trên máy đó |
| Tên miền | Tên miền thật, sau Cloudflare | `*.sslip.io` theo Elastic IP (do `bootstrap.sh` tạo), không qua Cloudflare |
| Dữ liệu | Chỉ hợp đồng mẫu đã ẩn thông tin, không hồ sơ thật (Lead chốt; DEC-BE-AI2-01 D6, BE-AI2-PROCESSING-CONTRACT §6.2) | Cả nhóm được tải lên, nhưng chỉ hợp đồng mẫu đã ẩn thông tin. Không hồ sơ thật, **không chép dữ liệu production sang** (Lead chốt 16/10) |

### Luồng deploy

- **Merge vào `develop`**, khi biến repo `STAGING_ENABLED=true`: job `staging` chạy trước. Staging lỗi thì job `deploy` (production) **không chạy**, production giữ nguyên bản cũ. `STAGING_ENABLED` khác `true` thì bỏ qua staging, production deploy như trước.
- **Thử một nhánh trước khi merge**:

  ```bash
  gh workflow run deploy.yml --ref <nhánh> -f target=staging
  ```

  Chỉ deploy lên staging, không đụng production. Production vẫn chỉ deploy được từ `develop`.
- Bấm tay staging không bao giờ huỷ hay thay một lần deploy production đang chờ: mỗi loại lần chạy có nhóm `concurrency` riêng, và hai lần deploy lên cùng một máy chạy lần lượt nhờ khoá `~/.ci-deploy.lock` trên server (DOC-15, "Workflow `deploy`").
- Các bước của một lần deploy nằm trong `.github/workflows/deploy-target.yml`, dùng chung cho cả hai nơi. Staging đọc secret và biến tên `STAGING_*`, **không bao giờ dùng giá trị production thay thế**: thiếu một secret staging thì lần chạy báo lỗi, chứ không deploy nhầm vào máy production.

### Dựng máy staging (một lần)

Làm theo "Triển khai trên AWS EC2", với các điểm khác:

1. **Máy:** `m7i-flex.large` (Lead chốt 16/10), chỉ bật khi cần; Ubuntu 24.04 x86-64, đĩa 40 GB gp3, cùng key pair. Không cần DB server riêng: để trống `BACKEND_DB_HOST`/`KEYCLOAK_DB_HOST`, DB chạy trên chính máy này.
2. **Security group riêng `ci-staging`:** TCP 22 từ IP người vận hành; TCP 80, 443 và UDP 443 từ mọi nơi. Không dùng chung `ci-app`.
3. **Elastic IP**, gắn trước khi chạy `bootstrap.sh`.
4. Bước 1–6 ở "Kế hoạch triển khai qua SSH". `bootstrap.sh` tự tạo mật khẩu mới và tên miền `sslip.io`. Không dùng chung mật khẩu với production.
5. **Khoá LLM:** điền `AI2_LLM_*`/`AI2_EMBEDDING_*` giống production, nhưng bằng **key LLM riêng của staging**, do @vdungx giữ, có hard limit thấp riêng, không dùng chung trần 30 USD/tháng của production (Lead chốt 16/10). Key và hạn mức phải có trước lần deploy staging đầu tiên; không ghi key vào repo hay comment.

### Khai báo trên GitHub (một lần, cần quyền admin repo)

1. Settings → Environments → **New environment** `staging`. Không cần người duyệt.
2. Secret của staging (khai trong environment `staging` hoặc ở cấp repo):

   | Secret | Giá trị |
   |---|---|
   | `STAGING_DEPLOY_HOST` | Elastic IP của máy staging |
   | `STAGING_DEPLOY_USER` | `ubuntu` |
   | `STAGING_DEPLOY_SSH_KEY` | Khoá bí mật cho GitHub Actions (tạo như "Cài CI/CD"; nên dùng khoá riêng cho staging) |
   | `STAGING_DEPLOY_KNOWN_HOSTS` | Dòng `ssh-keyscan -t ed25519 <elastic-ip>`, đã so với khoá máy |

3. Biến:
   - `STAGING_SECURITY_GROUP_ID` = ID của `ci-staging`, để workflow mở và đóng cổng 22 cho runner. Thêm security group này vào inline policy `ssh-window-on-ci-app` của IAM user `ci-github-deploy` (hiện chỉ cho phép `ci-app`).
   - Không đặt `STAGING_BEHIND_CLOUDFLARE`: staging không qua Cloudflare.
   - Biến repo `STAGING_ENABLED=true`: bật bước staging trước production. Đặt **sau cùng**, khi đã thử `-f target=staging` thành công.

### Chi phí và tạm tắt

- `m7i-flex.large` chạy cả tháng khoảng $87 ở Sydney, trừ vào cùng khoản credit với production. Không dùng thì **stop** máy (dữ liệu và Elastic IP giữ nguyên).
- **Trước khi stop, đặt `STAGING_ENABLED=false`**. Nếu không, mọi lần merge đều lỗi ở staging và production không được deploy. Start lại máy rồi mới bật lại `true`.

### Khác với production cần nhớ

- Staging không qua Cloudflare nên **không có giới hạn 100 MB** khi tải lên. File trên 100 MB chạy được trên staging vẫn bị từ chối (413) trên production.
- Trước buổi demo, chạy đúng kịch bản demo trên staging, gồm cả hồ sơ lớn (ví dụ hợp đồng 200 trang), rồi mới merge.

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
| Backup | `sudo deploy/backup.sh` (2 DB + MinIO vào `/var/backups/contract-intelligence`, giữ 7 ngày; chép ra ngoài máy: xem "Backup ra ngoài máy" bên dưới). Cron: `0 2 * * * /opt/contract-intelligence/deploy/backup.sh >> /var/log/ci-backup.log 2>&1` |
| Khôi phục DB backend | Chạy stack trước để backend tạo extension `vector` và role `ai2` (`pg_dump` không lưu role), rồi `docker exec -i ci-backend-db pg_restore -U ci -d contract_intelligence --clean < backend.dump`. DB ở máy riêng: xem bước 5 của "Chuyển sang máy mới cùng dữ liệu" |

Mật khẩu admin Keycloak, mật khẩu tài khoản demo và mọi secret nằm trong `deploy/.env.prod` trên server (quyền 600, không commit). Gửi mật khẩu demo cho nhóm qua kênh riêng.

### Cột "Đăng nhập gần nhất": bật login events cho realm đang chạy

Trang Người dùng lấy `last_login_at` từ event `LOGIN` của Keycloak. `keycloak/realm-export.json` đã bật sẵn (`eventsEnabled: true`, `eventsExpiration: 2592000` = 30 ngày), nhưng Keycloak chỉ import file này khi realm **chưa tồn tại**. Realm đã chạy từ trước giữ cấu hình cũ của nó, và `deploy.sh` không sửa phần này. Realm chưa lưu event thì cột luôn trống.

Kiểm tra và bật trên realm đang chạy:

1. Mở Keycloak admin qua SSH tunnel (dòng "Keycloak admin" ở bảng trên), chọn realm `contract-intelligence`.
2. **Realm settings → Events → User events settings**: bật **Save events**, đặt **Expiration** 30 ngày. Danh sách event được lưu phải có `LOGIN`. Bấm **Save**.
3. **Clients → `contract-intel-backend` → Service accounts roles**: phải có role `view-events` của client `realm-management`. Thiếu thì backend nhận 403 khi đọc event.
4. Đăng nhập một tài khoản rồi mở trang Người dùng: cột phải có giá trị. Nếu vẫn trống, tìm dòng `keycloak.login_events.failed` trong log backend.

Chỉ các lần đăng nhập sau khi bật mới được ghi. Ai không đăng nhập quá 30 ngày thì cột trống.

### Backup ra ngoài máy (Supabase Storage)

Mặc định `deploy/backup.sh` chỉ lưu backup trên chính máy chủ; máy hỏng thì backup mất theo. Khi `BACKUP_S3_ENDPOINT` có giá trị trong `deploy/.env.prod`, mỗi lần chạy script còn làm thêm:

1. Gom backup của lần chạy đó (2 DB + MinIO) thành một file, mã hoá AES-256 bằng `BACKUP_ENCRYPTION_PASSPHRASE`.
2. Cắt thành các phần `BACKUP_PART_SIZE` (mặc định 45 MB) và đẩy lên `<bucket>/<thời điểm>/`, kèm file `SHA256SUMS`.
3. Xoá các bản trên bucket cũ hơn `BACKUP_REMOTE_KEEP_DAYS` ngày (mặc định bằng bản local, 7 ngày).

Đẩy lên lỗi thì script exit 1 và ghi `off-site copy FAILED` vào log; bản backup local vẫn còn nguyên. Lúc chạy, máy chủ cần thêm chỗ trống bằng dung lượng một bản backup cho file tạm.

Cấu hình một lần:

1. Trên Supabase: tạo một bucket **private** (ví dụ `ci-backups`), rồi tạo S3 access key trong phần cài đặt Storage.
2. Điền vào `deploy/.env.prod`:

   ```env
   BACKUP_S3_ENDPOINT=https://<project-ref>.supabase.co/storage/v1/s3
   BACKUP_S3_REGION=<vùng của project, ví dụ ap-southeast-1>
   BACKUP_S3_BUCKET=ci-backups
   BACKUP_S3_ACCESS_KEY_ID=...
   BACKUP_S3_SECRET_ACCESS_KEY=...
   BACKUP_ENCRYPTION_PASSPHRASE=<ít nhất 20 ký tự>
   ```

3. **Lưu `BACKUP_ENCRYPTION_PASSPHRASE` ở một nơi ngoài máy chủ** (trình quản lý mật khẩu của nhóm). Mất passphrase thì không đọc được backup; nếu chỉ để trên máy chủ thì nó mất cùng lúc với máy.

   **Người giữ (Lead chốt ngày 14/10/2026):** Phạm Hoàng Chương giữ `BACKUP_ENCRYPTION_PASSPHRASE` và S3 access key của Supabase, có lưu một bản ngoài server. Lead đồng ý gửi bản backup **đã mã hoá** lên Supabase. Đổi người giữ thì ghi lại ở đây, và người cũ bàn giao cả passphrase lẫn key.
4. Chạy thử `sudo deploy/backup.sh`, kiểm tra dòng `[backup] off-site: ...` và các file trên bucket.

Giới hạn cần biết: Supabase đặt trần dung lượng cho mỗi file (gói miễn phí 50 MB) và tổng dung lượng Storage (gói miễn phí 1 GB). Mỗi đêm là một bản đầy đủ, nên 7 bản có thể vượt 1 GB khi hồ sơ nhiều; khi đó giảm `BACKUP_REMOTE_KEEP_DAYS` hoặc nâng gói.

Khôi phục từ bucket: tải cả thư mục của một lần backup về, rồi:

```bash
sha256sum -c SHA256SUMS
export BACKUP_ENCRYPTION_PASSPHRASE='...'
cat backup.tar.enc.part-* \
  | openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass env:BACKUP_ENCRYPTION_PASSPHRASE \
  | tar -xf -
```

Kết quả là thư mục `<thời điểm>/` gồm `backend.dump`, `keycloak.dump` và `minio/`, giống bản backup local. Khôi phục DB theo dòng "Khôi phục DB backend" ở bảng trên.

## Giới hạn đã biết

- **Kafka không lưu ra volume.** Mất message đang bay khi restart: watchdog AI1 sẽ fail run bị ảnh hưởng với `AI1_TIMEOUT`, người dùng bấm chạy lại OCR. Offset cũng quay về 0 sau mỗi lần restart; mọi event backend gửi đều có `event_id`, nên worker không nhầm event mới với event đã xử lý trước khi restart.
- Kết quả OCR lớn đi qua MinIO (`result_ref`), không gửi thẳng qua Kafka. Đã chạy thử local hồ sơ 200 trang (kết quả 6 MB).
- **Có giám sát, chưa có cảnh báo.** Dashboard Grafana ở `/admin/monitoring` (docs/MONITORING.md). Chưa có Alertmanager, nên vẫn phải có người xem.
