# Documentation management (on-demand)

Load when creating a plan or changing project documentation. Matches the repo's
markdown-location hard constraint (in CLAUDE.md's Hard constraints) + the
`hs:docs-manager` agent (owner of doc write operations).

## When to update docs

Update only when a change touches: user-visible behavior, setup, commands,
architecture, security posture, public contracts, or decisions for future
maintainers. Do NOT add changelog-noise for purely internal edits unless the
repo already requires it.

Common docs: `docs/code-standards.md`, `docs/system-architecture.md`,
`docs/codebase-summary.md`, `docs/project-roadmap.md` (when present).

## Auto-loaded standards -- keep in sync (no-drift)

`docs/system-architecture.md` (thin) + `docs/code-standards.md` are READ into
context by `hs:plan` / `hs:cook` before they work. A change to architecture-bearing
code (`harness/{hooks,scripts,plugins,data,schemas}`) that shifts what those docs
assert MUST update the matching doc in the same change -- otherwise plan/cook load a
stale map and build on it. Keep both THIN (token-cheap to auto-load); overflow
detail goes to `docs/system-architecture/` (chaptered, not auto-loaded). The
`standards_drift_nudge` hook flags this at turn-end (advisory, default ON) but the
sync is the author's responsibility, not the nudge's.

## Markdown location -- hard constraint

Markdown ONLY created in `docs/` or `plans/` (root README/CLAUDE/BACKLOG/
CONTRIBUTING/CHANGELOG are explicitly approved). Creating outside those two
directories is a violation.
No hook enforces this location rule — it is a convention checked in review
(a CLAUDE.md hard constraint). The `hs:docs-manager` agent's write lane is `docs/`,
`plans/`, and agent-memory (`.claude/agent-memory/**`) — it does not mutate code.

## Plan location

Save plans under `plans/<timestamp>-<descriptive-slug>/`:

```text
plans/<slug>/
  plan.md            # short: status, phases, dependencies, acceptance, phase links
  phase-01-<name>.md # enough detail to execute safely (see below)
  reports/
```

Phase files contain only: context links, requirements, files to create/edit/delete,
execution steps, tests/validation, risks + rollback.

## Procedure

1. **Read the current doc FIRST** before editing -- do not overwrite blindly.
2. After editing: verify **dates, links, and claims** match the actual change.
3. Check size: `wc -l docs/*.md | sort -rn` -- split off a reference file when one grows large.
4. Follow-up items from a review go into `BACKLOG.md`, not a separate review file.

## Rule-layer referential integrity (CS-10)

A rule file (`harness/rules/*.md`) is documentation the same way a doc under
`docs/` is: it must be reachable and it must not point at a ghost. Two invariants,
checked by `harness/scripts/validate_skill_crossrefs.py` (extended, not a new
prose rule -- the comparison is deterministic, so it is pure-script, not
methodology an agent needs to read):

- **No broken rule-ref.** A `harness/rules/<name>.md` cited anywhere in a
  SKILL.md body must resolve to a file that actually exists on disk.
- **No orphan rule.** Every rule file that exists must be **routed** --
  cited in at least one SKILL.md body, **or** named bare in the repo-root
  `CLAUDE.md` routing index (the always-load rules route this second way,
  never a full path).

Writing a new rule file without adding its route-line is the same mistake as
writing a doc nobody links to: the content exists but nothing ever loads it.
Add the route in the SAME change that adds the rule.
