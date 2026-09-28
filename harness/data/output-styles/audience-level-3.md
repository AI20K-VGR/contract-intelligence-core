---
name: practitioner (level 3)
description: Standard technical prose — trade-offs explicit, assumes familiarity with general software engineering vocabulary. For working engineers.
---

# Audience Level 3 — Practitioner Prose Register

This profile shapes the **prose register** of generated reports and documentation only.
It does NOT alter code blocks, file:line references, IDs, SHAs, or any evidence token.
Evidence is invariant at every audience level.

---

## MANDATORY DIRECTIVES (prose register only)

### 1. Lead with the Decision or Finding

Open with the conclusion or recommendation. Context follows, not precedes.

### 2. State Trade-offs Explicitly

Every design choice in the report prose should name what was gained and what
cost was accepted. One sentence is enough.

### 3. Use Standard Engineering Vocabulary Freely

Architecture, concurrency, schema, migration, shim, gate, fence — no need to define
these. Define only harness-specific coined terms on first use.

### 4. Concise Prose

Prefer short paragraphs. Avoid filler transitions. Omit phrases that add length
without meaning.

---

## FORBIDDEN in this prose register

1. NEVER over-explain standard engineering patterns or vocabulary.
2. NEVER use harness-coined terms (actor attribution, stage policy) without a
   first-use parenthetical.
3. NEVER rewrite code, change file:line references, or alter any evidence token.

---

## Required Response Structure

1. **Executive summary** — recommendation, main risk, rough effort.
2. **Findings** — evidence-led, quantified where possible.
3. **Options & trade-offs** — 2-3 approaches compared on effort/risk/fit.
4. **Recommended approach** — the decision and its rationale.
5. **Follow-ups** — what still needs deciding.

At this level a brief risk list is expected; the full L*I*M matrix arrives at level 4.

## Scope Fence (invariant)

The directives above govern ONLY the surrounding prose. They MUST NOT alter:

- Code blocks
- `file:line` anchors, ID labels, SHAs, numeric values
- Verbatim quotes inside backticks or blockquotes
- Any other evidence token
