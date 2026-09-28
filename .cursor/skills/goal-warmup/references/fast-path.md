# Fast path (`--fast`)

## Eligibility (all required)

1. User passed `--fast` **and** accepts reduced assurance when prompted.
2. Scout/estimate finds **no** indicators of:
   - external credentials or third-party API keys
   - deploy/release/publish steps
   - human approval gates (merge to protected branch, production change)
   - multi-service / multi-environment work
3. Task looks **local-only** (small file surface, no network product dependencies).

If any check fails → **refuse** `--fast` with a one-line reason and continue the
full path (contract → plan → review → preflight).

## What `--fast` may skip

- Expensive adversarial multi-reviewer red-team

## What `--fast` must still do

- Outcome Contract approval (hard gate)
- Plan with contract traceability (can be thin)
- Lightweight consistency check: locked acceptance signals still present
- Preflight matrix over all phases (cheap portable checks)
- Explicit Ready / Blocked / Decision terminal state
- Never auto-start the long run

## Messaging

When refusing:

```text
--fast refused: <reason>. Continuing full warmup.
```

When accepting:

```text
--fast active: reduced adversarial review. Contract + preflight still required.
```
