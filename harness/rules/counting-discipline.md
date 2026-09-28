# Counting discipline (on-demand)

Load when anyone — you, a subagent, a gate — submits a **number** as evidence.
Every rule below came from a real failure, not from theory; the cases are in
`docs/harness/counting-discipline-casebook.md`.

Distinct from `sampled-rate-reporting.md`, which governs a rate measured on a
SAMPLE (`k/n` + a Wilson interval). This one governs whether the count itself is
sound: what the denominator is, what was excluded, and whether the measurement
ran at all. A census needs no interval and still needs all of the below.

## Evidence labels

The four labels are the harness's, defined in `verification-mechanism.md`:
`[OBSERVED]` / `[DERIVED]` / `[PRIOR]` / `[ASSUMED]`. Do not invent a fifth. Two
cases the counting work runs into, and where each lands:

- **Checking was attempted and could not be completed.** That is `[ASSUMED]`,
  with the reason it could not be checked stated beside it — an unrun claim never
  gets a label of its own for having been almost-run. (`UNVERIFIED` without
  brackets is a *verdict* about wiring in `no-orphan-code.md`, a different thing
  from an evidence label; do not borrow it here.)
- **No independent record exists — the number rests on the doer's word.** Still
  `[OBSERVED]`, and the sentence says *by self-report* every time it is quoted.
  Dropping that phrase on requote is how a self-graded number becomes a measured
  one.

Two rules that decide which label a number ends up with:

**A mixed-input inference takes the label of its weakest input.** One `[ASSUMED]`
in the chain pulls the conclusion to `[ASSUMED]`. Inference does not launder a
label, and neither does re-stating it more confidently.

**A phenomenon and the mechanism explaining it carry SEPARATE labels.** An
observed effect does not make its explanation observed.

## The denominator — what is being counted

- **Denominators come from the machine, not the hand.** A glob, a registry query,
  something reproducible, with the command in the record. Cheaper still: feed the
  system a deliberately wrong input — the error usually prints the valid set with
  the system's own authority.
- **Group by the question being answered, not by the shape of a name.** "Doors a
  user can type" is the registry, not a filename glob. When two groupings give two
  numbers, the by-question number is the primary one and the other is a footnote
  stating how it counted. Never pick one and hide the other.
- **A compliance or coverage rate depends on the path walked**, so state the path
  with it. Two rates from different paths do not compare.
- **Count every cell.** Never take a total and subtract what you have seen: "6 use
  it, 1 rolls its own" invites the conclusion that one cell is odd, and never asks
  where cell 8 went — where a second, differently-shaped exception was hiding.
- **Two known numbers sitting next to each other that disagree is a free signal.**
  It costs no measurement, only a subtraction. Do it before measuring anything.

## What was excluded, and why

- **State the population boundary in the same sentence as the ratio.** "46/93" does
  not say whether that is 2 files or 10, and the reader's conclusion widens on its
  own.
- **Exclude on a load-bearing criterion, verified by call path.** The criterion must
  be the one the claim rests on, not a different one that happens to give the same
  answer — a right conclusion resting on a wrong reason is still a broken standard,
  because whoever applies it next follows the reason. An element's own docstring is
  not evidence of how it is used.
- **When a set splits cleanly in two, look for the third column** — and treat the
  element you just excluded as the strongest positive control you have. It is
  usually the one proving the right behaviour is possible in this very tree, which
  is what kills "the architecture does not allow it".

## Sample or census

**Every ratio declares which it is**, even with no statistics attached. A
confidence interval on a census is decoration that manufactures false uncertainty
(sampling error is zero). And a self-seeded sample looks textually identical to a
census — `8/9` closed-set members and `4/9` variants you happened to think of read
the same and mean nothing alike, so the writer states which.

**Changing a denominator invalidates every correlation built on the old one.** Re-run
them. A dead correlation looks exactly like a live one.

## Did the measurement actually run

- **An absence claim is only as strong as the scope scanned** — put the scope in the
  sentence. "X does not exist" without it is four true statements that are all wrong
  together.
