# Clarify requirements (clarify phase)

Applied in `--full` and `--fast` before delegating to `hs:plan`.

## Principles

- Ask one question at a time, wait for the answer before asking the next (`AskUserQuestion`).
- Challenge assumptions -- the best solution is often different from the initial idea.
- Stop when confident about: objective, hard constraints, and **out of scope**.

## Core questions (priority order)

1. **Objective**: What problem needs to be solved? Who are the users?
2. **Hard constraints**: Deadline, compute/infrastructure budget, security requirements?
3. **Scope out**: What does NOT need to be done this time?
4. **Integration**: Are there existing systems / APIs / data that must be connected?
5. **Quality**: What is the priority -- ship fast or long-term maintainability?

## When `--fast`

Combine questions into 1-2 rounds instead of sequential. Goal: a `requirement-brief` sufficient for `hs:plan` -- need not be perfect.

## Output of this phase

Requirements summary as bullets (<=20 lines), input for `hs:plan`:

```
Objective: <1 sentence>
Users: <description>
Constraints: <list>
Out of scope: <list>
Open questions: <if any>
```

Do not save a separate file -- pass directly to the `hs:plan` command.
