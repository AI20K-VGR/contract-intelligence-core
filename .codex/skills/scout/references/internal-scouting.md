# Internal scouting — Explore subagents

Use when SCALE ≥ 6 or external tools are unavailable.

## How it works

Spawn multiple `Explore` subagents via the Agent tool, parallel search; each gets one directory/pattern scope, no overlap.

**MANDATORY — pin `model:"haiku"` on every Explore spawn.** Explore inherits the session model (Opus post-CC-2.1.198) — expensive for a Haiku-class search job; every spawn MUST set it explicitly:

```
Agent(subagent_type="Explore", model="haiku",
      description="Scout <area>",
      prompt="<the scope prompt below>")
```

Genuinely need Opus for a search (rare)? Do not silently inherit it and do not route around this via `general-purpose` — write a reasoned override marker first (`"${HARNESS_BIN_ROOT:-.}"/harness/scripts/model_override.py`); the `model_guard` hook enforces the pin (block by default) and consumes that marker.

## Prompt template

```
Quick scout of {DIRECTORY} for files related to: {TARGET}

Instructions:
- Use Glob/Grep to find files by pattern
- List found files with a short description
- Timeout: 3 minutes max — stop if time runs out

Result format:
## Files found
- `path/to/file` — description

## Observed patterns
- Notable points
```

## Partitioning strategy

Divide along the repo's logical boundaries:

```
harness/hooks/     → hook implementations
harness/scripts/   → analytical + gate scripts
harness/rules/     → rule layer
harness/schemas/   → JSON schemas
harness/plugins/   → skill/agent plugins
harness/tests/     → test suite
harness/e2e/       → end-to-end tests
docs/              → documentation
plans/             → plans + reports
```

Adjust to actual repo structure.

## Reading file content (chunking)

When file content must be read (not just paths):

```bash
# Step 1: measure file length
wc -l path/to/file1.py path/to/file2.py

# Step 2: compute chunks (target 500 lines/chunk)
# chunks = ceil(total_lines / 500)
```

| File size | Strategy |
|---|---|
| < 500 lines | Read in full (1 agent) |
| 500-1500 lines | Split into 2-3 chunks (offset/limit) |
| > 1500 lines | `ceil(lines/500)` chunks |

Spawn all chunk agents in a single message → true parallelism.

## Merging results

1. Deduplicate file paths
2. Merge descriptions from all agents
3. Record agent timeouts explicitly (do not retry)
4. List open questions
