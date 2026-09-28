---
name: hs:compound
injectable: true
description: >-
  Compound the harness's own self-knowledge — telemetry lenses + skill-formalization candidates + open backlog +
  a completeness critic — into ONE ranked self-improvement proposal, carried across runs in a durable belief
  store. Use when closing a work cycle to decide what to improve next. Advisory only; never edits
  skills/code/config; maintains only its own append-only belief store; never auto-creates skills. The
  forward-looking twin of hs:insights (descriptive); read-only, proposals only.
argument-hint: "[--days N]"
allowed-tools: [Bash, Read, Write, Glob, Grep]
metadata:
  compliance-tier: workflow
---

# hs:compound — ranked self-improvement proposal

Where `hs:insights` *describes* how the harness is used, `hs:compound` *proposes what to do next*. It compounds four read-only self-knowledge sources into ONE prioritized list, so a periodic run turns accumulated signal into a short, ranked "improve these next" — without ever mutating anything or auto-generating a skill (that autogen step is deliberately deferred — the harness proposes, a
human formalizes; see the self-learning backlog item).

This is the **Mine → Score → Propose** loop adapted from the cowork dream-cycle, stopping at Propose. Draft/autogen is out of scope here by design.

## Flow

1. **Gather telemetry signal** (read-only):

   ```bash
   python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/analyze_telemetry.py --lens all --days 30
   ```

   Read the `## NOT measured` block and each lens's `gated` / `sufficient`. When `gated: true`, the corpus is below the low-volume threshold — report the raw counts but DO NOT derive proposals from them (sparse data is noise). On a single-user/quiet repo most lenses WILL gate; say so plainly.

2. **Pull the formalization candidates.** From the `workflow_chains` lens, read `candidates` (recurring UNDECLARED chains, scored `frequency × steps`). Each is a proposal: declare it in `"${HARNESS_BIN_ROOT:-.}"/harness/data/skill-chains.yaml` or distil it into a skill. Only when the lens is not gated.

3. **Read the open backlog.** Scan `BACKLOG.md` for unchecked `[ ]` / in-progress `[~]` items and the review-coverage notes. These are already-identified work — rank them by leverage, do not re-derive.

4. **Completeness critic** (the part that works even on sparse telemetry): scan for gaps the counters can't see —
   - lenses listed as "not yet shipped" in the `## NOT measured` block;
   - declared chains in `skill-chains.yaml` that never appear in telemetry (stale);
   - skills flagged by `check_skill_structure` (run it if useful);
   - docs/counts that drifted from the tree.

5. **Synthesize ONE ranked list.** Merge 2–4 into a single proposal table ordered by `leverage ÷ effort`, each row: *proposal · evidence (file:line / lens count / backlog id) · why · suggested next action (which tool/skill)*. Cap the list — the top handful, not everything. State what was SUPPRESSED for being gated, so a thin run doesn't read as "nothing to improve."

## Belief store — cross-run memory (`findings_store.py`)

Without this, every run re-derives from zero. The store remembers each proposal as a *belief* whose confidence seeds from its evidence source, decays over time, and rises each time the same idea recurs. It is append-only; confidence is recomputed at read time (replay-on-read). Promotion stays a HUMAN call (Shape A) — the store surfaces candidates, it never formalizes.

- **Step 0 (before gathering)** — read what is already carried, so you rank against memory instead of from scratch:

  ```bash
  python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/findings_store.py --list      # current beliefs (id, text, conf, evidence)
  python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/findings_store.py --promote   # conf>=0.80 & evidence>=3 — surface these first
  ```

  A belief reinforced across many runs is stronger evidence than a fresh single observation — weight it.

- **Step 6 (after the ranked list)** — record each proposal so run N+1 inherits it. The store dedups: an equivalent idea (Jaccard >= 0.85) reinforces the existing belief instead of duplicating it.

  ```bash
  python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/findings_store.py --emit --text "<proposal>" \
      --category <skills|telemetry|gates|docs> --source <telemetry|backlog|critic> \
      --source-ref "<lens count / BACKLOG id / file:line>"
  ```

  `--source` sets the seed confidence (telemetry 0.7 > backlog 0.5 > critic 0.4). Record only proposals that cleared the honesty gate — never emit from gated/low-volume data.

### Routing: belief category → where a human would formalize it

| category | suggested destination |
|---|---|
| `skills` | `harness/plugins/hs/skills/` |
| `telemetry` | `harness/scripts/` (a lens) / `"${HARNESS_BIN_ROOT:-.}"/harness/data/observation-signals.yaml` |
| `gates` | `harness/hooks/` + `"${HARNESS_BIN_ROOT:-.}"/harness/data/stage-policy.yaml` |
| `docs` | `docs/` |

## Boundaries

- NARROW WRITE: the only thing `hs:compound` may write is its OWN append-only belief store (`findings_store.py`, step 0 + 6). It must not edit telemetry, config, code, or skills — it reads `analyze_telemetry.py` output + `BACKLOG.md` / config / tree, and the ranked report plus the belief records are the whole job. (Earlier contract said "never mutates / the report is the whole job"; narrowed
  here so the store can persist, nothing else.)
- NEVER auto-create or auto-edit a skill — that is the deferred Shape-B autogen, gated behind a human review loop. `hs:compound` stops at "here is what I'd formalize, you decide."
- Honesty gate first: a proposal derived from gated/low-volume data is not a proposal. Suppress it and name the suppression.
- Render reports per `"${HARNESS_BIN_ROOT:-.}"/harness/rules/output-rendering.md`: resolve `language` / `audience` / `humanize` live via `python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/output_config.py --resolved` (never hand-read the tracked file); the rule holds the register behavior and the evidence-invariant fence.
- Never present a proposal as a decision already made — `hs:compound` ranks, the human adjudicates.
