# Run-state, resume & metrics

Machine-written run-state and the metrics corpus live under the **harness state dir**
(`harness_paths.state_dir()` — gitignored, e.g. `.harness/state/`), NOT under `plans/reports/`
(that is human-facing report scratch). `plan_orchestration.py` emits the resolved `state_path`
and `history_path` in its proposal.

For a real fan-out (above a small threshold — a two-sub spawn does not need it), write
`state.json` at `<state_dir>/orchestrate/<run-id>/state.json` on every job transition. It
records per job: id, runtime, model, task, status, exitCode, durationMs, timedOut, attempts,
worktree. On a crash, power loss, or killed session, rerun with `--resume <run-id>` —
completed jobs are skipped, in-flight jobs re-dispatch as a new attempt. Writes are atomic
(`.tmp` + replace) so a partial state.json never wedges the resume.

Append one JSON line per finished job to `<state_dir>/orchestrate-history.jsonl` via
`orchestrate_metrics.py`: run id, job id, runtime, model, task, duration, status, exit code,
attempts, and token/cost when the harness reports them. Every row is stamped with actor + ts.
The corpus is **advisory only**: at report time, when enough rows for a runtime/model/task
pair contradict the routing table, add a reviewable "routing suggestions" section to the
report. **Never silently edit a routing reference mid-run** — routing changes stay reviewable.
