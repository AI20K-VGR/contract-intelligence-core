# P3 - classifier calibration

**Status: BLOCKED.**

- Dataset: `dev`; GPT labels are unreviewed suggestions.
- Evaluation gate: `BLOCKED_UNREVIEWED_DEV_GOLD`; approved gold `0`, unapproved gold `215`.
- P3 classifier gate: `BLOCKED`; C/D have no approved dev positives yet.
- Production metric scores `approved=true` only. The weak-label result is retained as diagnosis, never as a recall gate.
- Selected prompt: `pairs-v4`; rejection reason: `pair-rejections-v1`.
- Requested model: `cx/gpt-5.5`; served model: `gpt-5.5`.

## Canonical dev diagnostic

| label | correct/gold (weak diagnostic) | predicted | covered |
| --- | ---: | ---: | ---: |
| CONFLICT | 0/5 | 1 | 1 |
| DUPLICATE | 0/2 | 0 | 0 |
| GENERAL_SPECIFIC | 3/13 | 7 | 7 |
| REFERENCE | 0/4 | 4 | 3 |

- Raw `UNRELATED`: 23
- Validation/policy rejections: 3 (`duplicate_value_mismatch`)
- False `DUPLICATE`: {'observed': 0, 'unreviewed': 0}
- Exact span, citation, model-family, strict approval, P3 gate and rejection telemetry tests: PASS.

## Root cause and disposition

The dev path previously treated all GPT suggestions as recall gold. The labels have no human approval and the independent calibration audit found semantic mismatches with the C/D rubric. The scorer now blocks the gate until a reviewed dev calibration set exists; the P3 classifier gate additionally requires an approved, correctly predicted CONFLICT and DUPLICATE with no observed false DUPLICATE.

The historical v5 prompt probe remains rejected because it introduced a false `DUPLICATE`. Runtime remains off and P4/P5 are not advanced.


## Current reviewed calibration (2026-10-10)

- Status: `P3_PASS_WAITING_HG2`; prompt `pairs-v7`; requested `cx/gpt-5.5`, served `gpt-5.5`.
- User review file: 7 decisions, SHA-256 `ec9d084c8f46a83466dc5da41a6db42e6e343b2d235df5af5aee7b65c8ceb038`; approved gold is CONFLICT 1, DUPLICATE 1, GENERAL_SPECIFIC 2.
- Canonical report: `evals/contract_graph/reports/l2-p3-classifier-dev.json`; artifact SHA-256 `a8aaaf35102c2f19624916aec189e37263d6dca175475b94fc182eee27421e49`.
- Results: 10 relations, 23 raw `UNRELATED` rejections, 5 `duplicate_value_mismatch` rejections; CONFLICT `1/1`, DUPLICATE `1/1`, observed false DUPLICATE `0`.
- The scorer now treats a reviewed rejection as observed negative evidence for the false-DUPLICATE veto while keeping it out of recall gold. A separate regression test covers this case.
- P4/HG-2 remains pending. No held-out data was read or tuned; runtime remains off until the human recall floor and expanded-gold decision are recorded.
