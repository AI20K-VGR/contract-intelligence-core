# Methodology review (self-governance gate)

The harness's other gates — code-review, verification, plan-approval — force
an ARTIFACT to anchor its claims in evidence. None of them run when someone
edits the methodology ITSELF: `harness/rules/**`, a skill markdown under
`harness/plugins/hs/skills/**`, or a schema under `harness/schemas/**`.
Unguarded, methodology can drift into a plausible-sounding rule or skill that
doesn't earn its keep — the confabulation shape the rest of the system
rejects everywhere else. This closes that gap, deliberately narrow: no
blanket gate on every doc edit.

The advisory hook `harness/hooks/methodology_review_gate.py` (`nudge`,
default OFF, fail-open) does only light structural detection — path match +
Write-vs-Edit — and points here. The 6-signal checklist below is PROSE a
human or LLM applies by reading the diff; nothing in the hook runs it, and
the hook does not import the grid confab-detector.

## When to apply

Run this review on a diff touching `harness/rules/**`, a skill file under
`harness/plugins/hs/skills/**/*.md`, or a schema under `harness/schemas/*.json`.
Classify the edit first — the classification decides the path (full review vs
rubber-stamp).

### HIGH-impact edit (full review required)

A change is HIGH-impact if **any** of the following hold:

1. Adds a **new skill file** under `harness/plugins/hs/skills/**/*.md`.
2. Edits an **axis / schema** file under `harness/schemas/*.json` (or a data
   file backing a hard invariant, e.g. `harness/data/test-policy.yaml`'s
   `test_types`).
3. Edits a **section contract** in a rule doc that another skill or gate
   depends on — a `harness-contract.md` posture row, a `tdd-discipline.md`
   invariant, or similar load-bearing prose other files cite by name.
4. **Retires a skill or rule** — any removal of a
   `harness/plugins/hs/skills/**/*.md` or `harness/rules/*.md` file.
5. **Bumps a skill's behavior in a breaking way** (a trigger, an owned glob,
   or a gate it feeds changes meaning) — a wording polish is not breaking.

### Trivial edit (rubber-stamp path)

Everything else: typo, link fix, wording polish, formatting, reordering a
bullet list, refreshing an example, fixing a stale count in a doc. If unsure
between HIGH-impact and trivial, default to HIGH-impact.

## Inputs

- The diff (`git diff` against the merge base, or the Write/Edit tool call).
- The existing skill/rule corpus for the affected area (overlap check on new
  additions).
- The rule docs the change touches, plus anything that cites them by name
  (`grep` for the rule's filename across `harness/`).
- For a schema/axis edit: what reads that schema (`grep` the field name) to
  gauge blast radius.

## Workflow

### Path A — HIGH-impact edit

Apply the six confab signals — ported from the FrankCode grid contract, here
run as a CHECKLIST over the skill/rule TEXT (never over the grid engine's
harness, which this gate deliberately stays independent of):

1. **UNANCHORED_HIGH** — does the new/edited text claim authority (a blocking
   gate, a new invariant other skills must follow) without citing a concrete
   anchor (a file path, a script, a fixture, a test name)?
2. **PHANTOM_EVIDENCE** — does it cite a file path, script, or fixture that
   does not exist on disk at HEAD?
3. **DUPLICATE_CONTENT** — does a new skill/rule overlap an existing one by
   more than roughly a third of its responsibility (same trigger conditions
   + same output)? Heuristic only, not a mechanical count.
4. **COORDINATE_LEAK** — does the change reach into another skill's or
   agent's owned surface (a plan-only rule instructing test edits, a review
   rule editing production code)? A cross-skill handoff is fine; claiming
   another skill's authority is not.
5. **HEDGING_DENSITY** — does every contract in the text hedge ("may",
   "usually", "depending on context") so nothing in it is falsifiable?
6. **STUB_AVOIDANCE** — does a section read `TBD` / `TODO` / an empty table
   with no named follow-up?

Log each triggered signal as a finding: `(signal, quote, suggested fix)`.
Verdict:

- **pass** — zero findings, or only advisory ones.
- **needs-revision** — at least one blocking finding; the change should not
  merge as-is.
- **reject** — the edit breaks a load-bearing contract with no migration
  path (e.g. removing a rule other skills route through without updating
  those routes); needs an explicit override decision.

### Path B — Trivial edit

Rubber-stamp with a one-line note in the commit message or PR description:

```
methodology-review: rubber-stamped ({N} files, no HIGH-impact trigger
matched). Category: {typo|wording|formatting|...}.
```

Do not run the 6-signal checklist on a trivial edit — that is the blanket-gate
anti-pattern below.

## Acceptance scenarios

- **Fake-skill edit** (plausible name + empty sections + no citations) →
  UNANCHORED_HIGH + STUB_AVOIDANCE fire; verdict `needs-revision`.
- **Typo-in-rule edit** → rubber-stamped; no checklist run; merges without
  ceremony.
- **New skill overlapping an existing one** (same triggers, same output) →
  DUPLICATE_CONTENT finding; verdict `needs-revision`; consolidate or justify
  the split.
- **New rule doc citing itself as its own authority** → UNANCHORED_HIGH;
  every new rule/skill must cite at least one anchor outside itself.

## Decision table

| Situation | Action | Severity |
|---|---|---|
| New skill/rule with no external citations | `needs-revision`; require ≥2 anchor references | blocking |
| Skill/rule retired without a migration note (what replaces it, who routes through it) | `needs-revision`; require the note | blocking |
| Change cites a fixture/schema/script that doesn't exist at HEAD | `needs-revision`; PHANTOM_EVIDENCE | blocking |
| Two new skills/rules in one change with heavy overlap | `needs-revision`; DUPLICATE_CONTENT | blocking |
| Trivial doc fix mis-flagged as HIGH-impact by the hook | apply the rubber-stamp path; note why it's trivial | advisory |
| Uncertain between trivial and HIGH-impact | default to HIGH-impact | advisory |
| Schema/axis edit with no blast-radius check | `needs-revision`; grep dependents, attach findings | blocking |
| Skill/rule removed; a doc's count or index not updated | `needs-revision`; trivial follow-up required before merge | advisory |

## Outputs

This gate does not write its own artifact file — record the verdict as a
`review-decision.json`/`.yaml` entry when it runs inside `hs:cook`/`hs:ship`'s
existing review step, or as a plain PR/commit-message note otherwise. A
recurring `needs-revision` pattern (roughly 3+ in a short window) is worth a
`BACKLOG.md` entry naming the drift, not a new gate.

## Anti-patterns

- **Blanket gate** — running the full 6-signal checklist on every doc typo.
  The rubber-stamp path exists; use it.
- **Self-approval** — the same agent both authoring and reviewing its own
  methodology change with no independent pass. Route review through a
  separate agent/session regardless of who authored the diff.
- **Cite-the-skill-being-added** — a new skill or rule citing itself as its
  own authority anchor. Every new addition needs at least one anchor outside
  itself (a sibling rule, a schema file, an existing test, a fixture).
- **Rubber-stamping a HIGH-impact edit** — the one-line attestation is for
  genuinely trivial edits only. A schema/axis edit or a new skill always
  forces the full review.

## References

- Hook: `harness/hooks/methodology_review_gate.py` (structural detection,
  points here).
- Posture: `harness/rules/harness-contract.md` (the three posture hooks —
  this gate is `nudge`, fail-open, never blocking, by deliberate choice: a
  hard gate on every methodology edit would be a denial-of-service on the
  harness's own maintenance).
- Deferred/repeat findings: `BACKLOG.md` (this repo's equivalent of an
  external issue tracker for a drift memo).
