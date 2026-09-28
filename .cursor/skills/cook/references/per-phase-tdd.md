# Per-phase TDD — red→green execution per phase

References `"${HARNESS_BIN_ROOT:-.}"/harness/rules/tdd-discipline.md` (the single source of truth for the red→green rule). This drawer explains how to apply it per-phase inside hs:cook.

## Three sub-steps per phase

On a `mode: hard` plan, sub-steps **3.T and 3.I both run INSIDE the `@developer` subagent** (it writes the failing test AND implements); main owns **3.V verify + a review of the subagent's code AND test + the commit**. On `--in-place`/`fast`, all three run at main.

```
3.T  Write test for NEW behavior → run to confirm intentional FAIL (wrong assert / ImportError)
3.I  Implement the minimum required to make the test pass
3.V  Re-run FULL suite (`python3 -m pytest harness/tests/ -q`) → paired commit test+module
     (scoped to the node's declared files only when the plan carries `defer_suite: true` —
     "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/cook/references/deferred-suite.md)
```

Sub-step 3.T must NOT be green before 3.I — if it is already green, the test is wrong; rewrite it.

## Delegation posture (sub-by-default + `--in-place` + resolution order)

The per-phase **red→green loop (3.T write the failing test + 3.I implement)** is **delegate-by-default**, mirroring code-review's `--in-place` opt-out: on a `mode: hard` plan the whole phase goes to a `@developer` subagent; the main thread keeps verify, a **review of the subagent's code AND test strength** (catch a tautological or weakened test), and the paired commit.
This is a **prose posture, not a hard gate** — it isolates the implement context and pins the standards read-directive onto a fresh subagent, but nothing blocks an inline run.

**Resolution order (first match wins).** Mode is READ from a deterministic source — a flag, the plan frontmatter, or the `plan-graph.yaml` sidecar — NEVER inferred from a prose impression that a plan "feels hard":

1. `--in-place` passed → main implements inline (the 3C fall-back); stamp `in-place:true` on the run note. The manual override always wins over the plan mode.
2. the covering **phase file** frontmatter opts into inline (`in_place: true`, `mode: fast|inline`, or `delegate: inline`) → inline for THAT phase.
   A phase-level signal beats the plan mode (it is more specific). Canonical case: a phase whose `owns` land where a `@developer` subagent cannot
   write (subagent RBAC confines writes to `harness/**` + `plans/**`), so main must cook it inline. Scoped to the phase's `owns` — an unscoped
   override does not silence unrelated writes.
3. plan frontmatter `mode: hard` → delegate the full red→green phase (test 3.T + implement 3.I) to `@developer`.
4. plan frontmatter `mode: fast` → inline, no subagent.
5. NO `mode:` in the plan frontmatter AND no `--in-place` → assess the `plan-graph.yaml` sidecar, not the difficulty in your head: **delegate** when the
   DAG is substantial (more than one phase, or a non-trivial modified-file footprint across the nodes' `owns`); go **inline** only for a genuinely
   trivial single-phase / few-file plan. The signal is the artifact's phase count + modified files — a deterministic read, not a gut call.

**Sequential delegate (NOT `--parallel`):** a `mode: hard` sequential run hands ONE phase at a time to a `@developer` writing **in-place** (no worktree — worktrees are only for `--parallel`, which branches from a base ref; see LESSONS.md on parallel-cook worktree base-ref).
The full delegation-context snippet (task · read/modify globs · acceptance · constraints · env) lives in `references/subagent-patterns.md` (`## Sequential Per-Phase Delegate`). A risky slice still verifies via the tier-2 independent verifier before its commit; Steps 4–6 stay MANDATORY.

## Paired commit

Commit after 3.V includes test + module, conventional commit, no AI references. Hard stage gate (`harness/hooks/gate_stage.py`) reads `verification.json` — this artifact must exist before advancing to the next stage.

## Fix loop

When 3.V fails: fix the **code**, do not delete/skip/weaken tests. Report lists ALL failures (name + 1-line reason). Verdict PASS / PASS_WITH_RISK / BLOCKED is written to `plans/<plan>/artifacts/verification.json`. Include `phase: <P-id>` (the matching `plan-graph.yaml` node id) in that verification — on a PASS, the `phase_progress_writer` hook snapshots it to `verification-<phase>.json`, the
per-phase evidence safe auto-close counts. A stateless phase still writes its verification (with `phase`), so its evidence is not lost.

**Preferred write path:** `python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/write_verification.py <plan_dir> --phase <id> --stage <stage> --verdict PASS --check <type>:PASS ...` writes the canonical verification, snapshots it, and drives the plan lifecycle deterministically in one run — 
even when the verification is not written through the Write tool (a Bash write never trips the `phase_progress_writer` hook, so the
snapshot/auto-close would otherwise be silently skipped). Hand-writing `verification.json` (a complex case: manual anchors, a grace clause) still works — the PostToolUse hook is the fallback net.

## Stateless phase

Phase with `stateless: true` in frontmatter: skip trace for that phase; `gate_stage.py` still runs (`"${HARNESS_BIN_ROOT:-.}"/harness/hooks/gate_stage.py` advisory, exit 0). Trace is telemetry fail-open — not a compliance gate.
