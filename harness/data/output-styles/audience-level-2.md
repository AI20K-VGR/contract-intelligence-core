---
name: informed (level 2)
description: Context-aware prose — uses technical vocabulary but provides brief clarifications for specialist terms. For readers comfortable with technology but new to this domain.
---

# Audience Level 2 — Informed Prose Register

This profile shapes the **prose register** of generated reports and documentation only.
It does NOT alter code blocks, file:line references, IDs, SHAs, or any evidence token.
Evidence is invariant at every audience level.

---

## MANDATORY DIRECTIVES (prose register only)

### 1. Brief Orientation

Open sections that introduce new concepts with one to two sentences of context:
what the thing is and why it exists in this system. Do not lead with jargon.

### 2. Clarify Domain-Specific Terms

Standard technical vocabulary (API, config, schema, hook) needs no definition.
Harness-specific or project-specific terms (guard policy, stage policy, RBAC lane,
actor attribution) MUST be briefly clarified on first use.

### 3. Trade-off Language

When explaining a design choice, state the trade-off explicitly: what was gained
and what was accepted as a cost. Keep it to one sentence.

### 4. Moderate Length

Paragraphs up to 6 sentences. Avoid lengthy preambles. Get to the point after one
orientation sentence.

---

## FORBIDDEN in this prose register

1. NEVER explain universally known programming concepts (variables, loops, functions).
2. NEVER use harness-internal labels without a one-phrase clarification on first use.
3. NEVER rewrite code, change file:line references, or alter any evidence token.

---

## Required Response Structure

1. **Summary** — recommendation + key caveat.
2. **Findings** — the evidence, organized by theme.
3. **Options** — the main alternatives, one line of trade-off each.
4. **Recommendation** — the chosen path and why.
5. **Next steps** — ordered, owned where possible.

## Scope Fence (invariant)

The directives above govern ONLY the surrounding prose. They MUST NOT alter:

- Code blocks
- `file:line` anchors, ID labels, SHAs, numeric values
- Verbatim quotes inside backticks or blockquotes
- Any other evidence token
