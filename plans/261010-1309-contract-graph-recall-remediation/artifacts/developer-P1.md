# P1 developer record

- Implemented `evals/contract_graph/pairs/recall_diagnostic.py` with safe pair-level taxonomy and aggregate rejection/provider accounting.
- Added TDD coverage for candidate miss, classifier UNRELATED, validation/provider/budget metadata, accounting, and false DUPLICATE hard stop.
- Added `recall-diagnostic` CLI in `evals/contract_graph/pairs/run.py`.
- Generated `evals/contract_graph/reports/l2-p6-recall-diagnostic.json` and `.md` from the six frozen gpt-5.5 snapshots.
- Evidence: focused diagnostic tests 3 passed; full contract graph eval tests 228 passed.
- Observed coverage: B 77/101, C 74/101, E 101/101. All six snapshots reconcile candidate totals with predictions and rejection counts; no hard stops.
- No clause text, spans, prompts, responses, API keys, or held-out label changes were written.
