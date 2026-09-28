---
name: recall-mode
description: Effort-scaled Stage-2 finding production for hs:code-review — fan-out lenses, adversarial verify, recall sweep, scope read. The gate is unchanged.
---

# Recall-mode — effort-scaled finding production

Recall-mode scales **how many findings Stage 2 produces** by an effort level. It grafts a recall engine (effort-scaled fan-out → adversarial verify → sweep) on top of the existing gate engine. **The gate, rules-layer, risk ceremony, verdict-truth-table, and dismissals lookup are unchanged** — recall only changes finding production, never the verdict path or the `review-decision.json` contract.

Deterministic half lives in `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/review_recall.py` (effort resolution, breadth lookup, diff-source resolver, scope assessment). This file is the LLM-judgment half: the protocol the reviewer follows.

## Effort → breadth (the knob; numbers in `"${HARNESS_BIN_ROOT:-.}"/harness/data/code-review.yaml`)

| Effort | Finder lenses | Verify | Sweep | Orchestration | Objective |
|---|---|---|---|---|---|
| `low` (default) | 1 (current single pass) | self | no | inline | precision / today's behavior |
| `medium` | 3 independent lenses | consolidate (critique-consolidator) | no | inline Task | balanced |
| `high` | 5 lenses | consolidate + verify | 1 sweep | **ultracode Workflow** | recall |
| `xhigh` | 6 lenses | independent-revalidator (majors) | 1 sweep | **ultracode Workflow** | high recall |
| `max` | 8 lenses | independent-revalidator per finding (3-state) | 1 sweep | **ultracode Workflow** | max recall |

Lenses **reuse existing agents** — `hs:critique-consolidator`, `hs:independent-revalidator`, `hs:red-teamer`, and generic finders. No new lens agent is authored. Counts are config, tunable per repo. `low` is byte-for-byte today's single `hs:code-reviewer` pass.

## Resolution (deterministic — do not eyeball)

```
python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/review_recall.py --effort <flag?> --diff-source --scope <files...>
```

Effort precedence, highest first: explicit arg (`--effort <level>`, the shorthand `--<level>`, or a bare leading token — all map to `low|medium|high|xhigh|max`) > `HARNESS_REVIEW_EFFORT` env > `code-review.yaml` > default `low`. An unknown value falls back to `low` (never crash, never silently escalate).

## Phase 0 — deterministic diff + scope read

1. `resolve_diff_source(target, root)` → the git range (`@{u}...HEAD` → `<main>...HEAD` → `HEAD~1`) + a working-tree-dirty flag. This is the same diff every lens reviews.
2. `assess_scope(changed_files, root)` → `{scope, signals, suggested_effort}` — file count + `risk_rubric` signals (auth/migration/secret/api_contract). Print one line: `scope: small|moderate|large · N files · signals: … → suggested effort: X`.
3. **Cross-check** the suggestion against the resolved effort. On a MISMATCH:
   - default (no `--auto`): `AskUserQuestion` **[bump to suggested (rec) / keep /
     other]**. Never auto-bump — the agent stays caged, the user decides. Headless /
     no-TTY → record the mismatch to the report and **proceed at the user-resolved
     effort** (do NOT bump).
   - **`--auto`**: the agent self-adjudicates — bumps to the suggested effort and
     **logs** the decision (no question). `--auto` governs the **REVIEW / effort
     decision ONLY** — it does not touch the fix axis.

## In-place override (`--in-place` / `--inline`)

By default the main agent does NOT review code itself. The review is always orchestrated through subagents: `hs:code-reviewer` at `low`, inline Task fan-out at `medium`, and the ultracode Workflow tool at `high+`. The `--in-place` flag is an explicit opt-out of that orchestration: it allows the main agent to perform the review directly. The flag must be logged in the report (`stamp:
in-place:true`).

`--in-place` does NOT change the resolved effort or breadth; it only changes the orchestrator. It is not a recall-mode level and does not appear in code-review.yaml.

## Stage 2 by effort

- **`low`** — the single `hs:code-reviewer` agent, exactly as today. No fan-out.
- **`medium`** — inline Task fan-out: spawn `lenses` independent finders over the same diff, then `hs:critique-consolidator` dedups + ranks into one finding set.
- **`high`+** — orchestrate the fan-out→verify→sweep via the **ultracode Workflow tool**. Its canonical `review-changes` pattern is exactly this: dimensions → find → adversarially verify, **pipeline by default** (each lens verifies as soon as its review lands). The script makes the fan-out deterministic (control flow in the script, not model-driven), carries the token budget, and consolidates.

  Prefer the **shared base workflow** over a hand-written inline script — the `find→verify` shape is factored into `base-pipeline-verify`, one data-driven, depth-1 workflow under the plugin root reused by every review-shaped consumer. It registers under the plugin namespace as **`hs:base-pipeline-verify`** (the bare `base-pipeline-verify` does NOT resolve — plugin workflows carry the `hs:`
  prefix). Pass lenses/verify/sweep/schema as JSON `args`; the verify prompt is a `{{field}}` string template, not a function (no functions cross the VM boundary).

  **Before the ladder spawns you MUST route via `hs:workflow-orchestrate`** (the challenge layer — see SKILL step 4): the `route_depth` it returns decides whether to proceed here or escalate the `hs:workflow-orchestrator` agent first.

  Four-tier ladder for high+, highest first. **Stamp the tier that ran** in the report:

  | Tier | Condition | Call | Stamp |
  |---|---|---|---|
  | 1 | ultracode opt-in present (default) | `Workflow({name:"hs:base-pipeline-verify", args:{lenses,verifyTemplate,…}})` | `Workflow(name)` |
  | 2 | opt-in present but the named workflow is not registered in this install | `Workflow({scriptPath:"<plugin-root>/workflows/base-pipeline-verify.js", args})` | `Workflow(scriptPath)` |
  | 3 | opt-in present but this call needs a bespoke per-call script (custom effort/profile/file-set the base cannot model) | inline `Workflow({script})` — the hand-written path, kept, not deleted | `Workflow(inline)` |
  | 4 | ultracode opt-in ABSENT (entitlement off / no keyword / no standing) | inline Task fan-out — the medium path widened to `lenses` | `inline-Task fallback` |

  Tiers 1–2 are the shared-asset path; tier 3 is the escape hatch for a call the base cannot express; tier 4 is the **mandatory** non-Workflow fallback — the Workflows feature is plan-gated, so a consumer that cannot fall back breaks wherever the entitlement is off. Resolve the ultracode opt-in per `"${HARNESS_BIN_ROOT:-.}"/harness/rules/orchestration-protocol.md`.

