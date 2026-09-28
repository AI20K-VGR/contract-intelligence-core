# Stitch — Actions

Full command flags, outputs, and project-isolation resolution for the stitch skill.

## generate

Generate UI design from text prompt.

```bash
npx tsx scripts/stitch-generate.ts "<prompt>" [--project <id>] [--project-name <title>] [--device MOBILE|DESKTOP|TABLET] [--variants <count>]
```

Returns: screen ID, preview image URL. With `--variants`: additional design alternatives.

## export

Export generated design as HTML/Tailwind, screenshot, or DESIGN.md.

```bash
npx tsx scripts/stitch-export.ts <screen-id> [--format html|image|all] [--output <dir>]
```

Outputs:
- `design.html` — Semantic HTML with Tailwind CSS classes
- `design.png` — Screenshot of the design
- `DESIGN.md` — Agent-readable design spec (colors, typography, spacing, components)

## quota

Check and manage daily quota.

```bash
npx tsx scripts/stitch-quota.ts check       # Show remaining credits
npx tsx scripts/stitch-quota.ts increment   # Bump after generation
npx tsx scripts/stitch-quota.ts reset       # Force reset (auto-resets daily)
```

## edit

Refine an existing design.

```typescript
const editedScreen = await screen.edit("Make the header darker and add a search bar");
```

## Project Isolation

Stitch auto-isolates designs per git repo — each gets its own project automatically.

**Resolution priority:**
1. `--project <id>` — direct Stitch project ID
2. `--project-name <title>` — title-based lookup-or-create
3. `STITCH_PROJECT_ID` env — user's global override
4. Auto-detect from git repo name
5. `"harness-default"` fallback

When an active plan exists, pass `--project-name "{repo}/{plan-slug}"` to group designs by plan:
```bash
npx tsx scripts/stitch-generate.ts "checkout page" --project-name "my-saas/auth-system"
```

If no plan is active, omit `--project-name` — script auto-detects from the git repo name.
