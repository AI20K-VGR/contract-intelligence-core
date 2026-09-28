# Harness-aware enrichment (Step 4)

Applies ONLY when the prompt's target is **internal** to this repo. It makes a generated prompt name
**real** local capabilities instead of generic instructions. It is **enrichment, not orchestration**: you never route work, never decide execution, never self-invoke, never run a state-changing command. If the user wants work *run in this session*, the defer boundary below fires first.

---

## Defer boundary (execution-locus, not phrasing)

Decide by WHERE the work runs — never by whether the user said "prompt" or "brief":

- Work to be **executed in THIS session** (build it / fix it / run it here) → **defer**: *"You don't need a prompt for that — run `/hs:plan` (or `/hs:find-skills`); the harness routes it."*
- **Text to paste ELSEWHERE** (another tool, another session, a second engine, or a brief the user will themselves paste into `/hs:plan`) → **write the prompt**.

The discriminator is the destination of execution, so "draft a plan for X to run here" defers while "draft a plan brief I'll paste into /hs:plan" is written — the words don't decide, the locus does.

---

## Discover by SCRIPT/SKILL — never blind-read, never guess

To name a capability you MUST have read its real one-line description first:

- **LIVE skills (name + purpose, OFF ones tagged `[OFF]`):** use **`hs:find-skills`** (or `hs:find-skills --list`). This is the only surface that returns live-skill descriptions.
- **OFF/omitted skills only:** `python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/disabled_skills.py --list` (optionally `--filter <kw>`). Note: this lists ONLY disabled skills — LIVE skills never appear here.
- **Verify one skill's state before naming an invoke:** `python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/disabled_skills.py --status <name>` → `live` | `disabled` | `unknown`.
- **Subagents:** name a real `agent_type` from the Task roster.

## Guards (hard)

- **No real description → no name.** Only name a capability whose real one-line description you just read (from `hs:find-skills`). If you cannot quote one, the capability does not exist for you — fall back to a plain external prompt and say why.
- **Status-verify.** `live` → the prompt may say `/hs:<name>`. `disabled` → the prompt may *quote* "exists but OFF — enable with `hs-cli skills --on <name>` or run through `/hs:use <name>`", but you MUST NOT run that command. `unknown` → do not mention it.
- **Never self-invoke, never execute.** You write the prompt that names the capability; you do not run it, and you never execute an enable/install/mutating command via Bash.

---

## Internal targets

| Target | The prompt is for… | Note |
|---|---|---|
| Task subagent | a brief handed to a real `agent_type` | driving agent spawns it, not you |
| gemini lane | a job the user hands to the gemini partner (`hs:gemini`, ships OFF) | if OFF, advise enabling — do not run it |
| `/hs:plan` brief | a task brief the user pastes into `/hs:plan` | write the brief; you do not run plan |
| Another Claude+harness session | a prompt another session will run | plain enrichment |
| `./orchestrator` | **future** target only — not wired to skills yet | advisory mention; never a live invoke |

## YAML examples (structured — copy the shape, fill from live discovery)

```yaml
# 1) A prompt to hand a review job to the gemini partner (text to paste → write it)
example: gemini-delegate
user_says: "write me a prompt to get gemini to red-team this auth module"
discover: "disabled_skills.py --status gemini  → live|disabled (if disabled: advise enable, don't run)"
emit_prompt_shape: |
  Review src/auth/** as an adversarial red-teamer. Find the failure mode the happy
  path missed. Per finding: concrete failure scenario (inputs→wrong outcome) + fix.
  Rank by severity. Findings only, no preamble.
route_line: "Route: gemini partner lane — matched: <real one-line purpose from hs:find-skills>"

# 2) A brief the USER will paste into /hs:plan (text to paste elsewhere → write it)
example: plan-brief
user_says: "give me a brief I can drop into /hs:plan to add rate-limiting"
locus: "user pastes it into /hs:plan themselves → paste-elsewhere → write"
discover: "hs:find-skills  → name any real skill the brief should mention"
emit_prompt_shape: |
  Objective: add token-bucket rate-limiting to POST /api/*.
  Context: [stack], current middleware chain. Target: limiter + tests; 429 on breach.
  Scope: src/middleware/** only. Acceptance: [ ] unit tests [ ] 429 verified [ ] no regression.
handoff_note: "Paste into /hs:plan."

# 3) DEFER — user wants the work RUN here, not a prompt
example: defer
user_says: "add dark mode to the settings page"   # execution locus = this session
action: 'Reply: "You don''t need a prompt for that — run /hs:plan (or /hs:find-skills)."'
```

---

## The line you never cross

Enrichment = the prompt *mentions* a real capability so a human (or another session) can use it. Orchestration = deciding and executing routing yourself. `hs:prompt` does the first, never the second. When in doubt about execution-locus, defer to `/hs:plan`.