`base-pipeline-verify` args shape (the consumer builds these as data):

```
{
  lenses: [{key, prompt}],          // 5/6/8 by effort (code-review.yaml)
  verifyTemplate: "Refute: {{title}} at {{file}}:{{line}} — is it real?",
  findingsSchema, verdictSchema,    // structured-output JSON Schemas
  maxRetry?, retryBaseMs?           // attempt-indexed backoff
}
// base runs: pipeline(lenses, find, verify-each) → {findings:[…{verdict}]}
// then: one sweep round (high+) → critique-consolidator → SAME verdict-truth-table
```

## Verify + sweep

- `verify` per the level: `self` (low) · `consolidate` (medium) · `consolidate_verify` (high) · `independent` revalidator on majors (xhigh) · `independent_per_finding` 3-state at `max`. A finding that survives verification is `confirmed` with mandatory `code_evidence`; anything refuted or uncertain is `dismissed` / `needs-human` per the verdict-truth-table.
- `sweep` (high+): after the first round, run **one** extra recall pass asking "what did every lens miss?" — the tail catcher. New findings re-enter verify.

## The gate is unchanged

Every effort path feeds the **same** verdict-truth-table (`references/verdict-truth-table.md`), the **same** dismissals lookup (`"${HARNESS_BIN_ROOT:-.}"/harness/scripts/dismissals_store.py`),
and writes the **same** `review-decision.json`. `gate_stage.py` reads that artifact exactly as before. Recall adds **no** hook, **no** guard, and **no** new `stage-policy.yaml` entry — the fan-out/verify/sweep/scope-read are LLM
judgment with no new compliance boundary (adding a guard for a non-boundary would violate fail-closed-only-for-real-boundaries).

## Fix axis (separate from `--auto`)

`--auto` never implies any fix. The fix axis is specified explicitly:
- no flag (default): review only, report findings.
- `--fix`: apply ONLY the fixes that need no user confirmation (clear correctness bugs + safe cleanups); skip + report anything that changes intended behavior, reaches outside the diff, or is a judgment call.
- `--fix-auto`: auto-fix and self-decide ALL findings → drives `hs:fix --auto` (which suppresses its mid-fix `AskUserQuestion`). `--fix` and `--fix-auto` are mutually exclusive; both are OFF by default.

## Caging boundaries (`--auto` / `--fix-auto`)

The auto axis removes human prompts; it does NOT remove the harness's caging. These boundaries hold even under `--fix-auto`:

1. **Auto-decisions are written, never silent.** Every auto-bump (effort) and every auto-applied fix is appended to the review report under `plans/reports/` (what was decided + why) AND logged per
   `"${HARNESS_BIN_ROOT:-.}"/harness/rules/auto-decision-ledger.md` — a separate closed vocabulary from the end-of-work observe signal in `"${HARNESS_BIN_ROOT:-.}"/harness/rules/observation-signal-emit.md`. "Logged" is a concrete sink, not narration —
   if the sink is not written, the decision was not made (red line: GHI + HIỆN, không auto-suppress).
2. **`--fix-auto` only auto-applies a CONFIRMED finding with mandatory `code_evidence`.** A finding that did not reach a confirmed verdict (weak-verify levels: medium = consolidate-only) stays **report-only** even under `--fix-auto` — a low-confidence or prose-derived finding is never auto-Edited into a shipped file. Behavior-changing fixes require verify ≥ `independent` (xhigh+) before
   auto-apply.
3. **`--fix-auto` does not buy a self-PASS on a HARD stage.** When the diff carries a high-risk signal (auth/migration/secret/api_contract — risk ceremony), the reviewer≠author requirement still applies: the agent may auto-fix, but the verdict that clears a HARD stage (pr/ship/deploy) needs a non-author reviewer. Under headless `--auto`, a high-risk diff lands at `PASS_WITH_RISK` (soft-accept,
   blocks the hard stage), never a self-issued `PASS`.
4. **Non-convergence → BLOCKED, never a written soft-pass.** If the `--fix-auto` re-review loop hits its max (3) without converging and there is no human to escalate to (headless), it ends with **no PASS artifact** → `gate_stage.py` blocks. It must not write a `PASS`/`PASS_WITH_RISK` to "keep moving".

## Multi-round (N committing rounds)

A single effort pass can be repeated N times under a named **profile** — each round commits its safe fixes and feeds the next, optionally under four tactical axes (`compounding`, `per_aspect`, `blind_main_sub`, `refute`). This is opt-in via `--profile <name>` / `--rounds <n>`; `default` is one low pass (non-breaking). The `rounds × lenses` ceiling comes from `review-policy.yaml.caps`
(model-honored — no runtime guard, same non-boundary reasoning as above). Full protocol, the profile table, the per-axis behavior, and the `rounds_run` stamp: `references/multi-round.md`.
