# Conventions — GROUP_LEVEL, Color=Identity, edge rounding

Adapted from drawio-ai-kit@bda82a2 (sparklabx, MIT). These are behavioral contracts enforced by `validate.py` (P8 audit layer).

## GROUP_LEVEL law

AWS container stencils follow a strict nesting hierarchy. Each level has a canonical stencil prefix. A child of level N must have level > N.

| Level | Container | Prefix |
|---|---|---|
| 0 | AWS Cloud | `group_aws_cloud` |
| 1 | Region | `group_region` |
| 2 | VPC | `group_vpc` |
| 3 | Availability Zone | `group_availability_zone` |
| 4 | Subnet (public/private) | `group_public_subnet` / `group_private_subnet` |
| 5 | Security Group | `group_security_group` |

**Rule**: a Subnet (level 4) must not be a direct child of a Region (level 1). Each level nests in the level immediately above it. The `validate.py` `check_group_levels()` audit flags violations.

## Color=Identity

Every AWS icon belongs to a category (Compute, Storage, Database, Security, Networking…), each with one official color defined in `data/category-colors.json` (from aws.json). The icon's `entry.color` sets the fill.

```
colorFor(icon):
  icon.entry.color
    → categoryColors[icon.entry.category]
    → "#232F3E" (default dark)
```

The `validate.py` `audit_aws_convention()` check flags icons whose fillColor deviates from their category color without explicit override.

## Edge rounding policy

- **Sequential/pipeline edges**: `rounded=1` (soft corners).
- **Fan-out/bus/tree edges** (one source → many targets): `rounded=0` (sharp right angles). This is a visual tell — rounded fan-out reads as hand-drawn, sharp reads as intentional.
- **Auto-routed edges** (no waypoints): let the router pick.

## Square frames

AWS container groups (Region, VPC, AZ, Subnet) use square/rectangular frames with the label in the top-left corner. Never use rounded corners on container frames.

## Read-only kit boundary

`validate.py` ships a `--strict` mode that escalates subjective warnings (aesthetic: palette scatter, font count) to failures. Objective checks (geometry overlap, stencil existence, nesting level) run by default and always flag.
