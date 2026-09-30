# Red-team report — Bad-day Operator

Plan under review: `plans/260929-2323-ai2-b-versioned-service/plan.md` and all four phase files. Review lens: turning off an incidenting LLM path and proving it is off. One suspected operational gap is retained.

| ID | Severity | Status | Anchor | Scenario | Cheapest fix |
|---|---|---|---|---|---|
| OPS-1 | M | [ASSUMED] | B plan `plan.md:227`; P2 `phases/phase-2-llm-enablement.md:19,40-46` | During an egress incident, the runbook says setting `AI2_LLM_ENABLED=false` and Backend flags is an immediate no-deploy rollback, but the plan defines environment settings and no reload mechanism, propagation delay, restart action, or post-change proof; an operator may believe the kill switch is active while existing processes still use the prior configuration. | State whether settings are dynamically reloaded or startup-bound; give the exact safe change/restart sequence for AI2 and Backend, then a verification command proving the provider receives zero calls before declaring rollback complete. |

## Irreversible paths

If configuration is startup-bound, an environment edit alone does not alter the environment already held by a running process. The claim “immediate without deploy” at `plan.md:227` is therefore unverified by the implementation steps; this is marked [ASSUMED], not asserted as a reproduced production failure.

## Residual risks accepted with condition

The planned kill switches remain appropriate if P2 establishes their activation semantics and a zero-upstream-call verification step. No locked decision is challenged.
