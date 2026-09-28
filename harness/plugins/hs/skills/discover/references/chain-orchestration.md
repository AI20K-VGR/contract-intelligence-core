# Chain orchestration — hs:discover

Call order for component skills, exact flags, handoff to hs:plan. Load this drawer in steps 3 and 6 of hs:discover when chain details are needed.

## Standard chain (without --quick)

```
hs:discover
  │
  ├─ 1. hs:research            (evidence gathering)
  │       └─ output: plans/reports/<slug>-research-<date>.md
  │
  ├─ 2. hs:brainstorm --diverge  (generate option space)
  │       └─ output: 2-4 approaches, no selection yet
  │
  ├─ 3. hs:brainstorm --critique (attack the hypotheses)
  │       └─ output: failure modes + reconsider conditions per option
  │
  ├─ 4. hs:brainstorm --converge (finalize recommendation)
  │       └─ output: chosen direction + trade-offs
  │
  └─ 5. Synthesize -> discovery-brief.md
```

## --quick chain

```
hs:discover --quick
  │
  ├─ 1. hs:brainstorm --quick   (single fast pass)
  │       └─ output: 1-2 directions + preliminary recommendation
  │
  └─ 2. Synthesize -> discovery-brief.md  (no evidence link -> write [SKIPPED])
```

## Calling component skills — specific guidance

### hs:research

Call with the central question = the problem framing from step 1.

```
/hs:research
  Topic: <problem to discover>
  Mode: breadth (default) or depth if implementation detail is needed
  Max sources: 5
```

Returns: absolute path to report -> use as the evidence link in the brief. Do not paste the full report content into the brief — only the link + 3-5 bullet summary.

### hs:brainstorm --diverge

```
/hs:brainstorm --diverge
  Problem: <problem framing>
  Hard constraints: <from step 1>
  Evidence: <research report link>
```

Output: 2-4 clearly named approaches, no selection made. Record in the option space of the brief.

### hs:brainstorm --critique

```
/hs:brainstorm --critique
  Options: <A>, <B>, <C> from the diverge step
```

Output per option: Adopt / Adopt-with-guard / Reject + failure modes. Use to fill the "Cons" column and "Risks" section of the brief.

### hs:brainstorm --converge

```
/hs:brainstorm --converge
  Options: <after critique>
  Constraints: <unchanged from step 1>
```

Output: chosen direction + clear trade-offs -> fill section 5 of the brief.

### hs:problem-solving (when blocked)

Trigger: option space is empty after diverge, or frame does not converge after 2 rounds.

```
/hs:problem-solving
  <description of where the block is>
```

After hs:problem-solving returns -> resume the chain from the blocked step.

## Handoff to hs:plan

Tier flag rationale (why each tier's `/hs:plan` command carries the flags it does):
- **Complex / multi-step** -> `--deep` buys per-phase scout (file-inventory + test-scenario matrix + dependency map), pays off when the surface is wide; `--tdd` keeps red->green discipline.
- **Standard feature/refactor** -> `--tdd` keeps red->green discipline; `--deep` skipped: surface doesn't justify the extra scout cost.
- **Tiny** -> `--fast` skips the heavy scout/tdd machinery entirely; no testable code, or change too small to warrant it.

After the brief is written and the user confirms:

1. Return absolute path: `plans/<slug>/discovery-brief.md`
2. `AskUserQuestion`:
   - Option A (recommended): `/clear` then `/hs:plan <brief-path>`
   - Option B: Revise the brief further before planning
   - Option C: Stop, save the brief, plan later
3. If the user chooses A -> remind: the `discover_isolation_nudge` will advise if planning continues in the same session, but `/clear` is the surest way to ensure a clean context (`"${HARNESS_BIN_ROOT:-.}"/harness/rules/workflow-handoffs.md` #5).

## Subagent fan-out (if needed)

When research scope is broad (>5 sources) or the user requests autonomous operation: spawn a `hs:researcher` agent following `"${HARNESS_BIN_ROOT:-.}"/harness/rules/orchestration-protocol.md`. Controller (hs:discover) retains: merging decisions, user approval, writing the brief.
Subagent: research only, returns report + path.

## Chain invariants

- Do not skip critique in the standard chain — critique prevents premature convergence, not optional polish.
- Only write the brief AFTER converge output is available — do not draft it in advance.
- All links in the brief must be absolute paths (usable after a /clear in a future session).
