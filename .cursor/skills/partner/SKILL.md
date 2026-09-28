---
name: hs:partner
injectable: false
description: Delegate an advisory or coding job to the ccs partner lane — a second full-Claude session run by a named provider (minimax/ds/km/gm/...), provenance-stamped (reviewer_engine ccs:<provider>, model+cost from the ccs JSON record). Use when you want a second-brain pass from a different provider before merging, with the delegated call's cost and identity kept separate from Claude's own.
argument-hint: "<verb> --provider <name> -p \"<prompt>\""
allowed-tools: [Bash, Read]
metadata:
  compliance-tier: workflow
---

# hs:partner — the ccs partner lane

Delegate to a **named ccs provider**: `ccs <provider> -p ...` runs a full Claude Code session, proxied to whatever backend that provider profile points at (minimax/ds/km/gm/...).
Unlike the gemini lane: **single-engine by construction** — `ccs` picks the destination once provider named, so no cross-engine fallback here; a down `ccs` degrades LOUD, never silently to a second lane or main Claude.

**Ships OFF** — not on the spine, default install omits it. Run via the off-skill proxy, or turn the lane on in config first.

## Delegation is enforced: spawn the `partner-relayer` subagent (default)

**Every partner call goes through `partner-relayer` — default, not optional.**
Spawn one relayer per call (verb + `--provider <name>` + `-p "<prompt>"`, `--config` passed through) — keeps the delegated session's I/O (file reads, streamed answer, cost) inside the subagent, never flooding main context.
Do NOT invoke `partner_companion.py` from the main thread as the normal path — that throws away the relayer's context isolation, the whole reason the lane exists.

Fall back to a direct in-thread `partner_companion.py` call ONLY when the user explicitly asks for it (e.g. "run it inline"). Absent an explicit request, always delegate.

## Preflight — never call ccs blind

Before any spawn: `command -v ccs` must resolve, and the named provider must be in the **live** discovery list (`partner_preflight.py --check` globs `~/.ccs/*.settings.json`, never reads file contents). `--provider` is **required** on every verb — no default provider, no blind call.

## Config (before anything runs)

Lane is inert until turned on in `"${HARNESS_BIN_ROOT:-.}"/harness/data/partner.yaml`. `master: off` = hard kill-switch. Axes:

- `master` — `on|off` (kill-switch)
- `write` — `read_only | worktree_staged` (advisory verbs never write regardless)
- `allow_live` — `off | on` — the REAL gate for `--live` (see below)
- `secret_scrub` — `warn` (v1 warn-only, never blocks)
- `cost_warn_usd` — per-call warn threshold

Config is **env-bound** — a change needs a session **restart**. `--config <path>` overrides per-invocation with **highest** precedence (`--config` > `$HARNESS_PARTNER` env > shipped tracked file) — read at process start, needs no restart.

## Verbs

```bash
# advisory (read-only) — a proposal/report, never an edit
partner_companion.py review              --provider minimax -p "<what to review>"
partner_companion.py adversarial-review  --provider minimax -p "<what to attack>"
partner_companion.py research            --provider ds      -p "<question>"
partner_companion.py critique            --provider km      -p "<what to critique>"

# delegated coding — default read-only (proposal); --write stages edits in a
# throwaway git worktree and returns a DIFF (the live tree is untouched)
partner_companion.py task --provider minimax -p "<task>"
partner_companion.py task --provider minimax --write -p "<task>"

# apply a staged write to the live tree (gated — see Live write below)
partner_companion.py task --provider minimax --write --live -p "<task>"

# job lifecycle (append-only registry under harness/state/partner/)
partner_companion.py status <job_id>
partner_companion.py result <job_id>

# lane preflight (ccs + live provider discovery)
partner_companion.py preflight
```

Every result carries a provenance stamp (`reviewer_engine: ccs:<provider>`, `reviewer_model`, `cost`) so a partner finding is never mistaken for Claude's or blurred with the gemini lane.

## Write is worktree-staged by default — `--live` is a gated intent flag

