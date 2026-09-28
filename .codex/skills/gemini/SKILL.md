---
name: hs:gemini
injectable: false
description: Delegate an advisory or coding job to the gemini partner lane (a pure-python print-mode companion) — research, review, adversarial-review, or a worktree-staged code task, with provenance stamped on every result. Use when you want a second-engine pass whose output stays provenance-stamped and separate from Claude's.
argument-hint: "<verb> -p \"<prompt>\""
allowed-tools: [Bash, Read]
metadata:
  compliance-tier: workflow
---

# hs:gemini — the gemini partner lane

Delegate a job to **gemini** (Google's terminal CLI) as an external colleague to Claude. A pure-python companion (`gemini_companion.py`) reaches gemini over **two print transports** behind ONE chokepoint — `gemini -p … -o json` (API key) and `agy -p` (Google OAuth) — picked by the `engine` axis. Both self-spawn, answer on stdout, and EXIT (no resident server to deadlock). The chokepoint
resolves the model, stamps provenance, warns on secrets, and degrades loudly (with a cross-engine fallback under `auto`), never silently to Claude. No Node, no MCP server — just a normal CLI call.

**This skill ships OFF.** Off-spine; default install omits it. Run it through the off-skill proxy, or turn the lane on in its config first.

## Delegation is enforced: spawn the `gemini-relayer` subagent (default)

**Every gemini call goes through the `gemini-relayer` subagent — this is the default, not an option.** Spawn one relayer per call (verb + `-p "<prompt>"`, `--engine`/`--config` passed through) so gemini's I/O — its file reads, its streamed answer, its token stats — stays inside the subagent and never floods the main context. Do NOT invoke `gemini_companion.py` from the main thread as the
normal path: that throws away the relayer's context isolation and the whole reason the lane exists.

**Fall back to a direct in-thread `gemini_companion.py` call ONLY when the user explicitly asks for it** (e.g. "run it inline", "don't spawn a subagent"). Absent explicit request, always delegate — even for a quick `setup`/`status`/`result` check. When in doubt, spawn the relayer.

## Config (before anything runs)

The lane is inert until turned on in `"${HARNESS_BIN_ROOT:-.}"/harness/data/gemini-partner.yaml` (or a dev override via `$HARNESS_GEMINI_PARTNER`). `master: off` is a hard kill-switch: every path inert. The four axes:

- `master` — `on|off` (kill-switch)
- `mode` — `partner` (hand-picked calls) | `route-all` (advisory fan-out defaults to gemini)
- `write` — `read_only` (proposals only) | `sandbox_write` (worktree-staged edits, **both engines**)
- `stop_review_gate` — `off | advisory | enforce`
- `engine` — `gemini-print | agy-print | auto` (the transport lane — see **Two engines** below)

The config is **env-bound**: a change needs a session **restart** to take effect (same discipline as the guard policy). Model ids are never hand-written — a purpose maps to a tier resolved against the model SSOT.

**Per-invocation override (`--config`, no restart).** The companion takes `--config <path>` with the **highest** precedence: `--config` > `$HARNESS_GEMINI_PARTNER` > shipped tracked file. Unlike the env var, it's read at process start — no restart needed. To run a `master: off` lane from a dev-enabled config WITHOUT editing the tracked file, pass
`--config <dev-on.yaml>` — and carry it **through the relayer** (`gemini_companion.py <verb> --config <path> -p …`). Do NOT invoke the companion directly to dodge an inert lane — that discards the relayer's context isolation.

## Two engines (the diagonal — engine+transport+auth, resolved together)

The lane speaks to gemini through **two print transports**, picked by the `engine` axis:

- **`gemini-print`** — `gemini -p … -o json` print mode. Auth: **`GEMINI_API_KEY`**. Advisory **and** the worktree-staged write path (`--approval-mode yolo`). Reports token stats (`stats.models.<model>.tokens`).
- **`agy-print`** — `agy -p` one-shot print mode. Auth: **Google OAuth** (browser login, no key). Advisory **and** write (re-probed: agy lands files when the write-target is an absolute path in the prompt — agy ignores cwd — and `SSH_*` is stripped from its env). Token stats are `n/a`. Multi-round recall works (conversation-id).
- **`auto`** (default) — detect the credential present: `GEMINI_API_KEY` → gemini-print, else agy-print. Under `auto`, a down engine **falls back** to the other (loud, stamped in `provenance.attempts[]`) — never to Claude. A **pinned** engine, the
  **write path**, and a **mid-conversation** call never fall back.

Pin per call with `--engine gemini-print|agy-print` (CLI verb + relayer passthrough); a pin disables fallback. Every result stamps the winning diagonal: `engine` (`gemini|agy`), `transport` (`print`), `auth` (`apikey|oauth`), plus `attempts[]`.
**agy's OAuth session expires (~1h)** — a mid-session expiry degrades loudly; `setup` canaries each engine and prints how to log in.

## Verbs

```bash
# advisory (read-only, mode=plan) — a proposal/report, never an edit
gemini_companion.py review              -p "<what to review>"
gemini_companion.py adversarial-review  -p "<what to attack>"
gemini_companion.py research            -p "<question>"

# pin the engine on any verb (disables cross-engine fallback)
gemini_companion.py review --engine agy-print -p "<what to review>"

# delegated coding — default read-only (proposal); --write stages edits in a
# throwaway git worktree and returns a DIFF for Claude to apply (never touches
# the live tree itself). Requires write: sandbox_write in config. BOTH engines
# write (gemini via yolo, agy via an absolute write-target in the prompt).
gemini_companion.py task -p "<task>"
gemini_companion.py task --write -p "<task>"

# job lifecycle (append-only registry under harness/state/gemini/)
gemini_companion.py status <job_id>
gemini_companion.py result <job_id>
gemini_companion.py cancel <job_id>

# lane preflight (config + canary)
gemini_companion.py setup
```

Every result carries a provenance stamp (`reviewer_engine`, `reviewer_model`) so a gemini finding is never mistaken for Claude's.

Each verb runs gemini under a **methodology template** (role + flow + output contract) distilled from the harness's own advisory agents, so gemini plays the role with Claude-level rigor — not a thin persona. The chokepoint injects it by purpose; you pass only the task.

## Feeding gemini files — it self-reads, do NOT inline

`gemini -p` print mode is a full headless agent with its own file tools. **Verified by probe (2026-07-09):** told to read an absolute file path with no inlining, it used one tool call and returned the exact content. So when a task needs file context,
**name the folder/file PATHS in the prompt and tell gemini to read them itself** — never paste file bodies into `-p`. Inlining a 50 KB file costs ~40 K input tokens for content gemini would read from disk for free — defeating the whole point of the relayer (context isolation + token thrift).

Frame the prompt as *"read `<path>` yourself with your tools"* and hand gemini exact paths rather than expecting it to search the tree (grep/ripgrep may be degraded — a startup banner warns of the ripgrep fallback).

**A slow or timed-out call is NOT proof the environment is blocking the engine — probe the real cause before you blame it.** Path-based self-read is fast and works: an engine told to read a path uses its own file tool and returns. When a call actually hangs or times out, diagnose the real culprit instead of guessing: (a) a broken env — a scrubbed `HOME`/config leaves the engine with no
credentials and it waits on auth; (b) a prompt so large it exceeds `ARG_MAX` or bloats context; (c) a genuinely slow model tier. If you suspect a local tool-call hook, **run that hook standalone and time it** — a hook you never exercised is a hypothesis, not a cause. Do NOT declare an "environmental blocker" and fall back to inlining the file (the exact token waste this section exists to
prevent). The lane reports `degraded` loudly when it truly cannot proceed — trust that signal, not an unverified guess.

## Backing (real wiring — not prose)

| Directive | Backing |
|---|---|
| One chokepoint, model-resolve, provenance, secret-warn, loud degrade + cross-engine fallback | `"${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/scripts/gemini_companion.py` → `partner_call` |
| Config axes + forbidden-state (S1/S6/S7) + engine axis + auto-detect | `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/gemini_partner_config.py` + `"${HARNESS_BIN_ROOT:-.}"/harness/data/gemini-partner.yaml` |
| Per-purpose methodology prompts (load-bearing) | `"${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/data/gemini-prompt-templates.yaml` |
| Transport seam (GeminiPrintTransport + PrintTransport behind the chokepoint) | `"${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/scripts/gemini_transport.py` |
| Stop-review gate (fail-open, default OFF) | `harness/hooks/gemini_stop_review_gate.py` |
| Model SSOT (no hardcoded ids) | `"${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/data/models.yaml` via `resolve_model.py` |

## Warnings (read before enabling route-all or write)

- **route-all sends your repo context to Google.** Secret-scan is v1 **warn-only** — it flags likely credentials on stderr but does NOT block or redact. Turn route-all on only where that data flow is acceptable.
- **Env is inherited in full** by the `gemini -p` / `agy -p` process — credentials in your shell are readable by the engine's own tools. A conscious, accepted risk. (Exception: `SSH_*` is stripped from the agy env — it breaks agy's file-token auth.)
- **agy runs on Google OAuth (browser login), no API key.** The session **expires (~1h)**; a mid-session expiry degrades loudly (never a silent Claude fallback). `setup` canaries agy and, if logged out, tells you to run `agy` once to re-auth.
- **sandbox_write is not an OS sandbox.** It stages edits in a git worktree and returns a diff to gate; a yolo engine could still escape its cwd. It blocks accidents and gives a diff to review — not adversarial containment. **Both engines write** (gemini via `--approval-mode yolo` in cwd; agy via an absolute write-target in the prompt). A write that produces an EMPTY worktree diff RAISES
  (never a silent "done") — it catches an agy write that landed in scratch OUTSIDE the repo, where the escape-scan is blind.
