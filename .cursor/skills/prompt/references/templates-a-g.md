# Prompt Templates A–G

Template library for `hs:prompt`, part 1 of 2. Load the one template that matches the task type — do not load everything at once. Templates H–M live in `templates-h-m.md`.

## Table of contents (all 13)

| Template | Best for | File |
|----------|----------|------|
| A — RTF | Simple one-shot tasks | this file |
| B — CO-STAR | Professional documents, business writing | this file |
| C — RISEN | Complex multi-step projects | this file |
| D — CRISPE | Creative work, brand voice | this file |
| E — Chain of Thought | Logic, math, analysis, debugging | this file |
| F — Few-Shot | Consistent structured output, pattern replication | this file |
| G — File-Scope | Cursor, Windsurf, Copilot — code-editing AI | this file |
| H — ReAct + Stop Conditions | Claude Code, Devin — autonomous agents | `templates-h-m.md` |
| I — Visual Descriptor | Midjourney, DALL-E, Stable Diffusion, Sora | `templates-h-m.md` |
| J — Reference Image Editing | Editing an existing image with a reference | `templates-h-m.md` |
| K — ComfyUI | ComfyUI node-based image workflows | `templates-h-m.md` |
| L — Prompt Decompiler | Break down / adapt / split existing prompts | `templates-h-m.md` |
| M — Opus 4.7 / 4.8 Task Brief | Complex, multi-step, or agentic task on Claude Opus | `templates-h-m.md` |

---

## Template A — RTF

*Role, Task, Format. Fast one-shot tasks where the request is clear and simple.*

```
Role: [One sentence defining who the AI is]
Task: [Precise verb + what to produce]
Format: [Exact output format and length]
```

**Example:**
```
Role: You are a senior technical writer.
Task: Write a one-paragraph description of what a REST API is.
Format: Plain prose, 3 sentences maximum, no jargon, suitable for a non-technical audience.
```

---

## Template B — CO-STAR

*Context, Objective, Style, Tone, Audience, Response. Professional documents, business writing, reports, marketing — where full context control matters.*

```
Context: [Background the AI needs to understand the situation]
Objective: [Exact goal — what success looks like]
Style: [formal / conversational / technical / narrative]
Tone: [authoritative / empathetic / urgent / neutral]
Audience: [Who reads this — knowledge level and expectations]
Response: [Format, length, and structure of the output]
```

**Example:**
```
Context: I am a founder pitching a B2B SaaS tool that automates expense reporting for mid-size companies.
Objective: Write a cold email that gets a reply from a CFO.
Style: Direct and conversational, not salesy.
Tone: Confident but not pushy.
Audience: CFO at a 200-person company, busy, skeptical of vendor emails.
Response: 5 sentences max. Subject line included. No bullet points.
```

---

## Template C — RISEN

*Role, Instructions, Steps, End Goal, Narrowing. Complex projects, multi-step tasks, any output needing a clear sequence.*

```
Role: [Expert identity the AI should adopt]
Instructions: [Overall task in plain terms]
Steps:
  1. [First action]
  2. [Second action]
  3. [Continue as needed]
End Goal: [What the final output must achieve]
Narrowing: [Constraints, scope limits, what to exclude]
```

**Example:**
```
Role: You are a product manager with 10 years of experience in mobile apps.
Instructions: Write a product requirements document for a habit tracking feature.
Steps:
  1. Define the problem statement in one paragraph
  2. List user stories in the format "As a [user], I want [goal] so that [reason]"
  3. Define acceptance criteria for each story
  4. List out-of-scope items explicitly
End Goal: A PRD an engineering team can begin sprint planning from immediately.
Narrowing: No technical implementation details. No wireframes. Under 600 words total.
```

---

## Template D — CRISPE

*Capacity, Role, Insight, Statement, Personality, Experiment. Creative work, brand voice, any task where personality, tone, and iteration matter.*

```
Capacity: [What capability or expertise the AI should have]
Role: [Specific persona to adopt]
Insight: [Key background insight that shapes the response]
Statement: [The core task or question]
Personality: [witty / authoritative / casual / sharp]
Experiment: [Request variants or alternatives to explore]
```

**Example:**
```
Capacity: Expert copywriter specializing in SaaS product launches.
Role: Brand voice for a productivity tool aimed at developers.
Insight: Developers hate marketing speak and respond to honesty and specificity.
Statement: Write the hero headline and sub-headline for the landing page.
Personality: Sharp, dry, confident — no adjectives, no exclamation marks.
Experiment: Give 3 variants ranging from minimal to bold.
```

---

## Template E — Chain of Thought

*Logic-heavy tasks, math, debugging, multi-factor analysis where the AI must reason carefully before committing.*

**Important:** Only use CoT for standard reasoning models (Claude, GPT-4o, Gemini). Do NOT add CoT to o1/o3 or Claude extended thinking — they reason internally and CoT instructions degrade their output.

```
[Task statement]

Before answering, think through this carefully:
<thinking>
1. What is the actual problem being asked?
2. What constraints must the solution respect?
3. What are the possible approaches?
4. Which approach is best and why?
</thinking>

Give your final answer in <answer> tags only.
```

**When to use:** debugging where the cause is not obvious · comparing two technical approaches · any math or calculation · analysis where a wrong first impression is likely.
**When NOT to use:** o1 / o3 / reasoning models · simple tasks where the answer is clear · creative tasks (CoT can kill natural voice).

---

## Template F — Few-Shot

*When the output format is easier to show than describe. Examples outperform written instructions for format-sensitive tasks every time.*

```
[Task instruction]

Here are examples of the exact format needed:

<examples>
  <example>
    <input>[example input 1]</input>
    <output>[example output 1]</output>
  </example>
  <example>
    <input>[example input 2]</input>
    <output>[example output 2]</output>
  </example>
</examples>

Now apply this exact pattern to: [actual input]
```

**Rules:** 2–5 examples is the sweet spot (more rarely helps, wastes tokens) · include edge cases, not just easy cases · wrap examples in XML tags (Claude parses XML reliably) · if you have re-prompted for the same formatting correction twice, switch to few-shot instead of rewriting instructions.

---

## Template G — File-Scope

*Cursor, Windsurf, GitHub Copilot, any AI that edits code inside a codebase. The most common failure here is editing the wrong file or breaking existing logic — this template prevents both.*

```
File: [exact/path/to/file.ext]
Function/Component: [exact name]

Current Behavior:
[What this code does right now — be specific]

Desired Change:
[What it should do after the edit — be specific]

Scope:
Only modify [function / component / section].
Do NOT touch: [list everything to leave unchanged]

Constraints:
- Language/framework: [specify version]
- Do not add dependencies not in [package.json / requirements.txt]
- Preserve existing [type signatures / API contracts / variable names]

Done When:
[Exact condition that confirms the change worked correctly]
```
