---
name: hs:remember
injectable: false
description: >-
  Capture the session's real knowledge — decisions made, non-obvious facts learned, user feedback — into the
  right durable home (DEC ledger, auto-memory, or BACKLOG) after you approve each entry. Use when you just made
  an architectural decision, learned something non-obvious, got correcting feedback worth keeping, or when the
  decision-capture nudge fires. Pairs with the decision_capture_nudge hook; you approve every entry before it is
  written.
allowed-tools: [Bash, Read, Write, Edit]
argument-hint: "[--since <git-ref>] [hint about what to capture]"
metadata:
  compliance-tier: workflow
---

# hs:remember — explicit knowledge capture

LLM-backed C-leg of memory-v2. Where `decision_capture_nudge` is a deterministic "you shipped a decision-shaped change, ledger didn't move" nudge, this skill does the real judgment — reads the recent session, decides what's worth keeping, proposes durable entries — never auto-writing a decision or gate. Human approves each before it lands.

## When it earns its keep

- A **decision** was made (a choice between approaches, a threshold, a schema, a scope cut) -> record a DEC.
- Something **non-obvious** was learned that the repo does not already encode (a constraint, a gotcha, a verified fact) -> record a memory.
- A **load-bearing term was coined** (a name settled once to replace re-explaining it) and the glossary lacks it -> register it via `glossary_register.py --add` (human-approved; never auto-written).
- The user gave **feedback** on HOW to work (a correction, a confirmed approach) -> record a feedback memory.
- A **failure was diagnosed and could recur** (a bug fixed, missing wiring added, a pattern gotten wrong, anything the user had to point out) -> record a lesson in `harness/LESSONS.md`.
- A learning is **rule-worthy** — a recurring violation a review gate should CATCH, not just a note someone may read -> still record the memory/lesson here, AND propose a **handoff to `hs:rule-author`** to author the enforcement rule (project `docs/standards/*.std.yaml` or shared `harness/rules/`). This skill NEVER writes a rule itself; it only points (see Hard rules).

If none holds, say so and write nothing. Capturing noise is worse than capturing nothing.

## The homes (one fact, one home)

| Kind | Home | Channel |
|---|---|---|
| Architectural decision | `docs/decisions.md` (or the active plan's Validation Log if the register is not yet initialized for this repo) | `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/decision_register.py` |
| Coined load-bearing term | `docs/glossary.yaml` (SSOT; `GLOSSARY.md` is its rendered view) | `glossary_register.py --add` (human-approved — never auto-written) |
| Durable fact / constraint / gotcha | the session auto-memory dir | a memory file + a one-line `MEMORY.md` pointer |
| User-work feedback | the session auto-memory dir | a `feedback`-type memory (with **Why** + **How to apply**) |
| Deferred work | `docs/backlog.yaml` (SSOT; `BACKLOG.md` is its rendered view) | `backlog_register.py add --text … --type … --priority …` (report link in the text) |
| Repeatable failure mode | `harness/LESSONS.md` | one entry: failure → rule → the test/check that catches it (file's own template) |

## Flow (always human-in-the-loop)

1. **Review** — read the recent turns (and the `--since <git-ref>` diff when given) for decisions, learnings, and feedback. Evidence-anchored: each candidate cites a file:line, an ID, a quote, or a concrete change. No fabrication — if you cannot point at evidence, do not propose it.
2. **Classify** — sort each candidate into DEC / memory / feedback / backlog / lesson; confirm not already recorded (search ledger + memory index first; one home per fact — update existing entry, don't duplicate).
3. **Propose** — present candidates as a short numbered list: kind, exact text to write, destination, evidence. Recommend what's worth keeping vs noise.
4. **Approve** — user picks what to write (all / some / none / edited); nothing written before this.
5. **Write** — only the approved entries, each through its channel above. A DEC goes through `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/decision_register.py` (it stamps actor + ts); a memory is a file plus its `MEMORY.md` pointer.

## Flipping a DEC (decision flip) — two tiers

Recording a NEW decision is the Flow above; retiring/replacing an existing one (`--supersedes DEC-n`) is governed — a flip can ripple into rulings the current plan never scoped.

**Tier 1 — inline, per flip (always):**

1. **Scan the blast radius first.** Run `python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/decision_register.py --root . --scan-flip DEC-n` (dry-run, exit-0 JSON: `{neighbors, in_scope, cross_scope}`). Loads only a small neighbour set, never the whole register.
2. `cross_scope` empty → flip directly (`--append-alloc --supersedes DEC-n`); gate WARNs on in-scope neighbours, allows.
3. `cross_scope` non-empty → **AskUserQuestion** (non-technical Vietnamese, an everyday analogy, recommended option first): show cross-scope neighbours, blast radius, trade-off, your recommendation.
On approval, mint confirm token — `python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/decision_confirm.py --root . --confirm --target DEC-n --neighbors <cross_scope ids>` — then run flip; gate
   finds token, consumes it, allows. On refusal, do NOT flip.
4. The gate is an analytical script — signals a block on the **stdout key `cross_scope_block`**, not via `$?`. Branch on that key.

**Tier 2 — periodic reconcile (by trigger):** when `decision_reconcile_nudge` fires (or on request), propose spawning the `@decision-reconciler` agent. Sweeps the whole register for semantic contradictions + DEC↔code drift, FLAGS flips; each flagged flip comes back through the Tier-1 flow above (scan → ask → confirm). The agent never mints a token, never edits the SSOT.

**Say the limit plainly (do not oversell):** the real floor is (a) `write_guard` blocking a direct tool-edit of `decisions.yaml`, and (b) the CLI refusing the write on an unconfirmed cross-scope flip (SSOT stays unchanged). The confirm token is
**tamper-evident + raise-the-price, NOT authentication** — an agent can mint its own; the genuine gate is the AskUserQuestion approval here. exit-2 only binds a caller that checks it.

## Hard rules

- **Never auto-write a DEC or touch a gate-config file.** This skill proposes; human approves; register writes. A gate-enforcing file (`stage-policy`, `ownership`, guard list, hook) is never edited here — human-placed.
- **No dev-id labels in shipped artifacts** — DEC / plan IDs live in ledger and register tooling, never leaking into code comments, test names, or commits.
- **Evidence is never invented, never translated** — file:line / IDs / SHAs / quotes copied verbatim.
- Render reports per `"${HARNESS_BIN_ROOT:-.}"/harness/rules/output-rendering.md`: resolve `language` / `audience` / `humanize` live via `python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/output_config.py --resolved` (never hand-read the tracked file); the rule holds the register behavior and the evidence-invariant fence.

## Pairs with

- `decision_capture_nudge` — the A-leg hook (deterministic, nudge-class, default OFF) that fires the reminder bringing you here.
- `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/memory_gap.py` — fence / parse-gap detector behind the older memory-gap nudge; a different, lower-tier signal.
- `hs:rule-author` — authors ENFORCEMENT rules (project `docs/standards/*.std.yaml` or shared `harness/rules/`). When a captured fact/lesson should become a gate, this skill PROPOSES the handoff; rule-author authors it. remember never edits a rule file — different stakes (blocks work / fires detectors), lifecycle, rigor (a floor needs a detector + a zero-false-positive scan
  first).
