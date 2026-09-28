# Subagent Patterns

Standard patterns for spawning and using subagents in cook workflows.

## Task Tool Pattern
```
Task(subagent_type="[type]", prompt="[task description]", description="[brief]")
```
> **The param is `subagent_type` — exact spelling.** A mistyped key (e.g. `subject_type`) is
> silently ignored and the spawn falls back to the DEFAULT general-purpose agent, not the one you
> named — no error, just the wrong agent running the gate. If a spawn returns a general-purpose /
> `claude` agent when you asked for `hs:code-reviewer`/`hs:tester`, suspect a param-name typo and
> respawn. This matters most at the mandatory Step 5 review: a general agent lacks the reviewer
> lens, so the independent-review gate becomes theatre.

## Research Phase
```
Task(subagent_type="hs:researcher", prompt="Research [topic]. Report ≤150 lines.", description="Research [topic]")
```
- Use multiple researchers in parallel for different topics
- Keep reports ≤150 lines with citations

## Scout Phase
- Use `/hs:scout ext` (preferred) or `/hs:scout` (fallback) — scout is a SKILL, not a spawnable agent

## Planning Phase
```
Task(subagent_type="hs:planner", prompt="Create implementation plan based on reports: [reports]. Save to [path]", description="Plan [feature]")
```
- Input: researcher and scout reports
- Output: `plan.md` + `phases/phase-*.md` files (scaffold layout)

## UI Implementation
```
Task(subagent_type="hs:ui-ux-designer", prompt="Implement [feature] UI per ./docs/design-guidelines.md", description="UI [feature]")
```
- For frontend work
- Follow design guidelines

## Testing
```
Task(subagent_type="hs:tester", prompt="Run test suite for plan phase [phase-name]", description="Test [phase]")
```
- Must achieve 100% pass rate

## Debugging
```
Task(subagent_type="hs:debugger", prompt="Analyze failures: [details]", description="Debug [issue]")
```
- Use when tests fail
- Provides root cause analysis

## Code Review
```
Task(subagent_type="hs:code-reviewer",
     prompt=("Review changes for [phase] against these MANDATORY checks: "
             "(a) every acceptance criterion met; (b) no regression to business logic in "
             "touchpoints/blast-radius from scout; (c) no breaking changes to public contracts "
             "(signatures, schemas, APIs, env vars) unless explicitly called out; (d) follows "
             "existing patterns from scout; (e) no new lint/type/build errors anywhere. "
             "CONTEXT — scout summary: <scout-summary>; acceptance criteria: <acceptance-criteria>. "
             "Return score (X/10), critical, warnings, suggestions, and explicitly flag any side "
             "effects to trigger HARD-GATE-NO-SIDE-EFFECTS."),
     description="Review [phase]")
```

Write reviewer output into `review-decision.json` using `_shared/workflow-artifacts.md`. Score is advisory.

## Adversarial Validation
```
Task(subagent_type="hs:code-reviewer",
     prompt="Adversarial validation for [phase]. Disprove implementation claims only. Check acceptance coverage, regression reachability, public contracts, and verification proof. Forbidden: style polish and broad rewrite suggestions. Return JSON-ready fields for adversarial-validation.json: decision, disprovenClaims[], unverifiedClaims[], missingProof[], reachableRegressions[].",
     description="Adversarial validate [phase]")
```
- Trigger for `--auto`, high-risk surfaces, large diffs, and ship/push/PR/deploy.
- Do not average reviewers. Any evidenced critical issue blocks.

## Domain-Risk Review
```
Task(subagent_type="hs:code-reviewer",
     prompt="Domain-risk review for [auth|secrets|payments|db|api|deploy|filesystem|production-config]. Return risks to risk-gate.json and blocking findings only.",
     description="Domain-risk review")
```
- Trigger only when the touched files affect the named domain.
- Keep findings tied to file/line evidence and required verification.

## Conditional Simplify
```
Task(subagent_type="hs:code-simplifier", prompt="Simplify these files while preserving behavior exactly: [file-list]", description="Simplify recent edits")
```
- Trigger when live `git diff --numstat HEAD --ignore-all-space` breaches any `thresholds` entry in `harness/data/simplify-policy.yaml` (shipped: 400 LOC / 8 files / 200 single-file LOC)
- Scope the prompt to `git diff --name-only HEAD`
- Verify with `git diff --shortstat HEAD -- [file-list]` before/after the subagent; do not rely on the agent's prose summary
- You cannot skip it: the gate has no env knob by design, and its `mode` lives in
  a write_guarded file only a human edits

## Project Management
Activate the `/hs:project-management` skill or the project-manager agent (MANDATORY at Finalize):
> Run full sync-back in [plan-path]: reconcile completed tasks with all phase files, backfill stale completed checkboxes across all phases, update plan.md status/progress, and report unresolved mappings.

## Documentation
```
Task(subagent_type="hs:docs-manager", prompt="Update docs for [phase]. Changed files: [list]", description="Update docs")
```

## Git Operations
```
Task(subagent_type="hs:git-manager", prompt="Stage and commit changes with conventional commit message", description="Commit changes")
```

## Sequential Per-Phase Delegate
The delegate-by-default path for a `mode: hard` plan running sequentially (NOT `--parallel`): one `@developer` per phase writing **in-place** (no worktree — worktrees are for `--parallel` only), doing the full red→green (writes the failing test AND implements).
`@developer` does **not** self-isolate: a plain spawn (no `isolation` param) runs in-place in the current tree, so its writes land where you cook. Do NOT pass `isolation` for a sequential phase.
Pass the full delegation-context; the main thread keeps verify, a **review of the subagent's code AND test** (catch a tautological or weakened test), and the paired commit.
```
Task(subagent_type="hs:developer",
     prompt="Implement phase [phase-file] in-place, TDD red→green.\n"
            "Read/modify globs: [globs] (in-lane only).\n"
            "Acceptance: [criteria per phase Success block].\n"
            "Constraints: [standards, no gate weakening, no other owner's files].\n"
            "Return: summary + files touched; do NOT commit — main commits.",
     description="Implement phase [N] sequential")
```
- One phase at a time; main verifies the slice, reviews the subagent's code AND test (catch a tautological or weakened test), then commits the test+module pair.
- A risky slice → tier-2 independent verifier before the commit.

## Parallel Execution
Each parallel slice MUST pass `isolation="worktree"` **explicitly** — `@developer` no longer self-isolates, so without the param a parallel slice would write in-place and collide with its peers on a shared tree.
```
Task(subagent_type="hs:developer", isolation="worktree", prompt="Implement [phase-file] TDD red→green (write the failing test + implement) with file ownership: [files]", description="Implement phase [N]")
```
- Launch multiple for parallel phases
- Include file ownership boundaries
