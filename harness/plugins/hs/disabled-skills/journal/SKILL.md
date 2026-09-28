---
name: hs:journal
injectable: false
description: Write a technical journal entry — record decisions, failures, and lessons learned after each session. Use after hs:ship, hs:cook, hs:fix, or when an incident needs honest documentation.
allowed-tools: [Read, Write, Task]
argument-hint: "[topic or reflection]"
metadata:
  compliance-tier: workflow
---

# hs:journal — technical journal

Write an honest technical journal entry to `plans/journals/` via `@journal-writer` agent. Do **NOT** write code; do **NOT** create markdown outside `plans/journals/` or `plans/` (CLAUDE.md rule #3).

A journal entry is not a ticket: write truthfully, including emotions; do not soften failures.

The journal is session **history** — a record of what happened and what was decided. It is **not** where a decision is made: a durable decision belongs in the DEC ledger (`docs/decisions.md`, recorded via `hs:remember` / `decision_register.py`). Capture that a decision was made and why; do not treat the entry as that decision's authority.

## When to use

| Situation | Example |
|---|---|
| After ship / implement | session reflection, decisions that were finalized |
| After bug fix | root cause + lessons learned |
| Active incident | repeated test failures, migration crash, vulnerability found |
| Architecture change | initial direction was wrong; record why |

No argument: `AskUserQuestion` — ask the journal topic.

## Process

1. **Parse argument** — identify the topic; if missing, ask the user.
2. **Delegate to journal-writer** — spawn `@journal-writer` with context: topic, path `plans/journals/`, requirement for honesty + specific technical detail.
3. **Entry structure** — agent follows format in `references/entry-format.md`; file named `YYYY-MM-DD-<slug>.md` in `plans/journals/`.
4. **Verify** — after agent completes: confirm file actually exists and is not empty.

Entry format details: `references/entry-format.md`. When to write: `references/when-to-journal.md`.

## Agent wiring

```
journal-writer (harness/plugins/hs/agents/journal-writer.md)
  └── writes file → plans/journals/YYYY-MM-DD-<slug>.md
```

The `@journal-writer` agent uses model `haiku` — lightweight, sufficient for prose reflection. By convention it only creates/edits `plans/journals/` and does not touch harness code.

## Cross-references

- **hs:retro** — analyzes git history data; journal records subjective reflection. Use both after a sprint: retro for metrics, journal for human lessons.
- **hs:ship** — journal immediately after ship to capture last-minute decisions.
- **hs:cook** — journal after implementing when the approach changed mid-stream.

## Boundaries

- Do NOT write code or modify files outside `plans/journals/`.
- Journal does not replace a plan or decision register: it adds the human perspective.
- `@journal-writer` confirms the file was actually created before reporting done.
- On close: return the absolute path of the new entry.

## HARD-GATE (actual wiring)

No dedicated hard gate for journal. However:
- Markdown must reside in `plans/journals/`: creating it elsewhere violates CLAUDE.md rule #3.
