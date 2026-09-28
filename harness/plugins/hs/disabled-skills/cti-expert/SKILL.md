---
name: hs:cti-expert
injectable: true
description: "Analyze cyber threat intelligence and OSINT cases. Use for exposure reviews, domain recon, breach checks, username/email/phone research, image forensics, blockchain tracing, darknet checks, cloud tenant recon, vulnerability lookup, threat modeling, and structured reports."
allowed-tools: [Bash, Read, Write, Edit, Glob, Grep, WebFetch, WebSearch, Skill]
argument-hint: "[target] [--yolo] [case|sweep|query|flow]"
metadata:
  compliance-tier: workflow
  version: "2.0"
  author: "Hieu Ngo - chongluadao.vn"
  source: "https://github.com/7onez/cti-expert"
  license: "MIT"
---

# CTI Expert

Cyber threat intelligence / OSINT skill: generates precision search queries, interprets public data, builds case timelines, delivers structured intelligence products — no API keys, no paid subscriptions.

Collection method: `agent-browser` when available (JS-heavy sites, infinite-scroll, screenshot evidence w/o real user login); `hs:chrome-profile` only when needing the user's actual Chrome cookies; auto-fallback to web search / web fetch / direct URL fetch. Tool limitations log as collection gaps — never case blockers.

## 1. Quick Start

```bash
# Full autonomous case — runs every applicable technique
/case target.com

# Guided flow for first-time investigators
/flow person

# Summary of what's been found so far
/brief
```

Append `--yolo` to any command to skip all interactive prompts and confirmations. The analyst makes every decision autonomously.

## 2. AEAD Case Lifecycle

Every investigation follows four phases:

| Phase | What Happens |
|-------|-------------|
| **Acquire** | Collect raw data — `/sweep`, `/query`, `/username`, `/phone`, `/email-deep`, `/subdomain` |
| **Enrich** | Expand leads — `/branch`, `/crossref`, `/link-subjects`, `/signatures` |
| **Assess** | Score and verify — `/exposure`, `/threat-model`, `/validate`, `/coverage`, `/verify-finding` |
| **Deliver** | Package output — `/report`, `/brief`, `/render`, `/workspace save` — **auto-saves .md + .docx** |

MUST: every `/report`, `/brief`, and `/render` command saves TWO files — `.md` + `.docx` — before the Deliver phase counts as done. Exact DOCX-JSON schema: `references/output-formats.md`.

Run `/progress` anytime to see current phase and pending items.

## Ethics & Boundaries

This skill operates strictly within publicly available information.

### Permitted

- Journalists verifying facts about public figures or institutions
- Security professionals auditing their own organization's exposure
- Individuals reviewing their own digital footprint
- Corporate due diligence on business partners
- Academic research and educational demonstrations

### Prohibited

- Stalking, harassment, or doxing of any individual
- Accessing accounts or systems without authorization
- Social engineering or deception campaigns
- Any activity violating applicable law

Ethical reminders auto-issue when the investigation nears sensitive territory. Public data is not a license to cause harm.

## References

Load on demand — the full operating manual is split across these drawers:

- `references/command-reference.md` — every `/command` (Acquire / Enrich / Assess / Deliver / UX & Navigation).
- `references/subject-and-finding-model.md` — subject & connection types, trust scores, source-reliability scale, confidence levels, ASCII map rendering, finding framework.
- `references/techniques-and-workflows.md` — technique catalog and the workflow guides per case type.
- `references/output-formats.md` — mandatory file export, the HYBRID/JSON/MD/pandoc DOCX generators, report/visual/connector formats.
- `references/tiers-autonomous-and-architecture.md` — skill tiers, guided flows, case templates, `--yolo` autonomous mode, and the architecture reference.
- `references/activation-matrix-and-tooling.md` — technique-activation matrix, exposure score bands, tool priority/fallback, and the tool auto-install policy.

Deep content lives in the bundled subdirectories: `techniques/` (per-technique playbooks), `handbook/` (operator queries, discovery paths, tool cascade), `guides/`, `workflows/`, `engine/` (subject registry, finding framework, workspace manager), `analysis/`, `connectors/`, `validation/`, `experience/`, and `output/`. Helper scripts (DOCX generators, install) are under `scripts/`.
