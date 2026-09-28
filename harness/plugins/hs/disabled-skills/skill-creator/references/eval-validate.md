# Trigger-eval: does this skill's description earn activation?

Structural checks (`catalog.py`, `check_skill_structure.py`) prove a skill is *well-formed*. They cannot tell you whether the **description actually triggers** when a user describes the task indirectly. `scripts/trigger_eval.py` measures that against a real model.

It runs only when you invoke it by hand during `validate` — never in CI, so the structural router check stays LLM-free.

## How it works

For each query, the runner:

1. Writes a throwaway command file under the project's `.claude/commands/` carrying the candidate description, so the description is visible in the model's catalog.
2. Runs `claude -p <query> --output-format stream-json --include-partial-messages` (with `CLAUDECODE` scrubbed so it can nest inside a Claude Code session).
3. Detects whether the model activated the candidate (a `Skill`/`Read` tool call carrying the skill's unique name) early from partial stream events.
4. Deletes the throwaway command file and reaps the process.

A query "triggers" when its trigger rate (over `--runs`) is at or above `--trigger-threshold` (default 0.5). It **passes** when that matches `should_trigger`.

## Writing an eval-set

A JSON list of `{query, should_trigger}`:

```json
[
  {"query": "I need to map out how to rebuild auth before writing code", "should_trigger": true},
  {"query": "walk me through restructuring this module step by step",     "should_trigger": true},
  {"query": "just fix this one typo in the README",                        "should_trigger": false},
  {"query": "what's the weather today",                                    "should_trigger": false}
]
```

Guidance:

- **Positive queries** (`should_trigger: true`) describe the task *indirectly* — the words a user would actually type, not the skill's own name. If only the literal skill name triggers it, the description is too narrow.
- **Negative queries** (`should_trigger: false`) are adjacent-but-out-of-scope tasks. They guard against an **over-broad** description that grabs everything.
- 4–8 queries is usually enough. More positives than negatives is fine.

## Running it

```bash
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/skill-creator/scripts/trigger_eval.py \
  --skill hs:<name> \
  --description-file <path-to-a-file-holding-the-description-under-test> \
  --eval-set <path-to-eval.json> \
  --runs 3
```

Useful flags: `--num-workers N` (fan out across N parallel `claude -p` processes — default 1, left conservative so a large eval-set does not spawn a swarm), `--timeout S` per query, `--model <id>`, `--project-root <dir>` (defaults to cwd; must hold `.claude/`).

Output is JSON: per-query `trigger_rate` + `pass`, plus a `summary` with `total / passed / failed / pass_rate`.

## Reading the verdict

| Symptom | Meaning | Fix |
|---|---|---|
| positive queries don't trigger (low rate) | description not "pushy" enough / too narrow | widen trigger phrasing → `optimize` mode |
| negative queries trigger (they shouldn't) | description too broad | tighten / add scope boundary → `optimize` mode |
| mixed, near threshold | description ambiguous | sharpen the "Use when…" clause |

When `validate` shows under- or over-trigger, hand the same eval-set to `optimize` (`references/optimize-loop.md`) to iterate the description automatically.

## Honesty note — a low rate is not always a bad description

`claude -p` does **not** reliably route an indirect request to a catalog skill; it often just does the task itself (Bash, direct edits) and never activates anything. So a low trigger rate can mean *the model chose to act directly*, not *the description is weak*. Always read the per-query results, not just the aggregate:

- Positives failing **uniformly across very different phrasings** → more likely a real description weakness.
- Positives failing only on phrasings where the task is trivially doable inline → likely the model-does-it-itself confound, not your description.

Treat the number as one signal among the structural checks and your own judgement — not a gate.
