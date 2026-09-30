# Red-team report — Failure Mode Analyst

Plan under review: `plans/260929-2323-ai2-b-versioned-service/plan.md` and all four phase files. Review lens: timeout, abandoned work, concurrency, and recovery. One suspected failure mode is retained with its uncertainty stated.

| ID | Severity | Status | Anchor | Scenario | Cheapest fix |
|---|---|---|---|---|---|
| FM-1 | H | [ASSUMED] | P2 `phases/phase-2-llm-enablement.md:20,43,45,57`; B plan `plan.md:236-237` | A provider call that trickles past the `future.result(timeout)` deadline can keep running after the request falls back; if the permit is released on timeout, repeated requests can exceed the intended four in-flight provider calls, while retaining it until a never-finishing worker exits can permanently consume all four slots. | Specify permit ownership through actual worker completion, a bounded executor/transport lifetime and recovery policy; add a test with a call that remains blocked after the HTTP deadline, then prove both provider-call count stays bounded and capacity recovers (or the process is deliberately recycled). |

## Irreversible paths

A provider call that outlives the caller can still consume billable tokens after the user has received a deterministic fallback. The plan recognizes abandoned-thread risk and a four-slot semaphore (`plan.md:237`) but does not define when that slot is released or how a stuck call terminates (`phase-2-llm-enablement.md:20,43,45`). This is suspected because the guard/executor is new work and its implementation is not present yet.

## Residual risks accepted with condition

The four in-flight cap is a useful bound only if the phase proves the lifetime and release semantics above. No locked decision is challenged.
