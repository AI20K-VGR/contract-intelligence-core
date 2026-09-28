# Render pipeline

Mô tả **hợp đồng render**. Scripts build + `assets/` đã hiện thực ở P4; tài liệu này mô tả input/output contract thực tế.

## Tổng quan luồng

```
docs/**/*.md (frontmatter+body)          ┐
docs/_index/bands.yaml (taxonomy band)   ├─► load_model ─► generate_showcase_data ─► <out-dir>/assets/js/*.js
docs/_present/* (order/sections/detail)  │                                          │
docs/_index/{modules,foundations,        │                                          ▼
            safety}.yaml                 ┘   build_showcase.py + assets/  ─► public/ (HTML+theme+JS)
                                              build_flat_md.py             ─► dist/<name>.md
                                              build_pdf.py                 ─► dist/<name>.pdf
                                              build_excel.py               ─► dist/<name>.xlsx
```

Nội dung sống ở **md vật lý**. Sau split (C1): design taxonomy (`band`/`cluster`) ở `_index/bands.yaml`; presentation (`order`/`sections`/`detail`/`text_fix`) ở `_present/*`. Legacy `showcase.yaml` gộp = back-compat (shim split-read tới khi migrate).

## md → html

1. Tách frontmatter + body mỗi `.md` (dùng `_docslib/docslib/frontmatter.py :: parse`).
2. Body Markdown → HTML qua thư viện `markdown` (extensions gợi ý: `tables`, `fenced_code`, `toc`, `attr_list`).
3. Gắn theme/CSS/JS từ `assets/`; giữ hiệu ứng tương tác (dim/highlight/dialog) của showcase baseline top-down 3 lớp.
4. Showcase data (graph) KHÔNG render từ prose mà sinh từ `_index/` qua `graph.generate_showcase_data(model, docs/showcase/assets/js)` (assembler bundle 4 file này cùng JS_PARTS → `public/assets/showcase.js`):
   - `module-m4-data.js` → `MOD_M4` (band/parts/configParts/consumes/feeds mỗi module).
   - `ptnt-layers-data.js` → `PTNT_LAYERS` (bands/l3/l4/foundations/safety).
   - `ptnt-clusters-data.js` → `PTNT_CLUSTERS` (clusters MOD-free + links + safety).
   - `part-modref-data.js` → `PART_MODREF` (owner/consumers/universal mỗi part).
   File `*.js` có banner GENERATED — đừng sửa tay.

## Assembler nội bộ (`docs/showcase/build.py`, consumer-repo, gọi qua subprocess)

`build_showcase.py` (script shipped ở đây) làm 2 bước rồi shell ra assembler thực:
1. Đọc model (`_present/*` + `_index/bands.yaml`, legacy `showcase.yaml` qua shim) → sinh 4 data-JS (`module-m4-data.js`, `ptnt-layers-data.js`, `ptnt-clusters-data.js`, `part-modref-data.js`).
2. Mỗi page có `source:` `.md` → `render_md_page.py` chuyển md→HTML partial.
3. Gọi `docs/showcase/build.py` (adapter, KHÔNG thuộc 10 script docs-build) — nó gọi `_assemble` nối CSS/JS parts → dựng `Ctx` → `ssg_engine.build(ctx, out)`.
4. `ssg_engine` nhận `Ctx.css`, `Ctx.js` (chuỗi đã nối) + `Ctx.assets_dir` → sinh toàn bộ `public/`.

## Thứ tự section (từ `_present/*`)

`sections[]` quyết thứ tự + độ sâu render (nguồn chuẩn `docs/_present/*`; legacy: `showcase.yaml`):
```yaml
sections:
- {id: overview,      order: 1}
- {id: architecture,  order: 2}
- {id: quality,       order: 3}
- {id: governance,    order: 4}
- {id: techstack,     order: 5}
- {id: modules,       order: 6}
- {id: operations,    order: 7}
- {id: guides,        order: 8}
- {id: glossary,      order: 9}
- {id: decisions,     order: 99}
```
- `order` → vị trí section trong showcase + flat-md (`_present/*`).
- `detail: full` render đầy đủ; `summary` rút gọn (tóm tắt/heading-level) (`_present/*`).
- `_present :: modules[].order` → thứ tự render; `_index/bands.yaml :: modules[].band` → band khi render layer/cluster view (TÁCH 2 nguồn sau C1).
- `_index/bands.yaml :: bands[]` (vi/en) → legend song ngữ.

## Output

