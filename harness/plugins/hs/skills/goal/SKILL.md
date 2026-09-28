---
name: hs:goal
injectable: false
description: >-
  Prepare a built-in /goal run at authoring time — interview the objective into a NEW self-contained goal.md,
  arm the autonomy bell, scaffold the intra-run cycle dir — then hand the loop to built-in /goal. Use when
  launching an unattended objective-until-met run that must survive being memory-blind between ticks. At the
  START of a run it arms hs:autonomous-bell with a run tag and scaffolds the cycle dir, then steps out of the
  way; never edits an existing ephemeral goal.md.
argument-hint: "\"<objective>\" [threshold]"
allowed-tools: [Bash, Read, Write, Glob, Grep]
disable-model-invocation: true
metadata:
  compliance-tier: workflow
---

# hs:goal — author a built-in /goal run, then step aside

Built-in `/goal` sets a string objective and self-iterates until a Stop-hook reports "met". It resets context every tick and never fires `UserPromptSubmit` mid-loop, so rules/voice are not re-injected and each tick forgets the last one. `hs:goal` does NOT fix that by reimplementing the loop (impossible — it is built-in). It prepares the run so the loop can work from FILES instead of memory,
then hands off.

Authoring boundary (do not cross): `hs:goal` generates a **NEW** self-contained `goal.md` and arms the substrate (full rule: Boundaries below).

Full detail: `references/authoring-protocol.md`. The intra-run breadcrumb convention the loop reads/writes each tick: `references/cycle-convention.md`.

## Three START actions, then hand off

1. **Interview → generate a NEW `goal.md`.** Ask objective, acceptance signal ("met" = what, concretely), scope fence. Write self-contained `goal.md` (objective + pointer to `harness/rules/` + explicit acceptance) — loop is rules-blind mid-run, everything needed must live in that file. Do not edit an existing `goal.md`; author fresh.

2. **Arm `hs:autonomous-bell`** with a **run tag** (cron id / goal run id) — the deterministic stop substrate, its backlog query scoped to that tag. Backlog items added during the run carry `source_ref: <run-tag>` so the bell's run-scoped query (`autonomy_bell.py --backlog-signal --source-ref
   <run-tag>`) sees only THIS run's open work — never a global open item.

3. **Scaffold the cycle dir.** The built-in host writes `goal.md` to `goals/<goal_name>/goal.md` (relative to launch cwd). Put cycle memory in that SAME dir: `goals/<goal_name>/cycle_N.md`, beside the host's `goal.md`, so each tick drops a breadcrumb (## Done / ## Next / ## Blocker /
   ## Decisions) the next tick reads. The whole `goals/` tree is gitignored, ephemeral per-run — never commit it. Shape + protocol: `references/cycle-convention.md`.

Then **hand the loop to built-in `/goal iterate-until-met`** and stop. `hs:goal` owns no iteration code — the built-in engine drives the loop, the bell decides when to stop, cycle breadcrumbs carry memory across ticks.

## Boundaries

- Do NOT reimplement the `/goal` iteration engine — it is built-in, not editable.
- Do NOT edit an existing `goal.md` (ephemeral per-run, never a durable target). Always author a NEW one.
- Cycle-memory is intra-run only (the goal dir is ephemeral) — not cross-run.
- This is for UNATTENDED runs; interactively the operator is the stop signal.
- Shared autonomous safety posture (loop/afk/goal group):
  `../loop/references/safety-guardrails.md` — bake the relevant rules into the generated goal.md (atomic commit, verify-or-rollback, no push/ship in-loop).

## Related skills

- `hs:autonomous-bell`: the stop substrate this skill arms.

## Auto-decision ledger

When acting autonomously (editing or deciding without asking), append one advisory line per governance-bearing decision — see `"${HARNESS_BIN_ROOT:-.}"/harness/rules/auto-decision-ledger.md`.
