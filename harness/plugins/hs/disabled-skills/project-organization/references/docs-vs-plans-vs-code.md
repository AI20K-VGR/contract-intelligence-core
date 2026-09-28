# docs/ vs plans/ vs code — distinguishing the three zones

Quick decision: which zone does this artifact belong to?
Hard backing: `"${HARNESS_BIN_ROOT:-.}"/harness/rules/documentation-management.md` + CLAUDE.md rule 5.

## Quick reference table

| Question | → zone | Example path |
|---------|--------|----------|
| Does a user/maintainer need to read this to understand the system? | `docs/` | `docs/system-architecture.md` |
| Is this an execution plan with a lifecycle (pending→done)? | `plans/` | `plans/260612-1237-harness-w2/plan.md` |
| Is this a temporary agent report / research artifact? | `plans/reports/` | `plans/reports/scout-260304-1530-hooks-report.md` |
| Is it runnable / testable / buildable? | code layer | `harness/hooks/gate_stage.py` |
| Is it config that a person edits by hand? | `harness/data/` (YAML) | `"${HARNESS_BIN_ROOT:-.}"/harness/data/stage-policy.yaml` |
| Is it runtime data written by a machine? | `harness/state/` (JSONL) | `harness/state/trace/` |

## docs/ — evergreen documentation

**Characteristics:** stable, no expiry date, reflects CURRENT system state.

```text
docs/
├── system-architecture.md      # architecture, data flow, components
├── codebase-summary.md         # auto-generated overview (hs:docs)
├── code-standards.md           # project coding conventions
├── project-roadmap.md          # milestones + progress
├── project-overview-pdr.md     # product/project requirements
├── deployment-guide.md         # deployment process
├── STANDARDIZE.md              # port attribution ledger
├── journals/                   # technical journals (timestamped)
│   └── {YYMMDD-HHmm}-{slug}.md
└── decisions.md                # architecture decision log (DEC log)
```

**When to UPDATE docs:**
- User-visible behavior changes
- Setup, install, or CLI commands change
- Architecture, data flow, or public contract changes
- Security posture or operational process changes
- Decisions that future maintainers should not have to rediscover

**Do NOT update** for purely internal edits (no noise).

**Operating owner:** `hs:docs-manager` agent — edits only `docs/` files, does not mutate code.

## plans/ — lifecycle plans

**Characteristics:** tied to a specific work item, has a status (pending/in_progress/completed/cancelled), expires at plan finish.

```text
plans/
├── {YYMMDD-HHmm}-{slug}/       # plan folder — always timestamped
│   ├── plan.md                  # overview (≤80 lines)
│   ├── plan-graph.yaml          # machine phase-DAG sidecar (mandatory)
│   ├── phases/                  # phase detail files (scaffold layout)
│   │   └── phase-{N}-{name}.md
│   ├── artifacts/               # gate evidence (cook/approve/review write here)
│   ├── research/                # research attached to this plan
│   └── reports/                 # agent reports attached to this plan
├── reports/                     # standalone reports (not attached to a plan)
│   └── {agent}-{YYMMDD-HHmm}-{slug}-report.md
└── research/                    # standalone research
```

**Minimum plan.md:** frontmatter status + overview + phases table + dependencies + success criteria. Keep it short (≤80 lines) — detail goes in phase files.

**Gate wiring:** `harness/hooks/gate_stage.py` + `"${HARNESS_BIN_ROOT:-.}"/harness/data/stage-policy.yaml` — push/pr/ship/deploy blocked when an active plan lacks an approval artifact (schema `"${HARNESS_BIN_ROOT:-.}"/harness/schemas/artifact-plan-approval.json`). No plan = cannot ship.

## code — execution layers

**Layering principles:**

| Artifact | Zone | Characteristics |
|----------|------|----------|
| Hook | `harness/hooks/*.py` | HOOK_CLASS constant; compliance fail-closed exit 2; telemetry/nudge fail-open |
| Gate script | `harness/scripts/*.py` | exit 2 on violation; analytical script exit 0 + JSON |
| Skill | `harness/plugins/hs/skills/*/SKILL.md` | workflow prose; does NOT import hooks/scripts |
| Rule | `harness/rules/*.md` | on-demand contract; load when task needs it |
| Config | `harness/data/*.yaml` | human-edited; no machine RMW |
| State | `harness/state/` | append-only JSONL; not committed; not in git |
| Test | `harness/tests/` | pytest; red→green TDD required |
| Standards | `harness/standards/` | user input at clone time (not present in repo by default) |

## Common mistakes

| Wrong | Right |
|-----|------|
| Creating a standalone `REVIEW.md` after a review | Record via `backlog_register.py add` (report link in the text) |
| Creating `notes.md` in root | `plans/reports/` if temporary; `docs/` if evergreen |
| Markdown in `harness/` outside `harness/rules/` | Move to `docs/` or `plans/` |
| `plan.md` > 80 lines due to stuffed detail | Split detail into phase files; keep `plan.md` as overview |
| Doc describing assumed behavior not yet implemented | Stop — docs-manager verifies `file:line` before writing |

## Checklist before creating a markdown file

- [ ] Is this evergreen documentation a person needs to read? → `docs/`
- [ ] Is this a plan/report with a lifecycle? → `plans/`
- [ ] Is this runnable code? → appropriate code layer
- [ ] Is the file name self-describing? (content is clear without opening the file)
- [ ] If timestamped: has `date +%y%m%d-%H%M` been run?
- [ ] Does the parent directory exist? (create if missing; add `.gitkeep` if empty)