- **A zero is evidence only with a positive control of the same kind**, in the same
  scope: show the probe finds a comparable thing where one exists. A file that reads
  fine is not a control for a pattern that never matches in it.
- **Before an absence claim, list the spelling variants and scan each.** Case,
  hyphen vs underscore, abbreviation, digits in the name. A positive control proves
  the probe RUNS; it does not prove it COVERS — different questions, and a green
  control still misses a variant.
- **A classification table needs at least one row whose answer is known in advance.**
  A table that is all-`no` and a correct table look identical: same rows, even
  columns, exit 0. Without an anchor row you cannot tell "the criterion does not
  separate" from "the instrument is not running". Shell loops are high-risk
  instruments here; prefer a real parser for the format being counted.
- **A positive control for a COUNT is opening the file and looking**, not re-running
  the same probe. Re-running reproduces the same blind spot. And a command truncated
  for readability (`| head -3`) produces a number about the PIPE — never quote it as
  the count.
- **When a lookup fails, say it failed.** Never fall back to a preselected target and
  then speak in the user's name about something they never typed.
- **A mechanism reaches `[OBSERVED]` only when the data distinguishes the two
  hypotheses.** If the evidence fits both, the phenomenon stays observed and the
  mechanism drops to `[ASSUMED]`. But "the counting channel cannot separate them" is
  not "they cannot be separated" — ask the other channels (read the code, read the
  config, ask the system) before declaring a structural limit and sending the next
  person to build an experiment for a question already closed.
- **A refutation is a claim too**, and so is a number that closes a caveat. Both meet
  the same evidence standard as what they overturn. A closing number looks like
  paperwork, which is exactly why nobody checks it.
- **After fixing an instrument, ask what it is measuring — not just whether it
  measures correctly.** The mid-course fix manufactures confidence that everything
  downstream is clean; the failure is not measure-wrong-conclude-wrong, it is
  fix-correctly-then-conclude-wrong on the wrong set. A right answer to the
  neighbouring question feels like an answer to yours.
- **Re-scanning an absence claim on a REPAIRED tree: read the timestamps first.** A
  new match conflates "I scanned badly" with "somebody applied my own suggestion" —
  and without mtime or history you may withdraw a finding that was correct.

## Counting this repo's tests: go through the declared roots

A tree-wide `find . -name 'test_*.py'` answers a different question than the one you mean.
It once overcounted by ~2.9x and the number reached a plan as a denominator. The
contaminants are legitimate files that are simply not this repo's tests: a mutation-testing
working copy of the whole tree, and a vendored research harness with its own suite.

Dropping the one directory you happen to remember is the near-miss fix — measured on this
tree, removing the largest single contaminator still leaves the count well over, and a
deny-list is only as complete as the last person's memory. Count through `test_census.py`,
whose roots are the suite roots this repo declares in `harness/data/test-strategy.yaml`
(four today; the constant is gated against that file, so do not quote a fixed count). It prints files and callables
separately, and it prints the roots with every number.

## Deleting tests: name them, and anchor them to a rev

A record of a deletion is only evidence if a later reader can look one up. Record the
deleted callables' **names** and the **baseline rev** they were deleted from — not the
reason alone. A ledger keyed by reason and a reviewer searching by function name never
meet, and the cost is a correct cut restored on the belief that it was undocumented.

The baseline half stands on its own: without a rev, "this name is gone" and "this name
never existed" are the same sentence, and one of them cites a callable that never was.

Reconcile with `cull_evidence.py --file <ledger> --baseline <rev>` — it asks git which
test callables vanished and subtracts what the ledger names, so omitting the key hides
nothing. Exit 1 means some cut is unaccounted for.

## Where a rule belongs

A rule checkable by ONE command MUST get a mechanical gate; only rules needing
judgment may rest on human discipline. Measured on the arena that produced this
chapter: every repeat violation was of the cheap-to-gate kind, committed after the
rule existed, by people who knew it — including one committed while applying the
very rule, and one by the person who had described that trap two rounds earlier.
The gap between writing a rule and following it was never difficulty. It was that
**nothing asked the question at the right moment**.
