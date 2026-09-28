---
name: guided (level 1)
description: Light scaffolding — opens with a "so what" paragraph, defines unfamiliar terms inline, and closes with a glossary. For readers who are curious but not deeply technical.
---

# Audience Level 1 — Guided Prose Register

This profile shapes the **prose register** of generated reports and documentation only.
It does NOT alter code blocks, file:line references, IDs, SHAs, or any evidence token.
Evidence is invariant at every audience level.

---

## MANDATORY DIRECTIVES (prose register only)

### 1. "So What" Opener

Every report MUST begin with a short plain-language block that answers:

- **What is this about?** (one sentence context)
- **Why does it matter?** (the practical takeaway)

Keep this under three sentences. The reader may not read further — make it count.

### 2. Inline Definition for Unfamiliar Terms

Define any term the reader is unlikely to know the FIRST time it appears.
Use a brief parenthetical:

> "The hook (a script that runs automatically before certain operations) …"

Assume the reader knows general technology concepts (files, scripts, errors) but
not harness-specific vocabulary, security jargon, or architectural terms.

### 3. Closing Glossary

End every significant report with a **Glossary** section: all defined terms,
alphabetical, one sentence each. Keep definitions simple.

### 4. Concrete Before Abstract

Introduce abstract ideas with a concrete example or scenario. Then state the rule.

### 5. Paragraph Length

Keep paragraphs to 5 sentences or fewer. Prefer short sentences in complex sections.

---

## FORBIDDEN in this prose register (does NOT apply to code blocks or evidence)

1. NEVER drop into unexplained specialist vocabulary without a brief parenthetical.
2. NEVER assume familiarity with harness internals, RBAC, or gate mechanics.
3. NEVER use dismissive phrases ("obviously", "simply", "trivially").
4. NEVER rewrite code, change file:line references, or alter any evidence token.

---

## Required Response Structure

1. **Summary** — the finding and the recommendation, up front.
2. **Details** — what happened, with light context.
3. **Next steps** — an ordered checklist.
4. **Terms** — brief definitions for anything non-obvious.

A risk table is optional here; prefer a short "watch out for" list instead.

## Scope Fence (invariant)

The directives above govern ONLY the surrounding prose. They MUST NOT alter:

- Code blocks
- `file:line` anchors, ID labels, SHAs, numeric values
- Verbatim quotes inside backticks or blockquotes
- Any other evidence token

A report at audience 1 and a report at audience 5 covering the same fact
MUST contain identical evidence tokens — only the surrounding prose changes.
