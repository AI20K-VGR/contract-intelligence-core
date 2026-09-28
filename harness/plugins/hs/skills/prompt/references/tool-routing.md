# Tool Routing — per-tool profiles

Identify the target tool and route accordingly. Load ONLY the profile you need. Every profile below is faithful to the source skill; model claims (GPT-5.x, Gemini 3 Pro, MiniMax M2.7, Opus 4.8) are the original author's — kept verbatim in spirit, not independently re-verified.

---

**Claude (claude.ai, Claude API, Claude 4.x)** — current default **Opus 4.8** (4.7 still selectable; assume 4.8 unless a version is named). *Durable across 4.6 / 4.7 / 4.8:* be explicit and specific — Claude follows instructions literally, missing context = narrow literal output · Opus over-engineers by default, add "Only make changes directly requested. Do not add features or refactor beyond
what was asked." · XML tags help complex multi-section prompts (`<context>`, `<task>`, `<constraints>`, `<output_format>`) · give reasoning WHY not just WHAT · always specify output format and length · for complex/multi-step tasks front-load everything in one turn · do NOT add "think step by step" or a fixed thinking budget — Opus calibrates adaptive thinking (influence via "Think carefully
before responding" / "Prioritize responding quickly") · use Template M for agentic/multi-step. *Opus 4.8 (default):* 4.7's literalism + adaptive thinking, same front-loading discipline · 1M-token window (relevant context, no padding) · effort/thinking auto-calibrated — do not specify. *Opus 4.7:* more literal than 4.6 — vague first turns produce narrower results; front-load intent, file scope,
constraints, acceptance criteria.

**ChatGPT / GPT-5.x / OpenAI GPT** — start with the smallest prompt that achieves the goal · be explicit about the output contract (format, length, what "done" looks like) · state tool-use expectations if it has tools · use compact structured outputs · constrain verbosity ("Respond in under 150 words. No preamble. No caveats.") · strong at long-context synthesis and tone adherence.

**o3 / o4-mini / OpenAI reasoning models** — SHORT clean instructions ONLY · NEVER add CoT / "think step by step" / reasoning scaffolding (it degrades output) · prefer zero-shot, add few-shot only if strictly needed and tightly aligned · state what you want and what done looks like, nothing more · keep system prompts under 200 words.

**Gemini 2.x / Gemini 3 Pro** — strong at long-context + multimodal · prone to hallucinated citations, add "Cite only sources you are certain of. If uncertain, say [uncertain]." · can drift from strict formats — use explicit format locks with a labelled example · for grounded tasks add "Base your response only on the provided context. Do not extrapolate."

**Qwen 2.5 (instruct)** — excellent instruction following, JSON, structured data · give a clear role in the system prompt · works well with explicit output specs incl. JSON schemas · shorter focused prompts outperform long ones.

**Qwen3 (thinking mode)** — two modes: thinking (`/think` or `enable_thinking=True`) and non-thinking · thinking mode = treat like o3 (short clean, no CoT, no scaffolding) · non-thinking = treat like Qwen2.5 instruct (full structure, explicit format, role).

**Ollama (local)** — ALWAYS ask which model is running first (Llama3, Mistral, Qwen2.5, CodeLlama behave differently) · the system prompt is the biggest lever — include it so the user can set it in their Modelfile · shorter simpler prompts win · temperature 0.1 for coding/deterministic, 0.7–0.8 for creative · for coding use CodeLlama or Qwen2.5-Coder.

**Llama / Mistral / open-weight** — shorter prompts (they lose coherence with deep nesting) · simple flat structure · be more explicit than with Claude/GPT · always include a role in the system prompt.

**DeepSeek-R1** — reasoning-native like o3, do NOT add CoT · short clean instructions, state goal + desired format · outputs reasoning in `<think>` tags by default — add "Output only the final answer, no reasoning." if needed.

**MiniMax (M3 / M2.7)** — OpenAI-compatible API, GPT prompts transfer directly · strong instruction following, structured output, long-context (1M on M2.7) · M2.7-highspeed optimized for speed (latency-sensitive tasks) · temperature must be between 0 and 1 inclusive (above 1 fails) · may output reasoning in `<think>` tags — add "Output only the final answer, no reasoning tags." if unwanted ·
good at code, JSON, multi-step analysis · responds well to explicit role + structured format · function calling supports OpenAI-style tool definitions.

**Claude Code** — agentic (runs tools, edits files, executes commands) · starting state + target state + allowed actions + forbidden actions + stop conditions + checkpoints · stop conditions are MANDATORY (runaway loops are the biggest credit killer) · default Opus 4.8 (4.7 selectable); effort/thinking harness-managed — do NOT hardcode · Opus 4.7/4.8 more literal than 4.6 — front-load intent,
file scope, constraints, acceptance criteria, session strategy · uses fewer tool calls by default — instruct explicitly ("Read all files in /src/auth/ before starting") · spawns fewer subagents — request explicitly · over-engineers — add "Only make changes directly requested. Do not add extra files, abstractions, or features." · always scope to specific files/dirs with a path anchor ·
human-review triggers required ("Stop and ask before deleting any file, adding any dependency, or affecting the database schema") · session hygiene (new task = new session, /rewind over mid-conversation correction, /compact at ~50%) · use Template M for complex tasks.

