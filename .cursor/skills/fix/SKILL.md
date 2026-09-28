---
name: hs:fix
injectable: false
description: Fix bugs, test failures, and CI/CD failures with an evidence-based workflow. Use when there is a concrete bug, a clear error, or a red test.
argument-hint: "[quick | standard | deep] [--auto] [--yagni] [--ultra [N] | --debate]"
allowed-tools: [Bash, Read, Write, Edit, Grep, Glob, Task]
metadata:
  compliance-tier: workflow
---

# hs:fix — evidence-based bug fixing

`--yagni` cuts scope not needed for the stated outcome; the default delivers the full ask. Pass it to `hs-run`, which stamps the posture and names the rule.

Standard flow: **debug → fix → red→green test → review → gate**. No step may be skipped. Diagnose the root cause BEFORE fixing.

**Who does what**: main owns diagnosis-approval, the fix (Step 3), and the red→green test (Step 4); `@debugger` investigates (Step 2) and `@code-reviewer` reviews (Step 5) — advisory, they do not mutate. When a slice is delegated to `@developer`, main re-verifies its test (Step 5).

**Where you stand**: run `hs-run fix next`. It reads the two things disk can answer — is a review-decision
recorded, does the push-stage gate clear — names the state, and loads the rules and references that state
needs. The four earlier steps leave no disk trace, so it says nothing about them; you narrate those. Read what
the envelope names, and only that. But satisfying the envelope is **not enough** to have fixed anything: it
routes DOCUMENTS, while the broken code and the red test are the artifact this step changes — open them.

Before you build a fix on "it's probably X", RUN the real thing to confirm the mechanism — reading code / `--help` / reasoning is a *hypothesis*, NOT a probe. An unconfirmed cause is `[ASSUMED]`, never OBSERVED; the red→green repro test IS that one real-run confirmation — no fix ships ahead of it.

## Modes

| Mode | When | Behavior |
|---|---|---|
| `quick` | lint/type error, obvious single-file issue | minimal scout → diagnosis abbreviated → fix → verify |
| `standard` (default) | multi-file bug, unclear cause | full pipeline: scout→diagnose→fix→test→review→gate |
| `deep` | architectural impact, 3+ failures | escalate: deep hs:debug + hs:brainstorm before fixing |

No argument → `AskUserQuestion` asking for error description + mode selection.

**`--auto`** (additive; default behavior unchanged): suppress the mid-fix `AskUserQuestion` prompts (mode selection here, and the vague-answer / reviewer-flag prompts below) — auto-pick the mode from the symptom, self-decide, and proceed. Every auto-decision is **written to a concrete sink, never just narrated**: appended to the fix report under `plans/reports/` (what was decided + why) AND
emitted via `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/emit_observation.py`. If the sink is not written, the decision was not made. This is the opt-in that lets a `--fix-auto` recall review drive a non-stop fix.
Without `--auto`, hs:fix asks at every decision point as before. `--auto` never weakens the gate, the red→green test, or the review step, and never auto-applies a behavior-changing fix on a high-risk path
without a non-author reviewer — it only removes the human prompts.

## HARD-GATE (real wiring)

Stage `push|pr|ship|deploy` is blocked by `harness/hooks/gate_stage.py` when `verification.json` is missing, any check is non-PASS/SKIP, or the verdict is `BLOCKED` (schema: `"${HARNESS_BIN_ROOT:-.}"/harness/schemas/artifact-verification.json`). The gate is a presence gate — it proves the step ran, not who ran it. `hs-run fix next` reports the same gate's verdict without running it.

### HARD-GATE-NO-SIDE-EFFECTS

Before writing `verification.json`, run a blast-radius sweep (the reference workflows cite this anchor):
walk every dependent caller of the changed functions (Step 1 blast radius), run the tests in modules
that share files/contracts, and confirm public contracts (signatures, schemas, APIs, env vars) are
unchanged. Any NEW red test → STOP and report to the user (revert / narrow scope / update dependents /
accept with explicit note) — do not proceed to the gate.

## Standard procedure

### Step 1 — Scout (required, cannot be skipped)

Understand the codebase BEFORE forming hypotheses:
- Use `hs:scout` or an Explore subagent to find: affected files, callers/dependents, related tests, `git log --oneline -20` (which recent commit is the cause?).
- Record the "blast radius": every code path that depends on the broken behavior.
- Quick mode: only the affected file + direct deps.

### Step 2 — Diagnose (required, cannot be skipped)

Principles:
- **Capture state before**: copy-paste the exact error message, test failure output, stack trace. The baseline for Step 4 comparison.

- Spawn the `@debugger` agent: investigate the root cause with an evidence chain (observe → hypothesize → test hypothesis → trace back to root cause).
- Do not propose a fix until all 6 questions are answered:
  1. Exact symptom (precise error)?
  2. Reproduction steps (minimal command)?
  3. Expected vs actual?
  4. Root cause at `file:line`?
  5. Why now — what change/condition exposed it (recent commit, data shape, env, dep upgrade)?
  6. Blast radius (which paths are affected)?
- If any answer is vague ("probably", "I think") → `AskUserQuestion` or scout further.
- If 2+ hypotheses fail → escalate to mode `deep`, ask the user.

### Step 3 — Fix (minimal scope)

