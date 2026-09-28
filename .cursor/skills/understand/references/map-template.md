# Map template — codebase map

Template for hs:understand output. Write to `plans/reports/` (temporary) or `docs/` when `--persist`. Every section must be based on files actually read — do not describe assumed behavior.

---

```markdown
# Codebase Map — <target name / subtree>

Generated: <ISO date>  
Scope: <path or description>  
Map path: <absolute path of this file>

## Module / layer overview

| Layer | Directory / Module | Primary responsibility |
|---|---|---|
| ... | ... | ... |

## File-key + responsibility

<!-- List only files with a distinct role; do not dump the full tree -->

- `/absolute/path/to/file.py` — short description (entrypoint / schema / gate / ...)
- ...

## Data / control flow

<!-- Describe the main data flow or control flow;
     sequential prose or a numbered list both work -->

1. ...
2. ...

## External boundaries

<!-- External APIs, services, user-edited config files, stdin/stdout contracts -->

- ...

## Task entry points

<!-- For typical tasks ("add feature X", "debug Y"), which file to start from -->

| Task | Start at |
|---|---|
| ... | ... |

## Open unknowns

<!-- Questions that could not be answered from the codebase; do not guess — write them out -->

- [ ] ...
```

---

## Filling guide

### Module / layer overview
- Group by function (hooks, scripts, skills, tests, install, data).
- No more than 10 rows — merge small or empty layers.

### File-key
- Only files with a significant role (entrypoint, gate, schema, config) — do not list every file. Use absolute paths.
- If a file has multiple roles: split into 2 lines.

### Data / control flow
- Prefer sequential prose (1 -> 2 -> 3) over a diagram when the flow is linear.
- Describe only flows observed directly from the code — do not speculate.

### External boundaries
- List: user-edited YAML config, external APIs, stdin/stdout, important env vars.

### Unknowns
- Any question without evidence from the codebase -> write it here, do not guess.
- These unknowns become input for hs:plan or hs:research.

## Size check
After writing: `wc -l <map-file>` — if > 300 lines, split subtrees into separate maps or summarize further. An oversized map defeats the purpose of comprehension.
