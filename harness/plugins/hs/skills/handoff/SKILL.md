---
name: hs:handoff
description: Create a concise, redacted conversation handoff for a fresh agent session. Use when switching context, ending a work session, or preserving decisions and blockers.
user-invocable: true
when_to_use: Invoke for conversation-state compaction, not a git-derived project status report.
category: utilities
keywords: [handoff, session, context, decisions, blockers]
argument-hint: "[next-session focus] [--dispatch <runtime>]"
injectable: false
allowed-tools: [Read, Glob, Grep, Write, Bash]
metadata:
  compliance-tier: workflow
---

# Handoff

Create factual, compact handoff letting a fresh agent continue with minimal
rediscovery — preserve state and rationale, not a next-agent command list.

## Workflow

1. Read project instructions and relevant plans before drafting. Read prior
handoff if one exists for same focus.
2. Capture goal, current state, key decisions+rationale, rejected approaches,
blockers, verification status, pointers to source artifacts.
3. Reference plans, issues, ADRs, commits, diffs, tests instead of copying them
into handoff.
4. Redact secrets, tokens, passwords, private URLs, customer data, personal
data. Mention only safe credential location when needed.
5. Output one fenced Markdown block; save same content under
plans/reports/handoff-YYYYMMDD-HHmm-<slug>.md. If project has no plans
directory, ask user for safe output location first.

6. **Dispatch (only with `--dispatch <runtime>`).** Capture first, always: never
dispatch without the artifact already saved. Check the runtime is declared in
`"${HARNESS_BIN_ROOT:-.}"/harness/data/runtime-targets.yaml` — refuse a name that is not there rather than
substituting a near match. Then route to `hs:coding-agent-orchestration --single`
with the saved artifact path, and instruct the successor to read that artifact
before acting. That skill owns runtime selection, safety gates, and consolidation;
do not re-implement any of it here. Report the artifact path, the runtime, and the
job result.

## Required Shape

    # HANDOFF: <short title>
    Generated: <timestamp> · Session focus: <one line>

    ## Goal
    ## Why This Matters
    ## Current State
    ## Key Decisions and Why
    ## Rejected Approaches and Traps
    ## Verification Status
    ## Relevant Files and Pointers
    ## Open Work and Dependencies

Describe open work as state and dependencies, not imperatives. End with short
fresh-agent prompt telling next agent to read listed files and verify handoff
against repository before acting.

## Boundaries

- Use hs:watzup for status report derived from branches, worktrees, plans,
repository history.
- Do not duplicate root project instructions or introduce new decisions.
- Never write a handoff outside the agreed project or reports location.
- Without `--dispatch`, stop after saving. Capture and dispatch are separate acts,
and handing work to another runtime is not something to infer from a request to
write a handoff.
