# Five-hat elaboration — constructive design generation (on-demand)

Load during the ELABORATE step of `hs:plan`, after intake and BEFORE the red-team
gate. Five internal "hats" each look at the same problem through a different lens and
each PRODUCES design material; the planner then synthesises that material into the
plan. This is the *constructive* counterpart to the adversarial passes — five-hat
BUILDS a design; red-team and premortem ATTACK one that already exists.

## When to run

- After intake/discovery has fixed the problem and constraints.
- Before there is anything to attack — five-hat produces the artifact the red-team
  gate and the 6-lens premortem then stress.
- Default is **five sequential lenses in one planner thread**. Fan-out to `@researcher`
  is optional, only when the problem is large enough that parallel lenses pay off — do
  NOT spawn a persona sub-agent per hat (YAGNI; a lens is a viewpoint, not an agent).

## The five hats

| Hat | Lens | Leading question | Produces → lands in plan |
|---|---|---|---|
| Product Manager | jobs-to-be-done | Who hires this and for what outcome? | JTBD statements, personas, pain points → §Discovery |
| Strategist | value & guardrails | What is the one metric that must move, and what must not regress? | north-star + success + guardrail metrics → §Strategy |
| UX Designer | user flow | What does the user actually do, step by step, and where do they get stuck? | draft flows, state matrix, onboarding → §Strategy/§UX |
| System Architect | structure & contracts | What ships as one unit, and which contracts change? | C4 context/container sketch, contract deltas, data model → §Architecture |
| Delivery Manager | decomposition | How does this split into ordered, verifiable work? | task DAG, risks, DoD, spec classification → phase-DAG |

The planner orchestrates: pose each hat a focused question, take its structured output,
and fold it into the matching plan section. The hats are invisible to the user — the
user talks to the planner, not to a hat.

## Spec classification (Delivery hat)

Every acceptance criterion is classified before ELABORATE closes. Do NOT re-coin the
decision tree here — it is the SSOT in [`../../../../rules/testability-triad.md`](../../../../rules/testability-triad.md):
each AC is a `test` (behavioural, one input→output), an `invariant` (universal /
structural / absence claim over a set — verified by a full-enumeration rule, see
[`multi-plan-split.md`](multi-plan-split.md) siblings and the claim-verify engine), or
`manual` (human judgement). A universal-and-behavioural AC splits into two items — one
invariant for structural enforcement, one test for the behaviour. Route each classified
item into the phase's acceptance block; that is what the Delivery hat hands to
[`phase-decomposition.md`](phase-decomposition.md).

## Five-hat ≠ red-team ≠ `hs:predict`

- **Five-hat builds.** It generates design material before any critique target exists.
- **Red-team ([`red-team-gate.md`](red-team-gate.md)) and the 6-lens premortem
  ([`../../../../rules/plan-quality-goodhart-premortem.md`](../../../../rules/plan-quality-goodhart-premortem.md))
  attack.** They run AFTER five-hat, over the design five-hat produced, hunting where it
  breaks or games its own metrics.
- **`hs:predict`** is a 5-expert adversarial debate over a proposed change — again a
  critique of an existing design, not construction.

Running a critique pass as if it were construction (or vice-versa) wastes both: you
cannot attack a design that does not exist yet, and you should not re-derive the design
inside the red-team.

## Anti-patterns

- **Empty hats** — a hat that "considered X" without producing concrete material is
  noise; each hat must land an artifact in a named plan section.
- **Spawning five persona agents for a small task** — the default is sequential lenses
  in one thread; fan-out is an optional optimisation for large problems only. Creating a
  new skill/agent per hat is out of scope (it drags in the full skill-wiring chain).
- **Re-coining the test/invariant/manual decision tree** — point at
  `testability-triad.md`; two copies drift.
- **Rewriting the red-team angle** — five-hat is constructive; keep the critique in the
  red-team gate.

## Handoff

Five-hat material → [`phase-decomposition.md`](phase-decomposition.md) (turn the Delivery
hat's DAG into phases) → [`red-team-gate.md`](red-team-gate.md) (attack the result).

Grounded in `docs/product/_refs/frankcode-src/planner-executor/agents/frankode-planner.md`
(Five Internal Hats table + spec-classification decision tree). The FrankCode sub-agent
tiers (`planner-jtbd`, `planner-strategy`, …) are adapted to harness lenses — the harness
has no such agents; a hat is a sequential viewpoint or an optional `@researcher` fan-out.
