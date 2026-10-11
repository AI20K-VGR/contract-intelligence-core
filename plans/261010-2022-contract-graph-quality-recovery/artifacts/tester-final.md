# Independent offline test report

Reviewer role: hs:tester (independent run, 2026-10-11)

- Focused plan suite with `PYTHONPATH=ai-service;.` and repo virtualenv: `ai-service/tests/test_contract_graph_pair_candidates.py ai-service/tests/test_contract_graph_pair_classifier.py ai-service/tests/test_contract_graph_pair_projection.py ai-service/tests/test_contract_graph_pair_builder.py evals/contract_graph/tests/test_cg_pairs_recall_diagnostic.py evals/contract_graph/tests/test_cg_pairs_candidate_eval.py -m 'not live' --basetemp .harness/state/tester-quality-final` — 178 passed.
- Offline eval tooling suite: `evals/contract_graph/tests -m 'not live' --basetemp .harness/state/tester-quality-final` — 307 passed, 1 skipped.

No code changed. No model calls, bakeoff, product-quality evaluation, or held-out access. The initial run using the default temp outside the repo had three manifest test failures; using an in-repo basetemp removed those setup failures.
