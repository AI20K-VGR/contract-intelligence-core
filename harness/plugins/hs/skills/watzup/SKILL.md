---
name: hs:watzup
injectable: true
description: "Generate short handoff reports from Git branches, remote refs, worktrees, unfinished plans, and roadmap docs. Surfaces priority-ranked next steps with checkbox progress and rationale. Use when the user asks what's in flight, wants progress/next steps, is in a fresh worktree or detached checkout, or needs end-of-session status."
allowed-tools: [Bash, Read, Glob, Grep]
argument-hint: "[--fetch]"
metadata:
  compliance-tier: workflow
---

# Wrap Up

Create a short, evidence-backed handoff report for the active project, with priority-ranked next steps grounded in plan progress and roadmap state.

Handles status/handoff reporting only -- no implement, edit, commit, checkout, merge, push, fetch unless user explicitly requests fresh remote refs.

For **conversation-state** compaction (redacted handoff from live session for a fresh agent, not git-derived status) use `hs:handoff` instead.

## Required Scan

Run scanner first, from project root:

```bash
node "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/watzup/scripts/watzup-scan.cjs --json
```

Use `--fetch` only when user asks to refresh remotes before report:

```bash
node "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/watzup/scripts/watzup-scan.cjs --json --fetch
```

Default behavior:
- Scan local branches and remote branch refs.
- Scan registered worktrees.
- Scan unfinished plans from visible worktrees and tracked branch refs.
- Count `- [ ]` / `- [x]` checkboxes in each plan directory (all `.md` files at the plan-dir root + all `.md` files under `phases/`) for progress %.
- Scan the top-level `docs/` folder (non-recursive) for filenames ending in `roadmap.md` or `milestone(s).md`.
- Build priority-ranked next steps via composite scoring (see below).
- Do not run network operations.
- Do not change branches or mutate the checkout.

## Priority Ranking

Scanner emits `nextSteps[]` pre-ranked as objects with `{priority, action, rationale, planId?}` — status, workspace alignment (current worktree/branch), provenance, momentum (mid-progress plans bumped) each feed composite score; use emitted `rationale`, do not recompute weights.

Hygiene steps (dirty working tree, detached HEAD) always rank first. Roadmap milestones fill remaining slots after plan-driven actions.

## Report Format

Keep output brief. Prefer this structure:

1. **Current State** - branch or detached HEAD, dirty/clean, active worktree.
2. **Recent Work** - only the highest-signal branches/worktrees.
3. **In-Flight Plans** - unfinished plans with `X/Y todos · NN% done` annotation.
4. **Roadmaps** - active milestones from top-level `docs/*roadmap.md` / `docs/*milestone(s).md` files, if any.
5. **Next Steps** - 5 to 6 priority-ranked actions, each with one-line rationale.
6. **Warnings** - scanner failures, stale remote-ref caveat, detached HEAD.

If scanner fails, say so + include error. Then use minimal read-only fallback commands:

```bash
git status --short --branch
git worktree list --porcelain
git for-each-ref --format='%(refname:short) %(committerdate:iso8601) %(objectname:short) %(subject)' refs/heads refs/remotes
find plans -maxdepth 2 -name plan.md -print
find docs -maxdepth 2 -iname '*roadmap*.md' -print
```

Do not pretend full scan completed when fallback used.
