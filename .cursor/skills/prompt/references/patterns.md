# Credit-Killing Patterns Reference

37 patterns that waste tokens and cause re-prompts. Load when the user pastes a bad prompt and asks you to fix it, or when diagnosing why a prompt is underperforming. Scan every user-provided prompt or rough idea for these; fix silently — flag only if the fix changes the user's intent.

---

## Task patterns

| # | Pattern | Bad example | Fixed |
|---|---------|------------|-------|
| 1 | **Vague task verb** | "help me with my code" | "Refactor `getUserData()` to use async/await and handle null returns" |
| 2 | **Two tasks in one prompt** | "explain AND rewrite this function" | Split into two prompts: explain first, rewrite second |
| 3 | **No success criteria** | "make it better" | "Done when the function passes existing unit tests and handles null input without throwing" |
| 4 | **Over-permissive agent** | "do whatever it takes" | Explicit allowed-actions list + explicit forbidden-actions list |
| 5 | **Emotional task description** | "it's totally broken, fix everything" | "Throws uncaught TypeError on line 43 when `user` is null" |
| 6 | **Build-the-whole-thing** | "build my entire app" | Break into Prompt 1 (scaffold), Prompt 2 (core feature), Prompt 3 (polish) |
| 7 | **Implicit reference** | "now add the other thing we discussed" | Always restate the full task — never reference "the thing we discussed" |

---

## Context patterns

| # | Pattern | Bad example | Fixed |
|---|---------|------------|-------|
| 8 | **Assumed prior knowledge** | "continue where we left off" | Include a Memory Block with all prior decisions |
| 9 | **No project context** | "write a cover letter" | "PM role at B2B fintech, 2yr SWE experience transitioning to product, shipped 3 features as tech lead" |
| 10 | **Forgotten stack** | New prompt contradicts prior tech choice | Always include a Memory Block with the established stack |
| 11 | **Hallucination invite** | "what do experts say about X?" | "Cite only sources you are certain of. If uncertain, say so explicitly rather than guessing." |
| 12 | **Undefined audience** | "write something for users" | "Non-technical B2B buyers, no coding knowledge, decision-maker level" |
| 13 | **No mention of prior failures** | (blank) | "I already tried X and it didn't work because Y. Do not suggest X." |

---

## Format patterns

| # | Pattern | Bad example | Fixed |
|---|---------|------------|-------|
| 14 | **Missing output format** | "explain this concept" | "3 bullet points, each under 20 words, with a one-sentence summary at top" |
| 15 | **Implicit length** | "write a summary" | "Write a summary in exactly 3 sentences" |
| 16 | **No role assignment** | (blank) | "You are a senior backend engineer specializing in Node.js and PostgreSQL" |
| 17 | **Vague aesthetic adjectives** | "make it look professional" | "Monochrome palette, 16px base font, 24px line height, no decorative elements" |
| 18 | **No negative prompts for image AI** | "a portrait of a woman" | Add: "no watermark, no blur, no extra fingers, no distortion, no text overlay" |
| 19 | **Prose prompt for Midjourney** | Full descriptive sentence | "subject, style, mood, lighting, composition, --ar 16:9 --v 6" |

---

## Scope patterns

| # | Pattern | Bad example | Fixed |
|---|---------|------------|-------|
| 20 | **No scope boundary** | "fix my app" | "Fix only the login form validation in `src/auth.js`. Touch nothing else." |
| 21 | **No stack constraints** | "build a React component" | "React 18, TypeScript strict, no external libraries, Tailwind only" |
| 22 | **No stop condition for agents** | "build the whole feature" | Explicit stop conditions + ✅ checkpoint output after each step |
| 23 | **No file path for IDE AI** | "update the login function" | "Update `handleLogin()` in `src/pages/Login.tsx` only" |
| 24 | **Wrong template for tool** | GPT-style prose prompt used in Cursor | Adapt to the File-Scope template (Template G) |
| 25 | **Pasting entire codebase** | Full repo context every prompt | Scope to only the relevant function and file |

---

## Reasoning patterns

| # | Pattern | Bad example | Fixed |
|---|---------|------------|-------|
| 26 | **No CoT for logic task** | "which approach is better?" | "Think through both approaches step by step before recommending" |
| 27 | **Adding CoT to reasoning models** | "think step by step" sent to o1/o3 | Remove it — reasoning models think internally, CoT instructions degrade output |
| 28 | **Expecting inter-session memory** | "you already know my project" | Always re-provide the Memory Block in every new session |
| 29 | **Contradicting prior work** | New prompt ignores earlier architecture | Include a Memory Block with all established decisions |
| 30 | **No grounding rule for factual tasks** | "summarize what experts say about X" | "Use only information you are highly confident is accurate. Say [uncertain] if not." |

---

## Agentic patterns

