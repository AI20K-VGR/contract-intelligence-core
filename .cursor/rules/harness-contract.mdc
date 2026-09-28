# Harness contract (always-load, <=75 lines)

**Probe before you build on a guess (load-bearing habit):** a load-bearing assumption that CAN be checked empirically -- check it FIRST by RUNNING the real thing (spike a thin slice / drive the real tool once), before you design or build on it. A doc, `--help`, wiki, grep, or a chain of reasoning is a *hypothesis*, NOT a probe -- never launder it as "probed"/"verified". An unrun claim is `[ASSUMED]` (training knowledge you have not re-checked is `[PRIOR]`), never OBSERVED: label it with its honest type + gate it behind one real-run step, never report "works" from reading or reasoning alone. The four claim labels (OBSERVED / DERIVED / PRIOR / ASSUMED) are defined in `harness/rules/verification-mechanism.md`. Home rule: `harness/rules/agent-operational-discipline.md`.

## Three posture hooks -- HOOK_CLASS constant in code

| Class | Default | On failure | Config-changeable |
|---|---|---|---|
| telemetry | ON | fail-open, silent | enabled |
| nudge | OFF | fail-open, advisory stderr | enabled |
| compliance | **ON + blocking** | **fail-closed exit 2 + reason** | enabled/mode (advisory opt-in) |

`harness/data/harness-hooks.yaml` config CANNOT change the class; it is set in each hook's code.

**Nudge visibility is a separate, config-driven axis** (stderr@exit-0 reaches NOBODY): `hook_runtime.emit_nudge` routes each advisory by name via `harness/data/nudge-channels.yaml`, where visibility is THREE independent boolean flags — `model` (relay-`additionalContext`: record `*_observation`, relayed next turn by `nudge_context_inject`), `user` (human `systemMessage`, `emit/queue_system_message`), and `stderr` (silent unless the model reads it). The four legacy sink names (`systemMessage`/`relay`/`stderr`/`off`) survive only as back-compat sugar mapped onto those flags — no shipped config uses them. A compliance guard is NOT silent -- its exit-2 stderr reaches the model; quiet only on pass. Full map: `docs/system-architecture/03-hook-classes.md` §3.1.

## Declared gate = real wiring (co-presence)

| Gate in prose | Real hook/file |
|---|---|
| Stage gate push/pr/ship/deploy | `harness/hooks/gate_stage.py` + `harness/data/stage-policy.yaml` |
| Pre-push transport | `harness/install/git-pre-push-hook.sh` (installer places this in `.git/hooks/`) |
| Session attribution | `harness/hooks/session_init.py` |

## Three honest truths (do not over-trust what the harness promises)

1. **Gate = presence gate, NOT authentication**: proves a step RAN; pr/ship/deploy
   also require plan-approval — under the personal-first posture this is a SELF-approval
   (plan_hash-bound, sidecar-gated; NO roster, NO quorum, NO reviewer≠author role check —
   `team.yaml`/`roles-policy.yaml` were deleted). It raises the cost of accidental drift, not fraud.
2. **actor = attribution, NOT authentication**: resolved from env
   (CI -> session cache -> HARNESS_USER -> git email -> $USER), spoofable, never
   an authz signal. It answers "recorded as whom", not "proved to be whom".
3. **Gate config is tamper-visible, not tamper-proof**: config can be edited in
   an emergency (tracked in git; diff + trace exposed); `HARNESS_*` env pointing to
   a different config/policy is a known gap (trace names the actual file). Guards
   accidental drift, NOT an insider. fs_guard is a script-path containment helper
   -- it does NOT block raw LLM Write calls; the stage gate only sees
   PreToolUse(Bash), other tools ungated (push still uses pre-push transport); state has no at-rest protection.

## Event-class -> store table

| Event | Store | Retention |
|---|---|---|
| gate_*, session_*, approval, DEC, memory_gap_* | `harness/state/trace/` (JSONL/day) | no rotation |
| usage counters (skill/script) | `harness/state/telemetry/` | rotate at 8MB, 1 generation .bak |
| claim files (acquire/release/reclaim) | `harness/state/claims/` -- RENAME-LIFECYCLE exception: JSON immutable, rename only, audit via trace | tombstone kept, no GC |

Machine-written store: append-only JSONL, no read-modify-write; every record
has actor + ts.

## Autonomy

`HARNESS_AUTONOMY=default|ask_all|god` -- default: hs:cook runs per-phase
autonomously, STOPS to wait for human at plan-approval + ship; ask_all: stops at
every phase; god: does not stop but trace is complete. No level self-ships past
the artifact gate.

## Steering a running subagent (on demand)

A spawned subagent is NOT locked until it finishes. When the user says "cancel /
change / redirect this" about running work -- or you spot a child drifting -- route
it, do not wait or re-spawn: `SendMessage(to:<agentId>)` queues a turn delivered at
the child's NEXT tool-round (its in-flight tool finishes first -- inject, not
preempt; works on a plain background subagent, not only Agent-Teams);
`TaskStop(<agentId>)` halts immediately; a FOREGROUND child needs `Ctrl+B` to
background it first. Default is judge-at-end -- steer only on demand. Steering never
authorizes: a note opens no gate, changes no RBAC, approves no ship.

## Standards are input

`harness/standards/` receives system-architecture + code-standards when the repo is
cloned locally (one clone per dev, shared standards); hs:plan/hs:cook read these
before starting -- if missing, they stop and prompt to load them (details:
`harness/standards/README.md`). On-demand: `harness/rules/{workflow-handoffs,verification-mechanism,tdd-discipline}.md` + the knob index `docs/harness/config-reference.md`; skills hs:plan/cook/test.
