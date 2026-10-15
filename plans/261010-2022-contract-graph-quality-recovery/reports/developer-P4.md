## Phase Implementation Report

### Executed Phase
- Phase: P4 — bounded development experiments
- Plan: `plans/261010-2022-contract-graph-quality-recovery`
- Status: implementation and offline regression pass; empirical quality gate blocked.

### Files changed for this phase
- `ai-service/app/pipeline/contract_graph/pair_candidates.py`
- `ai-service/app/pipeline/contract_graph/pair_classifier.py`
- `ai-service/app/pipeline/contract_graph/pair_builder.py`
- `evals/contract_graph/pairs/predictor.py`
- `ai-service/tests/test_contract_graph_pair_candidates.py`
- `ai-service/tests/test_contract_graph_pair_classifier.py`
- `evals/contract_graph/tests/test_cg_pairs_candidate_eval.py`
- `evals/contract_graph/tests/test_cg_pairs_predictor.py`
- Safe aggregate report: `evals/contract_graph/reports/quality-recovery-p4-development.json` and `.md`

### Work and findings
- Added malformed quality-frame role/direction validation; the new cases failed first with `TypeError`, then passed after guards returned `ValueError`.
- Added deterministic core-candidate preservation for C. Under the same cap, C preserves B’s top-K core candidates before using remaining slots for exploratory sources. Candidate version advanced to `pairs-cand-v3` so old reports cannot be reused.
- The approved dev frame gives B/40 coverage 10/37 positives; C/40 gives 11/37, C/80 gives 13/37, and uncapped C gives 29/37 at 11,143 candidates. Uncapped analysis found 8 misses (5 GENERAL_SPECIFIC, 3 REFERENCE), all absent from current source rules.
- Ran the registered 20-pair oracle and four bounded repeats on the same HG-QR1 dev sample. Baseline measured 14/20 twice; checklist measured 15/20 and 14/20; worst-trial total and per-label results tie, so baseline remains selected. No false DUPLICATE in any of the four repeats.
- Added a real, versioned checklist prompt ablation and test coverage; its two repeats did not establish a winner.
- No provider call touched held-out data. P5 remains closed. Runtime flag remains OFF.

### Tests
- Candidate/classifier/eval: **100 passed** after the prompt ablation was added.
- Builder/consent/flag/predictor regression: **105 passed in 144.10s**.
- Candidate preservation test: intentional red before implementation, green after.

### Remaining blockers
- The user accepted continuation on this small approved set (1 CONFLICT, 2 DUPLICATE, 27 GENERAL_SPECIFIC, 7 REFERENCE) and waived second human review. This waiver does not lower the Wilson recall floor; observed CONFLICT recall is 0/1.
- C uncapped misses 8/37 approved positive pairs under current source rules and produces 11,143 candidates.
- The user explicitly waived independent second human annotation; the AI annotation remains accurately labeled and is not represented as human review.
- The P4 development gate is BLOCKED; this report does not claim quality PASS.
