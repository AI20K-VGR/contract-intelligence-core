# Prompt Templates H–N

Template library for `hs:prompt`, part 2 of 2. Load the one template you need. Templates A–G and the full table of contents live in `templates-a-g.md`.

---

## Template H — ReAct + Stop Conditions

*Claude Code, Devin, AutoGPT, any AI that takes autonomous actions. Runaway loops and scope explosion are the biggest credit killers in agentic workflows — stop conditions are not optional.*

```
Objective:
[Single, unambiguous goal in one sentence]

Starting State:
[Current file structure / codebase state / environment]

Target State:
[What should exist when the agent is done]

Allowed Actions:
- [Specific action the agent may take]
- Install only packages listed in [requirements.txt / package.json]

Forbidden Actions:
- Do NOT modify files outside [directory/scope]
- Do NOT run the dev server or deploy
- Do NOT push to git
- Do NOT delete files without showing a diff first
- Do NOT make architecture decisions without human approval

Stop Conditions:
Pause and ask for human review when:
- A file would be permanently deleted
- A new external service or API needs to be integrated
- Two valid implementation paths exist and the choice affects architecture
- An error cannot be resolved in 2 attempts
- The task requires changes outside the stated scope

Checkpoints:
After each major step, output: ✅ [what was completed]
At the end, output a full summary of every file changed.
```

---

## Template I — Visual Descriptor

*Midjourney, DALL-E 3, Stable Diffusion, Sora, Runway, any image or video generation tool.*

```
Subject: [Main subject — specific, not vague]
Action/Pose: [What the subject is doing]
Setting: [Where the scene takes place]
Style: [photorealistic / cinematic / anime / oil painting / vector / etc.]
Mood: [dramatic / serene / eerie / joyful / etc.]
Lighting: [golden hour / studio / neon / overcast / candlelight / etc.]
Color Palette: [dominant colors or named palette]
Composition: [wide shot / close-up / aerial / Dutch angle / etc.]
Aspect Ratio: [16:9 / 1:1 / 9:16 / 4:3]
Negative Prompts: [blurry, watermark, extra fingers, distortion, low quality]
Style Reference: [artist / film / aesthetic reference if applicable]
```

**Tool-specific syntax:**
- **Midjourney**: comma-separated descriptors, not prose. Add `--ar`, `--style`, `--v 6` at the end.
- **Stable Diffusion**: `(word:1.3)` weight syntax. CFG scale 7–12. Negative prompt is mandatory.
- **DALL-E 3**: prose works well. Add "do not include any text in the image" unless text is needed.
- **Sora / video**: add camera movement (slow dolly, static shot, crane up), duration in seconds, cut style.

---

## Template J — Reference Image Editing

*When the user has an existing image to modify. Completely different from generation — never describe the whole scene from scratch, only describe the change.*

**Before writing the prompt, always tell the user:** "Attach your reference image to [tool name] before sending this prompt."

**Detect the tool's editing capability:**
- Midjourney: `--cref [image URL]` for character reference or `--sref` for style reference.
- DALL-E 3: use the Edit endpoint, not Generate. User must be in ChatGPT with image editing enabled.
- Stable Diffusion: use img2img mode, not txt2img. Denoising strength 0.3–0.6 to preserve the original.

```
Reference image: [attached / URL]
What to keep exactly the same: [list everything that must not change]
What to change: [specific edit only — be precise]
How much to change: [subtle / moderate / significant]
Style consistency: maintain the exact style, lighting, and mood of the reference
Negative prompt: [what to avoid introducing]
```

**Example:**
```
Reference image: [attached portrait photo]
What to keep exactly the same: face, hair, clothing, background, lighting
What to change: head angle — rotate from facing left to facing straight forward
How much to change: subtle, preserve all facial features exactly
Style consistency: maintain photorealistic style, same lighting direction
Negative prompt: no new elements, no style changes, no background changes
```

---

## Template K — ComfyUI

*ComfyUI node-based workflows. Always output Positive and Negative prompts as separate blocks. Ask for the checkpoint model before writing — syntax and token limits differ per model.*

**Ask first if not stated:** "Which checkpoint model are you using? (SD 1.5, SDXL, Flux, or other)"

**Model-specific notes:**
- SD 1.5: shorter prompts work better, under 75 tokens per block, use `(word:weight)` syntax.
- SDXL: handles longer prompts, supports more natural language alongside weighted syntax.
- Flux: natural language works well, less reliance on weighted syntax, very responsive to style descriptions.

```
POSITIVE PROMPT:
[subject], [style], [mood], [lighting], [composition], [quality boosters: highly detailed, sharp focus, 8k]

NEGATIVE PROMPT:
[what to exclude: blurry, low quality, watermark, extra limbs, bad anatomy, distorted, oversaturated]

CHECKPOINT: [model name]
SAMPLER: Euler a (recommended starting point)
CFG SCALE: 7 (increase for stricter prompt adherence)
STEPS: 20-30
RESOLUTION: [width x height — must be divisible by 64]
```