- Background + write is refused; advisory purposes cannot write; route-all with sandbox_write is refused at config load.

## Loop (Claude-driven)

To run gemini for **many rounds until a bar is met**, Claude holds each round: spawn a `gemini-relayer` (one call), score, then spawn a FRESH relayer with the delta — never a Stop-hook, never a gemini self-drive. Three modes: **converge** (no new `file:line` finding), **target** (a mechanical metric Claude measures), **judge** (a Claude-per-task criterion). The `loop.max_rounds` cap (default
3) is model-honored.
Full pattern: `references/loop-pattern.md`.

## Boundaries

- **Default invocation is via the `gemini-relayer` subagent, NOT the main thread** (enforced — see the callout near the top; a direct in-thread `gemini_companion.py` call is a fall-back reserved for when the user **explicitly** asks to run inline).
- Advisory results are proposals/reports — Claude applies any code, re-entering every gate. The companion never mutates the live tree.
- The lane is opt-in and default-off; leaving `master: off` makes it a no-op.
- The loop is a pattern Claude executes by hand — never wired to a hook.

## Quick reference

| Content | Drawer |
|---|---|
| Structured review output (finding + provenance schema) | `references/review-output-schema.json` |
| Claude-driven multi-round loop (3 modes + cap) | `references/loop-pattern.md` |
| Per-purpose role/methodology prompts (companion-owned) | `"${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/data/gemini-prompt-templates.yaml` |

## Related skills

- `hs:use`: run this skill while it ships OFF.
- `hs:insights`: the telemetry lens that reads this lane's job registry.
- `hs:setup`: turn the lane on / restart after a config change.
