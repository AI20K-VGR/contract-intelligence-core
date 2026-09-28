# Deferred suite — `--defer-suite` / `defer_suite`

Details for `needs_close`'s conditional reference in `cook.yaml`.
Backing: `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/defer_suite_carry.py`,
`"${HARNESS_BIN_ROOT:-.}"/harness/scripts/graph_test_scope.py`,
`"${HARNESS_BIN_ROOT:-.}"/harness/scripts/hs_run_cook.py` (`_phase_scoped_next_action`,
`_pending_for_debt`, `_suite_debt_unpaid`).

## What the flag changes

A plan approved with `defer_suite: true` (set via `/hs:plan --defer-suite`, pinned into
the approval hash) runs each phase's 3.V verify against ONLY the test files that phase's
own `plan-graph.yaml` node declares (`files_to_create`/`files_to_modify`, filtered
through the repo's test-path pattern) — not the full suite. The full suite runs once,
before `cook close`, instead of once per phase.

Without the flag: byte-identical to today. `pending` stays `[]`, no `route_flags` key
rides the envelope, no state here ever fires.

## The debt this creates, and how it is paid

Running a phase scoped means that phase's own verify never actually ran the full
suite — so the plan owes ONE full-suite run before it can honestly close. Pay it with
the same command every stack already uses:

```
python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/run_local_tests.py --harness
```

then record it with the stage that says WHICH run it was:

```
hs-run cook verify --phase <the last node's id> --stage deferred-suite \
    --verdict PASS --check regression:PASS
```

The `--stage deferred-suite` is load-bearing, not decoration. There is still no
separate artifact and no plan-wide phase id — `write_verification.py` requires a real
plan-graph node id — so the stage is what separates this run from the per-phase verify
that writes the same file. Omit it and the record reads as one more scoped run, which
is exactly what it would be.

## How you are reminded

Three channels, all derived from disk on every `hs-run cook next` call, never from a
cached cursor:

- `pending[]` — one item, in English (matching every other envelope field), whenever
  the flag is carried and the debt is unpaid. Never names a phase — the per-phase
  snapshot freezes at its own first PASS and every defer_suite snapshot is small by
  design, so "the snapshot whose total matches a full run" cannot answer this question
  either way. Reading it costs one JSON parse; it never runs a test collector.
- `advisory` — a plain-language nudge that fires once the plan reaches the
  `suite_debt_unpaid` close-refusal state.
- `route_flags` — carries `["defer_suite"]` in the envelope, which is what makes this
  file itself show up in `references` at `needs_close`.

## What "paid" means, mechanically

The debt reads as paid when the plan's canonical `verification.json` (or `.yaml`)
carries BOTH a closeable verdict (`PASS` or `PASS_WITH_RISK`) AND `stage:
deferred-suite`. Still no test count, no total, no junit — one more field on a record
that already exists.

Reading the verdict ALONE was tried first and measured broken: every phase's scoped
verify overwrites this same canonical file, so the last phase silently settled the debt
with a handful of tests and `cook close` returned 0 with the full suite never run. The
gate was dead on the exact flow it exists to catch, and every test of it missed that,
because each provoked the state by DELETING the file — something the ordinary flow
never does.

The residual limit is real and unchanged in kind: the stage says which run it WAS, not
how much it ran, so a scoped run stamped `deferred-suite` still reads as paid. An agent
who FORGETS is caught; an agent who MISREPRESENTS is not. That is the signed design —
treat all of this as a reminder, never a trap that catches a deliberately dishonest
record.

## When the debt-payment run itself fails

A debt-payment run that fails never reaches `suite_debt_unpaid` — it surfaces as
`phases_incomplete` instead, blaming the LAST plan-graph node, which may not be the
phase that actually caused the regression. Mechanically: the only valid way to record
this run is `write_verification.py --phase <a real plan-graph node>` (`--phase DEBT` or
any other non-node id is rejected: "not a plan-graph node"; omitting `--phase` is
rejected too), so a BLOCKED verdict lands under that node's id, flips
`derive_plan_completion.completion_state` to incomplete ("the latest write for phase
... was verdict 'BLOCKED', superseding an earlier PASS snapshot"), and `cook close`
dies at the `phases_incomplete` gate before the defer_suite gate is ever reached.
Read `phases_incomplete`'s warning as possibly a full-suite regression misattributed to
the last phase, not necessarily that phase's own defect — do not go fix the named phase
on faith alone when this flag is carried.

## Do not

- Do not invent a new artifact or check name for "full suite" — there isn't one, by
  design.
- Do not run `pytest --collect-only` or any subprocess to compute `pending` — it must
  stay a pure JSON read.
- Do not skip the full-suite run because a phase's own scoped verify already came back
  green. Scoped green proves the files that phase touched; it proves nothing about the
  rest of the tree.
