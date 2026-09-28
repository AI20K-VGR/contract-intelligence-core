---
name: hs:skill-creator
injectable: false
description: Create or update hs:* skills for the harness — SKILL.md, frontmatter, thin-core, references, validate via catalog.py. Use to create a new skill, refine triggers, or extend the harness.
argument-hint: "[skill-name or description]"
allowed-tools: [Bash, Read, Write, Edit, Grep, Glob]
metadata:
  compliance-tier: workflow
---

# hs:skill-creator — create harness-native skills

Create a new `hs:*` skill following the harness packaging convention: thin-core SKILL.md body <=15,000 chars
+ `references/` drawers. Every directive **must have real backing** (gate/script/rule/schema)
or be cut (backing-or-cut).

**Base convention** (full details): `references/frontmatter-and-packaging.md`.

## Surface load-bearing directives — do NOT bury them (non-negotiable)

A directive the reader MUST act on — who does the work (main vs subagent), a mandate that out-ranks the ambient output style, a STOP/gate — earns a **header-visible section or a table near the TOP**, never a bold sentence buried mid-paragraph in the longest step.
Progressive disclosure is for *detail*, not for the load-bearing rule itself: a rule parked in a `references/` drawer (loaded on demand) or at the tail of a wall-of-text reads as optional and gets skipped.

- **Role split up top.** If the skill delegates, state "held at main vs delegated to `@agent`" as a table/section BEFORE the Steps — not scattered across three distant paragraphs. Models to study: the `plan` skill's §"Who does what — main vs subagent"; the `cook` skill's §"Per-phase red→green: delegate to `@developer` … STOP before coding inline".
- **Beat the ambient style explicitly.** Proactive/autonomous output style pushes "act now, inline"; a `mode: hard` delegate mandate out-ranks it. When a directive conflicts with the style, SAY it out-ranks — do not leave the reader to arbitrate. Model sentence: the `cook` skill's §"Proactive / autonomous output style does NOT waive this … out-ranks it".
- **Every flag used in the body MUST be declared in `argument-hint`.** An orphan flag (used mid-body, absent from the hint) reads as undocumented and gets missed. Grep your own body for `--token`s and diff against `argument-hint`.
- **One term, one meaning within a span.** Don't let "inline" mean self-verify, don't-delegate, and no-spawn inside the same 8 lines — pick distinct words.

Detail + the pre-ship checklist: `references/thin-core-and-references.md` (§Surfacing load-bearing directives).

## Boundaries

- Only create files in `harness/plugins/hs/skills/<skill-name>/` — do NOT edit shared files (catalog.py, CLAUDE.md, BACKLOG.md).
- Non-skill primitives (hook/rule/schema/data/script/agent) do NOT belong here -> use `hs:harness-creator`. This skill only creates `hs:*` skills (leaf + orchestrator).
- Do not scaffold example skills into other directories.
- On completion: return the absolute path + `grep` clean-check result + STANDARDIZE row.

## Modes

| Mode | When |
|---|---|
| `new` (default) | Create a skill from scratch |
| `refine` | Update an existing SKILL.md or references |
| `validate` | Check an existing skill (structure + optional trigger-eval); no file creation |

## Process (new)

### Step 1 — Gather intent

Ask via `AskUserQuestion`:
- What does the skill do? Example of when the user would invoke it?
- Expected output (file, report, action)?
- Is there real backing in the harness (gate/script/rule)?
- **`injectable`?** Is this advisory / read-comprehension-safe methodology a second engine (the gemini partner lane) could usefully follow — `true`? Or harness machinery that runs a gate, writes the tree, ships/deploys, or drives the spine — `false`? Default by category: advisory/knowledge → `true`, executor/gate → `false`.

### Step 2 — Check the catalog

```bash
python3 -c "from harness.scripts.catalog import load_catalog; print(load_catalog())"
```

Check `harness/plugins/hs/skills/` — avoid duplicating an existing skill. If a similar skill exists -> suggest `refine` instead of `new`.

### Step 3 — Identify backing

For **each feature** in the new skill:

1. Find backing in the harness: gate (`harness/hooks/*.py`), script (`harness/scripts/*.py`), rule (`harness/rules/*.md`), schema (`harness/schemas/*.json`).
2. **Has backing** -> keep the directive, point to the backing name (not a `.claude/` path).
3. **No backing** -> CUT or move into `references/` as advisory.

