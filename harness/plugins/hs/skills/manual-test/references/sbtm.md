# SBTM details — charter, session, debrief, agent-memory

Session-Based Test Management adapted for the harness. Load when running a full manual-test session.

## Charter

A charter is ONE mission, timeboxed. Shape:

```
Charter: verify the password-reset flow rejects an expired token.
Area: auth/reset. Risk: a stale token still resets. Oracle: 400 + no DB write.
Timebox: 30m. Co-sign: <reviewer> (required only for a HARD gate).
```

The co-sign reuses `plan_approval`: a rostered reviewer distinct from the author records reading the charter + evidence. For a soft (advisory) manual run, skip it — the result stays soft.

**Coverage heuristic (SFDIPOT / FEW HICCUPPS — advisory).** Framing the charter: walk the SFDIPOT lenses so exploration isn't ad-hoc: **S**tructure,
**F**unction, **D**ata, **I**nterfaces, **P**latform, **O**perations, **T**ime. Each prompts a class of scenario (e.g. Data → boundary/empty/huge inputs; Time → expiry, races, ordering). This widens exploratory coverage; it is a thinking aid, never a gate.

## Session — anchored evidence

Export `HARNESS_MANUAL_TEST_SESSION=1` for the session. Every Bash command then leaves an anchor (`manual_test_anchor` hook → `state/telemetry/manual-test-anchor.jsonl`). Run real probes:

```
| ID | Scenario | Expected | Actual | HTTP | ms | anchor_id | Status |
|----|----------|----------|--------|------|----|-----------|--------|
| 1  | expired token | 400, no write | 400, 0 rows | 400 | 42 | <id> | PASS |
```

Cite the `anchor_id` the hook recorded for the command — do not invent one (the gate rejects an id absent from the telemetry).

Data proof: a before/after row count + a `SELECT ... LIMIT 1` makes a state change auditable. Config backup → revert if the session mutates config.

## Debrief — write the verification check

Emit the `manual` check (see SKILL.md). `evidence_tier`:
- `anchored` — output the hook witnessed (cite a real anchor_id).
- `claimed` — agent-written, below the floor (soft only; warn).

`charter_cosign` carries the reviewer identity for a hard gate, else `null`.

## Agent-memory (compounding learning)

Append durable manual-testing lessons to `state/manual-tester/<feedback|project>.jsonl` (append-only, actor+ts):
- `feedback` — a gotcha in the setup (an env quirk, a flaky probe).
- `project` — a real bug found + how it reproduced.

These compound across sessions so a later charter starts from known traps. Never write a result here — this is lessons, not evidence.
