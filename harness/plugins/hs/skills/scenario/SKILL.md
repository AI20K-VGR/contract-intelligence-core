---
name: hs:scenario
injectable: true
description: Decompose a feature/code path across 15 dimensions to generate edge cases, risks, and test targets before implementation. Use for QA planning, risk discovery, and coverage audits.
argument-hint: "<file|feature> [--iterations N | --saturation] [--domain <type>] [--focus <dim>] [--format <type>]"
allowed-tools: [Read, Write, Glob, Grep, Bash]
metadata:
  compliance-tier: knowledge
---

# hs:scenario — Edge case & scenario explorer

Decomposes any feature or code path across 15 dimensions to surface edge cases, risks, and test targets **before implementation**.

Saturation loop mechanism (novelty loop, halt condition, TSV log) lives in
`references/saturation-loop.md` — load for iterative mode.

## Modes

| Mode | When | Depth |
|------|------|-------|
| **one-shot** (default) | fast, single pass, 3-5 scenarios per applicable dimension | balanced |
| **iterative** (`--iterations N`) | N controlled rounds | deep, bounded |
| **saturation** (`--saturation`) | runs until coverage is exhausted | deepest |

No argument -> `AskUserQuestion`: target feature/file, mode, domain hint.

## Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--iterations N` | — | Run exactly N rounds then stop |
| `--saturation` | off | Stop when 2 consecutive rounds yield no new scenarios |
| `--domain <type>` | auto | Hint: `software`, `product`, `security`, `business` |
| `--focus <dim>` | auto | Prioritize dimension: `edge-cases`, `failures`, `security`, `scale` |
| `--format <type>` | table | `table`, `use-cases`, `test-scenarios`, `threat-scenarios` |

## 15 decomposition dimensions

Not every dimension applies — **filter first**, generate scenarios only for applicable dimensions, and explicitly note which are skipped. The base 13 are below; two orthogonal dimensions — 14 Stakeholder Perspectives and 15 Lifecycle Stage — extend them for who-is-affected and which-lifecycle-stage edge cases (`references/added-dimensions.md`, values in `data/added-dimensions.yaml`).

| # | Dimension | What to look for |
|---|-----------|-----------------|
| 1 | **User Types** | admin, guest, banned, new user, bot/scraper |
| 2 | **Input Extremes** | empty, null, max length, unicode, injection |
| 3 | **Timing** | concurrent, race condition, timeout, retry storm |
| 4 | **Scale** | 0 items, 1 item, 1M items, pagination boundary |
| 5 | **State Transitions** | first use, mid-flow abort, resume after crash |
| 6 | **Environment** | mobile/low-end, no JS, screen reader, timezone |
| 7 | **Error Cascades** | DB down, API timeout, disk full, partial write |
| 8 | **Authorization** | expired token, wrong role, privilege escalation |
| 9 | **Data Integrity** | duplicate, orphan ref, encoding mismatch |
| 10 | **Integration** | webhook replay, API version mismatch, outage |
| 11 | **Compliance** | GDPR deletion, audit log gap, PII exposure |
| 12 | **Business Logic** | zero/negative pricing, coupon stack, refund edge |
| 13 | **Contract-delta / Caller Impact** | a contract-delta (changed output/null/required-param/side-effect) breaks existing call-sites — grep callers, read depth-1 |
| 14 | **Stakeholder Perspectives** | an edge case that only bites one stakeholder — ops (noisy alerts), security (audit gap), end-user (confusing error) — `references/added-dimensions.md` |
| 15 | **Lifecycle Stage** | a failure tied to a lifecycle stage — bad rollback at ship, missing signal at measure, stranded data at deprecate/migrate — `references/added-dimensions.md` |

## Process

### One-shot (default)

1. Read the target file/feature
2. Filter the 15 dimensions — note skipped dimensions + reason
3. Generate 3-5 scenarios per applicable dimension
4. Classify severity: Critical / High / Medium / Low
5. Output table + summary

### Iterative / Saturation

Load `references/saturation-loop.md` before starting the loop.
Each round: pick a dimension -> generate 1 situation -> classify (New/Variant/Duplicate) -> log to `scenario-results.tsv` -> check halt condition. Print progress summary every 5 rounds.

### Severity

| Level | Meaning |
|-------|---------|
| **Critical** | Data loss, auth bypass, silent corruption |
| **High** | Feature broken for a user segment, data inconsistency |
| **Medium** | Degraded UX, recoverable error not surfaced |
| **Low** | Minor visual glitch, non-blocking warning |

## Output — one-shot

```
## Scenario Report: [target]

Dimensions analyzed: [list]
Dimensions skipped: [list + reason]

| # | Dimension | Scenario | Severity | Expected Behavior |
|---|-----------|----------|----------|-------------------|

### Summary
- Critical: N  High: N  Medium: N  Low: N
- Total: N scenarios across X dimensions
```

## Integration with other skills

| Next step | Skill | How |
|-----------|-------|-----|
| Generate test cases from scenarios | `hs:test` | Paste scenario table as input context |
| Feed risks into a plan | `hs:plan` | Paste Critical/High rows into risk assessment |
| Debate top risks in depth | `hs:predict` | Feed Critical scenarios as the change proposal |
| Research unclear risks further | `hs:research` | Use when evidence is needed for an unclear risk |
| Score quality-characteristic coverage | (this skill) | Build an ISO/IEC 25010 coverage matrix — covered / N-A-with-reason / gap per characteristic — then score it with `harness/scripts/iso_matrix_score.py` and report ITS verdict, never a count you made by eye (`references/iso-25010-matrix.md`) |

## Examples

```bash
# One-shot (default)
/hs:scenario src/api/payment.ts
/hs:scenario "User registration with OAuth providers"

# Bounded — exactly 25 rounds
/hs:scenario src/api/payment.ts --iterations 25

# Saturation — stops automatically when coverage is exhausted
/hs:scenario "Add multi-tenancy to the database layer" --saturation

# Security domain hint
/hs:scenario src/middleware/auth.ts --saturation --domain security
```
