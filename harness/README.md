# harness/ — SDLC Harness (source of truth)

Bộ kỷ luật SDLC file-based cho Claude Code. Toàn bộ source nằm ở đây;
installer copy cây `harness/` vào ROOT repo đích (`<target>/harness/`) + merge hook
registration vào `.claude/settings.json` — cây KHÔNG nằm trong `.claude/`, và dev-loop
không đụng `.claude/`. Xóa thư mục này = gỡ sạch.

Tài liệu: `../docs/system-architecture.md` (thiết kế) · `../docs/code-standards.md`
(kỷ luật code) · `../docs/harness/deployment-guide.md` (cài đặt).

## Layout

| Dir | Vai trò |
|---|---|
| `hooks/` | hook_runtime (3-class) + gate/session/trace hooks |
| `scripts/` | stage_detector, artifact_check, fs_guard, DEC register, manifest, preflight |
| `plugins/` | one plugin `hs` (110 skills; 16 always-on floor = 13-skill SDLC spine + use + find-skills + cleanup, the other 94 default-off via `/hs:use`); invoke colon-form `hs:plan`, `hs:brainstorm`, … |
| `rules/` | harness-contract.md (luôn-load) + on-demand rules |
| `data/` | stage-policy.yaml, ownership.yaml, skill-chains.yaml, harness-hooks.yaml |
| `schemas/` | artifact JSON schemas |
| `standards/` | structured standards tree (vision/STACK/charter/areas + templates); prose SSOT pair (system-architecture + code-standards) lives in `docs/` |
| `install/` | hooks-registration.yaml + git pre-push hook |
| `state/` | runtime (gitignored): trace/ sessions/ telemetry/ claims/ locks/ |
| `e2e/` | fixture-mini + run_vertical_slice.py |
| `tests/` | pytest suite (TDD đỏ→xanh per module) |

## Lệnh

```bash
python3 harness/scripts/preflight_deps.py          # check các gói khai ở harness/requirements.txt (khoảng phiên bản + import)
python3 -m pytest harness/tests/ -q                # toàn bộ tests
python3 harness/scripts/build_manifest.py          # sinh manifest.json
python3 harness/scripts/verify_install.py --strict # so hash chống drift
```

## Ba hạng hook (tóm tắt — chi tiết: docs/system-architecture.md §3)

`HOOK_CLASS` khắc trong code từng hook. telemetry = ON fail-open · nudge = OFF
advisory · compliance = **ON blocking fail-closed** (crash/thiếu dep → exit 2 +
cách xử lý). Config `data/harness-hooks.yaml` chỉ override enabled/mode —
tracked git để mọi thay đổi lộ diff (tamper-visible).
