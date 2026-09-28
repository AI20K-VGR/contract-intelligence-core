# hs:plan — cook-handoff flag detail (`--parallel` dual recommendation)

Load when recommending the cook command after plan approval (`## Context isolation before cook`
in SKILL.md). This is post-approval PHRASING advice, not a gate — nothing in the plan-to-cook
contract weakens if this detail lives here instead of inline.

**`--parallel` is a dual recommendation whenever the plan is parallel-capable** (it emitted the
dependency matrix + file-ownership table). Do NOT silently pick one side — print BOTH the
parallel and the sequential cook command, then add a one-line risk read that recommends which to
run:

- If the parallel-safe phases have disjoint ownership and touch no core/shared surface →
  recommend the parallel line (saves wall-clock; the integration barrier still runs the full
  suite serially).
- If any parallel batch touches core, a shared config, a migration, or a hot module → recommend
  sequential for safety, but STILL print the parallel line so the user can override with eyes
  open (e.g. *"phases 2+3 both touch the core resolver — run sequential; parallel command shown
  in case you split ownership first"*).

Example pair: `/hs:cook <plan.md> --tdd --parallel` · `/hs:cook <plan.md> --tdd` → *recommend:
<one>*.

A plan with no dependency matrix is sequential-only — omit the parallel line entirely.
