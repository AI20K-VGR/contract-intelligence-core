# Agent operational discipline (STRICT)

Behavioral input-discipline for any agent acting in this repo. It complements
the outcome-focused discipline (TDD, the verification invariants, the gates):
those say what a finished change must prove; this says how to act on the way
there so you do not burn turns on preventable mistakes.

> **The load-bearing one is PROBE BEFORE YOU BUILD ON A GUESS (below).** If you
> read nothing else here, internalize that: a load-bearing assumption you CAN
> check empirically must be checked FIRST — a real run is cheaper and firmer than
> predicting-then-building, and an unrun claim is `[ASSUMED]` (or `[PRIOR]` when it
> is training knowledge), never OBSERVED / "works". Claim typing is defined in
> `verification-mechanism.md`.

## THINK BEFORE EVERY ACTION

Before EVERY tool call, ask: **"Is this the smartest way to do this, or am I
taking a shortcut that will cost more later?"**

Three checkpoints:

1. **"What could go wrong?"** — If this fails or returns unexpected output, will
   I have what I need to diagnose it? If not, adjust BEFORE running.
2. **"Am I being lazy?"** — Is there a smarter approach that takes 2 more
   seconds of thought but saves minutes of wasted work?
3. **"Am I wasting resources?"** — Could I reuse previous output, validate
   locally, or avoid repeating work?

If you skip this step, you WILL do something avoidable. Most preventable
mistakes come from acting before thinking.

## NEVER DISCARD OUTPUT YOU MIGHT NEED

When running ANY command that could fail or produce diagnostic information, save
the full output to a temp file and then display a summary:

```bash
out=$(mktemp -t cmd-out.XXXXXX)
some-command 2>&1 | tee "$out" | tail -30
# Need more? Read "$out" — do NOT re-run the command.
```

An example in a rule is the default behaviour of everyone who reads it, so this
one names no fixed path. A literal `/tmp/cmd-out.txt` is the same filename in
every session: two agents running at once silently overwrite each other's
capture, and the second one reads the first one's output believing it is theirs.

Do NOT pipe through `tail` or `head` alone without also saving to a file. You
cannot predict where the useful information will be — capture everything, show a
summary, read more from the file if needed.

Do NOT re-run an expensive command just to see a different slice of its output.

## VALIDATE LOCALLY BEFORE REMOTE

Any validation that CAN be done locally MUST be done locally first. Remote
systems (CI, staging, etc.) confirm — they do not discover. If you are using a
remote system as your first line of validation, you are being lazy. Run the
focused tests, the lint, and the build locally before you push.

## PROBE BEFORE YOU BUILD ON A GUESS ★ (the priority discipline)

When a load-bearing assumption CAN be checked empirically, check it FIRST — before
you design, decide, or build anything on top of it. A real check is cheaper, faster,
and firmer than predicting-then-building on the guess, or verifying in circles by
reasoning without ever running the thing.

The cheapest real check almost always exists:

1. **Spike / PoC a thin slice.** A few lines that exercise the actual behavior beat a
   paragraph of hypothesis. Throw it away after — the knowledge is the deliverable.
2. **Run the real tool, not only a fake.** A fake or mock can pass while hiding the
   exact thing you were unsure about; drive the real dependency at least once.
3. **Read the source / the vendor doc, and web-search** to FORM the hypothesis — but
   a doc only tells you what X is *claimed* to do; confirm the behavior by running it.
4. **Right order:** probe → scope the finding by reading code / research → THEN build
   on the verified result. Do not invert it (guess → build → verify last).

**A doc, `--help`, man page, wiki, grep, or a chain of reasoning is NOT a probe — it is
a hypothesis about behavior.** For a load-bearing claim about how a tool/API/SDK actually
behaves, RUN it and read the real output; help text is wrong, incomplete, or misread often
enough to burn you (e.g. grepping `glab --help` and concluding a flag exists — when running
it would have shown it does not). Never launder doc-reading or reasoning as "probed" /
"verified": claiming you probed when you only read `--help` is a FALSE verification —
strictly worse than an honest `[ASSUMED]`, because it hides the gap instead of flagging it.

A claim you have not exercised for real is `[ASSUMED]` (training knowledge you have not
re-checked is `[PRIOR]`): label it with its honest type, and gate it behind one real-run
step (a probe, a dogfood pass, a live check). Never report "works" / OBSERVED from
reasoning alone. If you genuinely cannot probe now (missing creds/infra), say so plainly
and set a run-it-for-real gate — do not pretend it was verified.

**Respect the evidence ranking** — direct observation > reproduction > primary source >
secondary source > memory — and never build a load-bearing claim on a lower rung when a
higher one is one tool call away. And **read errors literally** before interpreting them:
the exact message, the exact line, the actual values — not what you expect them to say.
(The four claim labels OBSERVED / DERIVED / PRIOR / ASSUMED are defined in
`verification-mechanism.md`.)

## MINIMIZE TOOL COST

Every tool result stays in the context window and is read back on every
subsequent turn (the `cache_read` cost — the dominant token bill of a long
session). A fat result you needed once is a tax you pay every turn after. Keep
what enters context lean:

1. **Read only the slice you need.** For a large file, pass `limit`/`offset` and
   read the specific region — do not swallow the whole file to see ten lines.
2. **grep for the line, don't `cat` the file.** Search to the matching lines
   with line numbers; pull the file into context only when you actually need the
   surrounding body.
3. **Don't re-run an expensive command for a different slice.** Capture once to a
   temp file (see NEVER DISCARD OUTPUT) and read more from the file.
4. **Batch independent shell commands** into one call; avoid spawning a subagent
   or a second pass when the first result already answers the question.
5. **Bound tool output.** Prefer `--stat`/`--name-only`/`-q`/`| tail -N` over
   dumping full logs or diffs when a summary decides the next step.

These are soft input-discipline, not a gate — but on a long run they are the
single biggest lever on token cost.
