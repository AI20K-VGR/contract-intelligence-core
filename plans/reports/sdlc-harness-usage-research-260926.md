# Research: Cách sử dụng SDLC Harness cho Claude Code

**Mode**: depth  
**Date**: 2026-09-26  
**Sources reviewed**: 5

## Summary

- Đây là lớp kỷ luật file-based cho Claude Code: `/hs:plan` → `/hs:cook` → `/hs:test` → `/hs:ship`.
- Skills chỉ hướng dẫn; hook/runtime gate mới là lớp kiểm tra thực tế.
- Repo hiện tại đã có `harness/`, plugin `hs` và hook wiring; phiên terminal được kiểm tra chưa có Python trên `PATH`, nên CLI chưa chạy được.
- Khuyến nghị: cài Python ≥3.9, restart Claude Code, chạy `hs:setup`, rồi dùng quy trình xương sống cho mọi thay đổi có logic.

## Quick Start

### 1. Cài vào repository mới

Windows PowerShell:

```powershell
irm https://hieubui2409.github.io/sdlc-harness-release/install.ps1 | iex
```

Có thể ghim phiên bản bằng `-Version 6.3.0`; nên đọc bootstrap hoặc chạy dry-run trước khi cài. Máy đích cần Python ≥3.9, Git và Claude Code.

Linux/macOS/WSL:

```sh
curl -fsSL https://hieubui2409.github.io/sdlc-harness-release/install.sh | sh -s -- . --run-tests
```

Installer xác minh checksum nếu có sidecar, chặn tar path traversal, kiểm tra dependency, cài và verify strict; test suite là tùy chọn.

### 2. Khởi động trong Claude Code

Sau khi cài, restart Claude Code hoặc chạy `/reload-plugins`. Với workspace hiện tại, plugin `hs@hs-local` đã được khai báo trong `.claude/settings.json`.

Chạy `/hs:setup` một lần để cấu hình voice, guard/stage policy, output language và các component cần thiết. Thay đổi guard/stage cần session mới.

### 3. Vòng đời hằng ngày

1. `/hs:plan --hard --tdd <mô tả thay đổi>` — nghiên cứu, quét ràng buộc, thiết kế phase, red-team và tạo plan trong `plans/`.
2. Người dùng review và approve plan.
3. `/clear`, sau đó `/hs:cook <absolute-plan-path>` — thực thi từng phase, thường theo TDD đỏ → xanh.
4. `/hs:test` — chạy kiểm thử và tạo verification artifact.
5. `/hs:code-review` hoặc `/hs:review-pr` — review thay đổi.
6. `/hs:ship` — kiểm tra receipt/artifact, review và yêu cầu người dùng xác nhận trước push/PR.

Nếu gặp lỗi: `/hs:triage` → reproduce → debug → fix → test.

### 4. CLI vận hành

Trong repo project-local, dùng `harness/bin/hs-cli.cmd` trên Windows hoặc `harness/bin/hs-cli` trên POSIX. Engine dùng `harness/bin/hs-run`/`.cmd`.

Các lệnh nền:

```text
hs-cli doctor
hs-cli list
hs-cli skills --on <name>
hs-cli skills --off <name>
hs-cli components
hs-run plan next
hs-run cook next
hs-run test next
hs-run ship next
```

`hs-run <domain> next` là cửa duy nhất để biết bước deterministic tiếp theo; đọc JSON envelope và `next_action`, không tự suy diễn state. Skill tắt dùng `/hs:use <name>`, không gọi raw `/hs:<name>`.

## Common Pitfalls

- Không bỏ qua plan approval để vào cook; cook yêu cầu plan đã được người dùng duyệt.
- Không coi `[advisory]` local là gate ship thành công; artifact/receipt vẫn phải tồn tại.
- Không chạy `skills --on/--off` hoặc đổi guard/stage mà quên restart Claude Code.
- `HARNESS_BIN_ROOT` và `HARNESS_DATA_ROOT` phải trỏ đúng project/engine; gọi bare path từ sai thư mục có thể dùng nhầm project.
- Checksum chỉ chứng minh archive không bị hỏng hoặc thay đổi so với sidecar; release hiện không có build provenance attestation.

## Workspace-specific finding

- `CLAUDE.md:5-12`: workspace yêu cầu dùng `hs-run`, `hs-cli`, `HARNESS_BIN_ROOT` và `HARNESS_DATA_ROOT`.
- `harness/plugins/hs/README.md:8`: plugin local là version `6.3.0`.
- `.claude/settings.json`: plugin `hs@hs-local` và các hook `PreToolUse`/`PostToolUse` đã được khai báo.
- `harness/state/install-state.json:73`: `hooks_wired` là `true`.
- Probe ngày 2026-09-26: `Get-Command py,python,python3` không trả về interpreter; cần cài Python trước khi xác minh CLI bằng runtime.

## Recommendation

**Priority 1**: cài Python ≥3.9 và restart Claude Code; sau đó chạy `/hs:setup`.  
**Fallback**: nếu chỉ muốn xem catalog, đọc `harness/plugins/hs/README.md`; nếu muốn làm thay đổi code, bắt đầu bằng `/hs:plan --fast` cho thay đổi nhỏ hoặc `--hard --tdd` cho feature/refactor.

## Evidence and references

[1] https://github.com/hieubui2409/sdlc-harness-release | repository README | 2026-09-26 | VERIFIED  
[2] https://raw.githubusercontent.com/hieubui2409/sdlc-harness-release/main/install.ps1 | official PowerShell installer | 2026-09-26 | VERIFIED  
[3] https://raw.githubusercontent.com/hieubui2409/sdlc-harness-release/main/install.sh | official POSIX installer | 2026-09-26 | VERIFIED  
[4] https://github.com/hieubui2409/sdlc-harness-release/releases | official releases and v6.3.0 notes | 2026-09-26 | VERIFIED  
[5] `CLAUDE.md:5-12`, `harness/plugins/hs/README.md:8`, `.claude/settings.json`, `harness/state/install-state.json:73` | current workspace | 2026-09-26 | VERIFIED

## Open questions

- [ASSUMED] Claude Code trong môi trường người dùng sẽ nạp được plugin local sau restart; cần xác minh bằng một phiên Claude Code thực tế.
- Cần quyết định có cài thêm runtime target ngoài Claude Code hay không; không cần cho quy trình Claude Code cơ bản.
