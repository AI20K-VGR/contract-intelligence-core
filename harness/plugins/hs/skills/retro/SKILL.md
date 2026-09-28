---
name: hs:retro
injectable: false
description: Generate data-driven retrospective reports from git history — velocity, code health, hotspots, plan progress. Use for sprint reviews, periodic assessments, or engineering lookbacks.
argument-hint: "[timeframe] [--compare] [--team]"
allowed-tools: [Bash, Read, Write]
metadata:
  compliance-tier: workflow
---

# hs:retro — data-driven retrospective

Analyze git history to produce an objective retrospective report — no guesswork, no invented numbers. Lessons → action proposals; architectural lessons worth keeping long-term → record as a decision via `decision_register.py`.

**No commits, no code changes — read-only.**

## Flags

| Flag | Default | Description |
|---|---|---|
| `timeframe` | `7d` | Time range: `7d`, `2w`, `1m`, or `YYYY-MM-DD:YYYY-MM-DD` |
| `--compare` | off | Compare with the preceding period of the same length |
| `--team` | off | Break down by author |

No argument → `AskUserQuestion` to ask for timeframe and mode.

## Workflow

### Step 1 — Resolve the time range

Resolve `timeframe` into `SINCE` / `UNTIL`. With `--compare`, also compute `PREV_SINCE` / `PREV_UNTIL` (immediately preceding period, same length).

### Step 2 — Collect raw git data

Run the commands in `references/git-queries.md`. Record `0` for a genuine zero-count (e.g. 0 commits found); record `N/A` for unavailable/skipped data (e.g. no `gh` CLI). **Never invent numbers.**

Data groups:
- **Velocity**: total commits, commits/day, active days, files changed
- **Code health**: LOC added/removed/net, churn rate, test-to-code ratio
- **Commit types**: conventional commit type distribution
- **File hotspots**: top 10 most-changed files

### Step 3 — Compute derived metrics

See formulas in `references/metrics-guide.md`. Include the formula in the report so readers can verify the figures.

### Step 4 — Scan plans/

```bash
find plans/ -name "*.md" -newer /tmp/retro-since-sentinel 2>/dev/null | head -20
grep -r "\- \[x\]" plans/ | wc -l   # tasks done
grep -r "\- \[ \]" plans/ | wc -l   # tasks still open
```

Count `[x]` / `[ ]` checkboxes in plan files modified during the period.

### Step 5 — Analyze and propose

From real data:
- **What went well** (≥2): grounded in specific numbers — no generic praise
- **What to improve** (≥2): linked directly to a metric (hotspot, high churn, low test ratio)
- **Action items** (3-5): specific, actionable, tied to a metric

Architectural lessons (a decision worth recording long-term) MUST go to `decision_register.py`:
```bash
python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/decision_register.py --append-alloc ...
```

Everything else (short-term technical lessons, not substantial enough for a decision) MUST go to `backlog_register.py add`.

### Step 6 — Export report

Use the template at `references/retro-output-template.md`. Fill every cell with real data.

Save to: `plans/reports/retro-{YYMMDD}-{slug}.md`
- `YYMMDD` = today's date (`date +%y%m%d`)
- `slug` = timeframe (e.g. `7d`, `1m`, `2w-compare`)

With `--team`: add a per-author breakdown table.

After saving: print the absolute path of the report file.

### Step 7 — Journal when needed

If a serious failure pattern is detected (test ratio < 10% sustained, hotspot ≥ 30% of commits, churn rate > 3x consecutively) → suggest the user activate the `@journal-writer` agent to record it with full context (agent at `harness/plugins/hs/agents/journal-writer.md`).

## Boundaries

- Read git history, `plans/`, `docs/` only. **DO NOT** edit any source files.
- Markdown output goes only to `plans/reports/` (rule `"${HARNESS_BIN_ROOT:-.}"/harness/rules/harness-contract.md`).
- If `gh` CLI is unavailable: mark `N/A` instead of skipping a table row.
- Lessons → record via `backlog_register.py add` (do not create a standalone REVIEW.md).
- Recurring architectural decisions → `decision_register.py`, not code comments.
- On exit: return the absolute path of the report + a 3-bullet summary (what-went-well / what-to-improve / top action item).

## Related skills

- `hs:insights`: telemetry twin — reads runtime telemetry where this skill reads git history; use both for a full picture.

## HARD-GATE (real wiring)

No dedicated blocking gate — this skill is read-only. However:
- Bash does not trigger the stage gate for pure read commands.
- Invocation telemetry would come from `"${HARNESS_BIN_ROOT:-.}"/harness/hooks/track_skill_invocation.py`, but that hook ships **disabled** (no lens reads its sink) — assume the invocation sink is empty and do not treat it as a source. Enable it in `"${HARNESS_BIN_ROOT:-.}"/harness/data/harness-hooks.yaml` first if you want those counts.
- Report files are only valid inside `plans/reports/` — violations are caught by the CI invariant.