Principles:
- Fix the ROOT CAUSE, not the symptom.
- Minimal change: only necessary files, following existing patterns in the codebase.
- Do NOT create new abstractions when not needed; do NOT refactor outside bug scope.
- After 3 failures → STOP, reframe the architectural question with the user.

### Step 4 — Red→green test (required)

Red→green, in order:
1. Write a regression test **BEFORE** fixing (or confirm an existing test fails at the right point).
2. Run the test → must be **RED** (intentional failure).
3. Apply the fix → re-run → must be **GREEN**.
4. Run the full suite: `python3 -m pytest harness/tests/ -q` (or the repo suite per standards). All must pass.
5. Deleting/skipping/weakening tests to go green is forbidden — "Fix regressions, not the test."

Write `verification.json` (`harness/schemas/artifact-verification.json`): `stage`, `plan`, `actor`, `ts`, `checks[]`, `verdict`. The `verdict` is one of `PASS` / `PASS_WITH_RISK` / `BLOCKED`; for VERIFICATION a hard stage clears when no check FAILs and the verdict is not `BLOCKED` (both `PASS` and `PASS_WITH_RISK` pass). The exact-`PASS` rule applies to review-decision / critique-consensus,
not verification.

### Step 5 — Review

Spawn `@code-reviewer` agent:
- Input: modified files + blast radius from Step 1 + diagnosis report from Step 2.
- Ask reviewer to check: (a) root cause is genuinely resolved (not a symptom patch), (b) no regression in blast radius, (c) public contract unchanged (signatures, schemas, env vars), (d) no new errors.
- If reviewer flags a regression → `AskUserQuestion` with 2-4 specific options (revert / narrow scope / update dependents / accept with explicit note). Do not decide unilaterally.
- **Delegated slices** (parallel `@developer` per issue): main MUST re-run each delegated issue's regression test and confirm it fails WITHOUT the fix before accepting the slice — a subagent-authored test is not trusted red→green until main sees it go red then green.

### Step 6 — Gate and finalize

See HARD-GATE above for the block condition.
- After gate passes: ask user whether to commit (spawn `@git-manager` agent, conventional commit, no AI reference). If a plan is active → update plan status.
- If docs/behavior changed → spawn `@docs-manager` agent to update `docs/`.
- If the bug exposed a **repeatable failure mode** (wrong pattern, missing wiring, a gotcha that cost real time) → suggest `/hs:remember` to capture a one-line `harness/LESSONS.md` entry (failure → rule → check). Optional, human-approved; skip a one-off.

## Stop conditions

Counts to track, not judgment to re-derive: **3 failed fix attempts** ⇒ the approach is
wrong — escalate to `deep`, reopen the architecture with the user. **2 failed hypotheses**
⇒ the blast radius was drawn too small — scout wider or ask, do not guess a third alone.

## Boundaries

- Keep the change inside the bug's scope; a fix buried in a refactor cannot be reviewed
  against the symptom that started it. Open separate work instead of growing this one.
- Do NOT create abstractions, wrappers, or helpers not directly required.
- Do NOT bypass the gate by writing PASS without running real tests.
- Do NOT weaken/skip/delete tests to fake green.
- On completion: report root cause, files modified (absolute paths), tests added, gate verdict.
- If gate blocks → clearly state the reason + the missing checklist items.
- `--ultra [N]`/`--debate`: call `hs:workflow-orchestrate --ultra [N]|--debate --run-id <slug>` to size + drive N independent fix DESIGNS as text (proposed root cause + patch plan, nothing applied, no shared context); `hs:escalation-consultant` synthesizes ONE design, and only that design gets implemented + tested below. Approval gate is `hs:workflow-orchestrate`'s own.

## Agent/rule wiring

| Backing | Role |
|---|---|
| `@debugger` agent | Root cause investigation (Step 2) |
| `@code-reviewer` agent | Review fix + blast-radius sweep (Step 5) |

| `harness/hooks/gate_stage.py` | Presence gate before ship (Step 6) |
| `harness/schemas/artifact-verification.json` | verification.json schema |

| `plans/reports/` | Diagnosis + review reports |

The `workflow-*.md` references below carry richer historical process detail (TaskCreate/TaskUpdate phase tracking, extra activations like project-management / sequential-thinking). SKILL.md's Standard procedure + Agent/rule wiring table above is the critical path — treat that reference detail as supplementary context, not additional MUST steps.

## References (load when needed)

The four step references — diagnosis, minimal-fix, red→green, pre-gate — are routed by `hs-run fix next` at the state that needs each. Do not load them from a list here; ask the CLI where you are and read what it hands you.

- `references/skill-activation-matrix.md` — which helper skill/agent to reach for by signal
- `references/workflow-quick.md` — quick-mode procedure (single-file / obvious issue)
- `references/workflow-standard.md` — standard-mode pipeline (scout→diagnose→fix→test→review)
- `references/workflow-deep.md` — deep-mode escalation (architectural / 3+ failures)
- `references/workflow-ci.md` — CI/CD failure triage
- `references/workflow-types.md` — failure-type taxonomy → workflow selection
- `references/workflow-ui.md` — UI/visual-bug workflow (design search, visual diff)
- `references/workflow-logs.md` — log-driven investigation


## Auto-decision ledger

When acting autonomously, append one advisory ledger line per governance-bearing decision (this is separate from and additional to the emit_observation signal).
