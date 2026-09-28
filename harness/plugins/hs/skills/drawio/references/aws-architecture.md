# AWS Architecture Guidance — hs:drawio

Guidance for drawing AWS architecture diagrams with draw.io. Synthesized from drawio-ai-kit (sparklabx, MIT): aws-architecture.md + diagram-types.md + principles.md + style-guide.md.

## Diagram types — choose the right layout

| User request | Type |
|---|---|
| Data pipeline, ETL, request flow across tiers | pipeline (left→right) |
| Org structure, Landing Zone, account/OU hierarchy | hierarchy (top→bottom) |
| VPC/network topology, Multi-AZ, 3-tier | network |
| Event-driven, message bus, fan-in/fan-out | hub-spoke |
| Hybrid / DR (on-prem ↔ cloud) | hybrid |
| Numbered walkthrough request | sequence |

## Containers — nest in true order

```
AWS Cloud (group_aws_cloud_alt)
└─ Region (group_region, dashed)
   └─ VPC (group_vpc)
      └─ Availability Zone (group_availability_zone, dashed)
         └─ Subnet (group_subnet — public/private by label/color)
            └─ Security Group (group_security_group, dashed)
               └─ service icons
```

**Rules:**
- Child sets `parent="<containerId>"`, uses coordinates **relative to container**
- Managed/global services (S3, IAM, KMS, CloudWatch, Route53, Orgs) → **outside VPC**, in the AWS Cloud band
- Declare containers **first** (lower z-index) so they sit below child icons
- Group frames use `verticalAlign=top;align=left;spacingLeft=30`

## Icons and color — no recoloring

Each AWS icon has an official category color:
- Compute/Containers `#ED7100` (orange)
- Storage `#7AA116` (green)
- Database `#C925D1` (pink)
- Networking & Analytics `#8C4FFF` (purple)
- Security `#DD344C` (red)
- Management & App-Integration `#E7157B` (magenta)
- Migration/ML `#01A88D` (teal)

**DO NOT recolor** — a recolored icon is a recognizability bug. Use `shapesearch.py "<service name>"` to get the exact style string.

## Canonical layouts

### Data pipeline (left → right)
```
Sources → Ingestion → Processing → Storage → Integration/Serving → Consumers
```
Cross-cutting layers (Security, Monitoring, Governance, CI/CD) = band below, dashed links.

### VPC / network diagram
- Each **Availability Zone is one vertical COLUMN**, AZs **stand side by side**
- **VPC is a horizontal box** wrapping the AZ columns (Region → VPC → AZ columns → subnets)
- Subnets = tiers stacked top→bottom within each AZ: Public → App → Data
- Same tier **aligns horizontally** across AZs (public-a level with public-b)
- Users/Internet = outside VPC; shared ALB/NAT/bus = span horizontally across AZ columns

### Event-driven / bus
Place the bus (Kafka/MSK/EventBridge/SNS) at the **CENTER** of the producer/consumer row; producers from one side (`exitX=1`), consumers from the other side (`exitX=0`) — no crossing.

### Hybrid / DR
On-prem/external = SEPARATE block **OUTSIDE** the AWS Region container (do not nest on-prem inside Region). Direct Connect / VPN = a separate node between cloud and on-prem.

## Multi-AZ

- HA: ≥2 AZ columns, mirror the stateful tier in each AZ (same tier = same row)
- Stateless services scale horizontally within each AZ
- Managed data services (RDS Multi-AZ): one icon at VPC level with a note, or one icon per AZ with a sync link

## Edges

- Pipeline flow → `rounded=1`
- Fan-out/bus → `rounded=0` + pinned `exitX/entryX`
- Main flow animation: `flowAnimation=1` (animates in SVG/desktop)
- Solid = data/control flow; dashed = policy/lineage/sync/DR
- **Connect to bounding box, not each replica**: when a multi-AZ stack is wrapped in a clusterBox, point the edge at the BOX id — one arrow to the border, not N arrows to N child icons in each AZ

## Grid, alignment & sizing

- **Relative alignment** matters more than absolute grid: nodes in the same row share one `y`, same column share one `x`
- Standard icon size: **78×78** (primary), **48×48** (compact) — DO NOT mix sizes
- Min spacing: **80px horizontal**, **90px vertical** (room for the label under the icon)
- `aspect=fixed` required for resource icons (no distortion on resize)

## Placement — keep edges short

Place connected things close together:
- Shared resources (ECR, S3, CloudWatch, KMS) → band right next to consumers, **not** in a row way down below
- Node next to what it talks to most
- Cross-cutting links: group into a comb instead of fanning across the whole canvas

`validate.py` flag: "Long connector(s) spanning most of the diagram" = reposition nodes; "N edge crossings" = fix placement, don't reroute edges.

## OSS niche logos (from ai-kit)

7 OSS logos not in the shape-index, use image style:

| Tool | File | Style |
|---|---|---|
| Apache Hudi | `assets/oss-logos/hudi.png` | `shape=image;image=${HARNESS_BIN_ROOT:-.}/harness/plugins/hs/skills/drawio/assets/oss-logos/hudi.png;` |
| Apache Zeppelin | `assets/oss-logos/zeppelin.png` | `shape=image;image=...zeppelin.png;` |
| Debezium | `assets/oss-logos/debezium.png` | `shape=image;image=...debezium.png;` |
| Apache Iceberg | `assets/oss-logos/iceberg.png` | `shape=image;image=...iceberg.png;` |
| Delta Lake | `assets/oss-logos/delta.png` | `shape=image;image=...delta.png;` |
| Dagster | `assets/oss-logos/dagster.png` | `shape=image;image=...dagster.png;` |
| Apache Pinot | `assets/oss-logos/pinot.png` | `shape=image;image=...pinot.png;` |

Add `aspect=fixed;width=60;height=60;` to preserve aspect ratio. See `references/shapes.md` → "OSS niche logos" for the full syntax.

## Style — general patterns

- **Pale frames**: barely-tinted fills for containers (AWS icons carry the color)
- **Per-stage tint**: pipeline stages use a cohesive progression (green→orange→amber→purple)
- **2px edges** orthogonal, labeled
- Main flow animated (`flowAnimation=1`); fan-out/in = sharp combs

## Composing archetypes — real systems mix several

A real architecture usually COMBINES multiple types, not one pure type. Build the dominant type first, then nest others inside/around it.

Example: a full data platform = **pipeline** (layered stages) **inside** the AWS Cloud frame, with a **hybrid** on-prem block + Direct Connect channel alongside it, a **mesh** of accounts, and a cross-cutting **band**:

```text
AWS Cloud
├── Pipeline (Sources → Ingestion → Processing → Storage → Serving)
├── Cross-cutting band (Security · Monitoring · Governance · CI/CD)
└── (outside the Cloud: On-Premise block → Direct Connect node → Cloud)
```

- **Tree-adjacent-layer**: assign nodes to layers (rows), only connect between adjacent layers to minimize crossings.
- **Star-satellite**: hub at center, satellites around it — edges short and radial.
- Don't force a complex system into one archetype — **compose**. Use themed creators (`stage`/`band`/`endpoint`/`onpremFrame`) throughout to keep one unified style.
