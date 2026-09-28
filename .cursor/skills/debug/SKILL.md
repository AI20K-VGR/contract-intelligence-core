---
name: hs:debug
injectable: false
description: Systematic debugging with root-cause analysis before fixing. Use for bugs, test failures, unexpected behavior, performance issues, log analysis, CI/CD, and system investigation.
argument-hint: "[--system | --perf | --bisect] [--ultra [N] | --debate]"
allowed-tools: [Bash, Read, Write, Grep, Glob, Task]
metadata:
  compliance-tier: workflow
---

# hs:debug — systematic root-cause investigation

This skill stops at **root cause + failing repro test**. The actual fix belongs to `hs:fix` — always cross-reference after debugging is complete.

**Core rule**: DO NOT FIX before root cause identified. Guess→patch→guess again = waste + new bugs. Out-ranks proactive/"ship-it-fast" bias — no fix, no "probably", until root cause has evidence chain.

**Probe-first ★** (`"${HARNESS_BIN_ROOT:-.}"/harness/rules/agent-operational-discipline.md` — the priority discipline): the evidence chain is BUILT by running the real thing — reproduce, instrument, bisect. Reading the stack trace / `--help` / grep / a chain of reasoning is a *hypothesis*, NOT a probe. A cause you have not exercised for real is `[ASSUMED]`, never OBSERVED (the four claim labels:
`"${HARNESS_BIN_ROOT:-.}"/harness/rules/verification-mechanism.md`) — confirm it with one real run before you call it root cause.

## Modes / flags

| Mode | When to use |
|---|---|
| (default) | bug / test failure / unexpected behavior — code level |
| `--system` | system incident: server error, CI/CD failure, multi-component |
| `--perf` | performance degradation, slow query, high latency — load `references/performance-diagnostics.md` |
| `--bisect` | unclear which commit caused the regression — load `references/reproduction-and-bisection.md` |

**Inline vs delegate**: run default / `--perf` / `--bisect` inline. Delegate to `@debugger` when spanning multiple components/services or needing CI+DB+log correlation — typical for `--system` incidents, so `--system` is the usual delegate trigger (see "Delegating the investigation").

## Main procedure (4 phases — code-level)

Load details: `references/root-cause-method.md`.

**Phase 1 — Collect evidence** (required BEFORE thinking about a fix):
- Read the stack trace and error message in full — skip no lines.
- Reproduce the failure consistently: record the exact steps. Cannot reproduce → collect more data.
- Check recent changes: `git log --oneline -20`, diff config, dependency updates.
- Trace data flow: where does the bad value originate? Trace back up the call stack.

**Phase 2 — Analyze patterns**:
- Find similar working code in repo — compare every difference.
- Identify dependencies: which component, config, or env involved?

**Phase 3 — Hypothesis → evidence loop**: Load `references/hypothesis-loop.md`.
- Formulate 2-3 competing hypotheses — don't lock onto the first.
- Test each: smallest possible change, one variable at a time.
- Confirm/eliminate with evidence. 3+ failed attempts → stop, consider architecture (may need `hs:brainstorm`).
- **When the reasoning itself tangles — ≥ 3 interacting hypotheses (confirming one shifts another) OR a causal chain ≥ 3 hops deep that you are losing track of — you MUST route to `hs:sequential-thinking`** to externalize a labeled, revisable Thought trace (branch / revise / converge) before testing further. This is a DIFFERENT trigger from the 3+-failed-attempts escape above (that goes to
  `hs:brainstorm` / architecture): sequential-thinking is for when the cause IS knowable but the multi-step reasoning no longer fits in your head. Hard route, not a see-also.

**Phase 4 — Finalize root cause + failing repro test**:
- **Write a failing test that reproduces the bug** (`"${HARNESS_BIN_ROOT:-.}"/harness/rules/tdd-discipline.md` — red→green rule: test must fail INTENTIONALLY before the fix).
- Don't fix here — hand root cause + test to `hs:fix`.

## System procedure (`--system`, 5 steps)

Load `references/instrumentation.md` + `references/root-cause-method.md`.

1. **Initial assessment**: collect symptoms, identify affected components, check recent changes (deploy, config, dep update).
2. **Data collection**: server/app logs for the time window; CI/CD via `gh run view
   <id> --log-failed`; DB state via project stack's CLI; system metrics.
