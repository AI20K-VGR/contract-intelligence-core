# Convergence and decision — on-demand drawer

Load at Consensus phase (step 7). Goal: finalize a defensible approach and record the decision to prevent re-litigation.

## Convergence conditions

Brainstorm is considered converged when ALL of the following hold:

- [ ] ≥2 options have been presented and compared across ≥4 dimensions (see divergence-techniques)
- [ ] The trade-offs of the chosen option have been stated clearly (not just the benefits)
- [ ] The user has confirmed "I agree to go this direction" (explicit, not inferred)
- [ ] No open questions remain that affect the architecture

Not all conditions met → continue Debate, do not jump to recording DEC.

## Decision classification

| Type | Record DEC? | When |
|---|---|---|
| Architecture call (schema, public API, data model, infra pattern) | **Required** | Immediately at consensus |
| Internal technical choice (lib choice, algorithm, naming) | Recommended | If it could be relitigated |
| UX / scope cut | Not required | Recording in the report is sufficient |

## Recording a DEC (architecture call)

```bash
python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/decision_register.py --append-alloc \
  --title "<short decision title>" \
  --rationale "<chosen approach + reason in 1-2 sentences; note rejected alternatives and why>"
```

After recording: read the entry back to confirm it is correct before reporting to the user.

**Re-litigation rule**: when old tension about a recorded decision resurfaces, read the register first (`decision_register.py --list` or `--get <id>`). Reopen only when there is
**new evidence** or **clearly changed context** — do not relitigate because "I think differently".

## Convergence report

Report at `plans/reports/<slug>-brainstorm-report.md` must include:

```
## Brainstorm outcome

**Problem**: <1-2 sentence statement>

**Options evaluated**:
| Option | Pros | Cons | Reversibility |
|---|---|---|---|
...

**Decision**: <chosen approach>
**Rationale**: <2-3 sentences>
**Accepted trade-off**: <what is sacrificed>
**Open questions** (if any): <list>
**DEC recorded**: <id if applicable> or N/A
```

## Plan handoff

After the report is saved and DEC is recorded (if needed), propose the next step via `AskUserQuestion` with 3 options:

1. `/hs:plan --tdd` **(Recommended when)** refactoring core logic or existing test coverage must be protected.
2. `/hs:plan` (default) for a new feature or moderate change.
3. Stop — user wants to plan later or hand off elsewhere.

Pass the absolute report path as context for `/hs:plan` to ensure plan continuity (the plan does not need to re-read everything from scratch).
