# Research: Cách dùng sdlc-harness-release và vì sao Codex tự gọi skill

**Mode**: depth
**Date**: 2026-09-26
**Sources reviewed**: 4

## Summary

Repo công khai là showcase + bundle cài, không phải source harness. Cài vào repo đích bằng `install.ps1` / `install.sh`. Codex tự gọi skill vì installer copy `SKILL.md` vào `.codex/skills/` và Codex liệt kê `name` + `description` cho model mỗi lượt — model khớp mô tả với câu hỏi rồi đọc skill. Hook Codex không chạy cho đến khi user trust file hook.

## Options / Comparison

| Lớp | Việc nó làm | Có tự chạy không |
|---|---|---|
| Skill (`.codex/skills/*/SKILL.md`) | Prose chỉ dẫn; `description` được liệt kê cho model | Có — Codex nạp native |
| `AGENTS.md` → `CLAUDE.md` | Nhắc dùng `/hs:<tên>` | Có — file chỉ dẫn project |
| Hook (`.codex/hooks.json`) | Gate thật (Bash, SessionStart, …) | Không — untrusted cho đến khi trust lúc khởi động |

## Recommendation

**Priority 1**: Dùng luồng `plan → cook → test → code-review → ship`. Với Codex, mô tả việc bằng ngôn ngữ thường cũng đủ để skill khớp `description` được chọn.

**Fallback**: Gọi thẳng `/hs:<tên>` khi muốn ép skill, hoặc `/hs:find-skills` khi không chắc tên.

## Evidence and references

[1] https://raw.githubusercontent.com/hieubui2409/sdlc-harness-release/main/README.md | hieubui2409 | 2026-09-26 fetch | VERIFIED (doc, chưa chạy installer)
[2] `harness/data/runtime-targets.yaml:95-101` | local | — | VERIFIED — Codex đọc `.codex/skills`, `.codex/hooks.json`, `AGENTS.md`
[3] `.harness/runtimes/codex/INSTALL.md:17-23` | local install | — | VERIFIED — "Loaded verbatim by the runtime and listed to the model under the name each one declares"
[4] `harness/install/_runtime_wire.py:381-385` | local | — | VERIFIED — skill bật được inject vào danh sách của model mỗi lượt; skill tắt không được copy lại

## Open questions

- [PRIOR] Câu chữ chính xác trong system prompt của Codex CLI ("khi description khớp thì đọc SKILL.md") chưa đọc từ binary Codex trong phiên này. Neo chắc là file được liệt kê cho model (`INSTALL.md:23`), không phải prompt nội bộ.
- One-liner README cài runtime Claude. Chiếu sang Codex cần `--runtime codex` trên installer (`harness/install/install.py:568-571`). Chưa chạy lại installer trong phiên này.
