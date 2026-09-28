# Memory — the L4 lock (two-tier eval memory)

`eval_memory.py` closes the loop: a lesson learned in Phase 5 of one bootstrap
turn is recallable at Phase 1 of the next. This drawer is the reference for
`eval_memory.py` (verbs copied verbatim from its own `--help`) plus the four
usage rules `references/protocol.md` points at.

## 1. Two tiers — what routes where

| Type | Tier | Home | Tracked? |
|---|---|---|---|
| `lesson` | 1 | `<target>/evals/_memory/lesson.jsonl` | yes — lives in the target repo, team + CI visible |
| `incident` | 1 | `<target>/evals/_memory/incident.jsonl` | yes |
| `decision` | 1 | `<target>/evals/_memory/decision.jsonl` | yes |
| `standard` | 2 | harness state dir, per-machine (`eval_memory.py verify-home` resolves it) | no |

Accepted trade-off: a `standard` record is per-machine, not per-repo — it does
NOT travel with the repo, so a teammate on another machine or a CI runner
never sees it. That is the deliberate shape of tier-2 (cross-repo convention,
not a per-domain lesson); a `standard` important enough to bind the whole team
should graduate into a written rule, not rely on being read off this disk.

## 2. Record schema

One JSON object per line: `schema_version, actor, ts, type, id, domain,
surface, stack, card_hash, body`. `id` is `<type>-<ts-compact>-<4hex>`.
`actor` is `HARNESS_USER` env else the OS user — attribution, not auth.

Real example lesson record:

```json
{"schema_version": "1.0", "actor": "v.hieubt15", "ts": "2026-07-14T09:31:02.118000Z", "type": "lesson", "id": "lesson-20260714093102118000-a4f1", "domain": "cv_extraction", "surface": "extraction", "stack": "python", "card_hash": "sha256:9f1c...", "body": "empty-education-block samples score full marks under the old p0 rule; added an explicit empty-list case."}
```

## 3. Verbs (verbatim from `eval_memory.py --help` / per-verb `--help`)

```
append   --type {decision,incident,lesson,standard} --domain --surface
         --stack --body ["-" for stdin] [--target] [--card-hash | --auto-hash]
         [--tier {1,2}]
recall   [--filter k=v,k=v] --limit N [--type ...] [--target] [--tier {1,2,both}]
verify-home [--target]
```

Correct recall example (tier-1, AND-ed filter, capped):

```bash
python3 eval_memory.py recall --filter domain=cv_extraction,surface=extraction \
    --limit 10 --target .
```

## 4. Usage rules — each falsifiable

1. Phase 1 MUST run recall (limit 10, filter domain+surface+stack) before
   proposing a strategy; a proposal that ignores an applicable lesson must
   say why.
2. Phase 5 appends a lesson after verify is green — what made this eval
   differ from expectation (or a confirmation that nothing did).
3. The R9 gate's "add-guidance" choice appends a `standard` record (tier-2,
   cross-repo) — the user's correction becomes a durable, machine-recallable
   note, not a one-off comment lost after the turn ends.
4. An approved fill appends a `decision` record (tier-1) so resume compares
   the record's `card_hash` against the current card before reusing a fill.

## 5. Applying a lesson is judgment; the I/O is code

`recall` is deterministic I/O: it dumps matching records verbatim, nothing
more — it never ranks, summarizes, or decides which lesson applies. Reading a
lesson's `body` and deciding whether/how it reshapes THIS domain's card is the
model's judgment call (L1/L2 lock), never something the code auto-applies.
When a lesson does shape the card, cite its `id` in the card's
`cited_lessons` field (`references/protocol.md` Phase 2) so the user sees
exactly which past lesson is steering the proposal before they approve it.

## 6. Never dump the whole file

`recall --limit` is a required argument, not optional — there is no
"show me everything" mode by design (the flag's own help text: "max records
to print -- required, never dumps the whole file"). Context-budget note: keep
`--limit` small (10 is the standard this protocol pins); a memory file grows
across a project's life, and pasting the whole thing back into context
defeats the point of a compact, targeted recall.
