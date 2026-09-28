# Frontmatter and packaging convention

Harness-native skills live at `harness/plugins/hs/skills/<name>/SKILL.md`. The catalog loader (`"${HARNESS_BIN_ROOT:-.}"/harness/scripts/catalog.py`) reads frontmatter to build the `owned` set.

## Required frontmatter

```yaml
---
name: <name>             # bare, no hs: prefix; name = dir (kebab-case)
description: <<=512 chars, clear trigger phrase, third-person style>
metadata:
  compliance-tier: <workflow | gate | telemetry | knowledge>
---
```

Ownership is location-based: any dir with a `SKILL.md` under `harness/plugins/*/skills/` is harness-owned regardless of its `name:` — the invoke prefix (`/hs:<name>`) comes from the plugin namespace, not from the frontmatter.

### Useful optional fields

```yaml
argument-hint: "[arg1] [arg2]"   # syntax hint for the user
```

**Do NOT add a `when_to_use` that restates the description.** Claude Code APPENDS `when_to_use` to `description` in the skill listing (both share one 1,536-char cap), so a `when_to_use` derived from — or paraphrasing — the description only duplicates text and burns listing budget for zero routing gain. Put the "Use when…" trigger in `description` itself. Add `when_to_use` ONLY when it carries
DISTINCT trigger phrases or example requests the description does not; otherwise omit it entirely. Full official field list: `references/frontmatter-fields.md`.

## compliance-tier

| Tier | Meaning | Examples |
|---|---|---|
| `workflow` | Skill coordinates workflow, does not block git | hs:plan, hs:cook, hs:skill-creator |
| `gate` | Skill may exit 2 / block flow | hs:code-review |
| `telemetry` | Skill only reads/writes telemetry, no intervention | analytics skills |
| `knowledge` | Read-only or reference skill, no gate claim | hs:excalidraw, lookup skills |

## Naming rules

- `name: <name>` — bare, must match the directory name (segment after the last `/`); no `hs:` prefix
- No uppercase, no spaces; use kebab-case
- "claude" and "anthropic" are banned in names
- Cross-skill references in prose: `hs:<name>` (no `/`); when invoking: `/hs:<name>`

## Directory structure

```
harness/plugins/hs/skills/<name>/
├── SKILL.md              required, body <=15,000 chars; every line <=400 chars
└── references/           optional, each file <=15,000 chars (harness standard)
    ├── <topic-a>.md      load-on-demand: workflow details
    └── <topic-b>.md      load-on-demand: schemas, checklists, etc.
```

Do not create `scripts/`, `agents/`, or `assets/` unless there is a real need and corresponding harness backing.

## Description — "pushy" style

```yaml
# Under-triggers — too generic
description: Skill that creates documentation

# Correct triggers — specific phrase + third-person
description: Analyze the codebase and manage project documentation — initialize, update,
  summarize. Use when documentation needs to be created, refreshed, or audited.
```

Description rules:
- Third-person: "Use when..." / "Invoke when..."
- At least 1 specific trigger phrase, key use case FIRST
- <=512 chars (harness standard). Note: Claude Code truncates the COMBINED `description` + `when_to_use` at 1,536 chars in the skill listing — keep them lean and non-overlapping so the trigger is not lost to truncation.

## CI invariant (check_fence.py)

Files in `harness/` must not contain path references of the form `dot-claude/skills/` or `dot-claude/hooks/` (CI test `TestOwnershipBoundary`), and must not contain external brand names, old invoke prefixes, or dev-trace labels. Lines that explain a learned technical pattern need a `# learn:` suffix to be whitelisted in CI.

Run the grep clean check before reporting DONE — full commands at `references/validation.md`. Empty output = pass.
