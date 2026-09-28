# exit-conditions — stop conditions and crash recovery

Load during Phase 5 (Verify) or Phase 8 (Repeat or Stop).

## Stop matrix (any one condition → stop)

| Condition | Action |
|---|---|
| `Iterations` maximum reached | Stop, print final report |
| 10 consecutive DISCARDs | Stop, print report, suggest manual intervention |
| Metric reaches Goal | Stop, print success report |
| File `loop-stop` exists in CWD | Stop immediately (user soft interrupt) |
| Ctrl-C / session interrupt | Stop, record trace event `interrupt`, print memory summary |

When stopping: record 1 event in `harness/hooks/trace_log.py` (`event: loop_end`, `status: complete|stuck|interrupted|goal_met`).

## Crash recovery — Phase 5 Verify

| Verify result | Meaning | Action |
|---|---|---|
| Exit 0, prints a number | Success | Proceed to Phase 5.5 / 6 |
| Exit 0, no number | Command is wrong | Record `error:no-number`, revert, prompt to fix Verify command |
| Exit non-zero | Verify crash | Record `error:verify-crash`, revert, count as DISCARD |
| Timeout > 30s | Too slow | Record `error:timeout`, STOP LOOP, notify user |

## Crash recovery — Phase 5.5 Guard

```
Guard fail →
  git revert HEAD --no-edit →
  rework attempt 1 (different approach) →
    Guard fails again →
  rework attempt 2 (minimal change) →
    Guard fails again →
  record guard-failed → DISCARD
```

Never relax/modify the Guard to pass — Guard failure means the change is wrong, not the Guard.

## Revert vs reset

| Command | Preserves history | Use when |
|---|---|---|
| `git revert HEAD --no-edit` | Yes — preferred | Default DISCARD |
| `git reset --hard HEAD~1` | No | Revert produces a conflict |

Reason: `git log --grep="loop(iter-"` depends on intact history. Reset destroys try-discard data needed for pattern analysis.

## Dual-exit condition (task-complete AND no-new-work)

Loop ends only when **both** true:
1. **Task-complete**: metric reached Goal, or Iterations budget is exhausted.
2. **No-new-work**: Scope is fully explored (no files/techniques left untried) or 10 consecutive DISCARDs after rotating strategy.

Only one of two met → continue (if budget remains) or report plateau.

## Final report (printed when stopping)

```
--- Loop end ---
Baseline → Final: X → Y  (delta: Z, N%)
Iterations: total M  |  KEEP: K  |  DISCARD: D  |  Crash: C  |  Guard-fail: G
Best iteration: #n <description> (delta: +/-)
Assessment: [continue / plateau / goal met / manual intervention needed]
loop-results.tsv: <absolute path>
```

Next-step suggestions:
- Goal met → clean commit, suggest `hs:test` to verify everything.
- Plateau → suggest expanding Scope or switching technique manually.
- Stuck 10 times → suggest `hs:debug` to find why the metric is not improving.
- Further unattended run → suggest `hs:afk` for Docker sandbox + reviewer-stage.
