# patterns.md — Revision & Branching Patterns

Load for revision, branching, or hypothesis-testing examples in a Thought sequence.

## Revision patterns

### Assumption challenge

Initial assumption disproved by new data.

```
Thought 1/5: Assume X is the bottleneck
Thought 4/5 [REVISION of Thought 1]: X has sufficient capacity; Y is the real bottleneck
```

### Scope expansion

Problem larger than initially understood.

```
Thought 1/4: Fix a point bug
Thought 4/5 [REVISION of scope]: Architecture redesign needed, not just a patch
```

### Approach shift

Initial strategy doesn't meet requirements.

```
Thought 2/6: Optimize the query
Thought 5/6 [REVISION of Thought 2]: Need to optimize + add a cache layer
```

### Understanding deepening

Late insight fundamentally changes understanding.

```
Thought 1/5: Feature is broken
Thought 4/5 [REVISION of Thought 1]: Not a bug — the user is confused by the UX
```

## Branching patterns

### Trade-off evaluation

Compares two directions, different trade-offs.

```
Thought 3/7: Choose between X and Y
Thought 4/7 [BRANCH A]: X — simpler, less scalable
Thought 4/7 [BRANCH B]: Y — more complex, scales better
Thought 5/7 [CONVERGENCE]: Choose Y for long-term requirements
```

### Risk mitigation

Fallback for a high-risk primary direction.

```
Thought 2/6: Primary: API integration
Thought 3/6 [BRANCH A]: API integration details
Thought 3/6 [BRANCH B]: Fallback: webhook
Thought 4/6 [CONVERGENCE]: Implement A with B as contingency
```

### Parallel exploration

Investigate two independent unknowns at once.

```
Thought 3/8: Two unknowns — DB schema & API design
Thought 4/8 [BRANCH DB]: DB option
Thought 4/8 [BRANCH API]: API pattern
Thought 5/8 [CONVERGENCE]: Integrate findings
```

### Hypothesis testing

Try multiple explanations systematically.

```
Thought 2/6: Could be A, B, or C
Thought 3/6 [BRANCH A]: Test A — not the cause
Thought 3/6 [BRANCH B]: Test B — confirmed
Thought 4/6 [CONVERGENCE]: Root cause via Branch B
```

## Dynamic adjustment rules

**Increase M when:** New complexity discovered, more aspects to consider, verification needed, alternatives to explore.

**Decrease M when:** A key insight resolves things early, problem simpler than expected, steps merge naturally.

**Example:**
```
Thought 1/5: Initial
Thought 3/7: More complex (5→7)
Thought 5/8: Additional aspect (7→8)
Thought 8/8 [FINAL]: Complete
```

## Anti-patterns to avoid

- **Premature ending**: Placing `[FINAL]` before verification → add a verification Thought.
- **Uncontrolled revision cascade**: Repeated revision without clear reason → use `[META]` to diagnose.
- **Branch explosion**: Too many branches open → limit to 2-3, converge before opening a new branch.
- **Lost context**: Ignoring insights from previous Thoughts → always reference earlier Thoughts when needed.
