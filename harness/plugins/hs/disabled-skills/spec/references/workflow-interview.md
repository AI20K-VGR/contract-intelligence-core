# Workflow — Interview & Generate

End-to-end workflow the LLM follows for the **product / brd / prd / epic / story** flags (and the no-flag init flow). Phased, resumable, adaptive, bilingual.

## Detect State (no-flag entry)

1. Look for `<root>/docs/product/PRODUCT.md`.
2. If missing → propose **Init product** via AskUserQuestion. On confirm, run *Init flow* below.
3. If present → present the No-Flag Menu (see SKILL.md). Each menu choice maps to one of the flag flows below.

## Init Flow (no PRODUCT.md yet)

1. Ensure `docs/product/` exists (create if not).
2. Run the **Vision** interview (`references/interview-vision.md`) — V1 through V7.
3. After V1–V7, write:
   - `PRODUCT.md` via `generate_templates.py --type product` with the labels from the answers.
   - `vision.md` via `generate_templates.py --type vision` with the narrative.
4. Offer next step: "Create the BRD now, or stop here?"

## Detail-level preference (seed once, then consume every prose turn)

See [Detail-level preference & Engagement profile](workflow-interview-engagement-knobs.md).

## Engagement profile (interview rigor + action density)

See [Detail-level preference & Engagement profile](workflow-interview-engagement-knobs.md).

## Phased Interview Engine

The interview is **phased** (vision → brd → prd → epic → story) and **resumable** via `docs/product/.session.md` (committed). Session schema in `frontmatter-and-id-spec.md`.

### Resume Rules

- On every invocation that triggers an interview, first read `.session.md`.
- If present and `phase != done`: ask "**Resume from saved state** (continue at `pending[0]`) or **Discard and restart**?"
- If `updated > 30 days ago` OR `answers` reference IDs no longer in the spec → mark as **stale**, default to "Discard" but still offer resume.

### Session Writes

- After every `AskUserQuestion` batch, append the answer to `.session.md.answers` and remove it from `pending`.
- On phase completion, set `phase` to the next stage; if all phases done, set `phase: done` and write the final artifacts.

## Adaptive Skipping

- Skip questions whose `target` is already filled in the live spec (e.g., persona cap interview if `PRODUCT.md.personas` is set).
- Skip optional questions (P7/P8/P9, E5, S5) unless the PO explicitly asks for them.
- Combine related questions into a single `AskUserQuestion` batch (e.g., size + persona for a story).

## 5-Why & MoSCoW Hooks

- After every PO answer, the LLM scans for vagueness triggers (`interview-frameworks.md → trigger phrases`). If found → run 5-Why up to 3 rounds, then propose a quantified rewrite.
- During the PRD interview's `P4` step, the MoSCoW gate is **mandatory**. If >60% of requirements end up as `must`, iterate the "delay by a month" test until at most ~60% remain MUST.

## Scope Challenge (always-on, once per PRD, BEFORE decomposition)

See [Scope Challenge](workflow-interview-scope-challenge.md).

## Scout-First, Ask-Second

Before interrupting the PO with a question, **resolve it from the existing spec first** — the PO has often already answered it in a prior artifact, in `PRODUCT.md`, or in `.session.md`.

1. **Scout the live spec first.** For anything answerable from existing artifacts (a persona label, a core-value sentence, a parent ID, a prior MoSCoW call, a locked `scope_intent`), read the artifact and use the answer — **cite it by ID** so the PO sees where it came from ("PRODUCT.md lists the shopper + store-admin personas; reusing those").
2. **Ask the PO only when the spec is genuinely silent**, or when:
   - two **approved** artifacts conflict (surface both — never pick one silently; see the contradiction protocol in `validation-rules-spec.md`),
   - it is a **business judgement** the spec cannot answer (pricing, timing, scope boundary, a brand-new persona identity),
   - the answer would **reverse a PO-confirmed decision** (see the No Silent Reversal protocol in
     `workflow-auto.md → Step 4` — there is no separate `workflow-update.md`; the `--update` flag it
     would have belonged to is not shipped in this build).
3. Never ask the PO for something a quick read of the spec already answers. A wrong cited assumption is cheap for the PO to correct; an unnecessary question is friction.

This mirrors DRY (one authoritative home per fact) and the Script-vs-LLM split: structure comes from the artifacts; only genuine judgement goes to the PO.

## Validation Log (record every PO decision verbatim)

Every batch of PO answers that resolves an open question — a Scope Challenge lock, a MoSCoW call, a 5-Why quantified rewrite, an ambiguous-split decision — is recorded **verbatim** so the decision trail survives across sessions and the No Silent Reversal protocol (`workflow-auto.md → Step 4`) has something to protect.

Append to a `## Validation Log` section in the session notes body of `docs/product/.session.md` (the `.session.md` frontmatter schema itself lives in `frontmatter-and-id-spec.md`; this is a prose section in its body). Schema:

