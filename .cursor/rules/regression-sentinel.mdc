# Regression sentinel — one test per past incident, never delete

Institutional memory encoded as tests: an incident that reached a user becomes a test
that can never silently re-happen. The register (`harness/scripts/sentinel_register.py`
→ `harness/data/regression-sentinel.yaml`) is the SSOT index of these bindings — read
it when triaging a bug, write to it when a post-mortem closes.

## When a sentinel is mandatory

- **Every P0/P1 incident post-mortem** — the closing step registers at least one sentinel
  binding reproducing the original defect (`sentinel_register.py --add`). No sentinel,
  no closed post-mortem.
- **P2 with real user impact** — optional; add when the pattern is likely to repeat.
- **A new critical user journey** identified during a plan — bind a sentinel for the
  journey's north-star path within the same plan, not deferred to "later".
- **Anti-trigger**: a docs-only change does not need a new sentinel (existing sentinels
  still run in the regular suite; their outcome is informative, not a new-binding
  trigger).

## Workflow

1. **Write the reproducer first.** A red test that fails on the commit that caused the
   incident. If a red reproducer cannot be written, the root cause is not understood
   yet — do not register the sentinel prematurely.
2. **Land the regression test under `harness/tests/`** (or the target repo's own test
   tree), named for the *behavior*, never for a plan/DEC/incident label
   (`docs/code-standards.md` §4 — no plan-ID/DEC in test names).
3. **Register the binding**: `sentinel_register.py --add --incident-id <id> --symptom
   <s> --root-cause <r> --detection <d> --user-impact <u> --test-path <path to the
   test>`. The register refuses (non-zero exit, actionable reason) a missing header
   field or a repeat incident-id — a re-occurring incident-id means the earlier
   binding should be archived, not silently shadowed.
4. **Run on every suite pass.** There is no separate CI job for sentinels in this
   harness (unlike a dedicated `ci-acceptance.yml` job elsewhere) — a sentinel is a
   regular test under `harness/tests/`, so it runs on every
   `python3 harness/scripts/run_local_tests.py --harness` / full pytest pass. A
   red sentinel blocks the same way any other red test blocks (tdd-discipline rule:
   100% pass is the gate) — no bypass, no "known flake" skip.
5. **Flake is a defect, not noise.** A sentinel that flakes is worse than one that is
   missing — it teaches the team to ignore red. Root-cause the flakiness (determinism,
   timing, leaked state) and land a genuinely green replacement; do not quarantine or
   skip it to unblock a merge.
6. **Quarterly audit.** Walk `sentinel_register.py --list --status all`: archive
   bindings whose underlying flow is retired (`--archive`, never delete), check for
   duplicate coverage (two bindings for the same defect — consolidate, keep the union
   of reasons in one `test_path`), and confirm every live binding still names a test
   file that exists.

## Never-delete invariant

- The register has **no `delete` verb** — retiring a sentinel is **archive**
  (`status: active` → `status: archived`), which keeps the record. The count of
  records in `regression-sentinel.yaml` never decreases.
- Deleting the underlying test file to "unstick" a red suite is forbidden the same way
  weakening any other test is forbidden (tdd-discipline rule) — fix the code, or
  fix a genuinely wrong test with a stated reason; a sentinel is never the wrong test
  just because it is inconvenient.
- A hand-edit of `regression-sentinel.yaml` that removes a record is a decision that
  erases institutional memory — treat it like any other silent SSOT rewrite: it needs
  a DEC/BACKLOG entry stating why, not a quiet diff.

## Decision table

| Signal | Response |
|---|---|
| P0/P1 incident post-mortem without a sentinel | Post-mortem does not close until `sentinel_register.py --add` lands |
| Sentinel flakes | Root-cause immediately; ship a green replacement; never quarantine/skip |
| Sentinel fails on an unrelated change | Do not relax it — read the failure; it likely caught something real |
| New critical journey identified in a plan | Add its sentinel within the same plan, not deferred |
| Retired flow whose sentinel no longer applies | `sentinel_register.py --archive`; never delete the record or the test |
| Two bindings cover the same defect | Consolidate into one test, keep the union of reasons, archive the redundant binding |
| Repeat incident-id on `--add` | Rejected (non-zero exit) — archive the prior binding first, then add the new one under a fresh id |

## Checklist

- [ ] Every P0/P1 incident in the tracked period has ≥ 1 sentinel binding in
      `regression-sentinel.yaml`.
- [ ] Each binding carries all required fields (incident-id, symptom, root-cause,
      detection, user-impact, test-path) plus machine-written `actor` + `ts`.
- [ ] The sentinel suite runs on every full local/CI pass — failure blocks the same
      as any other red test.
- [ ] No sentinel is quarantined or skipped to force green.
- [ ] `regression-sentinel.yaml` lists every binding's status (`active` | `archived`);
      `sentinel_register.py --list --status all` is the source of truth, not a
      hand-maintained doc.
- [ ] A critical-journey sentinel exists for each live plan's north-star path.
- [ ] Quarterly audit performed; archived bindings still present (count never drops).
- [ ] Retiring a sentinel used `--archive`, never a hand-edit that removes the record.

## Anti-patterns

- **Deleting a flaky sentinel to unstick a merge** — erases institutional memory to
  buy a green checkmark; root-cause the flake instead.
- **A sentinel that doesn't reproduce the original defect** — false reassurance; if the
  red reproducer step (workflow #1) was skipped, the binding is worthless.
- **Sentinels living as ad-hoc, unregistered tests** — a regression test under
  `harness/tests/` that never gets an `--add` binding is easy to lose track of and
  never surfaces in a quarterly audit.
- **Skipping the sentinel step for an "emergency" hotfix** — emergencies are exactly
  the incidents that most need a binding, or the same class of bug returns.
- **A binding with no context** (thin symptom/root-cause prose) — six months later
  nobody remembers why the test exists; fill every required field honestly, not with
  placeholder text.
- **Treating pass/fail as binary with no flake awareness** — a sentinel that passes
  95% of the time is already a defect (workflow #5).

## Where this is wired

Routed by the CLI at two `hs-run test` states (`hs-run-registry.d/test.yaml`), which
is the only mechanical wiring that exists — no skill body carries a pointer to this
file. The two entries below describe how the defect workflow is meant to USE the
register; they are convention, not something a gate hands you at the step.

- **`hs:triage`** (`hs:scout` → `hs:debug` → `hs:fix` → `hs:test`): when triage
  classifies an incident as P0/P1, its close-out step runs
  `sentinel_register.py --add` for the reproducing test `hs:fix` landed, instead of
  leaving the binding implicit.
- **`hs:fix`**: after a red-first regression test goes green, check whether the bug
  came from a P0/P1-severity report — if so, register the sentinel binding before
  reporting the fix done (do not silently skip the register in favor of "the test
  exists in the suite already").
- **Quarterly audit** is a standing item for whoever owns test-suite health in this
  repo (tracked as a BACKLOG/DEC entry when scheduled, not a Linear ticket — this
  harness's decision ledger is `docs/decisions.yaml` / `BACKLOG.md`, not Linear).
