# Contract graph P1 — recall diagnostic

- Trạng thái: `OBSERVED`.
- Gold positive: `101`; approved: `181`.
- Báo cáo chỉ ghi pair id, metadata candidate và bộ đếm an toàn; không ghi clause text, span, prompt hay response.

## Candidate coverage

| Variant | Covered | Denominator | Rate |
| --- | ---: | ---: | ---: |
| B | 77 | 101 | 0.7624 |
| C | 74 | 101 | 0.7327 |
| E | 101 | 101 | 1.0000 |

## Trial failure taxonomy

### B1

```json
{
  "candidate_accounting": {
    "candidate_total": 165,
    "predicted_in_candidates": 17,
    "rejected_total": 148,
    "unaccounted": 0,
    "unclassified": 0,
    "unknown_predictions": 0
  },
  "failure_counts": {
    "candidate_miss": 24,
    "classifier_unrelated": 64,
    "classifier_wrong_direction": 1,
    "classifier_wrong_label": 11,
    "correct": 1,
    "validation_reject": 2
  },
  "false_duplicate": {
    "observed": 0,
    "unreviewed": 0
  },
  "hard_stops": [],
  "provider_or_budget": {
    "budget": {
      "seconds": 550.0,
      "tokens": 500000
    },
    "classification_failed_traces": 0,
    "elapsed_s": 212.048903,
    "error_types": [],
    "over_budget": false,
    "provider_error_traces": 0,
    "served_models": [
      "gpt-5.5"
    ],
    "trace_count": 27
  },
  "rejection_counts": {
    "bad_span": 0,
    "citation_invalid": 0,
    "conflict_same_span": 0,
    "duplicate_id": 0,
    "duplicate_value_mismatch": 0,
    "invalid_label": 0,
    "malformed": 0,
    "missing_direction": 0,
    "no_answer": 0,
    "reference_explicit": 2,
    "ungrounded_span": 0,
    "unknown_pair": 0,
    "unrelated": 146
  }
}
```

### B2

```json
{
  "candidate_accounting": {
    "candidate_total": 165,
    "predicted_in_candidates": 18,
    "rejected_total": 147,
    "unaccounted": 0,
    "unclassified": 0,
    "unknown_predictions": 0
  },
  "failure_counts": {
    "candidate_miss": 24,
    "classifier_unrelated": 64,
    "classifier_wrong_direction": 2,
    "classifier_wrong_label": 10,
    "correct": 1,
    "validation_reject": 2
  },
  "false_duplicate": {
    "observed": 0,
    "unreviewed": 0
  },
  "hard_stops": [],
  "provider_or_budget": {
    "budget": {
      "seconds": 550.0,
      "tokens": 500000
    },
    "classification_failed_traces": 0,
    "elapsed_s": 215.901555,
    "error_types": [],
    "over_budget": false,
    "provider_error_traces": 0,
    "served_models": [
      "gpt-5.5"
    ],
    "trace_count": 27
  },
  "rejection_counts": {
    "bad_span": 0,
    "citation_invalid": 0,
    "conflict_same_span": 0,
    "duplicate_id": 0,
    "duplicate_value_mismatch": 0,
    "invalid_label": 0,
    "malformed": 0,
    "missing_direction": 0,
    "no_answer": 0,
    "reference_explicit": 2,
    "ungrounded_span": 0,
    "unknown_pair": 0,
    "unrelated": 145
  }
}
```

### C1

```json
{
  "candidate_accounting": {
    "candidate_total": 174,
    "predicted_in_candidates": 33,
    "rejected_total": 141,
    "unaccounted": 0,
    "unclassified": 0,
    "unknown_predictions": 0
  },
  "failure_counts": {
    "candidate_miss": 27,
    "classifier_unrelated": 56,
    "classifier_wrong_direction": 3,
    "classifier_wrong_label": 13,
    "correct": 2,
    "validation_reject": 2
  },
  "false_duplicate": {
    "observed": 0,
    "unreviewed": 0
  },
  "hard_stops": [],
  "provider_or_budget": {
    "budget": {
      "seconds": 550.0,
      "tokens": 500000
    },
    "classification_failed_traces": 0,
    "elapsed_s": 248.7356,
    "error_types": [],
    "over_budget": false,
    "provider_error_traces": 0,
    "served_models": [
      "gpt-5.5"
    ],
    "trace_count": 28
  },
  "rejection_counts": {
    "bad_span": 1,
    "citation_invalid": 0,
    "conflict_same_span": 0,
    "duplicate_id": 0,
    "duplicate_value_mismatch": 0,
    "invalid_label": 0,
    "malformed": 0,
    "missing_direction": 0,
    "no_answer": 0,
    "reference_explicit": 1,
    "ungrounded_span": 0,
    "unknown_pair": 0,
    "unrelated": 139
  }
}
```

### C2

