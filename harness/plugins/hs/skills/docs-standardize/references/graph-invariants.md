# Graph invariant

Liệt kê mọi invariant `_docslib/docslib/graph.py :: validate(model, findings)` kiểm.
Tất cả **objective** (đếm/đi-graph, không phán nội dung). `error` chặn gate (exit 2); `warn` = gap.
Cách fix: chỉnh **cấu trúc** (frontmatter / `_index/*.yaml` / file thiếu). KHÔNG fix nội dung hộ;
cái cần-người-quyết → `FIX.md`.

## 1) Frontmatter + id + parent/provenance

| Code | Sev | Nghĩa | Fix |
|---|---|---|---|
| `missing-frontmatter` | error | thiếu block `---` | thêm frontmatter (xem frontmatter-spec.md) |
| `bad-frontmatter` | error | YAML hỏng / không mapping | sửa YAML |
| `missing-frontmatter-field` | error | thiếu field bắt buộc | thêm field |
| `bad-id-grammar` / `bad-type` / `bad-status` / `bad-version` / `bad-tier` / `bad-owner` | error | sai grammar/enum | sửa giá trị cho khớp khế ước |
| `duplicate-id` | error | `id` trùng ≥2 file | đổi 1 id thành unique |
| `dangling-parent` | error | `parent` trỏ id không tồn tại | sửa parent hoặc tạo doc cha |
| `dangling-provenance` | warn | path trong `provenance` không tồn tại | sửa path hoặc bỏ entry |

## 2) Parts (`_index/modules.yaml :: parts`)

| Code | Sev | Nghĩa | Fix |
|---|---|---|---|
| `part-bad-home` | error | `home` không phải module id thật | sửa `home` về module hợp lệ |
| `part-missing-file` | error | `at` không trỏ file thật (relative docs_root) | sửa `at` hoặc tạo file |
| `part-bad-layer` | error | `layer` ∉ `{L2,L3,L4}` (nếu có) | sửa `layer` |

## 3) Links (`_index/modules.yaml :: links`)

| Code | Sev | Nghĩa | Fix |
|---|---|---|---|
| `link-bad-from` | error | `from` không phải module id thật | sửa `from` |
| `link-dangling` | error | `uses` trỏ part không tồn tại | sửa `uses` về part thật |

## 4) Module: axis (intrinsic) + band (display)

| Code | Sev | Nghĩa | Fix |
|---|---|---|---|
| `module-bad-axis` | error | `axis` ∉ `{ingestion,extraction,decision,orchestration,posting}` | sửa axis (frontmatter README) |
| `module-missing-band` | error | thiếu `band` (taxonomy ở `_index/bands.yaml :: modules[]`; legacy fallback `showcase.yaml`) | thêm `band` cho module ở `_index/bands.yaml` |
| `module-bad-band` | error | `band` ∉ tập band của `_index/bands.yaml :: bands` (legacy: `showcase.yaml :: bands`) | sửa band |

## 5) Config parts (PTSP — `_index/modules.yaml :: config_parts`)

| Code | Sev | Nghĩa | Fix |
|---|---|---|---|
| `configpart-bad-home` | error | `home` không phải module thật | sửa home |
| `configpart-bad-owner` | error | `owner` ≠ `PTSP` | đặt `owner: PTSP` |
| `configpart-missing-bilingual` | error | thiếu `vi` hoặc `en` | điền cả vi+en |

## 6) Safety (`_index/safety.yaml`)

| Code | Sev | Nghĩa | Fix |
|---|---|---|---|
| `safety-missing-id` | error | safety entry thiếu `id` | thêm id |
| `safety-bad-anchor` | error | `anchors` chứa token không phải part thật | sửa anchor về part thật |

## 7) Foundations (`_index/foundations.yaml`)

| Code | Sev | Nghĩa | Fix |
|---|---|---|---|
| `foundation-missing-id` | error | foundation thiếu `id` | thêm id |
| `foundation-bad-anchor` | error | `anchor` không phải part thật và ≠ `infra` | sửa anchor (part thật hoặc `infra`) |

## 8) Required-set capability-driven (`capabilities.py :: check_module`)

Bắt buộc lai: `README.md`+`design.md` LUÔN; còn lại theo cờ `capabilities` (xem
docs-scaffold required-set).

| Code | Sev | Nghĩa | Fix |
|---|---|---|---|
| `mandatory-doc-missing` | error | thiếu `README.md` hoặc `design.md` | `hs:docs-scaffold` stub |
| `required-doc-missing` | warn | thiếu doc cờ-khai (api/workers/config/feature/agent) | scaffold stub, rồi viết nội dung |
| `undeclared-doc` | warn | có `api.md`/`workers.md`/`config.md` nhưng cờ tương ứng chưa khai | khai cờ trong README, hoặc bỏ file |

## 9) README guard — DRY vs boundary (`_readme_guard`)

Canonical: `docs/architecture/responsibility-boundary.md`. Ngưỡng:
`GUARD_BOUNDARY_MAX_LINES = 15`, dòng "substantive" = `len > 20` và không bắt đầu `#`.

| Code | Sev | Nghĩa | Fix |
|---|---|---|---|
| `mandatory-doc-missing` | error | module thiếu `README.md` | scaffold README |
| `readme-copies-boundary` | error | README trùng > 15 dòng nguyên-văn với boundary | giữ tóm tắt + link, đừng copy |
| `readme-missing-canonical-link` | warn | README không nhắc `responsibility-boundary.md` | thêm link canonical |

## Ghi nhớ

- `error` → gate exit 2. Sửa cấu trúc cho đến 0 error.
- `warn` = gap, không chặn. Gap doc-thiếu → scaffold. Gap cần-người-quyết → `FIX.md`.
- Tất cả là invariant **đi-graph/đếm**; không có invariant nào phán "nội dung dở".
