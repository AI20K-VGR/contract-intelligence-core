# Khế ước frontmatter

Nguồn sự thật (SSOT) = frontmatter YAML mỗi `.md` + `_index/*.yaml` mỏng.
Validate bởi `_docslib/docslib/frontmatter.py` (structural shape, KHÔNG đánh giá nội dung).
Nguồn sự thật của schema: `_docslib/docslib/frontmatter.py` (DOC_TYPES/ID_RE/STATUSES/TIERS).

## Field

| Field | Bắt buộc | Kiểu / Grammar | Ghi chú |
|---|---|---|---|
| `id` | ✓ | dot-path, mỗi segment kebab `[a-z0-9]` nối `-`/`.`; globally-unique | xem grammar dưới |
| `type` | ✓ | ∈ `DOC_TYPES` (23) | quyết khung template |
| `status` | ✓ | `draft \| review \| stable \| superseded` | |
| `owner` | ✓ | chuỗi (`PTNT \| PTSP \| <team>`) | config_part owner phải `PTSP` |
| `version` | ✓ | semver `x.y.z[-pre][+build]` | |
| `tier` | optional | ∈ `TIERS` nếu có | enum-check khi hiện diện |
| `parent` | optional | `id` doc cấp trên | resolve ở graph (dangling-parent = error) |
| `provenance` | optional | `[path, …]` nguồn raw | resolve ở graph (dangling = warn) |
| `capabilities` | optional | mapping; CHỈ `module-readme` | drive required-set (xem capabilities.py) |

## Grammar `id`

```
ID_RE = ^[a-z0-9]+(?:[-.][a-z0-9]+)*$
```

- Segment chỉ `a-z0-9`; nối bằng `-` (trong segment) hoặc `.` (phân cấp dot-path).
- Không in hoa, không `_`, không khoảng trắng, không bắt đầu/kết thúc bằng `-`/`.`.
- Globally-unique trên toàn `docs/` (trùng → `duplicate-id`, error).
- Quy ước dot-path (scaffold tự suy): module README = `mod-07`; con =
  `mod-07.design`, `mod-07.api`, `mod-07.feature.<f>.spec`, `mod-07.agent.<a>.model-card`,
  `mod-07.agent.<a>.prompt`.

## Enum

```
DOC_TYPES = sad, overview, quality, governance, module-readme, module-design,
            part, api, worker, config, techstack, operations, guide, feature-spec,
            agent-spec, model-card, eval, prompt, mcp-tool, adr, glossary,
            changelog, index            (23)
STATUSES  = draft, review, stable, superseded
TIERS     = L0, L1, L1x, L2, L3, platform, module      (optional)
SEMVER    = ^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.\-]+)?$
```

## Ví dụ block

Module README (có capabilities):
```yaml
---
id: mod-07
type: module-readme
status: draft
owner: PTNT
version: 0.1.0
tier: L2
capabilities:
  exposes_api: true
  has_workers: true
  tenant_config: false
  has_features: [reconcile, export]
  owns_agents: [classifier]
---
```

Doc con (design), có parent + provenance:
```yaml
---
id: mod-07.design
type: module-design
status: draft
owner: PTNT
version: 0.1.0
parent: mod-07
provenance: [_migration/module-attrs.json]
---
```

## Finding liên quan (frontmatter.validate)

| Code | Severity | Nguyên nhân |
|---|---|---|
| `missing-frontmatter` | error | thiếu block `---` |
| `bad-frontmatter` | error | YAML hỏng / không phải mapping |
| `missing-frontmatter-field` | error | thiếu 1 trong `id,type,status,owner,version` |
| `bad-id-grammar` | error | `id` sai `ID_RE` |
| `bad-type` | error | `type` ∉ `DOC_TYPES` |
| `bad-status` | error | `status` ∉ `STATUSES` |
| `bad-version` | error | `version` không semver |
| `bad-tier` | error | `tier` hiện diện nhưng ∉ `TIERS` |
| `bad-owner` | error | `owner` không phải chuỗi |

Cách fix: sửa frontmatter cho khớp khế ước. KHÔNG sửa prose. Field nội dung-cần-người-quyết
(vd `owner` thật là ai) → `FIX.md`.
