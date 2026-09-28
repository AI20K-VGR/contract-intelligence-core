# Phase decomposition — phase design and plan.md (on-demand)

Runs AFTER research, WHEN the planner writes plan.md + phase files. This is the correct technique for decomposing phases so cook can execute them — not a descriptive outline.

## Delegate phase-writing to `@planner` (sub-by-default; bookends stay at main)

On a `--hard` plan the mechanical middle — writing `plan.md` + the phase files — is **delegate-by-default** to a `@planner` subagent (lane `plans/**`, so it writes in-lane; `plan_approval` hashes the layout AFTER the write, so a delegated write does not skew the hash).
This isolates the plan-writing context and pins the standards read-directive onto a fresh subagent. `--in-place` (manual override, wins over mode) or a `--fast` plan keeps it inline.

**Bookends STAY at main (hard, never delegated):** the four interview steps — **understand**, **scope-challenge**, **validate**, **approval** — run only at main because a subagent has **no TTY**, so `AskUserQuestion` dies inside it, and because these are human decisions the harness must not auto-resolve.
Only the write-phase and red-team are eligible for delegation — the whole-plan consistency sweep stays at main (it feeds the human-approval gate, so it must not be delegated).
The delegation-context passed to `@planner` (task · read/modify globs · acceptance · constraints · env) mirrors `"${HARNESS_BIN_ROOT:-.}"/harness/rules/orchestration-protocol.md`; the planner still self-verifies inline (the two-way Evidence Filter) and the main thread runs the approval gate.

## Plan directory structure

```
plans/<timestamp>-<slug>/
├── research/               # researcher reports (path passed to planner)
├── reports/                # red-team / validate reports
├── plan.md                 # overview, required YAML frontmatter
├── plan-graph.yaml         # machine phase-DAG sidecar (mandatory)
├── artifacts/              # gate evidence — written at cook/approve/review time, NOT by plan
└── phases/
    ├── phase-1-<name>.md
    └── phase-N-<name>.md
```

Slug name: kebab-case, describing scope (e.g. `260615-1200-auth-refactor`).

**MANDATORY — stamp this skeleton with `scaffold.py`; do NOT hand-author the plan dir.** A hand-typed layout drifts from what the gates read: `plan_approval` hashes phase files at `phases/phase-*.md` (and legacy `phase-*.md` at root), so a phase file placed anywhere else is silently OUT of the approval hash — a phase edit then slips past drift detection.
Run:
`python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/scaffold.py plan --slug <slug> --title "<title>" --phases a,b,c` creates the dir, plan.md, and one `phases/phase-N-<name>.md` file each —
already carrying the correct `harness_version`/`kit_digest`/`schema_version` stamp (reused from `artifact_stamp`, so a new plan never ships a stale digest). Add a later phase the same way (rerun with the full `--phases` list and
`--force`, or copy an existing `phases/phase-*.md`); never invent a new phase-file location. Then fill the TBD sections with the real decomposition below; `scaffold.py report --type <t> --slug <slug> --title "<title>"` does the same for a report.

### Reuse an existing discovery-brief folder — do NOT mint a sibling

When `hs:discover` ran first, it wrote `plans/<id>-<slug>/discovery-brief.md`. The plan for that work MUST land in the SAME folder, not a fresh timestamped sibling — otherwise the brief is orphaned and the plan loses its captured direction (the common failure when plan runs a while after the brief, so the handoff context is gone).

Find the brief folder, then scaffold INTO it:

1. If the discover→plan handoff gave a brief path, use its parent dir. Otherwise scan: `ls plans/*/discovery-brief.md` and pick the one whose slug matches this work and has NO sibling `plan.md` yet (an un-planned brief).
2. The dir name is `<id>-<slug>` where `<id>` is `YYMMDD-HHMM`. Pass BOTH to scaffold so it targets that exact dir:
   `python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/scaffold.py plan --id <id> --slug <slug> --title "<title>" --phases a,b,c`.
   `--id` defaults to a FRESH `_now_id()` timestamp when omitted — that is what mints the sibling folder, so pass it explicitly whenever a brief dir exists.

The brief file is left in place; scaffold only adds `plan.md` + `phases/` alongside it (it refuses to clobber an existing `plan.md` without `--force`).

## Required YAML frontmatter for plan.md

