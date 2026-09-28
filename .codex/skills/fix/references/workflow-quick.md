# Quick Workflow

Fast scout-diagnose-fix-verify cycle for simple issues.

## Steps

### Step 1: Scout (Minimal)
Locate affected file(s) and their direct dependencies only.
- Read error message → identify file path
- Check direct imports/dependencies of affected file
- Skip full codebase mapping

**Output:** `✓ Step 1: Scouted - [file], [N] direct deps`

### Step 2: Diagnose (Abbreviated)
Activate `hs:debug` skill. Activate `hs:sequential-thinking` for structured analysis.

- Read error message/logs
- **Capture pre-fix state:** Record exact error output (this is your verification baseline)
- Identify root cause (usually obvious for simple issues)
- Skip parallel hypothesis testing for trivial cases

**Output:** `✓ Step 2: Diagnosed - Root cause: [brief description]`

### Step 3: Fix & Verify
Implement the fix directly.
- Make minimal changes
- Follow existing patterns

**Parallel Verification:**
Launch `Bash` agents in parallel:
```
Task("Bash", "Run typecheck", "Verify types")
Task("Bash", "Run lint", "Verify lint")
```

**Before/After comparison:** Re-run the EXACT pre-fix command; compare output.

Parallel exploration: spawn read-only scouts per `hs:scout`.

**Output:** `✓ Step 3: Fixed - [N] files, verified (types/lint passed)`

### Step 4: Review + Prevent
Use `@code-reviewer` subagent for quick review with explicit side-effect sweep.

Prompt: "Quick review of fix for [issue]. Check: (a) acceptance criteria met, (b) no regression to business logic in blast-radius from Step 1 scout, (c) no breaking changes to public contracts (signatures, schemas, APIs, env vars), (d) follows existing patterns, (e) no new lint/type/build errors. Score X/10. Explicitly flag any side effects."

See HARD-GATE-NO-SIDE-EFFECTS in SKILL.md — on reviewer-flagged regression → `AskUserQuestion` with 2-4 options (revert / narrow / update dependents / accept).

**Prevention (abbreviated for Quick):**
- Type errors/lint: type system IS the test → regression test optional
- Bug fixes: add at least 1 test covering the fixed scenario
- Still require before/after comparison of verification output

**Review handling:** See `references/verify-and-gate.md`

**Output:** `✓ Step 4: Review [score]/10 - [prevention measures]`

### Step 5: Report
Report summary to user (root cause, files changed, prevention).

**Output:** `✓ Step 5: Reported`

### Step 6: Finalize

Mirrors `SKILL.md` Step 6 (gate → commit → optional sync/journal). Only the gate + commit are required; the rest are conditional.

1. **If the fix is part of a plan** → activate `/hs:project-management` to sync plan/task status, update progress, hydrate Claude Tasks. (No active plan → skip.)
2. Spawn `@docs-manager` subagent if API/behavior changed.
3. `TaskUpdate` to mark Claude Tasks complete.
4. Spawn `@git-manager` subagent to commit (ask user first; conventional commit, no AI reference).
5. Optional: `/hs:journal` (or `/hs:remember`) to capture a repeatable failure mode; skip a one-off.

**Output:** `✓ Step 6: Finalized - gate passed, committed[, synced/journaled]`

## Skills/Subagents Activated

| Step | Skills/Subagents |
|------|------------------|
| 1 | `hs:scout` (minimal) or direct file read |
| 2 | `hs:debug`, `hs:sequential-thinking` |
| 3 | Parallel `Bash` for verification |
| 4 | `@code-reviewer` subagent |
| 5 | Report |
| 6 | `/hs:project-management` (if plan active), `@docs-manager`, `@git-manager`, `/hs:journal` (optional) |

**Extra:** `hs:context-engineering` if dealing with AI/LLM code

## Notes

- Skip if review fails → escalate to Standard workflow
- Total steps: 6
- No planning phase needed
- Pre-fix state capture is STILL mandatory (even for quick fixes)
- Step 6: gate + commit are required; `/hs:project-management` sync-back applies only when the fix is part of a plan; journaling is optional
