# P6 — Hướng dẫn máy mới và full-stack evidence

## Overview

Tạo một hướng dẫn chuẩn, chạy được từ clone sạch trên Windows PowerShell và Linux/macOS; hướng dẫn developer dựng toàn stack, cấu hình secrets cục bộ, đăng nhập, OCR, kiểm tra graph/citation, query và dọn stack. Sửa/điều hướng tài liệu cũ đang trỏ hai checkout và lệnh npm không reproducible (`HUONG-DAN-CHAY.md:5-64`; README quick start `README.md:73-110`).

## Requirements

- **Functional:** bao gồm prerequisites (Docker Desktop/Compose v2, Node 20+, uv/Python nếu chạy local), ports và `VITE_API_BASE_URL=http://127.0.0.1:8000` vì frontend fallback 8080 trong `frontend/src/api/client.ts:8` trong khi Compose Backend publish 8000 (`docker-compose.yml:366`); lệnh env/example, migrations, compose start/health/log/stop.
- **Product flow:** giải thích cần provider API keys và outbound egress để model thật chạy; dựng hồ sơ sample PDF an toàn; verify OCR completed, graph pair/operation có snapshot/job id và evidence, query LLM/vector khi consent/cap bật; UI opt-out trước khi chạy lại chứng minh deterministic path còn và không egress.
- **Security:** tuyệt đối không ghi keys vào git, issue, terminal transcript hoặc report; nói rõ `/health` embedding `NOT_RUN` không chứng minh vector; hướng dẫn xử lý degraded/missing key/timeout, ports, cleanup.
- **N/A gate:** tài liệu/config phase không cần TDD code mới; kiểm tra link/commands/copy-paste trên clean checkout và thực thi full system smoke checklist sau P1–P5.

## Related Code Files

**Create:**

- `docs/AI2-LOCAL-SETUP.md`

**Modify (ownership chỉ P6):**

- `README.md`
- `HUONG-DAN-CHAY.md`
- `deploy/README.md`

**Delete:** —

## Implementation Steps

1. Tạo canonical local guide với hai shell tracks (PowerShell; bash/zsh), một repo/branch checkout, chuẩn bị `.env` cục bộ từ sample; key examples dùng placeholder, thêm check gitignore/secrets và egress caveat.
2. Ghi rõ compose commands, API/UI URLs/ports, frontend `.env.local`, DB migration, health endpoints, logs, shutdown/cleanup và bước troubleshooting theo đúng files/commands đã cập nhật P1–P5. Dùng `npm ci`, không `npm install`.
3. Cập nhật `README.md` quick-start thành đường dẫn canonical; thay `HUONG-DAN-CHAY.md` cũ bằng hướng dẫn mới/redirect, bỏ đường dẫn stale `ci-backend` và `contract-intelligence-core`; bổ sung `deploy/README.md` link deploy/Environment gate.
4. Dogfood từ clean clone trên Windows PowerShell và ít nhất một môi trường POSIX (Linux hoặc macOS), không dựa vào `.env` cá nhân: làm theo hướng dẫn từng bước, ghi lỗi command/port và sửa hướng dẫn. Thử case không có provider key để xác nhận degraded/error trung thực; inference smoke thật chỉ khi người vận hành có key/egress hợp lệ. Nếu hướng dẫn tuyên bố Linux và macOS được hỗ trợ riêng, xác minh trên cả hai.
5. Sau docs update, chạy full CI từ final SHA và checklist E2E product với sample được phép; chụp evidence redacted (run URL/SHA, health states, job id + snapshot id, số graph edge, query state, consent test), tuyệt đối không lưu contract body/keys.

## Success Criteria

- [ ] Developer mới theo guide trên Windows PowerShell và ít nhất một môi trường POSIX (Linux hoặc macOS) đạt health + login + OCR + graph evidence + query smoke mà không dựa vào secrets đã có sẵn. Nếu guide hứa hỗ trợ Linux và macOS riêng, dogfood trên cả hai.
- [ ] API URL/ports match Compose; hướng dẫn không dùng stale two-checkout paths hoặc npm install.
- [ ] Thiếu provider key/egress có chỉ dẫn chẩn đoán rõ; không nhầm `/health` hoặc feature flag với inference thật.
- [ ] Clean checkout guide hoàn thành không lộ secret; links/commands được bấm/chạy; full required CI green trên SHA cuối.
- [ ] Actual deploy acceptance chỉ đạt nếu P5 external deployment smoke đã chạy trên develop; local dogfood không thay thế deploy evidence.

## Risk Assessment

**Trung bình × Cao:** docs đúng với máy tác giả nhưng thiếu `.env` hoặc ports trên checkout mới. **Mitigation:** clean clone/profile test, PowerShell và POSIX command blocks, ghi expected health/ports và lỗi thường gặp.

**Thấp × Rất cao:** ví dụ vô tình chứa credential hoặc hướng dẫn người dùng commit `.env`. **Mitigation:** chỉ placeholder, kiểm tra ignore rules, review secret hygiene trước artifact.

**Rollback:** revert docs/link nếu sai; không rollback app behavior. Giữ lại ghi chú lỗi clean-machine test trong plan reports để sửa vòng tiếp theo.
