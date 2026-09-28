# Contract-preserving review (warmup-local)

Warmup-only mode. **Does not** change `hs:plan`'s default red-team workflow.

## Intent

Risk findings are evidence and recommendations. They are **not** authority to
redefine user intent or silently reduce scope.

## Finding classes (exclusive)

| Class | Meaning | Plan edit |
|-------|---------|-----------|
| `mitigation-within-contract` | Safer/clearer implementation that preserves every locked outcome and acceptance signal | Allowed |
| `preflight-required` | Needs a readiness check later (cred, tool, access, quota) | Annotate only |
| `blocker` | Prevents Ready until resolved | Annotate; mark not-ready |
| `outcome-change-request` | Would change result, remove must-have, or swap approach outside Allowed substitutions | **No** silent edit; user gate |

## Rubric examples

| Observation | Class |
|-------------|-------|
| Rename helper for clarity; same behavior | `mitigation-within-contract` |
| Deploy phase needs cloud credentials | `preflight-required` or `blocker` if no path without them |
| "Skip E2E to ship faster" when E2E is acceptance signal | `outcome-change-request` |
| "Ship docs only" when feature is in scope | `outcome-change-request` |
| Unknown third-party rate limit | `preflight-required` |

## Hard stop vs default plan red-team

Do **not** invoke `hs:plan`'s red-team stage as a black box. Its default apply
step can apply accepted findings straight to the plan. That path can redefine
scope and is forbidden here.

Allowed patterns:

1. **Local review** under this skill (preferred for most warmups).
2. **Collect-only** adversarial pass: reviewers return findings; **you** classify
   with the taxonomy below **before any plan edit**.

Never apply `outcome-change-request` or `blocker` as plan scope edits.

## Adjudication

1. Collect findings (local review or collect-only adversarial).
2. Classify each; unclassifiable speculation without evidence → non-blocking notes only.
3. Apply only `mitigation-within-contract` edits.
4. Feed `preflight-required` / `blocker` into the Preflight Matrix.
5. On **any** `outcome-change-request` or infeasible locked outcome →
   **Decision required** immediately:
   - present options + consequences via `ask_user`
   - wait for user (do not auto-reject OCR to stay on the happy path)
   - if user changes contract → re-approve contract, then re-plan as needed
   - if user rejects the proposed change → keep contract; continue only if still
     feasible (else Blocked)

## `--fast`

Skip multi-persona adversarial review. Still:

- ensure acceptance signals appear in plan success criteria
- classify any known risks using the same taxonomy
