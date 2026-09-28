# Delegation judgment — shared by `hs:plan` and `hs:cook`

`hs-run` tells you **when** a step needs a model. It cannot tell you whether you delegated
that step or quietly did it inline. Nothing mechanical catches that, so the discipline is
entirely on you. This file is the discipline.

## The bookend rule: anything that asks the user stays at MAIN

A subagent has **no TTY**, so `AskUserQuestion` dies there. Every step that must ask a human
is therefore held at main and is never delegated — for planning that is understand ·
scope-challenge · validate · approval · the probe-first empirical checks · the constraint scan ·
the final consistency sweep; for execution it is every STOP-and-ask and the per-phase review
of a delegated slice.

The delegated middle is the work that produces an artifact for you to judge: research,
writing the phases, attacking the plan, implementing a phase, running the suite, reviewing
the diff.

## Delegate by default; going inline is a DECISION you must surface

On a `hard`-mode plan the delegated middle goes to a subagent **by default**, and for
execution that means the phase's WHOLE red→green (write the test AND implement) goes to
`@developer`. Main keeps verification, the review of the subagent's code *and* test, and the
paired commit.

Resolve the mode deterministically — never on a gut feel about difficulty. Only an explicit
inline flag, or the phase's own `in_place: true`, authorizes inline.

**No flag, but you want to go inline anyway?** That is a deviation, not a default. Stop, ask
via `AskUserQuestion` (why inline, what is lost), and wait. Rationalizing inline from a memory
or an edge case is the exact failure this guards against — burying it in a one-line announce
is the same failure with better manners.

**A proactive / autonomous output style does not waive this.** "Prefer action, execute inline"
is a style preference; the delegation mandate is a plan mandate and out-ranks it. When the two
conflict, delegate or surface — never let the style bias silently pick inline.

**Already inside a worktree is still not a reason to go inline.** A plain spawn with no
isolation parameter runs in-place and inherits the current working directory, so its writes
land in the worktree you are already in. Only a spawn that explicitly asks for worktree
isolation gets its own tree, and that is for concurrent slices editing shared files — never
for a normal sequential phase.

**The one real exception**: a phase whose owned paths lie where the subagent's write policy
cannot reach — concretely, RBAC confines a `@developer` subagent's writes to
`harness/**` + `plans/**`, so a phase owning paths outside those is the canonical case. Then
main cooks it inline — scoped to that phase's owned paths only. An unscoped override does not
silence unrelated writes and is not what the exception grants.

## The end-of-work delegations are mandatory, including on "small" work

Independent test, independent review, and finalize are not optional tails. Running the suite
yourself is not a substitute for the independent tester; reviewing your own diff at the final
gate is not a substitute for an independent reviewer — the whole point is that it re-derives
correctness without your reasoning in its context.

**If the number of delegation calls at the end of a run is zero, the run is incomplete.**
That is a flat rule, not a heuristic.

## Two subagent hazards that fail silently

1. **A mistyped subagent type is silently ignored** and the spawn falls back to the DEFAULT
   general-purpose agent. No error — just the wrong agent running your gate. If a generic
   agent shows up where you named a specific one, suspect the typo and respawn.
2. **Do not average reviewers.** Any evidenced critical issue blocks, regardless of how many
   other lenses came back clean and how high their scores were. A mean is not a verdict.

## Trigger a domain-risk lens only when the domain is actually touched

Auth · secrets · payments · database schema · public API contracts · CI/deploy/release ·
migrations · destructive filesystem operations · production config. Spawn the specialist lens
when the changed files touch one of these — not on every run. A lens fired reflexively on
unrelated work trains everyone to ignore it.
