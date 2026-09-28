# Chain orchestration — hs:understand

Orchestrates the 3 component skills + the fan-out scout rules.
Backing: `"${HARNESS_BIN_ROOT:-.}"/harness/rules/orchestration-protocol.md`.

## Call order

```
scope confirmed
    -> hs:repomix   (pack snapshot)
    -> hs:scout     (locate file-key, parallel when SCALE >= 3)
    -> hs:context-engineering  (budget check before synthesis)
    -> synthesize map
    -> hs:docs (optional, only when --persist)
```

Do not reverse the order: repomix must run first so scout knows the scope; context-engineering must run after scout to estimate actual token usage.

## hs:repomix — pack snapshot

Call with:
- `--style markdown` (readable for LLM synthesis)
- `--include "<scope-glob>"` — do not pack the full repo when only a subtree is needed
- `--remove-comments --no-line-numbers` if estimated tokens exceed the budget
- Output: `harness/state/understand-snapshot.<slug>.md` (do not commit)

Feature-detect the CLI first:
```bash
repomix --version 2>/dev/null || echo "MISSING"
```
If CLI is missing -> fallback: read file-key files manually after the scout step; record `[NO_CLI_FALLBACK]` in the map.

Token guard: if the expected snapshot size exceeds 60% of the context budget -> narrow scope or ask via `AskUserQuestion` before running.

## hs:scout — locate file-key

Call `hs:scout` — it self-routes its own fan-out (SCALE thresholds, subagent prompt schema,
   `hs:workflow-orchestrate` routing) per `"${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/scout/SKILL.md`.
   `understand` does NOT re-implement or double-route that fan-out (SKILL.md Backing table: "Parallel exploration
   | delegate to `hs:scout`"). Consume its report path from its own output — do not assume a fixed filename here.

## hs:context-engineering — budget check

Call after obtaining the scout report and snapshot size:
- Provide: token count of the snapshot + number of file-key files to load.
- Receive: strategy (Select / Compress / Isolate) + list of files to load.
- Apply before synthesizing the map — do not load the full snapshot if it exceeds the budget.

Reference thresholds (from hs:context-engineering):
- < 70%: continue normally.
- 70-80%: Select — load only file-key files, not the full snapshot.
- > 80%: Compress or Isolate — synthesize the map through a separate subagent.

## hs:docs — persist (optional)

Call only when `--persist` is passed AND the map is a long-lived document worth keeping. Call mode `update` if the doc already exists, `init` if not.
Backing: `"${HARNESS_BIN_ROOT:-.}"/harness/rules/documentation-management.md`.

Do not persist a temporary map (used once to understand, then plan) — keep temporary maps in `plans/reports/`; do not add noise to `docs/`.

## Subagent status protocol

Require every subagent to end with:
```
Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
Summary: 1-2 sentences
Concerns/Blockers: optional
```

`BLOCKED` / `NEEDS_CONTEXT` -> do not retry with the same prompt; change scope or ask the user. Advisory subagents must not mutate plan/code (read-only).
