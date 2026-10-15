# P5 — Deploy `develop` fail-closed và readiness

## Overview

Biến deploy sau merge/push vào `develop` thành bước có kết quả trung thực và có readiness thực: cấu hình thiếu thì fail, không skip xanh; Keycloak phải ready trước khi cấu hình realm; deploy chỉ xanh sau smoke external. Run `38200338190` đã fail khi xin Keycloak admin token dù Backend healthy và AI2 capability ready; không quy lỗi này cho AI2 model.

## Requirements

- **Functional:** workflow chỉ deploy trên develop/dispatch (`.github/workflows/deploy.yml:22-25`), deploy cùng SHA, kiểm tra 4 tên secret/host, fail rõ nếu thiếu/SSH/release config sai; concurrency còn nguyên. Keycloak readiness chờ trạng thái healthy và token acquisition retry có deadline, xử lý `TimeoutError` rõ. Probe external HTTPS/auth bắt buộc.
- **Ref guard:** `workflow_dispatch` chỉ hợp lệ khi `github.ref == refs/heads/develop`. Tạo preflight job không có production environment/secrets, job này fail tường minh cho mọi ref khác; deploy job có `needs: preflight` và chỉ gắn production environment sau preflight thành công. Test dispatch trên develop pass và feature ref fail; không dựa riêng vào job-level skip hoặc environment setting.
- **Security:** không in secret values; `known_hosts` vẫn pin host. Yêu cầu GitHub Environment chỉ deploy develop và approval theo repository policy được xác minh qua settings/API; workflow YAML không tự tạo Environment protection.
- **TDD:** fake Keycloak timeout rồi thành công, deadline hết, URL/config sai; workflow/config unit/validator test trước và sau. Không deploy thật trong unit tests.

## Related Code Files

**Create:**

- `deploy/tests/test_keycloak_configure.py`

**Modify (ownership chỉ P5):**

- `.github/workflows/deploy.yml`
- `docker-compose.yml`
- `deploy/deploy.sh`
- `deploy/keycloak_configure.py`

**Delete:** —

## Implementation Steps

1. Tạo regression tests cho `_admin_token()` (`deploy/keycloak_configure.py:49-93`): timeout transient→success; timeout liên tiếp tới deadline→non-zero actionable error; auth/config 4xx không retry vô hạn; assert không log token.
2. Thêm Keycloak healthcheck readiness (hiện healthcheck tắt/service_started tại `docker-compose.yml:174-178,269-271`), `depends_on: service_healthy`, timeout rõ và retry/backoff có giới hạn quanh admin token. Không swallow timeout và không retry 401 sai credentials.
3. Sửa workflow `deploy.yml:47-60,97`: mọi secret bắt buộc thiếu phải fail; không để check configured=false skip deploy+external verification nhưng job success. Kiểm tra deploy SHA, preserve concurrency và log chỉ tên trạng thái.
4. Chỉnh `deploy.sh:41-76` để chờ health/readiness có deadline, gọi cấu hình Keycloak sau service ready, dừng ngay khi command thất bại; ghi rõ điểm chẩn đoán mà không lộ env.
5. Thêm preflight job không có `environment` hoặc secrets để guard `workflow_dispatch` ref; deploy job phụ thuộc preflight. Test dispatch trên develop thành công và feature ref fail trước khi job production/environment được lên lịch. Validate push/dispatch paths, compose merge với production overlay và profiles; chạy shell/Python tests + YAML/action lint. Qua GitHub API/admin kiểm tra production environment branch/approval policy, develop required status checks (`backend`, `frontend`, `ai-service`, `pr-guard`) và deploy secret *names only*; không đọc values. Cấu hình required checks/environment policy trong cook khi quyền cho phép; nếu không có quyền, đánh dấu BLOCKED và không mở/merge PR.
6. Chạy deploy thử chỉ sau approval riêng, đủ host/secret/network, P1–P4 xanh và environment policy đúng; xác nhận deployed SHA, backend + AI2 readiness, Keycloak, external HTTPS/auth, AI2 egress/graph/query smoke. Nếu prerequisites chưa xác nhận, để deploy gate BLOCKED, không tạo claim success.

## Success Criteria

- [ ] `TimeoutError` được test; transient timeout phục hồi trong deadline, persistent timeout làm deploy fail nhanh với cause rõ.
- [ ] Thiếu một trong `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, `DEPLOY_KNOWN_HOSTS` không thể cho kết quả xanh kiểu skip.
- [ ] Dispatch từ `develop` deploy được; dispatch từ feature ref fail trong preflight job không có environment/secrets và không schedule deploy job.
- [ ] Compose chờ Keycloak healthy; deploy chờ health services và verify đúng SHA.
- [ ] Run thực có HTTPS/auth check và AI2 smoke sau khi đủ prerequisites; deploy summary phân biệt failure, not-run, success.
- [ ] GitHub environment/branch policy và required CI checks được quan sát cấu hình thực; nếu chưa, phase chưa đạt acceptance.

## Risk Assessment

**Trung bình × Rất cao:** retry gây deploy dài hoặc che credentials/config sai. **Mitigation:** bounded retry/deadline, chỉ retry transient timeout/connection; phân biệt 401/invalid config; external probe cuối là gate.

**Cao × Cao:** secrets có tên nhưng giá trị/host sai hoặc Environment không chặn nhánh khác. **Mitigation:** verify settings/secrets metadata không đọc values, push an toàn develop chỉ sau người vận hành xác nhận; fail closed; retain deploy rollback.

**Rollback:** revert workflow/compose/deploy fixes; pause push triggers theo vận hành nếu deployment lỗi; redeploy known-good SHA theo `deploy/README.md`, health/external probe lại. Không xoá/chỉnh secrets.
