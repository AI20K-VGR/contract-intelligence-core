---
name: hs:bakeoff
injectable: true
description: Empirical bake-off — run 2-4 candidate probes on one mechanical metric, pick the winner by numbers or hand to a human when inside the noise band. Use when reasoning can't separate measurable options.
argument-hint: "<decision> [--candidates a,b,c] [--metric '<cmd>'] [--noise low|medium|high]"
allowed-tools: [Bash, Read, Write, Glob, Grep, SlashCommand]
metadata:
  compliance-tier: workflow
---

# hs:bakeoff — decide by running, not by guessing

Several candidate directions, undecidable by reasoning. Build a cheap probe for each, run every probe on the SAME input set + the SAME mechanical metric, and let the numbers pick the winner — or refuse to pick when the gap is inside the measured noise. Trust reality, accept token cost, **but only when justified**.

**Probe-first ★** (`"${HARNESS_BIN_ROOT:-.}"/harness/rules/agent-operational-discipline.md` — the priority discipline): this skill IS the probe-first discipline made mechanical — the numbers a bake-off produces are OBSERVED; a candidate you reasoned about but never ran is `[ASSUMED]`, never OBSERVED. Never report a winner from argument alone, and never fabricate an "objective" metric where only
reasoning exists (see the table below).

## When to use / When NOT

| Situation | Use |
|---|---|
| ≥2 viable directions + a mechanical metric + reasoning can't separate them | **hs:bakeoff** |
| Decision a minute of reasoning settles | `hs:predict` / `hs:brainstorm` (cheaper) |
| No mechanical metric (only an LLM "quality score") | `hs:predict` — do NOT bake-off (fake objectivity) |
| Improving ONE solution over time against a metric | `hs:loop` (time axis, not comparison axis) |
| Unattended long run | `hs:afk` |

## Inputs

Missing any → `AskUserQuestion` (collect all at once).

| Field | Required | Example |
|---|---|---|
| `Candidates` | Yes (2-4) | `redis`, `in-memory`, `sqlite` |
| `Metric` | Yes | shell command printing **one number**, exit 0 (same contract as hs:loop) |
| `Direction` | Yes | `lower` (ms, bytes) or `higher` (throughput, coverage) |
| `Noise` | No (default medium) | `low`=1 trial · `medium`=2 worse-of · `high`=3-5 median |
| `rel_band` | No (default 0.05) | win margin: gap must beat 5% of the best score |
| `Budget` | Yes (≥1 axis) | `--budget-seconds` and/or `--budget-tokens` per probe |
| `Input set` | Yes | the fixed inputs every candidate runs against |

## Gate-first preconditions

Run BEFORE building any probe — `references/gate-first-preconditions.md`. Two halves:

1. **Machine-checked** — `bakeoff_rank.py preflight` (N∈[2,4], safety-scan, budget ceiling) + a dry-run of the metric (exit 0 + one number). Any fail → REFUSE, fall back to `hs:predict`.
2. **Judgment checklist** (you confirm with the user): is each probe a cheap *stub* (not a full feature)? is this decision load-bearing and costly to reverse? Both "no" → don't bake-off.

## Process

1. **Preflight** — dry-run the metric; `python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/bakeoff_rank.py preflight --candidate … --metric-cmd … --budget-seconds …`. Refuse on non-zero. Confirm the judgment checklist.
2. **Fan-out** — one isolated worktree per candidate via `hs:worktree`. Minimal throwaway probe ONLY, measuring the contested axis. Details → `references/run-mechanism.md`.
3. **Measure** — run the SAME metric on the SAME input in each worktree, N trials per noise; record each: `bakeoff_rank.py record --run <id> --candidate <c> --trial <i> --value <n> [--elapsed-s --tokens]`.
4. **Rank** — `bakeoff_rank.py rank --run <id> --direction … --noise … --rel-band … --plan-dir <plan>`. Exit 0=winner, 3=tie, 4=insufficient. Details → `references/honesty-ledger-and-verdict.md`.
5. **Report** — print the FULL scoreboard incl. losers + `observed_spread` + any `over_budget`. On tie/insufficient, hand to the human — do NOT invent a winner. Return the winning direction to the caller.
6. **Cleanup** — prune candidate worktrees (`hs:worktree remove`); keep the winner's branch if useful.

## HARD-GATE (real wiring)

- `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/bakeoff_rank.py` — `preflight` refuses N∉[2,4] / unsafe metric / over-budget; verdict refuses a winner when `gap ≤ band` (`band = max(rel_band·rep, observed_spread)`) or trials < noise minimum. Ledger is append-only JSONL under `state_dir()/bakeoff/` (actor+ts, no RMW).
- `"${HARNESS_BIN_ROOT:-.}"/harness/schemas/artifact-bakeoff-verdict.json` — the verdict shape. The verdict is a **handoff artifact**, NOT a stage gate — hs:bakeoff blocks no stage.

## Boundaries

- Do NOT bake-off a decision reasoning settles cheaply, or a metric an LLM scores (fake objectivity).
- Do NOT build full features — probes are throwaway stubs measuring the contested axis only.
- Do NOT silently drop losers; always show every candidate's score + spread.
- Tie within noise or too few trials → hand to the human; never manufacture a winner.
- Metric is a **proportion** (pass fraction, accuracy, hit rate) → the spread band above is
  not the noise test. Same items for every candidate: `wilson.py --mcnemar` on the discordant
  pairs, an interval containing 0.5 is a tie. Different item sets: `wilson.py --diff`, an
  interval containing 0 is a tie. Report `k/n` per candidate.
- Never call two candidates different because their intervals "overlap a bit" — that is not a
  comparison. Load `"${HARNESS_BIN_ROOT:-.}"/harness/rules/sampled-rate-reporting.md`.
- Report the winner on a **held-out** set, not the set the candidates were tuned against.
- Do NOT bypass `preflight`. Scope creep / multi-metric → record via `backlog_register.py add`.
- On completion: verdict path + full scoreboard + the winning direction (or the human-handoff reason).

## Output language

Render reports per `"${HARNESS_BIN_ROOT:-.}"/harness/rules/output-rendering.md`: resolve `language` / `audience` / `humanize` live via `python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/output_config.py --resolved` (never hand-read the tracked file); the rule holds the register behavior and the evidence-invariant fence.

## References (load on demand)

| Drawer | Content |
|---|---|
| `references/gate-first-preconditions.md` | The 4 conditions (machine vs judgment), preflight command, fall-back rule |
| `references/run-mechanism.md` | Worktree-per-candidate, minimal-probe discipline, fairness, budget enforcement |
| `references/honesty-ledger-and-verdict.md` | Noise/band rule, min-trial table, the 3 verdicts, no-silent-cut |
