# Naming Conventions

Detailed naming rules for every file type. See SKILL.md Rule 2 for the overview.

## Creating a slug

**Rules:**
- Lowercase; replace spaces and special characters with hyphens
- Preserve numbers
- Maximum 50 characters (cut at a word boundary)
- No leading/trailing hyphens; no consecutive hyphens
- Self-describing names preferred over abbreviations

**Examples:**

| Title | Slug |
|---------|------|
| "User Authentication Flow" | `user-authentication-flow` |
| "Fix: API Rate Limiting Bug #42" | `fix-api-rate-limiting-bug-42` |
| "SDLC Harness W2 Horizontal" | `harness-w2-horizontal` |

## Date format

Use `YYMMDD-HHmm` (default). No HARNESS_PLAN_DATE_FORMAT env var exists in the current repo — get a timestamp with:

```bash
date +%y%m%d-%H%M
```

| Format | Example | When |
|--------|-------|----------|
| `YYMMDD-HHmm` | `260304-1530` | plan, report, journal (time-sensitive) |
| `YYMMDD` | `260304` | ADR, daily report (date only) |
| No date | `{slug}` | evergreen doc, config, source code |

### When to use a timestamp

- Plan, report, journal, brainstorm, session
- AI-generated content
- Campaign assets
- Any content that can go stale over time

### When NOT to use a timestamp

- Docs (architecture, standards, guides)
- Config files
- Source code
- Templates
- Brand assets (logo, style)

## Code file naming

| Language | Convention | Example |
|----------|-----------|-------|
| JS/TS/Shell | kebab-case | `user-auth-service.ts`, `run-preflight.sh` |
| Python | snake_case | `gate_stage.py`, `harness_paths.py` |
| C#/Java/Kotlin/Swift | PascalCase | `UserAuthService.cs` |
| Go/Rust | snake_case | `user_auth_service.go` |
| CSS/SCSS | kebab-case | `auth-form-styles.scss` |

**Harness note:** `harness/scripts/` and `harness/hooks/` use Python `snake_case` — follow the existing pattern, do not invent a new one.

## File extensions

| Type | Extension |
|------|------|
| Images | `.png`, `.jpg`, `.webp`, `.svg`, `.gif` |
| Video | `.mp4`, `.mov`, `.webm` |
| Audio | `.mp3`, `.wav`, `.m4a` |
| Documents | `.md`, `.txt`, `.pdf` |
| Machine-written data | `.json`, `.jsonl` |
| Human-edited config | `.yaml`, `.yml` |

## Variant naming

### Size variant
Pattern: `{name}-{width}x{height}.{ext}`
- `hero-1920x1080.png`, `thumbnail-300x200.jpg`

### Platform variant
Pattern: `{name}-{platform}.{ext}`
- `cover-youtube.png`, `post-instagram.png`

### Theme/style variant
Pattern: `{name}-{variant}.{ext}`
- `logo-dark.svg`, `logo-light.svg`

### Version variant
Pattern: `{name}-v{N}.{ext}`
- `mockup-v2.png`, `proposal-v3.pdf`

## Directory naming

- Always kebab-case
- Plural for collections: `tests/`, `scripts/`, `assets/`
- Singular for a specific item: `src/auth/`
- No abbreviations (except well-established ones: `docs/`, `src/`)

## Report naming

Pattern in this repo (per naming-subagent): `{agent-type}-{YYMMDD-HHmm}-{slug}-report.md`

Examples:
- `general-purpose-260304-1530-auth-module-analysis-report.md`
- `scout-260304-1545-hook-inventory-report.md`
- `brainstorm-260304-1600-caching-strategy-report.md`

Stored at: `plans/reports/` (standalone report) or `plans/{slug}/reports/` (attached to a plan).

## Plan folder naming

Pattern: `{YYMMDD-HHmm}-{slug}/`

Examples:
- `260304-1530-implement-user-authentication/`
- `260612-1237-harness-w2-horizontal-1/`

## Phase file naming

Pattern: `phases/phase-{N}-{name}.md` — phase files live under the `phases/` subdir (the scaffold layout the gates hash), numbered from 1 (not zero-padded).

Examples:
- `phases/phase-1-research.md`
- `phases/phase-2-implement-hooks.md`
- `phases/phase-3-tdd-scripts.md`
