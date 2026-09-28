# When visuals help

This is the decision gate — read before generating any diagram. A visual is justified only when it enables faster understanding than prose.

## Visual HAS VALUE when

| Situation | Appropriate diagram type |
|---|---|
| Multiple components interacting in time order | Sequence diagram |
| Data flowing through multiple layers/services | Data-flow / flowchart |
| Module structure and dependencies | Architecture diagram |
| Before/after change (refactor, migration) | Before-after side-by-side |
| Phases of a plan or workflow | Flowchart with gates |
| Explaining an abstract concept (state machine, lifecycle) | State diagram / flowchart |

## Visual HAS NO VALUE when

- <=2 components -> prose is sufficient.
- Content is simply a list of files/functions -> use a bullet list.
- Change is a single simple logic line -> prose + code snippet.
- Diagram only repeats code without adding abstraction -> skip it.
- Topic not read from real code -> STOP; read code first.

## Decision

```
Are there >=2 COMPLEX interacting components that need explanation?
  No  -> write prose, no diagram needed.
  Yes -> choose a diagram type from the table above -> continue.
```

If unsure -> ask via `AskUserQuestion`:
"I can explain this in plain text. Would you like a diagram as well?"

## Output location rule

- Visual tied to an active plan -> `plans/<slug>/visuals/`
- Standalone visual -> `plans/visuals/`
- Durable architecture visual -> `docs/` (via `hs:docs`)
- Do NOT create anywhere else (CLAUDE.md rule #3).
