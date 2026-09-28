# Coverage-grid judgment — the rules that hold at BOTH grid layers

Two grids exist and they are not the same artifact:

| | **macro** (plan layer) | **micro** (cook layer) |
|---|---|---|
| how many | one per PLAN | one per PHASE |
| written by | `emit` with no `--phase` → `coverage-grid.<fmt>` | `emit --phase <id>` → `coverage-grid-<phase>.<fmt>` |
| axis-selection receipt | **required** | **not required** |
| independence protocol | two-pass (pre-register, then diff) | one-pass |

Everything below applies to both unless a row says otherwise. Layer-specific judgment lives
in each skill's own grid reference.

## The two gates read two different paths — never conflate them

Macro presence is checked at plan approval. The per-phase count is checked at plan **close**,
never at approval (no per-phase grid can exist that early). A tool that wires only the macro
check will look green all the way to close and then discover the per-phase promise was never
kept. When you read a "grid gate passed" line, know **which** gate passed.

The micro grid's exemption from the axis-selection receipt is decided by **structure and file
path**, never by a field the record writes about itself. A record that declares "I am an
executor grid" proves nothing; the gate does not trust a self-declared `agent` field, and
neither should you.

## Presence is not quality — the two enforcement tiers are different things

- **Hard tier**: the artifact exists and a fill actually ran. Mechanical, binary.
- **Advisory tier**: the verdict on whether the filled content is any good, plus the
  below-floor human-in-the-loop stop.

Passing the hard tier says nothing about content. A partially-thin FILLED grid clears it.
Never write "gated" bare and never let a green presence check stand in for having read the
cells.

The same honesty applies to the axis-selection receipt: the gate forces a receipt to **exist**,
not to contain real reasoning. A hand-written receipt that merely restates the feature list
clears it and may be pure confabulation. Read it.

And the coverage ratio is a **planning aid, never evidence of coverage** — it is computed over
mechanisms that verify presence, not truth. Do not quote it as if it measured risk.

## A `reject` / `needs-detail` / below-floor verdict never passes silently

When the verdict is below floor or `reject`:

1. surface the thin cells **and** the confabulation signals — quote them, do not summarize;
2. `AskUserQuestion`;
3. proceed **only** on an explicit confirm, otherwise resolve first.

Resolving means one of exactly two things — real coverage added, or an explicit
`[JUSTIFIED-THIN]` attestation. "We looked at it and it seemed fine" is neither.

## Freeze before fill — minting a rule during fill is fraud

Order is **build → freeze → fill**, and it is load-bearing. A combination-ban rule authored
after seeing the fill result is not a rule, it is an excuse written to match the answer.

When rules are auto-authored, they must come from the plan's **own architecture** — never
from which cells came out thin. Reading the fill outcome to decide what "cannot apply"
launders "nobody filled this" into "this is inapplicable". That is the single most attractive
way to fake a high coverage number.

An N/A attestation must **literally begin** `rule:<id>`. Prose earns **zero** credit even when
the prose is true: `N/A by the docs-x-cli rule` scores **0.21**, `rule:docs-x-cli — <why>`
scores **1.0**. This is a prefix match, not a judgement of eloquence.

## Axis selection is a two-ended contract (macro only)

Before the build: propose the axes for THIS project and check them. After the build: if the
grid lands on a wall of N/A cells, that is a forced **re-selection**, not a result to accept.

Do **not** build straight from the canned default axes. A project without those layers gets a
grid whose axis values do not exist in it, which lands mostly-N/A and teaches you nothing.

## Independence: two-pass at macro, one-pass at micro — and why

At macro, the pre-registration pass is run by an independent re-derivation in a **sealed room**
that never reads the plan's own feature list. Concretely: `hs:discover` spawns
`@independent-revalidator` (subagent_type `hs:independent-revalidator`), and main freezes the
result with `feature_checklist.py emit` (a `content_sha256`) BEFORE `§features` exists. The
independence is the entire reason the second-pass diff means anything; let the re-deriver see
the feature list and you have a checklist agreeing with itself.

At micro there is **no** diff-attest, and that is correct, not a gap: one phase is one moment,
so there is no earlier moment to diff against. Do not import the macro protocol into a phase
grid to look rigorous.

## Escalate vs amendment — say which one you are doing

- **Escalate** changes only the DIFFICULTY. Seed the old fill, keep the work already done.
- **Amendment** changes the QUESTION — an axis, a value, or a rule. It forces a fresh
  regeneration and a re-approval.

Calling an amendment an escalation keeps stale answers to a question nobody is asking any
more. Name it correctly even when the honest name costs you a redo.

## A guardrail breach is a four-door decision the machine never makes for you

split · run-and-pay · raise-the-guardrail · lower-the-strength.

The machine chooses **none** of these. Present the four with their costs and let the user
decide; the user is supreme here.
