# Principles for draw.io diagrams (AWS & system architecture)

Adapted from drawio-ai-kit@bda82a2 (sparklabx, MIT).

## Layout & sizing

- Standard icon size: **78×78** primary, 48×48 compact. Use ONE size per diagram.
- Minimum spacing: **80px horizontal**, **90px vertical** (room for label under icon).
- Relative alignment trumps grid: same-row nodes share `y`, same-column share `x`.
- Resource icons must include `aspect=fixed` to prevent distortion on resize.
- Do NOT stretch giant full-width banners — size elements to content.

## Flow direction

- Default **left→right** for data pipelines/request flows.
- **Top→bottom** for tiered layering.
- One consistent direction. Back-pointing arrows only for feedback/sync (use dashed).

## Containers — official AWS group stencils

Use real AWS group shapes from shape search (`search_icon --kind group`): `group_aws_cloud_alt`, `group_region`, `group_vpc`, `group_availability_zone`, `group_public_subnet`/`group_private_subnet`, `group_security_group`.

Nesting order: **AWS Cloud → Region → VPC → AZ → Subnet → Security Group**.

Group frames use `verticalAlign=top;align=left;spacingLeft=30` so the label sits next to the corner icon. Declare containers first (lower z-index).

## Color — restrained & theme-aware

- Icons keep their **category** color (Compute orange, Storage green, Database pink, Security red, Networking purple, Management magenta). Don't recolor.
- For backgrounds/frames, target **≤8 distinct fill colors** per diagram. Use a few neutral greys + 1-2 soft accents.
- Pipeline stages MAY carry a soft tint progression (green→amber→yellow→purple) — that's ordered, not "rainbow". Avoid saturated/clashing fills.
- Prefer `light-dark(#light, #dark)` tokens so the diagram works in both modes.
- Use `fillOpacity` 20-40 on frames. Reserve strong color for emphasis.

## Labels & typography

- Service labels below icon (`verticalLabelPosition=bottom;verticalAlign=top`).
- Limit to **3-4 font sizes**, label text **≤14px**. No oversized titles inside canvas.
- Long notes go in a separate **note box**, not crammed into icon label.
- Third-party components → rounded box with "(on EKS)"/"(on EC2)" notation.

## Edges — corner style by role

- Base: `edgeStyle=orthogonalEdgeStyle;html=1`.
- Sequential/pipeline flow → `rounded=1` (soft corners).
- **Fan-out/bus/tree branches** → `rounded=0` (sharp right angles). This is the single biggest "looks hand-made vs auto" tell.
- Pin connection points (`exitX/exitY`, `entryX/entryY`) for parallel/fan-out edges.
- **Solid** = primary flow; **dashed** = sync/dependency/policy/lineage.
- Color edges by source layer.
- Labels on bent edges: add a waypoint at the corridor center so the label doesn't land on the corner.

## Managed vs self-managed

- AWS managed: use the AWS icon + optional "▸ managed" label.
- OSS on EKS/EC2: text box, optionally placed next to the EKS/EC2 icon.

## Recommended layout

- Left: sources/clients. Center: AWS Cloud frame with pipeline. Right: consumers.
- Cross-cutting layers (security, monitoring, governance): separate band/column, connected with dashed lines.
- Hybrid/DR: separate block via Direct Connect node.

## Self-check (before returning)

- [ ] Every AWS stencil came from shape search (not invented).
- [ ] No icon missing `aspect=fixed`; consistent icon size.
- [ ] No edge points to a non-existent id.
- [ ] Icon colors match category; backgrounds ≤8 cohesive colors.
- [ ] ≤4 font sizes, no oversized label text.
- [ ] Fan-out edges use sharp corners + pinned connection points.
- [ ] One consistent flow direction.
