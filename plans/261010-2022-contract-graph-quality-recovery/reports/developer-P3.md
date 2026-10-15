## Phase Implementation Report

### Executed Phase
- Phase: P3 — rubric and reviewed development corpus
- Plan: `plans/261010-2022-contract-graph-quality-recovery`
- Status: partial; blocked on annotation, independent human review, fresh cluster coverage, and HG-QR1

### Files Modified
- `evals/contract_graph/pairs/LABELING.vi.md`
- `evals/contract_graph/pairs/corpus.py`
- `evals/contract_graph/pairs/manifest.py`
- `evals/contract_graph/pairs/review.py`
- `evals/contract_graph/tests/test_cg_pairs_corpus.py`
- `evals/contract_graph/tests/test_cg_pairs_manifest.py`
- `evals/contract_graph/tests/test_cg_pairs_review.py`
- `evals/contract_graph/pairs/quality-recovery-manifest.v1.json` (safe review-packet draft; not a P2 dataset lock)
- `evals/contract_graph/reports/quality-recovery-p3-dev-corpus.json` and `.md`
- `plans/261010-2022-contract-graph-quality-recovery/artifacts/verification.json` and `phase-latest-P3.json` (written through harness `write_verification.py`, verdict `BLOCKED`)

### Tasks Completed
- [x] Clarified rubric decision order, scope/additional obligation distinction, and directed A/B interpretation without changing the model prompt block.
- [x] Added cluster exposure and cross-split validation. Historical held-out exposure propagates to the full cluster.
- [x] Added candidate-independent blind annotation export/import, unique/missing membership checks, direction validation, and second-review coverage/disagreement audit. Human annotations never become approved gold through these APIs.
- [x] Added readiness accounting for per-label positives, negatives, cluster counts/dominance, and immutable non-overwriting v1 dataset file writing compatible with the P2 reader. A review lock is omitted until a separate human decision.
- [x] Generated the 600-row primary packet and 150-row independent packet under ignored `.harness/state/quality-recovery-p3-dev-20261011/`; emitted safe aggregate reports and SHA-256 records. The seed precision frame shares recall membership (`role=both`); actual candidate union remains a P4 prerequisite.
- [ ] Primary and independent annotations, adjudication receipts, and user HG-QR1 approval remain outstanding. No gold or review lock was created.

### Tests Status
- Type/lint check: `py_compile` PASS; no separate lint/type command.
- Unit tests: PASS — focused P3 command, 40 passed.
- Regression tests: PASS — score/predictor command, 69 passed.
- Integration tests: not run beyond planned regression selection.
- `git diff --check`: PASS; existing worktree line-ending warnings only.
- Provider calls: none.

### Issues Encountered
- The staged tranche contains 29 documents and 4,810 pool pairs. A combined near-duplicate audit against historical held-out found one exposed/template-linked document; it and its cluster were excluded.
- The remaining frame is 28 fresh independent clusters, below the P2 planning target of 30 for the retained cluster-Wilson floor. Thresholds remain unchanged.
- No annotation data exists in the staged tranche. The independent sheet is a blind random 25% source×pool-stratum subset; after primary review, its label/negative and ambiguous-row coverage must be audited and topped up if needed.
- The emitted in-repo manifest is intentionally a `contract-graph-p3-review-packet/1` draft. It is not accepted by the P2 quality dataset reader because reviewed gold and human review lock do not exist yet.

### Next Steps
- Obtain a new predeclared source tranche with at least two additional independent clusters after exposure audit; likely more may be needed for each scored label’s cluster coverage.
- Have the user complete the primary CSV and a distinct reviewer complete the independent CSV; adjudicate disagreements with explicit receipts.
- Recompute yield/readiness, prepare the final hash-bound HG-QR1 packet, and wait for user confirmation before creating approved gold or invoking `review-quality-dev-lock`.
- P4 remains blocked until those steps pass.

Harness note: the canonical verification was written through `write_verification.py` with verdict `BLOCKED`. Its snapshot policy does not emit `verification-P3.json` for a first non-PASS result; the packet detail remains in the P3 report artifacts above.

### Update — 2026-10-11

- Added an immutable v2 review packet after source/exposure audit. It contains 34 usable documents, excludes 2 contaminated documents, and retains 31 fresh independent clusters across 32 documents (4,834 fresh pool pairs). The cluster target of 30 is now met; v1 remains unchanged.
- Created new blind primary (600 rows) and independent (150 rows) annotation sheets, with every fresh cluster represented. Decision columns are blank. Files and membership remain in ignored `.harness/state/quality-recovery-p3-dev-20261011-v2/`.
- Produced 600 AI-only primary suggestions using requested `cx/gpt-6-sol` and served `gpt-6-sol`; 600 parsed, 0 request errors. Suggestions: 570 UNRELATED, 27 GENERAL_SPECIFIC, 2 DUPLICATE, 1 REFERENCE, 0 CONFLICT. This distribution is provisional and is not annotation yield, approved gold, or independent human review. The suggestion CSV and audit remain private/ignored and do not modify either blind review sheet.
- P3 remains blocked on primary human decisions, a distinct blind human second reviewer, adjudication/coverage, and user HG-QR1 approval. P4/P5 remain locked.
