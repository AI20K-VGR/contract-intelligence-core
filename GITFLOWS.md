# Git workflow

Tài liệu này quy định cách cộng tác trên repository `contract-intelligence-core`. Mục tiêu là
giữ `main` và `develop` luôn có thể build, kiểm thử và triển khai.

## Mô hình nhánh

| Nhánh | Mục đích | Push trực tiếp |
| --- | --- | --- |
| `main` | Mã đã được chấp thuận để release, demo ở sprint review | Không |
| `develop` | Nhánh tích hợp, target mặc định của mọi pull request | Không |
| `feat/<slug>`, `feature/<slug>` | Tính năng mới | Chỉ người phụ trách |
| `fix/<slug>` | Sửa lỗi thông thường | Chỉ người phụ trách |
| `hotfix/<slug>` | Sửa lỗi production khẩn cấp, tạo từ `main` | Chỉ người phụ trách |
| `docs/<slug>` | Thay đổi chỉ liên quan tài liệu | Chỉ người phụ trách |
| `chore/<slug>`, `refactor/<slug>`, `test/<slug>`, `release/<slug>` | Bảo trì, tái cấu trúc, test, chuẩn bị release | Chỉ người phụ trách |

Dùng chữ thường và dấu gạch ngang, không dấu tiếng Việt, ví dụ `feature/backend-upload-api` hoặc
`fix/bbox-offset-page-2`. Tên nhánh phải khớp
`^(feat|feature|fix|docs|chore|refactor|test|hotfix|release)/[a-z0-9._-]+$` — check `pr-guard` tự
động chặn pull request nếu sai.

## Quy trình hằng ngày

Tạo nhánh mới từ `develop` đã cập nhật:

```bash
git switch develop
git pull --ff-only origin develop
git switch -c feature/short-description
```

Trong quá trình làm việc:

```bash
git status --short
git diff
git add path/to/file
git commit -m "feat(scope): concise description"
```

Đồng bộ với nhánh tích hợp trước khi mở pull request:

```bash
git fetch origin
git rebase origin/develop
git push --set-upstream origin feature/short-description
```

Nếu nhánh đã được chia sẻ và cần cập nhật sau rebase, chỉ dùng
`git push --force-with-lease`; không dùng `--force`.

## Commit convention

Sử dụng Conventional Commits với scope là subsystem:

| Type | Khi sử dụng |
| --- | --- |
| `feat` | Thêm hành vi hoặc khả năng mới |
| `fix` | Sửa lỗi |
| `refactor` | Đổi cấu trúc mà không đổi hành vi |
| `docs` | Chỉ thay đổi tài liệu |
| `test` | Thêm hoặc sửa test |
| `ci` | Pipeline và automation |
| `chore` | Công việc bảo trì khác |

Định dạng bắt buộc cho tiêu đề pull request (commit lẻ trong nhánh có thể lỏng hơn):

```text
<type>(<scope>): <mô tả ngắn ở thể mệnh lệnh>
```

`scope` chỉ được là một trong: `frontend | backend | ai | ai-service | docs | infra | repo`.
`pr-guard` chặn tự động pull request có tiêu đề không đúng định dạng này.

Ví dụ:

```text
feat(ai): clause segmentation for Article > Clause > Point
fix(backend): batch job status stuck in queued
docs(docs): clarify PostgreSQL local setup
```

Mỗi commit nên có một mục đích có thể review độc lập. Không trộn formatting,
refactor và thay đổi hành vi không liên quan trong cùng commit.

## Pull request

Mỗi pull request phải có:

- mô tả vấn đề và giải pháp;
- phạm vi thay đổi (frontend/backend/ai/docs) và phần cố ý không thay đổi;
- cách kiểm thử, kèm lệnh hoặc bằng chứng;
- migration, environment variable hoặc compatibility impact nếu có;
- ảnh hoặc video cho thay đổi UI đáng kể;
- liên kết issue/task liên quan (`Closes #12`).

Điều kiện merge:

1. Có ít nhất **2** reviewer khác approve (không tự-approve).
2. Check bắt buộc `pr-guard`, cùng CI của thư mục bị đổi khi đã bật, đều pass.
3. Không còn conversation chưa được xử lý.
4. Nhánh không xung đột và đã cập nhật với nhánh đích.
5. Tài liệu và migration được cập nhật cùng code nếu contract thay đổi.

Merge vào `main` bắt buộc **squash + linear history**. Merge vào `develop` chấp nhận mọi phương
thức; ưu tiên squash cho nhánh có nhiều commit sửa vặt.

## Hotfix production

Tạo hotfix từ `main`:

```bash
git switch main
git pull --ff-only origin main
git switch -c hotfix/short-description
```

Pull request vào `main` chỉ được `pr-guard` chấp nhận nếu tạo từ `hotfix/*`, `release/*` hoặc
`develop`. Sau khi pull request vào `main` được merge và release đã xác minh, tạo thêm một pull
request đưa cùng thay đổi trở lại `develop`. Không bỏ qua bước này vì lỗi sẽ tái xuất hiện ở release
tiếp theo.

## Branch protection

Áp dụng cho cả `main` và `develop` qua GitHub ruleset:

- yêu cầu pull request trước khi merge;
- yêu cầu tối thiểu 2 approval;
- yêu cầu status check `pr-guard` (và CI subsystem khi được bật) pass, nhánh cập nhật với đích;
- từ chối force-push và xóa nhánh trực tiếp;
- yêu cầu xử lý hết review conversations;
- `main` chỉ nhận pull request từ `develop`, `release/*` hoặc `hotfix/*`;
- giới hạn quyền bypass cho mentor.

Tên status check phải khớp pipeline hiện hành trong `.github/workflows/` (`pr-guard`, và
`backend`/`frontend`/`ai-service` khi được bật làm required check).

## Xử lý secret và dữ liệu nhạy cảm

- Không commit hợp đồng thật/test, bản scan, annex hay archive của chúng. `pr-guard` tự động chặn
  file `.pdf .doc .docx .tif .tiff .jpg .jpeg .png .zip .rar .7z` ngoài `docs/assets/`.
- Không commit `.env`, API key hoặc credential. GitHub push protection chặn định dạng secret đã biết.
- Nếu secret hoặc dữ liệu hợp đồng đã vào lịch sử Git, việc xóa file ở commit mới là chưa đủ: phải
  rotate secret và thực hiện quy trình làm sạch lịch sử được mentor phê duyệt.
- Dữ liệu dùng để kiểm thử/đánh giá nằm ở OneDrive chung; code đọc qua đường dẫn từ biến môi trường,
  không bao giờ đọc từ trong repo.

## Checklist trước khi push

- [ ] `git diff --check` không báo whitespace error.
- [ ] Chỉ stage file thuộc phạm vi task, không kèm hợp đồng/scan/secret.
- [ ] Test và lint của thư mục bị đổi (`backend`/`frontend`/`ai-service`) đã chạy.
- [ ] Tên nhánh và tiêu đề pull request đúng convention.
- [ ] README/docs/API spec đã cập nhật nếu contract thay đổi.
