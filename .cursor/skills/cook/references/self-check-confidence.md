# Self-check confidence — pre-handoff score

Details for the "run before handoff" step. Backing: `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/self_check_confidence.py`
(port of FrankCode's `selfCheck.ts`, adapted from AJV plan-schema validation to reading
this repo's `plan.md` + `phases/*.md` + `plan-graph.yaml` directly).

## When to run it

- Before the final handoff of a cook run (Steps 4-6), as one more signal alongside the
  independent `@tester`/`@code-reviewer` gates — not a replacement for either.
- Before a phase that carries real risk (touches a shared contract, a hard-mode plan,
  a phase with no test coverage) — run it on the plan directory to see if the plan
  itself still reads as decided and complete before committing more work to it.

It is **advisory, not a gate**: a low score is a prompt to re-read the plan, not a
block. Human plan approval is still the actual authority — this script's job is
narrower: catch the specific gaps its 10 checks can see (undecided either/or paths,
speculative file references, empty risk mitigations, a missing rollback section, a
dirty phase-DAG sidecar). A high score does not mean the plan is good; it means these
10 mechanical checks did not find a problem.

## How to run it

```bash
python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/self_check_confidence.py <plan-dir>            # human summary, exit 0
python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/self_check_confidence.py <plan-dir> --json     # full JSON result
python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/self_check_confidence.py <plan-dir> --strict   # exit 1 if confidence < 0.7 (CI opt-in only)
```

## Reading the score

Output carries `gate_scores` (per-gate 0.0-1.0), a weighted `confidence` (0.0-1.0),
`failures[]` (code + gate + cited_field + message), `top_uncertainties` (up to 3
failure messages, gate-priority ordered: requirements before design before structure),
and `needs_revision` (`confidence < 0.7`).

- `needs_revision: true` → read `top_uncertainties` first (already capped + prioritized)
  and revise the plan/phase **before** moving on to Step 4 (test) — do not push a
  low-confidence plan further down the pipeline and hope the human catches it later.
- `needs_revision: false` does not waive the human-review checkpoints (plan approval,
  `--tdd`/`--parallel` pauses, ship gate) — it only means this mechanical pass found
  nothing.

## The 3 gates (adaptation from selfCheck.ts)

| Gate | Weight | Items | Reads |
|---|---|---|---|
| `requirements` | 0.45 | FRONTMATTER_VALID, PHASES_EXIST, SINGLE_ACTIVATION_PATH, NO_SPECULATIVE_PATHS, ACCEPTANCE_MEASURABLE | `plan.md` frontmatter + body |
| `design` | 0.35 | RISKS_HAVE_MITIGATION, PREMORTEM_OR_REDTEAM_RAN, ROLLBACK_PRESENT | `plan.md` + `phases/*.md` Risk tables, Validation Log, Rollback |
| `structure` | 0.20 | PLAN_GRAPH_PRESENT, PLAN_GRAPH_CLEAN | `plan-graph.yaml` (via `plan_graph.py`) |

FrankCode's 3rd gate is named `grid` and reads a coverage-grid attestation. This port's
3rd gate is named `structure` and reads the phase-DAG sidecar instead — it is
deliberately independent of the grid-port coverage engine (no dependency edge between
them); do not conflate the two when reading a "structure" failure.

Per-gate score = `max(0, 1 - failed_items / gate_items)`; composite `confidence` is the
weighted sum. Same formula and threshold as the source (`selfCheck.ts:93-99,307-313`).
