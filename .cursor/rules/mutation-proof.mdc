# Mutation proof — a gate counts only after something made it RED

**When:** you wrote or widened a **gate** — a test whose job is to catch a class of
mistake in someone else's future work (a guard, an absence check, a structural
invariant, a detector). Not for an ordinary behavior test, which the red→green cycle
already proves. Fires whenever a gate is edited, including outside any `hs-run` verb.

This is NOT the red of `tdd-discipline`. There, red means *nothing is built yet*. Here
the code is finished and green, and red has to be **manufactured** by breaking the
subject on purpose. A gate is written against a tree that already satisfies it, so it
is green from birth and nothing has shown it can ever fail.

## The three obligations

1. **Break what the gate claims to catch, run it, watch it go red.** The mutation must
   break the exact behavior named in the gate's own message, not something adjacent.
   Green under mutation means the gate is weak, the mutation missed, or both — find out
   which before believing either.

2. **Counter-control.** A gate proven to FIRE is not a gate proven to be RIGHT. Plant
   the case that must NOT be flagged and confirm it stays green. Without this, a gate
   that flags everything passes its own mutation and blocks honest work forever.

   **When the gate reads PROSE, sow a rewrite, not the sentence you just deleted.**
   That sentence is guaranteed to be caught — it is what the matcher was built from,
   so re-planting it measures nothing. Plant two or three sentences that teach the
   same thing in different words, and in the other language if the tree is bilingual.
   Measured twice, on gates that had already passed a mutation this way: a phrase-list
   matcher caught its own deleted sentence and let 3/3 rewrites through, and a matcher
   keyed on an identifier stayed green through a rewrite that kept the identifier and
   dropped the clause carrying the meaning. Both looked mutation-proven. The question a
   prose gate has to answer is *what makes this a violation* — lock THAT, then confirm a
   rephrasing that is still correct passes.

3. **Restore from a COPY you made yourself — never `git checkout` / `git restore`.**
   Those restore from the INDEX, not from the state before the mutation, so on a tree
   with uncommitted work they delete it. The failure is silent: the mutation step prints
   its expected result and its own restore line reads as success. Compare the restored
   file byte-for-byte against the copy; a clean `git status` does not prove it.

## Reading the result honestly

- **SURVIVED and NEVER-RAN look identical** on a results table. Before concluding a gate
  is weak, confirm the mutation actually changed the condition: a term still stated
  elsewhere in the same file leaves the condition genuinely true, so the gate is right
  and the mutation was incomplete. Replace EVERY occurrence, then re-read.
- A surviving mutation is a finding about the GATE, not a nuisance. Rewrite the gate;
  do not lower the mutation.
- Report mutations as `killed/total` with what each one broke. "Mutation-tested" with no
  count is a claim nobody can check.

## Scope-fence the gate itself

A gate whose scope is defined by a string the correct fix REMOVES goes blind exactly
when the fix is right — the more correctly someone repairs the tree, the fewer files the
gate looks at. Prefer an invariant a correct fix cannot erase. Sow the mutation AFTER
the fix lands, not before: the gate may have died of the fix.

## Not a severity

There is no mechanical detector for "this gate was never mutated", and there cannot
easily be one — the evidence is a run that happened and left nothing behind. Do not
promote this to a blocking severity in a standards file to make it visible; a
`critical` with no enforcement advertises a gate that does not exist, which is the
failure this rule is about.
