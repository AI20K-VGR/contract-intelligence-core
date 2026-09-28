# Retrospective — {TIMEFRAME}

**Period:** {SINCE} → {UNTIL}
**Generated:** {TODAY}
**Repo:** {REPO_NAME}
**Active authors:** {AUTHOR_COUNT}

---

## Velocity

| Metric | Value | {COMPARE_COL} |
|---|---|---|
| Total commits | {TOTAL_COMMITS} | {DELTA_COMMITS} |
| Commits / day | {COMMITS_PER_DAY} | {DELTA_CPD} |
| Active days | {ACTIVE_DAYS} / {PERIOD_DAYS} ({ACTIVE_PCT}%) | {DELTA_ACTIVE} |
| Files changed | {FILES_CHANGED} | {DELTA_FILES} |

*Omit delta column if `--compare` was not used.*

---

## Code Health

| Metric | Value | {COMPARE_COL} |
|---|---|---|
| LOC added | {LOC_ADDED} | {DELTA_LOC_ADDED} |
| LOC removed | {LOC_REMOVED} | {DELTA_LOC_REMOVED} |
| LOC net | {LOC_NET} | {DELTA_LOC_NET} |
| Churn rate | {CHURN_RATE}x | {DELTA_CHURN} |
| Test-to-code ratio | {TEST_RATIO}% | {DELTA_TEST} |

*Formulas: see `references/metrics-guide.md`. Omit delta column if `--compare` was not used.*

---

## Commit Type Distribution

```
{COMMIT_TYPE_DISTRIBUTION}
```

Example format:
```
feat     ████████████ 12 (40%)
fix      ████████      8 (27%)
chore    ████          4 (13%)
refactor ███           3 (10%)
test     ██            2  (7%)
docs     █             1  (3%)
```

---

## File Hotspots

Most-changed files:

| # | File | Change count |
|---|---|---|
| 1 | {FILE_1} | {COUNT_1} |
| 2 | {FILE_2} | {COUNT_2} |
| 3 | {FILE_3} | {COUNT_3} |
| … | … | … |

---

## Plan Progress

| Metric | Value |
|---|---|
| Tasks done | {TASKS_DONE} |
| Tasks still open | {TASKS_OPEN} |
| Completion rate | {PLAN_PCT}% |

---

## Team Breakdown

*Include only when `--team` is set. Remove this section if the flag was not used.*

| Author | Commits | LOC net | Types |
|---|---|---|---|
| {AUTHOR_1} | {COMMITS_1} | {LOC_1} | {TYPES_1} |
| {AUTHOR_2} | {COMMITS_2} | {LOC_2} | {TYPES_2} |

---

## What went well

- [OK] {POSITIVE_1}
- [OK] {POSITIVE_2}

*2-4 observations grounded in real numbers. No generic praise.*

---

## What to improve

- [!] {IMPROVE_1} — metric reference: {METRIC_REF_1}
- [!] {IMPROVE_2} — metric reference: {METRIC_REF_2}

---

## Action Items

1. **{ACTION_1}** — {RATIONALE_1} (based on: {METRIC_1})
2. **{ACTION_2}** — {RATIONALE_2} (based on: {METRIC_2})
3. **{ACTION_3}** — {RATIONALE_3} (based on: {METRIC_3})

*3-5 specific, actionable items. No generic advice.*

---

*Source: git history. Missing data → N/A, not 0.*
