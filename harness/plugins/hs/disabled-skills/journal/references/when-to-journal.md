# When to write a journal entry

A guide for deciding: write or skip.

## Write immediately (no hesitation)

- Test suite keeps failing despite multiple fix attempts.
- Serious bug discovered in production or staging.
- Implementation approach proved fundamentally flawed; must start over.
- External dependency (API, library, service) is blocking progress.
- Security vulnerability discovered.
- Database migration failed or caused data integrity loss.
- CI/CD pipeline broke unexpectedly.
- Integration conflict between major components.
- Architecture decision proved wrong in practice.
- Feature took twice as long as estimated, and you know why.

## Write after a session (good to have)

- After `hs:ship` — record last-minute decisions and accepted risks.
- After `hs:cook` — when the approach changed mid-stream relative to the plan.
- After `hs:fix` — when the bug was more complex than expected and the root cause is worth remembering.
- On reaching a significant milestone — record the honest feeling, not just "done".

## No need to write

- Small planned changes with no surprises.
- Typo, format, or cosmetic fixes.
- Routine commits fully described in the plan.

## Journal vs. other tools

| Tool | Records |
|---|---|
| `hs:journal` | Subjective reflection, genuine emotion, human lessons |
| `hs:retro` | Git history analysis, objective metrics, velocity |
| `decision_register.py` | Finalized architecture decisions — prevents re-litigation |
| `BACKLOG.md` | Work to do later, report links, no emotion |

Use journal and retro together after a sprint: retro for numbers, journal for people.
