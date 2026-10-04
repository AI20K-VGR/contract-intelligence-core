# Kịch bản triển khai toàn bộ dự án lên Azure (Pay-As-You-Go)

Đưa **cả dự án** lên một máy ảo Azure: frontend, backend, backend-worker, AI1, AI2, Keycloak, PostgreSQL ×2, Kafka, MinIO và bộ giám sát. Caddy đứng trước, tự xin chứng chỉ HTTPS.

Kịch bản dùng lại bộ `deploy/` sẵn có ([README.md](README.md)) và thêm hai phần:

- `deploy/azure/provision.sh`: tạo hạ tầng Azure bằng Azure CLI.
- `deploy/compose.frontend.yml`: build frontend và phục vụ nó trên cùng máy, bật khi `APP_HOST` có giá trị trong `deploy/.env.prod`.

> **Trạng thái kiểm chứng (04/10/2026).** Đã chạy trên máy dev: build image frontend, SPA fallback, cấu hình Caddy với ba host, và `docker compose config` của cả ba file compose. **Chưa chạy trên Azure thật**: `provision.sh` mới qua kiểm tra cú pháp, và chưa có lần `deploy.sh` nào trên VM Azure. Lần triển khai đầu tiên cần được coi là lần chạy thử.

## 1. Kiến trúc

```
Internet ──► NSG Azure (22 từ IP người vận hành; 80, 443 từ mọi nơi)
              │
              ▼
        VM Ubuntu 24.04 (IP tĩnh)
              │
            Caddy :80/:443 (Let's Encrypt)
              ├── https://app-<ip>.sslip.io  ──► frontend:80   (bản build tĩnh)
              ├── https://api-<ip>.sslip.io  ──► backend:8000  (REST, SSE, /grafana)
              └── https://auth-<ip>.sslip.io ──► keycloak:8080 (/admin trả 404)

        Chỉ trong mạng Docker ci-network, không có cổng ra ngoài:
        backend-worker, ai1-worker (Kafka), ai2-service (HTTP :8002),
        backend-db, keycloak-db, kafka, minio, grafana, prometheus
```

`sslip.io` phân giải `app-1-2-3-4.sslip.io` về `1.2.3.4`, nên không cần mua tên miền mà vẫn có chứng chỉ thật. IP phải là IP tĩnh; `provision.sh` tạo sẵn như vậy.

Luồng kỹ thuật không đổi so với bản local: AI1 nhận lệnh và trả kết quả qua Kafka, backend gọi AI2 qua HTTP nội bộ.

## 2. Chi phí

Subscription Pay-As-You-Go tính tiền theo tài nguyên đang tồn tại. Kịch bản tạo ba thứ có phí:

| Tài nguyên | Mặc định | Tính phí khi |
|---|---|---|
| Máy ảo | `Standard_B4ms` (4 vCPU, 16 GiB) | Máy đang chạy. `az vm deallocate` thì dừng tính |
| Đĩa hệ thống | 64 GB Standard SSD | Luôn tính, kể cả khi máy đã deallocate |
| IP công khai tĩnh | Standard | Luôn tính |

