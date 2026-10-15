# P3 developer record

## Result

- Status: `PASS` for the reviewed dev calibration gate; held-out remains sealed.
- Requested model: `cx/gpt-5.5`; served model: `gpt-5.5`.
- Prompt: `pairs-v7` with relation-first ordering, explicit Vietnamese CONFLICT/DUPLICATE calibration, exact-span grounding, and the existing fail-closed validator.
- Reviewed input: 7 user decisions (`approve`, `relabel`, `reject`) in `dev_classifier_review.jsonl`; SHA-256 `ec9d084c8f46a83466dc5da41a6db42e6e343b2d235df5af5aee7b65c8ceb038`
- Approved dev gold: 4 rows (CONFLICT 1, DUPLICATE 1, GENERAL_SPECIFIC 2); reviewed rejects are excluded from gold and remain visible to the false-duplicate veto.

## Canonical run

- Report: `evals/contract_graph/reports/l2-p3-classifier-dev.json`.
- Relations returned: 10; raw `UNRELATED` rejections: 23; `duplicate_value_mismatch` validation/policy rejections: 5.
- CONFLICT recall: `1/1`; DUPLICATE recall: `1/1`; observed false DUPLICATE: `0` (one unreviewed false duplicate is reported separately).
- `evaluation_gate=PASS`, `p3_classifier_gate.status=PASS`, `gold_provenance.unapproved=0`, and `invalid_approval=0`.
- Manifest locks the reviewed dev file and the canonical report. The report artifact SHA is `9281c493246ca46964216d540ef0317a1e7f6521ef63583ad3f16d00351fcf27`; the report self-digest is `59ec48bbf671c6dc1b56f0fa389610241a4b2a9c1e2e805df6c378ec4f886bb7`.

## Safety and remaining gate

- The previous weak-label diagnostic treated 215 unreviewed GPT suggestions as recall gold; that path is diagnostic-only and cannot close P3/P5.
- The prompt calibration did not weaken span, citation, model-family, or rejection checks. A reviewed rejection is distinct from an unreviewed or malformed approval value.
- Both provenance guards are covered: a reviewed reject predicted as DUPLICATE is observed false evidence, and malformed/non-human HG-1 rows are rejected before held-out classification.
- P4/HG-2 remains intentionally pending: a human must choose the Wilson lower recall floor and approve any expanded scored gold before P5 can read held-out data. Runtime remains off.


## Final guard hardening

- The HG-1 loader also rejects duplicate selection `pair_id` rows independently of the locked `n_rows` value.
- Regression coverage: `test_heldout_review_loader_rejects_duplicate_selection_ids`.
- Final review verdict: `PASS`; P3 remains `PASS` and P4/HG-2 remains intentionally blocked pending the separate human recall-floor decision.
