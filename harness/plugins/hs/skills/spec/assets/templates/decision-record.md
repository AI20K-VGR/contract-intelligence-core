<!--
TEMPLATE: decision-record.md — the reference shape of one record block in
docs/product/decisions.md, the per-workspace DEC ledger. The live allocator,
scripts/dec_ledger.py, renders this block inline (its own `_render_block`
function) rather than reading this file — treat this as documentation of the
shape, not a file dec_ledger.py substitutes into. Never point dec_ledger.py at
scripts/decision_register.py — that is a different, schema-incompatible tool
for the harness's own architecture register (see references/dec-ledger.md).

The ledger is APPEND-ONLY: a new ruling is always added; prior bytes are
never rewritten. dec_ledger.py has no supersede mechanism — there is no
`status: superseded` flip and no `supersedes:` field. To revisit an earlier
ruling, append a fresh `DEC-<n>` whose body prose names the prior id it
replaces. IDs are parent-free, globally monotonic (`DEC-<n>`, allocated
max+1 — never reused).

DRY GUARD — what a decision record holds, and what it must NEVER hold:
  HOLDS  : the PO ruling + its one-paragraph RATIONALE + ID links
           (`affects: PRD-AUTH-E1`). Links, not copies.
  NEVER  : structural facts that already have an authoritative home — a persona
           narrative (lives in vision.md), a business goal (brd.md), a feature
           scope or AC (the PRD/story). A decision POINTS at those by ID; it does
           not duplicate them. Copying a fact here creates a second source of
           truth that drifts. Reference `affects:` by ID and stop.

Bilingual: the prose (title + rationale) localizes per the session `lang`; the
frontmatter keys and the `DEC-<n>` id stay English (CLAUDE.md → Bilingual
Conventions).
-->

---
id: {{id}}
status: {{status}}
date: {{date}}
actor: {{actor}}
ts: {{ts}}
affects: {{affects}}
---

## {{id}} — {{title}}

{{rationale}}
