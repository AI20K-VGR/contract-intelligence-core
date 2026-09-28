# Auto-decision ledger — record what an auto-mode decided on its own

When a mode runs **autonomously** — it edits code or picks an option without asking the
user (default `hs:cook`, `hs:fix --auto`, `hs:code-review --fix/--fix-auto/--auto`,
`hs:review-pr --fix`, `hs:ship`, `hs:vibe`, and the unattended runners `hs:afk`/`hs:goal`/
`hs:loop`) — append ONE advisory line per governance-bearing decision to the ledger. The
ledger is **read-only, advisory**: it never blocks a stage. It is NOT the user-approved DEC
register (`docs/decisions.yaml` → `docs/decisions.md`) — do not touch that here.

## Emit contract

```
python3 harness/scripts/auto_decision_log.py \
    --skill hs:<mode> --mode <auto|fix|...> --label <LABEL> \
    --what "<what was decided>" --why "<why>" --evidence "<file:line | id | quote>" \
    [--in-plan]            # set when the decision stayed inside the active plan lane
```

- `--evidence` is **mandatory** — a decision with no cited `file:line` / id / quote is
  rejected (exit 2, nothing written). `--label` must be in the closed vocabulary.
- The sink resolves the store to the active plan's `artifacts/auto-decisions.jsonl` (or a
  `plans/reports/` fallback) on the MAIN worktree; you normally just call it — pass
  `--plan-dir <abspath>` only when you already resolved the plan dir (the cook barrier does).
- Review later: `auto_decision_log.py --mark-reviewed <id>` (or `--mark-reviewed-all`),
  reading ids from the rendered `auto-decisions.md` view.

## Labels — closed vocabulary (`harness/data/auto-decision-labels.yaml`)

Two baskets. **must_review** (a human should skim): `ARCH`, `DEC-FLIP`, `SCOPE`,
`SECURITY`. **trace_only** (recorded for the trail): `BEHAVIOR`, `DEPS`, `ASSUMPTION`,
`TRIVIAL`. The file carries the per-label criteria. When a decision could sit in either
basket, **lean to the HEAVIER basket** (must_review over trace_only) — a false alarm costs a
skim, a missed one hides a real decision.

## `in_plan` — the caller computes it, the sink only stores the boolean

1. **No active plan** (a stray PR fix, a one-off bug fix) → `in_plan=false` always.
2. **An active plan** → compare the file/work touched against the current phase lane
   (`files_to_create` + `files_to_modify` in `plan-graph.yaml`). In-lane and within the
   phase's intent → `in_plan=true`. A file outside the lane, an API/contract change the plan
   never named, or a choice the plan did not specify → `in_plan=false` (a *deviation*).

## `hs:cook` records ONLY deviations

Cook is the exception: emit **only** when a decision **deviates** from the approved plan
(i.e. `in_plan` would be false). A decision already inside the approved plan is not "the AI
deciding on its own" — the user approved it — so it is not recorded. Every OTHER mode emits
every labelled decision with `in_plan` set correctly.

Cook's ledger is therefore **best-effort with a larger blast radius**: because `in_plan` is
the emit GATE here, mislabelling a deviation as in-plan does not just mistag it — it hides
the deviation entirely (no line at all). So when you are unsure whether something is a
deviation, **lean to recording it** (treat it as a deviation) — an extra line beats a hidden
one. In every other mode a mislabel is only a wrong tag, since the line still exists.

## Writer-model — who calls the sink

- **In-place modes** (default `hs:cook`, `hs:fix`, `hs:code-review`, `hs:review-pr`,
  `hs:ship`, `hs:vibe`, `hs:afk`/`hs:goal`/`hs:loop`) → the agent calls
  `auto_decision_log.py` **directly** (cwd is the main tree, env is correct).
- **Cook `--parallel isolation=worktree`** → a developer subagent must **NOT** call the sink:
  its worktree is `git worktree remove`d after cook, so a line written there is lost. Instead
  the subagent **reports** each deviation (label + what + why + evidence) in its
  result-envelope, and the cook **MAIN** agent (in-place, correct env) folds those reports and
  calls the sink at the **integration barrier** — the point where MAIN has already compared
  output against the plan. One writer, resolving to the correct tree.

## Emit failure is advisory — never halt the mode

If the sink exits non-zero — exit 2 (bad label / missing evidence) or any other error — the
mode **logs it and CONTINUES its work**; it does NOT abort, halt, or stop. exit 2 is the
ledger telling you the LINE is wrong (fix the label/evidence and re-record), not a signal to
stop the mode. This is load-bearing for the unattended runners (`hs:vibe`/`hs:afk`/`hs:goal`/
`hs:loop`) running overnight: one bad ledger line must never kill the whole run.
