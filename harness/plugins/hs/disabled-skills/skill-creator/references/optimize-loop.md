# Optimize: iterate a description until it triggers right

When `validate` (trigger-eval, `references/eval-validate.md`) shows under- or over-triggering, `optimize` closes the loop automatically: eval the description, ask a model for a structurally different one, re-eval, keep the best. It is a manual, opt-in tool — it spawns real `claude -p` processes and never runs in CI.

## The self-improvement loop

`scripts/run_loop.py` drives the loop:

1. Split the eval-set into **train** and **test** (stratified by `should_trigger`) so the chosen description isn't overfit to the queries that tuned it.
2. Each iteration: `trigger_eval.run_eval` the current description on train+test, record history.
3. If all **train** queries pass → stop (converged). If `max-iterations` hit → stop.
4. Otherwise `improve_description` (via `claude -p`) proposes a new description from the failures + blinded history (test scores stripped so the model can't peek).
5. At the end, pick the iteration with the best **test** score (or train if no holdout).

```bash
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/skill-creator/scripts/run_loop.py \
  --eval-set <eval.json> \
  --skill-path harness/plugins/hs/skills/<name> \
  --model <model-id> \
  --max-iterations 5 --holdout 0.4 --runs-per-query 3 \
  --results-dir <dir>      # optional: save results.json + per-iteration improve logs
```

Output is JSON: `best_description`, `best_score`, `exit_reason`, `iterations_run`, plus the full `history`. No HTML — the harness keeps reports in markdown. Without `--results-dir` the per-iteration improve transcripts are not written anywhere — pass it if you want to inspect why each round changed the description.

`improve_description.py` can also be run standalone on a single `run_eval` result (`--eval-results <json> --skill-path <dir> --model <id>`) to get one proposal.

## Human-in-the-loop — the loop proposes, you decide

`run_loop` returns the best *candidate*; it does NOT edit the skill. Read the `best_description`, sanity-check it against the skill's real scope, and apply it by hand (or via `refine`). A description that scores well on a small eval-set can still be wrong — the number is an aid, not an authority. The honesty caveat from `eval-validate.md` applies: a low trigger rate can mean the model did the
task directly, not that the description is weak.

## Output-quality benchmark (templates + aggregate) — bundled, needs an executor

`agents/{grader,comparator,analyzer}.md` and `scripts/aggregate_benchmark.py` support a *different* question than trigger-eval: not "does the description trigger" but "does the skill produce better output **with** vs **without** the skill." That flow needs an
**executor** that runs the skill on tasks and writes transcripts + `grading.json` per run — which this skill does NOT ship. What is bundled:

- **grader** — grade expectations against a transcript + outputs, and critique the evals.
- **comparator** — blind A/B comparison of two outputs with a generated rubric.
- **analyzer** — post-hoc unblind ("why did the winner win") + benchmark-pattern notes.
- **aggregate_benchmark.py** — roll per-run `grading.json` files into summary stats (mean/stddev/min/max, with/without-skill delta) + a markdown report.

Treat these as the prompt contracts + the aggregator for a benchmark harness you wire yourself. They are faithful ports, intentionally bundled for that build-out — not a turnkey benchmark. Don't read "they're here" as "the benchmark runs."

## Cost, sizing, and failure handling

- **Cost is multiplied.** One run is up to `max_iterations × queries × runs_per_query` real `claude -p` eval calls, plus up to `max_iterations × 2` improvement calls. `run_loop` prints this estimate to stderr before it starts — read it. The documented default (`--max-iterations 5 --runs-per-query 3`) on a 10-query set is ~150+ paid calls.
- **Eval-set must be big enough for the holdout.** A tiny set under a high `--holdout` can send every query to test, leaving train empty. `run_loop` refuses that (raises) rather than reporting a phantom "converged" — add queries or pass `--holdout 0`.
- **A model failure stops the loop cleanly.** If `claude -p` times out / errors / returns an empty or untagged response, the loop does not crash or adopt garbage: a hard CLI failure ends the loop early (`exit_reason: improve_error`) and still returns the best candidate found so far; an untagged/refusal response keeps the current description unchanged for that round. Run from inside the project
  (where `.claude/` lives) so the trigger-eval sees the real skill catalog.

## Flags worth knowing

| Flag | Meaning |
|---|---|
| `--max-iterations` | cap improvement rounds (default 5) |
| `--holdout` | test fraction held out from tuning (default 0.4; 0 disables the split) |
| `--runs-per-query` | samples per query for a stable trigger rate (default 3) |
| `--num-workers` | parallel `claude -p` workers (default 1 — raise deliberately) |
| `--model` | required: which model proposes descriptions / answers eval queries |