See the full backing-or-cut table: `references/thin-core-and-references.md`.

### Step 4 — Create the structure

```
harness/plugins/hs/skills/<name>/
├── SKILL.md          (required, body <=15,000 chars; every line <=400 chars)
└── references/       (optional: load-on-demand drawers, each <=15,000 chars)
    ├── <topic-a>.md
    └── <topic-b>.md
```

Create `SKILL.md` following the frontmatter convention:

```yaml
---
name: <name>
injectable: true | false          # partner-lane allowlist (see Step 1)
description: <<=512 chars, clear trigger phrase, third-person>
argument-hint: "<syntax hint>"   # optional
metadata:
  compliance-tier: workflow | gate | telemetry
---
```

Full details: `references/frontmatter-and-packaging.md`. Full official field list (incl. the `description`+`when_to_use` 1,536-char listing cap): `references/frontmatter-fields.md`.

**`injectable` authoring contract:** if you set `injectable: true`, keep the skill's methodology (role + process + output shape) SEPARATE from harness-machinery calls — do NOT embed a gate call (`python3 "${HARNESS_BIN_ROOT:-.}"/harness/{hooks,scripts}/<gate>.py`) in the body, or `check_skill_structure` flags an `injectable-gate-conflict` (HARD).
An injectable skill teaches a method a second engine can follow; it never runs a harness gate.

### Step 5 — Write the thin-core

The thin-core SKILL.md must contain:

1. **Boundaries** — clearly state "what NOT to do", when to stop, when to ask the user.
2. **Wiring block** — "HARD-GATE (real wiring)" or "Backing" pointing to real targets (actual gate/script filename, not phantom).
3. **Modes/Flags table** — if the skill has multiple modes.
4. **Process** — numbered steps, each <=3 lines; details -> references drawer.
5. **Quick reference** — table of reference drawers with short descriptions.
6. **Surfaced load-bearing directives** — role split / style-override / STOP-gate live in a header-visible section near the top, and every body flag is declared in `argument-hint` (see §"Surface load-bearing directives" above).

Language: English, imperative, sacrifice grammar for brevity.

### Step 6 — Validate

```bash
# Grep clean check (must be EMPTY) — see full commands at references/validation.md
python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/catalog.py
# Or verify the slug appears in load_catalog()['owned']
```

Full checklist: `references/validation.md`. To measure whether the description actually
**triggers** on indirect queries (not just that it is well-formed), run the trigger-eval:
`references/eval-validate.md` — and iterate it automatically with the optimize loop: `references/optimize-loop.md`.

### Step 7 — Write the STANDARDIZE row

Add one line to `docs/STANDARDIZE.md`:

```
| ADAPT | hs:<name> skill (native thin-core + references) | <source> (origin, MIT) | harness/plugins/hs/skills/<name>/ | <notes> | grep-clean invariant + SKILL.md |
```

## HARD-GATE (real wiring)

Catalog loader `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/catalog.py` -> `load_catalog()` -> field `owned` is LOCATION-based: every directory with a `SKILL.md` under `harness/plugins/*/skills/` is in the `owned` set, regardless of its frontmatter `name:`. Put the skill in the right directory; the name no longer decides ownership.

CI invariant (`harness/tests/test_bug_class_invariants.py` -> `TestOwnershipBoundary`): any path reference of the form `dot-claude/skills/` or `dot-claude/hooks/` in `harness/` -> test fails, except lines with `# learn:`. Grep clean check is required before reporting DONE — commands at `references/validation.md`.

## Quick reference

| Content | Drawer |
|---|---|
| Frontmatter fields + compliance-tier | `references/frontmatter-and-packaging.md` |
| Backing-or-cut + thin-core structure | `references/thin-core-and-references.md` |
| Naming + routing + cross-skill calls | `references/naming-and-routing.md` |
| Authoring orchestrator skills (chain meta-skills) | `references/orchestrator-skills.md` |
| Validate checklist + grep patterns | `references/validation.md` |
| Trigger-eval a description (does it activate?) | `references/eval-validate.md` |
| Optimize loop: iterate a description until it triggers right | `references/optimize-loop.md` |
| Portability & third-party safety when porting/importing a skill | `references/skill-ecosystem-portability-and-safety.md` |
