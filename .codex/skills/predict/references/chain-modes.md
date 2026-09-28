# hs:predict — Chain modes protocol (on-demand)

Chain modes run IN THE SAME predict session, not separate skills. Load this file only when `--chain <mode>` fires — zero cost for normal invocations.

---

## `--chain reason` — Subjective refinement loop

Use when verdict is **CAUTION** with subjective trade-offs (architecture, design, consistency) — no single correct answer, only "best so far".

### Protocol

```
1. Generate candidate
   - Take Recommendations from predict as the seed proposal
   - Materialize ONE specific refined version

2. Adversarial critique
   - Spawn 2 critic personas (independent of the original 5 personas):
     * Sceptic — find weaknesses, weak assumptions, hidden costs
     * Steel-Manner — produce the strongest possible counter-proposal
   - Each critic delivers 3-5 sharp findings (not "looks fine")

3. Synthesize
   - Take the strongest finding from each critic
   - Generate a NEW candidate that addresses them
   - Keep lineage log of previous candidates (do not discard)

4. Blind judge
   - Present the 3 most recent candidates anonymously (Candidate A/B/C — order not revealed)
   - Score on: clarity, durability, simplicity, fit-constraint (1-5)
   - Choose winner BEFORE revealing which candidate is which

5. Convergence check
   - If winner == previous winner OR all 3 candidates differ by <=1 point -> STOP
   - Otherwise: feed winner back to step 2, repeat

6. Limit
   - Maximum 5 refinement rounds. If exceeded -> surface lineage for user to choose
```

### Additional output (append to Prediction Report)

```
## Refinement Lineage (--chain reason)

| Round | Candidate | Key findings | Judge Score |
|-------|-----------|-------------|-------------|
| 1 | [seed = predict recs] | [sceptic + steel-manner top finds] | a/b/c/d -> total |
| 2 | [synthesis 1] | ... | ... |

## Converged recommendation
[Final winner with reasoning — replaces base Recommendations]
```

### When NOT to use `--chain reason`

- Verdict is **STOP** — fix the blocker first; refining a broken proposal wastes cycles
- Verdict is **GO** with all personas in agreement — nothing subjective left to refine
- The decision can be determined mechanically (perf benchmark, security audit) — use `hs:loop` or a security scan instead

---

## `--chain probe` — Mine missing requirements

Use when verdict is **CAUTION** or **STOP** due to "missing constraints" or "unstated assumptions" — proposal incomplete, requirements not yet gathered.

### Protocol

```
1. Seed
   - Take all predict findings tagged "assumption" / "constraint missing" / "unclear"
   - Convert each into a probe question:
     "What MUST be true about <X> for this proposal to work?"
     "What constraint on <Y> would invalidate this?"

2. Saturation generation
   - For each seed, generate 3-7 follow-up probe questions
   - Prioritize probes for:
     * Negative requirements ("MUST NOT happen when...")
     * Boundary conditions ("at scale N, with concurrency M...")
     * Stakeholder gaps ("who must approve before shipping?")
   - Continue until 2 consecutive batches yield no new constraints (saturation reached)

3. Group + de-duplicate
   - Group probes by domain (data, security, ops, UX, billing)
   - Within each group: merge duplicates, keep the sharpest formulation

4. Output as constraint cards
   - Each remaining probe becomes a card:
     * Question (probe)
     * Why it matters (1 line)
     * Next step: ASK (ask stakeholder) / TEST (run experiment) / DECIDE (commit to assumption)
```

### Additional output (append to Prediction Report)

```
## Probe Findings (--chain probe)

### Harvested constraints

| Domain | Question | Why it matters | Next step |
|--------|----------|---------------|-----------|
| Data | What MUST be true about row growth for this query plan to hold? | Determines index strategy | TEST |
| Security | What approvals are required for the new auth boundary? | Compliance gate | ASK |

### Open assumptions
[List of probes the user must resolve before implementation begins.]
```

### When NOT to use `--chain probe`

- The proposal is already constrained by an existing PRD/spec — probing will rediscover what is already known
- Verdict is **GO** — no missing constraints; proceed
- User has stated "I don't want a Q&A loop, just give me the verdict"

### Connection to `hs:plan`

Probe output feeds directly into `hs:plan` — each constraint card maps to one acceptance criterion. Recommended sequence:
`/hs:predict ... --chain probe` -> `/hs:plan` (pass the constraint table as input).

---

## Combining chains

`--chain reason --chain probe` is permitted but rarely useful — they target different failure modes:

| Verdict | Use |
|---------|-----|
| CAUTION (subjective) | `--chain reason` |
| CAUTION/STOP (missing constraints) | `--chain probe` |
| Both | `--chain probe` first (harvest constraints) -> re-run predict -> `--chain reason` (refine with full constraints) |

Do not run both in a single invocation unless the user explicitly requests it; the output will be noisy.
