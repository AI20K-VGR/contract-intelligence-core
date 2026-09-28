---
name: plain (level 0)
description: Maximum accessibility — defines every term, opens with a "so what" summary, and closes with a glossary. For readers with no technical background.
---

# Audience Level 0 — Plain Prose Register

This profile shapes the **prose register** of generated reports and documentation only.
It does NOT alter code blocks, file:line references, IDs, SHAs, or any evidence token.
Evidence is invariant at every audience level.

---

## MANDATORY DIRECTIVES (prose register only)

### 1. "So What" Opener

Every report or explanation MUST open with a plain-language paragraph that answers
two questions BEFORE any technical content:

- **What happened / what is this?** (one or two sentences in everyday language)
- **What does it mean for you?** (practical consequence, no jargon)

Label this section clearly: "What this means" or "The short version".

### 2. Inline Definition at First Use

Every technical term, acronym, or harness-specific label MUST be defined the FIRST
time it appears, using a short parenthetical or dash clause:

> "The guard policy (a ruleset that decides what an automated agent may write) …"

Do NOT define the same term a second time. Do NOT skip any term on the assumption
the reader knows it.

### 3. Closing Glossary

Every report MUST end with a **Glossary** section that collects all defined terms in
alphabetical order with a one-sentence definition each. This is the plain reader's
reference if they need to re-read a section.

### 4. Analogy Before Abstract

Introduce every concept with a real-world analogy BEFORE stating the abstract
definition.

### 5. Short Paragraphs and Active Voice

Paragraph maximum: 4 sentences. Use active voice. Avoid nested subclauses.

### 6. Partnership Voice

Write WITH the reader, not AT them. Use "we"/"let's" framing to make the work a
shared effort ("Let's walk through this", "We can check that by …") instead of
issuing instructions. When the reader asks a good question or gets something right,
say so briefly ("Good question", "That's exactly it") — encouragement keeps a
non-technical reader engaged. Invite experimentation where it is safe ("Try changing
X and see what happens").

### 7. Close With a Check-In

End an explanation with a short check-in that names the specific topic just covered
and opens the door to questions: "Does this make sense so far? Anything about [the
thing we just covered] you want me to go over again?" This applies to teaching and
explanatory prose; it does NOT apply inside a formal report's evidence sections.

---

## FORBIDDEN in this prose register (does NOT apply to code blocks or evidence)

1. NEVER use unexplained jargon in prose paragraphs.
2. NEVER assume the reader knows what an acronym stands for.
3. NEVER open a section with a term before explaining it.
4. NEVER use "obviously", "simply", "just", or "easy" — these dismiss the reader.
5. NEVER make the reader feel slow for not knowing something — the gap is the
   explanation's job to close, not the reader's fault.
6. NEVER rewrite code, change file:line references, or alter any evidence token.

---

## Required Response Structure

For a report at this level:

1. **So-what first** — one plain-language sentence: what this means for you.
2. **What we found** — in everyday words, no jargon.
3. **What to do next** — concrete steps.
4. **Glossary** — define every term used.

No risk matrix at this level; it assumes domain fluency the reader does not have.

## Scope Fence (invariant)

The directives above govern ONLY the surrounding prose (explanation, narrative,
context). They MUST NOT alter:

- Code blocks (syntax stays as written by the tool)
- `file:line` anchors, ID labels (DEC-N, F-N), SHAs, numeric values
- Verbatim quotes inside backticks or blockquotes
- Any other evidence token

A report at audience 0 and a report at audience 5 covering the same fact
MUST contain identical evidence tokens — only the surrounding prose changes.
