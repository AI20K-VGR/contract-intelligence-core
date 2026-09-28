---
name: hs:autonomous-bell
injectable: true
description: Use when starting an unattended /goal or AFK loop that should end itself. Arms a reminder cron carrying a self-contained post-check protocol plus a consecutive-empty counter whose STOP is a deterministic off-decision read from disk — not a recollection — backed by the cron's 7-day expiry and session exit as hard floors.
argument-hint: "[threshold] [scope]"
allowed-tools: [Bash, Read, Glob, Grep]
metadata:
  compliance-tier: workflow
---

# hs:autonomous-bell — a self-ending unattended loop

Arms an autonomy bell: a reminder cron plus a consecutive-empty counter that helps an unattended loop end itself. The counter makes the off-DECISION deterministic (STOP is read from a disk ledger, not from the model re-reading a rule it cannot see inside an autonomous loop). STOP is not self-enforcing — the loop ends when the model runs `CronDelete` on STOP; the cron's 7-day expiry +
session exit are the hard floors that bound it regardless.

Full lifecycle, cron-prompt template, CLI, and the stop-guarantee detail: `references/bell-protocol.md`.

## When to use

- An unattended `/goal` / AFK loop that should end itself when the work is done.
- NOT for interactive sessions — there the operator is the stop signal.

## Setup (three steps)

1. **Arm the cron.** Create a recurring reminder (e.g. every 15 min) whose prompt carries the protocol verbatim from `references/bell-protocol.md`. Note the returned cron id — it is the `<CRON_ID>` below.

2. **Seed the counter, keyed by the cron id** (parallel runs never share a ledger), with a threshold (consecutive empty scans before STOP, default 2):

       python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/autonomy_bell.py --session <CRON_ID> --init --cron-id <CRON_ID> --threshold 2

3. **Run the loop.** On each fire, gather evidence, then report one outcome. For the backlog half of that evidence, consult the deterministic, run-scoped query instead of eyeballing prose — it answers `found` / `empty` / `abstain` for THIS run only (tagged by `<CRON_ID>`):

       python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/autonomy_bell.py --backlog-signal --source-ref <CRON_ID>

   `found` = this run still has open backlog items; `empty` = none of this run's items are open; `abstain` = no run tag (the backlog stays silent — use your other scope evidence). A GLOBAL open item from another run must NOT make you report `found` (C2). Then fold the outcome into the counter:

       python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/autonomy_bell.py --session <CRON_ID> --report empty   # nothing left
       python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/autonomy_bell.py --session <CRON_ID> --report found    # work remains

   The command prints `CONTINUE` or `STOP`. On `STOP`, `CronDelete <CRON_ID>` and HALT — do not re-scan (a later `found` would resurrect the loop). The `--backlog-signal` query is deterministic evidence; YOU still own the report.

## Rules

- Decide empty vs found from EVIDENCE (open phases, failing tests, this run's open backlog items via `--backlog-signal --source-ref <CRON_ID>`), not vibe. A false `found` never lets the loop end; a false `empty` ends it early. The backlog query is run-scoped: a global open item from another run must never pin you to `found` (C2).
- Only CONSECUTIVE empties trip STOP — a `found` resets the streak.
- STOP is terminal: delete the cron and stop. The run is over.
- Not full autonomy: pause and interview the operator on any design or resource decision. The bell decides WHEN to stop, not whether to ask.

## Backstops (hard floors)

The cron's 7-day auto-expiry and session exit bound the loop even if the CronDelete on STOP is missed — they are the hard stop; the counter is the best-effort off-decision on top. Details: `references/bell-protocol.md`.
