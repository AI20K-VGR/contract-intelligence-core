# Visualize — hs:drawio

Two visualization types: (a) codebase import/class-graph and (b) harness skill-graph.

## (a) Codebase import graph and class hierarchy

### Python import graph

```bash
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/drawio/scripts/pyimports.py <root> \
    [--group] [-o graph.json]
# --group: box modules by sub-package (nested containers)
# Output: JSON for autolayout.py
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/drawio/scripts/autolayout.py graph.json -o out.drawio
```

### JS/TS import graph

```bash
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/drawio/scripts/jsimports.py <root> [-o graph.json]
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/drawio/scripts/autolayout.py graph.json -o out.drawio
```

### Go import graph

```bash
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/drawio/scripts/goimports.py <root> [-o graph.json]
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/drawio/scripts/autolayout.py graph.json -o out.drawio
```

### Rust import graph

```bash
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/drawio/scripts/rustimports.py <root> [-o graph.json]
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/drawio/scripts/autolayout.py graph.json -o out.drawio
```

### Python class hierarchy

```bash
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/drawio/scripts/pyclasses.py <root> \
    [--group] [-o graph.json]
# --group: box classes by module
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/drawio/scripts/autolayout.py graph.json -o out.drawio
```

See `references/autolayout.md` for the full JSON contract, flags, and examples.

## (b) Harness skill-graph

Visualizes the dependency graph between harness skills, read from `"${HARNESS_BIN_ROOT:-.}"/harness/data/skill-deps.yaml` (SSOT) and grouped by `"${HARNESS_BIN_ROOT:-.}"/harness/data/components.yaml`.

### skillgraph.py

```bash
# All skills
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/drawio/scripts/skillgraph.py \
    [-o graph.json]

# Subset + transitive deps
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/drawio/scripts/skillgraph.py \
    --skills cook,plan [-o graph.json]

# Custom data files
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/drawio/scripts/skillgraph.py \
    --deps-file /path/to/skill-deps.yaml \
    --components-file /path/to/components.yaml
```

### Output contract

JSON matching `autolayout.py` input:
```json
{
  "direction": "TB",
  "nodes": [
    {"id": "cook", "label": "cook", "group": "hs"}
  ],
  "edges": [
    {"source": "cook", "target": "plan"}
  ]
}
```

- `direction`: "TB" (top-bottom) or "LR" (left-right)
- Node `id` = skill slug (unique, not "0" or "1")
- Node `group` = group from components.yaml; spine skills not present in components → group "hs"
- Edge direction: `source` depends on `target` (skill → dep)

### End-to-end

```bash
# 1. Export graph JSON
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/drawio/scripts/skillgraph.py \
    --skills cook -o /tmp/skill-graph.json

# 2. Layout with Graphviz (if `dot` is available)
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/drawio/scripts/autolayout.py \
    /tmp/skill-graph.json -o /tmp/skill-graph.drawio

# 3. Validate
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/drawio/scripts/validate.py \
    /tmp/skill-graph.drawio

# 4. Preview offline
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/drawio/scripts/make_preview_html.py \
    /tmp/skill-graph.drawio
```

### Default behavior

- **`--skills` not given**: all skills in `skill-deps.yaml` (currently ~107 entries).
- **`--skills cook,plan` given**: cook + plan + all their transitive deps (BFS closure).
- **Skill doesn't exist**: exit non-zero with a clear message, no traceback.
- **No network needed**: only reads local YAML files.

### "Owned" set

All keys in `skill-deps.yaml` — this is the harness skill graph; it includes shared resource dirs (`common`, `_docslib`) that have no SKILL.md. To restrict to invokable skills (those with a SKILL.md), filter by checking dir existence after install.
