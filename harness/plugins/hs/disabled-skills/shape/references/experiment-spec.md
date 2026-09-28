# Experiment spec — author + read verdict, kẹp 2 đầu (verification-tiering rule)

`hs:shape` pre-registers a market experiment as a first-class artifact and later
reads its verdict. It does **not** run the experiment. This is the hard boundary
The verification-tiering rule draws: **POC kỹ thuật** (does the thing work) closes at tầng-1 through
`cook`→`test`→`review` (see `poc-gate-loop.md`); **market experiment**
(will customers want it / pay for it) is owned by the PO, and the harness only
clamps the two ends of that loop — author the spec before anyone runs it, read
the verdict after someone else runs it.

## Why pre-register instead of post-hoc

`docs/product/outcomes.md` (`--learn`) was *designed* as a PO outcome loop that records a
*measurement* after the fact: a BRD goal, a target, an actual, a computed verdict — but `--learn`
is not a flag `hs:spec` exposes and `record_outcome.py` does not exist on disk (see
`hs:spec/references/frontmatter-and-id-spec.md`'s Outcome records caveat); it is not a live loop
today. Whether or not that loop ships, it was never going to capture the hypothesis or the decision
rule the PO committed to *before* looking at the numbers. This module adds
that missing pre-registration: `hypothesis` / `design` / `success_metric` /
`decision_rule` are written to `docs/product/shape/experiments/EXP-<n>.md`
BEFORE the experiment is run, so a verdict later can't be quietly rationalized
to fit whatever the numbers turned out to be.

## What lives outside the harness (never build this here)

- Soliciting real customers, running the A/B split, collecting the metric.
- Any fetch/poll/subprocess that "runs" or "checks on" an experiment.
- Multi-run unattended orchestration across many experiments — that is
  tầng-2 `orchestrator/` territory (the two-tier landmine: never import
  `orchestrator/**` from a skill script).

`experiment_spec.py` and `experiment_verdict.py` are guarded against this
drifting back in: `harness/tests/test_shape_experiment.py` greps both scripts'
source for running-code tokens (`subprocess`, `urllib`, `requests`,
`http.client`, `socket.`) and for any `orchestrator` import — both must be
absent. These are hard mechanical guards, not just prose.

## File model

One file per experiment (unlike the DEC ledger's single append-only file):
`docs/product/shape/experiments/EXP-<n>.md`, YAML frontmatter + free-text body.
A separate file per experiment lets `experiment_verdict.py` rewrite just that
one artifact's frontmatter in place when the verdict lands, without touching
any other experiment's record.

| Field | Type | Notes |
|---|---|---|
| `id` | `EXP-<n>` | parent-free, monotonic — max existing `EXP-<n>.md` filename + 1, never reused |
| `hypothesis` | string | the falsifiable claim under test |
| `linked_to` | `[id]` | brd_goal/prd/epic ids from `hs:spec`'s spec graph; a story id or a truly missing id both flag as `dangling_linked_to` (author still writes the file — this is a flag, not a rejection) |
| `design` | object | free-form `{method, control, variant}` or similar — description only, never executable |
| `success_metric` | string | the metric slug the decision_rule judges |
| `decision_rule` | object | `{direction, target, hit_floor, partial_floor}` — see Verdict math below |
| `status` | `draft \| running \| concluded` | `draft` at author time; `concluded` after `apply_verdict` |
| `verdict` | `hit \| partial \| miss \| null` | null until concluded |
| `actual` | number \| null | the PO-supplied metric result, set by `apply_verdict` |
| `measured_on` | ISO date \| null | set by `apply_verdict`, defaults to today (UTC) |

Schema backing: `schemas/experiment.schema.json` (draft-07, validated in tests
via `jsonschema` — same optional-dependency pattern as `spec-graph.schema.json`,
skipped with `pytest.importorskip` if the library is unavailable).

## Verdict math (deterministic, 3-tier)

Modeled on `outcome_verdict.py`'s ratio-floor computation (see the "Verdict
math" paragraph in `frontmatter-and-id-spec.md`'s Outcome records section) —
reimplemented locally in `experiment_verdict.py` rather than imported, since
that module lives in a separate `product-spec` project (its own tree, not
part of this harness install) and this skill cannot take a cross-project
dependency on it.

- `direction: higher` → `ratio = actual / target`
- `direction: lower` → `ratio = target / actual` (`actual <= 0` → best possible → `hit`: 0 avoids the div-by-zero, and a negative actual — e.g. a churn delta that fell — is at least as good as 0)
- `ratio >= hit_floor` → `hit`
- `partial_floor <= ratio < hit_floor` → `partial`
- else → `miss`

`decision_rule.target` must be a positive finite number (rejects `<= 0`, `NaN`,
and `±Inf` — a `target: 0` divides by zero under `higher`, a negative target
sign-flips the ratio, and a `NaN` target slips a bare `<= 0` check then makes
every ratio `NaN` → a constant `miss`) and `0 <= partial_floor < hit_floor <= 1` — both checked by
`validate_decision_rule()` at author time AND again at verdict time (a
hand-edited or otherwise corrupted spec file is caught, not crashed on).

`compute_verdict()` is a pure function of its five scalar arguments — same
inputs always produce the same verdict; there is no clock, no I/O, no randomness
in the math itself.

## Write containment

Every write resolves through `experiment_path(root, rel)`: it resolves
`root/docs/product/shape/experiments/<rel>`, asserts the resolved path is still
*under* that directory, and raises `PermissionError` on escape (`..`, an
absolute override, a symlink pointing outside). This is the same invariant
shape as `shape_paths.shape_path()`, reimplemented independently here —
`experiment_spec.py` depends only on `spec_graph` (for `linked_to`
resolution), never on `shape_paths`, so the two modules stay independently
testable and buildable in either order.

## CLI

```
python3 experiment_spec.py --root <ws> --add \
    --hypothesis "..." --linked-to BRD-G1,PRD-AUTH \
    --metric signup-conversion --method "A/B" \
    --direction higher --target 10 --hit-floor 0.9 --partial-floor 0.5

python3 experiment_verdict.py --root <ws> --id EXP-1 --actual 9.4
```

`experiment_spec.py --list` and `experiment_verdict.py`'s CLI both exit
non-zero with a one-line `error: ...` message on a malformed input — never a
raw Python traceback.
