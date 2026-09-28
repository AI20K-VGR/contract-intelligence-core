# Saturation loop — hs:scenario

Iterative loop mechanism: generate -> classify -> log -> check halt. Use when `--iterations N` or `--saturation` mode is specified.

Source pattern: uditgoenka/autoresearch (MIT).

---

## Core loop

```
while not halted:
    pick highest-priority unexplored dimension or combination
    generate ONE concrete situation (specific trigger, flow, expected outcome)
    classify against all previously kept situations
    if New or Variant: keep -> expand edge cases -> log row
    if Duplicate / OutOfScope / LowValue: discard -> log reason
    check halt condition
    if iteration % 5 == 0: print progress summary
```

Each round is atomic: generate -> classify -> decide -> log -> repeat.

---

## Novelty detection

Classify by semantics, not keywords.

| Classification | Criteria |
|---------------|---------|
| **New** | Different dimension AND different trigger/precondition from all kept situations |
| **Variant** | Same dimension OR similar trigger but meaningfully different actor, data, or outcome |
| **Duplicate** | Same dimension + same trigger + same expected outcome |
| **Out of scope** | Cannot be mapped to the seed scenario |
| **Low value** | Technically possible but not realistic in the domain under consideration |

Same flow, different field name = Duplicate. Different actor, same step = Variant (persona shift has value).

---

## Halt conditions

### Bounded mode (`--iterations N`)
Stop after exactly N rounds. Print final summary.

### Saturation mode (`--saturation`)
Track `consecutive_no_new` counter:
- Any round with 0 `New` classifications -> increment counter
- Any round with >=1 `New` -> reset counter to 0
- When counter reaches **2** -> halt, print confidence message

Threshold of 2: one blank round may signal dimension exhaustion; two consecutive rounds confirm saturation.

### One-shot (default, no flag)
No loop. Generate 3-5 scenarios per applicable dimension in a single pass.

---

## Diminishing returns warning

In saturation mode, print a warning after 5 consecutive rounds with no new situations:

```
[!] Diminishing returns: 5 consecutive iterations produced no novel scenarios.
    Consider narrowing scope or using --saturation to halt automatically.
```

(Advisory only — does not stop; waits for halt condition.)

---

## Progress summary (every 5 rounds)

```
=== Scenario Progress (iteration 15) ===
Scenarios kept:    12  (8 new, 4 variants)
Discarded:          3  (2 duplicates, 1 out-of-scope)
Dimensions covered: 7/12 (58%)
Edge cases found:  18
Severity:          2 Critical, 4 High, 8 Medium, 4 Low
Coverage gaps:     scale, temporal, recovery
```

---

## TSV log (`scenario-results.tsv`)

Append 1 row per round:

```tsv
iteration	dimension	classification	severity	title	description	parent
1	happy_path	new	-	Successful checkout	User completes standard checkout	-
2	error_path	new	HIGH	Payment declined	Card rejected during checkout	-
3	edge_case	duplicate	-	Empty cart	Already covered by #1	#1
```

---

## Rotation strategies

Rotate to avoid dimension lock — required after 3 rounds on the same dimension:

| Strategy | When |
|----------|------|
| Dimension walk | First rounds — cover all dimensions once |
| Combination | Middle: combine 2 dimensions (e.g. edge_case + concurrent) |
| Negation | When stuck: negate a happy-path step |
| Amplification | Amplify one parameter of an existing situation to an extreme |
| Persona shift | Same scenario, different actor |
| Temporal shift | Same scenario, different point in time (peak load, first use, maintenance) |

---

## Composite score (bounded mode)

Calculated at the end of a bounded run:

```
score = scenarios_generated * 10
      + edge_cases_found * 15
      + (dimensions_covered / total_dimensions) * 30
      + unique_actors_explored * 5
      + high_severity_found * 3
```

High score = breadth + depth achieved.

---

## Anti-patterns

| Anti-pattern | Why to avoid |
|---|---|
| Generating 50 happy paths | No value after the baseline is established |
| Sticking to one dimension | Rotation is required after 3 rounds on the same dimension |
| Vague situations | Must have a specific trigger, flow, and expected outcome |
| Skipping classification | Duplicates inflate the count without increasing coverage |
