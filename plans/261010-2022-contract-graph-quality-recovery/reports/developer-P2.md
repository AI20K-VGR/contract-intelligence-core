# Phase Implementation Report

### Executed Phase
- Phase: P2 — direction-aware quality gates
- Plan: `plans/261010-2022-contract-graph-quality-recovery`
- Status: completed

### Files Modified
- `evals/contract_graph/pairs/score.py` (321 lines)
- `evals/contract_graph/pairs/predictor.py` (704 lines; kept pre-existing P1 telemetry changes)
- `evals/contract_graph/pairs/bakeoff.py` (1302 lines)
- `evals/contract_graph/pairs/run.py` (865 lines)
- `evals/contract_graph/tests/test_cg_pairs_score.py` (165 lines)
- `evals/contract_graph/tests/test_cg_pairs_predictor.py` (558 lines)
- `evals/contract_graph/tests/test_cg_pairs_bakeoff.py` (673 lines)
- `evals/contract_graph/tests/test_cg_pairs_run.py` (152 lines; new)
- `evals/contract_graph/reports/quality-recovery-p2-gates.json` (55 lines) and `.md` (16 lines)
- `plans/261010-2022-contract-graph-quality-recovery/artifacts/verification-P2.json` (26 lines)
- `plans/261010-2022-contract-graph-quality-recovery/reports/developer-P2.md` (34 lines)

### Tasks Completed
- [x] Added direction-aware exact scoring with independent immutable recall and precision frames while preserving legacy scorer semantics.
- [x] Added strict v1 dataset reader, reviewed-gold/frame validation, hashes/counts/path checks, and no legacy fallback.
- [x] Added per-label recall/precision readiness floors, false-DUPLICATE safety gate, cluster precision gate, and raw-evidence recomputation during bakeoff preflight.
- [x] Added independent dev review/report locks and explicit report path plumbing; held-out stays blocked without new-protocol authorization.
- [x] Added deterministic regression coverage and P2 reports. No provider calls; no commit.
- [x] Recorded cluster feasibility: five perfect clusters of 12 yield Wilson cluster lower `0.5655175352168254`; 30 perfect independent clusters of 12 yield `0.9894419431113063`. P3 should retain thresholds, target at least 30 independent clusters as a planning minimum, and check per-label feasibility before human review.

### Tests Status
- Type/lint check: `py_compile` PASS; no separate type/lint command was run.
- Unit tests: PASS — focused suite `153 passed, 1 skipped`.
- Integration/regression tests: PASS — all offline `evals/contract_graph/tests`, `296 passed, 1 skipped`.
- `git diff --check`: PASS.

### Issues Encountered
- Cluster floor `>=5` alone cannot satisfy the retained `>=0.85` cluster-Wilson lower gate: the five-cluster all-success fixture lower is `0.5655175352168254`. The threshold was not weakened. This is a P3 feasibility/data-readiness requirement.
- Product quality remains NOT EVALUATED. No live calls or real-data review were performed in P2.

### Next Steps
- P3 should implement reviewed corpus/manifest creation and check feasible independent-cluster counts for every scored label before asking for human data review; target at least 30 as a planning minimum, derive the actual needed count from observed cluster sizes/outcomes, and keep the system OFF if infeasible.
- P4/P5 remain gated on their planned review and fresh held-out approvals.
