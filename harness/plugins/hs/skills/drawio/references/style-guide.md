# Style guide — drawio house design system

Adapted from drawio-ai-kit@bda82a2 (sparklabx, MIT).

The skill has ONE visual style — use the themed patterns below, don't hand-pick colors ad-hoc, so every diagram inherits the same polished look.

## The look

- **Pale, theme-aware tints.** Frames use `light-dark(#…,#…)` pairs that are barely tinted, so the diagram reads cleanly in both light and dark mode. The strong color comes from the **icons**, not the frames.
- **Per-stage tint, not rainbow.** Pipeline stages take a cohesive progression (green→orange→amber→purple). That's ordered + meaningful. Avoid saturated fills or color with no meaning.
- **Clean 2px edges**, orthogonal, with `light-dark` label background. Main flow is animated (`flowAnimation`); fan-out/in are sharp combs.
- **Square frames** (AWS convention). Icons carry category color and keep it.

## Themed patterns

| Pattern | Use for | Color |
|---|---|---|
| Stage/layer | Pipeline layer/column | Soft per-stage tint (green→orange→amber→purple) |
| Band | Cross-cutting band (governance/security/ops) | Neutral |
| Endpoint card | Source/consumer (diagram entry/exit) | Pale blue |
| OSS box | Plain OSS/component box | Theme-aware white |
| On-prem frame | On-premise / external site | Pale beige |
| AWS group stencil | Region/VPC/AZ/Subnet | Stencil's own light fill |

## Rules of thumb

1. Use a themed pattern first; pass explicit `fillColor` only for one-offs.
2. Let **icons** be the color; keep **frames pale**.
3. Animate only the **main flow** (a few spine edges), not every edge.
4. `fillOpacity` 20-40 on frames keeps the look airy.
