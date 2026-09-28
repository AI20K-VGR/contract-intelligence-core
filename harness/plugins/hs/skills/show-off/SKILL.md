---
name: hs:show-off
injectable: true
description: "Create preference-aware self-contained HTML pages to showcase work. Use for demos, visual presentations, interactive showcases."
allowed-tools: [Bash, Read, Write, Edit, Glob, Grep, WebFetch, WebSearch]
argument-hint: "[markdown-or-prompt]"
disable-model-invocation: true
metadata:
  compliance-tier: workflow
---

ultrathink
Activate `hs:frontend-design`: showcase HTML presentation for this request.

## REQUEST / MISSION
$ARGUMENTS

## PURPOSE
Showcase, social-media posting, and optional output images for articles.

## Persisted Preferences (MANDATORY — resolve BEFORE project-management)

`show-off` has user-level workflow preferences. Defaults preserve legacy behavior:

```json
{ "screenshots": true, "publishing": true, "languages": ["vi", "en"] }
```

`--no-antv`, `--no-diagram-design`, `--no-editorial-visuals` turn the decoration off for
one invocation; the standing defaults live in `output.yaml` under `visual:` and resolve
through `output_config.py --resolved`, the same door as `audience` and `code_style`. For
KPI tiles and micro-charts the vendored bundle is
`"${HARNESS_BIN_ROOT:-.}"/harness/assets/antv/infographic.min.js` (874 KB, global
`window.AntVInfographic`) — inline it, never link a CDN, and reach for it only at three
or more panels. Below that, hand-authored SVG is smaller and reads better. Its optional
CJK webfont is blocked by the artifact CSP and falls back to the declared stack.

Resolve them before reading the mission content:

```bash
PREF_SCRIPT="${HARNESS_BIN_ROOT:-.}/harness/plugins/hs/skills/show-off/scripts/preferences.js"
node "$PREF_SCRIPT" get
```

Helper stores preferences at `~/.claude/show-off/preferences.json` (override: `SHOW_OFF_PREFS_PATH`). Full CLI: `references/capture-and-preferences.md`.

Parse only workflow-control intent before project-management:
- Screenshots: "no screenshots" / `--no-screenshots`.
- Publishing: "no publish" / "local only" / `--no-publish`.
- Language: "English only" / "Vietnamese only" / `--languages en`.
- Reset: "reset show-off preferences". One-time: "for this run only" → apply without persisting.

If the user changes a setting and does not say it is only for this run, persist it immediately (`node "$PREF_SCRIPT" set ...`). The latest explicit instruction wins over stored preferences; do not ask the user to repeat a persisted opt-out.

## Prerequisite (MANDATORY — run BEFORE content workflow)

After resolving preferences, invoke `/hs:project-management` **before** content work — it owns the plan/task lifecycle; `show-off` is a consumer. It must:
- Create a dated plan dir under `plans/` (`{date}-{issue}-{slug}` from hook injection).
- Register the checklist as tasks: always request-analysis, content, HTML, local review; add capture if `screenshots=true`; add publish if `publishing=true`.
- Set the active plan context so `frontend-design`, the capture script, and assets share one folder.
- Record invocation args + resolved preferences in `plan.md`.

Hard gate: do NOT proceed until the plan dir exists and the checklist is registered. If `project-management` returns `BLOCKED` / `NEEDS_CONTEXT`, resolve it first.

## Detailed Instructions

Follow strictly in order; update the registered tasks as each step starts/completes:

1. Read and analyze the request; split into 2–6 topics/sections (including a hero section).
2. Search the internet for supporting evidence / fact-checking.
3. Write content markdown at `assets/showoff/<mission-name>/content.md`, organized by section. If a writing-styles dir exists (`~/www/writing-styles/`, `~/.claude/writing-styles/`, `~/writing-styles/`), read it for style; attach citation URLs as footnotes.
4. If `publishing=true`, MUST check `agentwiki` is on PATH (`command -v agentwiki`) before invoking it; if absent, mark the publish task skipped and report it — do not fail silently. Otherwise publish via the `agentwiki` CLI. If `publishing=false`, keep local and mark publish skipped.
5. For any diagram or chart section, start from
   `"${HARNESS_BIN_ROOT:-.}"/harness/assets/diagram-templates/<type>/<light|dark|full>.html`
   (24 types, `VENDOR.yaml` indexes them) — self-contained, no network fetch. Copy it
   out; never edit the vendored file. Then activate `hs:frontend-design` to build a
   stunning multi-section HTML file: hero section first (eye-catching), smooth
   top-to-bottom scroll with parallax, diagrams/illustrations, optional
   micro-animations, citation footnotes. Remember each section's id/class for capture.
6. Content uses the resolved language preference: `["vi","en"]` bilingual with toggle; `["en"]` English only; `["vi"]` Vietnamese only.
7. If `screenshots=true`, capture each section to `assets/showoff/<mission-name>/images/` with a ratio prefix (`horizontal`/`vertical`/`square`) via the parallel capture script. If `false`, skip capture and mark the task skipped. Commands + `rws` publish-fallback rules: `references/capture-and-preferences.md`.
8. If `publishing=true`, publish/update the static site via `agentwiki` when complete — same PATH check and skip-and-report rule as step 4.
9. Open the resulting HTML with `open` (or equivalent).

## Output Requirements

- Each section fits within the browser viewport; responsive for 16:9, 9:16, 1:1.
- Font supports Vietnamese well when Vietnamese is enabled.
- Theme toggle: system (default) / light / dark.
- Layout never breaks; content never clipped; good on all screen sizes.
- Output images at proper ratio sizes when `screenshots=true`. Modular, maintainable code.

## References

| Topic | File |
|-------|------|
| Preference + capture CLI, `rws` fallback, readiness chain | `references/capture-and-preferences.md` |

## Security Policy

Handles HTML generation + screenshot capture only. No auth, DB access, server deploy, or sensitive-data processing. Never include API keys or credentials in generated HTML.

## See also

- For hi-fi HTML production (clickable prototypes, animated films, HTML decks, MP4/PPTX): see
  **huashu-design** (+ wider external design-skill catalog) in `hs:ui-ux`.
