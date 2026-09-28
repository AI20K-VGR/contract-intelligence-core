# Observation signal — the end-of-work emit checkpoint (on-demand)

Load at the END of a skill run that carries an observe checkpoint (`hs:cook`, `hs:plan`,
`hs:code-review`, `hs:critique`, `hs:fix`). Those skills each keep a one-line pointer here
and the signal vocabulary that is theirs alone; the shared contract — when to emit, when to
stay silent, what the record is for — is this file and is not restated in any of them.

A counter can see that a gate blocked three times. It cannot see that the third block was
the same root cause wearing a different hat. That judgment is the only thing worth emitting.

## When to emit

Emit ONE closed-vocab signal when the run surfaced a judgment a counter cannot see.
Not every run produces one. Most do not.

| Situation | Emit? |
|---|---|
| The run hit friction a metric already records (a count, a duration, an exit code) | No — the counter has it |
| The run surfaced WHY a repeated failure repeats | Yes |
| Nothing notable happened | No — skip silently |
| Something notable happened but no vocabulary term fits | No — see "Vocabulary" below |

**A fabricated signal is worse than none.** The `observations` lens is honesty-gated: it is
read as a record of real judgment, so a signal emitted to look diligent poisons the read for
everyone downstream. Silence is the correct and expected default.

## Vocabulary

Terms live in `harness/data/observation-signals.yaml` — closed vocabulary, no free text in
the `--signal` field. Each skill's own pointer names the subset valid for that skill.

If no term fits what you observed, do NOT stretch the nearest one to fit. Skip the emit and,
if the gap looks durable, route to `hs:remember` to propose a vocabulary addition instead.
A mislabelled signal is indistinguishable from a fabricated one once it is in the store.

## Invocation

```bash
python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/emit_observation.py --skill hs:<skill> \
    --signal <term-from-this-skill's-subset> \
    --payload "<one line: what happened>"
```

The `--payload` is one line of prose for the human who reads the lens later. Write the
observation, not the emotion: "red-team reopened a phase the plan marked settled" beats
"plan quality was poor".

## Two-output nudge

When a run hits recurring friction or produces a convention worth keeping, suggest capturing
it — `hs:remember` for a durable rule or decision, or a per-repo review rule via the
rule-author skill (writes `standards.user.yaml`). A reusable insight that dies with the run
is wasted work.

Suggestion only: no new gate, no heavy process, and never a blocker on the handoff.
