# Parallel execution for cook (default-on)

`cook` cooks independent phases concurrently to cut wall-clock. **On by default** (`cook.parallel: true`) — the partitioner only fans out phases marked `parallel_safe` with disjoint `owns`; every other phase stays sequential, so default-on never parallel-edits a shared path. `--parallel`/env still override.
This drawer = full protocol; SKILL.md section = summary. Backing rule: `"${HARNESS_BIN_ROOT:-.}"/harness/rules/orchestration-protocol.md` (delegation context, parallel-ownership safety, `claims.py` 1-winner, status protocol).

## When NOT to use it

Parallelism buys nothing — and adds merge risk — when phases are a dependency chain, when ownership cannot be cleanly split, or when the plan has ≤2 independent phases. Default-on is safe here anyway: the partitioner keeps a coupled or non-`parallel_safe` phase sequential on its own — pass `--parallel`-off routes (env `HARNESS_COOK_PARALLEL=0`) only when you want to force the whole run sequential.

## 1. Resolve the opt-in (deterministic, not eyeballed)

Precedence, highest first:

1. `--parallel` flag on the cook invocation
2. `HARNESS_COOK_PARALLEL` env (`1/true/yes/on` → on)
3. `cook.parallel` in `"${HARNESS_BIN_ROOT:-.}"/harness/data/cook.yaml` (shipped **true**)
4. built-in fallback **false** (only reached if the config layer is absent)

`cook.parallel_max` (default 4) is an advisory cap the orchestrating agent applies when fanning out — the planner below emits the safe partition but does NOT itself limit concurrency:

```bash
python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/cook_parallel_plan.py --root . --phases-json phases.json --expand
# add --parallel to force ON; prints {parallel_enabled, parallel, sequential, conflicts}
```

## 2. Build the phase list

Each phase file declares its parallel eligibility in frontmatter:

```yaml
parallel_safe: true
owns:
  - harness/hooks/simplify_gate.py
  - harness/tests/test_simplify_gate.py
```

`owns` is the set of paths (globs allowed) the phase may create or modify. A phase with no `parallel_safe: true` is always sequential.

## 3. Partition (safety core)

`cook_parallel_plan.partition()` returns three lists:

- `parallel` — `parallel_safe` phases whose `owns` are disjoint from every other `parallel_safe` phase. These may run concurrently.
- `sequential` — everything else: non-parallel-safe phases, plus any phase whose ownership **overlaps** another (overlap demotes BOTH, conservatively).
- `conflicts` — the overlapping pairs and the shared paths, so the fallback to sequential is logged, never silent.

Rule, non-negotiable: **never run two phases that touch a shared path in the same batch.** Same file, a generated artifact, a migration sequence, or shared config all count as shared.

## 4. Delegate each parallel slice

One `hs:developer` subagent per slice, in its own **worktree** (isolation prevents parallel edits from colliding). Pass `isolation="worktree"` **explicitly on the spawn** — `@developer` no longer
self-isolates from its frontmatter, so a slice spawned without the param would run in-place and collide with its peers.
The prompt MUST carry the full delegation context (orchestration-protocol): task · files allowed to read · files allowed to modify (the phase's `owns`) · acceptance criteria · constraints · work-context path · env (CWD, OS). Ownership is enforced 1-winner via
`"${HARNESS_BIN_ROOT:-.}"/harness/scripts/claims.py`.

**Worktree base ref (non-negotiable for dependency-coupled phases).** An isolated worktree branches from the configured base ref — which may be the fresh origin-default, NOT the current branch HEAD. A parallel slice fanned out in the same run as an earlier phase it depends on (it reads a module/file the predecessor just committed) will find that prerequisite ABSENT in the worktree, and the
subagent will improvise — reconstructing the predecessor's files inside its own slice, violating ownership and producing a diff that cannot merge cleanly. Before delegating ANY slice whose phase depends (per the plan-graph edges) on an in-session committed phase: (a) ensure the worktree branches from the current HEAD (so prerequisite phases are present), and (b) verify each prerequisite file
is present in the worktree (`ls <worktree>/<prereq>`). An absent prerequisite means the base ref is wrong — STOP, fix the base, do not let the subagent rebuild it. A phase with no in-session dependency may use the default base. (See `harness/LESSONS.md`.)

Each subagent ends with the status protocol block (`DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT`). `BLOCKED`/`NEEDS_CONTEXT` → change scope/approach, do not re-run the same prompt.

## 5. Verify every slice — MANDATORY, never trust on sight

A returned subagent is an **unverified claim**, not a result. Two tiers:

1. **Self-verify (always)**: cook re-runs that slice's tests + lint and reads the diff against the phase's acceptance criteria. Any red → the slice does not merge.
2. **Independent verify (risky slices)**: spawn an `hs:independent-revalidator` (or `hs:code-reviewer`) subagent that re-derives correctness from the diff ALONE, without the builder's reasoning. Disagreement → the slice returns to sequential rework.

Risky = touches a gate/hook, changes a contract, or has thin test evidence. When unsure, verify independently.

## 6. Integration barrier

After all verified slices merge into the working tree, run the **full suite serially** — the real green gate. Only then write `plans/<plan>/artifacts/verification.json` and commit. `gate_stage.py` is unchanged: `--parallel` never bypasses the artifact gate.

**`--parallel` + `defer_suite` together:** `verification.json` is last-write-wins, so this
barrier's full-suite evidence only survives to `cook close` if the barrier happens to be
the LAST write in the run — a later per-phase scoped write overwrites it. Do not read "the
barrier ran the full suite" as the `defer_suite` debt already paid; check the actual latest
verdict (`"${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/cook/references/deferred-suite.md`).

## Failure handling

- Partition reports a conflict → those phases run sequentially; log the shared paths.
- A slice fails verification → pull it out of the parallel batch, rework sequentially.
- Worktree merge conflict → ownership was mis-declared; fix `owns`, fall back to sequential.
- The integration suite goes red after a clean per-slice pass → an integration gap the per-slice tests missed; bisect by slice, this is exactly what the barrier exists to catch.