- **public/** — showcase HTML (index + section pages) + `assets/` (theme: `showcase.css`, `showcase.js` đã bundle data-JS, `lib/`). Giữ hiệu ứng tương tác baseline.
- **dist/** — phát hành tĩnh:
  - flat-md: gộp md theo section order (1 file đọc tuyến tính).
  - pdf: từ flat-md hoặc HTML (xhtml2pdf).
  - excel: ma trận module/part/config + reuse, từ `_index/*.yaml` + frontmatter (openpyxl).

## Dependency

| Thư viện | Dùng cho |
|---|---|
| `pyyaml` | đọc `_index/*.yaml` + frontmatter (đã dùng ở `_docslib`) |
| `markdown` | md body → HTML |
| `xhtml2pdf` | HTML/flat-md → PDF |
| `openpyxl` | sinh `.xlsx` |

## Điểm CI

1. **Gate trước build** — `hs:docs-standardize` (`docs_gate.py --fresh`) phải PASS (0 error). Build KHÔNG chạy khi còn error structural.
2. **Build** — chạy 4 script P4; non-zero exit = fail CI.
3. **Smoke** — kiểm `public/index.html` + `public/assets/showcase.js` chứa `var MOD_M4/PTNT_LAYERS/PTNT_CLUSTERS/PART_MODREF`; `dist/` có md/pdf/xlsx.
4. Artifact build (nếu có) tách khỏi artifact validate (`harness/state/docs-check.json`).

## Ranh giới

- Build thuần render — KHÔNG sinh/sửa nội dung, KHÔNG đổi `_index/*.yaml`.
- `*.js` showcase data do `graph.generate_showcase_data` sinh; đừng sửa tay (có banner GENERATED).
- Quyết định trình bày-cần-người (theme/order/detail) đặt ở `_present/*` (tách khỏi design taxonomy `bands.yaml`).

## Playbook orchestration (`docs/playbook.yaml`)

Một config điều phối — content ⟂ ui ⟂ output (tinh thần Antora playbook). Đổi theme hoặc thêm nguồn nội dung = 1 dòng config, không sửa code. Loader: `_docslib/docslib/playbook.py :: load_playbook`.
```yaml
content:                 # nguồn nội dung (dir/glob rel docs-root)
- modules/
- architecture/
- guides/
ui: {bundle: _present, theme: showcase}   # bundle trình bày + theme
output: build/           # out-dir build (mặc định build/ nếu vắng)
```
Fail-closed: thiếu file / thiếu `content` / `content` không phải list → `PlaybookError` actionable.
- **Build đọc playbook** để lấy out-dir (thay cho hardcode `docs/showcase/assets/js`) — repoint `build_showcase.py` (Bước A out-dir = `playbook.output`, Bước B assembler đọc cùng out-dir) làm ở **C5 migrate showcase** vì đụng assembler `docs/showcase/build.py` ở repo showcase (đổi nửa vời tách khỏi assembler = vỡ). Harness-side ship loader + convention; chưa có playbook → giữ legacy.

## Derived output — commit nguồn, gitignore output

Cây nguồn KHÔNG mang build output. SSOT của "cái gì là output dẫn xuất" = `_docslib/docslib/derived.py` (`DERIVED_OUTPUT_GLOBS` + `is_derived_output`). Build ghi ra out-dir (CI `public/`), CI `pages:` là builder duy nhất — KHÔNG commit lại vào `docs/`.

Quy ước `.gitignore` (repo consumer) cho tập derived an toàn:
```gitignore
# Docs build output — sinh ở CI (GitLab pages: → root public/), KHÔNG commit
docs/public/
docs/showcase/assets/js/*-data.js
docs/_diagram/png/
```
- `*-data.js` = 4 file sinh bởi `generate_showcase_data` (KHÔNG đụng JS hand-authored như `09-search.js`).
- `_diagram/png/` derived từ `_diagram/puml/` (giữ `puml/` nguồn).
- `showcase/partials/*.html` CỐ Ý chưa nằm trong tập này (mixed hand-authored prose + md-sourced render) — quyết định người dùng, xem BACKLOG.

⚠️ Bước `git rm --cached docs/public/**` (gỡ output đã commit) là **bất khả hồi** + ở repo showcase ngoài → chỉ chạy SAU khi pipeline GitLab `pages:` xanh chứng minh regenerate được (committed `docs/public/` là STALE, KHÔNG phải fallback hợp lệ). KHÔNG tự chạy — xin người vận hành.
