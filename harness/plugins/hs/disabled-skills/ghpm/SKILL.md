---
name: hs:ghpm
injectable: false
description: "GitHub project management for humans and AI agents. Use for issue/task planning, Projects boards, handoff status, gh/API automation, and CI-driven work tracking."
allowed-tools: [Bash, Read, Write, Edit, Glob, Grep]
argument-hint: "[bootstrap|intake|execute|handoff|audit]"
metadata:
  compliance-tier: workflow
---

# GHPM

GitHub = single source of truth (SSOT) for project work, human+AI shared. Handles task intake, triage, issue/project schemas, status updates, handoff logs, GitHub automation via `gh`, `git`, GraphQL, REST, Actions. Does NOT replace product judgment, private planning, secrets management, code review.

## Security

- Never paste secrets into issues, project fields, PR bodies, workflow logs, or comments.
- Treat public repos as public evidence ledgers; redact customer data and credentials.
- Use least-privilege tokens. For Projects, verify `project` scope before edits: `gh auth status`.
- Prefer `GH_TOKEN` in Actions; do not write PATs to workflow files.
- If a task needs private data, store only a pointer: owner, system, access request, and redacted summary.

## Use When

- User asks to manage tasks, status, roadmap, project boards, issue labels, GitHub Projects, or handoff/handover.
- Work spans humans + AI agents and needs durable context between sessions.
- Need convert chat/plans/TODOs into GitHub Issues with evidence, owners, dependencies, status.
- Need chain skills into execution pipelines and report progress from GitHub state.
- Need automate triage/status/comments with GitHub Actions or `gh api`.

## Core Model

Use GitHub primitives deliberately:

| Primitive | Role |
| --- | --- |
| Issue | Atomic task, bug, decision, or milestone slice |
| Issue body | Contract: context, acceptance criteria, handoff log |
| Labels | Stable routing: type, priority, area, risk, agent/human lane |
| Project | Live board: status, iteration, owner, estimate, target |
| PR | Execution evidence linked to issues |
| Actions | Automation worker for triage, reminders, stale checks, reports |
| Comments | Append-only handoff log and decision trail |
| Branch | Work-in-progress pointer linked to issue/PR |

Prefer Projects `Status` for live state; labels for taxonomy/search. No Project? Use `status:*` labels as fallback.

## Workflow

1. Orient repo and auth:
   ```bash
   git remote -v
   gh repo view --json nameWithOwner,defaultBranchRef,owner
   gh auth status
   gh project list --owner OWNER
   gh issue list --state open --limit 50 --json number,title,labels,assignees,updatedAt
   ```

2. Choose operating mode:
   - **Bootstrap**: create labels, project fields, templates, automation.
   - **Intake**: turn request/plan/chat into GitHub issues.
   - **Execute**: link branch/PR/checks to issues, update status.
   - **Handoff**: write current state, blockers, commands, next owner.
   - **Audit**: compare GitHub state against local repo/plans/CI.

3. Load only needed references:
   - `references/schema-and-taxonomy.md` for labels, fields, issue body contract.
   - `references/command-cookbook.md` for `gh`, GraphQL, REST, and Actions snippets.
   - `references/skill-pipelines.md` for chained workflows with other skills.

4. Update GitHub first, then local artifacts:
   - If a task changes, update issue/project/comment.
   - If code changes, link PR/branch/checks back to the issue.
   - If docs/plans change, put the canonical task state in GitHub and link local files.

5. Report from evidence:
   - Cite issue/PR/project URLs, check names, branch names, timestamps.
   - End with unresolved questions only if GitHub/current repo cannot answer them.

## Task Contract

Every task issue should contain:

```markdown
## Outcome
What done means.

## Context
Relevant repo, branch, files, links, constraints.

## Acceptance Criteria
- [ ] Verifiable condition

## Handoff Summary
- YYYY-MM-DD HH:mm TZ - actor: state, evidence, next step. (last-known-state only, overwrite each time)

## Skill Chain
Suggested skills and order, e.g. hs:scout -> hs:plan -> hs:cook -> hs:test -> hs:git -> hs:ship.
```

Issue body = contract; `Handoff Summary` holds only current state. Append chronological entries as comments only, using Handoff Comment Template in `references/schema-and-taxonomy.md`.

## Operating Rules

- Use `gh` first for normal operations; use `gh api graphql` when Projects fields need precise reads/writes.
- Never silently create broad label taxonomies; inspect existing labels and extend minimally.
- Keep statuses mutually exclusive: one live status only.
- Record blockers as both field/label and comment with owner + unblock condition.
- Prefer issue dependencies/sub-issues when available; otherwise cross-link with `Blocked by #N` and `Blocks #M`.
- For AI handoff, include exact commands already run, tests/checks result, touched files, and next safe command.
- For humans, summarize current decision, risk, and what needs approval.

## Quick Commands

Load `references/quick-commands.md` — copy-paste `gh` snippets for create-task, update-state, link-branch, and trigger-automation.

## Output Format

When using this skill, return concise evidence-based status:

```markdown
**GHPM Status**
- Repo: OWNER/REPO
- Project: URL or none
- Issues: #N title [status, owner, priority]
- Actions: workflow/check result
- Handoff: last comment URL, next owner/action

Unresolved questions:
- None
```