3. **Analysis**: reconstruct timeline, identify patterns, trace request path.
4. **Identify root cause**: eliminate hypotheses systematically; document full event chain trigger→symptom.
5. **Propose a fix**: immediate (min to restore service) + root fix + preventive (monitoring gap). Actual fix via `hs:fix`.

## Instrumentation and log analysis

Load `references/instrumentation.md` when additional trace/log observation is needed.

Stack-agnostic tools:
- Log parsing: `grep`, `awk`, `sed` — always use `grep --line-buffered` when piping.
- CI/CD: `gh run list --limit 10`, `gh run view <id> --log-failed`.
- DB: project stack CLI (sqlite3, psql, mysql, etc.) per project.
- Codebase: read `docs/codebase-summary.md` if < 2 days old; otherwise use `hs:scout`.

## Skill output

The skill ends with:
1. **Confirmed root cause** (evidence chain, not "possibly").
2. **Failing repro test** committed (or ready to commit) — this test is the input for `hs:fix`.
3. **Report** at `plans/reports/<slug>-debug-report.md` (format: `references/root-cause-method.md` section Report).
4. Cross-reference: `/hs:fix <path-to-failing-test>` — guides user to the next step.

## Delegating the investigation

For complex investigations (multi-component, CI/CD, system), spawn `@debugger` — runs the full behavioral checklist (gather evidence → 2-3 hypotheses → eliminate → root cause chain → recurrence prevention). Reports written to `plans/reports/`.

```
hs:debug → spawn debugger agent (investigation)
         → failing repro test (tdd-discipline.md)
         → hs:fix (fix)
```

## Boundaries

- Do NOT implement a fix — belongs to `hs:fix`.
- Do NOT skip Phase 1 even if issue "looks simple".
- Do NOT claim "fixed" without a failing test confirming root cause.
- 3+ hypotheses fail: STOP, reconsider architecture, ask user.
- Reports must distinguish "confirmed cause" vs "likely cause" — be honest about certainty.
- Root cause = **recurring trap** (would bite again): flag as `harness/LESSONS.md` candidate for `/hs:remember` once fix lands — don't write it here (debug doesn't mutate).
- `--ultra [N]`/`--debate`: call `hs:workflow-orchestrate --ultra [N]|--debate --run-id <slug>` to size + drive N independent root-cause investigations over the SAME symptoms (no shared context); `hs:escalation-consultant` synthesizes the confirmed cause, and only that cause is reported. Approval gate is `hs:workflow-orchestrate`'s own.

## HARD-GATE (real wiring)

- `"${HARNESS_BIN_ROOT:-.}"/harness/rules/tdd-discipline.md`: a failing repro test is required evidence — no test → debug not complete, cannot hand off to fix.
- `"${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/agents/debugger.md`: the investigation agent has a behavioral checklist (evidence-first, multi-hypothesis, elimination documented).
- Reports → `plans/reports/` (harness-contract rule).

## Red flags — STOP

Thinking any of these → return to Phase 1:
- "Quick fix to get it done, investigate later"
- "Let me try changing X and see"
- "It's probably X, let me just fix it"
- "Tests are passing, done" (when no failing repro test existed beforehand)

## References (load on demand)

| Drawer | Content | When to load |
|---|---|---|
| `references/root-cause-method.md` | Full 4-phase procedure, evidence chain, report format | When the main debug procedure needs detailed steps |
| `references/hypothesis-loop.md` | Formulate/test/eliminate competing hypotheses | When entering Phase 3 (hypothesis testing) |
| `references/instrumentation.md` | Log/trace/metric tooling, stack-agnostic commands | When Phase 1 evidence collection needs instrumentation |
| `references/reproduction-and-bisection.md` | `git bisect` workflow for regression hunting | When using `--bisect` mode |
| `references/defense-in-depth.md` | Four-layer validation pattern: entry, business logic, environment guards, debug instrumentation | When root cause is invalid data reaching unsafe code and multi-layer validation is needed |
| `references/frontend-verification.md` | Browser-driven verification loop (console/network/visual via the chrome-profile + agent-browser skills) | When the bug is in rendered UI / client behaviour |
| `references/performance-diagnostics.md` | Performance toolkit incl. the PostgreSQL `EXPLAIN ANALYZE` query-plan workflow | When diagnosing latency, slow queries, or resource bottlenecks |

