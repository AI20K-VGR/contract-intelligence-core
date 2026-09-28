# Doc triggers — when to trigger docs updates

Loaded at Step 5 (Trigger doc update): decides WHETHER docs need updating, then delegates to `hs:docs-manager` — PM decides *when*; `hs:docs-manager` handles *how*.

Source rule: `"${HARNESS_BIN_ROOT:-.}"/harness/rules/documentation-management.md` — read before triggering.

## Filter principle

Only update docs when a change touches **at least one criterion** below. Purely internal edits (refactors that do not change behavior, local variable renames, comment tweaks) do NOT trigger a doc update — avoid changelog noise.

| # | Trigger criterion | Why |
|---|---|---|
| 1 | **User-visible behavior** changes | Users see a difference, docs must reflect it |
| 2 | **Setup / commands** change | Install, run, or build commands change, onboarding breaks |
| 3 | **Architecture** changes | Module boundaries, data flow, new components |
| 4 | **Security posture** changes | Auth, secret handling, gates, threat surface |
| 5 | **Public contract** changes | Signatures, schemas, env vars, artifact shapes |
| 6 | **Decisions for future maintainers** | Trade-offs, decisions, rationale for a direction |

No criterion matched → **do not** update docs (unless the repo requires a changelog for every edit).

## Trigger-to-doc mapping

| Specific trigger | Docs to check |
|---|---|
| Phase status / plan progress changes | `docs/project-roadmap.md` |
| Major feature completed | `docs/codebase-summary.md`, `docs/project-roadmap.md` |
| API / contract / schema changes | `docs/system-architecture.md`, `docs/code-standards.md` |
| New architecture decision | `docs/system-architecture.md` |
| Breaking change | `docs/code-standards.md` |
| New or changed setup / command | `README.md` (only if explicitly approved), `docs/codebase-summary.md` |
| Security posture changes | `docs/system-architecture.md` |
| Changelog present in repo | `docs/project-changelog.md` |

## Trigger workflow

1. Match the completed change against the 6 criteria above.
2. At least one match → identify the target doc from the mapping table.
3. Read `"${HARNESS_BIN_ROOT:-.}"/harness/rules/documentation-management.md` to confirm update scope.
4. Delegate to `hs:docs-manager` agent with: target doc + change summary + trigger criterion.
5. After `hs:docs-manager` finishes → verify that dates, links, and claims match the actual change.

## Boundaries

- DO NOT update docs directly — always delegate to `hs:docs-manager`.
- DO NOT trigger for internal-only edits that do not touch users, contracts, or architecture.
- DO NOT create markdown outside `plans/` or `docs/` (approved root files are the exception).
- On exit: list which docs were triggered and the criterion, or state clearly "no trigger".
