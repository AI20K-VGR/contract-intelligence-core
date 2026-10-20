# 11 · Tài liệu Quản trị viên (Admin Guide)

| Thuộc tính | Nội dung |
|---|---|
| Người phụ trách | Chương (BE) |
| Phối hợp | Trang (FE) |
| Cập nhật | 20/10/2026 |

Tài liệu cho người quản trị hệ thống production, gồm hai nhóm việc:
- **Trong ứng dụng** (mục 1–2): quản lý người dùng, xem nhật ký và giám sát. Chỉ cần tài khoản vai trò Quản trị.
- **Trên server** (mục 3–8): log, khởi động lại dịch vụ, backup, khôi phục, cấu hình. Cần SSH vào `ci-app` (xem [07](07-huong-dan-deploy.md) §1 và [12](12-danh-sach-tai-khoan.md)).

Mọi thay đổi cấu hình trên production (Cloudflare, security group, `deploy/.env.prod`) phải có **PR được duyệt trước** (Lead chốt 14/10/2026). Riêng việc vận hành thường ngày (xem log, backup, restart một container, quản lý người dùng) thì không cần PR.

---

## 1. Quản lý người dùng (trong ứng dụng)

Đăng nhập bằng tài khoản **Quản trị**, vào **Người dùng & Phân quyền** (`/nguoi-dung-phan-quyen`). Ứng dụng gọi Keycloak giúp, nên **không cần** mở trang quản trị Keycloak cho các việc thường ngày.

