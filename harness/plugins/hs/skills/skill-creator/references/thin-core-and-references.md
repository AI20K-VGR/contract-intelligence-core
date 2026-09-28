# Thin-core and references — skill content structure

## Core principles

**Backing-or-cut (hard):** every directive in SKILL.md must point to real backing. No backing -> cut from the thin-core (move to references as advisory or drop entirely).

**Progressive disclosure:**
1. Description (<=512 chars) — always in context
2. SKILL.md body (<=15,000 chars, ~3,750 tokens) — loaded when the skill activates
3. references/ drawers — only loaded when needed

## Valid backing types

| Type | Path | Example |
|---|---|---|
| Gate hook | `harness/hooks/<name>.py` | `gate_stage.py`, `artifact_check.py` |
| Script | `harness/scripts/<name>.py` | `catalog.py`, `decision_register.py` |
| Rule | `harness/rules/<name>.md` | `tdd-discipline.md`, `verification-mechanism.md` |
| Schema | `harness/schemas/<name>.json` | artifact schemas |
| Policy | `harness/data/<name>.yaml` | `stage-policy.yaml` |

When referencing backing in SKILL.md: use the **filename** (not a `.claude/` path).

## Thin-core <=15,000 chars — required blocks

### 1. Boundaries
```markdown
## Boundaries
- Do NOT do X — when to stop
- When Y occurs -> ask the user via AskUserQuestion
- On completion: return [specific artifact]
```

### 2. Wiring block
```markdown
## HARD-GATE (real wiring)
<gate/script name> blocks/checks <condition> — points to a real target, not phantom.
```
If the skill has no gate -> use a "Backing" block instead of "HARD-GATE".

### 3. Modes / Flags (if applicable)
```markdown
## Modes
| Mode | When | Gates |
|---|---|---|
| fast | ... | skip X |
| hard | ... | X -> Y -> Z |
```

### 4. Process
- Numbered steps, each step <=3 lines
- Details -> "load `references/<drawer>.md`"
- Do not repeat content already in references

### 5. Quick reference table
```markdown
## Quick reference
| Content | Drawer |
|---|---|
| Topic A | `references/topic-a.md` |
```

## Backing-or-cut — quick decision

```
Directive X ->
  Has gate/script/rule in harness? -> KEEP, point to backing name
  No backing, important?           -> OPEN references drawer (advisory)
  No backing, not important?       -> CUT
```

## Surfacing load-bearing directives

Progressive disclosure decides WHERE detail lives; it does NOT decide where the load-bearing
RULE lives. A rule the reader must act on stays in the thin-core, header-visible, near the top —
burying it in a drawer (loaded on demand) or at the tail of the longest step is how it gets
skipped in practice. Observed failure: a `mode: hard` "delegate plan-writing to `@planner`"
mandate parked as one bold sentence at the bottom of a 22-line step got read past; the same
mandate as a top "Who does what" table did not.

**What counts as load-bearing** (must be surfaced, not buried):
- **Who does the work** — main vs a `@subagent`. Put it in a table/section BEFORE the numbered
  Steps. List what is held at main (anything calling `AskUserQuestion` — a subagent has no TTY)
  vs what each named agent gets.
- **A mandate that out-ranks the ambient output style** — the Proactive/autonomous style pushes
  "act now, inline"; a delegate-by-default mandate out-ranks it. State the precedence in words;
  do not rely on the reader to arbitrate a silent conflict.
- **A STOP / gate / irreversible checkpoint** — its own header, not a mid-paragraph clause.

**Flag/hint parity (mechanical):** every `--flag` that appears in the body must be declared in
`argument-hint`. An orphan flag reads as undocumented.
```bash
# grep the body for flag tokens, eyeball against argument-hint
grep -oE '`--[a-z-]+`' SKILL.md | sort -u
```

**One term one meaning:** within a short span, do not overload a word (e.g. "inline" meaning
self-verify AND don't-delegate AND no-spawn) — pick distinct words per meaning.

**Pre-ship checklist** (run before reporting a skill/edit DONE):
1. Does every delegation have a home the reader hits BEFORE the Steps (table or top section)?
2. Is any style-conflicting mandate marked as out-ranking the style, in words?
3. `grep` body flags == `argument-hint` flags? (no orphan)
4. Any term carrying >1 meaning in one span?
5. Is any must-act rule living ONLY in a `references/` drawer? → pull a one-line pointer into the thin-core.

Models to copy: `hs:plan` §"Who does what — main vs subagent"; `hs:cook` §"Per-phase implement
(3.I): delegate to `@developer` … STOP before coding inline" + its "output style does NOT waive
this … out-ranks it" sentence.

## References drawers — when to split

Split into `references/<topic>.md` when:
- Details exceed 10 lines for one topic
- Content is only needed in one branch of the workflow (not every time)
- Schemas, checklists, or full examples

Each file <=15,000 chars, every line <=400 chars. Filename: kebab-case, self-documenting.

## Example of correct separation

```
SKILL.md (thin-core):
  "Identify backing -> load references/thin-core-and-references.md"

references/thin-core-and-references.md:
  Backing types table, decision process, full examples  <- this file
```

Do not put the full backing types table in SKILL.md — too heavy for a thin-core.
