# Intake and interview discipline (on-demand)

Load during `hs:plan`'s Understand step and `hs:discover`'s scoping step — how hard to
interview, when to stop, and what never gets skipped regardless of how hard.

### band-driven posture ladder

Interview posture scales with the `interview_rigor` voice knob (light/standard/deep):
`light` asks only blocking questions, `standard` challenges the vaguest fact, `deep`
probes every gap/edge-case/acceptance-criteria hole before moving on. The band sets HOW
MANY questions to ask — never whether to ask the ones the P0 check requires.

### P0 check

Before decomposing, a small set of facts is load-bearing (the plan's 5-facts floor:
expected output, acceptance criteria, scope boundary, non-negotiable constraints,
touchpoints — spelled out at `hs:plan`'s `no_plan` step). Call this a **check**, not a gate —
"gate" stays reserved for the artifact-presence mechanism
(`harness/rules/harness-contract.md:17-23`); this is a pre-decomposition pass over facts,
not an artifact-existence check.

### skip-already-answered

Before asking, scan what the user already stated this turn or in an attached
brief/spec — re-asking a fact already on the page wastes the user's patience. Ask only
the facts still missing after that scan.

### JTBD filter

Before adding a question, ask "does the answer change what gets built" — a question
whose answer is cosmetic (naming preference with no behavior impact) is not worth the
user's turn; cut it. The floor is 5 facts, not 5 questions — one AskUserQuestion round
can pin several at once.

### no-fabrication + surface-conflicts-before-missing

Never invent an answer the user did not give — an assumed fact must be tagged
`[ASSUMED]` and confirmed, never silently baked in. When gathered facts CONFLICT with
each other (a stated constraint contradicts the requested scope), surface and resolve
the conflict FIRST — before chasing a still-missing fact, since resolving it can change
what is actually missing.

### precedence knob-vs-band

`interview_rigor` wins on HARSHNESS ONLY — how many probing follow-ups, how hard claims
get challenged. It never lowers the P0 check: the 5-facts floor (expected output /
acceptance criteria / scope boundary / non-negotiable constraints / touchpoints) is
INVARIANT regardless of band — even `light` posture must pin all 5 before decomposing,
it just asks fewer probing follow-ups to get there.

## Examples

IN: "add pagination to the users list", user already answered "cursor-based, 50/page" ->
skip re-asking page-size (skip-already-answered), still pin scope boundary (does this
cover the admin list too?) before decomposing.
OUT: asking 8 questions on a `light`-band trivial config change because a probing habit
ignored the band — the ladder exists precisely to prevent this.
