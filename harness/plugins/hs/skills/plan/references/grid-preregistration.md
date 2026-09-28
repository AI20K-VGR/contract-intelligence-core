# hs:plan --grid — checklist independence + ruleset pre-registration

Split out of `grid-mode.md` (which owns the build/verdict/emit flow) because this is one
self-contained contract: where the feature checklist comes from, and how combination-ban rules
get frozen into the plan BEFORE any cell fills. Load it when producing or consuming a
`grid-preregistration.json`, or when an N/A cell needs to earn coverage credit.

## Two-pass macro (discover → plan) + freeze-before-fill

Pass-1 (`hs:discover`): an INDEPENDENT re-derivation, not a self-authored checklist — spawns
`@independent-revalidator` (subagent_type `hs:independent-revalidator`) in a SEALED ROOM: it
re-derives feature/risk from the ORIGINAL PROBLEM, never reads `§features` (discover has none
yet — `build_planner_axes RAISES on empty features`, axes.py). Main FREEZES the result via
`feature_checklist.py emit` (`content_sha256`) BEFORE `§features` exists. Optional; a
checklist-less plan still builds — independence is what makes the pass-2 diff real.

Pass-2 (`hs:plan` Step 6, `emit --checklist`): build the macro-grid, hash-verify the frozen
pass-1 checklist, DIFF-ATTEST against it, THEN freeze: pre-register to FREEZE the
combination-ban rules and stamp the grid BEFORE the first cell fills — before approval too (see
Consume below). Timeline: build → freeze → fill; minting a rule during fill is fraud. An
amendment re-generates the WHOLE grid + a receipt. **HONEST LIMIT:** pass-1 is still
model-authored — the strength is structural independence, not completeness; a dropped feature
rides the below-floor HITL above, not a new block.

**Produce** the sidecar with `grid_engine.py preregister --rules-in <rules-in.yaml>
--plan <plan.md>` — loads the author-declared rules-in file (`constraint_rules:`, same shape as
`grid-axes.yaml`'s own, plus an optional `local_rules:` list), freezes both tiers, writes the
sidecar (default `<plan-dir>/artifacts/grid-preregistration.json`), and appends the rendered
ruleset into a `## Grid constraint rules (frozen)` BODY section of plan.md — NOT frontmatter or
`## Phases` (both stripped from `plan_hash`, so a rule placed there would fall OUTSIDE the
freeze) — so the user sees the actual rules at Approve. Idempotent re-run replaces the section.
Do this BEFORE the plan is approved.

**Consume** at fill/review/emit: `--rules artifacts/grid-preregistration.json --plan <plan.md>
--root <repo-root>`. `--plan` must resolve to `plan.md` ITSELF (a dir derives `<dir>/plan.md`;
else dies naming why) — no `in_progress` requirement, but must be the file `plan_hash` covers (a
same-dir decoy no longer passes). Hash still verified against the resolved plan (`--plan`, else
active plan); a mismatch/forged `rule:<id>` dies closed. `--rules` on a not-yet-approved plan
prints one `UNAPPROVED` stderr line (not an error) — the fraud barrier is the human reviewing the
rule table at Approve. `emit`, given `--rules`, stamps the `ruleset` mark (`{ruleset_hash,
rule_count}`); `_ruleset_mark_ok` checks more than shape — the hash must match the
`grid_ruleset_hash:` line. No `--rules` → `frozen_rules` stays None.

**The attestation must literally start `rule:<id>` — prose earns ZERO credit.** An N/A cell
counts toward coverage only if `attestation` matches `^rule:([A-Za-z0-9_-]+)` with that id in the
frozen ruleset: a prefix match, not a reading. `N/A by the docs-x-cli rule` is true and worth
nothing — same cells scored 0.21 (below floor → `reject`) vs 1.0 on a 12-char prefix. Write
`rule:docs-x-cli — <why>`; no space after the colon.

## Auto-freeze (`plan.grid.autoPreregister`, default ON)

**Automatic once `plan.grid.autoPreregister` is true** (the shipped default — resolve it live
with `skill_config.py --resolved`, never hand-read the file). Step 6 authors the rules-in file
itself from the plan's OWN architecture prose: the module split, the ownership statements, the
explicit out-of-scope list — and **never from which cells came out thin**. The direction is the
whole point. Reading the fill outcome would convert "nobody filled this" into "this cannot
apply", which is laundering rather than coverage. And since a below-floor reading only exists
AFTER the fill, "wait for the floor to fail, then mint rules" is structurally forbidden: the
ordering stays build → freeze → fill, and minting during fill is fraud.

Say plainly what the freeze does and does not buy, so nobody over-trusts the number: the engine
verifies a rule is frozen, that its combo applies to the cell, and that nothing changed after
approval. It CANNOT verify the rule is TRUE — "rm never touches models.py" is a claim, not a
checkable fact, and the human at the Approve gate is its only real reviewer. That is exactly
why the ruleset renders into the plan BODY under `plan_hash`: tamper-EVIDENT, not tamper-proof.
When an auto-authored ruleset is in play, echo the rendered table to chat at Approve rather than
letting it pass as boilerplate. Set `autoPreregister: false` to return to hand-authored rules;
the manual `preregister` CLI path is unchanged either way.
