# ISO 25010 coverage matrix — QA-planning lens (on-demand)

A `hs:scenario` reference. "Unit tests pass" is not coverage; it is one of eight quality
dimensions. This matrix forces an explicit decision — *covered*, *N/A with reason*, or
*gap* — for each ISO/IEC 25010 quality characteristic against each task. A silent N/A is
treated as a defect: the plan either tests the property, documents why it is irrelevant,
or the planner accepts the gap in writing.

The canonical 8 characteristics and the per-tier coverage floors are the SSOT in
[`../../../../data/iso-25010-matrix.yaml`](../../../../data/iso-25010-matrix.yaml) — read
that file for the list; this reference does not restate the floor numbers inline (DRY).
This is a QA-planning output, advisory (personal-first) — not a hard local gate.

## When to apply

- After the 13-dimension scenario filter has selected the relevant tasks/features.
- Any task with a non-empty API/data/event contract — integration/contract coverage is
  mandatory there.
- Post-incident: if a production failure exposed a characteristic that had been N/A'd
  silently, re-open the matrix and make that N/A explicit.

Anti-trigger: pure docs/copy changes — skip.

## Build the matrix

Rows = tasks/features; columns = the 8 characteristics from the SSOT. Default every cell
to `unknown`, then:

1. **Classify each cell** as `covered` (a named test layer covers it), `N/A` (with a
   one-sentence reason), or `gap` (should be covered, is not yet).
2. **Map each covered cell to a test layer** — unit | integration | contract | e2e |
   security | load | uat | manual (regression for reliability). A `covered` cell without a
   named layer is actually a `gap`.
3. **Weight by task risk** — pull each task's severity, then apply the floor from the
   SSOT (`risk_floors`: critical 8/8, high ≥6/8, medium ≥4/8, low ≥2/8).
4. **Reject on silent N/A** — every N/A needs a plain-English reason. "Usability N/A —
   internal migration, no human-facing surface" is fine; blank is a reject.
5. **Score it with the machine, then read the defects.** Write the matrix to JSON and run

   ```bash
   python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/iso_matrix_score.py <matrix.json>
   ```

   One row per task: `{"task": ..., "risk": "critical|high|medium|low", "cells":
   {"<characteristic_id>": {"state": "covered", "layer": "unit"} | {"state": "na",
   "reason": "..."} | {"state": "gap"}}}`. The scorer counts the covered cells, applies
   the floor for that row's risk, and refuses a covered cell that names no test layer,
   an N/A with no reason, and a missing cell. Exit 0 = PASS, 1 = FAIL with one sentence
   per defect, 2 = the input could not be read. Do NOT report the coverage counts from
   your own reading — paste what the scorer printed.
6. **Close the gaps** — each `gap` becomes a new test requirement on the task, a new
   test-only work item, or an accepted exception signed by the planner (named).

## Frame

```
        | F.Suit | Perf | Compat | Usab | Reliab | Security | Maint | Portab |
task-041 |  covu  |  gap |  covc  | N/A1 |  covi  |   covs   | covr  |  N/A2  |
task-042 |  covu  | covL |  covc  | covx |  covi  |   covs   | covr  |  cove  |

Legend: cov=covered (layer letter u=unit i=integration c=contract e=e2e s=security
L=load x=uat/manual r=review) · gap=should cover, not yet · N/A=with numbered reason.
N/A1 "internal migration, no UI"   N/A2 "single-platform internal tool"
```

## Decision table

| Task type | Floor characteristics usually covered | Usual N/A |
|---|---|---|
| Schema migration (HIGH) | Functional · Compatibility · Reliability · Security · Maintainability | Usability · Portability |
| User-facing feature (HIGH) | Functional · Performance · Usability · Reliability · Security · Maintainability | Compatibility/Portability if single-platform |
| Internal refactor (LOW) | Functional · Maintainability | most others |
| Background worker (MED) | Functional · Performance · Reliability · Security | Usability |
| Public API change (CRITICAL) | all 8 | none |

## Checklist

- [ ] One row per task, one column per characteristic (8 from the SSOT).
- [ ] Every cell is one of {covered, N/A-with-reason, gap}.
- [ ] Every covered cell names a test layer.
- [ ] Every N/A cell has a plain-English reason ≤1 sentence.
- [ ] Every gap has a closure path.
- [ ] `iso_matrix_score.py` ran on the matrix and its verdict is in the report.

## Anti-patterns

- **Silent N/A** — the single most common bypass; always require a written reason.
- **Counting the cells by eye** — eight columns times N rows against a per-row threshold
  is arithmetic, and a count reported from memory is one nobody downstream can check.
  Run the scorer.
- **Treating unit coverage as total coverage** — it catches ~1/8 of the quality surface.
- **Copy-paste matrices across tasks** — hides task-specific gaps.
- **Retrofitting coverage post-hoc** — a matrix built after implementation reflects what
  was done, not what should have been.
- **N/A'ing Security or Maintainability** — almost never legitimate; flag it.

Adapted from `docs/product/_refs/frankcode-src/qa/methodology/qa/iso25010-coverage.md`;
tracker/PR-routing references dropped, test layers mapped to tier-1 test types. Routing
this reference into `scenario/SKILL.md` (and bumping the dimension count) is the
scenario-skill integration phase's job — not done here.
