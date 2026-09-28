# Comparison — drawio vs alternatives

## vs Native agent (no skill)

Without a skill, LLMs can generate draw.io XML but lack the structured review loop, layout guidance, and validation the skill provides.

| Feature | Native agent | This skill |
|---|---|---|
| Generate draw.io XML | Yes | Yes |
| Self-check after export | No | Yes — vision-based, 2-round cap |
| Iterative review loop | No | Yes — targeted edits, 5-round valve |
| Proactive triggers | No | Yes — auto-suggests when 3+ components |
| Layout guidance | None | Complexity-scaled spacing, routing corridors |
| Grid alignment | No | Yes — 10px snap |
| Diagram type presets | No | Yes — 6 presets |
| Visualize codebase | No | Yes — Py/JS/Go/Rust import graphs |
| Auto-layout | No | Yes — Graphviz + ortho routing |
| Structural validation | No | Yes — deterministic .drawio linter |
| Official shape search | No | Yes — 10k+ shapes + OSS catalog |
| AI/LLM brand logos | No | Yes — 321 logos |
| Animated connectors | No | Yes |
| Color palette | Random | 7-color semantic system |
| Edge routing rules | Basic | Entry/exit points, waypoint corridors |
| Container/group patterns | None | Swimlane, group, custom containers |
| Embed diagram in export | No | Yes |
| Browser fallback | No | Yes |
| Auto-launch desktop app | No | Yes |

## Proactive trigger rule

When the user describes a system with **3 or more components** connected in a graph (services, databases, queues, layers), the skill auto-suggests generating a diagram — the user doesn't need to explicitly ask.

## Key advantages

1. **Self-check + iterative loop** — reads its own PNG output, auto-fixes before showing the user
2. **6 diagram type presets** — ERD, UML Class, Sequence, Architecture, ML/Deep Learning, Flowchart
3. **ML/DL model diagrams** — tensor shapes, layer-type color coding
4. **Zero-config** — all scripts are stdlib Python (plus declared optional deps); draw.io desktop is the only external requirement
5. **Production-grade layout** — grid-snapped, complexity-scaled spacing, routing corridors
