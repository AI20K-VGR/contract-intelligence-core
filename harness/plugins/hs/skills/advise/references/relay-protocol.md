# Relay protocol (hs:advise `--agent` path)

A Claude Code subagent cannot call `AskUserQuestion`. The `advisor` subagent therefore runs the
whole interview in its own isolated context on its pinned model, then **relays** each question
to the orchestrator, which asks the user and re-spawns the advisor with the answer. The
deterministic seam (state I/O, marker emit/parse, question-schema check) lives in
`scripts/advise_relay.py`.

## Main-only constraint (F5)

The relay works **ONLY when the orchestrator is the main session** — only the main session can
call `AskUserQuestion` to inject the relayed question. A nested spawn (a subagent spawning the
advisor) CANNOT relay, because its parent is itself a subagent with no `AskUserQuestion`.

- Use the **main-thread path** (the skill runs `AskUserQuestion` itself) for a short interview
  invoked directly at the main session.
- Use the **relay path** when a long interview would pollute the main context, or a workflow at
  the main session wants the interview isolated on the advisor's model. The value is exactly
  that: heavy interview in an isolated context, main only pumps the question.

## Turn budget >= 2 (F5)

Never spawn the advisor capped at a single turn (`maxTurns: 1`). The advisor must scout
(Read/Grep) FIRST and only THEN emit `NEEDS_USER_INPUT` — that is at least two turns. A
one-turn cap dies at the tool-use boundary and returns an EMPTY envelope (no marker, no
question). Every re-spawn is likewise allowed at least two turns so the advisor can re-read the
state and continue. Pin the budget to `>= 2` turns.

## The loop

1. Pick a state file path (JSON, under the reports directory) and a report path. Neither need
   exist yet.
2. Spawn `advisor` via the `Agent` tool with: the original input and flags, the state file
   path, the report path, and — on re-spawns only — the latest answer as `ANSWER to Q<n>: <text>`.
3. Read the advisor's final message:
   - Starts with `NEEDS_USER_INPUT` — parse the fenced `json` block (`advise_relay.parse_needs_input`)
     and pass it VERBATIM to `AskUserQuestion`. Do not reword the question or invent options.
     Then re-spawn the advisor with the user's answer.
   - Starts with `ADVICE_READY: <path>` — read that report, present the advice, run Step 6
     (emit outputs per flags). Done.
   - Starts with `ADVISE_SKILL_NOT_FOUND` or another error — surface it and stop; do not fake
     advice.
4. Cap the loop at 12 relay rounds; if not `ADVICE_READY` by then, stop and report the partial
   state file path rather than looping forever.

The advisor never spawns the flag subagents; the orchestrator owns Step 6 after `ADVICE_READY`.

## State file schema (`advise_relay` JSON)

`advise_relay.write_state` / `read_state` persist the advisor's working state atomically so a
fresh advisor resumes exactly where the last one paused. Fields:

- `phase` — one of `analyze | scout | interview | confirm | advise`
- `input` — the original prompt or URL, verbatim
- `flags` — e.g. `--agent --md`
- `scout_findings` — a list of bullets, or empty
- `qa_log` — a list of `{q, a}` entries; record every answer before proceeding
- `reframing_draft` — `{problem, requirements, goals, non_goals, constraints}`, filled as they firm up
- `next` — what the advisor intends to ask or do next turn

## Question schema (one per turn)

`advise_relay.emit_needs_input` enforces the shape the orchestrator passes to `AskUserQuestion`:
a `question` string, a `header` (<= 12 chars), a bool `multiSelect`, and 2-4 `options` each with
a `label` and a `description`. Put the recommended option first with `(Recommended)` in its
label. It raises rather than emit a malformed question.

## Finding the skill

The advisor loads the `hs:advise` procedure from its `SKILL.md` in the installed plugin tree —
resolve it with `Glob` on `**/skills/advise/SKILL.md` and read the first match. If none
resolves, report `ADVISE_SKILL_NOT_FOUND` with the paths tried and stop; do not improvise a
different procedure.
