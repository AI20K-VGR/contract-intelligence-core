---
id: {{id}}
type: module-readme
tier: L2
status: {{status}}
owner: {{owner}}
version: {{version}}
parent: {{parent}}
module_class: {{module_class}}
# capabilities = "tờ khai" → suy ra required-set. Sửa cho khớp module thật; bỏ field không có.
capabilities:
  exposes_api: false
  has_workers: false
  tenant_config: false
  has_features: []
  owns_agents: []
---

# {{title}}

> TBD — một câu mô tả module làm gì (engine PTNT build-once).

**Tier:** {{module_class}} · **Band:** TBD

## Ranh giới PTNT | PTSP
- **Engine (PTNT, build-once):** TBD
- **Config / recipe (PTSP):** TBD

> Tóm tắt NGẮN + link canonical, KHÔNG copy §5: [responsibility-boundary.md](../../architecture/responsibility-boundary.md)

## Parts (sở hữu tại module này — nhà vật lý)
- TBD — liệt kê part + link `parts/<id>.md` (nguồn graph: `_index/modules.yaml`).

## Reuses (logical link → nhà vật lý ở module khác)
- TBD — hoặc _(không reuse)_.

## Contract chính
TBD — sự kiện vào → output ra.
