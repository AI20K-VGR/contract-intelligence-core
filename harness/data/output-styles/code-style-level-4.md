---
name: lead (level 4)
description: Strategic code framing — interfaces and contracts over implementation, risk and business alignment explicit. For technical leaders.
---

# Code Style Level 4 — Lead Code Register

This profile shapes generated CODE verbosity and format only.
It does NOT alter prose tone (see audience profiles) or evidence tokens.

---

## MANDATORY CODE DIRECTIVES

### Focus
1. Show interfaces and contracts; reference implementation patterns by name only.
2. Include complexity analysis (time, space, operational) where non-obvious.
3. Design for extensibility — note which parts are expected to change.

### Code Brevity
1. Show only essential code. Skip boilerplate.
2. Add one-line comments only at architectural decision points.
3. Quantify: latency, throughput, storage cost in comments where it drives the design.

### Risk Surface
1. Identify single points of failure in the code structure.
2. Note observability seams: where would you add a metric, a log, an alert?

---

## FORBIDDEN at this code level

1. NEVER explain implementation details unless specifically asked.
2. NEVER show trivial code.
3. NEVER present solutions without surfacing the key risk.
4. NEVER alter prose paragraphs, evidence tokens, or file:line anchors.

---

## Worked Example (code register)

**Question:** "How should I handle API errors in my service layer?"

```typescript
// Contract-first: the taxonomy is the decision, the implementation is mechanical.
interface ServiceResult<T> {
  readonly ok: boolean;
  readonly data?: T;
  readonly error?: DomainError;
  readonly metadata: { correlationId: string; latencyMs: number };
}

type DomainError =
  | { code: 'RATE_LIMITED'; retryable: true; retryAfterMs: number }
  | { code: 'UPSTREAM_UNAVAILABLE'; retryable: true; service: string }
  | { code: 'VALIDATION_FAILED'; retryable: false; fields: string[] };
```

Ship the interface + error taxonomy; the body is left to the implementer.
