---
name: hs:bootstrap
injectable: false
description: Bootstrap a new project from scratch -- clarify requirements, init git, create doc structure, delegate to hs:plan + hs:cook. Use when starting a new repo or resetting a project's SDLC foundation.
argument-hint: "[--full|--fast|--auto|--parallel] [requirements] [--ultra [N] | --debate]"
allowed-tools: [Bash, Read, Write, Edit, Grep, Glob, Task]
metadata:
  compliance-tier: workflow
---

# hs:bootstrap -- project bootstrap

Orchestrate the new-project initialization flow: git init, clarify requirements, create doc structure, then delegate to `hs:plan` and `hs:cook`.

**Does not write code directly.** All implementation goes through plan + cook.

## Modes

| Flag | When | User gate |
|---|---|---|
| (none) -> `--full` | Fully interactive | After each major phase |
| `--fast` | Skip long clarify, run quickly | After research synthesis |
| `--auto` | Autonomous (explicit opt-in) | Only at the final step |
| `--parallel` | Multi-agent parallel build (research + design + parallel plan/cook) | Design approval, then normal cook review gates |

`--parallel` adds a design/wireframe phase and exclusive-file-ownership parallel execution — see `references/workflow-parallel.md`.

## Workflow

### Step 0: Git init (all modes)

Check whether git is already initialized. If not:
- `--full`: ask the user first, then `@git-manager` agent inits the `main` branch.
- Other modes: auto-init via `@git-manager` agent.

### Step 1: Clarify requirements (`--full` / `--fast`)

Load `references/clarify.md`.

`--auto`: skip gate, synthesize requirements from input directly.

### Step 2: Quick research (optional)

Use `@researcher` agent (<=5 sources) when technology or feasibility is unclear. Report <=150 lines, saved to `plans/reports/`.

Gate `--full`: present results, wait for approval. `--fast`/`--auto`: continue automatically.

### Step 3: Create doc structure

`@docs-manager` agent creates the minimal skeleton (only missing files):

- `docs/codebase-summary.md`
- `docs/code-standards.md`
- `docs/system-architecture.md`

`@project-manager` agent creates:

- `docs/project-roadmap.md`

Scaffold the project's shared-language registry (same register + four-field schema harness uses for its own glossary):

```bash
python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/glossary_register.py --root . --migrate   # idempotent
```

This creates `docs/glossary.yaml` (the SSOT) and renders `docs/GLOSSARY.md` (a generated view with the no-clobber marker). Load terms with
`glossary_register.py --root . --add` — never hand-edit the rendered view.

Do not overwrite existing files -- only create what is missing.

### Step 4: Planning -> implementation

Activate `hs:plan`:
- `--full` -> `/hs:plan <requirements>`
- `--fast` -> `/hs:plan --fast <requirements>`
- `--auto` -> `/hs:plan --auto <requirements>`

Plan returns an absolute path. Gate `--full`: wait for user to approve the plan before continuing.

After the plan is approved, activate `hs:cook <plan-path>` (matching mode).

### Step 5: Completion report

Load `references/final-report.md`. After cook finishes:

1. Summarize changes
2. Onboarding guide (getting-started instructions)
3. Ask about commit/push -> `@git-manager` agent if agreed
4. Call `hs:journal` to record the session

## Boundaries

- Do NOT write code directly -- delegate through plan + cook.
- Do NOT autonomously choose a specific stack (framework, language) -- ask or write into requirements so plan decides.
- New markdown files are only created in `docs/` or `plans/` (harness rule).
- `--auto` is only used when the user explicitly requests it.
- `--ultra [N]`/`--debate`: call `hs:workflow-orchestrate --ultra [N]|--debate --run-id <slug>` to size + drive N independent scaffold plans over the SAME requirements (no shared context); `hs:escalation-consultant` synthesizes ONE plan, and only that plan gets scaffolded below. Approval gate is `hs:workflow-orchestrate`'s own.

## Cross-references

- `hs:plan` -- generate a plan from requirements
- `hs:cook` -- implement according to the plan
- `hs:docs` -- deepen documentation if needed after bootstrap
- `hs:project-management` -- track progress after launch
- `hs:journal` -- record the session when done