---

## Template L — Prompt Decompiler

*When the user pastes an existing prompt and wants to break it down, adapt it for a different tool, simplify it, or understand its structure. Analysis and adaptation, not building from scratch. This is `--fix` mode.*

**Detect which Decompiler task is needed:**
- **Break down** — explain what each part of the prompt does.
- **Adapt** — rewrite for a different tool while preserving intent.
- **Simplify** — remove redundancy and tighten without losing meaning.
- **Split** — divide a complex one-shot prompt into a cleaner sequence.

**For Adapt tasks, always ask:** "What tool is the original prompt from, and what tool are you adapting it for?"

**Break down output format:**
```
Original prompt: [paste]

Structure analysis:
- Role/Identity: [what role is assigned and why]
- Task: [what action is being requested]
- Constraints: [what limits are set]
- Format: [what output shape is expected]
- Weaknesses: [what is missing or could cause wrong output]

Recommended fix: [rewritten version with gaps filled]
```

**Adapt output format:**
```
Original ([source tool]): [original prompt]

Adapted for [target tool]:
[rewritten prompt using target tool syntax and best practices]

Key changes made:
- [change 1 and why]
- [change 2 and why]
```

**Split output format:**
```
Original prompt: [paste]

This prompt is doing [N] things. Split into [N] sequential prompts:

Prompt 1 — [what it handles]:
[prompt block]

Prompt 2 — [what it handles]:
[prompt block]

Run these in order. Each output feeds the next.
```

---

## Template M — Opus 4.7 / 4.8 Task Brief

*Any complex, multi-step, or agentic task on Claude Opus 4.7 or 4.8 (current default) — claude.ai, API, or Claude Code. Both read prompts literally and produce narrow output when context is missing. Front-loads everything so the first turn is the only turn.*

```
## Objective
[What needs to be built, fixed, or produced — one clear sentence. Add WHY if it affects approach.]

## Context
[What exists now — relevant files, current behavior, stack already in place, what was tried and failed]

## Target State
[What done looks like — specific files changed, behavior produced, tests passing. Binary where possible.]

## Scope
- Work only in: [specific files and directories]
- Do NOT touch: [forbidden files — .env, package-lock.json, configs, anything outside scope]

## Constraints
- [Stack version, naming conventions, no new dependencies without asking]
- Only make changes directly requested. Do not add features, abstractions, or files beyond what was asked.

## Acceptance Criteria
- [ ] [Binary check 1]
- [ ] [Binary check 2]
- [ ] [Binary check 3]

## Stop Conditions
Stop and ask before:
- Deleting any file
- Adding any dependency
- Modifying database schema or migrations
- Touching anything outside Scope

## Progress
After each completed step: ✅ [what was done] — [file(s) affected]
```

**Thinking depth** — add only when needed, delete otherwise:
- Hard multi-step task: `"Think carefully and step-by-step before starting."`
- Simple targeted change: `"Prioritize responding quickly. This is a scoped change."`
- Default: say nothing — adaptive thinking calibrates itself.

**Claude Code only — add a Session Strategy block when relevant:**
```
## Session Strategy
[Pick one:]
- New session — unrelated to prior context, start fresh
- Continue — prior context still needed
- Subagent — spin off for [file-heavy research / verification] so intermediate output stays out of main context
- Compact first — run /compact [focus on X] then begin
```

**When to use:** Opus 4.7 or 4.8 on any surface when the task is complex, multi-file, ambiguous, or agentic. Not needed for simple one-shot tasks.

---

## Template N — Research Brief

For `--for=research`: a self-contained assignment that lets a human or AI researcher return decision-ready, source-backed findings without a follow-up exchange. Writes the brief; does not perform the research.

```
[Plain-English project + situation for a reader with NO prior context.]

Research question: [the one question] — informing this decision: [the decision].

Sub-questions (3–6, fully cover the decision, no unrelated missions):
1. ...
2. ...

Source hierarchy: prefer PRIMARY sources — official docs, repositories, papers,
filings, changelogs. Treat forums and social posts as weak signals, never as
factual proof. Separate confirmed fact, inference, and unresolved uncertainty
when sources conflict.

Gap round (required): before finishing, revisit every contradiction and every
single-source claim; resolve or flag it explicitly.

Per-finding format (required): source URL + the specific claim + a one-line
decision relevance. Nothing without a source.

Completion bar: every sub-question answered or explicitly marked unresolvable;
gap round done.

Deliverable: a single detailed Markdown result — no second artifact, no
marketing copy, no speculative solution.
```

**When to use:** any `--for=research` brief handed to `hs:research`, a deep-research runner, or a human — when the value is a decision, not prose. Keep it to the structure above; do not invent findings.
