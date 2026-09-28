---
name: hs:preview
injectable: true
description: Explain a change or architecture with a diagram when visuals are clearer than prose — flow/architecture, before-after, sequence; output to docs/ or plans/.
argument-hint: "[--explain|--diagram|--ascii|--slides|--diff|--plan-review|--recap] <topic>"
allowed-tools: [Read, Write, Edit]
metadata:
  compliance-tier: workflow
---

# hs:preview — visual explanation

Visual explanation (diagram/slide-outline) when visuals aid understanding more than prose. No code-write; no markdown outside `docs/`/`plans/` (CLAUDE.md rule #3).

**When is a visual needed?** Read `references/when-visual-helps.md` first — sole decision gate. No added value over prose -> return prose, skip diagram.

## Modes

| Flag | When | Output |
|---|---|---|
| _(no arg)_ | unclear | `AskUserQuestion` asks for topic + mode |
| `--explain <topic>` | explain a concept or code path | ASCII + Mermaid fenced + prose |
| `--diagram <topic>` | focused diagram (flow, arch, sequence) | ASCII + Mermaid fenced |
| `--ascii <topic>` | terminal-only, no Mermaid | ASCII box diagram + legend |
| `--slides <topic>` | outline of sequential ideas | Markdown slide-outline |
| `--diff [ref]` | visual diff review of a change set | structured-analysis Markdown report — `references/analysis-diff.md` |
| `--plan-review [plan]` | plan vs codebase comparison | structured-analysis Markdown report — `references/analysis-plan-review.md` |
| `--recap [window]` | project context snapshot after time away | structured-analysis Markdown report — `references/analysis-recap.md` |

No `--html` flag — harness ships no HTML renderer. Mermaid fenced blocks render in editor/GitHub markdown preview; `--diff` / `--plan-review` / `--recap` emit as Markdown reports (Mermaid + review cards) per the save-location rule, NOT HTML.

## Workflow

1. **Decision gate** (required): load `references/when-visual-helps.md` — if no evidence a visual helps, return prose and stop.
2. **Parse arg**: determine topic + mode; if missing -> `AskUserQuestion`.
3. **Read context**: scout related code/docs (`hs:scout` for a real-codebase topic); do NOT diagram an unread system.
4. **Choose diagram pattern**: load `references/diagram-patterns.md` — pick type (flowchart, sequence, architecture, before-after) by content.
5. **Create output**: follow template in `references/diagram-patterns.md`; always include ASCII fallback alongside Mermaid (except `--ascii`).
6. **Save location**:
   - Active plan -> `plans/<slug>/visuals/<topic-slug>.md`
   - No active plan -> `plans/visuals/<topic-slug>.md`
   - Durable architecture doc -> `docs/` (via `hs:docs`)
   - Create directory if missing.
7. **Report**: return the absolute path of the saved file + recommended next step.

## Boundaries

- Do NOT create markdown outside `docs/` or `plans/` — violates CLAUDE.md rule #3.
- Do NOT diagram assumed architecture (unread code) — violates the Evidence Filter (`"${HARNESS_BIN_ROOT:-.}"/harness/rules/verification-mechanism.md`).
- Do NOT use external render libraries (HTML server, Excalidraw, video) — no such
  renderer; diagrams are Mermaid fenced blocks or ASCII only. This is a decision,
  not a missing feature: a preview is read in the terminal and diffed in review,
  and a rendered video is neither. It also cannot be reviewed — nobody can see
  what changed between two versions of it. Anything that needs a rendered artifact
  belongs in a durable document, not a preview.
- Durable diagram output (architecture decision) -> update `docs/` via `hs:docs`.
- Finish: return absolute path of saved file.

## HARD-GATE (real wiring)

No hard gate specific to visuals — but:
- Output files must be under `docs/` or `plans/` -> `harness/hooks/write_guard.py` enforces containment (CLAUDE.md rule #3 + `"${HARNESS_BIN_ROOT:-.}"/harness/data/ownership.yaml`).

## Workflow position

**Typically after:** `hs:plan` (visualize plan), `hs:cook` (explain diff), `hs:brainstorm` (diagram chosen approach).
**Typically before:** review/handoff (diagram accompanies report).
**Related:** `hs:docs` (save durable diagram to `docs/`).
