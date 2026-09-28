# Metrics Guide — hs:retro

Definitions, formulas, and interpretation thresholds for each metric. Include the formula in the report so readers can verify the figures.

---

## Velocity Metrics

### Commit Frequency
**Measures:** delivery cadence.
**Formula:** `total_commits / days_in_period`
**Thresholds:**
- `< 1/day` — sparse commits; check for blocked PRs or large batches
- `1–3/day` — healthy for solo or small teams
- `> 5/day` — high activity; verify commits are meaningful, not noise

### Active Day Ratio
**Measures:** fraction of days with at least one commit out of total days in the period.
**Formula:** `days_with_commits / days_in_period * 100`
**Thresholds:**
- `> 70%` — steady cadence, no major gaps
- `40–70%` — acceptable; check whether any days were blocked
- `< 40%` — batch pattern; investigate cause

---

## Code Health Metrics

### LOC Added / Removed / Net
**Measures:** volume of code written and deleted.
**Interpretation notes:**
- Negative net (more removed than added) in non-test files = good (simplification)
- Positive net > 500 LOC/day sustained → check whether quality is keeping pace

### Churn Rate
**Measures:** code rewritten vs. retained.
**Formula:** `(LOC_added + LOC_removed) / max(LOC_net, 1)`
**Thresholds:**
- `1.0–1.5` — additive and clean, low rewrite
- `1.5–3.0` — normal iteration
- `> 3.0` — high rework; worth discussing in the retro

### Test-to-Code Ratio
**Measures:** test coverage accompanying code changes (proxy — measures presence, not quality).
**Formula:** `test_file_changes / total_file_changes * 100`
**Harness pattern:** files matching `test_*.py`, `*_test.py`, `harness/tests/`, `harness/e2e/`
**Thresholds:**
- `> 30%` — tests accompany changes (TDD discipline — rule `"${HARNESS_BIN_ROOT:-.}"/harness/rules/tdd-discipline.md`)
- `10–30%` — partially tested
- `< 10%` — tests lagging; technical debt accumulating

### File Hotspots
**Measures:** most frequently changed files.
**Key threshold:** a file appearing in > 30% of commits likely has high coupling — consider refactoring. Top 3 hotspots per period → include in action items if recurring.

---

## Commit Distribution

**Measures:** distribution of conventional commit types (`feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `perf`).
**Interpretation:**
- `feat > 40%` — feature-driven period
- `fix > 40%` — reactive period (many bugs); investigate cause
- `refactor > 20%` — code quality investment (good if intentional)
- `test > 15%` — TDD discipline maintained

---

## Plan Metrics

### Task Completion Rate
**Formula:** `tasks_done / (tasks_done + tasks_open) * 100`
**Source:** `[x]` / `[ ]` checkboxes in plan files modified during the period.
**Thresholds:**
- `> 80%` — on track
- `60–80%` — acceptable; check blockers
- `< 60%` — scope inflation or capacity mismatch; action needed

---

## Delta Columns (only with --compare)

For each compared metric, add a delta column:
- `+N` / `-N` for absolute values
- `+N%` / `-N%` for ratios

`+` on commit frequency, active ratio, test ratio = improvement. `+` on churn rate = degradation — note the direction clearly in the report.
