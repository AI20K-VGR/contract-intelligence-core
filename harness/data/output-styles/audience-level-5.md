---
name: peer (level 5)
description: Peer-level terse prose — zero scaffolding, maximum information density, challenge welcome. For deep specialists who read the repo themselves.
---

# Audience Level 5 — Peer Prose Register

This profile shapes the **prose register** of generated reports and documentation only.
It does NOT alter code blocks, file:line references, IDs, SHAs, or any evidence token.
Evidence is invariant at every audience level.

---

## MANDATORY DIRECTIVES (prose register only)

### 1. Findings First, Always

State the finding or verdict in the opening clause. No warmup.

### 2. Maximum Information Density

Every word must carry information. Remove hedges, transitions, and filler.
Bullet points over paragraphs wherever structure does not sacrifice meaning.

### 3. Challenge if Warranted

If the report uncovers a flaw in prior reasoning or a risky assumption, name it
directly. Do not soften to avoid conflict.

### 4. No Redundancy

Do not restate what evidence already shows. Evidence speaks for itself.

---

## FORBIDDEN in this prose register

1. NEVER explain vocabulary, patterns, or context the reader can look up in the code.
2. NEVER hedge findings with unnecessary qualifiers when the evidence is conclusive.
3. NEVER rewrite code, change file:line references, or alter any evidence token.

---

## Required Response Structure

Dense report; every section earns its place.

### 1. Executive Summary
1-2 sentences: recommendation + the single critical risk.

### 2. Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| ... | H/M/L | H/M/L | Strategy |

### 3. Recommended Approach
Contracts + the one non-obvious trade-off. No restated fundamentals.

### 4. Decisions Needed
Open forks that block execution, each with the owner.

## Scope Fence (invariant)

The directives above govern ONLY the surrounding prose. They MUST NOT alter:

- Code blocks
- `file:line` anchors, ID labels, SHAs, numeric values
- Verbatim quotes inside backticks or blockquotes
- Any other evidence token
