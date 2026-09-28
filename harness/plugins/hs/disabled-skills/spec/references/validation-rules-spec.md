# Validation Rules Spec

Check catalog, script-vs-LLM ownership split, severity levels, and the findings JSON schema scripts emit. Drives `--validate` (`--approve` would also draw on this catalog, as designed, but `--approve` is not a flag hs:spec exposes in this build — see `workflow-validate.md`'s caveat).

## Script vs LLM — Non-Negotiable Split

| Layer | Owns |
|-------|------|
| **Script** | Anything answerable by parsing YAML, traversing a graph, counting fields, or matching against a closed enum. |
| **LLM** | Anything requiring reading prose, weighing meaning, or judging quality. |

If a check needs to *understand* the words, it's LLM. If it can be answered by walking edges or counting items, it's script. **No exceptions.** This rule is enforced by the script code review gate — any heuristic in a script that judges quality must be removed.

## Check Catalog

See [Check Catalog](validation-rules-spec-check-catalog.md).

## `--strict` Gate Behavior

Default behavior (no `--strict`):
- All findings reported.
- The skill proceeds with whatever action was requested.

With `--strict`:
- Any finding with `severity: error` blocks the action.
- The skill stops and presents the errors; the PO must resolve before proceeding.
- `severity: warn` never blocks.

The gate is enforced in the **LLM/orchestration layer** (workflow-validate.md), not in the scripts.
The analytical findings-emitters (`check_traceability`, `check_consistency`, `build_traceability_matrix`, `spec_graph`) always exit 0 with JSON on stdout; the LLM reads severities and decides.
(`visualize` and `generate_templates` are a renderer and a generator, not findings-emitters: `visualize` exits non-zero on a user CLI error — e.g. an empty-after-`--layers` filter — by design; `generate_templates` always exits 0, surfacing a bad input — including an unresolved template token — as a JSON `error`/`written:false` finding on stdout instead, per the analytical-script contract below.)
The sole exception in the gate path is `strict_gate.py`, a CI-side wrapper that re-runs the analytical scripts PLUS its own cross-layer shape-serves check (the `dangling_serves` error — a shape task pointing at a story absent from this spec's graph), applies the gate, and exits `2` on `error` findings — usable from shell pipelines without an LLM.

## Severity Definitions

- **error** — the spec is structurally broken (orphan, dangling link, missing AC, dup ID, dependency cycle, dangling dependency) or contradicts an approved decision. With `--strict`, blocks.
- **warn** — the spec is structurally OK but may have a quality issue (low AC count, vague language, status inconsistency, unaddressed parent, child due after parent, dependency-order conflict). Never blocks; advisory.
- **advisory** — emitted ONLY by the out-of-gate `time_advisory.py` (`overdue`). It consumes the wall clock, so it is never part of the reproducible `--validate` gate; the script always exits 0. Informational only.

## Core-Value Scoring (LLM)

For every PRD/epic/story, the LLM scores against `PRODUCT.md`'s `core_value` sentence:

| Score | Meaning |
|-------|---------|
| `aligned` | clearly serves the core value |
| `weak` | tangentially serves; could be cut without harm to core |
| `off` | does not serve the core value |

Score + 1-line rationale included in the finding. The PO confirms the `scope: core-value` tag (or chooses `scope: in` / `scope: out`); the script only validates that the tag is one of the allowed enum values.

## `time_realism` LLM Scaffold (anchored — never date-math by the LLM)

`time_realism` is an LLM-judgment warn ("this deadline is unrealistic for this scope"), but it is **pinned to structured, script-precomputed numbers** so the LLM cannot hallucinate (the classic over-flag). The split:

- **Script half** — `scripts/time_realism_anchors.py --root <root> [--today YYYY-MM-DD]` pre-computes, per **epic**, the anchor record:

  ```json
  {"artifact_id": "PRD-X-E1", "file": "epics/PRD-X-E1.md", "type": "epic",
   "size": "L", "horizon": "now",
   "target_date": "2026-06-15", "today_date": "2026-06-01",
   "days_remaining": 14, "child_story_count": 6, "incomplete": true,
   "eligible": true}
  ```

  `days_remaining = (target_date − today).days` and `child_story_count` (a graph traversal) are computed **here, by the script** — the LLM does NO date arithmetic.
  `today_date` comes from the pinnable `--today` (default real today; **evals/tests PIN it** so the anchor — and the gate — is reproducible).
  When `target_date` or `size` is absent the anchor is still emitted with that field null and `eligible: false`.

- **LLM half** — apply this FIXED rule to each anchor (no prose, no velocity speculation):

  | Anchor state | LLM output |
  |--------------|------------|
  | `eligible == false` (any required anchor null) | `{finding: null, reason: "missing_anchor"}` |
  | `size == "L"` AND `child_story_count >= 6` AND `days_remaining < 21` | a `time_realism` **warn** (see below) |
  | otherwise (eligible but rule not met) | `{finding: null, reason: "below_threshold"}` |

  The conservative default is **no-flag**: if uncertain, or any anchor is missing, do not flag.

- **The finding REQUIRES cited data.** A `time_realism` warn MUST carry `context.cited_data` = `{size, child_story_count, days_remaining, target_date, horizon}` (verbatim from the anchor) plus `context.threshold_crossed` (which conditions tripped).
  The LLM MUST attach `cited_data`; this is the hallucination-guard convention — a prose discipline on the `--validate` flow, NOT a code-enforced gate (nothing in this build inspects or rejects a finding that omits it).

This mirrors the Script-vs-LLM split (CLAUDE.md): the structural numbers are deterministic Python; only the "is this realistic" judgment is the LLM's, and even that is reduced to a fixed threshold over script-supplied numbers.

## `competitive_drift` LLM Scaffold (anchored — never parity-guessed by the LLM)

`competitive_drift` is an LLM-judgment warn ("this PRD is losing its competitive edge"), the COMPETITION sibling of `time_realism`. "Mất lợi thế" is the classic over-flag, so the LLM is **pinned to structured, script-resolved parity anchors** and forbidden from inventing a competitor or a parity verdict. The split:

- **Script half** — `scripts/competitive_drift_anchors.py --root <root>` resolves each PRD's ID-keyed `competitive_parity` map against the BRD's DRY competitor identity home (`graph['competitors']`) and pre-computes, per **PRD**, the anchor record:

  ```json
  {"artifact_id": "PRD-CHECKOUT", "type": "prd", "scope": "core-value",
   "competitive_parity": [{"competitor_id": "COMP-ACME", "competitor": "Acme Commerce", "parity": "behind"},
                          {"competitor_id": "COMP-SHOPIFY", "competitor": "Shopify", "parity": "behind"}],
   "competitors_with_data": 2, "all_behind_competitors": ["Acme Commerce", "Shopify"],
   "incomplete": true, "eligible": true}
  ```

  `competitors_with_data` (the count of parity entries whose value is NOT `none`), the resolved competitor NAMES, and `all_behind_competitors` are computed **here, by the script** — the LLM does NO counting and never re-parses `brd.md`.
  `none` parity means "tracked, no verdict yet" and is **not** a data point.
  A parity KEY that does not resolve to a BRD competitor is dropped from the resolved block (its `unknown_ref` error is the consistency check's job) so the LLM never sees a phantom competitor.
  `eligible = (scope == "core-value" AND competitors_with_data >= 2)` — the anchored gate.
  PRDs with no `competitive_parity` map are not emitted (a v1 PRD is not a drift unit). Output is sorted by `artifact_id` → deterministic. The script NEVER decides flag/no-flag.

- **LLM half** — apply this FIXED rule to each anchor (no prose, no market speculation):

  | Anchor state | LLM output |
  |--------------|------------|
  | `eligible == false` (scope ≠ core-value, OR `competitors_with_data < 2`) | `{finding: null, reason: "missing_anchor"}` |
  | `eligible == true` AND EVERY real (non-`none`) parity is `behind` (i.e. `len(all_behind_competitors) == competitors_with_data`) | a `competitive_drift` **warn** (see below) |
  | otherwise (eligible but at least one real parity is `ahead`/`parity`) | `{finding: null, reason: "below_threshold"}` |

  The conservative default is **no-flag**: if uncertain, scope is not core-value, there are fewer than 2 real verdicts, or any tracked competitor is NOT `behind`, do not flag.

- **The finding REQUIRES cited data.** A `competitive_drift` warn MUST carry `context.cited_data` = `{scope, competitors_with_data, all_behind_competitors, competitive_parity}` (verbatim from the anchor) plus `context.threshold_crossed` (which conditions tripped).
  The LLM MUST attach `cited_data`; this is the hallucination-guard convention — a prose discipline on the `--validate` flow, NOT a code-enforced gate (nothing in this build inspects or rejects a finding that omits it).

This mirrors `time_realism` exactly: the structural resolution + counting is deterministic Python; only the "is this drift" judgment is the LLM's, and even that is a fixed rule over script-supplied parity anchors.

## Impact-Pass LLM Scaffold (per-change propagation — distinct from the catalog checks)

**NOT SHIPPED in this build.** No script or workflow step currently drives this pass into a
report — see `workflow-validate-judgment-cache.md`. The script-half primitives named below
(`spec_graph.downstream` / `diff_graphs` / `changed_nodes`) do exist and remain available for a
future implementation, but nothing wires them into `docs/product/impact/<ts>.md` today, and the
`--update` flag this design would have hung off is not in SKILL.md's Flags table. The rest of this
section is a design reference only.

The **impact-pass** would answer "I changed X — what downstream is affected, and how?" It would run on `--update` (one explicit `changed_id`) AND on `--validate` (change-set derived from the snapshot delta — see `workflow-validate-judgment-cache.md`, itself not shipped).
It is **per-CHANGE propagation**, NOT a per-ARTIFACT quality check — keep it separate from `risk_blindspot`/`time_realism`/`competitive_drift` so neither bloats the other. The split:

- **Script half (deterministic)** — `spec_graph.downstream(graph, changed_id)` returns the transitive child closure (iterative, cycle-safe).
  On `--validate` the change-set itself is deterministic: the `delta` view's added ∪ changed nodes between the two most-recent `.snapshots/` (`spec_graph.diff_graphs` for added/removed + `spec_graph.changed_nodes` for the per-node field diff — the single home for the tracked-field set `spec_graph.CHANGED_FIELDS`, the same rule `render_ascii.delta` displays);
  no previous snapshot → empty change-set → no impact-pass.
  The script NEVER interprets.

- **LLM half (judgment)** — for each affected node, emit one annotation record:

  ```json
  {"node": "PRD-AUTH-E1-S1", "dim_touched": "ac",
   "one_liner": "AC still references the pre-change scope wording.",
   "action": "review AC"}
  ```

  - `dim_touched` ∈ a **closed enum** — `{scope, risk, time, competition, ac, traceability}` — so the annotation stays bounded (an open-vocabulary tag would drift). Pick the single most-affected dimension.
  - `one_liner` — ONE sentence on HOW the change reaches this node; grounded in the node's actual content, never speculative.
  - `action` — a concrete suggestion: `review` / `review AC` / `re-estimate` / `split` / `re-approve` / `no-op`.
  - **Conservative default:** a node reachable but plausibly unaffected → `action: no-op` with a one-liner saying so; do not invent downstream damage.

- **Approved + contradicted** → if an affected node is `status: approved` AND the change contradicts its content, run the **Contradiction Protocol** below (keep/change/hybrid). The impact-pass NEVER auto-flips an approved artifact — this is the deal-breaker the `impact-pass` eval's approved branch gates.

- **Output (design only)** — the annotation records would become the rows of `docs/product/impact/<ts>.md` (skeleton `assets/templates/impact-report.md`, itself not-shipped) and the `dims` (the union of `dim_touched`) + `affected_set` of a change-log entry — but no script writes either file today.

This mirrors the Script-vs-LLM split exactly: `downstream()` + the snapshot delta are deterministic Python; only the dimension/interpretation/action is the LLM's.

## Contradiction Protocol (CRITICAL — never auto-flip)

When the LLM detects a contradiction with an `approved` artifact:

1. Emit a finding with `severity: error` and `check: contradiction`.
2. The orchestration layer presents three options to the PO via AskUserQuestion:
   - **Keep** the approved version, reject the new claim.
   - **Change** to the new claim — requires re-approval of the affected artifact(s).
   - **Hybrid** — record both, define a follow-up to reconcile.
3. The skill **never** auto-edits the approved artifact based on the contradiction. The PO decides.

This mirrors the global "No silent reversals" rule in CLAUDE.md.

## Findings JSON Schema (script output)

→ `frontmatter-and-id-spec.md` § Findings JSON Schema (single authoritative home for the script-output JSON shape).

## Human Report Format (LLM layer)

After scripts run and LLM judgment layers on:

```
# Validation Report — <date>

## Summary
- 23 artifacts checked
- 0 errors · 3 warnings
- Strict gate: OFF (no errors block; warns advisory)

## Errors (0)
(none)

## Warnings (3)

### PRD-AUTH-E1-S2 — low_ac_count (warn)
File: stories/PRD-AUTH-E1-S2.md
Detail: Story has 1 acceptance criterion. Suggest ≥2.

### PRD-BILLING — core_value_drift (warn — LLM)
File: prds/billing.md
Detail: Core-value alignment is "weak": billing flow is tangential to "help boutique
brands sell directly". Consider whether this PRD belongs in the next horizon.

### BRD-G3 — orphan_brd_goal (warn)
File: brd.md
Detail: No PRDs address this goal. Either drop, defer, or write a PRD.

## Suggested Next Steps
1. Add 1 more AC to PRD-AUTH-E1-S2.
2. PRD-BILLING: discuss core-value alignment with stakeholders.
3. BRD-G3: decide between drop / defer / new PRD.
```

## What This Spec Does NOT Define

- The exact prose template for the human report — that's the LLM's job.
- The order of script invocations — that's `workflow-validate.md`.
- The interactive flow on `contradiction` — that's `workflow-validate.md`.
- The change-set derivation + report-write steps of the impact-pass — those would have lived in
  `workflow-validate.md` (`--validate`) and a `workflow-update.md` (`--update`); neither the
  impact-pass nor `--update` is shipped in this build (see the caveat at the top of this section),
  so this spec's annotation rule below is design reference only, not an active check.
- Eval rubric for the LLM judgment checks — a formal `eval/evals.json` harness is NOT SHIPPED in this build; the cited-data invariant above is enforced inline per finding.