**Antigravity (Google's agent-first IDE, Gemini 3 Pro)** — task-based prompting (describe outcomes, not steps) · prompt for an Artifact (task list, plan) before execution to review it first · browser automation built-in — include verification ("After building, verify UI at 375px and 1440px using the browser agent") · specify autonomy level ("Ask before running destructive terminal commands") ·
one deliverable per session.

**Cursor / Windsurf** — file path + function name + current behavior + desired change + do-not-touch list + language/version · never a global instruction without a file anchor · "Done when:" required · for complex tasks split into sequential prompts.

**Cline (formerly Claude Dev)** — agentic VS Code extension (edits files, runs terminal, browser tools) · match prompting style to the underlying model · starting state + target state + file scope + stop conditions + approval gates · specify which files to edit and which to leave · add "Ask before running terminal commands" / "Ask before installing dependencies" · leverage its
read/search/browser for context · break multi-step tasks into sequential prompts with checkpoints · it shows a task list before executing — review and adjust scope.

**GitHub Copilot** — write the exact function signature, docstring, or comment immediately before invoking · describe input types, return type, edge cases, and what the function must NOT do · it completes what it predicts, not what you intend — leave no ambiguity.

**Bolt / v0 / Lovable / Figma Make / Google Stitch** — full-stack generators default to bloated boilerplate, scope it down · always specify stack, version, what NOT to scaffold, component boundaries · Lovable responds to design-forward descriptions (include visual/UX intent) · v0 is Vercel-native (specify if you need non-Next.js) · Bolt is full-stack (be explicit frontend vs backend vs
database) · Figma Make is design-to-code (reference your Figma component names) · Google Stitch is prompt-to-UI (describe the interface goal, add "match Material Design 3 guidelines" for Google-native styling) · add "Do not add authentication, dark mode, or features not explicitly listed."

**Devin / SWE-agent** — fully autonomous (browse web, run terminal, write+test code) · very explicit starting state + target state required · a forbidden-actions list is critical (it will make decisions you didn't intend) · scope the filesystem ("Only work within /src. Do not touch infrastructure, config, or CI files.").

**Research / Orchestration AI (Perplexity, Manus)** — Perplexity search: specify search vs analyze vs compare, add citation requirements, reframe hallucination-prone questions as grounded queries · Manus + Perplexity Computer are multi-agent orchestrators — describe the end deliverable, not steps · Perplexity Computer: specify the output artifact type (report / spreadsheet / code / summary),
add "Flag any data point you are not confident about" · for long chains add verification checkpoints.

**Computer-Use / Browser Agents (Perplexity Comet/Computer, OpenAI Atlas, Claude in Chrome, OpenClaw)** — they control a real browser (click, scroll, fill forms, transact) · describe the outcome not the navigation ("Find the cheapest flight from X to Y on Emirates or KLM, no Boeing 737 Max, one stop maximum") · specify constraints explicitly · add permission boundaries ("Do not make any
purchase. Research only.") · add a stop condition for irreversible actions ("Ask me before submitting any form, completing any transaction, or sending any message") · Comet best for research/comparison/extraction; Atlas stronger for multi-step commerce/account management.

**Image AI — Generation (Midjourney, DALL-E 3, Stable Diffusion, SeeDream)** — first detect generation-from-scratch vs editing-existing. Midjourney: comma-separated descriptors, subject→style→mood→lighting→composition, params at end `--ar 16:9 --v 6 --style raw`, negatives via `--no`. DALL-E 3: prose works, add "do not include text in the image unless specified", describe fore/mid/background
separately for complex scenes. Stable Diffusion: `(word:weight)` syntax, CFG 7-12, negative prompt MANDATORY, steps 20-30 draft / 40-50 final. SeeDream: strong artistic/stylized, specify art style before scene, mood/atmosphere descriptors work, negative prompt recommended. → **editing existing** = Template J; **ComfyUI** = Template K.

**3D AI — Text-to-3D (Meshy, Tripo, Rodin)** — style keyword (low-poly/realistic/stylized) + subject + key features + primary material + texture detail + technical spec · negatives supported ("no background, no base, no floating parts") · Meshy best for game assets/teams; Tripo fastest clean topology; Rodin highest quality photorealistic (slower/pricier) · specify export use (game GLB/FBX,
print STL, web GLB) · for characters specify A-pose or T-pose if rigging.

**3D AI — In-Engine (Unity AI, Blender AI)** — Unity AI (6.2+, replaces Muse): `/ask` docs+project, `/run` repetitive Editor tasks, `/code` C# — be precise about the Editor action · Unity generators: text-to-sprite/texture/animation — describe asset type, art style, technical constraints (resolution, palette, loop or one-shot) · BlenderGPT / Blender AI add-ons generate Python that runs in
Blender — be specific about geometry, material names, scene context, add "apply to selected object" / "apply to entire scene".

**Video AI (Sora, Runway, Kling, LTX, Dream Machine)** — Sora: direct it like a film shot, camera movement critical (static vs dolly vs crane) · Runway Gen-3: cinematic language, reference film styles · Kling: strong realistic human motion, describe body movement + camera angle + shot type · LTX: fast, prompt-sensitive, keep concise+visual, specify resolution + motion intensity · Dream Machine
(Luma): cinematic, reference lighting setups, lens types, color grading.

**Voice AI (ElevenLabs)** — specify emotion, pacing, emphasis markers, speech rate directly · use SSML-like markers for emphasis (which words to stress, where to pause) · prose descriptions do not translate — specify parameters directly.

**Workflow AI (Zapier, Make, n8n)** — trigger app + trigger event → action app + action + field mapping, step by step · note auth requirements explicitly ("assumes [app] is already connected") · for multi-step workflows number each step and specify what data passes between steps.

---

## Unknown tool

Identify the closest matching tool category from context. If genuinely unclear, ask "Which tool is this for?" then route. If no listed tool fits, connect to the closest related category and build using its profile + template.
