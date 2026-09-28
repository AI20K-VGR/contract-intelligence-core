# Journal entry format

Each file: `plans/journals/YYYY-MM-DD-<slug>.md`
Entry length: 200-500 words. Concise, technical, honest.

> The journal records history, **not** decisions: a durable decision belongs in the DEC ledger (`docs/decisions.md` via `hs:remember`); the entry only notes that the decision was made and why.

## Required structure

```markdown
# [Short title describing the event / problem]

**Date**: YYYY-MM-DD HH:mm  
**Severity**: [Critical / High / Medium / Low]  
**Component**: [System / feature affected]  
**Status**: [In progress / Resolved / Blocked]

## What happened

[Concrete, factual description. No softening.]

## The real truth

[Genuine emotion — frustration, exhaustion, relief. This is a journal, not a ticket.]

## Technical details

[Error messages, metrics, relevant code snippet, stack trace if available.]

## What was tried

[List of solutions attempted and why each failed.]

## Root cause

[Why did this actually happen? Design flaw? Wrong assumption? External dependency?]

## Lessons learned

[A future developer reads this and changes their behavior.]

## Next steps

[What needs to be done, who is responsible, and by when.]
```

## Completion checklist

- [ ] Root cause stated directly: "did not test migration before shipping" rather than "there was an oversight"
- [ ] At least 1 specific technical detail (error, metric, code snippet)
- [ ] Decision recorded: what was chosen, what was dropped, and why
- [ ] Lesson is actionable
- [ ] Genuine emotion present — not sanitized
- [ ] Next steps are actionable

## File naming convention

| Situation | Example filename |
|---|---|
| Post-production bug fix | `2026-06-15-webhook-timeout-root-cause.md` |
| Architecture decision | `2026-06-15-switch-from-polling-to-push.md` |
| Post-ship reflection | `2026-06-15-ship-afk-skill-retrospective.md` |
| Active incident | `2026-06-15-migration-rollback-in-progress.md` |
