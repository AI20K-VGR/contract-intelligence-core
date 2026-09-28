# progress-tracking — recording progress

Load during Phase 5 (Verify — Noise-aware measurement-count rubric) and Phase 7 (Log), or when reading back loop state.

## Two recording layers

### 1. Trace audit — `harness/hooks/trace_log.py`

Record events at key milestones (fail-open — trace never blocks the loop):

| Milestone | event | status |
|---|---|---|
| Loop starts | `loop_start` | `running` |
| KEEP | `loop_iter` | `keep` |
| DISCARD | `loop_iter` | `discard` |
| Guard fail | `loop_iter` | `guard_failed` |
| Verify crash | `loop_iter` | `crash` |
| Normal stop | `loop_end` | `complete` / `goal_met` |
| Stuck 10 times | `loop_end` | `stuck` |
| Interrupt | `loop_end` | `interrupted` |

Call:
```python
# harness/hooks/trace_log.py — append_event(hook, event, ...)
append_event(
    hook="hs:loop",
    event="loop_iter",
    actor=None,          # resolve_actor() fills this in
    status="keep",       # or discard / guard_failed / crash
    note="iter-3: add null guard to parse()",
)
```

### 2. TSV results — `loop-results.tsv`

File in the loop's CWD. Append each iteration, do NOT overwrite.

**Schema:**
```
iteration\tcommit\tmetric\tdelta\tstatus\tdescription
```

| Column | Type | Notes |
|---|---|---|
| iteration | int | 0 = baseline |
| commit | string | 7-char short SHA, or `-` on discard/crash |
| metric | float | Value from the Verify command |
| delta | float | Change vs previous best; `-` for baseline |
| status | enum | See status table below |
| description | string | One sentence: what was tried this iteration |

**Status values:**

| Status | Meaning |
|---|---|
| `baseline` | First measurement before any change |
| `keep` | Improved + guard passed, committed |
| `keep (reworked)` | Guard failed first time, rework passed |
| `discard` | No improvement or below Min-Delta |
| `guard-failed` | Metric improved but Guard failed; reverted |
| `crash` | Verify errored or timed out |
| `no-op` | Improved but below Min-Delta threshold |

**Example:**
```tsv
iteration	commit	metric	delta	status	description
0	a1b2c3d	62.5	-	baseline	Baseline coverage harness/scripts/
1	e4f5a6b	65.0	+2.5	keep	Add null input test case for preflight_deps
2	-	64.8	-0.2	discard	Extract assertion helper — metric did not move
3	c7d8e9f	67.3	+2.3	keep	Cover missed branch in verify_install
4	-	-	-	crash	pytest command timed out at 35s — narrow scope needed
```

## Summary every 5 iterations

Print after iterations 5, 10, 15, ...:
```
--- Progress @ iteration 5 ---
Best: 67.3 (baseline: 62.5, +7.7%)
KEEP: 2  |  DISCARD: 2  |  Crash: 1  |  Guard-fail: 0
Most effective strategy: add branch miss tests
```

## Quick read of a running loop state

```bash
tail -5 loop-results.tsv              # last 5 iterations
grep "keep" loop-results.tsv | wc -l  # total KEEPs
```

## Noise-aware — multiple measurements

| Noise | Measurements | Value to use |
|---|---|---|
| low | 1 | Single result |
| medium | 2 | Take the worse value (conservative) |
| high | 3-5 | Median |

High-stakes (last 3 iterations, or delta > 20% baseline): run Verify once extra before committing.
