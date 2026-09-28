# advanced.md — Advanced techniques

Load for complex problems requiring Spiral Refinement, Parallel Constraint Satisfaction, Uncertainty Management, or Meta-Thinking.

## Spiral refinement

Return to a concept multiple times, progressively deeper — each pass refines, not restarts.

```
Thought 1/7: Initial design (surface level)
Thought 2/7: Constraint A discovered
Thought 3/7: Refine for A
Thought 4/7: Constraint B discovered
Thought 5/7: Refine for both A and B
Thought 6/7: Integration reveals edge cases
Thought 7/7 [FINAL]: Final design handles all constraints
```

**Use for:** Complex systems, constraints emerging gradually during analysis.

## Hypothesis-driven investigation

Hypothesis → test → refine loop — effective for debugging.

```
Thought 1/6: Observe symptoms
Thought 2/6 [HYPOTHESIS]: Explanation X
Thought 3/6 [VERIFICATION]: Test X — partial match
Thought 4/6 [HYPOTHESIS]: Refine to Y
Thought 5/6 [VERIFICATION]: Test Y — confirmed
Thought 6/6 [FINAL]: Solution based on verified Y
```

**Use for:** Debugging, root-cause analysis, diagnostics.

## Multi-branch convergence

Explore multiple options, then synthesize the best approach — convergence typically produces a better result than any single branch.

```
Thought 2/8: Multiple viable directions
Thought 3/8 [BRANCH A]: Benefits of A
Thought 4/8 [BRANCH A]: Limitations of A
Thought 5/8 [BRANCH B]: Benefits of B
Thought 6/8 [BRANCH B]: Limitations of B
Thought 7/8 [CONVERGENCE]: Hybrid combining X from A with Y from B
Thought 8/8 [FINAL]: Hybrid outperforms either branch alone
```

**Use for:** Complex decisions with no clearly superior option.

## Uncertainty management

Handle incomplete information systematically.

```
Thought 2/7: Decision X is needed
Thought 3/7: Insufficient data — two possible scenarios
Thought 4/7 [SCENARIO A if P is true]: Analysis for A
Thought 4/7 [SCENARIO B if P is false]: Analysis for B
Thought 5/7: Decision that works for both scenarios
Thought 6/7: Or identify the minimum information needed
Thought 7/7 [FINAL]: Robust solution or clear information request
```

**Strategies:**
- Find a solution robust to the uncertainty
- Identify the minimum information needed to resolve it
- State assumptions explicitly with documentation

## Revision cascade management

Handle revisions invalidating multiple downstream Thoughts.

```
Thought 1/8: Foundational assumption
Thought 2/8: Build on Thought 1
Thought 3/8: Continue building
Thought 4/8: Discover Thought 1 is invalid
Thought 5/8 [REVISION of Thought 1]: Foundation corrected
Thought 6/8 [REASSESSMENT]: Are Thoughts 2-3 still valid?
  - Thought 2: Partially valid, needs adjustment
  - Thought 3: Completely invalid
Thought 7/8: Rebuild from corrected Thought 5
Thought 8/8 [FINAL]: Solution on the correct foundation
```

**Principle:** After a major revision, explicitly assess downstream impact before continuing.

## Meta-thinking calibration

Observe and adjust the thinking process when stuck.

```
Thought 5/9: [Normal thought]
Thought 6/9 [META]: Last 3 thoughts have been going in circles without progress
  Diagnosis: Missing a key piece of information
  Adjustment: Need to look up X before continuing
Thought 7/9: Result of looking up X
Thought 8/9: Decision is possible with complete information
Thought 9/9 [FINAL]: Continue on the effective path
```

**Use when:** Stuck, going in circles, or recognizing an ineffective pattern.

## Parallel constraint satisfaction

Handle multiple independent constraints simultaneously.

```
Thought 2/10: Solution must satisfy A, B, C
Thought 3/10 [CONSTRAINT A]: Solutions satisfying A: {X, Y, Z}
Thought 4/10 [CONSTRAINT B]: Solutions satisfying B: {Y, Z, W}
Thought 5/10 [CONSTRAINT C]: Solutions satisfying C: {X, Z}
Thought 6/10 [INTERSECTION]: Z satisfies all three
Thought 7/10: Verify Z is feasible
Thought 8/10 [BRANCH if not feasible]: Which constraint to relax?
Thought 9/10: Decide whether to relax a constraint
Thought 10/10 [FINAL]: Optimal solution within constraints
```

**Use for:** Optimization problems, multi-criteria decisions.
**Pattern:** Analyze independently → Find intersection → Verify feasibility.
