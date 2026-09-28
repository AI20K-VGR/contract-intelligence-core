# Run mechanism — fan-out, probe, measure fairly

The run is pure orchestration (the verdict logic lives in `bakeoff_rank.py`). The only thing that matters here is **fairness** and **minimal probes** — get either wrong and the numbers are meaningless.

## One isolated worktree per candidate

Each candidate gets its own worktree via `hs:worktree` so the probes never touch each other's files:

```bash
# per candidate (see hs:worktree for the full procedure)
git worktree add ../<repo>-bakeoff-<candidate> -b bakeoff/<candidate> <base>
```

Isolation rules (from `hs:worktree` `references/isolation-rules.md`):

- Each worktree owns its own branch; never edit the same file in two worktrees at once.
- Shared config (`harness-hooks.yaml`, `stage-policy.yaml`, `pyproject.toml`) and schemas/migrations are
  **serialized** — modify in one worktree at a time, not in parallel.
- `harness/state/` is append-only JSONL, so the score ledger is race-safe across worktrees.

**v1 runs candidates sequentially.** Sequential is correct; parallel (via `hs:team`) is only a speed optimization and is deferred to BACKLOG — it adds the shared-config serialization hazard for no correctness gain.

## Minimal probe discipline

A probe is a **throwaway stub that measures only the contested axis** — not a feature.

- Build the smallest thing that makes the metric runnable for that candidate. If the decision is "redis vs in-memory cache", the probe is a 30-line adapter behind the existing interface, not a production cache layer.
- The probe is discarded after measuring. Do not invest in code you will throw away.
- If a candidate cannot be probed cheaply, it fails precondition #3 — cut it before fan-out, do not let it blow the budget.

## Fairness (non-negotiable)

The comparison is only valid if every candidate runs **identically**:

- **Same input set** passed to every worktree.
- **Same metric command** run in every worktree — byte-identical.
- **Same trial count** per candidate at a given noise level. `bakeoff_rank.compute_verdict` refuses a winner if any candidate has fewer trials than the noise minimum (low 1 / medium 2 / high 3), so unequal effort cannot manufacture a result.

If A runs on different inputs than B, the bake-off is worthless — stop and fix the harness, do not report a number.

## Budget enforcement (time + tokens)

Per `--budget-seconds` and/or `--budget-tokens` (at least one):

- **Time** is always measured — wall-clock the probe run and pass `--elapsed-s` to `record`.
- **Tokens** are recorded only when the probe ran as a subagent (read the real `subagent_tokens` from the Agent result and pass `--tokens`). For an inline probe with no clean token source, omit `--tokens` — it is stored as `null` and the token budget is skipped for that trial. **Never estimate tokens**; an invented number is exactly the fake-objectivity trap one level down.
- A probe that breaches EITHER ceiling is marked `over_budget` in the verdict — surfaced, not silently dropped, so a runaway candidate is visible.

## Measuring

For each candidate × trial, run the metric in that candidate's worktree on the shared input, then record:

```bash
python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/bakeoff_rank.py record --run <run-id> \
  --candidate redis --trial 1 --value 0.42 --elapsed-s 8.1 --tokens 12000
```

Trials per noise: low → 1; medium → 2 (the verdict keeps the worse one); high → 3-5 (the verdict keeps the median). After all scores are recorded, rank — see `honesty-ledger-and-verdict.md`.
