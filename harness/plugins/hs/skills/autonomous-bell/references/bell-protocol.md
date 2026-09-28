# Bell protocol — arming and running an autonomy bell

The autonomy bell helps an unattended loop end itself. It pairs a reminder cron (which re-states the protocol on every fire) with a consecutive-empty counter (`"${HARNESS_BIN_ROOT:-.}"/harness/scripts/autonomy_bell.py`) that prints STOP after K scans find nothing left to do.

## What STOP does and does NOT guarantee

The counter makes the off-DECISION deterministic: STOP is read from a disk ledger, not from the model remembering to stop (an autonomous loop bypasses context injection, so a "remember to stop" rule is never re-read). But STOP is a string the script prints — it does NOT itself kill anything. The loop ends only when the model, on seeing STOP, runs `CronDelete <CRON_ID>` and halts.

So the HARD floors that bound a runaway loop even if the model misses that step are: the cron's 7-day auto-expiry and session exit. Treat the counter as a best-effort, deterministic off-decision atop those hard floors — not an enforced stop.

## Lifecycle

1. **Arm the cron** (learn its id first). Create a recurring reminder whose prompt carries the protocol below verbatim. CronCreate returns a job id — the `<CRON_ID>` used everywhere below.

2. **Seed a fresh run, keyed by the cron id** (so two parallel runs never share a ledger):

       python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/autonomy_bell.py --session <CRON_ID> --init --cron-id <CRON_ID> --threshold <K>

   K is the number of CONSECUTIVE empty scans that should end the loop (default 2). `--session <CRON_ID>` keys the ledger to THIS run; `--cron-id` records the id so the protocol can delete the right job on STOP. `--init` is idempotent — re-running it preserves a previously seeded cron id when `--cron-id` is omitted.

3. **Run the loop.** On each fire, follow the per-fire protocol. On STOP, delete the cron and halt.

## Cron prompt template (carry the protocol verbatim)

Pass this as the CronCreate `prompt`. Replace `<PLAN/SCOPE>` and `<CRON_ID>`:

    [autonomy bell] Scan <PLAN/SCOPE> for remaining work. For the backlog half,
    run the deterministic run-scoped query (this run's open items only):
        python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/autonomy_bell.py --backlog-signal --source-ref <CRON_ID>
      -> found = open items remain for THIS run; empty = none; abstain = no tag.
      A global open item from ANOTHER run must NOT make you report found.
    - Work remains -> do the next unit, then:
        python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/autonomy_bell.py --session <CRON_ID> --report found
    - Nothing left -> python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/autonomy_bell.py --session <CRON_ID> --report empty
    The command prints CONTINUE or STOP.
    - STOP     -> CronDelete <CRON_ID> and HALT NOW. Do NOT re-scan: a later
                  `found` would reset the streak and resurrect a loop you already
                  stopped.
    - CONTINUE -> keep going; the next fire repeats this scan.
    Not full autonomy: pause and ask the operator on any design/resource decision.

The prompt is self-contained: every fire re-states what to do, so the loop never depends on the model remembering across turns.

## Per-fire protocol

- Re-read the scope + the run tracker before scanning — work from state, not memory.
- Decide empty vs found from EVIDENCE (open phases, failing tests, backlog items), not vibe. A false `found` never lets the loop end; a false `empty` ends it early.
- For the backlog evidence, use the deterministic run-scoped query (`autonomy_bell.py --backlog-signal --source-ref <CRON_ID>`), NOT a prose grep. It is scoped to THIS run's `source_ref`: a GLOBAL `query --status open` is wrong here — one unrelated open backlog item would pin the bell to `found` forever and the loop could never STOP (the exact failure this section warns about). No run tag →
  the query abstains and you fall back to your other scope evidence. The query is deterministic; the model still owns the empty/found REPORT and the counter still owns STOP — the script does not compute the stop-decision.
- Report exactly one outcome per fire. `found` resets the streak; only CONSECUTIVE empties trip STOP.
- On STOP, treat it as TERMINAL: `CronDelete <CRON_ID>` so the job stops firing, then report done and halt. Do not run another scan — the run is over.

## Counter CLI

| Command | Effect |
|---|---|
| `--session KEY --init [--cron-id ID] [--threshold K]` | seed a fresh run (count 0) |
| `--session KEY --report empty` | advance the streak; prints CONTINUE or STOP |
| `--session KEY --report found` | reset the streak to 0; prints CONTINUE |
| `--session KEY --status` | print CONTINUE or STOP without changing state |
| `--session KEY --reset` | force count to 0 |
| `--state PATH` | point at an explicit ledger file (overrides `--session`) |

`--session` selects the per-run ledger (default key `current` when omitted — fine for a single run, but pass the cron id for any run that might overlap another). State is append-only JSONL under `harness/state/autonomy-bell/<key>.jsonl` (gitignored). A re-fired cron restores the last PARSEABLE record, so the streak survives across fires even if one append was torn by a kill (last-record-wins,
mirroring the afk circuit-breaker store).

## Backstops (the hard floors)

- The cron auto-expires after 7 days — a runaway loop cannot outlive that even if the CronDelete on STOP is missed.
- Session exit kills a session-only cron.
- The counter is the best-effort off-decision; the expiry and session-exit are the hard floors beneath it.

## Interactive vs autonomous

This skill is for UNATTENDED runs. In an interactive session the operator is the stop signal, so no bell is needed. The bell substitutes for a human when no one is watching — which is why the decision must be a counter read from disk, not a recollection the loop cannot reliably re-read.
