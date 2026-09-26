---
phase: 1
title: "Hygiene"
status: pending
plan: 260926-2107-repo-hygiene-restructure
created: 2026-09-26
harness_version: 6.3.0
harness_kit_digest: 672de2e098c3cb8451018791788f1052b1b812ccec08a1f124191bd8bbc04ebd
harness_schema_version: 1.0
---

# Phase 1 — Hygiene

## Overview

Gỡ 5 nhóm artifact ra khỏi git index bằng `git rm --cached` (giữ nguyên trên đĩa),
mở rộng `.gitignore` để cache local không lọt lại vào index, và thêm một script
kiểm tra chạy được để khoá kết quả. KHÔNG chuyển/đổi/xoá bất kỳ file logic nào.
Đây là phase gốc, không phụ thuộc phase khác.

## Requirements

Functional:
- `git ls-files` KHÔNG còn liệt kê: `apps/web/node_modules/**` (448 file),
  `apps/web/.vite/**` (2 file), `output/**` (15 file), root `ocr-result.json`,
  root `result_khoiluong.json` — đã đếm bằng git 2026-09-26.
- Mọi path ở trên VẪN còn trên đĩa (gỡ `--cached`, không xoá file).
- `.gitignore` chặn: root `/node_modules/`, `/apps/web/node_modules/`, `/apps/web/.vite/`, `/output/`, `ocr-result.json`,
  `result_khoiluong.json`, `.pytest-*` (basetemp đặt tên tay), `.uv-cache-*`,
  `backend/backend/`, `tmp/`, `.tmp-*`.

Non-functional:
- Không đụng file sản phẩm chưa commit (danh sách ở `plan.md` → Ràng buộc).
- Một commit riêng cho hygiene (do cook), không trộn sửa logic.

## Related Code Files

- **Modify:** `.gitignore` — thêm khối "Repo hygiene (P1)" với các pattern trên.
  Giữ nguyên ngoại lệ có sẵn `.gitignore:15-16` (`!docs/assets/**`, không ignore
  `frontend/src/data`).
- **Create:** `scripts/check_repo_hygiene.py` — script Python cross-platform:
  chạy `git ls-files` với 5 path, assert rỗng; chạy `git check-ignore` cho mẫu
  cache, assert được ignore; assert 5 path còn tồn tại trên đĩa. Exit 0 = xanh.
- **Gỡ khỏi index (git rm --cached, KHÔNG xoá đĩa):** `apps/web/node_modules/`,
  `apps/web/.vite/`, `output/`, `ocr-result.json`, `result_khoiluong.json`.
  (Không phải file create/modify — là thao tác index; cook chạy khi commit.)

## File inventory (--deep)

| Path | Action | Cỡ | Test impact |
|---|---|---|---|
| `.gitignore` | Modify | ~15 dòng thêm | Không ảnh hưởng runtime; đổi hành vi `git check-ignore` |
| `scripts/check_repo_hygiene.py` | Create | ~60 dòng | Là chính test/gate của phase |
| `apps/web/node_modules/**` | Rm --cached | 448 file tracked | 0 — không import từ product code (`research/...:14`) |
| `apps/web/.vite/**` | Rm --cached | 2 file tracked | 0 — build cache |
| `output/**` | Rm --cached | 15 file tracked | 0 — chỉ nơi GHI report (`research/...:17-19`) |
| `ocr-result.json` | Rm --cached | 1 file | 0 — không test nào đọc (`research/...:19-20`) |
| `result_khoiluong.json` | Rm --cached | 1 file | 0 — không test nào đọc (`research/...:19-20`) |

## Test scenario matrix (--deep)

| Ưu tiên | Scenario | Kỳ vọng |
|---|---|---|
| Critical | `git ls-files apps/web/node_modules` sau khi gỡ | rỗng |
| Critical | 5 path còn trên đĩa sau `rm --cached` | tồn tại (không mất file) |
| Critical | `git check-ignore -q node_modules/x` | ignored (exit 0) |
| High | `git check-ignore -q output/foo`, `ocr-result.json`, `result_khoiluong.json` | ignored |
| High | `git check-ignore -q .pytest-review-r2-ai2/x`, `.uv-cache-x/y`, `backend/backend/x` | ignored |
| Medium | `git check-ignore` cho `frontend/src/data/mock.ts` (source) | KHÔNG ignored (âm tính — không chặn nhầm source) |
| Medium | `apps/web/.vite` không còn tracked | rỗng |