Các con số dưới đây là **ước lượng, chưa đối chiếu bảng giá Azure tại ngày viết**; xem giá thật ở [Azure Pricing Calculator](https://azure.microsoft.com/pricing/calculator/) theo vùng đã chọn: máy `B4ms` vào khoảng 0,17–0,21 USD/giờ (khoảng 120–150 USD/tháng nếu chạy liên tục), đĩa và IP cộng lại dưới 10 USD/tháng.

Chi phí ngoài Azure: OCR (Mistral, OpenAI) của AI1 và LLM của AI2 tính theo lượng dùng trên tài khoản của key tương ứng.

Cách giảm chi phí:

- Chỉ bật máy khi demo: `az vm deallocate` sau buổi demo, `az vm start` trước buổi sau. IP giữ nguyên, container tự chạy lại (`restart: unless-stopped`).
- Tự tắt hằng ngày: đặt `AZ_AUTO_SHUTDOWN_UTC=1500` (22:00 giờ Việt Nam) khi chạy `provision.sh`.
- Đặt ngân sách và cảnh báo trong Azure Portal → Cost Management → Budgets.

Lưu ý: tắt máy từ bên trong (`sudo shutdown`) **không** dừng tính tiền; phải `deallocate`.

## 3. Chuẩn bị

| Cần có | Ghi chú |
|---|---|
| Subscription Azure Pay-As-You-Go | Tài khoản có quyền tạo resource group (Contributor trở lên) |
| Azure CLI | Cài trên máy dev rồi `az login`, hoặc dùng Azure Cloud Shell |
| Quota vCPU | Cần 4 vCPU dòng B ở vùng đã chọn. Kiểm tra: `az vm list-usage --location southeastasia -o table` |
| Quyền đọc repo | Repo riêng tư thì cần Personal Access Token hoặc deploy key để `git clone` trên VM |
| Key AI1 | `MISTRAL_API_KEY`, `OPENAI_API_KEY` (team AI1 cấp) |
| LLM cho AI2 | `AI2_LLM_BASE_URL`, `AI2_LLM_API_KEY` (Lead chốt nhà cung cấp) |
| SMTP (tuỳ chọn) | Để gửi thư mời và chia sẻ. Azure chặn cổng 25 chiều ra; dùng cổng 587 (ví dụ Gmail SMTP) |

## 4. Các bước

### Bước 1. Tạo hạ tầng Azure (trên máy dev)

```bash
az login
az account set --subscription "<tên hoặc ID subscription>"
deploy/azure/provision.sh
```

Script in kế hoạch và hỏi xác nhận trước khi tạo. Tuỳ chỉnh bằng biến môi trường:

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `AZ_RESOURCE_GROUP` | `rg-contract-intelligence` | Mọi tài nguyên nằm trong nhóm này |
| `AZ_LOCATION` | `southeastasia` | Vùng Azure |
| `AZ_VM_NAME` | `ci-vm` | Tên máy ảo |
| `AZ_VM_SIZE` | `Standard_B4ms` | Tối thiểu 4 vCPU, 8 GiB; khuyên dùng 16 GiB |
| `AZ_OS_DISK_GB` | `64` | Image Docker, dữ liệu DB, MinIO và backup đều nằm trên đĩa này |
| `AZ_SSH_SOURCE` | IP công khai của máy đang chạy script | Địa chỉ được phép SSH |
| `AZ_SSH_PUBLIC_KEY` | trống | Đường dẫn public key; trống thì `az` tạo hoặc dùng `~/.ssh/id_rsa` |
| `AZ_AUTO_SHUTDOWN_UTC` | trống | Giờ UTC tự tắt hằng ngày, dạng `hhmm` |

Kết quả: resource group, NSG (22 chỉ từ `AZ_SSH_SOURCE`; 80, 443 từ mọi nơi), IP tĩnh và VM. Script in IP và ba địa chỉ `app-…`, `api-…`, `auth-…`.

Nếu IP nhà mạng của bạn đổi và không SSH được nữa, mở lại bằng:

```bash
az network nsg rule update -g rg-contract-intelligence --nsg-name ci-vm-nsg \
  -n allow-ssh --source-address-prefixes "$(curl -s https://api.ipify.org)/32"
```

### Bước 2. Cài máy chủ (trên VM)

```bash
ssh azureuser@<ip>
sudo git clone https://github.com/AI20K-VGR/contract-intelligence-core.git /opt/contract-intelligence
cd /opt/contract-intelligence
sudo git checkout <nhánh cần deploy>      # thường là develop
sudo deploy/bootstrap.sh
```

`bootstrap.sh` cài Docker, bật firewall trong máy (chỉ SSH, 80, 443), thêm swap nếu RAM dưới 16 GB và tạo `deploy/.env.prod` với:

- `API_HOST`, `AUTH_HOST`, `APP_HOST` theo IP của máy;
- `FRONTEND_ORIGINS` và `FRONTEND_BASE_URL` trỏ về `https://app-<ip>.sslip.io`;
- mọi secret được sinh ngẫu nhiên.

Sau đó điền phần script không tự sinh được:

```bash
sudo nano deploy/.env.prod     # AI2_LLM_BASE_URL, AI2_LLM_API_KEY; SMTP_* nếu gửi thư thật
sudo nano ai-service/.env      # MISTRAL_API_KEY, OPENAI_API_KEY; AI2_EMBEDDING_* nếu dùng vector
```

Không muốn máy này phục vụ frontend thì để `APP_HOST=` trống và bỏ `https://app-…` khỏi `FRONTEND_ORIGINS`.

### Bước 3. Triển khai (trên VM)

```bash
sudo deploy/deploy.sh
```

Script làm lần lượt:

1. Build image (backend, worker, AI1, AI2, Keycloak, và frontend nếu có `APP_HOST`). Frontend được build với `VITE_API_BASE_URL=https://$API_HOST` và `VITE_KEYCLOAK_URL=https://$AUTH_HOST`.
2. `up -d`, chờ backend healthy. Backend tự chạy `alembic upgrade head`.
3. Cấu hình Keycloak: thêm `FRONTEND_ORIGINS` vào redirect và web origins, đổi secret client backend, **đổi mật khẩu ba tài khoản demo**, cấu hình SMTP, bật khoá tạm khi đăng nhập sai nhiều lần.
4. Smoke test: `/health`, issuer OIDC, `/admin` bị chặn, `/grafana` từ chối người lạ, frontend trả 200 cho một đường dẫn phía client.

Lần đầu Caddy cần khoảng một phút để xin chứng chỉ cho ba host.

### Bước 4. Kiểm tra từ bên ngoài (trên máy dev)

Kiểm tra cổng phải chạy từ máy khác: từ chính VM gọi IP công khai của nó có thể đi vòng trong máy và bỏ qua NSG.

```bash
deploy/check_external.sh api-<ip>.sslip.io auth-<ip>.sslip.io app-<ip>.sslip.io
```

Hoặc GitHub → Actions → `deploy-external-check`. Script kiểm HTTPS, issuer OIDC, `/admin` trả 404, `/grafana` trả 401, frontend trả 200 và 19 cổng nội bộ đều đóng.

Sau đó chạy tay luồng chính trên `https://app-<ip>.sslip.io`:

| # | Việc | Kết quả mong đợi |
|---|---|---|
| 1 | Đăng nhập `operator@ci.local` (mật khẩu `DEMO_OPERATOR_PASSWORD` trong `deploy/.env.prod`) | Vào được trang danh sách hồ sơ |
| 2 | Tải lên một hợp đồng PDF vài trang | Hồ sơ chuyển sang OCR, tiến độ cập nhật trực tiếp (SSE) |
| 3 | Xác nhận manifest | Hồ sơ sang bước AI2 rồi `pending_review` |
| 4 | Mở trang cấu trúc và hỏi đáp trên hồ sơ | Có cây điều khoản; câu trả lời kèm trích dẫn |
| 5 | Đăng nhập `reviewer@ci.local`, thẩm định một xung đột | Trạng thái xung đột đổi |
| 6 | Đăng nhập `admin@ci.local`, mở Giám sát hệ thống | Dashboard Grafana hiện, có số liệu OCR vừa chạy |

## 5. Vận hành

Mọi lệnh `docker compose` trên VM dùng cùng bộ file:

```bash
cd /opt/contract-intelligence
C="docker compose -f docker-compose.yml -f deploy/compose.prod.yml -f deploy/compose.frontend.yml --env-file deploy/.env.prod"
sudo $C ps
sudo $C logs -f backend backend-worker
```

Bỏ `-f deploy/compose.frontend.yml` nếu `APP_HOST` trống.

| Việc | Cách làm |
|---|---|
| Cập nhật bản mới | `sudo deploy/deploy.sh --pull` (kéo nhánh đang checkout, build lại, khởi động lại) |
| Quay lại bản cũ | `sudo git checkout <commit cũ> && sudo deploy/deploy.sh`. Migration không tự lùi: nếu bản mới đã đổi schema thì khôi phục DB từ backup |
| Đổi key AI1 | Sửa `ai-service/.env`, rồi `sudo deploy/deploy.sh` (container phải được tạo lại mới đọc `.env`) |
| Backup | `sudo deploy/backup.sh`: hai DB và MinIO vào `/var/backups/contract-intelligence`, giữ 7 ngày. Cron: `0 2 * * * /opt/contract-intelligence/deploy/backup.sh >> /var/log/ci-backup.log 2>&1` |
| Keycloak admin | Qua SSH tunnel, xem [README.md](README.md) mục "Việc vận hành" |
| Tắt máy để tiết kiệm | `az vm deallocate -g rg-contract-intelligence -n ci-vm` |
| Bật lại | `az vm start -g rg-contract-intelligence -n ci-vm` |
| Xoá toàn bộ | `az group delete --name rg-contract-intelligence` (mất cả dữ liệu) |

Backup nằm trên chính đĩa của VM. Muốn giữ được khi mất máy thì chép `/var/backups/contract-intelligence` ra ngoài, hoặc tạo snapshot đĩa: `az snapshot create -g rg-contract-intelligence -n ci-vm-snap --source <ID đĩa hệ thống>`.

## 6. Bảo mật

- Chỉ Caddy mở cổng ra Internet (80, 443). NSG của Azure và `ufw` trong máy cùng chặn phần còn lại.
- SSH chỉ từ `AZ_SSH_SOURCE` và chỉ bằng khoá.
- Secret nằm trong `deploy/.env.prod` và `ai-service/.env` trên VM (quyền 600, không commit). Backend ở `ENV=prod` từ chối khởi động nếu secret còn là giá trị mặc định.
- Mật khẩu tài khoản demo trong `realm-export.json` là công khai; `deploy.sh` đổi chúng sang giá trị trong `deploy/.env.prod`. Gửi mật khẩu cho nhóm qua kênh riêng.
- Console quản trị Keycloak không ra Internet.

## 7. Giới hạn đã biết

- **Một máy, không dự phòng.** VM hỏng hoặc Azure bảo trì thì cả hệ thống dừng.
- **Kafka không lưu ra volume.** Khởi động lại (kể cả deallocate) làm mất message đang xử lý; run bị ảnh hưởng báo `AI1_TIMEOUT` và người dùng bấm chạy lại OCR.
- **Dữ liệu nằm trên đĩa hệ thống của VM.** Xoá resource group là mất hết nếu chưa chép backup ra ngoài.
- **Có giám sát, chưa có cảnh báo.** Chưa có Alertmanager, nên vẫn cần người xem dashboard.
- **Chưa dùng dịch vụ quản lý của Azure** (Azure Database for PostgreSQL, Blob Storage, Event Hubs, Container Apps). Chuyển sang các dịch vụ đó là việc riêng, cần đổi cấu hình kết nối và kiểm thử lại.
