# Preflight gate (before the cut)

`release_orchestrator.preflight()` is a hard gate — any failure aborts before step 1, so a broken tree never gets a tag. Checks, in order:

1. **decisions reconciled** — refuse the cut while the Decision Register has drifted (new DECs / flips) since the last reconcile marker. Cheapest, first.
2. **docs structure** — `docs-standardize/scripts/docs_gate.py --fresh` must pass (exit 2 on a `severity=error`: missing frontmatter / broken graph invariant). Release VERIFIES doc structure — it never regenerates content. Stale/broken docs → abort; refresh + commit them first, then cut.
3. **local CI** — `bash scripts/ci_local.sh` must be green (unit, invariants, schema, ownership, standards, footprint, e2e). Red CI → abort.
4. **skill structure** — `check_skill_structure.py --strict` over the skills root.
5. **skill cross-refs** — `validate_skill_crossrefs.py` (no broken references).
6. **clean tree** — `git status --porcelain` must be empty; the manifest the cut hashes has to match the release commit, so uncommitted tracked changes abort.
7. **gh auth** — `gh auth status` must succeed; step 3 needs it.

The two cheap structural gates (reconcile, docs) run before heavy CI so a predictable failure surfaces without paying for the full suite first.

**Scope note:** the docs gate only covers structural docs under `docs/` (the frontmatter + graph tree; `.docsignore` exclusions apply). It does NOT touch root `*.md` (README/CLAUDE/BACKLOG) and does NOT judge content freshness — stale prose is an authoring step you run + review before the cut, not something release generates.

If preflight aborts, fix the cause and re-run the dry-run checklist — the engine has written nothing yet.
