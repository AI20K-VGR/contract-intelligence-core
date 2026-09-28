---
name: hs:context-engineering
injectable: true
description: >-
  Manage the context budget — check limits, optimize tokens, coordinate subagents,
  debug context failures. Use when context is nearly full, designing multi-agent,
  or deciding what to load or drop.
argument-hint: "(no arguments)"
allowed-tools: [Bash, Read, Grep, Glob]
metadata:
  compliance-tier: workflow
---

# hs:context-engineering — context budget

Select the highest-signal tokens for the task — maximize reasoning quality, minimize token cost. **No code writing.** Output = load/drop decisions, a compaction strategy, or task fragmentation for subagents.

**Evidence rule**: `"${HARNESS_BIN_ROOT:-.}"/harness/rules/verification-mechanism.md` — all claims about context must be measurable (%, token count) or tagged `[ASSUMED]` (or `[PRIOR]` if the figure rests on prior/training knowledge).

## Four core strategies

| Strategy | When | Effect |
|---|---|---|
| **Write** | large output that must be preserved | write to file, do not keep in session |
| **Select** | load on need | hs:scout first, load the right file, no broadcasting |
| **Compress** | context >= 70% | anchored-iterative compaction; prioritize dropping old tool output |
| **Isolate** | parallel tasks / heavy context | fragment via subagent, each agent gets a clean context |

## Action thresholds

| Level | Context % | Action |
|---|---|---|
| Normal | < 70% | continue, passively monitor |
| Warning | 70-80% | plan compaction; prefer Isolate for parallel tasks |
| Urgent | 80-90% | execute compaction; write artifacts to file |
| Critical | > 90% | compact immediately or reset session; delegate to subagent |

## Process — what to load and when

1. **Scout first, load second** — use hs:scout to locate files/symbols; load only the relevant portion, not the entire codebase.
2. **Progressive disclosure** — load in layers: metadata (100 words) -> SKILL.md body -> references/ (only when more depth is needed).
3. **Place important information at the start or end** — attention U-shape: the middle of context is lost most often. Decisions, constraints, requirements -> start or end.
4. **Trigger compaction** — at >= 70%: load `references/compaction-guide.md`; anchored-iterative summary (keep: decisions, edited files, next steps; drop: old tool output, settled debates).
5. **Isolate via subagent** — parallel tasks or heavy context: load `references/subagent-delegation.md`; each subagent receives minimal context (question + specific files + acceptance criteria), not the full history.
6. **Pack with hs:repomix** — when an entire module must be loaded into an LLM at once: use hs:repomix pack -> compact XML/MD file; avoid loading individual files separately.

## Subagent coordination (orchestration rule)

- **Do not pass full history** — summarize only the decisions needed; do not paste old conversation.
- **Clear file ownership** — parallelism only when no shared files; avoid parallel edits to the same file.
- **Return minimal context to controller** — subagent returns summary + file paths; controller does not need to re-read full subagent output.
- **See** `"${HARNESS_BIN_ROOT:-.}"/harness/rules/workflow-handoffs.md` #5 — context isolation before cook: after plan approval, `/clear` is RECOMMENDED before cooking from a clean context.

## Boundaries

- Do NOT write code, do NOT edit plans, do NOT commit.
- Load/drop decisions must be based on real measurements (context %) or task scope assessment — no guessing.
- On completion: return a specific action list (files to load / strategy to apply / subagents to spawn) + brief rationale.

## Real wiring

| Mechanism | File/rule |
|---|---|
| Orchestration pattern | `"${HARNESS_BIN_ROOT:-.}"/harness/rules/workflow-handoffs.md` |
| Context isolation | nobody's — the advisory that watched for it ships disabled |
| No-code-writing boundary | no Write/Edit/MultiEdit in `allowed-tools` (advisory only — Bash-mediated writes are not enforced) |
| Scout files before loading | skill hs:scout |
| Pack module compactly | skill hs:repomix |

## Scripts / Automation

Two scripts under `"${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/context-engineering/scripts/` provide automated measurement, **augmenting** (not replacing) the manual 70/80/90% thresholds above.

| Script | Purpose | Key command |
|---|---|---|
| `scripts/context_analyzer.py` | Score context health; detect lost-in-middle + poisoning risk | `analyze <transcript.json>` · `budget --system … --history …` |
| `scripts/compression_evaluator.py` | Measure before/after compression ratio; probe quality across 6 dimensions | `evaluate <original.json> <summary.txt>` · `generate-probes <context.json>` |

Both scripts are stdlib-only. Output is JSON — pipe into `jq` or consume programmatically. Tests live in `harness/tests/test_context_engineering_scripts.py`.

## References (load when needed)

| Topic | When to load |
|---|---|
| `references/compaction-guide.md` | context >= 70%, compaction plan needed |
| `references/subagent-delegation.md` | designing multi-agent, fragmenting tasks |
| `references/what-to-load-when.md` | unsure which files to load |
| `references/token-budget.md` | need to estimate token cost before loading |
| `references/degradation-patterns.md` | quality dropped (forgets reqs, repeats a corrected error, mixes tasks) — name the failure mode |
| `references/tool-design.md` | designing the tools/interfaces an agent calls — naming, granularity, error surfaces |
| `references/memory-systems.md` | need persistent context beyond the window — memory architectures and retrieval |
