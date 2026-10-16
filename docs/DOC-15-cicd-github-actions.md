# DOC-15 — CI/CD với GitHub Actions

Trạng thái ngày 14/10/2026; luồng staging cập nhật ngày 16/10/2026 (PR #112). Tài liệu này mô tả các workflow trong `.github/workflows/` và cách chuyển phần deploy tự động sang AWS. Cách dựng server nằm ở [`deploy/README.md`](../deploy/README.md).

## Tóm tắt

- **CI:** mỗi PR chạy kiểm tra theo phần code bị sửa (backend, ai-service, frontend) cộng `pr-guard`.
- **CD:** mỗi lần push vào `develop` (tức là merge PR), workflow `deploy` SSH vào server, chuyển checkout tới đúng commit vừa merge, chạy `deploy/deploy.sh`, rồi kiểm tra server từ bên ngoài. Khi biến repo `STAGING_ENABLED=true`, bản mới lên staging trước; staging lỗi thì production giữ bản cũ.
- **Server đích là app server AWS** `52.63.103.239` (Sydney) từ 14/10/2026: dữ liệu đã chuyển từ server cũ `150.95.104.132`, DNS `contract-intelligence.tech` trỏ AWS, và lần merge #77 đã tự deploy lên đó. Cả ba tên miền đứng sau Cloudflare (`deploy/README.md`, "Đứng sau Cloudflare").

## Chi phí AWS và cảnh báo

Lead chốt ngày 14/10/2026: chuyển sang AWS; trần chi phí do Phạm Hoàng Chương (backend) đặt.

| Mục | Giá trị |
|---|---|
| Nguồn tiền | $200 credit của tài khoản AWS dự án (Free plan, chỉ dùng được region Sydney) |
| Trần | Tổng không vượt $200 credit; mỗi tháng không quá **$150** |
| Mức chi dự kiến | ~$115/tháng khi hai máy chạy 24/7; dưới $10/tháng khi stop cả hai (chỉ còn đĩa và Elastic IP) |
| Cảnh báo | AWS Budgets `ci-monthly-150`: email khi chi phí thực tế **trong tháng** vượt **$50**, **$100**, **$150**. Budget tính chi phí **không trừ credit**, để cảnh báo phản ánh lượng credit đã tiêu |
| Người nhận cảnh báo | Phạm Hoàng Chương (email cá nhân đã đăng ký trong Budgets; không ghi địa chỉ vào repo vì repo công khai) |
| Khi nhận cảnh báo $150, hoặc credit sắp hết | Stop cả hai máy (`ci-app` trước, rồi `ci-db`) và báo Lead trước khi bật lại |

Xem hoặc đổi mức cảnh báo: AWS Console → Billing → Budgets → `ci-monthly-150`, hoặc `aws budgets describe-budget --account-id 706421610602 --budget-name ci-monthly-150`.

```mermaid
flowchart LR
  A[PR vào develop] --> B{CI theo path<br/>+ pr-guard}
  B -->|merge| C[push develop]
  C --> P[preflight]
  P --> S{STAGING_ENABLED<br/>= true?}
  S -->|có| T[job staging<br/>deploy-target.yml<br/>environment staging]
  T -->|thành công| D[job deploy<br/>deploy-target.yml<br/>environment production]
  T -->|lỗi| X[production giữ bản cũ]
  S -->|không| D
  M[bấm tay -f target=staging<br/>từ nhánh bất kỳ] --> P2[preflight] --> T2[job staging<br/>chỉ staging]
  D -->|SSH| E[server: git checkout --detach SHA<br/>deploy/deploy.sh]
  E --> F[check_external.sh<br/>chạy trên runner]
```

## Các workflow

| File | Chạy khi | Làm gì |
|---|---|---|
| `backend-ci.yml` | PR vào `main`/`develop` sửa `backend/**`; push vào `main` hoặc `feature/**` sửa `backend/**` | import-linter, Ruff, MyPy, unit test, integration test trên PostgreSQL thật (`pgvector/pgvector:pg16`, bỏ marker `ai2_local_e2e`) |
| `ai-service.yml` | PR sửa `ai-service/**`; push vào `develop`/`main` sửa `ai-service/**` | Kiểm tra AI1/AI2 |
| `frontend.yml` | PR sửa `frontend/**`; push vào `develop`/`main` sửa `frontend/**` | Kiểm tra frontend |
| `pr-guard.yml` | Mọi PR | Tên nhánh, tiêu đề PR (`<type>(<scope>): …`), nguồn PR vào `main`, cấm commit PDF/ảnh/file nén ngoài `docs/assets/` |
| `labeler.yml` | Mọi PR (`pull_request_target`) | Gắn nhãn theo thư mục |
| `deploy.yml` | PR vào `develop` (chỉ `preflight`); push vào `develop`; bấm tay (Run workflow, chọn `target`) | `preflight` kiểm luật nhánh và chạy test deploy. Push: job `staging` (khi `STAGING_ENABLED=true`) rồi job `deploy` lên production. Bấm tay: `target=production` chỉ từ `develop`; `target=staging` từ nhánh bất kỳ, chỉ lên staging |
| `deploy-target.yml` | Chỉ được `deploy.yml` gọi (`workflow_call`, input `target`) | Các bước của một lần deploy lên một server: mở SSH, deploy đúng SHA, kiểm tra từ bên ngoài, đóng SSH. Staging đọc secret/biến `STAGING_*`, không bao giờ lấy giá trị production thay thế |
| `deploy-external-check.yml` | Chỉ bấm tay | Kiểm tra từ bên ngoài một server bất kỳ: HTTPS, issuer OIDC, `/admin` bị chặn, `/grafana` 401, các cổng nội bộ đóng |

### Luật merge (ruleset, không phải branch protection kiểu cũ)

Repo dùng **ruleset** (Settings → Rules → Rulesets), nên API branch protection kiểu cũ trả 404 dù nhánh vẫn được bảo vệ. Ruleset `develop`, đọc ngày 14/10:

- Chỉ vào `develop` qua PR, không push thẳng, không force-push, không xoá nhánh.
- Cần **2 approve**, trong đó có code owner (`.github/CODEOWNERS`: team `@AI20K-VGR/ai20k-ojt-batch-3`, thêm `@hieubui2409` cho `.github/`). Approve phải có sau lần push cuối (push mới tự huỷ approve cũ), và người push cuối không tự approve thay được.
- Mọi thread review phải resolve.
- Check bắt buộc: chỉ `pr-guard`, và nhánh phải cập nhật với `develop`. `Backend CI`, `ai-service`, `frontend` chạy nhưng không bắt buộc.
- Không ai được bỏ qua (danh sách bypass rỗng).

Ruleset `main` giống vậy, thêm: chỉ squash merge và lịch sử thẳng. Ruleset `branch-naming` ép tên nhánh `^(feat|feature|fix|docs|chore|refactor|test|hotfix|release)/[a-z0-9._-]+$`.

## Workflow `deploy`

### Các bước

1. **Đủ cấu hình chưa?** Thiếu một trong `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, `DEPLOY_KNOWN_HOSTS` (với staging là bản `STAGING_*`) thì job báo lỗi và dừng.
2. **Khoá SSH:** ghi `DEPLOY_SSH_KEY` và `DEPLOY_KNOWN_HOSTS` ra `~/.ssh` của runner, `StrictHostKeyChecking yes`: runner chỉ nói chuyện với đúng server đã ghim khoá.
3. **Cập nhật và deploy:** trên server, trong `/opt/contract-intelligence`:
   ```bash
   # checkout có file sửa hay file lạ thì dừng, không ghi đè
   git fetch origin "$SHA"; git checkout --detach "$SHA"
   deploy/deploy.sh
   ```
   `deploy.sh` build image, kiểm tra DB server (nếu DB ở máy riêng) và nhà cung cấp LLM/embedding của AI2 **trước** khi `up -d`. Kiểm tra lỗi thì stack đang chạy giữ nguyên. Sau đó nó chờ backend và AI2 sẵn sàng, cấu hình Keycloak và chạy smoke test.
4. **Kiểm tra từ bên ngoài:** đọc `API_HOST`, `AUTH_HOST`, `APP_HOST` từ `deploy/.env.prod` trên server, rồi chạy `deploy/check_external.sh` **trên runner**, tức là từ Internet. Có secret `DEPLOY_DB_PUBLIC_IP` thì kiểm thêm cổng 5432/5433 của DB server.

Một lần chạy tối đa 60 phút. GitHub chỉ giữ **một** lần chạy đang chờ trong mỗi nhóm `concurrency`: lần mới thay lần đang chờ. Vì vậy mỗi loại lần chạy có nhóm riêng:

| Lần chạy | Nhóm | Hệ quả |
|---|---|---|
| Push vào `develop`, bấm tay `target=production` | `deploy-production` | Các lần deploy production chạy lần lượt, staging rồi production trong cùng một lần chạy. Chỉ một lần merge mới hơn mới thay được lần deploy production đang chờ |
| Bấm tay `target=staging` | `deploy-staging-manual` | Không bao giờ huỷ hay thay lần deploy production đang chờ |
| PR vào `develop` | Riêng cho từng lần chạy | Chỉ chạy `preflight`, không chờ ai và không thay ai |

Job staging của một lần push và một lần bấm tay staging có thể tới máy staging cùng lúc. Script deploy giữ khoá `~/.ci-deploy.lock` trên server (`flock`, chờ tối đa 50 phút), nên hai lần deploy lên cùng một máy vẫn chạy lần lượt. Test `test_manual_staging_cannot_replace_a_waiting_production_deployment` trong `deploy/tests/test_keycloak_configure.py` giữ các luật này.

### Secrets

| Secret | Giá trị | Có chưa (14/10) |
|---|---|---|
| `DEPLOY_HOST` | IP hoặc tên server | Có, trỏ app server AWS `52.63.103.239` (14/10) |
| `DEPLOY_USER` | User SSH: `root`, hoặc user có `sudo` không hỏi mật khẩu | Có |
| `DEPLOY_SSH_KEY` | Khoá bí mật riêng cho GitHub Actions | Có |
| `DEPLOY_KNOWN_HOSTS` | Dòng `ssh-keyscan -t ed25519 <host>`, đã so tay với khoá của server | Có |
| `DEPLOY_DB_PUBLIC_IP` | IP công khai của DB server riêng (không bắt buộc) | Chưa |
| `AWS_DEPLOY_ACCESS_KEY_ID`, `AWS_DEPLOY_SECRET_ACCESS_KEY` | Access key của IAM user `ci-github-deploy`, chỉ dùng để mở/đóng cổng 22 trên AWS | Có (14/10) |

Đặt bằng `gh secret set <TÊN>` (gõ giá trị khi được hỏi), hoặc Settings → Secrets and variables → Actions.

### Duyệt trước khi deploy

Job `staging` chạy trong environment `staging` (không cần người duyệt), job `deploy` trong environment `production`. Khi `STAGING_ENABLED=true`, job `deploy` chỉ bắt đầu, và chỉ xin duyệt, sau khi staging thành công. **Hiện environment `production` chưa có luật nào** (`protection_rules` rỗng ngày 14/10), nên mọi push vào `develop` deploy ngay. Admin repo bật người duyệt theo mục "Duyệt trước khi deploy" trong `deploy/README.md`. Khi đã bật, mỗi lần merge tạo một lần chạy "Waiting"; server chỉ đổi sau khi người duyệt bấm **Review deployments → Approve**.

### Chạy tay

GitHub → Actions → `deploy` → Run workflow, chọn nhánh và `target`:

- `target=production` (mặc định): chỉ từ `develop`; nhánh khác bị `preflight` từ chối.
- `target=staging`: từ nhánh bất kỳ, để thử một PR trước khi merge. Chỉ deploy lên staging, không đụng production.

```bash
gh workflow run deploy.yml --ref <nhánh> -f target=staging
```

## Chuyển CD sang AWS

**Đã xong cả 5 bước ngày 14/10/2026.** Các mục dưới ghi lại cách đã làm, để làm lại khi đổi máy chủ.

### 1. Cho runner SSH được vào app server — đã làm

Security group `ci-app` chỉ mở cổng 22 cho IP của người vận hành, còn runner GitHub chạy từ dải IP rất rộng và thay đổi. Vì vậy mỗi lần deploy, workflow **mở cổng 22 cho đúng IP của runner** rồi đóng lại ở bước cuối, kể cả khi deploy lỗi.

Thông tin xác thực AWS cho việc này: dự định ban đầu là OIDC (không lưu key nào trong GitHub), nhưng policy của Organization chặn tạo OIDC provider (`iam:CreateOpenIDConnectProvider`, policy `p-xs3ungxb`). Vì vậy dùng một IAM user riêng có access key, quyền tối thiểu:

| Thành phần | Giá trị |
|---|---|
| IAM user | `ci-github-deploy`, inline policy `ssh-window-on-ci-app` |
| Quyền | `ec2:AuthorizeSecurityGroupIngress`, `ec2:RevokeSecurityGroupIngress` **chỉ trên** `sg-070e3d258f1793c3e`; `ec2:DescribeSecurityGroups`/`DescribeSecurityGroupRules` (chỉ đọc) ở `ap-southeast-2` |
| Secrets đã đặt | `AWS_DEPLOY_ACCESS_KEY_ID`, `AWS_DEPLOY_SECRET_ACCESS_KEY` |
| Repo variables (đặt ở bước 4) | `DEPLOY_SECURITY_GROUP_ID=sg-070e3d258f1793c3e`, `DEPLOY_AWS_REGION=ap-southeast-2` |

- Việc mở/đóng nằm trong `deploy/ssh_window.sh`. Mỗi rule mang mô tả `github-actions run <run id>`, nên `close` chỉ xoá đúng rule của lần chạy đó. `open` dọn trước các rule do lần chạy cũ bỏ lại (ví dụ runner chết giữa chừng).
- Hai bước này chỉ chạy khi có variable `DEPLOY_SECURITY_GROUP_ID`. Chưa đặt thì workflow giống hệt trước, nên deploy vào server cũ không bị ảnh hưởng.
- **Đã thử ngày 14/10** bằng một workflow tạm trên GitHub với đúng secrets này: mở cổng cho IP runner, đóng lại đúng rule đó; user này bị từ chối (`UnauthorizedOperation`) khi thử sửa security group `ci-db`. Rule SSH của người vận hành không bị đụng tới.
- Lộ access key thì kẻ xấu chỉ thêm/xoá được rule trên `ci-app`; muốn đăng nhập vẫn cần khoá SSH. Xoay key: `aws iam create-access-key --user-name ci-github-deploy`, đặt lại hai secret, rồi `aws iam delete-access-key` key cũ.
### 2. Khoá SSH riêng cho GitHub Actions

Không dùng `ci-deploy-aws.pem` của người vận hành:

```bash
ssh-keygen -t ed25519 -N "" -C github-actions-deploy -f ./deploy_key
ssh -i ~/.ssh/ci-deploy-aws.pem ubuntu@52.63.103.239 'cat >> ~/.ssh/authorized_keys' < ./deploy_key.pub
ssh-keyscan -t ed25519 52.63.103.239   # so với khoá đã thấy khi SSH lần đầu
```

User `ubuntu` trên EC2 có `sudo` không hỏi mật khẩu, đúng như workflow cần.

### 3. Checkout trên app server theo `develop`

App server đang chạy nhánh `feature/code-full`, vì `compose.db.yml` và bản sửa Caddy chưa có trên `develop`. Sau khi PR #77 merge:

```bash
ssh -i ~/.ssh/ci-deploy-aws.pem ubuntu@52.63.103.239 \
  'cd /opt/contract-intelligence && sudo git fetch origin develop && sudo git checkout develop && sudo git merge --ff-only origin/develop'
```

### 4. Đổi secrets, sau khi đã chuyển dữ liệu

Đổi secrets **sau** bước chuyển dữ liệu và DNS ("Chuyển sang máy mới cùng dữ liệu" trong `deploy/README.md`). Đổi sớm hơn thì các lần merge sẽ deploy vào server thử, còn prod vẫn ở server cũ.

| Secret | Giá trị mới |
|---|---|
| `DEPLOY_HOST` | `52.63.103.239` (Elastic IP, không đổi khi stop/start) |
| `DEPLOY_USER` | `ubuntu` |
| `DEPLOY_SSH_KEY` | Nội dung `deploy_key` ở bước 2; xoá file sau khi đặt |
| `DEPLOY_KNOWN_HOSTS` | Dòng `ssh-keyscan` ở bước 2 |
| `DEPLOY_DB_PUBLIC_IP` | Bỏ trống, hoặc gắn Elastic IP cho DB server rồi điền (thêm khoảng $3,6/tháng) |

Cùng lúc đặt các **repo variable** (Settings → Secrets and variables → Actions → Variables, hoặc `gh variable set`): `DEPLOY_SECURITY_GROUP_ID=sg-070e3d258f1793c3e` và `DEPLOY_AWS_REGION=ap-southeast-2` để bật bước mở/đóng cổng 22, và `DEPLOY_BEHIND_CLOUDFLARE=true` khi các tên miền đứng sau Cloudflare. Biến cuối cho bước kiểm tra từ bên ngoài dò cổng trên `DEPLOY_HOST` thay vì địa chỉ của Cloudflare, và kiểm rằng máy chủ từ chối 80/443 với người gọi không phải Cloudflare.

DB server chỉ có IP công khai tự cấp, nên **IP này đổi mỗi lần stop/start**. Điền `DEPLOY_DB_PUBLIC_IP` mà không gắn Elastic IP thì sau lần start tiếp theo, bước kiểm tra sẽ kiểm nhầm một IP không còn là của mình.

### 5. Chạy thử một lần

Actions → `deploy` → Run workflow trên `develop`, xem đủ ba bước xanh, rồi mới bật người duyệt cho `production`.

## Khi server đang stop

Hai máy AWS được stop ngoài giờ demo để tiết kiệm credit. Khi đó workflow `deploy` sẽ fail ở bước SSH (timeout). Có hai cách xử lý:

- Bật máy trước khi merge: start `ci-db` trước, rồi `ci-app`.
- Tạm dừng deploy tự động bằng cách xoá secret `DEPLOY_HOST`, rồi đặt lại khi cần (với workflow hiện tại).

## Quay lại bản trước

Workflow chỉ đi tới, không có nút rollback. Cách an toàn nhất là revert commit gây lỗi trên `develop` bằng một PR. Merge PR đó sẽ deploy lại bản cũ qua đúng đường thường. Không nên `git checkout <sha cũ>` tay trên server: checkout sẽ lệch khỏi `develop` và lần deploy sau bị chặn vì không fast-forward được.

## Sự cố thường gặp

| Triệu chứng | Nguyên nhân | Xử lý |
|---|---|---|
| Bước SSH timeout | Server đang stop, hoặc security group không cho IP của runner | Bật server; kiểm tra đã đặt variable `DEPLOY_SECURITY_GROUP_ID` và bước "Open SSH" chạy xanh |
| Bước "Open SSH" báo `AuthFailure`/`InvalidClientTokenId` | Access key của `ci-github-deploy` sai hoặc đã bị xoá | Tạo key mới, đặt lại `AWS_DEPLOY_ACCESS_KEY_ID`/`AWS_DEPLOY_SECRET_ACCESS_KEY` |
| `Host key verification failed` | Server được tạo lại nên đổi khoá host | `ssh-keyscan` lại, so tay, cập nhật `DEPLOY_KNOWN_HOSTS` |
| `Not possible to fast-forward` | Checkout trên server có commit riêng, hoặc đang ở nhánh khác | SSH vào xem `git status` và `git log`, đưa về `develop` |
| `database … does not answer; nothing was restarted` | DB server đang stop, sai IP/cổng, hoặc security group `ci-db` | Bật `ci-db`; kiểm tra `BACKEND_DB_*`/`KEYCLOAK_DB_*` trong `deploy/.env.prod` |
| `AI2 providers are not ready … nothing was restarted` | Key LLM/embedding sai hoặc nhà cung cấp lỗi | Xem `/tmp/ai2-preflight.log` trên server; sửa key trong `deploy/.env.prod` |
| Smoke test `Failed to connect … port 443` | Caddy không chạy. Đã gặp ngày 14/10: site frontend khai báo hai lần trong `Caddyfile` và `frontend.caddy` (sửa ở `0a23948`) | `docker logs ci-caddy` |
| `check_external.sh` báo một cổng nội bộ mở | Một service bị publish cổng ra ngoài | Xem `ports:` trong `deploy/compose.prod.yml`; trên AWS xem cả security group |

## Việc đang mở

- **PR #85 viết lại `deploy.yml`.** PR #77 thêm bước kiểm DB server và hai bước mở/đóng cổng 22; PR nào merge sau phải gộp tay các bước này vào. Thêm job kiểm tra chạy trên PR vào `develop`; chỉ cho deploy từ `develop`; deploy đúng SHA bằng `git checkout --detach`; fail (thay vì bỏ qua) khi thiếu secret; từ chối deploy khi checkout trên server có thay đổi hoặc file chưa track. Sau khi #85 merge, tài liệu này cần cập nhật các mục "Các bước", "Chạy tay" và "Khi server đang stop".
- Server cũ có hai file chưa track `deploy/.env.prod.bak-*`. Với luật mới của #85, hai file này sẽ chặn deploy cho tới khi được dọn đi.
- Chưa bật người duyệt cho `production`: PR đã đủ 2 approve thì merge xong là deploy ngay.
