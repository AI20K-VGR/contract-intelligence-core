# Schema-drift checklist — migration-phase discipline (knowledge doc)

A knowledge reference for `hs:contract-test`, applied when a plan or PR carries a
migration (`type: migration`, a schema change, a data backfill). A migration that
passes review with a vague "update the user table" description is exactly how drift
happens. This checklist enforces that the migration declares its phasing and that the
merged change actually followed it.

**This is a knowledge doc, not a gate.** It never enters any `stage-policy.yaml
requires:` and no hook fires it — the same red line as the rest of `hs:contract-test`
("never gate-driven"). Use it as a review lens; capture any evidence it demands as
anchored manual evidence (`references/probe-catalog.md`) if you want it attached.

## When to apply

- **Requirements phase**: any plan containing ≥1 migration task.
- **Execution phase**: any PR whose source work is a migration.

## Migration phasing (expand → contract)

Every schema migration is phased, never a single destructive step:

1. **expand** — additive only: new column/table, nullable, no reader depends on it.
2. **backfill** — populate the new shape from the old; idempotent, resumable.
3. **backfill-verify** — row-count + checksum parity between old and new shape.
4. **reader-switch** (cutover) — flip readers to the new shape; writers still dual-write.
5. **contract** — drop the old shape once no reader/writer touches it.

Each phase is its own PR. An expand PR does not also switch readers.

## Requirements-phase checks

| # | Check | Pass criteria |
|---|---|---|
| 1 | Phasing declared | Tasks name explicit expand / backfill / backfill-verify / reader-switch / contract phases |
| 2 | Review required on every migration task | Migration steps carry an explicit human/independent review flag |
| 3 | PII columns tagged | Any column-name PII heuristic match → human co-sign required |
| 4 | Rollback per phase | Each phase has a `rollback:` — the reverse DDL/backfill, not "revert the PR" |
| 5 | Observation window declared | Each phase boundary names the observable evidence to collect before advancing |
| 6 | Retention/access preserved or tightened | Access-diff and retention-diff described; never silently widened |

Any fail → the migration is `revise` with the specific failing check named.

## Execution-phase checks

| # | Check | Pass criteria |
|---|---|---|
| 1 | PR phase matches declared phase | The diff only touches that phase's allowed surfaces |
| 2 | Shadow-write parity evidence attached | For the dual-write phase: described parity evidence over the observation window |
| 3 | Backfill-verify output attached | Row-count + checksum parity evidence present |
| 4 | Cutover checklist filled | Every item `Y` or `N/A` — no empty boxes |
| 5 | PII tag inheritance verified | New columns derived from PII inherit the `pii` annotation |
| 6 | No mixed phases in one PR | e.g. an expand PR does not also switch readers |

Any fail → `block` (not `revise` — a migration does not iterate in-flight).

## Cutover checklist

- [ ] New shape deployed and backfilled; parity verified.
- [ ] Readers switched behind a flag; rollback = flip the flag back.
- [ ] Writers dual-write for the declared window; parity holds.
- [ ] Old shape unused (no reader, no writer) before the contract PR.
- [ ] Contract PR drops old shape only; rollback = re-add nullable.

## Adaptation from source

Ported from `docs/product/_refs/frankcode-src/qa/methodology/qa/schema-drift-review.md`.
The source anchors parity/observation to SaaS metric queries (`parity_hours`,
`observation_h`); the harness is file-based, so those become **described evidence items
to attach**, not automated metric queries — capture them as anchored manual evidence,
never a live SaaS lookup.

## Anti-patterns

- "Migration-lite" plans that skip phasing "because the table is small".
- Rollback blocks that say "revert the PR" — true but useless; name the reverse DDL/backfill.
- PII tag missed because a column was renamed — annotation inheritance must catch it.
- Accepting a dual-write phase with only partial parity "because the diffs look explainable".
