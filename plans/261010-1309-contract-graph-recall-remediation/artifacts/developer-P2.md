# P2 developer record

- Added a deterministic dev-only engineering target assessment to `candidate_eval.py` and preserved S4/HG-1 metadata when regenerating the candidate report.
- Measured frozen dev coverage: 15/24 overall; CONFLICT 3/5, DUPLICATE 2/2, GENERAL_SPECIFIC 8/13, REFERENCE 2/4; S1 6/6 and S3 9/18.
- Decision: `KEEP_CURRENT`. The 95% per-label target is not met, but adding a new candidate rule would change the frozen S4/HG-1 universe and require a new human HG-2 review. No candidate version, top_k, manifest, S4 files, or review decisions changed.
- Report: `evals/contract_graph/reports/l2-p2-candidates.json` and `.md`; it records the label/stratum gaps and the P3 handoff without clause text.
- Evidence: candidate/eval tests 229 passed; pair-candidate tests 23 passed.
