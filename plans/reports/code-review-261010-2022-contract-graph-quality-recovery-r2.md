# Code Review — 261010-2022-contract-graph-quality-recovery (round 2)

## Code Review Summary

### Scope

- Files: 13 changed P4T/P4U files — candidate generation, pair classification/building/projection, evaluation prediction/diagnostics, and their focused tests.
- Diff size: 961 additions, 54 deletions.
- Focus: approved plan scope, with emphasis on P4T/P4U. Other dirty worktree files were excluded because the plan marks them as pre-existing/out of scope.
- Scout findings: traced candidate generation through `build_pair_relations()` and eval `predict_doc()`; checked that diagnostic events carry only pair/node ids, outcome/reason, model identifiers, and truncation flags, not clause text or provider payloads. No async/shared-state path was added.
- Plan: P1–P4U technical verification receipts are PASS; P5 evaluation was waived. This review did not inspect held-out/evaluation data or call a model.

### Overall Assessment

PASS for the reviewed technical scope. The new `VALUE_MISMATCH` expansion has a deterministic eight-entry posting window and a counter for comparisons; abstentions have a distinct diagnostic class and an aggregate coverage count. Offline regressions pass. This verdict makes no recall, precision, or product-quality claim; product quality remains NOT_EVALUATED and runtime remains OFF.

### Critical Issues

None.

### High Priority

None.

### Medium Priority

None.

### Low Priority

- Suggestion — `evals/contract_graph/pairs/recall_diagnostic.py:146`: JSON with a list/dict in `phase` (or `outcome` at line 149) raises `TypeError` during set membership instead of following the malformed-event filter. A direct synthetic call reproduced `TypeError: unhashable type: 'list'`. Validate that these fields are strings (while allowing `None` for phase) before membership checks. Dismissal lookup: no prior dismissal found (`cb15ab005a841e17`).

### Edge Cases Found by Scout

- Synthetic high-frequency term coverage confirms the new VALUE_MISMATCH pair-comparison loop is bounded by posting size times the configured window.
- The existing SAME_ARTICLE and SAME_KEY generators still enumerate all pair combinations before top-K selection (`pair_candidates.py:208`, `pair_candidates.py:223`). This is outside the P4U change, but top-K does not bound that earlier work. Keep the feature OFF until realistic input-size limits or bounded generation for those sources are part of product-readiness work.
- The runtime abstention counter is an aggregate; per-pair events remain in the optional evaluation callback. The result schema keeps `coverage` as an open object.

### Positive Observations

- Abstention increments the explicit counter and remains unclassified; it does not create a relation.
- Candidate behavior changes advance `CANDIDATES_VERSION`; the prompt version is separately tracked.
- Consent, egress, model-family, citation grounding, and review-only relation boundaries remain in the existing builder path.

### Recommended Actions

1. Add type guards for malformed diagnostic `phase` and `outcome` values.
2. Before enabling runtime, bound or impose an evidenced input cap on SAME_ARTICLE and SAME_KEY all-pairs work.
3. Keep product-quality gates NOT_EVALUATED until explicitly authorized evaluation is performed on eligible data.

### Metrics

- Type/Lint Coverage: Ruff passed on the reviewed Python source and tests; no static type checker was run.
- Test Coverage: percentage not measured; focused offline regression result: 129 passed in 1.38s.
- Linting Issues: 0.
- Fan-in (data only): unavailable; the worktree has no `codemap.yaml`.
- Additional check: `git diff --check` passed for the reviewed files.

### Unresolved Questions

- Product recall, precision, direction accuracy, and abstention rate remain unmeasured by user decision.
- Runtime stays OFF. The all-pairs work on SAME_ARTICLE/SAME_KEY needs a separate boundedness decision before enablement.
