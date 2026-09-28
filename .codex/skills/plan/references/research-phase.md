# Research phase — multi-source gathering before design (on-demand)

Runs in hard mode AFTER scope challenge, BEFORE the planner writes plan.md.
Goal: build sufficient understanding of the problem surface before finalizing a direction — prevent the planner from inventing facts.

Skip when: `--fast`, a researcher report already exists, or the task is <20 words and unambiguous.

## Collection tools

| Tool | When to use |
|---|---|
| Delegate `hs:researcher` agent | Topics requiring web/docs outside the repo — spawn <=2 in parallel, one aspect per agent |
| `hs:sequential-thinking` | Multi-step analysis requiring revision (unclear scope, multiple approaches) |
| `gh` CLI | Read GitHub Actions logs, PRs, and issues directly related to the task |
| `hs:scout` | Locate files/symbols in the repo — preferred for finding real backing |

Do not use a researcher agent for questions answerable by grep/read inside the repo.

## Recipe

1. **Read harness docs first**: `docs/system-architecture.md` + `docs/code-standards.md` — if missing, prompt the user to load them per `"${HARNESS_BIN_ROOT:-.}"/harness/standards/README.md`.
2. **Identify unknowns**: each question that cannot be answered from the repo = one research task.
3. **Spawn researcher** (max 2 in parallel): assign different aspects, max 5 tool calls/agent; wait for completion before synthesizing.
   A fan-out over two agents — or a `--parallel` plan that will drive a wide phase fan-out at cook — routes through `hs:workflow-orchestrate` FIRST
   to size and group the spawn (subagents vs Workflow vs Agent Teams). Hard route: sizing the fan-out is not the same judgment as running it,
   and an ad-hoc spawn skips it.
4. **Synthesize**: write findings to `plans/<slug>/research/` (1 file/researcher); absolute paths for the planner.
5. **Hand off to planner**: pass report paths — planner reads them, does not repeat the research.

## Sufficiency criteria

- >=3 independent sources for important claims; priority: official doc > maintainer post > tutorial.
- Each option is weighed: trade-off, adoption risk, architectural fit with the stack.
- Ends with a **ranked conclusion with reasoning** — not just a list.
- Open questions -> written explicitly at the end of the report, not silently passed over.

## Backing

- `"${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/agents/researcher.md` — agent being delegated to.
- `"${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/agents/planner.md` — receives reports from researcher.
- `"${HARNESS_BIN_ROOT:-.}"/harness/rules/verification-mechanism.md` — Evidence Filter: claims must have a `file:line` or source URL anchor.

