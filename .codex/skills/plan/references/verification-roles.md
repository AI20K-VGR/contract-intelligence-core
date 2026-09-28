# Verification roles — verifying the plan before and after validate/red-team (on-demand)

Applied when: the planner self-verifies while writing phases, validate-gate runs a verification pass, or red-team uses it as an evidence filter. The evidence rules live in `"${HARNESS_BIN_ROOT:-.}"/harness/rules/verification-mechanism.md` — this file is the **recipe for specific roles**.

## Tiers (auto-scale by phase count)

| Phase count | Tier | Active roles | Budget |
|---|---|---|---|
| 1-2 | Light | Fact Checker | 5 claims/phase |
| 3-4 | Standard | Fact Checker + Contract Verifier | 10 claims/phase |
| 5+ | Full | All 4 roles | 15+ claims/phase |

## Role: Fact Checker

Goal: every file path, symbol, endpoint, and config key declared in the plan must exist.

```bash
grep -rn "<symbol>" .          # confirm symbol exists
# glob "<path>" to confirm file path
```

Output per claim: `VERIFIED (file:line)` | `FAILED (not found)` | `ASSUMED (unconfirmed)`

## Role: Flow Tracer

Goal: behavior claims ("X calls Y", "middleware runs before handler") must be traceable from entry point to target through real code.

- Read the actual code path: entry -> guards -> branching -> target.
- List early returns, middleware chain, and event listeners in the path.
- Async: verify ordering guarantees (await, Promise.then, callback).

Output: traced path with `file:line`, or FAILED + explanation of the actual flow.

## Role: Scope Auditor

Goal: new state (field, singleton, env var) must not leak across isolation boundaries.

- Grep all instantiation sites of the struct/class receiving a new field.
- Determine lifetime: per-request / session / process-global.
- Flag when a new field duplicates an existing field (different name, same purpose).

Output: lifetime classification + instantiation sites, or FAILED + leak description.

## Role: Contract Verifier

Goal: interface changes (API endpoint, function signature, config schema) must enumerate ALL consumers — do not write "update all callers" generically.

```bash
grep -rn "<function_name>" .   # list all callers
```

- If >10 callers: list the first 10 + total count.
- Check downstream: tests, imports, re-exports, barrel files.
- Check upstream: config files, CI scripts, CLI help text.

Output: caller list `file:line` + compatibility assessment, or FAILED + missing callers.

## Whole-Plan Consistency Sweep

Runs AFTER any validate or red-team session that edits plan files.

1. Re-read `plan.md` + ALL `phases/phase-*.md`.
2. Build a delta list from the current session: renamed fields/APIs/files/tags, reversed decisions, reordered phases.
3. Search all plan files for old terms, stale assumptions, duplicate embedded drafts.
4. Reconcile: not just the edited file, but the entire plan.
5. Append results to `## Validation Log` or `## Red Team Review`:

```markdown
### Whole-Plan Consistency Sweep
- Files reread: plan.md, phases/phase-1-..., phases/phase-2-...
- Decision deltas checked: N
- Reconciled stale references: N
- Unresolved contradictions: N
```

If `Unresolved contradictions > 0`: list each conflict + affected files, ask the user before recommending cook. Only **0 contradictions** allows a cook recommendation.

## Integration points

- **Planner self-verify** when writing phases: apply Fact Checker inline; tag `[ASSUMED]` (or `[PRIOR]` for claims resting on prior/training knowledge) for claims that cannot be confirmed -> validate-gate handles them later.
- **Validate-gate** (Step 7): run the appropriate tier before asking the user; FAILED findings become additional questions.
- **Red-team**: each reviewer brings an adversarial lens + verification role; findings without `file:line` -> auto-reject.
- **After any propagation**: run Whole-Plan Consistency Sweep before recommending cook.

## Backing

- `"${HARNESS_BIN_ROOT:-.}"/harness/rules/verification-mechanism.md` — 5 invariants + two-way Evidence Filter.
- `"${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/plan/references/validate-gate.md` — validate workflow.
- `"${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/plan/references/red-team-gate.md` — red-team workflow.
