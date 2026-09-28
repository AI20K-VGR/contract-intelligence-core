# POC-gate loop — closing the technical-feasibility half at tầng-1

`hs:shape --poc` closes a narrower question than the market experiment does: does the
thing actually work, technically. That question is answered entirely by the harness's
own already-closed dev loop — `hs:plan` → `hs:cook` → `hs:test` → `hs:code-review` — not
by anything this skill builds or re-runs.

## Why a POC is not another review engine

`hs:code-review` already produces a machine-written verdict (`review-decision.json`),
and the verification step already produces its own (`verification.json`). Both carry the
same three-way taxonomy: `PASS` / `PASS_WITH_RISK` / `BLOCKED`. `poc_gate.py` reads those
two artifacts — nothing else — and records the result on a POC sidecar record. It never
spawns a review, never shells out, never fetches anything over the network:
`harness/tests/test_shape_poc_gate_loop.py`'s `test_no_running_code_in_poc_gate` and
`test_no_review_spawn_tokens_in_poc_gate` grep the script's own source for the tokens
that would indicate otherwise (`subprocess`, `urllib`, `requests`, `http.client`,
`socket.`, a `Task(` spawn, a literal `code_review`/`code-review.py` reference) — these
are hard mechanical guards, not just prose.

## Closed means both, not either

A POC only reads as **closed** when the review verdict AND the verification verdict are
BOTH exactly `PASS`. `PASS_WITH_RISK` is a conscious soft-accept upstream, not a closure
license here — the same posture hard stages already take on that verdict elsewhere in
the harness. A `BLOCKED` review, a missing artifact, or a verification that never ran all
leave the POC open.

## Fail-open on a missing or reshaped artifact

`poc_gate.py` reads each verdict artifact defensively: an absent file, a file that is not
valid JSON, or a JSON object without a recognized `verdict` value all read back as an
unknown verdict (`None`) rather than raising. A moved path, a renamed field, or a POC
authored before the verifying run even exists must not crash the gate — the POC simply
stays open until a real `PASS`/`PASS` pair lands. This is a deliberate advisory posture,
not a best-effort excuse: the gate never fabricates a `PASS` it did not actually read.

## Why the POC-gate precedes a roadmap rollup

A milestone rollup that counts unproven work as done is worse than no rollup at all. The
data flows one way only: a POC's `closed` verdict is a precondition a roadmap rollup
reads before counting a milestone's work as feasible — the POC-gate loop never reads
roadmap state back, and never reorders a roadmap itself. There is no cycle here by
construction, only a one-directional precondition edge.

## Storage

One file per POC, `docs/product/shape/poc/POC-<n>.md` (YAML frontmatter + free-text
body) — the same one-file-per-record shape the sibling task and experiment sidecars use,
so `gate()` can rewrite just that one record's frontmatter in place without touching a
sibling POC. `POC-<n>` is parent-free and globally monotonic (max existing `POC-<n>.md`
filename + 1, never reused).

| Field | Type | Notes |
|---|---|---|
| `id` | `POC-<n>` | monotonic, never reused |
| `subject` | string | what this POC verifies (a story id, a feature description) |
| `plan_id` | string \| `null` | the `plans/<plan_id>` this POC is verified by — see `ba-to-plan-intake.md`'s two-way link |
| `status` | `open \| closed` | `closed` only after `gate()` reads a `PASS`/`PASS` pair |
| `verdict` | `PASS \| PASS_WITH_RISK \| BLOCKED \| null` | the raw review verdict as read |
| `verification_verdict` | same enum \| `null` | the raw verification verdict as read |
| `closed` | boolean | `verdict == PASS and verification_verdict == PASS` |
| `review_decision_path`, `verification_path` | string \| `null` | the artifact paths `gate()` was pointed at, for audit |

## CLI

```
python3 poc_gate.py --root <ws> --add --subject "shorter signup form is technically feasible"

python3 poc_gate.py --root <ws> --gate --id POC-1 \
    --review-decision plans/<plan_id>/artifacts/review-decision.json \
    --verification plans/<plan_id>/artifacts/verification.json \
    --plan-id plans/<plan_id>
```

`--gate` requires `--id` and `--review-decision`; `--verification` and `--plan-id` are
both optional (a POC can gate on a review verdict alone — it will simply not close
without a verification verdict too).