```yaml
---
title: "<concise>"
description: "<1 sentence for card preview>"
status: pending
priority: P2          # P1 | P2 | P3
effort: "<total estimate>"
branch: "<current git branch>"
tags: [relevant, tags]
created: <YYYY-MM-DD>
# Optional, passive provenance — standards rule ids this plan implements
# (STD-<AREA>-RG<n>-R<n>). Doc-only: NOT a gate, NOT required, and frontmatter
# is stripped from plan_hash so adding it never forces a re-approval.
applies_rules: [STD-...]
---
```

## Each phase file must contain

- **Overview** — 1-2 sentence deliverable.
- **Requirements** — explicit functional + non-functional.
- **Related Code Files** — Create / Modify / Delete with full paths.
- **Implementation Steps** — numbered, specific enough for another developer to execute.
- **Success Criteria** — measurable checkboxes (not subjective).
- **Risk Assessment** — likelihood x impact; mitigation for High items.

## Decomposition rules

1. **Each phase is self-contained**: no runtime dependency on a parallel phase.
2. **File ownership**: each file belongs to only one phase — overlap is a conflict.
3. **>8 files in one phase**: challenge -> split or merge (YAGNI).
4. **>3 phases**: ask the user "can any phases be merged?" before committing the structure.
5. **Naming honesty / SRP** (the Maintainer red-team persona will check): new file/module names must accurately and completely describe their real responsibility — `core.py` that also handles artifact I/O is a misleading name and needs splitting.

## Machine-readable phase-DAG sidecar (MANDATORY) — `plan-graph.yaml`

Every plan MUST ship a `plan-graph.yaml` sidecar next to plan.md so the phase-DAG is machine-checkable — no exception for phase count or `--fast` mode (a trivial plan ships a trivial sidecar; the cost is near-zero and the drift-guard + conflict-detection value is uniform). It carries edges + per-phase file ownership + each node's `post` artifact obligation —
**no status** (status is mutable and lives in plan.md's `## Phases`):

```yaml
edges:
  - {from: P1, to: P2}      # {from: A, to: B} = "A runs BEFORE B" (A is B's prerequisite)
subtasks:
  P3:
    files_to_create: [...]
    files_to_modify: [...]   # no status field — ever
    post: [verification-P3.json]   # end-of-phase artifact obligation
```

Each node **MUST** declare `post:` — the artifacts that phase must emit before it counts as done. Emit `[verification-<node>.json]` for every node; a review phase adds `review-decision.json` (e.g. `post: [verification-P4.json, review-decision.json]`). `derive_plan_completion` reads `post` as the single source of truth for completion, and the ship/deploy gate blocks while any node's `post` is
missing. This is **enforced**: `plan_graph.py` HARD-fails (exit 2, both advisory and `--require` modes) on a node with a missing/malformed `post` — a structural contract violation, not an advisory. A sidecar that omits `post` will NOT pass the validate-step graph check or the cook preflight; declare it explicitly on every node (do not rely on a default). Do NOT add a `pre:` key — it is
deferred (the schema tolerates it, nothing reads it).

Conventions: the filename is fixed (`plan-graph.yaml`); the plan.md frontmatter `phase_graph:` marker is read-only (it does not source the hashed name); pin the edge direction explicitly. Parallelism is **derived, not authored** — do not add a `parallel:` field; a parallel batch is a topological antichain, and the real blocker is a shared file, not a logical edge. `plan_approval` raw-hashes
the sidecar (folded into the plan hash, so an edge change re-triggers the drift guard); `plan_graph.py` reads it read-only at Validate.

## Parallel mode — additional requirements

With `--parallel`: add a **dependency matrix** to plan.md (which phases run concurrently, which are sequential) and a **file ownership table** (phase -> files). Cook reads the matrix to spawn agents in parallel without conflicts.

## Deep mode (`--deep`) — per-phase scout

Each phase file in `--deep` must include:
- File inventory table (action, rough size, test impact).
- Test scenario matrix (critical / high / medium paths).
- Dependency map (links to phases this one depends on).

## Backing

- `"${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/agents/planner.md` — agent that writes plans using this template.
- `"${HARNESS_BIN_ROOT:-.}"/harness/rules/workflow-handoffs.md` — handoff structure plan -> cook.
- `"${HARNESS_BIN_ROOT:-.}"/harness/data/ownership.yaml` — confirm zone before placing a path (-> constraint-scan.md).
- `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/plan_approval.py` — record approval after the user approves the plan.
