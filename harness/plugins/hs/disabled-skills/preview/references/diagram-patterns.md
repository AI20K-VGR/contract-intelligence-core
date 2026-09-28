# Diagram patterns

Pick diagram type by content, then use the matching template. All output includes an ASCII fallback (except `--ascii`, ASCII-only).

## Choosing the diagram type

| Content | Type | Mermaid directive |
|---|---|---|
| Processing flow, decision branch | Flowchart | `flowchart LR` / `flowchart TD` |
| Time-ordered interactions between actors | Sequence | `sequenceDiagram` |
| Modules, layers, static dependencies | Architecture | `graph TD` or ASCII box |
| States and transitions | State | `stateDiagram-v2` |
| Before/after change | Before-after | ASCII 2-column or 2 parallel graphs |
| Phase/workflow as a pipeline | Pipeline | `flowchart LR` with gate nodes |

## Templates

### --explain (ASCII + Mermaid + prose)

```markdown
# Visual Explanation: {Topic}

## Overview
[1-2 sentences describing what is being explained]

## Quick diagram (ASCII)
[ASCII box diagram — main components + arrows]

## Detailed flow
[Mermaid fenced block]

## Key concepts
1. **A** — explanation
2. **B** — explanation

## Code example (if applicable)
[short snippet + comment]
```

### --diagram (ASCII + Mermaid)

```markdown
# Diagram: {Topic}

## ASCII
[Box diagram + legend]

## Mermaid
[Mermaid fenced block]
```

### --ascii (terminal-only)

```
[ASCII box diagram]

Legend:
  [A] = ...
  --> = ...
```

### --slides (Markdown slide-outline)

```markdown
# {Topic}

---
## Slide 1: Problem
- bullet
- bullet

---
## Slide 2: Solution
[Mermaid or ASCII]

---
## Slide 3: Conclusion
- bullet
```

## Mermaid rules

- Quote node text containing special characters: `A["text/with/slash"]`
- Escape brackets in labels: `A["array[0]"]`
- Use `flowchart LR` for left-to-right pipelines; `flowchart TD` for hierarchies.
- Maximum ~12 nodes per diagram — split if denser.
- Verify Mermaid syntax by re-reading — common mistakes: arrow through box, overlapping labels, duplicate node ids.

## ASCII rules

- Use `+---+` for boxes, `-->` or `->` for arrows, `|` for pipes.
- Add a legend below when symbols are not self-explanatory.
- Align consistently — misalignment is hard to read in a terminal.

## After creating the diagram

- Re-read output — check arrows clearly show direction, labels unambiguous.
- If diagram is complex (>8 nodes) -> add prose explaining important nodes.
- Save per location rules in `when-visual-helps.md`.
- Durable architecture diagram -> update `docs/` via `hs:docs`.