| # | Pattern | Bad example | Fixed |
|---|---------|------------|-------|
| 31 | **No starting state** | "build me a REST API" | "Empty Node.js project, Express installed, `src/app.js` exists" |
| 32 | **No target state** | "add authentication" | "`/src/middleware/auth.js` with JWT verify. `POST /login` and `POST /register` in `/src/routes/auth.js`" |
| 33 | **Silent agent** | No progress output | "After each step output: ✅ [what was completed]" |
| 34 | **Unlocked filesystem** | No file restrictions | "Only edit files inside `src/`. Do not touch `package.json`, `.env`, or any config file." |
| 35 | **No human review trigger** | Agent decides everything autonomously | "Stop and ask before: deleting any file, adding any dependency, or changing the database schema" |
| 36 | **Vague first turn on Opus 4.7 / 4.8** | "fix the auth bug" with no scope, no files, no criteria | Opus 4.7/4.8 read prompts literally — they no longer fill implicit context like 4.6 did. Use Template M. Front-load intent, file scope, constraints, and acceptance criteria. |
| 37 | **Context rot on long sessions** | Keeps correcting in the same session for 60+ turns | New task = new session. Use /rewind instead of correcting. /compact at ~50% context. Subagents for file-heavy investigation. |

---

## Diagnostic checklist

Scan every user-provided prompt or rough idea for these failure classes. Fix silently — flag only if the fix changes the user's intent.

**Task failures** — vague task verb → precise operation · two tasks in one → split into Prompt 1 / Prompt 2 · no success criteria → derive a binary pass/fail from the goal · emotional description ("it's broken") → extract the specific technical fault · scope is "the whole thing" → decompose into sequential prompts.

**Context failures** — assumes prior knowledge → prepend a Memory Block with all prior decisions · invites hallucination → add a grounding constraint ("State only what you can verify. If uncertain, say so.") · no mention of prior failures → ask what they already tried (counts toward the 3-question limit).

**Format failures** — no output format → derive from task type + add an explicit format lock · implicit length ("write a summary") → add a word/sentence count · no role for complex tasks → add a domain-specific expert identity · vague aesthetic ("make it professional") → translate to concrete measurable specs.

**Scope failures** — no file/function boundaries for IDE AI → add an explicit scope lock · no stop conditions for agents → add checkpoint + human-review triggers · entire codebase pasted → scope to the relevant file/function only.

**Reasoning failures** — logic/analysis with no step-by-step → add "Think through this carefully before answering" · CoT added to o3/o4-mini/R1/Qwen3-thinking → REMOVE IT · new prompt contradicts prior session decisions → flag, resolve, include a Memory Block.

**Agentic failures** — no starting state → add current project state · no target state → add a specific deliverable · silent agent → add "After each step output: ✅ [what was completed]" · unrestricted filesystem → add a scope lock on touchable files/dirs · no human-review trigger → add "Stop and ask before: [list destructive actions]".

---

## Memory Block

When the request references prior work, decisions, or session history, prepend this block to the generated prompt. Place it in the **first 30%** of the prompt so it survives attention decay in the target model.

```
## Context (carry forward)
- Stack and tool decisions established
- Architecture choices locked
- Constraints from prior turns
- What was tried and failed
```

This is the single biggest fix for long sessions — most wasted re-prompts come from the AI forgetting what was already decided.

---

## Safe techniques — apply only when genuinely needed

**Role assignment** — for complex/specialized tasks, assign a specific expert identity. Weak: "You are a helpful assistant". Strong: "You are a senior backend engineer specializing in distributed systems who prioritizes correctness over cleverness".

**Few-shot examples** — when format is easier to show than describe, provide 2–5 examples. Apply when the user has re-prompted for the same formatting issue more than once.

**Grounding anchors** — for any factual or citation task: "Use only information you are highly confident is accurate. If uncertain, write [uncertain] next to the claim. Do not fabricate citations or statistics."

**Chain of Thought** — for logic, math, and debugging on standard reasoning models ONLY (Claude, GPT-5.x, Gemini, Qwen2.5, Llama). NEVER on o3/o4-mini/R1/Qwen3-thinking. "Think through this step by step before answering."

---

## Excluded techniques — why each is fabrication-prone (single-prompt)

Prefer the safe techniques above. The following carry higher fabrication risk in a single prompt and should be applied ONLY when the user explicitly requests them AND the target tool supports them:

- **Mixture of Experts** — simulated multi-persona routing in a single forward pass (no real routing happens).
- **Tree of Thought** — simulated branching without real parallel execution.
- **Graph of Thought** — requires an external graph engine not present in most tools.
- **Universal Self-Consistency** — requires independent sampling passes the tool may not run.
- **Prompt chaining as a layered technique** — compounds fabrication risk across longer chains.

---

## Agentic output warning

For prompts targeting agentic tools (Claude Code, Devin, Cursor, Windsurf, Cline, Bolt, SWE-agent, Manus, or anything that executes commands or edits files — mandatory for Templates G, H, M and any prompt referencing filesystem, terminal, dependency, or database operations), append this notice:

> "This prompt is for an agentic tool with real system access. Review the scope locks, forbidden actions, and stop conditions before pasting. Confirm file paths, directories, and permissions match the actual project."

---

## Fabrication-prone techniques — why each is risky (apply only on explicit request + a supporting tool)

These carry higher fabrication risk in a single-prompt context. Do NOT reach for them by default; the reason each is risky is the signal for whether the target tool can support it:

- **Mixture of Experts** — simulated multi-persona routing in a single forward pass (no real routing happens).
- **Tree of Thought** — simulated branching without real parallel execution.
- **Graph of Thought** — requires an external graph engine not present in most tools.
- **Universal Self-Consistency** — requires independent sampling passes the single call cannot do.
- **Prompt chaining as a layered technique** — compounds fabrication risk across the longer chain.

Prefer role assignment, few-shot, grounding anchors, and (on standard reasoning models only) chain of thought — see "Safe techniques" above.

