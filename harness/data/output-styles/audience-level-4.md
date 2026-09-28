---
name: expert (level 4)
description: Dense, assumption-heavy prose — high jargon tolerance, minimal scaffolding. For readers deeply familiar with the domain and system.
---

# Audience Level 4 — Expert Prose Register

This profile shapes the **prose register** of generated reports and documentation only.
It does NOT alter code blocks, file:line references, IDs, SHAs, or any evidence token.
Evidence is invariant at every audience level.

---

## MANDATORY DIRECTIVES (prose register only)

### 1. Lead with the Critical Point

First sentence must state the key finding, risk, or recommendation. No preamble.

### 2. Assume Full Domain Familiarity

All harness vocabulary is known: guard policy, RBAC lane, actor attribution, stage
policy, fence checker, manifest re-pin, fail-open vs fail-closed. No definitions needed.

### 3. Quantify When Possible

State specific counts, sizes, durations, and version numbers rather than vague
qualitative descriptions.

### 4. One Sentence Per Idea

Prose is as dense as a code comment: every sentence adds new information.

### 5. Frame Recommendations Strategically

When the prose carries a recommendation, frame it the way a lead weighs options:
name the build-vs-buy-vs-partner trade-off explicitly, state the technical-debt
trajectory it sets (accumulating vs paying down), and tie the choice to the business
objective it serves. This is framing in the prose, not a design spec — the underlying
evidence and numbers stay invariant.

---

## FORBIDDEN in this prose register

1. NEVER add "context" sentences that restate facts the reader already knows.
2. NEVER define domain vocabulary — they know it.
3. NEVER rewrite code, change file:line references, or alter any evidence token.

---

## Required Response Structure

### 1. Executive Summary
3-4 sentences: key recommendation, critical risk, estimated effort.

### 2. Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| ... | H/M/L | H/M/L | Strategy |

### 3. Strategic Options
Compare 2-3 approaches on effort, risk, flexibility, and team fit.

### 4. Recommended Approach
Architecture / interfaces; essential code only.

### 5. Operational Considerations
Monitoring, alerting, runbooks, incident response.

### 6. Decisions Needed
What requires broader alignment, and who must be involved.

## Scope Fence (invariant)

The directives above govern ONLY the surrounding prose. They MUST NOT alter:

- Code blocks
- `file:line` anchors, ID labels, SHAs, numeric values
- Verbatim quotes inside backticks or blockquotes
- Any other evidence token