```json
{
  "candidate_accounting": {
    "candidate_total": 174,
    "predicted_in_candidates": 30,
    "rejected_total": 144,
    "unaccounted": 0,
    "unclassified": 0,
    "unknown_predictions": 0
  },
  "failure_counts": {
    "candidate_miss": 27,
    "classifier_unrelated": 58,
    "classifier_wrong_direction": 3,
    "classifier_wrong_label": 12,
    "correct": 1,
    "validation_reject": 1
  },
  "false_duplicate": {
    "observed": 0,
    "unreviewed": 0
  },
  "hard_stops": [],
  "provider_or_budget": {
    "budget": {
      "seconds": 550.0,
      "tokens": 500000
    },
    "classification_failed_traces": 0,
    "elapsed_s": 220.02585,
    "error_types": [],
    "over_budget": false,
    "provider_error_traces": 0,
    "served_models": [
      "gpt-5.5"
    ],
    "trace_count": 28
  },
  "rejection_counts": {
    "bad_span": 0,
    "citation_invalid": 0,
    "conflict_same_span": 0,
    "duplicate_id": 0,
    "duplicate_value_mismatch": 0,
    "invalid_label": 0,
    "malformed": 0,
    "missing_direction": 0,
    "no_answer": 0,
    "reference_explicit": 1,
    "ungrounded_span": 0,
    "unknown_pair": 0,
    "unrelated": 143
  }
}
```

### E1

```json
{
  "candidate_accounting": {
    "candidate_total": 655,
    "predicted_in_candidates": 68,
    "rejected_total": 587,
    "unaccounted": 0,
    "unclassified": 0,
    "unknown_predictions": 0
  },
  "failure_counts": {
    "classifier_unrelated": 80,
    "classifier_wrong_direction": 4,
    "classifier_wrong_label": 14,
    "correct": 3,
    "validation_reject": 0
  },
  "false_duplicate": {
    "observed": 0,
    "unreviewed": 0
  },
  "hard_stops": [],
  "provider_or_budget": {
    "budget": {
      "seconds": 550.0,
      "tokens": 500000
    },
    "classification_failed_traces": 0,
    "elapsed_s": 714.874393,
    "error_types": [],
    "over_budget": true,
    "provider_error_traces": 0,
    "served_models": [
      "gpt-5.5"
    ],
    "trace_count": 89
  },
  "rejection_counts": {
    "bad_span": 0,
    "citation_invalid": 0,
    "conflict_same_span": 0,
    "duplicate_id": 0,
    "duplicate_value_mismatch": 0,
    "invalid_label": 0,
    "malformed": 0,
    "missing_direction": 0,
    "no_answer": 0,
    "reference_explicit": 0,
    "ungrounded_span": 0,
    "unknown_pair": 0,
    "unrelated": 587
  }
}
```

### E2

```json
{
  "candidate_accounting": {
    "candidate_total": 655,
    "predicted_in_candidates": 82,
    "rejected_total": 573,
    "unaccounted": 0,
    "unclassified": 0,
    "unknown_predictions": 0
  },
  "failure_counts": {
    "classifier_unrelated": 74,
    "classifier_wrong_direction": 5,
    "classifier_wrong_label": 17,
    "correct": 5,
    "validation_reject": 1
  },
  "false_duplicate": {
    "observed": 0,
    "unreviewed": 0
  },
  "hard_stops": [],
  "provider_or_budget": {
    "budget": {
      "seconds": 550.0,
      "tokens": 500000
    },
    "classification_failed_traces": 0,
    "elapsed_s": 737.984944,
    "error_types": [],
    "over_budget": true,
    "provider_error_traces": 0,
    "served_models": [
      "gpt-5.5"
    ],
    "trace_count": 89
  },
  "rejection_counts": {
    "bad_span": 1,
    "citation_invalid": 0,
    "conflict_same_span": 0,
    "duplicate_id": 0,
    "duplicate_value_mismatch": 0,
    "invalid_label": 0,
    "malformed": 0,
    "missing_direction": 0,
    "no_answer": 0,
    "reference_explicit": 0,
    "ungrounded_span": 0,
    "unknown_pair": 0,
    "unrelated": 572
  }
}
```

## Provenance

```json
{
  "code_sha256": {
    "ai-service/app/pipeline/contract_graph/pair_candidates.py": "7691ba5691e8d2e69fde9ba6968ca7801321ca2130a3276f4d3476bb23100e85",
    "ai-service/app/pipeline/contract_graph/pair_classifier.py": "95f67eca62e71f0dbdcd6e3eaa7d14b7148692b269ee69d5dd823e612e462397",
    "evals/contract_graph/pairs/bakeoff.py": "a4e8ffe07c877c38fa81c6cd0d8f0e265abd19d23d3341521b97d452795be12e",
    "evals/contract_graph/pairs/predictor.py": "04a42287f8de05bea5e173753cbfcfa21af694f3d6b20422c354d2db9feb3bdb",
    "evals/contract_graph/pairs/recall_diagnostic.py": "0c29adc84a8b46245edcfe29c92257e4558b5b1a624a7e709afeec3e04b4223e"
  },
  "git_head": "533b8e051442d788e58536e0ccc521371c89c412",
  "heldout_decisions_sha256": "1271c998e07c6085345522e0da394b293ae6de6ea19a03b20962170e3f805a64",
  "manifest_sha256": "5ec4686918743e4419e74e4e4da20af1f733732a1f14b378bd8efcb5c9182cd7",
  "requested_models": [
    "cx/gpt-5.5"
  ],
  "review_selection_sha256": "4a11541913acd5fab6e9ec5716fa44d77ded7411d5c4c293f77e55bc2d802d12",
  "served_models": [
    "gpt-5.5"
  ],
  "snapshot_dir": "C:\\Users\\dungs\\OneDrive\\Documents\\VSF-ai2-contract-graph\\.harness\\state\\contract-graph-pairs\\bakeoff-gpt55-final-20261010"
}
```

Hard stops: `none`.
