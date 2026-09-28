# scale-game — testing at extremes

Test at extreme values (1000x larger/smaller, instant/years) to reveal truths hidden at normal scale.

## Core principle

**Extremes reveal the foundation.** Something that works at this scale may break at another. "Should scale fine" with no evidence = an unverified assumption.

## When to use

| Symptom | Action |
|---|---|
| "Should scale fine" (no evidence) | Test at extremes |
| Not sure about behavior in production | Scale up 1000x |
| Edge cases unclear | Test min and max |
| Architecture needs validation | Extreme testing |

## Dimensions to test

| Dimension | Extreme test | Reveals |
|---|---|---|
| **Volume** | 1 item vs 1 billion items | Algorithmic complexity limits |
| **Speed** | Instant vs 1 year | Async requirements, caching needs |
| **Users** | 1 user vs 1 billion users | Concurrency, resource exhaustion |
| **Duration** | Milliseconds vs many years | Memory leaks, state growth |
| **Failure rate** | Never fails vs always fails | Error handling adequacy |

## Process

1. **Choose a dimension** — what can vary to an extreme?
2. **Test the minimum** — 1000x smaller/faster/fewer?
3. **Test the maximum** — 1000x larger/slower/more?
4. **Record break points** — where do limits appear?
5. **Record survival points** — what is fundamentally sound?
6. **Design for reality** — use insights to validate the architecture

## Both directions matter

**Testing smaller is equally important:**
- Only 1 user? Is the complexity still reasonable?
- Only 10 items? Is the optimization premature?
- Instant response? What becomes unnecessary?

Often reveals over-engineering or premature optimization.

## Harness-relevant example

**Architecture:** Hook emits events into an append-only JSONL file
**Max scale:** 10 million events/day (CI running continuously)
**Reveals:** JSONL file is unbounded -> disk exhaustion; a rotation policy is needed
**Min scale:** 1 event/month (small project)
**Reveals:** Overhead of parsing JSONL on each read is still acceptable -- no index needed

**Insight:** Log rotation is needed but an index is not -- the scale game confirms the trade-off

## Red flags — scale game is needed

- "Works in dev" (but what about production?)
- Limits are unknown
- "Should scale fine" with no evidence
- Surprised by production behavior
- Architecture feels arbitrary

## After the scale game, you must know

- Where the system breaks (specific limits)
- What survives (fundamentally sound)
- What needs redesign (scale-dependent)
- Production readiness (architecture validated)