## Dependency map (--deep)

- Phụ thuộc: không (phase gốc).
- Bị phụ thuộc bởi: Phase 2 (edge P1→P2 trong `plan-graph.yaml`). P2 giả định index
  đã sạch và `.gitignore` đã có `backend/backend/` trước khi guard bằng
  `test_repo_layout.py`.
- File dùng chung: `.gitignore` do P1 sở hữu HOÀN TOÀN (P2 không sửa) để tránh
  đụng cùng file.

## TDD

### Tests Before (RED — viết trước khi sửa)
- [ ] `check_repo_hygiene.py` assert `git ls-files apps/web/node_modules` rỗng →
  chạy hiện tại **FAIL** (448 file đang tracked). Khoá: artifact vendored phải rời index.
- [ ] Assert `git check-ignore -q backend/backend/x` → hiện tại **FAIL** (chưa có
  pattern). Khoá: cache nested phải bị ignore.
- Chạy: `python scripts/check_repo_hygiene.py` → phải đỏ trước khi implement.

### Implement
1. Thêm khối pattern hygiene vào `.gitignore` (danh sách ở Requirements), giữ ngoại lệ `.gitignore:15-16`.
2. Grep lại reference tới `output/` và 2 JSON để xác nhận không có fixture đọc (chốt `research/...:17-20`).
3. Copy `output/`, `ocr-result.json`, `result_khoiluong.json` sang `tmp/hygiene-backup/` (ngoài git) TRƯỚC khi đụng index. Assert `os.path.exists` trên 5 path TRƯỚC `git rm`.
4. `git rm -r --cached -- apps/web/node_modules apps/web/.vite output` và `git rm --cached -- ocr-result.json result_khoiluong.json` (không `-f`; `--` chặn flag). Cook mới chạy lúc commit.
5. Viết đủ `scripts/check_repo_hygiene.py`. Nếu không có `.git` hoặc không có binary `git`, script in lý do và exit 0 (skip) — suite sản phẩm không gọi script này. Khi có git: ls-files rỗng + check-ignore dương/âm + tồn tại-trên-đĩa.

### Tests After (hành vi mới)
- [ ] `python scripts/check_repo_hygiene.py` → **PASS** toàn bộ scenario Critical/High.
- [ ] Xác nhận 5 path vẫn còn trên đĩa (script assert `os.path.exists`).

### Regression Gate (lệnh thật)
`python scripts/check_repo_hygiene.py` — MUST PASS trước khi qua Phase 2.
Frontend suite (`cd frontend; npm test`) = **N/A cho phase này** — P1 KHÔNG đụng
`frontend/src`; gate là kiểm tra gitignore/ls-files ở trên.

## Success Criteria

- [ ] `git ls-files` rỗng cho cả 5 nhóm path (đo bằng lệnh, không "commit là xong").
- [ ] `git check-ignore` dương tính cho mẫu cache, âm tính cho `frontend/src/data/*`.
- [ ] 5 path còn trên đĩa (không mất file logic/sản phẩm).
- [ ] `scripts/check_repo_hygiene.py` exit 0.

## Risk Assessment

| Risk | Khả năng × Tác động | Mitigation |
|---|---|---|
| `git rm --cached` lỡ dính `-f` xoá đĩa | thấp × cao | Backup `tmp/hygiene-backup/` và assert tồn tại TRƯỚC lệnh; lệnh không có `-f`; commit riêng. |
| Pattern `.gitignore` chặn nhầm source | thấp × cao | Pattern hẹp + scenario âm tính `frontend/src/data`; giữ `.gitignore:15-16`. |
| `output/`/JSON hoá ra là fixture | thấp × trung bình | Grep lại ở bước Implement #2; file vẫn trên đĩa nên test đọc-đĩa vẫn chạy. |
| Diff khổng lồ 448+ file gây nhiễu review | cao × thấp | Một commit hygiene riêng, tách khỏi logic. |