| Việc | Trên giao diện | API (để tra cứu) |
|---|---|---|
| Xem, tìm người dùng | Danh sách, ô tìm kiếm | `GET /users` |
| Thêm người dùng | Nhập email, tên, vai trò → hệ thống gửi email đặt mật khẩu | `POST /users` |
| Gửi lại email đặt mật khẩu | Nút gửi lại lời mời | `POST /users/{id}/invite` |
| Đổi vai trò | Chọn Vận hành / Thẩm định / Quản trị | `PATCH /users/{id}` |
| Khoá tài khoản | Nút vô hiệu hoá. Mọi phiên đang mở của người đó kết thúc **ngay** (back-channel logout, #129) | `POST /users/{id}/disable` |
| Mở khoá | Nút kích hoạt | `POST /users/{id}/enable` |

**Vai trò:**

| Vai trò | Được làm |
|---|---|
| Vận hành (`OPERATOR`) | Tạo và tải hồ sơ, chạy lại xử lý, chia sẻ hồ sơ của mình |
| Thẩm định (`REVIEWER`) | Thẩm định mâu thuẫn, khoá hồ sơ để thẩm định |
| Quản trị (`ADMINISTRATOR`) | Mọi việc trên, cộng: duyệt hồ sơ, quản lý người dùng, xem nhật ký dịch vụ, giám sát hệ thống |

Ngoài vai trò, mỗi hồ sơ còn có quyền riêng: chủ hồ sơ, và người được chia sẻ `read` hoặc `edit` có thời hạn. Chi tiết ở DOC-05b §2.

**Lưu ý:**
- **Email:** thư mời và thư đặt lại mật khẩu gửi qua SMTP cấu hình trong `deploy/.env.prod` (`SMTP_*`). Chưa cấu hình SMTP thì thư rơi vào Mailpit trên server (mục 3, dòng "Đọc email trên server").
- **Mật khẩu:** người dùng tự đổi mật khẩu qua liên kết "Quên mật khẩu" ở trang đăng nhập. Keycloak tự khoá tạm tài khoản 15 phút sau 5 lần sai mật khẩu.
- **Cột "Đăng nhập gần nhất" trống** nghĩa là realm chưa lưu sự kiện đăng nhập. Cách bật: `deploy/README.md` §"Cột Đăng nhập gần nhất".

## 2. Nhật ký và giám sát (trong ứng dụng)

| Trang | Nội dung | Ai xem |
|---|---|---|
| **Nhật ký hoạt động** (`/nhat-ky-hoat-dong`) | Ai làm gì trên hồ sơ của tenant: tải lên, xoá, chạy lại, chia sẻ… | Mọi vai trò |
| **Giám sát hệ thống** (`/admin/monitoring`) | Grafana nhúng trong app, 2 tab: "Hệ thống & AI1 (OCR)" (CPU, RAM theo container, request, lỗi, OCR) và "AI2: chi phí & tốc độ" (token, chi phí USD ước tính, thời gian job) | Quản trị |
| Nhật ký dịch vụ (`GET /ops/service-logs`) | Log đã chuẩn hoá của Backend, AI2, Frontend, lọc theo `X-Request-Id` | Quản trị |

**Đọc Grafana:**
- **Container bị khởi động lại liên tục:** thường là thiếu RAM (OOM). Kiểm ở mục 3, rồi tăng `*_MEM_LIMIT` trong `deploy/.env.prod` (cần PR).
- **Hàng đợi OCR hoặc AI2 dài:** hồ sơ lớn đang chạy. AI2 xử lý **mỗi lần một hồ sơ** (`AI2_MAX_CONCURRENT_JOBS=1`), hồ sơ đến sau chờ ở backend.
- **Có giám sát, chưa có cảnh báo:** chưa cài Alertmanager, nên cần có người xem định kỳ.

Chi tiết dashboard: `docs/MONITORING.md`.

## 3. Thao tác trên server: log, trạng thái, khởi động lại

Đăng nhập server:

```bash
ssh -i ~/.ssh/ci-deploy-aws.pem ubuntu@52.63.103.239
cd /opt/contract-intelligence
```

Tạo alias cho lệnh compose, dùng trong mọi lệnh bên dưới:

```bash
alias dc='sudo docker compose -f docker-compose.yml -f deploy/compose.prod.yml -f deploy/compose.frontend.yml -f deploy/compose.external-db.yml -f deploy/compose.cloudflare.yml -f deploy/compose.cloudflare-aop.yml --env-file deploy/.env.prod'
```

Thứ tự file giống `deploy.sh` (dòng 19–55):
- `compose.frontend.yml` khi có `APP_HOST`;
- `compose.external-db.yml` khi có `BACKEND_DB_HOST`;
- `compose.cloudflare.yml` khi có `deploy/certs/origin.pem`;
- `compose.cloudflare-aop.yml` khi có thêm `deploy/certs/origin-pull-ca.pem`.

Production hiện thoả các điều kiện trên. File nào không thoả thì bỏ khỏi alias.

| Việc | Lệnh |
|---|---|
| Trạng thái mọi container | `dc ps` |
| Log một dịch vụ | `dc logs --tail 200 -f backend` (thay bằng `backend-worker`, `ai1-worker`, `ai2-service`, `keycloak`, `caddy`) |
| Tìm log theo request | `sudo docker logs ci-backend 2>&1 \| grep <X-Request-Id>` |
| Container có bị OOM không | `sudo docker inspect -f '{{.State.OOMKilled}} {{.RestartCount}}' ci-ai2-service` |
| RAM, CPU hiện tại | `sudo docker stats --no-stream` |
| Khởi động lại một dịch vụ | `dc restart backend` (dịch vụ khác tương tự). Không ảnh hưởng dữ liệu |
| Đĩa còn trống | `df -h /` ; dọn image cũ: `sudo docker image prune -f` |
| Phiên bản đang chạy | `git -C /opt/contract-intelligence log --oneline -1` |
| Đọc email trên server (Mailpit) | Lấy IP: `sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' ci-mailpit`. Trên máy mình: `ssh -L 8025:<IP>:8025 ubuntu@52.63.103.239`, rồi mở http://localhost:8025 |

**Không** dùng `dc down -v` trên server: lệnh này xoá volume (MinIO, Prometheus, dữ liệu Keycloak nếu chạy cùng máy).

**Khởi động lại cả stack** (ví dụ sau khi reboot máy): Docker tự chạy lại các container (`restart: unless-stopped`). Muốn chạy lại có kiểm tra thì dùng `sudo deploy/deploy.sh`; lệnh này cũng chạy smoke test.

## 4. Backup và khôi phục

**Backup** (`deploy/backup.sh`):
- **Nội dung:** dump hai database (`backend.dump`, `keycloak.dump`, chạy qua mạng tới `ci-db`) cùng toàn bộ MinIO. Mỗi bản khoảng 1,8 GB.
- **Lịch:** tự động lúc **02:00 giờ Việt Nam** (`0 19 * * *` UTC) mỗi đêm.
  - `deploy.sh` ghi lịch vào `/etc/cron.d/ci-backup` ở mỗi lần deploy, theo `BACKUP_SCHEDULE` trong `deploy/.env.prod`; `off` thì xoá lịch (#150).
  - Không cần sửa crontab bằng tay.
- **Trên server:** `/var/backups/contract-intelligence/<thời điểm>/`, giữ **3 ngày** (`BACKUP_KEEP_DAYS`). Đĩa `ci-app` 38 GB, nên không giữ lâu hơn.
- **Ngoài máy (AWS S3):** sau mỗi lần backup, script mã hoá AES-256 bằng `BACKUP_ENCRYPTION_PASSPHRASE`, chia thành các phần, rồi đẩy lên bucket `ci-backups-706421610602` (Sydney).
  - Lần đầu chạy ngày 20/10/2026: 42 object, 1,89 GB.
  - Thiết kế **chống xoá:**
    - IAM user `ci-backup-writer` trên server chỉ ghi và đọc được, không có quyền xoá;
    - bucket bật versioning;
    - lifecycle của bucket tự xoá bản cũ sau **7 ngày** (`BACKUP_REMOTE_KEEP_DAYS=0`).

    Ai chiếm được `ci-app` cũng không xoá được bản ngoài máy.
  - Chi phí khoảng 0,3 USD/tháng. Cách dựng: `deploy/README.md` §"Backup ra ngoài máy: AWS S3".

| Việc | Lệnh |
|---|---|
| Backup ngay | `sudo deploy/backup.sh` |
| Kiểm lịch tự động | `cat /etc/cron.d/ci-backup` |
| Xem các bản trên server | `sudo ls -lh /var/backups/contract-intelligence/` |
| Xem kết quả lần chạy gần nhất | `sudo tail -n 20 /var/log/ci-backup.log`. Phải có dòng `[backup] off-site: ci-backups-706421610602/<thời điểm> … part(s)` |
| Xem các bản trên S3 (máy người vận hành, AWS CLI đã đăng nhập) | `aws s3 ls s3://ci-backups-706421610602/ --region ap-southeast-2`; tổng dung lượng: thêm `--recursive --summarize` |

**Luôn backup tay trước** khi: merge một migration xoá hoặc đổi dữ liệu, đổi image database, hoặc chuyển máy.

**Khôi phục:** theo `deploy/README.md`:
- **Một database:** dòng "Khôi phục DB backend" ở bảng "Việc vận hành".
- **Cả hai database và MinIO** (ví dụ sang máy mới): mục "Chuyển sang máy mới cùng dữ liệu", bước 5 và 8.
- **Từ S3** (khi server mất cả bản tại chỗ):
  1. Dùng tài khoản quản trị AWS, không dùng `ci-backup-writer`: `aws s3 cp --recursive s3://ci-backups-706421610602/<thời điểm>/ .`.
  2. Kiểm `SHA256SUMS`, ghép các phần, rồi giải mã bằng `BACKUP_ENCRYPTION_PASSPHRASE`. Lệnh ở `deploy/README.md`, đoạn "Khôi phục từ bucket".
  3. Khôi phục như hai dòng trên.

Ba điểm phải nhớ:
1. **Role `ai2` phải có trước** khi khôi phục database backend (`pg_dump` không lưu role). Chạy stack một lần để backend tạo role, rồi mới `pg_restore`.
2. **Dừng `backend`, `backend-worker`, `ai2-service`** trong lúc khôi phục, để không có gì ghi vào.
3. **Bản ngoài máy cần `BACKUP_ENCRYPTION_PASSPHRASE`** để giải mã. Người giữ: [12](12-danh-sach-tai-khoan.md).

## 5. Cấu hình

| Ở đâu | Chứa gì | Đổi thế nào |
|---|---|---|
| `deploy/.env.prod` (server) | Tên miền, mật khẩu database, secret Keycloak, HMAC backend↔AI2, SMTP, khoá LLM của AI2, trần RAM, backup | Sao lưu sang `/root/ci-env-backups/` trước khi sửa; sửa bằng `sudo nano`; chạy lại `sudo deploy/deploy.sh` |
| `ai-service/.env` (server) | Khoá OCR (Mistral, OpenAI) và cấu hình AI1, AI2 | Như trên |
| Repo (`docker-compose.yml`, `deploy/compose.prod.yml`, `deploy/Caddyfile`…) | Mọi thứ không bí mật | Qua PR, merge là deploy |

Danh sách biến môi trường: `deploy/.env.prod.example` (có chú thích từng biến) và tài liệu 8 của Văn Dũng.

**Sửa file mount từng file** (`deploy/Caddyfile`, `deploy/frontend.caddy`, `infra/monitoring/prometheus/prometheus.yml`):
- `deploy.sh` so sha256 với bản trong container, kiểm cấu hình rồi restart.
- Muốn tự kiểm, ví dụ với Caddy:
  ```bash
  sha256sum deploy/Caddyfile; sudo docker exec ci-caddy sha256sum /etc/caddy/Caddyfile
  ```
  Hai mã phải giống nhau. Prometheus tương tự, với `ci-prometheus` và `/etc/prometheus/prometheus.yml`.

**Đổi khoá LLM** (ví dụ khoá hết tiền, preflight AI2 chặn deploy):
1. Sao lưu `deploy/.env.prod` sang `/root/ci-env-backups/`.
2. Thay `AI2_LLM_API_KEY`, `AI2_EMBEDDING_API_KEY` (và `AI2_CONTRACT_GRAPH_PAIRS_API_KEY` nếu có).
3. Chạy lại workflow deploy.

Không dán khoá vào lệnh terminal hay chat: mở file bằng editor trên server.

## 6. Mạng và truy cập

**SSH vào `ci-app` bị timeout:** security group chỉ cho IP của người vận hành vào cổng 22, mà IP nhà hay đổi. Cần AWS CLI đã đăng nhập (`aws login --region ap-southeast-2`):

```bash
IP=$(curl -s -4 https://checkip.amazonaws.com)
aws ec2 authorize-security-group-ingress --region ap-southeast-2 --group-id sg-070e3d258f1793c3e \
  --ip-permissions "IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{CidrIp=$IP/32,Description=operator-ssh-$(date +%Y%m%d)}]"
# xoá rule của IP cũ (lấy id bằng describe-security-group-rules)
aws ec2 revoke-security-group-ingress --region ap-southeast-2 --group-id sg-070e3d258f1793c3e --security-group-rule-ids <sgr-…>
```

**Mở trang quản trị Keycloak:** Cloudflare và Caddy chặn `/admin` từ Internet, nên phải đi qua SSH tunnel.
1. Lấy IP container: `sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' ci-keycloak`.
2. Trên máy mình: `ssh -i ~/.ssh/ci-deploy-aws.pem -L 8080:<IP>:8080 ubuntu@52.63.103.239`.
3. Mở http://localhost:8080/admin, user `admin`, mật khẩu là `KEYCLOAK_ADMIN_PASSWORD` trong `deploy/.env.prod`.

**Cloudflare** (người giữ tài khoản ở [12](12-danh-sach-tai-khoan.md)):

| Việc | Nơi làm |
|---|---|
| Đang bị tấn công | Security → Settings → **Under Attack Mode**; tắt lại khi hết |
| Sửa theme đăng nhập mà chưa thấy | Caching → Purge Cache → Custom Purge, dán URL file CSS |
| Đổi luật WAF, rate limit | Security → WAF (gói Free có 5 luật custom, đang dùng 4) |

Cấu hình đầy đủ: `deploy/README.md` §"Đứng sau Cloudflare".

## 7. Dữ liệu hồ sơ

- **Xoá hồ sơ:** chủ hồ sơ hoặc Quản trị xoá trong app. Hồ sơ biến mất ngay; vòng bảo trì của backend xoá hẳn database, file MinIO và dữ liệu AI2 sau đó. Bảng `deletion_ledger` ghi lại bằng chứng (xem [02](02-thiet-ke-csdl.md) §5).
- **Consent gửi nội dung ra LLM (AI2):** bật hoặc tắt **theo từng hồ sơ**, do chủ hồ sơ quyết định.
  - Bật consent cho hồ sơ đã chạy AI2 thì AI2 tự chạy lại hồ sơ đó.
  - **Không bật hàng loạt** cho các hồ sơ cũ (Lead chốt 15/10/2026).
- **Chạy lại xử lý:** trên giao diện hồ sơ có các nút:
  - "Chạy lại phần lỗi" (`/ocr/retry-failed`);
  - "Chạy lại AI2" (`/ai2/retry`);
  - "Chạy lại toàn bộ" (`/reprocess`).

  Hồ sơ phân tích bằng bản AI2 cũ cần chạy lại AI2 để có graph và finding mới.
- **Dữ liệu trên production:** chỉ hợp đồng mẫu đã ẩn thông tin, không hồ sơ thật (DEC-BE-AI2-01 D6). Nội dung hồ sơ đi qua Cloudflare dạng đọc được, và gửi tới LLM khi bật consent.

## 8. Khi có sự cố

| Triệu chứng | Kiểm tra trước | Xử lý |
|---|---|---|
| Không vào được site | https://www.cloudflarestatus.com; `dc ps` trên server | Container chết thì xem log rồi `dc restart <dịch vụ>`; không SSH được thì xem mục 6 |
| Đăng nhập được nhưng mọi API trả 401 | Giờ của server (`timedatectl`); log `backend` có `Session has ended`? | Token của phiên đã đăng xuất là bình thường; nếu lỗi hàng loạt, `dc restart backend keycloak` |
| Tải lên báo lỗi với file lớn | Mạng người dùng chậm; Cloudflare cắt một request sau khoảng 125 s (#145) | Frontend đã tải theo khúc (`/uploads`, từ 20/10/2026), nên mất mạng thì tiếp tục từ khúc đang dở. Lỗi `429` là người đó đang có 3 lượt tải chưa xong: chờ, hoặc huỷ một lượt. File > 50 MiB thì nén hoặc tách |
| `/api/v1/readyz` báo `degraded` | `checks.db_ok`, `checks.ai_service_ok` trong kết quả | `db_ok: false` thì xem `ci-db`; `ai_service_ok: false` thì `dc logs ai2-service` (backend không gọi được `/healthz` của AI2) |
| Bấm "Đọc lại N trang" báo chưa hỗ trợ | Bình thường: production chưa có service đọc lại từng trang (#152) | Dùng "Đọc lại" cả hồ sơ |
| Không có bản backup mới hoặc thiếu dòng `off-site` | `sudo tail -n 20 /var/log/ci-backup.log`; `cat /etc/cron.d/ci-backup`; `df -h /` | Hết đĩa thì xoá bớt bản cũ trên server; `off-site copy FAILED` thì kiểm `BACKUP_S3_*` (mục 4) rồi chạy `sudo deploy/backup.sh` |
| OCR không chạy | `dc logs ai1-worker`; khoá Mistral, OpenAI trong `ai-service/.env` | Sửa khoá, `dc restart ai1-worker`, bấm chạy lại phần lỗi |
| AI2 báo lỗi hoặc treo | `dc logs ai2-service`; OOM (mục 3); khoá LLM còn hạn mức | Sửa khoá hoặc tăng RAM (cần PR), chạy lại AI2 |
| Deploy dừng ở `AI2 preflight` | Log workflow: lỗi provider (`credit_balance_exhausted`, model không tồn tại) | Đổi khoá (mục 5); production vẫn chạy bản cũ trong lúc chờ |
| Hết đĩa | `df -h /`, `sudo du -sh /var/backups/contract-intelligence /var/lib/docker` | `sudo docker image prune -f`; xoá bớt backup cũ (giữ ít nhất một bản) |
