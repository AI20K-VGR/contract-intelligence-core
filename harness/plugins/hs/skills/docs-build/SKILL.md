---
name: hs:docs-build
injectable: false
description: Đổ docs (md+frontmatter) + _index (graph+bands.yaml) + _present (presentation) → public/ (showcase HTML giữ theme/hiệu ứng) + dist/ (flat-md, pdf, excel). Nội dung sống ở md vật lý. Legacy showcase.yaml gộp = back-compat.
argument-hint: "[--docs docs] [--out public] [--dist dist]"
allowed-tools: [Bash, Read, Glob]
metadata:
  compliance-tier: workflow
---

# hs:docs-build — render docs → public/ + dist/

Đổ nội dung `docs/**/*.md` (frontmatter + body) + `_index/` (graph + `bands.yaml`) + `_present/` thành:
- **`public/`** — showcase HTML (giữ theme + hiệu ứng tương tác dim/highlight/dialog).
- **`dist/`** — bản phát hành: flat-md (gộp), pdf, excel.

**Nguyên tắc nội dung**: nội dung sống ở **md vật lý**. Sau split (C1): design taxonomy (`band`/`cluster` + `bands`) ở `_index/bands.yaml`; presentation (`pages`/`categories`/`asset_slots`/ `footer_pages`/`theme`/`order`/`sections`/`text_fix`) ở `_present/*`. Legacy `showcase.yaml` gộp = back-compat (shim split-read). Build KHÔNG sinh nội dung — chỉ render cái đã có.

**Ranh giới CỨNG** (lặp ở cả 3 skill docs-*): skill **không sáng tạo nội dung thiết kế**,
**không debate chất lượng**. Build là thuần render; cấu trúc phải đã PASS `hs:docs-standardize`.

> Scripts build nằm trong `skills/docs-build/scripts/` (10 file: `build_showcase.py`,
> `build_flat_md.py`, `build_pdf.py`, `build_excel.py`, `build_all.py`, `ssg_engine.py`,
> `e2e_static.py`, `e2e_browser.mjs`, `render_md_page.py`, `_selfcheck.py`).
> Tài liệu này mô tả **hợp đồng input/output/hành vi**.

## Tiền điều kiện

- `hs:docs-standardize` PASS (0 error) — build trên docs đã hợp khế ước cấu trúc.
- `docs/_present/*` (presentation: pages/categories/asset_slots/footer_pages/theme) + `_index/bands.yaml` (taxonomy) tồn tại; legacy `showcase.yaml` gộp vẫn chạy qua shim. Showcase data JS sinh qua `_docslib/docslib/graph.py :: generate_showcase_data(model, out_dir)`
  → `module-m4-data.js`, `ptnt-layers-data.js`, `ptnt-clusters-data.js`, `part-modref-data.js`.

## Hợp đồng (input → output)

| Script | Input | Output |
|---|---|---|
| `build_showcase.py` | `docs/`, `_present/*` + `_index/bands.yaml` (legacy `showcase.yaml` gộp qua shim), `assets/` | `public/` (HTML + theme + JS data) |
| `build_flat_md.py` | `docs/`, `_present/*` (section order; legacy `showcase.yaml` qua shim) | `dist/<name>.md` (gộp theo section order) |
| `build_pdf.py` | flat-md / HTML | `dist/<name>.pdf` |
| `build_excel.py` | `_index/*.yaml` + frontmatter | `dist/<name>.xlsx` (ma trận module/part/config) |

Chi tiết pipeline (md→html, thứ tự section, dependency, điểm CI): `references/render-pipeline.md`. E2E test spec: `references/e2e.md`. Default shell bundle: `default-theme/`.

Chi tiết luồng render thực (`build_showcase.py` sinh data-JS → `render_md_page.py` chuyển md→HTML partial → assembler đóng gói `public/`; assembler = `docs/showcase/build.py`, **consumer-repo-owned adapter gọi qua subprocess, không thuộc 10 script shipped ở đây**): `references/render-pipeline.md`.

## Step-by-step

1. **Gate trước** — chạy `hs:docs-standardize` (`docs_gate.py --fresh`); 0 error mới build. Nếu có glossary (`docs/glossary.yaml`), seed bảng thuật ngữ vào docs sinh ra qua `glossary_register.py --root . --list` (schema chung term/definition/forbidden/backing); vắng file → bỏ qua êm.
2. **Sinh showcase data** — `generate_showcase_data(model, docs/showcase/assets/js)` → 4 file `*.js`.
3. **Render showcase** — `build_showcase.py` đổ md→html + theme/assets → `public/`.
4. **Render dist** — `build_flat_md.py` → `build_pdf.py` → `build_excel.py` → `dist/`.
5. **Xác minh** — mở `public/index.html`; kiểm hiệu ứng tương tác + thứ tự section đúng showcase.yaml.

## presentation/taxonomy quản gì (sau split C1)

Presentation → `_present/*` (legacy gộp: `showcase.yaml`):
- `pages[]` — `{key, en, vi, partial, title, accent, empty}` (tên page + partial html + accent color).
- `categories[]` — `{key, en, vi, pages[]}` (nhóm sidebar, song ngữ).
- `asset_slots` — `{js[], css[], vendor[]}` (danh sách part file; `@generated` expand ra 4 data-JS).
- `footer_pages[]` — `{key, vi, en}` (link footer bar, thứ tự tùy chỉnh).
- `theme` — theme name (mặc định `default-theme`).
- `text_fix[]` — chuỗi sửa hiển thị nhỏ (không đổi md nguồn).

Design taxonomy → `_index/bands.yaml` (KHÔNG ở presentation):
- `bands[]` — `{id, cluster_vi, cluster_en}` (legend layer view, song ngữ) + per-module `band`.

KHÔNG quản nội dung. Đổi `detail`/`order` = đổi cách render, không đổi md nguồn.

## Ranh giới (không làm)

- KHÔNG sinh/sửa nội dung md — chỉ render.
- KHÔNG build khi `hs:docs-standardize` còn error.
- KHÔNG đổi `_index/*.yaml` (việc của standardize/migrate).

## Related skills

- `hs:deploy`: sau build PASS, publish `public/` lên GitHub/GitLab Pages (tự nhận diện "Static site (HTML/CSS/JS)" → Pages). docs-build chỉ render, không deploy.