`task --write` always stages in a throwaway git worktree and returns a diff; the live tree is never touched by that alone.
`--live` additionally applies the exact captured diff to the live tree, but `--live` is **only ever an intent marker** — the real gate is `allow_live: on` in `partner.yaml` (env-restart bound).
Turning `allow_live` on is the user granting standing authority; main is then delegated to operate live, self-passing `--live` only when the instruction is actually to edit the live tree.
This prose ENCOURAGES asking the human first (AskUserQuestion, in Vietnamese) before a risky live write — that's UX, **not** a security gate; `allow_live` is the gate.

## Egress honesty (read before enabling)

Enabling partner means the delegated full-Claude session can **Read the whole repo plus `~/.ccs/*`** (holds `ANTHROPIC_AUTH_TOKEN`) and egress any of it to an external lab through whatever tools that session has.
`secret_scrub` scans **only the composed prompt string** before send — **blind to the delegated session's own self-read**, so NOT an egress defense; treat as a prompt-level typo-catcher, nothing more.
Real containment: run under a scrubbed `HOME`/env (don't expose real `~/.aws`, `~/.ssh`, `.env` in the delegated session's read range) plus `--add-dir` scoping where ccs supports it.
Stated plainly: an **accepted risk**, not a hidden one — don't market `secret_scrub` as protection it doesn't provide.

## Recursion ban

`ccs` is on `PATH` inside the delegated child session — the delegated model **must NOT call `ccs` itself or invoke a nested partner/gemini skill**. One call per invoke, full stop. A second opinion on the delegated output needs a fresh call FROM main (a new relayer spawn), never one the delegated session makes on its own.

## Cost — post-hoc, not a pre-spend brake

Every result reads `total_cost_usd` straight from the ccs JSON record (never self-computed) and compares it to `cost_warn_usd` — **after** the call already ran and spent money. It's a warning (stderr + `cost_over: true` on the result), not a brake that stops the spend before it happens. No pre-flight cost estimate.

## Ships OFF

Reachable through the off-skill proxy when stashed. Reference companion-owned files with `${CLAUDE_PLUGIN_ROOT}` when the path must survive stash/restore — never a literal dot-claude runtime-install path (CI-banned inside `harness/`).

## Backing (real wiring — not prose)

| Directive | Backing |
|---|---|
| One chokepoint, provider-validate, compose, secret-warn, provenance, cost, loud degrade | `${CLAUDE_PLUGIN_ROOT}/scripts/partner_companion.py` → `partner_call` |
| Config axes + env-bound + `--config` override | `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/partner_config.py` + `"${HARNESS_BIN_ROOT:-.}"/harness/data/partner.yaml` |
| Live provider discovery (never reads settings contents) | `${CLAUDE_PLUGIN_ROOT}/scripts/partner_preflight.py` |
| Single-lane transport (no cross-engine fallback) | `${CLAUDE_PLUGIN_ROOT}/scripts/partner_transport.py` (`CcsPrintTransport`) |
| Per-purpose methodology prompts (load-bearing) | `${CLAUDE_PLUGIN_ROOT}/data/partner-prompt-templates.yaml` |
| Worktree-staged write + `--live` apply gated by `allow_live` | `partner_companion.py` → `_run_staged_write` |
| Context-isolation courier (one call per spawn) | `harness/plugins/hs/agents/partner-relayer.md` |
| Job registry usage lens (count/cost/pass/degrade/latency) | `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/lens_partner.py` |

## Boundaries

- Default invocation is via `partner-relayer`, NOT the main thread (enforced — a direct in-thread call is a fall-back reserved for explicit user request to run inline).
- Advisory results are proposals/reports — Claude applies any code, re-entering every gate. The companion never mutates the live tree outside the gated `--live` apply path.
- The lane is opt-in and default-off; leaving `master: off` makes it a no-op.
- The delegated session never calls `ccs` itself or a nested partner/gemini skill (recursion ban above).

## Related skills

- `hs:use`: run this skill while it ships OFF.
- `hs:insights`: the telemetry lens that reads this lane's job registry.
- `hs:gemini`: the sibling second-engine lane (two-print-transport, cross-engine fallback) — partner is single-engine by construction and speaks only through `ccs`.
- `hs:setup`: turn the lane on / restart after a config change.
