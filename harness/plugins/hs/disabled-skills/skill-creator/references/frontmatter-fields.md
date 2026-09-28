# SKILL.md frontmatter fields — reference

The full set of frontmatter keys Claude Code reads from a `SKILL.md`, plus the harness-specific conventions layered on top. Source: the official Claude Code skills docs (code.claude.com/docs/en/skills, "Frontmatter reference"). All fields are optional; only `description` is *recommended* so Claude knows when to use the skill.

## Official Claude Code fields

| Field | Required | What it does |
|---|---|---|
| `name` | No | Display name shown in skill listings. Defaults to the directory name. For a plugin-root `SKILL.md` it also sets the command name. |
| `description` | Recommended | What the skill does **and when to use it** — Claude routes on this. Put the key use case FIRST. If omitted, the first paragraph of the body is used. |
| `when_to_use` | No | Extra trigger context (trigger phrases / example requests). **Appended to `description`** in the skill listing and shares its cap. |
| `argument-hint` | No | Autocomplete hint for expected args, e.g. `[issue-number]` or `[filename] [format]`. |
| `arguments` | No | Named positional args for `$name` substitution in the body. Space-separated string or YAML list; names map to positions in order. |
| `disable-model-invocation` | No | `true` stops Claude from auto-loading the skill (manual `/name` only). Also blocks subagent preload and scheduled-task firing (v2.1.196+). Default `false`. |
| `user-invocable` | No | `false` hides the skill from the `/` menu (background knowledge users should not call directly). Default `true`. |
| `allowed-tools` | No | Tools Claude may use without a permission prompt while the skill is active. Space/comma string or YAML list. |
| `disallowed-tools` | No | Tools removed from the pool while the skill is active (e.g. block `AskUserQuestion` in a background loop). Clears on the next user message. |
| `model` | No | Model for the rest of the current turn while active; not saved. Same values as `/model`, or `inherit`. |
| `effort` | No | Effort level while active (`low`/`medium`/`high`/`xhigh`/`max`; availability depends on the model). Overrides session effort. |
| `context` | No | `fork` runs the skill in a forked subagent context. |
| `agent` | No | Which subagent type to use when `context: fork` is set. |
| `hooks` | No | Hooks scoped to this skill's lifecycle. |
| `paths` | No | Glob patterns that limit when the skill auto-activates (same format as path-specific rules). |
| `shell` | No | Shell for inline `` !`command` `` blocks: `bash` (default) or `powershell`. |

## The `description` / `when_to_use` cap (read before authoring either)

Claude Code **concatenates `description` + `when_to_use`** into the skill listing the routing model reads, and **truncates the combined text at 1,536 characters** to save context. Consequences:

- The "Use when…" trigger belongs in **`description`** — that is the field Claude routes on, key use case first.
- `when_to_use` is a SUPPLEMENT, not a second copy. A `when_to_use` that restates or paraphrases the description just duplicates text under the shared cap for zero routing gain — and risks pushing the real trigger past the 1,536-char truncation.
- Add `when_to_use` ONLY when it carries DISTINCT trigger phrases or example requests the description does not. Otherwise omit it — the harness `apply_frontmatter.py` deliberately does NOT auto-generate one.

## Harness conventions layered on top

The harness requires/expects a few fields beyond the CC defaults (see `frontmatter-and-packaging.md` for the authoring template):

| Field | Harness rule |
|---|---|
| `name` | Bare, matches the directory name (kebab-case) — no `hs:` prefix (the plugin namespace supplies the invoke prefix, `/hs:<name>`). "claude"/"anthropic" banned. |
| `description` | `<=512` chars (harness standard, stricter than the 1,536 listing cap); third-person, ≥1 specific trigger phrase, key use case first. |
| `metadata.compliance-tier` | `workflow` \| `gate` \| `telemetry` \| `knowledge` (see `frontmatter-and-packaging.md`). Ownership itself is location-based (any dir under `harness/plugins/*/skills/`), so tier is the only thing `metadata` needs to carry. |
| `paths` | Optional glob(s) to bind auto-activation to a file-type when the skill is narrowly file-scoped (e.g. `**/*.tsx` for a React-only skill). Do not add it "just in case" — an unbound skill still routes on `description`. |
| `disable-model-invocation` | Optional; `true` ONLY for skills that must never self-trigger from the model reading a description — the harness's own "push button" skills (ship, release, cleanup, afk, goal, show-off). Do not add it elsewhere; it does not block an explicit `/hs:<name>` invoke or an internal handoff, only auto-invocation. |

`category`, `license`, `keywords`, and `user-invocable` are retired harness fields — do NOT add them to a new skill. `apply_frontmatter.py` no longer auto-fills them.

Body budget is separate from the listing cap: SKILL.md body `<=200` lines, each `references/*.md` `<=300` lines (enforced by `check_skill_structure.py`).
