# Red-team report — Security Adversary

Plan under review: `plans/260929-2323-ai2-b-versioned-service/plan.md` and all four phase files. Review lens: error-data egress across mixed-version deploys and rollback. One finding survived the evidence filter.

| ID | Severity | Status | Anchor | Scenario | Cheapest fix |
|---|---|---|---|---|---|
| SEC-1 | H | proven | `backend/src/contract_intelligence/infrastructure/ai_adapters.py:84-91`; B plan `plan.md:84-85`; P1 `phases/phase-1-versioned-contracts.md:18-20,65-68,94-98` | If an older AI2 instance returns an error body containing a contract value during the supported N/N-1 window or rollback, Backend logs and raises the first 500 bytes verbatim; P1 sanitizes AI2's new error producers but omits this Backend sink from its change inventory, so the leak survives that rollout path. | Normalize upstream error responses in the Backend adapter before logging/persisting (allow-list code/status; never retain raw body), and add a canary test using an old-format AI2 error through adapter and worker logging paths. |

## Irreversible paths

SEC-1 is a data disclosure into durable or centrally collected logs; deletion after collection cannot reliably retract copies. The current raw-body sink is directly observable at `ai_adapters.py:84-91`; P1 identifies Backend logging/storage as an existing risk at `plan.md:84-85`, but its sanitize implementation is scoped to AI2 producers at `phase-1-versioned-contracts.md:65-68`.

## Residual risks accepted with condition

None in this lens. This report does not reopen any locked product or architecture decision.
