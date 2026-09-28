# Review and test gate config (4 tiers — surface during Full or when asked)

Walk MAIN tier first (day-one impact), offer EDGE as an opt-in branch, SHOW-warn the sensitive tier on request, and only list the internal tier.

## TIER 1 — MAIN (affects ship gate; surface on day one)

| File | How to change | Notes |
|---|---|---|
| `review-policy.yaml` | `review_policy_config.py --set profiles.<name>.<knob>=<v>` or `--set stage_floor.<stage>.<knob>=<v>` | Three built-in profiles: `default` (1 round, low), `thorough` (3 rounds, high, diff), `ship-grade` (3 rounds, max, full project). Stage floor is off by default — opt in per stage. |
| `code-review.yaml` | Hand-edit (no CLI — like stage-policy); git-visible diff | Show the current `default:` value and `levels:` block before guiding the edit. Precedence: explicit arg > `HARNESS_REVIEW_EFFORT` env > this file > `low`. |
| `test-policy.yaml` (DoD) | Guided git-visible hand-edit — `test_policy.py` has NO `--set` writer **by design** (DoD changes are high-stakes; they must be deliberate, reviewable diffs). | **CONFIGURE, don't just show.** Surface `change_classes:` + `preset:` + `components:`, give the posture-aware reading in "DoD walk" below, propose a recipe diff for the user to approve/apply. Never `--set`. |

Read current values first: `python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/review_policy_config.py` (profiles + stage_floor). For `code-review.yaml` / `test-policy.yaml`: read the file and surface the relevant block verbatim.

**DoD walk (posture-aware).** Read `test-policy.yaml`, then judge it against the review-policy profile the user just chose (`default`/`thorough`/`ship-grade`) and *propose* (never impose) a fitting baseline:

- **solo** → a team-grade DoD (every `feature` requires `integration` + `coverage:{line:80}`, `**` enforcement `hard`, `release` requires regression+smoke) is usually TOO STRICT for one fast-moving person. Offer a solo-lean recipe: `feature: {required:[unit]}`, coverage `no_regression` (or drop), KEEP `security` hard on `**/auth/**` + `**/payment/**`, keep `release` heavier. Trade-off to
  state: less mandated proof per change.
- **team** → a lean DoD (unit-only, no coverage floor) is TOO LOOSE when paired with self-review — nothing independent gates a merge. Offer to restore `integration` + a coverage floor on `feature`, and confirm reviewers are real people, not the author.

**WHERE to write the override — two surfaces, pick by intent:**

1. **tier-1** (`"${HARNESS_BIN_ROOT:-.}"/harness/data/test-policy.yaml`, the default) = a permanent baseline change for this install — it is the install's own gate. Edit it for a permanent solo-lean (or stricter) DoD.
2. **tier-2** (`<root>/test-policy.yaml`, at the repo root OUTSIDE `harness/**`) = the per-repo override layer. It MERGES over tier-1 (strictness-aware union). Strengthening applies directly; a WEAKENING class (fewer required types / lower coverage / softer enforcement) is REJECTED unless it carries `grace: { reason: <why>, expires: <ISO date> }` — past `expires` the gate re-arms the full
   tier-1 hard gate. Use this for a justified, time-boxed loosening.

Surface the concrete diff and let the user approve before writing. Then run the per-step coherence check (does this DoD match the review-policy profile chosen above?). See `references/coherence-lint.md`.

## TIER 2 — EDGE (optional: "do you also want to configure…?")

| File | Tool | Notes |
|---|---|---|
| `risk-rubric.yaml` | Hand-edit | Risk-assessment lens thresholds. Show current values before guiding edits. |
| `critique.yaml` | `critique_config.py --set mode=<advisory\|gate>` | `advisory` writes a verdict but does NOT enforce; `gate` enforces when a stage lists `critique-consensus` in `requires:`. |
| `simplify-policy.yaml` | Hand-edit | Simplification pass thresholds. Show current values before guiding edits. |

## TIER 3 — SHOW + warn (RBAC/fence — casual exposure is a footgun)

Read and surface the current value verbatim, then warn. Do NOT invite `--set` or casual hand-edits.

| File | What it controls |
|---|---|
| `write-deny-policy.yaml` (soft tier) + `write_deny_policy.py` (hard floor, code) | The write-RBAC deny-list — the agent cage. Wrong edits silently widen what an agent can write. The hard floor is a code constant; only `soft_rules` is config. |
| `ownership.yaml` | File-ownership fences for agent RBAC. |
| `protected-branches.yaml` | Branches where force-push / direct commit are fenced. |
| `standards.yaml` | Compliance standards tree read by the review gate. For authoring new standards, use the rule-author skill (not setup). |

> "This file cages the agent / is a fence — edit carefully, prefer a git-visible diff,
> and test after any change. For standards authoring, use the rule-author skill instead."

**Workflow `--fix` code-lane.** A Workflow-orchestrated `--fix` runs as a `workflow-subagent` that edits project source out of the box — no lane setup, refused only the hard floor.

## TIER 4 — INTERNAL (harness-managed — do not hand-edit)

Managed by `harness/scripts/build_manifest.py`; hand-editing breaks manifest drift detection. List only — do not show content or invite edits:

`skill-deps.yaml`, `skill-chains.yaml`, `decomposition-map.yaml`, `components.yaml` (component toggles: `component_config.py` is the sanctioned seam), `observation-signals.yaml`, `route-probes.yaml`, `component-policy.yaml`.

> These are managed by harness/scripts/build_manifest.py and related tooling. Do not hand-edit.