```markdown
## Validation Log

### Session {N} — {YYYY-MM-DD}
**Trigger:** {what prompted this batch — e.g. "PRD-AUTH Scope Challenge", "MoSCoW gate on PRD-BILLING"}

1. **[{Category — Scope | Assumptions | Tradeoffs | Risks | Architecture}]** {full question text, verbatim — not a summary}
   - Options: {every option presented, verbatim} | Other
   - **Answer:** {the PO's choice, verbatim}
   - **Custom input:** {verbatim "Other" free-text if the PO typed one; omit if none}
   - **Rationale:** {one line — why this decision matters / what it locks}

#### Confirmed Decisions
- {decision}: {choice} — {brief why}
```

Recording rules:

- **Full question text** — the exact question, never a paraphrase.
- **All options** — every option presented, including the automatic "Other".
- **Verbatim custom input** — record any "Other" free-text exactly as the PO typed it.
- **Session numbering** — increment from the last `### Session N` in the log.
- **Rationale** — state what the decision locks (e.g. "locks PRD-AUTH at MVP this round").

The Validation Log is the verbatim source the No Silent Reversal protocol reads back to the PO before any regeneration — see `workflow-auto.md → Step 4`.

## Bilingual Handling

- `.session.md.lang` carries the active language (`en` or `vi`).
- `AskUserQuestion` text + options use the active language; IDs and frontmatter keys stay English.
- VI ships best-effort. If the PO writes mixed EN/VI, accept both, normalize whitespace, but keep the answer in whatever language the PO used.
- There is **no PO-facing `--lang` skill flag** in this build. Language rides `.session.md.lang` (above); the underlying scripts (`generate_templates.py`, `visualize.py`) still take a `--lang en|vi` arg internally, but there is no top-level `--lang` workflow and no `workflow-lang.md`. Do not advertise a `--lang` switch to the PO.

### PO reflect / behavioral-memory harvest — not shipped in this build

There is no `--reflect` command in this build. The PO-style behavioral-memory harvester (retro-scan of prior sessions to propose memory writes) was **NOT PORTED**; do not advertise a `--reflect` flow. See the PO-voice note below for the related unshipped voice store.

### PO voice — not shipped in this build

An earlier design sketched a "behavioral memory" layer (`scripts/behavioral_memory.py`) that would
read back the PO's own vocabulary/register/recurring-asks before composing prose, and record a
wording correction after the PO gave one. That script does not exist in this install — there is no
`--dump po-style` / `--voice` CLI to call. Compose prose from the interview answers and the live
spec directly; there is no separate voice store to consult or write.

## Generation Flow — `--brd`, `--prd`, `--epic`, `--story`

For each flag:

1. Read the relevant interview bank for the phase.
2. Compose `AskUserQuestion` batches sized 3–5 questions; never overwhelm.
3. Once enough fields are filled, call:
   - `generate_templates.py --root <root> --type <type> --parent <parent_id> --slug <SLUG> --values <json> --keep-optional <list> --lang <lang> --write`
4. Inspect the script's response (`id`, `path`, `written`). Confirm to PO that the file was created.
5. Update `.session.md` (mark phase complete or proceed to the next artifact).

## Multi-PRD Targeting (`--prd <feature>`)

- If `--prd` is given an explicit slug → use it.
- Else: list existing PRDs (from `spec_graph.py`) and present an `AskUserQuestion` menu: "Refine which PRD, or create a new one (give a SLUG)?"

## Multi-Story / Multi-Epic Loops

After writing a story, ask:

- "Another story under {epic_id}?"
- "Move to the next epic?"
- "Stop here?"

Loop with a clear termination question — never go more than ~6 stories without offering an explicit stop.

## Closing the Loop

When the PO ends the session:

1. Save `.session.md` with `phase: done` and the last `updated` timestamp.
2. **End-of-interview validate nudge.** If the session changed N items since the spec was last
   validated, nudge before closing: *"you changed N items since your last `--validate` — run it now to re-gate them?"*
   It is a nudge, never a block — the PO may decline.
3. **Engagement-knob adjustment (OPTIONAL — only when live evidence exists).** If THIS session
   produced real conversational evidence about engagement fit — e.g. goals omitted a metric ×N times, or
   the PO repeatedly waved off deep probing as noise, or kept asking "what's next?" — fold ONE tighten-or-
   relax proposal into the SAME close-out `AskUserQuestion` batch above (do **not** raise a separate
   interrupt). Ask once whether to adjust a knob, **bidirectionally**: propose *raising* `interview_rigor`
   to `deep` (or `action_prompting` to `proactive`) when the PO wanted more push, OR *lowering* it to
   `light` / `minimal` when they found it noisy. **`scripts/preferences.py` is not shipped in this build**
   — there is no `--set` CLI to persist the choice, so an explicit PO confirm here can only be honored for
   the rest of the live session, not saved for next time. Say so plainly rather than promising a
   persisted setting. Skip the item entirely when no live evidence exists.
4. Offer a quick `--validate` and `--viz tree` to summarize what was built.

## Examples (snippets the LLM emits)

> "I see PRODUCT.md exists. Want to (1) refine BRD, (2) add a new PRD, (3) add stories under an existing epic, (4) validate, (5) update, (6) visualize, (7) approve, (8) summary?"

> "Sounds like 'easy onboarding' — what does easy look like specifically? What does the user see or do in the first 60 seconds?" *(5-Why round 1)*

> "Out of 12 candidate requirements you've named, you've marked 10 as MUST. If any one of those delays launch by a month — is it still MUST?" *(MoSCoW gate)*
