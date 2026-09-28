# Fixture: --fast refused — external dependency signals

## Input

```text
/hs:goal-warmup "Deploy staging and verify health" --fast
```

## Estimate

External: deploy + credentials.

## Expected behavior

- MUST refuse `--fast` with reason mentioning external/deploy/credential signals
- MUST continue full path (contract → plan → review → preflight)
- MUST NOT skip preflight or contract approval

## Assertions

- Output contains refuse messaging for `--fast`
- No Ready without final `ask_user` confirm
