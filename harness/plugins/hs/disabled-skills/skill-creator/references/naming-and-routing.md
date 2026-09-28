# Naming and routing — skill naming conventions and linking

## Naming rules

| Component | Rule | Example |
|---|---|---|
| Dir name | kebab-case, matching the part of the name after `:` | `skill-creator/` for `hs:skill-creator` |
| `name:` frontmatter | `hs:<dir>` | `name: hs:skill-creator` |
| Files inside dir | kebab-case | `references/naming-and-routing.md` |
| Reference drawers | short topic, self-documenting | `frontmatter-and-packaging.md` |

## Cross-skill routing in prose

Use the skill name, not a path:

```markdown
# CORRECT
Activate hs:research before planning.
See hs:brainstorm to explore options.
Invoke /hs:cook after the plan is approved.

# WRONG — exposes runtime path into the dot-claude tree (banned, see TestOwnershipBoundary)
Read dot-claude/skills/research/ ...
See harness/plugins/hs/skills/brainstorm/SKILL.md
```

## When to write `/hs:<name>` in prose

- Only write `/hs:<name>` when directing the user to invoke directly (user-facing instruction)
- In internal skill-to-skill mentions: use `hs:<name>` (no `/`)

## Referencing AGENTS vs skills vs workflows in prose

Three distinct kinds, three distinct forms — do not conflate them (the ref validator, `validate_skill_crossrefs.py`, checks each against its own registry):

| Kind | Prose form | Resolves against | Example |
|---|---|---|---|
| Skill | `hs:<name>` / `/hs:<name>` | skills registry | `hs:cook` |
| **Agent** (subagent you delegate to via Task) | **`@<name>`** (bare name) | agent registry (`agents/*.md` frontmatter `name:`) | `@code-reviewer` |
| Workflow | `hs:<name>` inside a `Workflow({name:...})` call | workflows registry (`workflows/*.js`) | `hs:base-pipeline-verify` |

The agent form is **bare** (`@code-reviewer`, not `@hs:code-reviewer`) — the `@` sigil marks the agent kind, and the name mirrors the agent `.md` frontmatter `name:` (which is bare). Never write an agent as `hs:<name>` (that reads as a skill route and the validator flags it broken).

## Skill name map (ck -> hs)

Ported skills — use these names in all cross-references:

| Skill | Invoke | Status |
|---|---|---|
| hs:plan | `/hs:plan` | Available |
| hs:cook | `/hs:cook` | Available |
| hs:test | `/hs:test` | Available |
| hs:git | `/hs:git` | Available |
| hs:research | `/hs:research` | Available |
| hs:brainstorm | `/hs:brainstorm` | Available |
| hs:debug | `/hs:debug` | Available |
| hs:fix | `/hs:fix` | Available |
| hs:code-review | `/hs:code-review` | Available |
| hs:scout | `/hs:scout` | Available |
| hs:afk | `/hs:afk` | Available |
| hs:skill-creator | `/hs:skill-creator` | Available |
| hs:find-skills | `/hs:find-skills` | Forward ref (not yet ported) |

Skills EXCLUDED (not ported, no references): stack-specific (frontend/ui/mobile/shopify/db/deploy) -> omit all references.

## When a skill wants to call another skill

Write in SKILL.md as:

```markdown
Activate hs:research to gather context before step X.
After completion -> the runner invokes /hs:cook <path>.
```

Do not hardcode file paths of other skills. Do not create runtime dependencies between skill files.

## Catalog resolve

`"${HARNESS_BIN_ROOT:-.}"/harness/scripts/catalog.py` -> `load_catalog()` returns:
- `dirs` — set of dir names that have a SKILL.md
- `slug_to_dir` — map from `name:` value and variants -> dir name
- `owned` — dirs with `name: hs:*` (harness-native)

A new skill appears in `owned` once it has a correctly formatted `name: hs:<name>` in its frontmatter.
Verify:

```bash
python3 -c "
import sys; sys.path.insert(0, 'harness/scripts')
from catalog import load_catalog
c = load_catalog()
print('owned:', sorted(c['owned']))
"
```

## Wiring block — naming in HARD-GATE

Point to the actual filename, not a phantom:

```markdown
# CORRECT
Gate `harness/hooks/gate_stage.py` blocks push when an artifact is missing.
Script `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/catalog.py` -> load_catalog() builds the owned set.

# WRONG — phantom backing
"Harness will automatically check on push"  <- mechanism is unclear
"Internal gate"                             <- no real file referenced
```
