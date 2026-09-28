---
name: hs:coding-agent-orchestration
description: "Coordinate multiple coding agents and AI developer tools across one workflow — choose which agent plans, implements, reviews, or tests; split work safely; define handoffs; consolidate the result. Use when a task benefits from more than one coding agent/tool, or the user asks which agent should own a step. Internal partner/gemini lanes first; external CLIs are the fallback."
injectable: false
argument-hint: "[task or workflow] [--single|--sequential|--parallel|--review-loop]"
allowed-tools: [Read, Bash]
metadata:
  compliance-tier: workflow
---

# Coding Agent Orchestration

Coordinate multiple coding agents without duplicate work, file fights, or lost source of truth.

This skill plans the **human/tool workflow** — which agent owns which step and how they hand off. It does not itself fan out subagents, run the implementation, or review a PR; the harness has dedicated skills for those (see Related skills). Use this when the decision is *which coding agent or CLI* should do a step, not *how to spawn harness subagents*.

**Reach order inside the harness.** Prefer the internal delegated lanes FIRST — partner lane
(second full-Claude session via named provider) and gemini lane (second-engine advisory/coding
pass) — both provenance-stamped, kept separate from main context. Internal fan-out (harness
subagents/Workflow/Agent Teams) is owned by the fan-out planner, not this skill. Reach for an
**external** CLI (Codex, Cursor, Amp, Droid, OpenCode, Antigravity, …) only as **fallback** when
internal lanes miss the needed tool.

## Core Rules

1. Start from the repo, issue, PR, or spec as the source of truth.
2. Use one final integrator — multiple agents may advise/implement, but one owner reconciles outputs.
3. Never let parallel agents edit the same files unless a merge owner and strategy are explicit.
4. Prefer one agent for small tasks. Orchestration overhead must buy lower risk, better coverage, or real parallelism.
5. Require evidence before completion: tests, build, lint, screenshots, CI, or a concrete manual check.
6. Use adversarial review for security, auth, billing, migrations, data loss, release automation, and public contracts.

## Agent Selection

Within the harness, map a step onto the internal partner/gemini lanes first; use this table to pick the external tool as fallback, or to classify a user-named tool.

| Agent/tool | Best use | Avoid when |
| --- | --- | --- |
| Claude Code | Repo-aware interactive implementation, skills/hooks/workflows, local edits | The task is mostly external research or a huge one-shot audit |
| Codex | Deep reasoning, spec/PR audit, code generation, alternative implementation review | It lacks the exact local tool or environment needed to verify |
| Gemini | Huge-context code/docs/image/video analysis, multimodal extraction | Precise repo edits and local test loops are the main work |
| OpenCode | Provider-flexible/local workflows, open execution constraints | The project depends on Claude-specific skills/hooks |
| Antigravity | IDE/workspace orchestration and large exploration passes | A small terminal-only fix is enough |
| Amp | Cross-repo/team context, Sourcegraph-backed code intelligence | The work is local and narrow |
| Droid | Long-running ticket execution with clear acceptance criteria | The task needs tight interactive product judgment |
| Cursor | IDE-native pair programming and fast local iteration | Headless automation or non-IDE workflows are required |

If the tool list is incomplete or the user names a different coding agent, classify by capabilities: context access, edit access, verification access, autonomy level, review strength.

## Workflow

1. Clarify objective, constraints, repo state, deadline, and acceptable risk.
2. Classify the task: feature, bug, refactor, migration, test, review, architecture, docs, release, or incident.
3. Choose the execution shape:
   - **single-agent**: small, low-risk, same file area, easy verification.
   - **sequential**: plan -> implement -> review -> fix -> verify.
   - **parallel**: independent files/modules with explicit ownership.
   - **review-loop**: implementation already exists or risk is high.
4. Assign roles: scout/researcher, planner, implementer, reviewer, tester, docs writer, final integrator.
5. Define file ownership and blocked paths before parallel work starts.
6. Specify handoff format and required evidence for each agent.
7. Reconcile disagreements by checking repo truth, tests, docs, and user requirements; do not average opinions.
8. Produce one final plan, patch, PR summary, or handoff.

## Execution Patterns

### Single-Agent

Use for one focused fix or feature.

```text
Owner: <agent>
Scope: <files/modules>
Verification: <commands/manual checks>
Exit: patch ready + evidence captured
```

### Sequential

Use when each step improves the next.

```text
Planner -> Implementer -> Reviewer -> Fixer -> Tester -> Integrator
```

Rules:
- Reviewer must read the diff and the original request.
- Fixer receives exact findings, not a vague "improve quality" prompt.
- Tester verifies the final state after fixes, not the pre-review state.

### Parallel

Use only when workstreams are independent.

```text
Agent A owns: packages/api/**
Agent B owns: apps/web/**
Agent C owns: docs/**
Integrator owns: shared files, merge conflicts, final test pass
```

Rules:
- Shared files require a named owner.
- Each agent reports touched files and tests run.
- Integrator reads every diff before merging outputs.

**Arbiter checklist (Integrator, before the final integration is declared done).** The final report is blocked until the arbiter answers, independently:
- Did each job produce the requested artifact?
- Did any job fail, timeout, or emit an uncertainty marker?
- Do job outputs contradict each other?
- Were all listed checks run, and did they pass?
- Are claims supported by file paths, command output, citations, or tests?
- Are any destructive actions proposed but not approved?
- Are unresolved questions listed plainly?

### Review Loop

Use for high-risk changes or existing PRs.

```text
Implementation -> Adversarial review -> Fix -> Re-review -> Verification
```

Run at least one reviewer with a different model/tool family when the risk is high enough to justify it.

## Handoff Templates

Copy-ready assignment/brief/review-request/final-integration templates live in `references/handoff-templates.md` — load when you need the exact handoff shape.

## Anti-Patterns

- Agent pile-on for a small edit.
- Parallel implementation with overlapping file ownership.
- Treating model consensus as proof.
- Losing the user requirement after agents debate architecture.
- Accepting a handoff without files touched, evidence, and blockers.
- Letting a reviewer rewrite scope instead of reviewing the requested change.
- Reporting done when only a plan or unverified patch exists.

## Related skills

Soft pointers — reach for these first; not co-install dependencies:

- `hs:partner` — the internal partner lane (a named-provider full-Claude pass); prefer this before an external CLI.
- `hs:gemini` — the internal gemini lane (second-engine advisory/coding pass); prefer this before an external CLI.
- `hs:workflow-orchestrate` — owns internal fan-out across harness subagents / Workflow / Agent Teams.
- `hs:cook` — executes an approved plan phase by phase.
- `hs:review-pr` — reviews a pull request / merge request.
