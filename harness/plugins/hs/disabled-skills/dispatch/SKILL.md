---
name: hs:dispatch
user-invocable: true
injectable: true
description: "Decide who owns a piece of work before any of it starts — answer it directly, route it to one skill, or chain several — and set the quality gate its risk earns. Use when a request is multi-step, spans domains, or has no obvious owner."
when_to_use: "Invoke when the next move is genuinely unclear: the request touches several areas, no single skill obviously owns it, or the risk is high enough that the sequence matters more than the first step."
category: workflow
keywords: [dispatch, route, classify, delegate, proportionality, sequence]
argument-hint: "[the request]"
allowed-tools: [Read, Glob, Grep, Bash]
metadata:
  compliance-tier: workflow
---

# Dispatch

Decide who does the work. Directed routing — the request is known and the question is
ownership. For "does a skill exist for X", that is `hs:find-skills`; for a defect's
lifecycle, `hs:triage`; for sizing a fan-out, `hs:workflow-orchestrate`.

## Step 0 — proportionality gate, always first

Most requests end here, and ending here is the correct outcome, not a shortcut.

| The request | Do |
|---|---|
| Names a skill | Invoke it. Stop routing. |
| One domain, one step, one obviously matching live skill | Invoke it. Stop routing. |
| Conversation, an opinion, a fact question | Answer it. No skill, no subagent. |
| Multi-step, multi-domain, ambiguous, or high-risk | Continue below |

Routing a request that did not need routing costs a turn and a document budget and
returns the same answer. Treat "no obvious owner" as the entry condition, never
"I am not certain".

## Steps 1–3 — classify, inventory, chain

Classify the work by what it changes, not by what it mentions. Then take the inventory
from the engine, never from memory: `hs-run skills next --skill <name>` answers
`target_live` (invoke `/hs:<name>` directly), `target_disabled` (route through
`/hs:use <name>`, which the envelope also hands the stash path and dep order for), or
`target_unknown`. Never propose a skill without that answer, and never propose a raw
`/hs:<name>` for a disabled one.

Chaining rules and the intent→skill table live in
`"${HARNESS_BIN_ROOT:-.}"/harness/rules/skill-routing.md`; the primary-skill precedence
lives in `hs:find-skills`. Do not restate either here — a fifth copy is how they drift.

## Step 4 — where a subagent is worth spawning

Spawn points, sizing, and the group cap are
`"${HARNESS_BIN_ROOT:-.}"/harness/rules/orchestration-protocol.md`. Read it at the moment
before a spawn, which is the only moment its numbers apply.

## Step 5 — the gate the risk earns

The quality gate is a function of what the work can break, not of how long it took.
`hs-run <domain> next` names the gate for that domain's current state; run it and follow
the envelope rather than deciding the gate here.

## Boundaries

| Situation | Owner |
|---|---|
| Pick and sequence live skills, time subagent spawns, in this session | this skill |
| Coordinate headless jobs across runtimes, models, worktrees | `hs:coding-agent-orchestration` |
| Size a fan-out, or convene a panel when several answers are defensible (`--ultra`/`--debate`) | `hs:workflow-orchestrate` |
| Find whether a skill exists at all | `hs:find-skills` |
| Route a measured-improvement goal | `hs:finetune` |
| Run a defect from report to fix | `hs:triage` |
| Execute the domain work | the routed skill |

This skill decides and hands over. It does not implement, and it never reports a routed
skill's result as its own.
